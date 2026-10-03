"""P2.3a-ci (D-CI-1): the committed fixture of the raw rows the golden rules cases need
(tests/golden/rules/raw_subset.json, scripts/verify/rules_fixture.py). It holds only codes, dates,
modifier indicators and unit limits (no descriptions, so no AMA CPT descriptor text, H10), and
wherever data/raw/ is in use it equals a fresh extraction."""

import re
from typing import Any

import pytest

from scripts.verify.raw_manifest import MANIFEST, read_manifest
from scripts.verify.rules_fixture import (
    FIXTURE,
    KEYS,
    NOTE,
    case_codes,
    code_tables,
    extract,
    fresh_fixture,
    load_cases,
    raw_in_use,
    read_fixture,
    render,
)

DATA = read_fixture()
ICD10 = re.compile(r"[A-TV-Z][0-9][0-9AB][0-9A-Z]{0,4}")
PROCEDURE = re.compile(r"[0-9]{4}[0-9A-Z]|[A-Z][0-9]{4}")
PLACE = re.compile(r"[0-9]{2}")
DAY = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
INDICATORS = {"0", "1", "9"}


def strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [s for k, v in value.items() for s in [k, *strings(v)]]
    if isinstance(value, list):
        return [s for item in value for s in strings(item)]
    return []


def test_the_fixture_holds_only_codes_dates_indicators_and_limits() -> None:
    assert tuple(DATA) == KEYS
    assert DATA["note"] == NOTE
    assert set(DATA["sources"]) <= {entry.path for entry in read_manifest(MANIFEST)}
    assert list(DATA["icd10_codes"]) == ["2027"]
    assert all(ICD10.fullmatch(code) for code in DATA["icd10_codes"]["2027"])
    assert all(PROCEDURE.fullmatch(code) for code in DATA["procedure_codes"])
    assert all(PLACE.fullmatch(code) for code in DATA["place_of_service_codes"])
    for column1, column2, effective, deletion, indicator in DATA["ncci"]:
        assert PROCEDURE.fullmatch(column1) and PROCEDURE.fullmatch(column2)
        assert DAY.fullmatch(effective) and (deletion is None or DAY.fullmatch(deletion))
        assert indicator in INDICATORS
    assert all(PROCEDURE.fullmatch(code) for code in DATA["mue"])
    assert all(type(units) is int and units >= 1 for units in DATA["mue"].values())


def test_no_text_beyond_codes_and_dates_outside_the_note_and_source_paths() -> None:
    """No descriptor can hide anywhere: every other string is a code, a year, a date or an
    indicator (at most 10 characters: upper case, digits, hyphens)."""
    values = [value for key, value in DATA.items() if key not in ("note", "sources")]

    assert all(re.fullmatch(r"[0-9A-Z-]{1,10}", s) for s in strings(values))


def test_codes_the_real_tables_lack_stay_absent() -> None:
    used = case_codes(load_cases())

    assert "M541" in used.diagnoses and "M541" not in DATA["icd10_codes"]["2027"]
    assert "99999" in used.procedure_codes and "99999" not in DATA["procedure_codes"]
    assert "00" in used.places_of_service and "00" not in DATA["place_of_service_codes"]


def test_the_fixture_is_the_scripts_output_for_its_own_tables() -> None:
    """Not edited by hand: extracting from the fixture's tables writes the same file."""
    again = extract(load_cases(), code_tables(DATA), DATA["sources"])

    assert render(again) == FIXTURE.read_text(encoding="utf-8")


@pytest.mark.skipif(not raw_in_use(), reason="data/raw/ not present or hidden")
def test_the_fixture_equals_a_fresh_extraction_from_data_raw() -> None:
    """If this fails, data/raw/ or the golden cases changed: rewrite the fixture deliberately with
    `uv run python -m scripts.verify.rules_fixture --write` and review the diff."""
    assert render(fresh_fixture()) == FIXTURE.read_text(encoding="utf-8")
