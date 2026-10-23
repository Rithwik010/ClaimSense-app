"""The gate's status per split and writer (data/generated/v3/gate.jsonl, each sheet's latest note),
with the sheets that have no note yet. Report only.

    uv run python -m scripts.verify.v3_gate_table
"""

import json
from collections import Counter

from training.generate.v3.config import OUT_DIR
from training.generate.v3.dataset import latest, load_sheets, read_jsonl


def gate_table() -> dict:
    sheets = load_sheets(OUT_DIR)
    notes = latest(read_jsonl(OUT_DIR / "notes.jsonl"))
    gate = {g["sheet_id"]: g for g in read_jsonl(OUT_DIR / "gate.jsonl")}
    table: dict[str, Counter[str]] = {}
    for sheet_id, sheet in sheets.items():
        if sheet["writer"] == "H":
            continue
        g = gate.get(sheet_id)
        note = notes.get(sheet_id)
        if note is None:
            state = "no note yet"
        elif g is None or g["attempt"] != note["attempt"]:
            state = "not gated"
        else:
            state = "waiting" if g["pending"] else ("passed" if g["passed"] else "failed")
        table.setdefault(f"{sheet['split']} {sheet['writer']}", Counter())[state] += 1
    return {k: dict(sorted(v.items())) for k, v in sorted(table.items())}


if __name__ == "__main__":
    print(json.dumps(gate_table(), indent=2))
