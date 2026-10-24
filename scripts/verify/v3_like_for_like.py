"""Step 8 compares like with like (the team's checks of 24 Oct, before go / no-go item g is scored).
Report only.

`prompts`: the prompt Kaggle sent for each record of a set against the prompt the laptop pipeline
builds with its Qdrant lookup; every one must match.

- Kaggle side: the evaluation dataset as Kaggle holds it (`uvx kaggle datasets download <dataset>
  --unzip -p <dir>`). Its runner sends each record's own system and user messages unchanged
  (training/evaluate/model.py `run`, prompt "record"), so their hash is the hash of what was sent;
  the code in the dataset is checked to be byte-identical to this checkout's.
- Laptop side: the pipeline's own steps after the rules (app/workflow/pipeline.py `process_claim`):
  member and network from the database, `prompt_lookups`, `assemble_context` with the
  `ExactCriteriaRetriever` on a Qdrant server, then `render_user_message` and `system_prompt` with
  the settings' prompt version. The database is a fresh one (migrated; the curated data, the
  generated reference and the ICD-10 codes, as tests/e2e/test_parity.py seeds it) and the Qdrant
  collection a fresh one (`build_coverage_collection`, policy set v2), on servers other than the
  demo's (the script refuses the configured ones). The collection's vectors come from a constant
  embedder: the v2 lookup filters and scrolls and never reads them. The rules outcome is the
  record's (the build checked each against the rules engine, `check_record_v2`).

`--control` hides the test-only policies from the lookup (as the training split sees it): every
record on a test-only policy must then differ, which shows the comparison sees retrieval.

`settings`: the model Kaggle ran against its evaluated-model file (training/finetune/evaluated/):
the GGUF's SHA-256 (the notebook's own check, and the run's `<model>-weights.json` when the output
is given), the Ollama version, the Modelfile settings and the request options (D-MODEL-7).

Writes data/generated/eval/v3study/like_for_like-<set>.json.

    uv run python -m scripts.verify.v3_like_for_like --kaggle-data <dir> [--kaggle-output <dir>]
        [--set test_messy] [--database-url <url>] [--qdrant-url <url>]
"""

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from alembic import command
from alembic.config import Config
from qdrant_client import QdrantClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.context.assemble import assemble_context
from app.core.settings import get_settings
from app.db import lookups, raw
from app.db.curated import load_curated
from app.db.models import Icd10Code
from app.db.seed import ICD10_FISCAL_YEAR, load_reference, seed_curated, upsert
from app.domain.contracts import IntakeClaim, Network, RulesOutcome
from app.ml.client import request_options
from app.ml.prompt import render_user_message, system_prompt
from app.rag.knowledge import COVERAGE_COLLECTIONS, build_coverage_collection
from app.rag.retrieve import ExactCriteriaRetriever
from app.workflow.pipeline import prompt_lookups
from training.evaluate.kaggle_eval import STUDY_DIR, read_jsonl
from training.finetune.modelfile import differences, evaluated, settings
from training.generate.common import DEFAULT_SEED
from training.generate.reference import generate_reference
from training.generate.scenarios_v2 import TEST_ONLY_POLICIES

ROOT = Path(__file__).resolve().parents[2]
DATABASE = "claimsense_v3_like_for_like"
CODE = (  # the files the Kaggle runner's prompt and request go through
    "training/evaluate/model.py",
    "training/evaluate/kaggle_eval.py",
    "app/ml/client.py",
    "app/ml/prompt.py",
)


class ConstantEmbedder:  # the v2 exact lookup never reads the vectors
    name = "constant"
    dim = 4

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0, 0.0, 0.0] for _ in texts]

    def embed_query(self, text: str) -> list[float]:
        return [1.0, 0.0, 0.0, 0.0]


def digest(system: str, user: str) -> str:
    return hashlib.sha256(f"{system}\x00{user}".encode()).hexdigest()


