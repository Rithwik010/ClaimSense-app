"""The rules engine against the 90 golden rules cases (tests/golden/rules/, README assumptions
A-R1 to A-R11). Never change an expected value to make a test pass (H12).

Skipped where data/raw/ is absent (CI): the code tables come from the public files.
"""

import json
from functools import cache
from pathlib import Path
from typing import Any

import pytest

from app.core.settings import Settings
from app.db import raw
from app.db.curated import load_curated
from app.db.rules_reference import CodeTables, build_reference, load_code_tables
from app.domain.contracts import RuleResult
from app.rules.engine import evaluate
from app.rules.reference import RulesReference

GOLDEN = Path(__file__).resolve().parents[1] / "golden" / "rules"
SHARED = json.loads((GOLDEN / "reference.json").read_text(encoding="utf-8"))
CASES = [
    case
    for path in sorted(GOLDEN.glob("*.json"))
    if path.name != "reference.json"
    for case in json.loads(path.read_text(encoding="utf-8"))["cases"]
]
# The claim status a rules outcome leads to (pipeline RULE_STATUS; A-R10: a pass stays RECEIVED).
STATUS = {
    "PASS": "RECEIVED",
    "REJECT": "REJECTED",
    "DENY": "DENIED_BY_RULE",
    "PEND": "PENDED_BY_RULE",
}
CONFIDENCE_MIN = 0.85  # A-R9: EXTRACTION_CONFIDENCE_MIN, which the expected values assume

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
    """Every failing rule as the cases list it: Group A and B in rule order, then Group C by line
    and rule order."""
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


def test_the_cases_threshold_is_the_settings_default() -> None:
    assert Settings.model_fields["extraction_confidence_min"].default == CONFIDENCE_MIN


@pytest.mark.parametrize("case", CASES, ids=[case["case_id"] for case in CASES])
def test_golden_rules_case(case: dict[str, Any]) -> None:
    given, expected = case["given"], case["expected"]

    outcome = evaluate(
        given["claim"],
        given["field_confidences"],
        reference_for(case),
        confidence_min=CONFIDENCE_MIN,
    )

    assert outcome.claim_outcome.value == expected["claim_outcome"]
    assert STATUS[outcome.claim_outcome.value] == expected["status"]
    assert failures(outcome.rule_results) == expected["failures"]
    if expected["line_outcomes"] is None:
        assert outcome.line_outcomes == []
    else:
        assert [o.model_dump() for o in outcome.line_outcomes] == expected["line_outcomes"]
    assert outcome.flags == expected["flags"]
