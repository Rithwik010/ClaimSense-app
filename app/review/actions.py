"""Review actions (INSTRUCTIONS.md §8.8): from a decision record awaiting review and a reviewer's
ReviewAction to the final line decisions and final status. Pure functions; the workflow
(app/workflow/finalize.py) locks, recomputes the amounts and writes.

- ACCEPT keeps every line decision as it is, with its source and reason codes.
- The final status follows the claim-decision rule of §8.5: any PEND -> FINAL_PENDED, all DENY ->
  FINAL_DENIED, all APPROVE -> FINAL_APPROVED, APPROVE and DENY -> FINAL_PARTIAL.
- Approved lines count toward the stored accumulators at finalization, FINAL_PENDED included
  (D-REV); pended and denied lines carry no amounts and change nothing.
"""

from dataclasses import dataclass

from app.calculator.engine import Accumulators, CalculationResult
from app.domain.contracts import (
    ClaimDecision,
    ClaimStatus,
    DecisionRecord,
    FinalLineDecision,
    LineDecision,
    ReviewAction,
    ReviewActionType,
)
from app.workflow.decisions import derive_claim_decision

FINAL_STATUS = {
    ClaimDecision.APPROVE: ClaimStatus.FINAL_APPROVED,
    ClaimDecision.DENY: ClaimStatus.FINAL_DENIED,
    ClaimDecision.PEND: ClaimStatus.FINAL_PENDED,
    ClaimDecision.PARTIAL: ClaimStatus.FINAL_PARTIAL,
}


class ReviewRefused(ValueError):
    """The review cannot be applied as given (HTTP 422); the claim stays AWAITING_REVIEW."""


def review_decisions(record: DecisionRecord, action: ReviewAction) -> list[FinalLineDecision]:
    """The final line decisions after the reviewer's action."""
    if action.claim_id != record.claim_id:
        raise ReviewRefused(f"the review is for {action.claim_id}, not {record.claim_id}")
    if action.action is ReviewActionType.ACCEPT:
        return list(record.line_decisions)
    raise ReviewRefused("line overrides are not supported yet")  # P5.3 checkpoint 3


@dataclass(frozen=True)
class Finalization:
    claim_decision: ClaimDecision
    status: ClaimStatus
    accumulators_after: Accumulators
    accumulators_updated: bool  # True when an approved line counted toward the accumulators


def finalization(
    decisions: list[FinalLineDecision], calculation: CalculationResult
) -> Finalization:
    """The final status and the stored accumulators after the claim. The accumulators come from
    the calculator's own working-accumulator logic (A5, A6, the out-of-pocket order A4), which
    counts approved lines only."""
    claim_decision = derive_claim_decision(decisions)
    return Finalization(
        claim_decision=claim_decision,
        status=FINAL_STATUS[claim_decision],
        accumulators_after=calculation.accumulators_after,
        accumulators_updated=any(d.decision is LineDecision.APPROVE for d in decisions),
    )
