"""What the two-part rule (verify.supports_parts, D-V3-14) changes. Report only.

The gate runs in memory on every sheet's latest note twice, with the rule off and on; the report
counts the notes that pass without it and fail with it (by split and writer), with examples.

    uv run python -m scripts.verify.v3_parts_impact
"""

import json
from collections import Counter

from training.generate.v3 import verify
from training.generate.v3.config import OUT_DIR
from training.generate.v3.dataset import gate_rows, load_sheets


def parts_impact() -> dict:
    sheets = load_sheets(OUT_DIR)
    verify.PARTS_CHECK = False
    off = {r["sheet_id"]: r for r in gate_rows(OUT_DIR)[0]}
    verify.PARTS_CHECK = True
    on = {r["sheet_id"]: r for r in gate_rows(OUT_DIR)[0]}
    passing = [sid for sid, r in off.items() if r["passed"]]
    newly = [sid for sid in passing if not on[sid]["passed"]]
    return {
        "passing_without_the_rule": len(passing),
        "failing_with_it": len(newly),
        "share": round(len(newly) / len(passing), 4),
        "by_split_writer": dict(
            Counter(f"{sheets[s]['split']} {sheets[s]['writer']}" for s in newly).most_common()
        ),
        "examples": {s: [f for f in on[s]["failures"] if "only part" in f] for s in newly[:15]},
    }


if __name__ == "__main__":
    print(json.dumps(parts_impact(), indent=2))
