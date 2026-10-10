"""Line decisions and the claim decision, derived by code (INSTRUCTIONS.md §8.5).

The model never decides the claim: each line's decision comes from the rules (R11–R13 denials),
the validated model output, or validation (PEND when the output is invalid), and the claim decision
follows from the line decisions. A model line's decision is derived from its criterion statuses
(D-DEC-1, `app.ml.derive`); the model's own decision stays in the record's `slm_output`.
"""

from app.domain.contracts import (
    ClaimDecision,
    ContextPackage,
    FinalLineDecision,
    LineDecision,
    RulesOutcome,
)
from app.ml.derive import derive_line
from app.ml.validate import MODEL_OUTPUT_INVALID, ValidationResult


def final_line_decisions(
    rules: RulesOutcome, result: ValidationResult, context: ContextPackage | None = None
) -> list[FinalLineDecision]:
    """`context` gives each line's retrieved criteria (their types and groups) to the derivation;
    without it every criterion counts as outside a group."""
    model_lines = (
        {line.line_no: line for line in result.output.lines}
        if result.valid and result.output
        else {}
    )
    shown = {line.line_no: line.criteria for line in context.lines} if context else {}
    flags = {outcome.line_no: outcome.flags for outcome in rules.line_outcomes}
    decisions = []
    for outcome in rules.line_outcomes:
        if outcome.outcome == "DENY":
            decisions.append(
                FinalLineDecision(
                    line_no=outcome.line_no,
                    decision=LineDecision.DENY,
                    benefit_category=None,
                    source="RULE",
                    reason_codes=list(outcome.reason_codes),
                )
            )
        elif outcome.line_no in model_lines:
            line = model_lines[outcome.line_no]
            derived = derive_line(line, shown.get(line.line_no, []), flags[line.line_no])
            decisions.append(
                FinalLineDecision(
                    line_no=line.line_no,
                    decision=derived.decision,
                    benefit_category=line.benefit_category,
                    source="MODEL",
                    reason_codes=derived.reasons,
                )
            )
        else:
            decisions.append(
                FinalLineDecision(
                    line_no=outcome.line_no,
                    decision=LineDecision.PEND,
                    benefit_category=None,
                    source="VALIDATION",
                    reason_codes=[MODEL_OUTPUT_INVALID],
                )
            )
    return decisions


def derive_claim_decision(decisions: list[FinalLineDecision]) -> ClaimDecision:
    values = {decision.decision for decision in decisions}
    if LineDecision.PEND in values:
        return ClaimDecision.PEND
    if values == {LineDecision.DENY}:
        return ClaimDecision.DENY
    if values == {LineDecision.APPROVE}:
        return ClaimDecision.APPROVE
    return ClaimDecision.PARTIAL
