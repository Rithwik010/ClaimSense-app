"""Review actions (INSTRUCTIONS.md §8.8): from a decision record awaiting review and a reviewer's
ReviewAction to the final line decisions and final status. Pure functions; the workflow
(app/workflow/finalize.py) locks, recomputes the amounts and writes.

- ACCEPT keeps every line decision as it is, with its source and reason codes.
- OVERRIDE changes the decision, the benefit category, or both, of lines the model or the output
  validation decided; rule outcomes (R11-R13 line denials) are automatic and never overridden
  (D-REV-2). An overridden line gets source REVIEWER and no reason codes; every other line keeps
  its own. An APPROVE line's category is the reviewer's, else the line's current (model) one, else
  the line's only candidate category in the record's context (D-REV-4).
- The final status follows the claim-decision rule of §8.5: any PEND -> FINAL_PENDED, all DENY ->
  FINAL_DENIED, all APPROVE -> FINAL_APPROVED, APPROVE and DENY -> FINAL_PARTIAL.
- Approved lines count toward the stored accumulators at finalization, FINAL_PENDED included
  (D-REV-7); pended and denied lines carry no amounts and change nothing.
"""

from dataclasses import dataclass

from app.calculator.engine import Accumulators, CalculationResult
from app.domain.contracts import (
    ClaimDecision,
    ClaimStatus,
    DecisionRecord,
    FinalLineDecision,
    LineDecision,
    LineOverride,
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


def candidate_categories(record: DecisionRecord) -> dict[int, list[str]]:
    """Each line's candidate benefit categories, as context assembly gave them to the model."""
    if record.context_refs is None:
        return {}
    return {
        line.line_no: [fact.benefit_category for fact in line.candidate_benefits]
        for line in record.context_refs.lines
    }


def _overridden(
    line: FinalLineDecision, override: LineOverride, candidates: list[str]
) -> FinalLineDecision:
    n = line.line_no
    if line.source == "RULE":
        raise ReviewRefused(f"line {n}: rule outcomes are automatic and cannot be overridden")
    if override.benefit_category is not None:
        if override.decision is not LineDecision.APPROVE:
            raise ReviewRefused(f"line {n}: a benefit category goes with an APPROVE decision only")
        if override.benefit_category not in candidates:
            raise ReviewRefused(
                f"line {n}: {override.benefit_category} is not one of the line's candidate "
                f"categories ({', '.join(candidates) or 'none'})"
            )
    category = line.benefit_category
    if override.decision is LineDecision.APPROVE:
        category = override.benefit_category or line.benefit_category
        if category is None and len(candidates) == 1:
            category = candidates[0]
        if category is None:
            raise ReviewRefused(
                f"line {n}: choose the benefit category to approve it under "
                f"({', '.join(candidates) or 'no candidate category'})"
            )
    if override.decision is line.decision and category == line.benefit_category:
        raise ReviewRefused(f"line {n}: the override changes neither the decision nor the category")
    return FinalLineDecision(
        line_no=n,
        decision=override.decision,
        benefit_category=category,
        source="REVIEWER",
        reason_codes=[],
    )


def review_decisions(record: DecisionRecord, action: ReviewAction) -> list[FinalLineDecision]:
    """The final line decisions after the reviewer's action."""
    if action.claim_id != record.claim_id:
        raise ReviewRefused(f"the review is for {action.claim_id}, not {record.claim_id}")
    if action.action is ReviewActionType.ACCEPT:
        return list(record.line_decisions)
    lines = {line.line_no: line for line in record.line_decisions}
    overrides: dict[int, LineOverride] = {}
    for override in action.line_overrides:
        if override.line_no not in lines:
            raise ReviewRefused(f"line {override.line_no} is not on the claim")
        if override.line_no in overrides:
            raise ReviewRefused(f"line {override.line_no} is overridden twice")
        overrides[override.line_no] = override
    candidates = candidate_categories(record)
    return [
        _overridden(line, overrides[line.line_no], candidates.get(line.line_no, []))
        if line.line_no in overrides
        else line
        for line in record.line_decisions
    ]


def changes(
    record: DecisionRecord, action: ReviewAction, decisions: list[FinalLineDecision]
) -> list[dict[str, object]]:
    """Every overridden line before and after, with the reviewer's reason (for the audit trail;
    never for the logs, the reason may hold clinical detail)."""
    before = {line.line_no: line for line in record.line_decisions}
    after = {line.line_no: line for line in decisions}
    return [
        {
            "line_no": override.line_no,
            "reason": override.reason,
            "before": before[override.line_no].model_dump(mode="json", exclude={"line_no"}),
            "after": after[override.line_no].model_dump(mode="json", exclude={"line_no"}),
        }
        for override in action.line_overrides
    ]


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
