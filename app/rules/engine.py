"""Rule evaluation (§8.3). Walking skeleton (P1.5): R05 only.

P2.3 adds Group A (R01–R04, duplicates), the rest of Group B (R06–R10), Group C (R11–R13) and the
H5 conversion. The outcome shape is already final: a claim-level failure stops the claim with no
line outcomes; a passing claim lists one outcome per line.
"""

from app.domain.contracts import (
    IntakeResult,
    LineRuleOutcome,
    RuleOutcomeValue,
    RuleResult,
    RulesOutcome,
)
from app.rules.eligibility import check_eligibility
from app.rules.reference import MemberRef

# D8: REJECT over DENY over PEND.
PRECEDENCE = (RuleOutcomeValue.REJECT, RuleOutcomeValue.DENY, RuleOutcomeValue.PEND)


def claim_outcome(results: list[RuleResult]) -> RuleOutcomeValue:
    failed = {result.outcome for result in results if not result.passed}
    return next((outcome for outcome in PRECEDENCE if outcome in failed), RuleOutcomeValue.PASS)


def evaluate(intake: IntakeResult, member: MemberRef) -> RulesOutcome:
    claim = intake.claim
    results = [check_eligibility(claim, member)]
    outcome = claim_outcome(results)
    if outcome is not RuleOutcomeValue.PASS:
        return RulesOutcome(claim_outcome=outcome, rule_results=results, line_outcomes=[])
    return RulesOutcome(
        claim_outcome=outcome,
        rule_results=results,
        line_outcomes=[
            LineRuleOutcome(line_no=line.line_no, outcome="PASS") for line in claim.service_lines
        ],
    )
