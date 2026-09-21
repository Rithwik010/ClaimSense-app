"""Readers for data/raw/ (skipped when the public files are not present, for example in CI)."""

from datetime import date

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


def test_place_of_service_codes() -> None:
    codes = raw.read_place_of_service_codes()
    assert codes["11"] == "Office"
    assert "00" not in codes and "35" not in codes
