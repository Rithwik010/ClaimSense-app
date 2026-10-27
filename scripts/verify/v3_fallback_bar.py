"""Go / no-go item (a), the fallback bar (D-V3-16): the 12 notes the team judged really wrong in the
hand check of 19 Oct, each the very attempt that was judged (round 3's gate results), through the
final gate code (verify.py with the second look off, D-V3-14, and the lead-line and two-part rules).
Item (a) is met only when all 12 are rejected. Report only.

    uv run python -m scripts.verify.v3_fallback_bar
"""

import json

from scripts.verify.v3_gate_change import REALLY_WRONG
from training.generate.v3.config import OUT_DIR
from training.generate.v3.dataset import lead_fixed, load_sheets, read_jsonl
from training.generate.v3.verify import check_note, filled_target, second_look_on


def fallback_bar() -> dict:
    sheets = load_sheets(OUT_DIR)
    judged = {g["sheet_id"]: g["attempt"] for g in read_jsonl(OUT_DIR / "gate_r3_before_fix.jsonl")}
    notes = {(n["sheet_id"], n["attempt"]): n for n in read_jsonl(OUT_DIR / "notes.jsonl")}
    answers = {(v["sheet_id"], v["attempt"]): v for v in read_jsonl(OUT_DIR / "verifier.jsonl")}
    old_lead = lead_fixed(OUT_DIR)
    rows = {}
    for sheet_id in sorted(REALLY_WRONG):
        attempt = judged[sheet_id]
        note = notes[(sheet_id, attempt)]
        found = (answers.get((sheet_id, attempt)) or {}).get("answers")
        known = {k: tuple(v) for k, v in note["spans"].items()} if note.get("spans") else None
        result = check_note(sheets[sheet_id], note["note"], known, found)
        failures = list(result.failures)
        if attempt <= old_lead.get(sheet_id, 0):
            failures.append("lead: written with a lead line that states a missing fact")
        if not failures and not result.verifier_pending:
            failures += filled_target(sheets[sheet_id], note["note"], result.spans)[1]
        rows[sheet_id] = {"attempt": attempt, "rejected": bool(failures), "failures": failures[:3]}
    rejected = sum(r["rejected"] for r in rows.values())
    return {
        "second_look": second_look_on(),
        "rejected": f"{rejected} of {len(rows)}",
        "met": rejected == len(rows),
        "notes": rows,
    }


if __name__ == "__main__":
    print(json.dumps(fallback_bar(), indent=2))
