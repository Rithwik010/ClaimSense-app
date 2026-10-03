"""R05: the member is eligible on every date of service (§8.3)."""

from app.domain.contracts import IntakeClaim, RuleOutcomeValue, RuleResult
from app.rules.reference import MemberRef
from app.rules.results import failed, line_fields, passed


def check_eligibility(claim: IntakeClaim, member: MemberRef) -> RuleResult:
    """Coverage start and end dates are inclusive. `fields_used` is the member ID and every date of
    service (the G1 H5 mapping): a low-confidence date on any line rejects a failing claim."""
    uncovered = [line for line in claim.service_lines if not member.covers(line.date_of_service)]
    end = member.coverage_end.isoformat() if member.coverage_end else "open"
    coverage = f"coverage {member.coverage_start.isoformat()} to {end}"
    fields = ["member_id", *line_fields(len(claim.service_lines), "date_of_service")]
    if not uncovered:
        return passed("R05", f"Every date of service is within {coverage}.", fields)
    dates = ", ".join(line.date_of_service.isoformat() for line in uncovered)
    return failed(
        "R05",
        RuleOutcomeValue.DENY,
        "DN_NOT_ELIGIBLE",
        f"Date of service {dates} is outside {coverage}.",
        fields,
    )
