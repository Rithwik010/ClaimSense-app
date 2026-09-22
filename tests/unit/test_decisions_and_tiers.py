"""Line and claim decisions (§8.5), review tiers (§8.5) and status transitions (§5)."""

import pytest

from app.domain.contracts import (
    ClaimDecision,
    ClaimStatus,
    Complexity,
    LineDecision,
    LineRuleOutcome,
    ReviewTier,
    RuleOutcomeValue,
    RulesOutcome,
    SLMLine,
    SLMOutput,
)
from app.ml.validate import MODEL_OUTPUT_INVALID, ValidationResult
from app.review.tiers import review_tier
from app.workflow.decisions import derive_claim_decision, final_line_decisions
from app.workflow.states import InvalidTransition, check_transition, is_final

RULES = RulesOutcome(
    claim_outcome=RuleOutcomeValue.PASS,
    rule_results=[],
    line_outcomes=[
        LineRuleOutcome(line_no=1, outcome="PASS"),
        LineRuleOutcome(line_no=2, outcome="DENY", reason_codes=["DN_NCCI_BUNDLED"]),
    ],
)


def slm_line(decision: str, line_no: int = 1) -> SLMLine:
    return SLMLine(
        line_no=line_no,
        decision=LineDecision(decision),
        benefit_category="OFFICE_VISIT_PCP",
        criteria=[],
        reasons=[] if decision == "APPROVE" else ["DN_NOT_MEDICALLY_NECESSARY"],
        missing_information=["x"] if decision == "PEND" else [],
    )


def output(*decisions: str, complexity: str = "LOW") -> SLMOutput:
    lines = [slm_line(d, n) for n, d in enumerate(decisions, start=1)]
    return SLMOutput(lines=lines, complexity=Complexity(complexity))


def test_final_line_decisions_combine_rules_and_model() -> None:
    result = ValidationResult(output=output("APPROVE"), errors=())

    decisions = final_line_decisions(RULES, result)

    assert [(d.line_no, d.decision, d.source, d.reason_codes) for d in decisions] == [
        (1, LineDecision.APPROVE, "MODEL", []),
        (2, LineDecision.DENY, "RULE", ["DN_NCCI_BUNDLED"]),
    ]
    assert decisions[0].benefit_category == "OFFICE_VISIT_PCP"
    assert decisions[1].benefit_category is None


def test_invalid_output_pends_every_model_line() -> None:
    result = ValidationResult(output=output("APPROVE"), errors=("line 1: something",))

    decisions = final_line_decisions(RULES, result)

    assert [(d.decision, d.source, d.reason_codes) for d in decisions] == [
        (LineDecision.PEND, "VALIDATION", [MODEL_OUTPUT_INVALID]),
        (LineDecision.DENY, "RULE", ["DN_NCCI_BUNDLED"]),
    ]
    assert decisions[0].benefit_category is None


@pytest.mark.parametrize(
    ("decisions", "expected"),
    [
        (["APPROVE", "PEND", "DENY"], ClaimDecision.PEND),
        (["DENY", "DENY"], ClaimDecision.DENY),
        (["APPROVE", "APPROVE"], ClaimDecision.APPROVE),
        (["APPROVE", "DENY"], ClaimDecision.PARTIAL),
    ],
)
def test_claim_decision_is_derived_from_line_decisions(decisions, expected) -> None:
    result = ValidationResult(output=output(*decisions), errors=())
    rules = RulesOutcome(
        claim_outcome=RuleOutcomeValue.PASS,
        rule_results=[],
        line_outcomes=[
            LineRuleOutcome(line_no=n, outcome="PASS") for n in range(1, len(decisions) + 1)
        ],
    )

    assert derive_claim_decision(final_line_decisions(rules, result)) is expected


def test_rule_denied_line_counts_toward_the_claim_decision() -> None:
    result = ValidationResult(output=output("APPROVE"), errors=())

    assert derive_claim_decision(final_line_decisions(RULES, result)) is ClaimDecision.PARTIAL


def tier(result: ValidationResult, allowed: int = 0, low: list[str] | None = None) -> ReviewTier:
    return review_tier(result, allowed, low or [], high_dollar_cents=100_000)


@pytest.mark.parametrize(
    ("result", "expected"),
    [
        (ValidationResult(None, ("does not parse",)), ReviewTier.FULL),
        (ValidationResult(output("APPROVE"), ("line 1: bad",)), ReviewTier.FULL),
        (ValidationResult(output("APPROVE", "DENY"), ()), ReviewTier.FULL),
        (ValidationResult(output("APPROVE", complexity="HIGH"), ()), ReviewTier.FULL),
        (ValidationResult(output("PEND"), ()), ReviewTier.STANDARD),
        (ValidationResult(output("APPROVE", complexity="MEDIUM"), ()), ReviewTier.STANDARD),
        (ValidationResult(output("APPROVE"), ()), ReviewTier.QUICK),
    ],
    ids=["unparsed", "invalid", "deny", "high", "pend", "medium", "quick"],
)
def test_review_tier(result: ValidationResult, expected: ReviewTier) -> None:
    assert tier(result) is expected


def test_high_dollar_and_low_confidence_raise_quick_to_standard() -> None:
    quick = ValidationResult(output("APPROVE"), ())

    assert tier(quick, allowed=99_999) is ReviewTier.QUICK
    assert tier(quick, allowed=100_000) is ReviewTier.STANDARD
    assert tier(quick, low=["service_lines.0.units"]) is ReviewTier.STANDARD


def test_allowed_transitions() -> None:
    for status in (
        ClaimStatus.REJECTED,
        ClaimStatus.DENIED_BY_RULE,
        ClaimStatus.PENDED_BY_RULE,
        ClaimStatus.AWAITING_REVIEW,
    ):
        check_transition(ClaimStatus.RECEIVED, status)
    check_transition(ClaimStatus.AWAITING_REVIEW, ClaimStatus.FINAL_PARTIAL)


@pytest.mark.parametrize(
    ("current", "new"),
    [
        (ClaimStatus.RECEIVED, ClaimStatus.FINAL_APPROVED),
        (ClaimStatus.AWAITING_REVIEW, ClaimStatus.RECEIVED),
        (ClaimStatus.DENIED_BY_RULE, ClaimStatus.AWAITING_REVIEW),
        (ClaimStatus.FINAL_APPROVED, ClaimStatus.FINAL_DENIED),
    ],
)
def test_other_transitions_raise(current: ClaimStatus, new: ClaimStatus) -> None:
    with pytest.raises(InvalidTransition, match=f"{current.value} -> {new.value}"):
        check_transition(current, new)


def test_final_statuses() -> None:
    assert is_final(ClaimStatus.REJECTED) and is_final(ClaimStatus.FINAL_PENDED)
    assert not is_final(ClaimStatus.RECEIVED) and not is_final(ClaimStatus.AWAITING_REVIEW)
