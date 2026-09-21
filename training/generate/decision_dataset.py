"""Decision dataset generator (P3.5, INSTRUCTIONS.md §9.4): chat records for fine-tuning.

Each record is system (prompt `decision_v1`) + user (claim, rules result, plan benefits, retrieved
criteria) + assistant (the target `SLMOutput` as JSON). Structured inputs go to a sidecar file so
the records can be re-rendered (for example with real retrieval after P3.3).

Splits: train and validation use policies marked TRAIN and note template set A. The test split uses
template set B only: about 100 records whose lines come from TEST_ONLY policies (never seen in
training) and the rest from TRAIN policies. The leakage and quality checks run before anything is
written; a failing dataset is not written.

    uv run python -m training.generate.decision_dataset [--seed N] [--train N] [--out DIR]
"""

import argparse
import json
import random
from pathlib import Path
from typing import Any

import jinja2

from app.db.curated import load_curated
from app.ml.prompt import PROMPT_VERSION, PromptLookups, render_user_message, system_prompt
from training.generate.checks import check_record, distribution
from training.generate.claims import claim_decision
from training.generate.common import DEFAULT_SEED, GENERATED_DIR, write_json, write_jsonl
from training.generate.reference import generate_reference
from training.generate.scenarios import GENERATOR_VERSION as SCENARIO_VERSION
from training.generate.scenarios import ScenarioBuilder, ScenarioError

GENERATOR_VERSION = "decision-dataset-v1"
SCENARIO_WEIGHTS = {
    "approve_single": 20,
    "deny_dx": 9,
    "deny_criterion": 11,
    "deny_exclusion": 5,
    "pend_missing": 13,
    "office_visit": 6,
    "office_plus_procedure": 8,
    "office_same_day": 4,
    "same_profile_multi": 8,
    "two_policy": 6,
    "ncci_bypass": 6,
    "rule_denied_line": 4,
}
DEFAULT_SIZES = {"train": 2000, "validation": 300, "test": 300}
TEST_UNSEEN_POLICY_RECORDS = 100
TEMPLATES_DIR = Path(__file__).parent / "templates"
CHARS_PER_TOKEN = 3.5


def prompt_lookups() -> PromptLookups:
    from training.generate.codebook import load_codebook

    codebook = load_codebook()
    return PromptLookups(
        icd10_descriptions=codebook.icd10,
        procedure_descriptions=codebook.curated.descriptions,
        policy_codes={
            p.policy_id: list(p.procedure_codes) for p in codebook.curated.policies.values()
        },
    )


def _records(
    builder: ScenarioBuilder,
    split: str,
    count: int,
    start: int,
    seed: int,
    lookups: PromptLookups,
    skip_types: tuple[str, ...] = (),
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rng = random.Random(f"{seed}-{split}-{start}")
    system = system_prompt()
    records, inputs = [], []
    weighted = {t: w for t, w in SCENARIO_WEIGHTS.items() if t not in skip_types}
    types, weights = list(weighted), list(weighted.values())
    number = start
    while len(records) < count:
        scenario_type = rng.choices(types, weights=weights)[0]
        claim_id = f"CLM-{split[:2].upper()}-{number:05d}"
        try:
            scenario = builder.build(scenario_type, claim_id)
        except ScenarioError:
            continue  # this split's policies cannot produce the type; draw another
        number += 1
        record_id = f"DEC-{split[:2].upper()}-{number:05d}"
        user = render_user_message(scenario.claim, scenario.rules, scenario.context, lookups)
        assert scenario.target is not None
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
            {"role": "assistant", "content": scenario.target.model_dump_json()},
        ]
        metadata = {
            **scenario.metadata(),
            "record_id": record_id,
            "split": split,
            "claim_id": claim_id,
            "seed": seed,
            "dataset_version": GENERATOR_VERSION,
            "scenario_version": SCENARIO_VERSION,
            "prompt_version": PROMPT_VERSION,
            "policy_id": scenario.policy_ids[0] if scenario.policy_ids else None,
            "claim_decision": claim_decision(scenario.line_labels),
        }
        records.append({"messages": messages, "metadata": metadata})
        inputs.append(
            {
                "record_id": record_id,
                "claim": scenario.claim.model_dump(mode="json"),
                "rules_outcome": scenario.rules.model_dump(mode="json"),
                "context": scenario.context.model_dump(mode="json"),
                "target": scenario.target.model_dump(mode="json"),
            }
        )
    return records, inputs


