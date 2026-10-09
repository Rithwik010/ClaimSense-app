"""Rule R05 (member eligible on every date of service) against the golden rules cases.

The full engine runs every golden rules case in test_rules_golden.py.
"""

import json
from datetime import date
from pathlib import Path

import pytest

from app.domain.contracts import IntakeClaim, IntakeResult, RuleOutcomeValue, SourceFormat
from app.rules import RULES_VERSION
from app.rules.eligibility import check_eligibility
from app.rules.reference import MemberRef

GOLDEN = Path(__file__).resolve().parents[1] / "golden" / "rules"
CASES = json.loads((GOLDEN / "R05_eligibility.json").read_text())["cases"]
MEMBERS = {
    m["member_id"]: MemberRef(
        member_id=m["member_id"],
        plan_id=m["plan_id"],
        coverage_start=date.fromisoformat(m["coverage_start"]),
        coverage_end=date.fromisoformat(m["coverage_end"]) if m["coverage_end"] else None,
    )
    for m in json.loads((GOLDEN / "reference.json").read_text())["members"]
}


def intake(case: dict) -> IntakeResult:
    given = case["given"]
    return IntakeResult(
        claim=IntakeClaim.model_validate(given["claim"]),
        field_confidences=given["field_confidences"],
        source_format=SourceFormat(given["source_format"]),
    )


@pytest.mark.parametrize("case", CASES, ids=[c["case_id"] for c in CASES])
def test_r05_matches_golden(case: dict) -> None:
    claim = intake(case).claim
    result = check_eligibility(claim, MEMBERS[claim.member_id])
    r05_failures = [f for f in case["expected"]["failures"] if f["rule_id"] == "R05"]

    assert result.rule_id == "R05"
    assert result.passed is not r05_failures
    if r05_failures:
        assert result.outcome is RuleOutcomeValue.DENY
        assert result.reason_code == "DN_NOT_ELIGIBLE"
    else:
        assert result.outcome is RuleOutcomeValue.PASS
        assert result.reason_code is None


def test_failing_result_uses_every_date_of_service() -> None:
    """G1 H5 mapping (P2.3a): every date, not only the uncovered ones, so a low-confidence date on
    any line rejects the claim instead of denying it (the cautious reading)."""
    case = next(c for c in CASES if c["case_id"] == "R05-04")  # line 2 is after coverage ends
    claim = intake(case).claim

    result = check_eligibility(claim, MEMBERS[claim.member_id])

    assert result.fields_used == [
        "member_id",
        "service_lines.0.date_of_service",
        "service_lines.1.date_of_service",
    ]


def test_passing_result_uses_every_date_of_service() -> None:
    case = next(c for c in CASES if c["case_id"] == "R05-03")
    claim = intake(case).claim

    result = check_eligibility(claim, MEMBERS[claim.member_id])

    assert result.fields_used == ["member_id", "service_lines.0.date_of_service"]


def test_rules_version() -> None:
    """v1 rules (P2.3a), rules v2 R14 to R20 (P2.3b) and R11's modifiers (P2.3c, D-RULE-9)."""
    assert RULES_VERSION == "2.1.0"
