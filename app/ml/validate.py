"""Deterministic validation of the model output (INSTRUCTIONS.md §8.5; DECISIONS.md D3 and
2026-09-22).

Every retrieved criterion must appear exactly once for its line (prompt decision_v2), and an APPROVE
line cannot have a criterion that is NOT_MET or NOT_DOCUMENTED.

Any failure makes the whole output invalid: every rules-passed line becomes PEND with reason
MODEL_OUTPUT_INVALID and the claim goes to FULL review. There are no automatic retries. Error
messages name lines, fields and IDs only, never the model's text or the clinical notes.
"""

from collections import Counter
from dataclasses import dataclass

from pydantic import ValidationError

from app.domain.contracts import (
    ContextPackage,
    CriterionStatus,
    LineDecision,
    RulesOutcome,
    SLMOutput,
)
from app.ml.prompt import lines_to_decide

MODEL_OUTPUT_INVALID = "MODEL_OUTPUT_INVALID"


@dataclass(frozen=True)
class ValidationResult:
    output: SLMOutput | None  # kept for the record when it parses, even if a later check fails
    errors: tuple[str, ...]

    @property
    def valid(self) -> bool:
        return not self.errors


def _parse_error(exc: ValidationError) -> str:
    first = exc.errors()[0]
    location = ".".join(str(part) for part in first["loc"]) or "output"
    return f"does not parse as SLMOutput ({location}: {first['msg']})"


def validate_output(text: str, rules: RulesOutcome, context: ContextPackage) -> ValidationResult:
    try:
        output = SLMOutput.model_validate_json(text)
    except ValidationError as exc:
        return ValidationResult(output=None, errors=(_parse_error(exc),))

    errors = []
    expected = lines_to_decide(rules)
    counts = Counter(line.line_no for line in output.lines)
    for line_no in expected:
        if counts[line_no] == 0:
            errors.append(f"line {line_no} is missing from the output")
        elif counts[line_no] > 1:
            errors.append(f"line {line_no} appears {counts[line_no]} times")
    errors += [f"line {n} is not a line to decide" for n in sorted(set(counts) - set(expected))]

    by_line = {line.line_no: line for line in context.lines}
    for line in output.lines:
        line_context = by_line.get(line.line_no)
        if line_context is None or line.line_no not in expected:
            continue
        retrieved = [criterion.criterion_id for criterion in line_context.criteria]
        listed = Counter(result.criterion_id for result in line.criteria)
        for criterion_id in retrieved:
            if listed[criterion_id] == 0:
                errors.append(
                    f"line {line.line_no}: criterion {criterion_id} is missing from the output"
                )
            elif listed[criterion_id] > 1:
                errors.append(
                    f"line {line.line_no}: criterion {criterion_id} appears "
                    f"{listed[criterion_id]} times"
                )
        errors += [
            f"line {line.line_no}: criterion {criterion_id} was not retrieved for this line"
            for criterion_id in listed
            if criterion_id not in retrieved
        ]
        candidates = {fact.benefit_category for fact in line_context.candidate_benefits}
        if line.benefit_category not in candidates:
            errors.append(
                f"line {line.line_no}: benefit category {line.benefit_category} is not a "
                "candidate category"
            )
        if line.decision is not LineDecision.APPROVE and not line.reasons:
            errors.append(f"line {line.line_no}: {line.decision.value} needs at least one reason")
        if line.decision is LineDecision.PEND and not line.missing_information:
            errors.append(f"line {line.line_no}: PEND needs the missing information")
        if line.decision is LineDecision.APPROVE:
            errors += [
                f"line {line.line_no}: APPROVE with criterion {result.criterion_id} "
                f"{result.status.value}"
                for result in line.criteria
                if result.status in (CriterionStatus.NOT_MET, CriterionStatus.NOT_DOCUMENTED)
            ]
    return ValidationResult(output=output, errors=tuple(errors))
