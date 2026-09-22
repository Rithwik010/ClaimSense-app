"""R05: the member is eligible on every date of service (§8.3)."""

from app.domain.contracts import IntakeClaim, RuleOutcomeValue, RuleResult
from app.rules.reference import MemberRef


def check_eligibility(claim: IntakeClaim, member: MemberRef) -> RuleResult:
    """Coverage start and end dates are inclusive. On failure, `fields_used` names only the dates
    that fall outside coverage, so a low-confidence date on a covered line cannot trigger H5."""
    uncovered = [
        index
        for index, line in enumerate(claim.service_lines)
        if not member.covers(line.date_of_service)
    ]
    end = member.coverage_end.isoformat() if member.coverage_end else "open"
    coverage = f"coverage {member.coverage_start.isoformat()} to {end}"
    if not uncovered:
        return RuleResult(
            rule_id="R05",
            passed=True,
            outcome=RuleOutcomeValue.PASS,
            detail=f"Every date of service is within {coverage}.",
            fields_used=["member_id"]
            + [f"service_lines.{i}.date_of_service" for i in range(len(claim.service_lines))],
        )
    dates = ", ".join(claim.service_lines[i].date_of_service.isoformat() for i in uncovered)
    return RuleResult(
        rule_id="R05",
        passed=False,
        outcome=RuleOutcomeValue.DENY,
        reason_code="DN_NOT_ELIGIBLE",
        detail=f"Date of service {dates} is outside {coverage}.",
        fields_used=["member_id"] + [f"service_lines.{i}.date_of_service" for i in uncovered],
    )
