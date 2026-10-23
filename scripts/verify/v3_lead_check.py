"""Did any note with a leaky lead line reach a dataset? (D-V3-14, the team's check of 23 Oct.)
Report only.

The sheets whose lead stated part of a criterion they mark missing (data/generated/v3/
lead_fixes.json, from `dataset fix-leads`) got the neutral lead; their old notes fail the gate. This
reports, for those sheets: how many were written again with the neutral lead, how many of those pass
the gate, and how many are left out. Then it checks every final dataset (data/generated/v3/final/):

- no record of such a sheet comes from a note written before the fix (its attempt);
- no note in any split holds one of the old lead wordings (A or B) of phrases/leads.yaml while its
  sheet marks a criterion that lead states as missing.

    uv run python -m scripts.verify.v3_lead_check
"""

import json
from collections import Counter

from training.generate.v3.config import OUT_DIR, phrases
from training.generate.v3.dataset import latest, load_sheets, read_jsonl

SPLITS = ("train", "validation", "test_messy", "test_unseen_style")


def lead_check() -> dict:
    sheets = load_sheets(OUT_DIR)
    fixes = json.loads((OUT_DIR / "lead_fixes.json").read_text())
    notes = latest(read_jsonl(OUT_DIR / "notes.jsonl"))
    gate = {g["sheet_id"]: g for g in read_jsonl(OUT_DIR / "gate.jsonl")}
    state: Counter[str] = Counter()
    by_split: dict[str, Counter[str]] = {}
    for sheet_id, fix in fixes.items():
        note = notes.get(sheet_id)
        g = gate.get(sheet_id)
        if note is None or note["attempt"] <= fix["attempt"]:
            outcome = "left out: not written again"
        elif g and g["attempt"] == note["attempt"] and g["passed"]:
            outcome = "written again and passed"
        elif g and g["attempt"] == note["attempt"] and g["pending"]:
            outcome = "written again, waiting"
        else:
            outcome = "written again, failed: left out"
        state[outcome] += 1
        by_split.setdefault(sheets[sheet_id]["split"], Counter())[outcome] += 1

    wordings: dict[str, set[str]] = {}  # each rule's lead -> every wording it had (A and B)
    for fix in fixes.values():
        for rule in phrases("leads"):
            if rule["lead"] in fix["old"].values():
                wordings.setdefault(rule["lead"], set()).update(fix["old"].values())
    violations = []
    records = 0
    for split in SPLITS:
        path = OUT_DIR / "final" / f"{split}_inputs.jsonl"
        if not path.exists():
            continue
        for row, sidecar in zip(
            read_jsonl(OUT_DIR / "final" / f"{split}.jsonl"), read_jsonl(path), strict=True
        ):
            records += 1
            meta = row["metadata"]
            sheet = sheets[meta["sheet_id"]]
            fix = fixes.get(meta["sheet_id"])
            if fix and meta.get("attempt", 0) <= fix["attempt"]:
                violations.append(f"{split} {meta['sheet_id']}: a note written before the lead fix")
            missing = {f.get("criterion_id") for f in sheet["facts"] if f["status"] == "missing"}
            note = sidecar["claim"]["clinical_notes"]
            for rule in phrases("leads"):
                if not missing & set(rule["states"]):
                    continue
                for wording in wordings.get(rule["lead"], {rule["lead"]}):
                    if wording in note:
                        violations.append(f"{split} {meta['sheet_id']}: {wording!r}")
    return {
        "sheets_with_a_fixed_lead": len(fixes),
        "outcome": dict(state),
        "outcome_by_split": {k: dict(v) for k, v in sorted(by_split.items())},
        "final_records_checked": records,
        "violations": violations,
    }


if __name__ == "__main__":
    print(json.dumps(lead_check(), indent=2))
