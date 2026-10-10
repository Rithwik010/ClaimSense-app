"""Training readiness gate: everything that must hold before the one fine-tuning run
(docs/training-readiness.md).

Automated checks (all must pass):
  1. dataset is current: generator and prompt versions, and the system prompt text in the records,
     match the code
  2. real retrieval: the dataset was built with the live retriever, and the knowledge version and
     retrieval settings still match
  3. every record passes the leakage and quality checks; splits are separated
  4. retrieval meets the golden target (recall@3 >= 0.85, no result for "no policy" queries)
  5. train/live parity: for sampled records, the live pipeline (database -> context -> retrieval ->
     prompt) produces exactly the training prompt
  6. retrieval rarely misses a criterion the scenario planned (at most 10% of records per split)
  7. estimated lengths fit the training max length
  8. the blind-review set was built with the same retrieval
  9. a baseline evaluation exists for this dataset
Team items are listed with where to record them. It also writes a 20-record review packet and, once
the blind-review sheet is filled in, the reviewers' agreement with the generator's labels.

    uv run python -m training.readiness    # needs seeded Postgres, Qdrant and the embedding model
"""

import csv
import json
import random
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.context.assemble import assemble_context
from app.db import lookups
from app.db.curated import load_curated
from app.db.session import get_engine
from app.domain.contracts import IntakeClaim, Network, RulesOutcome
from app.ml.prompt import PROMPT_VERSION, render_user_message, system_prompt
from app.rag.retrieve import CriteriaRetriever, Retriever
from app.workflow.pipeline import prompt_lookups
from training.finetune.data import CONFIG
from training.generate import decision_dataset
from training.generate.common import GENERATED_DIR

ROOT = Path(__file__).resolve().parents[1]
DECISION_DIR = GENERATED_DIR / "decision"
OUT_DIR = GENERATED_DIR / "readiness"
PARITY_SAMPLE = 25
MAX_MISSED_SHARE = 0.10

TEAM_ITEMS = [
    ("Contracts approved and frozen", "DECISIONS.md 2026-09-22"),
    ("Prompt decision_v2 read and accepted", "DECISIONS.md"),
    (
        "3 policies spot-checked against their LCDs (criteria and which are conditional)",
        "DECISIONS.md",
    ),
    (
        "20 sample records read (notes realistic, evidence, labels): readiness/sample-records.md",
        "DECISIONS.md",
    ),
    (
        "Blind-review sheet filled in; disagreements with the labels discussed",
        "tests/golden/blind_review/review_sheet.csv",
    ),
    ("Visit limits stay out of v1; NCCI bypass modifiers stay XE/XP/XS/XU", "DECISIONS.md"),
    ("Max sequence length 3072 accepted (keeps every record)", "DECISIONS.md"),
    ("Kaggle: phone-verified account, GPU and internet on, Gemma license accepted", "team"),
    ("Dataset uploaded as a PRIVATE Kaggle dataset", "team"),
]


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def load_dataset(directory: Path = DECISION_DIR) -> dict[str, Any]:
    splits = {
        split: (
            read_jsonl(directory / f"{split}.jsonl"),
            read_jsonl(directory / f"{split}_inputs.jsonl"),
        )
        for split in ("train", "validation", "test")
    }
    curated = load_curated()
    return {
        "splits": splits,
        "curated": curated,
        "test_only": {p for p, x in curated.policies.items() if x.split == "TEST_ONLY"},
        "summary": json.loads((directory / "summary.json").read_text()),
    }


def check_current(data: dict[str, Any]) -> list[str]:
    summary = data["summary"]
    problems = []
    if summary.get("generator_version") != decision_dataset.GENERATOR_VERSION:
        problems.append(f"dataset version {summary.get('generator_version')} is out of date")
    system = system_prompt()
    for split, (records, _) in data["splits"].items():
        versions = {r["metadata"]["prompt_version"] for r in records}
        if versions != {PROMPT_VERSION}:
            problems.append(f"{split}: prompt versions {sorted(versions)} != {PROMPT_VERSION}")
        if any(r["messages"][0]["content"] != system for r in records):
            problems.append(f"{split}: system prompt text differs from {PROMPT_VERSION}.txt")
    return problems


def check_retrieval_label(data: dict[str, Any], live_label: str) -> list[str]:
    built_with = data["summary"].get("retrieval", "simulated")
    if built_with == "simulated":
        return ["dataset built with simulated retrieval"]
    if built_with != live_label:
        return [f"dataset retrieval '{built_with}' != live retrieval '{live_label}'"]
    return []


def check_records(data: dict[str, Any]) -> list[str]:
    return decision_dataset.run_checks(data)["problems"]


