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
from app.rules.engine import claim_outcome
from app.rules.integrity import check_group_a
from app.rules.reference import RulesReference
from app.rules.requirements import check_group_b

GOLDEN = Path(__file__).resolve().parents[1] / "golden" / "rules"
SHARED = json.loads((GOLDEN / "reference.json").read_text(encoding="utf-8"))
CASES = [
    case
    for path in sorted(GOLDEN.glob("*.json"))
    if path.name != "reference.json"
    for case in json.loads(path.read_text(encoding="utf-8"))["cases"]
]
GROUP_A = frozenset({"R01", "R02", "R03", "R04", "DUP"})
GROUP_B = frozenset({"R05", "R06", "R07", "R08", "R09", "R10"})
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


def assert_failures(found: list[dict[str, Any]], expected: list[dict[str, Any]]) -> None:
    """Until H5 is in (checkpoint 3), a failure the case expects as RJ_LOW_CONFIDENCE_FIELD is
    compared by rule and line only."""
    assert [(f["rule_id"], f["line_no"]) for f in found] == [
        (f["rule_id"], f["line_no"]) for f in expected
    ]
    for got, want in zip(found, expected, strict=True):
        if want["reason_code"] != LOW_CONFIDENCE:
            assert got == want


def expected_in(case: dict[str, Any], group: frozenset[str]) -> list[dict[str, Any]]:
    return [f for f in case["expected"]["failures"] if f["rule_id"] in group]


B_CASES = [case for case in CASES if not expected_in(case, GROUP_A)]


def test_there_are_90_cases() -> None:
    assert len(CASES) == 90
    assert len({case["case_id"] for case in CASES}) == 90


@pytest.mark.parametrize("case", CASES, ids=[case["case_id"] for case in CASES])
def test_group_a_finds_the_golden_group_a_failures(case: dict[str, Any]) -> None:
    """Group A alone, on every case."""
    _, results = check_group_a(case["given"]["claim"], reference_for(case))

    assert_failures(failures(results), expected_in(case, GROUP_A))


@pytest.mark.parametrize("case", B_CASES, ids=[case["case_id"] for case in B_CASES])
def test_group_b_finds_the_golden_group_b_failures_and_flags(case: dict[str, Any]) -> None:
    """Group B on every case that passes Group A: its failures, the claim flags and, when Group B
    stops the claim without H5, the claim outcome (D8)."""
    reference = reference_for(case)
    claim, _ = check_group_a(case["given"]["claim"], reference)
    assert claim is not None

    results, flags = check_group_b(claim, reference.members[claim.member_id], reference)

    expected = expected_in(case, GROUP_B)
    assert_failures(failures(results), expected)
    assert flags == case["expected"]["flags"]
    if expected and all(f["reason_code"] != LOW_CONFIDENCE for f in expected):
        assert claim_outcome(results).value == case["expected"]["claim_outcome"]
