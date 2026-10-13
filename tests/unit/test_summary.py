"""D-UI-6: the claim summary for reviewers and admins (app/explain/summary.py), for each path:
approve, pend, deny, a rule rejection and a low-confidence rejection. Why the claim got its review
tier agrees with the tier itself (app/review/tiers.py)."""

import itertools

import pytest

from app.domain.contracts import (
    ClaimStatus,
    Complexity,
    CriterionStatus,
    LineDecision,
    ReviewTier,
    SLMOutput,
)
from app.explain.summary import ClaimSummary, claim_summary, tier_reason
from app.ml.validate import ValidationResult
from app.review.tiers import review_tier
from tests.unit.ui_records import (
    APPROVE,
    CRITERION_TEXT,
    DENY,
    PEND,
    amounts,
    breakdown,
    claim,
    final,
    model_record,
    review,
    rule_record,
)

HIGH = 100_000
TIER_OF_REASON = {
    "the model's answer could not be used": ReviewTier.FULL,
    "a line recommended for denial": ReviewTier.FULL,
    "a high-complexity case": ReviewTier.FULL,
    "a line recommended to pend": ReviewTier.STANDARD,
    "a medium-complexity case": ReviewTier.STANDARD,
    "a high amount": ReviewTier.STANDARD,
    "fields read with low confidence": ReviewTier.STANDARD,
    "every line recommended for approval": ReviewTier.QUICK,
}


def summarize(status, record, confidences=None, lines=1) -> ClaimSummary:  # noqa: ANN001
    return claim_summary(status, record, claim(lines), confidences or {}, 0.85, HIGH)


def texts(summary: ClaimSummary) -> list[str]:
    return [item.text for item in summary.items]


def test_approve_path() -> None:
    record = model_record(
        ClaimStatus.AWAITING_REVIEW,
        [final(1, APPROVE)],
        breakdown(amounts(1, 30000, allowed=24000, copay=5000)),
        tier=ReviewTier.QUICK,
    )

    summary = summarize(ClaimStatus.AWAITING_REVIEW, record)

    assert (summary.outcome, summary.outcome_label) == ("IN_REVIEW", "In review")
    assert texts(summary) == [
        "1 line, $300.00 billed; Quick review: every line recommended for approval.",
        "All checks passed.",
        "Line 1, 64483: Approve. 1 of 1 criteria met.",
        "If accepted: plan pays $190.00, patient pays $50.00.",
    ]


def test_pend_path_then_final() -> None:
    record = model_record(
        ClaimStatus.AWAITING_REVIEW,
        [final(1, APPROVE), final(2, PEND)],
        breakdown(amounts(1, 30000, allowed=24000, copay=5000), amounts(2, 30000)),
        statuses={1: [CriterionStatus.MET], 2: [CriterionStatus.NOT_DOCUMENTED]},
    )
    finalized = record.model_copy(update={"status": ClaimStatus.FINAL_PENDED, "review": review()})

    waiting = texts(summarize(ClaimStatus.AWAITING_REVIEW, record, lines=2))
    final_ = summarize(ClaimStatus.FINAL_PENDED, finalized, lines=2)

    assert waiting[0] == "2 lines, $600.00 billed; Standard review: a line recommended to pend."
    assert waiting[3] == f"Line 2, 99214: Pend. Not documented: {CRITERION_TEXT}"
    assert final_.outcome == "PARTLY_APPROVED"  # one line paid, one pended
    assert texts(final_)[2:] == [
        "Line 1, 64483: Approved. 1 of 1 criteria met.",
        f"Line 2, 99214: Pended. Not documented: {CRITERION_TEXT}",
        "Final: plan pays $190.00, patient pays $50.00.",
        "Outcome: partly approved after review; reviewer-7 accepted the recommendation.",
    ]


