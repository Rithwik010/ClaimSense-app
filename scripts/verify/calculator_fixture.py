"""Task P2.4: the PFS rows the golden calculator cases need, as a committed fixture, so CI (which
has no data/raw/, H9) runs the golden fee-consistency check (tests/unit/test_golden_files.py).

tests/golden/calculator/raw_subset.json holds, for every procedure code a golden calculator case
has a fee for, its national non-facility total RVU from the PFS RVU26A file (D6), as the decimal
text the file gives. Codes and numbers only: no descriptions are read or written (H10). The
conversion factor and the network percentages come from data/curated/fee_schedule.yaml.

tests/unit/test_calculator_fixture.py checks the fixture holds nothing but codes and RVUs and,
wherever data/raw/ is in use, that it equals a fresh extraction (D-CI-2).

    uv run python -m scripts.verify.calculator_fixture           # compare with data/raw/
    uv run python -m scripts.verify.calculator_fixture --write   # rewrite it (deliberately)
"""

import argparse
import json
from collections.abc import Iterable, Mapping
from decimal import Decimal
from pathlib import Path
from typing import Any

from app.db import raw

ROOT = Path(__file__).resolve().parents[2]
GOLDEN_CALCULATOR = ROOT / "tests" / "golden" / "calculator"
FIXTURE = GOLDEN_CALCULATOR / "raw_subset.json"
NOTE = (
    "Derived from data/raw/ by scripts/verify/calculator_fixture.py for the golden calculator "
    "cases: procedure codes and national non-facility total RVUs only (D-CI-2). Do not edit by "
    "hand."
)
KEYS = ("note", "sources", "nonfacility_total_rvu")


def load_cases(folder: Path = GOLDEN_CALCULATOR) -> list[dict[str, Any]]:
    """Every golden calculator case (files without `cases`, such as this fixture, hold none)."""
    return [
        case
        for path in sorted(folder.glob("*.json"))
        for case in json.loads(path.read_text(encoding="utf-8")).get("cases", [])
    ]


def fee_codes(cases: Iterable[Mapping[str, Any]]) -> list[str]:
    return sorted({code for case in cases for code in case["given"]["fee_schedule"]})


def extract(codes: Iterable[str], rvus: Mapping[str, Decimal]) -> dict[str, Any]:
    return {
        "note": NOTE,
        "sources": [raw.PFS_CSV.relative_to(raw.RAW_DIR).as_posix()],
        "nonfacility_total_rvu": {code: str(rvus[code]) for code in sorted(codes)},
    }


def fresh_fixture() -> dict[str, Any]:
    codes = fee_codes(load_cases())
    pfs = raw.read_pfs(set(codes))
    return extract(codes, {code: entry.nonfacility_total_rvu for code, entry in pfs.items()})


def rvus(fixture: Mapping[str, Any]) -> dict[str, Decimal]:
    return {code: Decimal(value) for code, value in fixture["nonfacility_total_rvu"].items()}


def render(fixture: Mapping[str, Any]) -> str:
    return json.dumps({key: fixture[key] for key in KEYS}, indent=2) + "\n"


def read_fixture(path: Path = FIXTURE) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--write", action="store_true", help="rewrite the committed fixture")
    args = parser.parse_args()
    if not raw.raw_available():
        raise SystemExit("data/raw/ is required to extract the fixture (see SOURCES.md)")
    fixture = fresh_fixture()
    if args.write:
        FIXTURE.write_text(render(fixture), encoding="utf-8")
        print(
            f"wrote {FIXTURE.relative_to(ROOT)}: "
            f"{len(fixture['nonfacility_total_rvu'])} codes with their RVUs"
        )
        return
    same = FIXTURE.exists() and render(read_fixture()) == render(fixture)
    print(f"{FIXTURE.relative_to(ROOT)} {'equals' if same else 'DIFFERS FROM'} a fresh extraction")
    if not same:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
