"""The rules engine against the 90 golden rules cases (tests/golden/rules/, README assumptions
A-R1 to A-R11). Never change an expected value to make a test pass (H12).

Skipped where data/raw/ is absent (CI): the code tables come from the public files.
"""

import json
from functools import cache
from pathlib import Path
from typing import Any

import pytest

from app.db import raw
from app.db.curated import load_curated
from app.db.rules_reference import CodeTables, build_reference, load_code_tables
from app.domain.contracts import RuleResult
from app.rules.integrity import check_group_a
from app.rules.reference import RulesReference

GOLDEN = Path(__file__).resolve().parents[1] / "golden" / "rules"
SHARED = json.loads((GOLDEN / "reference.json").read_text(encoding="utf-8"))
CASES = [
    case
    for path in sorted(GOLDEN.glob("*.json"))
    if path.name != "reference.json"
    for case in json.loads(path.read_text(encoding="utf-8"))["cases"]
]
GROUP_A = frozenset({"R01", "R02", "R03", "R04", "DUP"})
LOW_CONFIDENCE = "RJ_LOW_CONFIDENCE_FIELD"

pytestmark = pytest.mark.skipif(not raw.raw_available(), reason="data/raw/ not present")


@cache
def _code_tables() -> CodeTables:
    return load_code_tables(frozenset(load_curated().scope))


def reference_for(case: dict[str, Any]) -> RulesReference:
    """`reference.json` plus the case's additions (authorizations, claims on file)."""
    additions = case["given"]["reference_additions"]
    return build_reference(
        load_curated(),
        _code_tables(),
        SHARED["members"],
        SHARED["providers"],
        SHARED["provider_networks"],
        [*SHARED["authorizations"], *additions.get("authorizations", [])],
        [*SHARED["existing_claims"], *additions.get("existing_claims", [])],
    )


def failures(results: list[RuleResult]) -> list[dict[str, Any]]:
    return [
        {
            "rule_id": r.rule_id,
            "outcome": r.outcome.value,
            "reason_code": r.reason_code,
            "line_no": r.line_no,
        }
        for r in results
        if not r.passed
    ]


def test_there_are_90_cases() -> None:
    assert len(CASES) == 90
    assert len({case["case_id"] for case in CASES}) == 90


@pytest.mark.parametrize("case", CASES, ids=[case["case_id"] for case in CASES])
def test_group_a_finds_the_golden_group_a_failures(case: dict[str, Any]) -> None:
    """Group A alone, on every case. H5 comes later (checkpoint 3), so a failure the case expects
    as RJ_LOW_CONFIDENCE_FIELD is compared by rule and line only."""
    _, results = check_group_a(case["given"]["claim"], reference_for(case))

    expected = [f for f in case["expected"]["failures"] if f["rule_id"] in GROUP_A]
    found = failures(results)
    assert [(f["rule_id"], f["line_no"]) for f in found] == [
        (f["rule_id"], f["line_no"]) for f in expected
    ]
    for got, want in zip(found, expected, strict=True):
        if want["reason_code"] != LOW_CONFIDENCE:
            assert got == want