def check_missed(data: dict[str, Any]) -> tuple[list[str], dict[str, float]]:
    shares = {}
    problems = []
    for split, (records, _) in data["splits"].items():
        missed = sum(1 for r in records if r["metadata"].get("criteria_missed"))
        shares[split] = round(missed / len(records), 4)
        if shares[split] > MAX_MISSED_SHARE:
            problems.append(f"{split}: retrieval missed a planned criterion in {shares[split]:.1%}")
    return problems, shares


def check_lengths(data: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
    lengths = {
        split: decision_dataset.record_lengths(records)
        for split, (records, _) in data["splits"].items()
    }
    limit = CONFIG["max_seq_length"]
    problems = [
        f"{split}: estimated {v['tokens_max']} tokens, over 95% of max length {limit}"
        for split, v in lengths.items()
        if v["tokens_max"] > 0.95 * limit
    ]
    return problems, lengths


class Excluding:
    """The live retriever with the test-only policies left out, as the generator does for the
    training splits (a deliberate generator-only difference)."""

    def __init__(self, retriever: Retriever, excluded: set[str]) -> None:
        self.retriever = retriever
        self.excluded = excluded

    def retrieve(self, query, plan_id, day, procedure_code=None, exclude_policies=()):  # noqa: ANN001, ANN201
        return self.retriever.retrieve(query, plan_id, day, procedure_code, self.excluded)


def check_parity(
    data: dict[str, Any], session: Session, retriever: Retriever, sample: int = PARITY_SAMPLE
) -> list[str]:
    """The live pipeline rebuilds the training prompt exactly (context, retrieval, rendering). The
    rules outcome is taken from the record; the rules engine is checked by its golden cases."""
    problems = []
    for split, (records, inputs) in data["splits"].items():
        chosen = random.Random(f"parity-{split}").sample(
            range(len(records)), min(sample, len(records))
        )
        for index in chosen:
            record, record_inputs = records[index], inputs[index]
            claim = IntakeClaim.model_validate(record_inputs["claim"])
            rules = RulesOutcome.model_validate(record_inputs["rules_outcome"])
            member = lookups.get_member(session, claim.member_id)
            if member is None:
                problems.append(f"{record['metadata']['record_id']}: member not in the database")
                continue
            network = (
                Network.IN_NETWORK
                if lookups.is_in_network(session, claim.billing_npi, member.plan_id)
                else Network.OUT_OF_NETWORK
            )
            claim_lookups = prompt_lookups(session, claim, "v1")  # model v1 (D-POL-2)
            search = retriever if split == "test" else Excluding(retriever, data["test_only"])
            context = assemble_context(
                session, claim, rules, member.plan_id, network, claim_lookups, search
            )
            live = render_user_message(claim, rules, context, claim_lookups).splitlines()
            trained = record["messages"][1]["content"].splitlines()
            if live != trained:
                diff = [(a, b) for a, b in zip(live, trained, strict=False) if a != b]
                first = diff[0] if diff else (f"{len(live)} lines", f"{len(trained)} lines")
                problems.append(
                    f"{record['metadata']['record_id']}: live prompt differs: {first[0][:90]!r} "
                    f"vs {first[1][:90]!r}"
                )
    return problems


def check_blind_review(live_label: str) -> list[str]:
    path = ROOT / "tests" / "golden" / "blind_review" / "claims.json"
    built_with = json.loads(path.read_text()).get("retrieval", "simulated")
    return [] if built_with == live_label else [f"blind review built with '{built_with}'"]


def check_baseline(data: dict[str, Any]) -> tuple[list[str], list[str]]:
    summary = data["summary"]
    matching = []
    for path in sorted((GENERATED_DIR / "eval").glob("baseline*.json")):
        report = json.loads(path.read_text())
        dataset = report["dataset"]
        if (
            dataset.get("generator_version") == summary.get("generator_version")
            and dataset.get("retrieval") == summary.get("retrieval")
            and dataset.get("seed") == summary.get("seed")
            and dataset.get("test_records") == summary["sizes"]["test"]
        ):
            matching.append(report["label"])
    return ([] if matching else ["no baseline evaluation for this dataset"]), matching


def blind_review_agreement(
    sheet: Path = ROOT / "tests" / "golden" / "blind_review" / "review_sheet.csv",
    key_path: Path = GENERATED_DIR / "blind_review" / "answer_key.json",
) -> dict[str, Any] | None:
    """Reviewers' line decisions against the generator's labels (the label audit)."""
    with sheet.open(encoding="utf-8") as f:
        rows = [row for row in csv.DictReader(f) if row["decision"].strip()]
    if not rows or not key_path.exists():
        return None
    key = json.loads(key_path.read_text())["key"]
    compared = []
    for row in rows:
        target = key[row["claim_id"]]["target"]
        line = next(x for x in target["lines"] if x["line_no"] == int(row["line_no"]))
        compared.append(
            {
                "claim_id": row["claim_id"],
                "line_no": row["line_no"],
                "reviewer": row["decision"].strip().upper(),
                "label": line["decision"],
            }
        )
    agree = sum(c["reviewer"] == c["label"] for c in compared)
    return {
        "lines": len(compared),
        "agreement": round(agree / len(compared), 4),
        "disagreements": [c for c in compared if c["reviewer"] != c["label"]],
    }


def sample_packet(data: dict[str, Any], count: int = 20) -> str:
    """Records spread over splits and scenario types, for the team to read."""
    rng = random.Random("packet")
    by_type: dict[str, list[dict[str, Any]]] = {}
    for records, _ in data["splits"].values():
        for record in records:
            by_type.setdefault(record["metadata"]["scenario_type"], []).append(record)
    chosen = []
    while len(chosen) < count:
        for scenario_type in sorted(by_type):
            if len(chosen) < count and by_type[scenario_type]:
                items = by_type[scenario_type]
                chosen.append(items.pop(rng.randrange(len(items))))
    parts = ["# Sample training records for review", ""]
    for record in chosen:
        meta = record["metadata"]
        target = json.dumps(json.loads(record["messages"][2]["content"]), indent=2)
        parts += [
            f"## {meta['record_id']} ({meta['split']}, {meta['scenario_type']})",
            "",
            "```text",
            record["messages"][1]["content"],
            "```",
            "",
            "Target answer:",
            "",
            "```json",
            target,
            "```",
            "",
        ]
    return "\n".join(parts)


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    data = load_dataset()
    retriever, live_label = decision_dataset.live_retriever()
    results: list[tuple[str, list[str], Any]] = []
    results.append(("1 dataset current", check_current(data), None))
    results.append(("2 real retrieval", check_retrieval_label(data, live_label), live_label))
    results.append(("3 record quality checks", check_records(data), None))

    from training.evaluate.rag import evaluate, load_queries

    at_3 = CriteriaRetriever(retriever.client, retriever.embedder, 3, retriever.min_score)
    rag = evaluate(at_3, load_queries())  # P3.3 acceptance is recall@3
    results.append(
        (
            "4 retrieval golden target",
            []
            if rag["passed"]
            else [f"recall {rag['recall_at_k']}, empty {rag['empty_queries_passed']}"],
            {"recall@3": rag["recall_at_k"], "empty": rag["empty_queries_passed"]},
        )
    )
    with Session(get_engine()) as session:
        results.append(("5 train/live parity", check_parity(data, session, retriever), None))
    missed, shares = check_missed(data)
    results.append(("6 retrieval misses", missed, shares))
    too_long, lengths = check_lengths(data)
    results.append(("7 lengths", too_long, {s: v["tokens_max"] for s, v in lengths.items()}))
    results.append(("8 blind review retrieval", check_blind_review(live_label), None))
    no_baseline, baselines = check_baseline(data)
    results.append(("9 baseline evaluation", no_baseline, baselines))

    (OUT_DIR / "sample-records.md").write_text(sample_packet(data), encoding="utf-8")
    agreement = blind_review_agreement()
    lines = ["# Training readiness", ""]
    for name, problems, detail in results:
        status = "PASS" if not problems else "FAIL"
        lines.append(f"- [{status}] {name}" + (f": {detail}" if detail else ""))
        lines += [f"    - {p}" for p in problems[:10]]
    lines += ["", "Team items (record in the place named):", ""]
    decisions = (ROOT / "DECISIONS.md").read_text(encoding="utf-8")
    lines += [
        f"- [{'x' if item.startswith('Contracts') and 'Contracts approved' in decisions else ' '}] "
        f"{item} ({where})"
        for item, where in TEAM_ITEMS
    ]
    lines += ["", "Blind review agreement with the labels:", ""]
    lines.append(json.dumps(agreement, indent=2) if agreement else "- sheet not filled in yet")
    report = "\n".join(lines) + "\n"
    (OUT_DIR / "report.md").write_text(report, encoding="utf-8")
    print(report)
    print(f"review packet: {OUT_DIR / 'sample-records.md'}")
    failed = [name for name, problems, _ in results if problems]
    counts = Counter("FAIL" if p else "PASS" for _, p, _ in results)
    print(f"automated checks: {counts['PASS']} passed, {counts['FAIL']} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
