"""More v2-style clean training records for the 40/60 training mix (D-V3-7). Synthetic data only.

v2's training set has 2,000 records; a v3 training split of 6,000 and more needs about two v2
records for every three v3 ones. These come from the v2 generator and its labelling logic
(training/generate/decision_dataset_v2.py, unchanged) with a new seed (`v2_extra.seed`) and record
numbers from `v2_extra.start`, so none is one of v2's own. A record is kept only when:

- its note and its user message repeat no v2 record (train, validation or test);
- its note is no near-duplicate of a v2 test note (5-word shingles, Jaccard of
  `verification.near_duplicate_jaccard` or more); the v3 test notes are checked at the build;
- no line goes beyond its plan's visit limit (D-V3-8);
- it passes v2's own record checks (check_record_v2, through run_checks_v2).

The v2 clean test set is not touched. Written to data/generated/v3/v2_extra/ (git-ignored):
train.jsonl, train_inputs.jsonl and report.json.

    uv run python -m training.generate.v3.v2_extra --count 2600 --v2 data/generated/decision_v2
"""

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from app.db.curated import load_curated
from training.generate.common import DEFAULT_SEED
from training.generate.decision_dataset_v2 import (
    POLICY_SET,
    _records,
    exact_retriever,
    lookups_v2,
    run_checks_v2,
)
from training.generate.reference import generate_reference
from training.generate.scenarios_v2 import (
    TEST_ONLY_POLICIES,
    TRAIN_STYLES,
    ScenarioBuilderV2,
    reference_dicts,
)
from training.generate.v3.config import OUT_DIR, config
from training.generate.v3.verify import near_duplicates
from training.generate.v3.visits import over_limit_lines, usage_index

BATCH = 400


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def user_message(record: dict[str, Any]) -> str:
    return next(m["content"] for m in record["messages"] if m["role"] == "user")


def build_v2_extra(count: int, v2_dir: Path, out_dir: Path = OUT_DIR / "v2_extra") -> dict:
    cfg = config()["v2_extra"]
    curated = load_curated(POLICY_SET)
    reference = generate_reference(DEFAULT_SEED)[0]
    lookups = lookups_v2()
    retriever = exact_retriever()
    train_policies = set(curated.policies) - TEST_ONLY_POLICIES
    builder = ScenarioBuilderV2(
        cfg["seed"] + 10,
        TRAIN_STYLES,
        train_policies,
        set(TEST_ONLY_POLICIES),
        retriever,
        reference,
        lookups,
    )
    v2 = {
        split: (read_jsonl(v2_dir / f"{split}.jsonl"), read_jsonl(v2_dir / f"{split}_inputs.jsonl"))
        for split in ("train", "validation", "test")
    }
    seen_notes = {i["claim"]["clinical_notes"] for _, inputs in v2.values() for i in inputs}
    seen_users = {user_message(r) for records, _ in v2.values() for r in records}
    test_notes = {i["record_id"]: i["claim"]["clinical_notes"] for i in v2["test"][1]}
    plan_of = {m["member_id"]: m["plan_id"] for m in reference.members}
    usage = usage_index(reference_dicts(reference.visit_usage))
    dropped: Counter[str] = Counter()
    records: list[dict[str, Any]] = []
    inputs: list[dict[str, Any]] = []
    start = cfg["start"]
    while len(records) < count:
        batch_records, batch_inputs = _records(
            builder,
            "train",
            BATCH,
            start,
            cfg["seed"],
            lookups,
            forbidden_notes=frozenset(seen_notes),
        )
        start += BATCH
        near = {
            a
            for a, _, _ in near_duplicates(
                {
                    "extra": {i["record_id"]: i["claim"]["clinical_notes"] for i in batch_inputs},
                    "test": test_notes,
                }
            )
        }
        for record, item in zip(batch_records, batch_inputs, strict=True):
            note = item["claim"]["clinical_notes"]
            if note in seen_notes or user_message(record) in seen_users:
                dropped["repeats a v2 or earlier extra record"] += 1
            elif item["record_id"] in near:
                dropped["near-duplicate of a v2 test note"] += 1
            elif over_limit_lines(item["claim"], item["rules_outcome"], plan_of, usage, curated):
                dropped["a line beyond its visit limit"] += 1
            elif len(records) < count:
                records.append(record)
                inputs.append(item)
            seen_notes.add(note)
            seen_users.add(user_message(record))
    checks = run_checks_v2(
        {
            "splits": {"train": (records, inputs), "test": v2["test"]},
            "curated": curated,
            "retriever": retriever,
            "reference": reference,
            "lookups": lookups,
        }
    )
    if checks["problems"]:
        raise SystemExit(
            "v2 extra records fail v2's checks:\n" + "\n".join(checks["problems"][:30])
        )
    write_jsonl(out_dir / "train.jsonl", records)
    write_jsonl(out_dir / "train_inputs.jsonl", inputs)
    report = {
        "records": len(records),
        "seed": cfg["seed"],
        "first_record": records[0]["metadata"]["record_id"] if records else None,
        "dropped": dict(dropped),
        "v2_checks": "passed",
        "decisions": dict(
            Counter(line["decision"] for i in inputs for line in i["target"]["lines"])
        ),
    }
    (out_dir / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--count", type=int, required=True)
    parser.add_argument("--v2", type=Path, required=True, help="the decision_v2 folder")
    parser.add_argument("--out", type=Path, default=OUT_DIR / "v2_extra")
    args = parser.parse_args()
    print(json.dumps(build_v2_extra(args.count, args.v2, args.out), indent=2))


if __name__ == "__main__":
    main()
