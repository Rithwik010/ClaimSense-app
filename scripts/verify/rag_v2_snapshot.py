"""Policies v2, checkpoint 3: the golden snapshot of every in-scope code's v2 criteria (D-RAG-2).

For each procedure code a v2 policy covers, the criteria the exact lookup must return for a date in
the claims window (2026-10-01 to 2026-12-31; every v2 policy is effective from 2026-01-01 for plan
ALL): criterion ID, type and group, in policy-file order. Written from the v2 policy files; the
retrieval test compares the exact lookup with it, so any change to what a code shows the model is
deliberate and visible in the diff.

    uv run python -m scripts.verify.rag_v2_snapshot write   # tests/golden/rag/v2_criteria.json
    uv run python -m scripts.verify.rag_v2_snapshot check   # exit 1 when the file is stale
"""

import argparse
import json
from pathlib import Path
from typing import Any

from app.db.curated import load_curated

ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT = ROOT / "tests" / "golden" / "rag" / "v2_criteria.json"


def snapshot() -> dict[str, Any]:
    curated = load_curated("v2")
    codes: dict[str, list[dict[str, str | None]]] = {}
    for policy in curated.policies.values():
        for criterion in policy.criteria:
            for code in policy.criterion_codes(criterion):
                codes.setdefault(code, []).append(
                    {
                        "criterion_id": criterion.criterion_id,
                        "criterion_type": criterion.criterion_type,
                        "group": criterion.group,
                    }
                )
    return {
        "description": (
            "Policy set v2: the criteria the exact lookup returns for each in-scope code (plan "
            "ALL, effective 2026-01-01), in policy-file order (D-RAG-2). Written by "
            "scripts/verify/rag_v2_snapshot.py from data/curated/coverage_policies/v2/."
        ),
        "codes": {code: codes[code] for code in sorted(codes)},
    }


def render() -> str:
    return json.dumps(snapshot(), indent=2) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("step", choices=("write", "check"))
    step = parser.parse_args().step
    text = render()
    if step == "write":
        SNAPSHOT.write_text(text, encoding="utf-8")
        print(f"wrote {SNAPSHOT.relative_to(ROOT)}: {len(snapshot()['codes'])} codes")
    elif not SNAPSHOT.exists() or SNAPSHOT.read_text(encoding="utf-8") != text:
        raise SystemExit(f"{SNAPSHOT.relative_to(ROOT)} is stale: run the write step")


if __name__ == "__main__":
    main()