def file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fresh_database(server_url: str) -> str:
    url = make_url(server_url).set(database=DATABASE)
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{DATABASE}" WITH (FORCE)'))
        conn.execute(text(f'CREATE DATABASE "{DATABASE}"'))
    admin.dispose()
    rendered = url.render_as_string(hide_password=False)
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", rendered)
    config.attributes["configure_logger"] = False
    command.upgrade(config, "head")
    return rendered


def seed(engine_url: str) -> None:
    reference = generate_reference(DEFAULT_SEED)[0]
    engine = create_engine(engine_url)
    with Session(engine) as session:
        seed_curated(session)
        load_reference(
            session,
            {
                "members": reference.members,
                "providers": reference.providers,
                "provider_networks": reference.provider_networks,
                "visit_usage": reference.visit_usage,
            },
        )
        upsert(
            session,
            Icd10Code,
            [
                {"code": c, "fiscal_year": ICD10_FISCAL_YEAR, "description": d}
                for c, d in raw.read_icd10_codes().items()
            ],
        )
        session.commit()
    engine.dispose()


def first_difference(live: str, sent: str) -> str:
    a, b = live.splitlines(), sent.splitlines()
    for x, y in zip(a, b, strict=False):
        if x != y:
            return f"laptop {x[:120]!r} | Kaggle {y[:120]!r}"
    return f"laptop {len(a)} lines | Kaggle {len(b)} lines"


class HidingTestOnly:  # the control: retrieval as the training split sees it
    def __init__(self, retriever: ExactCriteriaRetriever) -> None:
        self.retriever = retriever

    def retrieve(self, query, plan_id, day, procedure_code=None, exclude_policies=()):  # noqa: ANN001, ANN201
        return self.retriever.retrieve(query, plan_id, day, procedure_code, TEST_ONLY_POLICIES)


def prompts(
    kaggle_data: Path, set_name: str, database_url: str, qdrant_url: str, control: bool = False
) -> dict:
    configured = get_settings()
    if make_url(database_url).port == make_url(configured.database_url).port:
        raise SystemExit("refusing the configured (demo) Postgres server: pass another")
    if qdrant_url.rstrip("/") == configured.qdrant_url.rstrip("/"):
        raise SystemExit("refusing the configured (demo) Qdrant: pass another")
    code = {path: file_sha(ROOT / path) == file_sha(kaggle_data / "code" / path) for path in CODE}
    url = fresh_database(database_url)
    seed(url)
    client = QdrantClient(url=qdrant_url)
    policy_set = configured.policy_set
    points, version = build_coverage_collection(
        client, ConstantEmbedder(), load_curated(policy_set)
    )
    retriever: Any = ExactCriteriaRetriever(client, COVERAGE_COLLECTIONS[policy_set])
    if control:
        retriever = HidingTestOnly(retriever)
    prompt = configured.prompt_version
    system = system_prompt(prompt)
    rows, matched = [], 0
    engine = create_engine(url)
    with Session(engine) as session:
        for shard in sorted((kaggle_data / "sets" / set_name).iterdir()):
            records = read_jsonl(shard / "test.jsonl")
            sidecars = read_jsonl(shard / "test_inputs.jsonl")
            for record, given in zip(records, sidecars, strict=True):
                record_id = record["metadata"]["record_id"]
                sent_system = record["messages"][0]["content"]
                sent_user = record["messages"][1]["content"]
                claim = IntakeClaim.model_validate(given["claim"])
                rules = RulesOutcome.model_validate(given["rules_outcome"])
                member = lookups.get_member(session, claim.member_id)
                if member is None:
                    rows.append({"record_id": record_id, "match": False, "why": "no member"})
                    continue
                network = (
                    Network.IN_NETWORK
                    if lookups.is_in_network(session, claim.billing_npi, member.plan_id)
                    else Network.OUT_OF_NETWORK
                )
                claim_lookups = prompt_lookups(session, claim, policy_set)
                context = assemble_context(
                    session, claim, rules, member.plan_id, network, claim_lookups, retriever
                )
                user = render_user_message(claim, rules, context, claim_lookups, prompt)
                live, sent = digest(system, user), digest(sent_system, sent_user)
                row: dict[str, Any] = {"record_id": record_id, "match": live == sent}
                if live == sent:
                    matched += 1
                else:
                    row["why"] = (
                        "system prompt differs"
                        if system != sent_system
                        else first_difference(user, sent_user)
                    )
                row |= {"laptop_sha256": live[:16], "kaggle_sha256": sent[:16]}
                rows.append(row)
    engine.dispose()
    client.delete_collection(COVERAGE_COLLECTIONS[policy_set])
    return {
        "set": set_name,
        "control": control,
        "prompt_version": prompt,
        "policy_set": policy_set,
        "qdrant": {"url": qdrant_url, "points": points, "knowledge_version": version},
        "code_identical_on_kaggle": code,
        "records": len(rows),
        "matched": matched,
        "all_match": matched == len(rows) and all(code.values()),
        "mismatches": [r for r in rows if not r["match"]],
        "records_checked": rows,
    }


