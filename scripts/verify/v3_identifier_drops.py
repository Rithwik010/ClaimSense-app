"""What the invented-identifier check (D-V3-17) took out of a v3 split. Report only.

For each sheet of the split, its latest gate result (data/generated/v3/gate.jsonl):

- `identifier only`: the note fails the gate only on the identifier check, so it passed before the
  check and is out of the dataset because of it;
- `identifier and other`: it fails the identifier check and something else as well, so it was out
  before the check too;
- `passing`: in the dataset (the split's size in data/generated/v3/final/).

Each `identifier only` note is listed with the identifiers the check found.

    uv run python -m scripts.verify.v3_identifier_drops [--split test_unseen_style]
"""

import argparse
import json
from collections import Counter
from typing import Any

from training.generate.v3.config import OUT_DIR
from training.generate.v3.dataset import load_sheets, read_jsonl

PREFIX = "identifier:"


def identifier_drops(split: str) -> dict[str, Any]:
    sheets = load_sheets(OUT_DIR)
    gate = {g["sheet_id"]: g for g in read_jsonl(OUT_DIR / "gate.jsonl")}
    state: Counter[str] = Counter()
    only: dict[str, list[str]] = {}
    kinds: Counter[str] = Counter()
    for sheet_id, sheet in sorted(sheets.items()):
        if sheet["split"] != split or (g := gate.get(sheet_id)) is None:
            continue
        found = [f for f in g["failures"] if f.startswith(PREFIX)]
        if g["passed"]:
            state["passing"] += 1
        elif found and len(found) == len(g["failures"]):
            state["identifier only"] += 1
            only[sheet_id] = found
            kinds.update(f.split("invents a ", 1)[-1].split(":")[0] for f in found)
        elif found:
            state["identifier and other"] += 1
        else:
            state["failing, no identifier"] += 1
    final = OUT_DIR / "final" / f"{split}.jsonl"
    return {
        "split": split,
        "gate_results": dict(state),
        "in_final_dataset": len(read_jsonl(final)) if final.exists() else None,
        "passing_without_the_identifier_check": state["passing"] + state["identifier only"],
        "identifier_kinds": dict(kinds.most_common()),
        "identifier_only": only,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--split", default="test_unseen_style")
    print(json.dumps(identifier_drops(parser.parse_args().split), indent=2))
