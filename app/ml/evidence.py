"""Evidence guard (D-EVID-1): a MET criterion must quote the clinical notes.

A MET criterion whose evidence is not found in the claim's clinical notes (the exact text, as the
evaluation checks it) counts as NOT_DOCUMENTED when the line decision is derived (D-DEC-1). The
model's own answer stays as it is in the decision record (`slm_output`); each changed criterion is
recorded in the record's `output_errors` as `EVIDENCE_NOT_IN_NOTES: line <n> <criterion ID>`, so
the explanation and the review page show it. Such an entry is a check result, not an invalid answer.
"""

from app.domain.contracts import CriterionStatus
from app.ml.validate import ValidationResult

GUARD = "EVIDENCE_NOT_IN_NOTES"  # app/explain/render.py reads these entries by this text


def evidence_guard(result: ValidationResult, notes: str) -> tuple[ValidationResult, list[str]]:
    """The answer with every MET criterion whose evidence is not in the notes made NOT_DOCUMENTED,
    and one note per changed criterion. An invalid answer is returned as it is."""
    if not result.valid or result.output is None:
        return result, []
    found: list[str] = []
    lines = []
    for line in result.output.lines:
        criteria = []
        for criterion in line.criteria:
            if criterion.status is CriterionStatus.MET and criterion.evidence not in notes:
                found.append(f"{GUARD}: line {line.line_no} {criterion.criterion_id}")
                criterion = criterion.model_copy(update={"status": CriterionStatus.NOT_DOCUMENTED})
            criteria.append(criterion)
        lines.append(line.model_copy(update={"criteria": criteria}))
    if not found:
        return result, []
    return ValidationResult(result.output.model_copy(update={"lines": lines}), result.errors), found