def model_settings(kaggle_data: Path, kaggle_output: Path | None) -> dict:
    run = json.loads((kaggle_data / "run.json").read_text())
    found = {}
    for key, model in run["models"].items():
        pinned = evaluated(model["name"]) or {}
        problems = differences(pinned.get("settings") or {}, settings(model["modelfile"]))
        if model.get("weights_sha256") != pinned.get("weights_sha256"):
            problems.append("weights_sha256 in run.json differs from the evaluated-model file")
        if model.get("ollama") != pinned.get("ollama") or run["ollama"] != pinned.get("ollama"):
            problems.append(f"Ollama {run['ollama']} against the evaluated {pinned.get('ollama')}")
        requests = {"first": request_options(1), "retry": request_options(2)}
        if requests != pinned.get("requests"):
            problems.append(f"request options {requests} against {pinned.get('requests')}")
        ran = None
        if kaggle_output is not None:
            weights = sorted(kaggle_output.rglob(f"{key}-weights.json"))
            ran = json.loads(weights[0].read_text())["sha256"] if weights else None
            if ran != pinned.get("weights_sha256"):
                problems.append(f"the GGUF Kaggle loaded has SHA-256 {ran}")
        found[key] = {
            "model": model["name"],
            "evaluated_file": f"training/finetune/evaluated/{model['name'].replace(':', '-')}.json",
            "weights_sha256_pinned": pinned.get("weights_sha256"),
            "weights_sha256_kaggle_loaded": ran,
            "ollama": run["ollama"],
            "modelfile_settings": settings(model["modelfile"]),
            "request_options": requests,
            "problems": problems,
            "same": not problems,
        }
    return found


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--kaggle-data", type=Path, required=True)
    parser.add_argument("--kaggle-output", type=Path)
    parser.add_argument("--set", default="test_messy")
    parser.add_argument(
        "--database-url", default="postgresql+psycopg://claimsense:claimsense@127.0.0.1:5443/x"
    )
    parser.add_argument("--qdrant-url", default="http://127.0.0.1:6343")
    parser.add_argument("--settings-only", action="store_true")
    parser.add_argument(
        "--control",
        action="store_true",
        help="hide the test-only policies from retrieval: their records must then differ",
    )
    args = parser.parse_args()
    report: dict[str, Any] = {"settings": model_settings(args.kaggle_data, args.kaggle_output)}
    if not args.settings_only:
        report["prompts"] = prompts(
            args.kaggle_data, args.set, args.database_url, args.qdrant_url, args.control
        )
    STUDY_DIR.mkdir(parents=True, exist_ok=True)
    suffix = "-settings" if args.settings_only else "-control" if args.control else ""
    out = STUDY_DIR / f"like_for_like-{args.set}{suffix}.json"
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    summary = {k: {m: v["same"] for m, v in report["settings"].items()} for k in ("settings",)}
    if "prompts" in report:
        p = report["prompts"]
        summary["prompts"] = (
            f"{p['matched']} of {p['records']} match; code {p['code_identical_on_kaggle']}"
        )
        summary["first_mismatches"] = p["mismatches"][:5]
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
