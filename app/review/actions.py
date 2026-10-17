"""Review actions (INSTRUCTIONS.md §8.8): from a decision record awaiting review and a reviewer's
ReviewAction to the final line decisions and final status. Pure functions; the workflow
(app/workflow/finalize.py) locks, recomputes the amounts and writes.

- ACCEPT keeps every line decision as it is, with its source and reason codes.
- OVERRIDE changes the decision, the benefit category, or both, of lines the model or the output
  validation decided; rule outcomes (R11-R13 line denials) are automatic and never overridden
  (D-REV-2). An overridden line gets source REVIEWER; every other line keeps its own reason codes.
  An APPROVE line's category is the reviewer's, else the line's current (model) one, else the
  line's only candidate category in the record's context (D-REV-4).
- A DENY or PEND override names its reason code, one of OVERRIDE_REASONS, which becomes the line's
  reason code (its CARC/RARC and plain reason follow from it); an APPROVE override names none and
  the line has no reason code (D-REV-9). The reviewer's free-text reason stays in the audit trail.
- The final status follows the claim-decision rule of §8.5: any PEND -> FINAL_PENDED, all DENY ->
  FINAL_DENIED, all APPROVE -> FINAL_APPROVED, APPROVE and DENY -> FINAL_PARTIAL.
- Approved lines count toward the stored accumulators at finalization, FINAL_PENDED included
  (D-REV-7); pended and denied lines carry no amounts and change nothing.
- Approved lines in a visit-limited benefit category add one visit per distinct date of service
  (D-REV-8), FINAL_PENDED included.
"""

from dataclasses import dataclass
from datetime import date

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


# D-REV-9: the reason codes a reviewer may give. DENY: the line-level denial codes with approved
# CARC/RARC mappings (the model's, then the rules' in rule order, R11 to R21); the claim-level rule
# reasons (R05 to R10) are not line reasons. PEND: the pend reasons (no CARC, D-CARC-1);
# MODEL_OUTPUT_INVALID is an internal marker, not a reason.
OVERRIDE_REASONS: dict[LineDecision, tuple[str, ...]] = {
    LineDecision.DENY: (
        "DN_NOT_MEDICALLY_NECESSARY",
        "DN_CONDITIONAL_EXCLUSION",
        "DN_NCCI_BUNDLED",
        "DN_MUE_EXCEEDED",
        "DN_EXCLUDED",
        "DN_MULTIPLE_BLOCKS",
        "DN_DX_NOT_SUPPORTED",
        "DN_HOME_TEST_PARASOMNIA",
        "DN_ESI_LEVELS",
        "DN_FACET_LEVELS",
        "DN_VISIT_LIMIT",
    ),
    LineDecision.PEND: ("PD_MISSING_DOCUMENTATION", "PD_PROVIDER_ENROLLMENT"),
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
    allowed = OVERRIDE_REASONS.get(override.decision, ())
    if override.reason_code is not None and not allowed:
        raise ReviewRefused(f"line {n}: a reason code goes with a DENY or PEND decision only")
    if allowed and override.reason_code is None:
        raise ReviewRefused(f"line {n}: a {override.decision.value} override needs a reason code")
    if allowed and override.reason_code not in allowed:
        raise ReviewRefused(
            f"line {n}: {override.reason_code} is not a reason for a {override.decision.value} "
            f"override ({', '.join(allowed)})"
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
        reason_codes=[override.reason_code] if override.reason_code else [],
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
    """Every overridden line before and after, with the reviewer's reason and reason code (for the
    audit trail; never for the logs or the provider, the reason may hold clinical detail)."""
    before = {line.line_no: line for line in record.line_decisions}
    after = {line.line_no: line for line in decisions}
    return [
        {
            "line_no": override.line_no,
            "reason": override.reason,
            "reason_code": override.reason_code,
            "before": before[override.line_no].model_dump(mode="json", exclude={"line_no"}),
            "after": after[override.line_no].model_dump(mode="json", exclude={"line_no"}),
        }
        for override in action.line_overrides
    ]


def visit_counts(
    record: DecisionRecord, decisions: list[FinalLineDecision], dates: dict[int, date]
) -> dict[str, int]:
    """The visits the claim adds to each visit-limited benefit category (D-REV-8): one per distinct
    date of service among the approved lines in that category. Pended and denied lines add none.
    The limits are the ones context assembly gave the model."""
    lines = record.context_refs.lines if record.context_refs else []
    limited = {
        fact.benefit_category
        for line in lines
        for fact in line.candidate_benefits
        if fact.visit_limit is not None
    }
    days: dict[str, set[date]] = {}
    for line in decisions:
        if line.decision is LineDecision.APPROVE and line.benefit_category in limited:
            days.setdefault(line.benefit_category, set()).add(dates[line.line_no])
    return {category: len(found) for category, found in sorted(days.items())}


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