def build_dataset(seed: int = DEFAULT_SEED, sizes: dict[str, int] | None = None) -> dict[str, Any]:
    sizes = sizes or DEFAULT_SIZES
    curated = load_curated()
    reference = generate_reference(DEFAULT_SEED)[0]
    lookups = prompt_lookups()
    train_policies = {p for p, x in curated.policies.items() if x.split == "TRAIN"}
    test_only = {p for p, x in curated.policies.items() if x.split == "TEST_ONLY"}
    everything = train_policies | test_only

    splits: dict[str, tuple[list, list]] = {}
    splits["train"] = _records(
        ScenarioBuilder(seed, "A", train_policies, train_policies, reference),
        "train",
        sizes["train"],
        0,
        seed,
        lookups,
    )
    splits["validation"] = _records(
        ScenarioBuilder(seed + 1, "A", train_policies, train_policies, reference),
        "validation",
        sizes["validation"],
        0,
        seed,
        lookups,
    )
    unseen = min(TEST_UNSEEN_POLICY_RECORDS, sizes["test"] // 3)
    test_unseen = _records(
        ScenarioBuilder(seed + 2, "B", test_only, everything, reference),
        "test",
        unseen,
        0,
        seed,
        lookups,
        skip_types=("office_visit",),  # office visits have no policy, so they test nothing unseen
    )
    test_seen = _records(
        ScenarioBuilder(seed + 3, "B", train_policies, everything, reference),
        "test",
        sizes["test"] - unseen,
        unseen,
        seed,
        lookups,
    )
    splits["test"] = (test_unseen[0] + test_seen[0], test_unseen[1] + test_seen[1])
    return {"splits": splits, "curated": curated, "test_only": test_only}


def run_checks(built: dict[str, Any]) -> dict[str, Any]:
    curated, test_only = built["curated"], built["test_only"]
    problems: list[str] = []
    for split, (records, inputs) in built["splits"].items():
        for record, record_inputs in zip(records, inputs, strict=True):
            for problem in check_record(record_inputs, record["messages"], curated):
                problems.append(f"{record['metadata']['record_id']}: {problem}")
            meta = record["metadata"]
            expected_set = "B" if split == "test" else "A"
            if meta["template_id"] != expected_set:
                problems.append(
                    f"{meta['record_id']}: template set {meta['template_id']} in {split}"
                )
            retrieved = {
                c["policy_id"]
                for line in record_inputs["context"]["lines"]
                for c in line["criteria"]
            }
            if split != "test" and (set(meta["policy_ids"]) | retrieved) & test_only:
                problems.append(f"{meta['record_id']}: test-only policy in {split}")
    train_notes = {i["claim"]["clinical_notes"] for i in built["splits"]["train"][1]}
    shared = sum(
        1 for i in built["splits"]["test"][1] if i["claim"]["clinical_notes"] in train_notes
    )
    if shared:
        problems.append(f"{shared} test notes also appear in train")
    unseen = sum(
        1 for r in built["splits"]["test"][0] if set(r["metadata"]["policy_ids"]) & test_only
    )
    return {"problems": problems, "test_records_with_unseen_policies": unseen}


def record_lengths(records: list[dict[str, Any]]) -> dict[str, int]:
    """Characters per record, and an estimated token count (about 3.5 characters per token for
    this text; the Gemma tokenizer is only on the training machine)."""
    sizes = sorted(sum(len(m["content"]) for m in r["messages"]) for r in records)

    def at(share: float) -> int:
        return sizes[int(share * (len(sizes) - 1))]

    return {
        "p50": at(0.5),
        "p95": at(0.95),
        "max": sizes[-1],
        "tokens_p95": round(at(0.95) / CHARS_PER_TOKEN),
        "tokens_max": round(sizes[-1] / CHARS_PER_TOKEN),
    }


def data_card(built: dict[str, Any], checks: dict[str, Any], seed: int) -> str:
    stats = {split: distribution(records) for split, (records, _) in built["splits"].items()}
    lengths = {split: record_lengths(records) for split, (records, _) in built["splits"].items()}
    tables = [
        ("Line decisions", "line_decisions"),
        ("Reasons", "reasons"),
        ("Claim decisions (lines denied by rules included)", "claim_decisions"),
        ("Complexity", "complexity"),
        ("Scenario types", "scenario_types"),
        ("Benefit categories", "benefit_categories"),
        ("Policies", "policies"),
    ]
    keys = {key: sorted({k for s in stats.values() for k in s[key]}) for _, key in tables}
    environment = jinja2.Environment(
        loader=jinja2.FileSystemLoader(TEMPLATES_DIR), keep_trailing_newline=True
    )
    return environment.get_template("data_card.md.j2").render(
        version=GENERATOR_VERSION,
        scenario_version=SCENARIO_VERSION,
        prompt_version=PROMPT_VERSION,
        seed=seed,
        stats=stats,
        lengths=lengths,
        unseen=checks["test_records_with_unseen_policies"],
        test_only=sorted(built["test_only"]),
        tables=tables,
        keys=keys,
        problems=len(checks["problems"]),
    )


def write_dataset(
    out_dir: Path, seed: int, sizes: dict[str, int], card_path: Path | None
) -> dict[str, Any]:
    built = build_dataset(seed, sizes)
    checks = run_checks(built)
    if checks["problems"]:
        raise SystemExit("dataset checks failed:\n" + "\n".join(checks["problems"][:50]))
    for split, (records, inputs) in built["splits"].items():
        write_jsonl(out_dir / f"{split}.jsonl", records)
        write_jsonl(out_dir / f"{split}_inputs.jsonl", inputs)
    summary = {
        "generator_version": GENERATOR_VERSION,
        "seed": seed,
        "sizes": {split: len(records) for split, (records, _) in built["splits"].items()},
        "distribution": {
            split: distribution(records) for split, (records, _) in built["splits"].items()
        },
        "checks": {"problems": 0, **{k: v for k, v in checks.items() if k != "problems"}},
    }
    write_json(out_dir / "summary.json", summary)
    card = data_card(built, checks, seed)
    (out_dir / "data-card.md").write_text(card, encoding="utf-8")
    if card_path:
        card_path.write_text(card, encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--train", type=int, default=DEFAULT_SIZES["train"])
    parser.add_argument("--validation", type=int, default=DEFAULT_SIZES["validation"])
    parser.add_argument("--test", type=int, default=DEFAULT_SIZES["test"])
    parser.add_argument("--out", type=Path, default=GENERATED_DIR / "decision")
    parser.add_argument(
        "--card", type=Path, default=Path(__file__).resolve().parents[2] / "docs" / "data-card.md"
    )
    args = parser.parse_args()
    sizes = {"train": args.train, "validation": args.validation, "test": args.test}
    summary = write_dataset(args.out, args.seed, sizes, args.card)
    print(json.dumps(summary["sizes"]), "checks passed")


if __name__ == "__main__":
    main()
