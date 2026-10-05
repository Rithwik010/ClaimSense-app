"""P2.4 (D-CI-2): the committed fixture of the PFS rows the golden calculator cases need
(tests/golden/calculator/raw_subset.json, scripts/verify/calculator_fixture.py). It holds only
procedure codes and RVUs (no descriptions, so no AMA CPT descriptor text, H10), covers every code a
golden case gives a fee for and, wherever data/raw/ is in use, equals a fresh extraction."""

import re

import pytest

from scripts.verify.calculator_fixture import (
    FIXTURE,
    KEYS,
    NOTE,
    extract,
    fee_codes,
    fresh_fixture,
    load_cases,
    read_fixture,
    render,
    rvus,
)
from scripts.verify.raw_manifest import MANIFEST, read_manifest
from scripts.verify.rules_fixture import raw_in_use

DATA = read_fixture()
PROCEDURE = re.compile(r"[0-9]{4}[0-9A-Z]|[A-Z][0-9]{4}")
RVU = re.compile(r"[0-9]+(\.[0-9]+)?")


def test_the_fixture_holds_only_codes_and_rvus() -> None:
    assert tuple(DATA) == KEYS
    assert DATA["note"] == NOTE
    assert set(DATA["sources"]) <= {entry.path for entry in read_manifest(MANIFEST)}
    assert all(PROCEDURE.fullmatch(code) for code in DATA["nonfacility_total_rvu"])
    assert all(RVU.fullmatch(value) for value in DATA["nonfacility_total_rvu"].values())


def test_the_fixture_covers_every_code_a_golden_case_gives_a_fee_for() -> None:
    assert list(DATA["nonfacility_total_rvu"]) == fee_codes(load_cases())
    assert len(load_cases()) == 56


def test_the_fixture_is_the_scripts_output_for_its_own_values() -> None:
    """Not edited by hand: extracting from the fixture's values writes the same file."""
    again = extract(fee_codes(load_cases()), rvus(DATA))

    assert render(again) == FIXTURE.read_text(encoding="utf-8")


@pytest.mark.skipif(not raw_in_use(), reason="data/raw/ not present or hidden")
def test_the_fixture_equals_a_fresh_extraction_from_data_raw() -> None:
    """If this fails, data/raw/ or the golden cases changed: rewrite the fixture deliberately with
    `uv run python -m scripts.verify.calculator_fixture --write` and review the diff."""
    assert render(fresh_fixture()) == FIXTURE.read_text(encoding="utf-8")
