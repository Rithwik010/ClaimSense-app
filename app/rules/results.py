"""Building `RuleResult`s. `fields_used` holds dotted claim paths with 0-based line indexes (A-R9),
following the H5 field mapping (scripts/verify/golden_checks.py FIELDS_USED, confirmed in G1-G2,
plus member_id for R07 and R09: D-GOLD-4, D-GOLD-5)."""

from app.domain.contracts import RuleOutcomeValue, RuleResult


def line_fields(line_count: int, *names: str) -> list[str]:
    """`service_lines.<i>.<name>` for every line, field by field."""
    return [f"service_lines.{i}.{name}" for name in names for i in range(line_count)]


def passed(rule_id: str, detail: str, fields_used: list[str]) -> RuleResult:
    return RuleResult(
        rule_id=rule_id,
        passed=True,
        outcome=RuleOutcomeValue.PASS,
        detail=detail,
        fields_used=fields_used,
    )


def failed(
    rule_id: str,
    outcome: RuleOutcomeValue,
    reason_code: str,
    detail: str,
    fields_used: list[str],
    line_no: int | None = None,
) -> RuleResult:
    return RuleResult(
        rule_id=rule_id,
        passed=False,
        outcome=outcome,
        reason_code=reason_code,
        detail=detail,
        fields_used=fields_used,
        line_no=line_no,
    )
