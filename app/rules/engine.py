"""Rule evaluation (§8.3, D8): Group A (R01–R04, duplicates) → REJECT and stop; Group B (R05–R10),
all evaluated, REJECT over DENY over PEND, any failure stops; Group C (R11–R13) per line, every line
denied → DENY. The H5 conversion applies to every failure. A claim stopped before Group C has no
line outcomes; a claim that reaches it has one outcome per line.
"""

from collections.abc import Mapping
from typing import Any

from app.domain.contracts import (
    RuleOutcomeValue,
    RuleResult,
    RulesOutcome,
)
from app.rules.confidence import apply_h5
from app.rules.integrity import check_group_a
from app.rules.line_edits import check_line_edits
from app.rules.reference import RulesReference
from app.rules.requirements import check_group_b

# D8: REJECT over DENY over PEND.
PRECEDENCE = (RuleOutcomeValue.REJECT, RuleOutcomeValue.DENY, RuleOutcomeValue.PEND)


def claim_outcome(results: list[RuleResult]) -> RuleOutcomeValue:
    failed = {result.outcome for result in results if not result.passed}
    return next((outcome for outcome in PRECEDENCE if outcome in failed), RuleOutcomeValue.PASS)


def evaluate(
    claim_data: Mapping[str, Any],
    field_confidences: Mapping[str, float],
    reference: RulesReference,
    *,
    confidence_min: float,
) -> RulesOutcome:
    """The v1 rules (RULES_VERSION) on a claim as received. `confidence_min` is the extraction
    confidence threshold (settings `extraction_confidence_min`)."""

    def h5(results: list[RuleResult]) -> list[RuleResult]:
        return [apply_h5(result, field_confidences, confidence_min) for result in results]

    claim, group_a = check_group_a(claim_data, reference)
    group_a = h5(group_a)
    if claim is None or claim_outcome(group_a) is not RuleOutcomeValue.PASS:
        return RulesOutcome(
            claim_outcome=RuleOutcomeValue.REJECT, rule_results=group_a, line_outcomes=[]
        )

    member = reference.members[claim.member_id]
    group_b, flags = check_group_b(claim, member, reference)
    results = group_a + h5(group_b)
    outcome = claim_outcome(results)
    if outcome is not RuleOutcomeValue.PASS:
        return RulesOutcome(
            claim_outcome=outcome, rule_results=results, line_outcomes=[], flags=flags
        )

    group_c, line_outcomes = check_line_edits(claim, reference.plans[member.plan_id], reference)
    results += h5(group_c)
    if claim_outcome(results) is RuleOutcomeValue.REJECT:
        return RulesOutcome(
            claim_outcome=RuleOutcomeValue.REJECT,
            rule_results=results,
            line_outcomes=[],
            flags=flags,
        )
    every_line_denied = all(line.outcome == "DENY" for line in line_outcomes)
    return RulesOutcome(
        claim_outcome=RuleOutcomeValue.DENY if every_line_denied else RuleOutcomeValue.PASS,
        rule_results=results,
        line_outcomes=line_outcomes,
        flags=flags,
    )