def test_deny_path() -> None:
    record = model_record(
        ClaimStatus.AWAITING_REVIEW,
        [final(1, DENY)],
        breakdown(amounts(1, 30000)),
        statuses={1: [CriterionStatus.NOT_MET]},
        tier=ReviewTier.FULL,
    )

    shown = texts(summarize(ClaimStatus.AWAITING_REVIEW, record))

    assert shown[0] == "1 line, $300.00 billed; Full review: a line recommended for denial."
    assert shown[2] == "Line 1, 64483: Deny. Coverage criteria not met."


def test_a_line_denied_by_a_rule_names_the_rule() -> None:
    record = model_record(
        ClaimStatus.AWAITING_REVIEW,
        [final(1, APPROVE), final(2, DENY, "RULE", ["DN_NCCI_BUNDLED"])],
        breakdown(amounts(1, 30000, allowed=24000), amounts(2, 30000)),
        rule_results=[
            *rule_record(
                ClaimStatus.DENIED_BY_RULE, "R11", "DN_NCCI_BUNDLED", [], line_no=2
            ).rules_outcome.rule_results
        ],
        line_flags={1: ["NCCI_BYPASS"]},
    )

    shown = texts(summarize(ClaimStatus.AWAITING_REVIEW, record, lines=2))

    assert shown[1] == (
        "Checks passed for the claim; line 2 denied by a check: Included in another service on "
        "the claim (R11)."
    )
    assert shown[3] == "Line 2, 99214: Deny. Included in another service on the claim (R11)."
    assert shown[-1] == "Flags: an NCCI bypass modifier on line 1."


def test_rule_reject_path() -> None:
    record = rule_record(ClaimStatus.REJECTED, "R04", "RJ_MEMBER_NOT_FOUND", ["member_id"])

    summary = summarize(ClaimStatus.REJECTED, record)

    assert summary.outcome == "REJECTED"
    assert texts(summary) == [
        "1 line, $300.00 billed; decided by the automatic checks, with no review.",
        "Stopped at the checks: Member not found (R04).",
        "Outcome: rejected by the automatic checks.",
    ]


def test_low_confidence_reject_path() -> None:
    record = rule_record(ClaimStatus.REJECTED, "R01", "RJ_LOW_CONFIDENCE_FIELD", ["billing_npi"])

    shown = texts(summarize(ClaimStatus.REJECTED, record, {"billing_npi": 0.0}))

    assert shown[1] == "Stopped at the checks: Part of the claim could not be read clearly (R01)."
    assert shown[2] == "Flags: 1 field read with low confidence."


def test_a_claim_not_processed_yet() -> None:
    summary = summarize(ClaimStatus.RECEIVED, None)

    assert summary.outcome == "NOT_PROCESSED"
    assert texts(summary) == [
        "1 line, $300.00 billed; not processed yet.",
        "Checks not run yet.",
    ]


@pytest.mark.parametrize(
    ("decisions", "complexity", "allowed", "low", "valid"),
    list(
        itertools.product(
            [(APPROVE,), (APPROVE, PEND), (APPROVE, DENY), (PEND, DENY)],
            list(Complexity),
            [0, HIGH],
            [[], ["billing_npi"]],
            [True, False],
        )
    ),
)
def test_the_reason_given_for_the_tier_agrees_with_the_tier(
    decisions: tuple[LineDecision, ...],
    complexity: Complexity,
    allowed: int,
    low: list[str],
    valid: bool,
) -> None:
    lines = [final(n, d) for n, d in enumerate(decisions, start=1)]
    record = model_record(
        ClaimStatus.AWAITING_REVIEW,
        lines,
        breakdown(
            *[amounts(n, HIGH, allowed=allowed // len(lines)) for n, _ in enumerate(lines, 1)]
        ),
        output_errors=[] if valid else ["does not parse as SLMOutput (lines: missing)"],
    )
    output = SLMOutput(lines=record.slm_output.lines, complexity=complexity)
    record = record.model_copy(update={"slm_output": output})
    result = ValidationResult(output, () if valid else ("does not parse",))
    total = record.amounts.totals.allowed_cents

    assert TIER_OF_REASON[tier_reason(record, low, HIGH)] is review_tier(result, total, low, HIGH)
