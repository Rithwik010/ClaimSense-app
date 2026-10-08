"""P5.3: review actions and finalization, pure parts (app/review/actions.py)."""

from datetime import UTC, date, datetime

import pytest

from app.calculator.engine import (
    Accumulators,
    CalcLine,
    CostShareTerms,
    FeeEntry,
    NetworkTerms,
    calculate,
)
from app.domain.contracts import (
    ClaimStatus,
    CostShareRule,
    DecisionRecord,
    FinalLineDecision,
    LineDecision,
    Network,
    ReviewAction,
    RulesOutcome,
    Timestamps,
    Versions,
)
from app.review.actions import ReviewRefused, finalization, review_decisions

APPROVE, DENY, PEND = LineDecision.APPROVE, LineDecision.DENY, LineDecision.PEND
TERMS = NetworkTerms(deductible_cents=50000, coinsurance_bps=2000, oop_max_cents=300000)
IMAGING = CostShareTerms(CostShareRule.DEDUCTIBLE_COINSURANCE, None)
FEES = {"70551": FeeEntry(24425, 19540)}


def decision(line_no: int, value: LineDecision, source: str = "MODEL") -> FinalLineDecision:
    reasons = {
        APPROVE: [],
        DENY: ["DN_NOT_MEDICALLY_NECESSARY"],
        PEND: ["PD_MISSING_DOCUMENTATION"],
    }
    return FinalLineDecision(
        line_no=line_no,
        decision=value,
        benefit_category="ADVANCED_IMAGING",
        source=source,  # type: ignore[arg-type]
        reason_codes=reasons[value],
    )


def run(decisions: list[FinalLineDecision], before: Accumulators):
    lines = [
        CalcLine(d.line_no, "70551", 1, 39000, d.decision, d.benefit_category) for d in decisions
    ]
    calculation = calculate(
        lines, Network.IN_NETWORK, TERMS, {"ADVANCED_IMAGING": IMAGING}, FEES, before
    )
    return calculation, finalization(decisions, calculation)


@pytest.mark.parametrize(
    ("values", "status"),
    [
        ([APPROVE, APPROVE], ClaimStatus.FINAL_APPROVED),
        ([DENY, DENY], ClaimStatus.FINAL_DENIED),
        ([APPROVE, DENY], ClaimStatus.FINAL_PARTIAL),
        ([APPROVE, PEND], ClaimStatus.FINAL_PENDED),
        ([DENY, PEND], ClaimStatus.FINAL_PENDED),
        ([PEND], ClaimStatus.FINAL_PENDED),
    ],
)
def test_the_final_status_follows_the_claim_decision_rule(
    values: list[LineDecision], status: ClaimStatus
) -> None:
    decisions = [decision(n, value) for n, value in enumerate(values, start=1)]

    _, outcome = run(decisions, Accumulators(0, 0))

    assert outcome.status is status


def test_a_pended_claim_counts_its_approved_line_only() -> None:
    """D-REV: approved lines on a FINAL_PENDED claim count toward the accumulators; the pended line
    carries no amounts and changes nothing."""
    before = Accumulators(deductible_met_cents=10000, oop_met_cents=10000)

    calculation, outcome = run([decision(1, APPROVE), decision(2, PEND)], before)

    approved, pended = calculation.amounts.lines
    share = approved.deductible_cents + approved.copay_cents + approved.coinsurance_cents
    assert outcome.status is ClaimStatus.FINAL_PENDED
    assert outcome.accumulators_updated
    assert outcome.accumulators_after == Accumulators(
        before.deductible_met_cents + approved.deductible_cents, before.oop_met_cents + share
    )
    assert (pended.allowed_cents, pended.member_pays_cents) == (0, 0)


def test_no_approved_line_changes_no_accumulator() -> None:
    before = Accumulators(deductible_met_cents=10000, oop_met_cents=10000)

    _, outcome = run([decision(1, DENY), decision(2, PEND)], before)

    assert not outcome.accumulators_updated
    assert outcome.accumulators_after == before


def _record(decisions: list[FinalLineDecision]) -> DecisionRecord:
    return DecisionRecord(
        claim_id="CLM-1",
        status=ClaimStatus.AWAITING_REVIEW,
        rules_outcome=RulesOutcome(claim_outcome="PASS", rule_results=[], line_outcomes=[]),
        line_decisions=decisions,
        versions=Versions(rules_version="1.0.0"),
        timestamps=Timestamps(received=date(2026, 10, 20)),
    )


def test_accept_keeps_every_line_with_its_source_and_reason_codes() -> None:
    decisions = [decision(1, APPROVE), decision(2, DENY, "RULE"), decision(3, PEND, "VALIDATION")]
    action = ReviewAction(
        claim_id="CLM-1", reviewer_id="r1", action="ACCEPT", timestamp=datetime.now(UTC)
    )

    assert review_decisions(_record(decisions), action) == decisions


def test_a_review_for_another_claim_is_refused() -> None:
    action = ReviewAction(
        claim_id="CLM-2", reviewer_id="r1", action="ACCEPT", timestamp=datetime.now(UTC)
    )

    with pytest.raises(ReviewRefused, match="CLM-2"):
        review_decisions(_record([decision(1, APPROVE)]), action)
