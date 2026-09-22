"""Review tier, computed by code (INSTRUCTIONS.md §8.5). A model confidence score is not used."""

from app.domain.contracts import Complexity, LineDecision, ReviewTier
from app.ml.validate import ValidationResult


def review_tier(
    result: ValidationResult,
    total_allowed_cents: int,
    low_confidence_fields: list[str],
    high_dollar_cents: int,
) -> ReviewTier:
    output = result.output
    if not result.valid or output is None:
        return ReviewTier.FULL
    decisions = {line.decision for line in output.lines}
    if LineDecision.DENY in decisions or output.complexity is Complexity.HIGH:
        return ReviewTier.FULL
    if (
        LineDecision.PEND in decisions
        or output.complexity is Complexity.MEDIUM
        or total_allowed_cents >= high_dollar_cents
        or low_confidence_fields
    ):
        return ReviewTier.STANDARD
    return ReviewTier.QUICK
