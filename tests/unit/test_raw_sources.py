"""Readers for data/raw/ (skipped when the public files are not present, for example in CI)."""

from datetime import date
from pathlib import Path

import pytest

from app.db import raw
from app.db.curated import load_curated

pytestmark = pytest.mark.skipif(not raw.raw_available(), reason="data/raw/ not present")


def test_icd10_codes_are_fy2027_without_dots() -> None:
    codes = raw.read_icd10_codes()
    assert len(codes) > 70000
    assert "M5416" in codes
    assert "M541" not in codes  # category header, not a billable code


def test_every_in_scope_code_has_a_price_and_mue() -> None:
    scope = set(load_curated().scope)
    pfs = raw.read_pfs(scope)
    mue = raw.read_mue(scope)
    assert set(pfs) == scope and set(mue) == scope
    assert pfs["99213"].nonfacility_total_rvu > 0
    assert {entry.conversion_factor for entry in pfs.values()} == {
        load_curated().fee_rule.conversion_factor
    }


def test_ncci_pairs_include_known_edits() -> None:
    pairs = raw.read_ncci_pairs(set(load_curated().scope))
    active = {
        (p.column1, p.column2): p.modifier_indicator
        for p in pairs
        if p.active_on(date(2026, 10, 1))
    }
    assert active[("45380", "45378")] == "0"
    assert active[("11042", "97597")] == "1"


def test_every_policy_code_is_supported_by_its_article_groups() -> None:
    curated = load_curated()
    articles = raw.read_article_diagnoses({p.billing_article for p in curated.policies.values()})
    icd10 = raw.read_icd10_codes()
    for code, support in curated.diagnosis_support.items():
        article = articles[support.billing_article]
        for alternative in support.alternatives:
            for group in alternative:
                assert article.covered.get(group), (code, group)
                assert article.covered[group] & icd10.keys(), (code, group)


def _part_files(part: str) -> dict[str, Path]:
    folder = raw.NCCI_DIR / f"{raw.NCCI_VERSION}-{part}"
    return {p.suffix.lower(): p for p in folder.iterdir() if p.stem == folder.name}


@pytest.mark.parametrize("part", ["f2", "f3", "f4"])
def test_ncci_xlsx_gives_the_same_edits_as_the_txt(part: str) -> None:
    """G2: the official .xlsx of each part, from the same CMS zip, is read with the same results
    as its .txt: code pairs, modifier indicators, effective and deletion dates, record count."""
    files = _part_files(part)
    from_txt = list(raw.read_ncci_records(files[".txt"]))
    from_xlsx = list(raw.read_ncci_records(files[".xlsx"]))

    assert len(from_txt) == len(from_xlsx) > 600_000
    differing = [
        (n, a, b) for n, (a, b) in enumerate(zip(from_txt, from_xlsx, strict=True)) if a != b
    ]
    assert not differing, differing[:5]


def test_ncci_f1_is_read_from_its_xlsx_with_the_cms_counts() -> None:
    """G2: the f1 .txt was lost (SOURCES.md); its official .xlsx has CMS's 675,157 edit records,
    and f1 to f4 total SOURCES.md's 2,637,645 pairs."""
    files = raw._ncci_files()
    f1 = files[0]
    records = list(raw.read_ncci_records(f1))

    assert f1.name == f"{raw.NCCI_VERSION}-f1.xlsx"
    assert len(records) == 675_157
    assert any(r[0] == "11042" and r[1] == "97597" for r in records)
    assert (
        len(records) + sum(sum(1 for _ in raw.read_ncci_records(path)) for path in files[1:])
        == 2_637_645
    )


def test_place_of_service_codes() -> None:
    codes = raw.read_place_of_service_codes()
    assert codes["11"] == "Office"
    assert "00" not in codes and "35" not in codes


def test_place_of_service_names_that_wrap_in_the_pdf_are_read_whole() -> None:
    """Regression (G2): a name was cut at the PDF's first line break ("On Campus-")."""
    codes = raw.read_place_of_service_codes()

    assert len(codes) == 52
    assert codes["22"] == "On Campus-Outpatient Hospital"
    assert codes["19"] == "Off Campus-Outpatient Hospital"
    assert codes["23"] == "Emergency Room – Hospital"
    assert codes["07"] == "Tribal 638 Free-standing Facility"
    assert codes["72"] == "Rural Health Clinic"  # the next row is an unassigned range
    assert codes["27"] == "Outreach Site/ Street"
    assert not any(name.endswith("Unassigned") for name in codes.values())
