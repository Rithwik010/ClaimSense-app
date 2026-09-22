"""Line decisions and the claim decision, derived by code (INSTRUCTIONS.md §8.5).

The model never decides the claim: each line's decision comes from the rules (R11–R13 denials),
the validated model output, or validation (PEND when the output is invalid), and the claim decision
follows from the line decisions.
"""

from app.domain.contracts import (
    ClaimDecision,
    FinalLineDecision,
    LineDecision,
    RulesOutcome,
)
from app.ml.validate import MODEL_OUTPUT_INVALID, ValidationResult


def final_line_decisions(rules: RulesOutcome, result: ValidationResult) -> list[FinalLineDecision]:
    model_lines = (
        {line.line_no: line for line in result.output.lines}
        if result.valid and result.output
        else {}
    )
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
            decisions.append(
                FinalLineDecision(
                    line_no=line.line_no,
                    decision=line.decision,
                    benefit_category=line.benefit_category,
                    source="MODEL",
                    reason_codes=list(line.reasons),
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
