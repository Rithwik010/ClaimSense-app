"""H5 conversion (§8.3): a failing rule whose `fields_used` includes a field read below the
extraction confidence threshold becomes REJECT RJ_LOW_CONFIDENCE_FIELD, never DENY.

`field_confidences` keys are dotted paths with 0-based indexes; a key counts for a field when it is
the field or inside it (`diagnoses.0` is inside `diagnoses`). Below the threshold means strictly
less than it (A-R9).
"""

from collections.abc import Mapping

from app.domain.contracts import RuleOutcomeValue, RuleResult

LOW_CONFIDENCE_REASON = "RJ_LOW_CONFIDENCE_FIELD"


def low_confidence_fields(
    fields_used: list[str], field_confidences: Mapping[str, float], threshold: float
) -> list[str]:
    return sorted(
        path
        for path, value in field_confidences.items()
        if value < threshold
        and any(path == field or path.startswith(f"{field}.") for field in fields_used)
    )


def apply_h5(
    result: RuleResult, field_confidences: Mapping[str, float], threshold: float
) -> RuleResult:
    if result.passed:
        return result
    low = low_confidence_fields(result.fields_used, field_confidences, threshold)
    if not low:
        return result
    shown = ", ".join(f"{path} ({field_confidences[path]:.2f})" for path in low)
    return result.model_copy(
        update={
            "outcome": RuleOutcomeValue.REJECT,
            "reason_code": LOW_CONFIDENCE_REASON,
            "detail": (
                f"{result.detail} Read with confidence below {threshold:.2f}: {shown}; "
                f"{result.reason_code} becomes {LOW_CONFIDENCE_REASON} (H5)."
            ),
        }
    )
