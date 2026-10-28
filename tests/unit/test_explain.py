"""P5.4: the explanation rendered from the decision record (app/explain/render.py). Every amount and
reason it shows matches the record (tests/explain_support.py); the end-to-end test runs the same
check on every golden case."""

from datetime import UTC, date, datetime

import pytest

from app.domain.contracts import (
    AmountTotals,
    ClaimStatus,
    ContextPackage,
    CostBreakdown,
    CriterionResult,
    DecisionRecord,
    FinalLineDecision,
    LineAmounts,
    LineContext,
    LineDecision,
    LineOverride,
    Network,
    RetrievedCriterion,
    ReviewAction,
    RuleResult,
    RulesOutcome,
    SLMLine,
    SLMOutput,
    Timestamps,
    Versions,
)
from app.explain.render import money, render, view
from tests.explain_support import html_mismatches, mismatches

APPROVE, DENY, PEND = LineDecision.APPROVE, LineDecision.DENY, LineDecision.PEND
FIELDS = [name for name in LineAmounts.model_fields if name.endswith("_cents")]


def line_amounts(line_no: int, billed: int, allowed: int, plan: int, member: int) -> LineAmounts:
    values = dict.fromkeys(FIELDS, 0)
    values.update(
        billed_cents=billed,
        allowed_cents=allowed,
        contractual_adjustment_cents=billed - allowed,
        coinsurance_cents=member,
        plan_pays_cents=plan,
        member_pays_cents=member,
    )
    return LineAmounts(line_no=line_no, **values)


def breakdown(*lines: LineAmounts) -> CostBreakdown:
    totals = {name: sum(getattr(line, name) for line in lines) for name in FIELDS}
    return CostBreakdown(lines=list(lines), totals=AmountTotals(**totals))


def criterion(cid: str, text: str) -> RetrievedCriterion:
    return RetrievedCriterion(
        criterion_id=cid,
        policy_id=cid.split(".")[0],
        policy_title="Brain MRI",
        text=text,
        source="L37373",
        effective_date=date(2026, 1, 1),
    )


def record(
    status: ClaimStatus,
    decisions: list[FinalLineDecision],
    amounts: CostBreakdown | None,
    review: ReviewAction | None = None,
    evidence: str = "Headache for 6 weeks with new focal weakness.",
) -> DecisionRecord:
    rules = [
        RuleResult(rule_id="R01", passed=True, outcome="PASS", detail="All fields", fields_used=[]),
        RuleResult(
            rule_id="R12",
            passed=True,
            outcome="PASS",
            detail="Units within the MUE",
            fields_used=[],
            line_no=1,
        ),
    ]
    return DecisionRecord(
        claim_id="CLM-EXP-00001",
        status=status,
        rules_outcome=RulesOutcome(claim_outcome="PASS", rule_results=rules, line_outcomes=[]),
        context_refs=ContextPackage(
            claim_id="CLM-EXP-00001",
            plan_id="PLN-PPO-GOLD",
            plan_type="PPO",
            network=Network.IN_NETWORK,
            excluded_codes=[],
            lines=[
                LineContext(
                    line_no=n,
                    procedure_code=code,
                    candidate_benefits=[],
                    criteria=[criterion("POL-IMG-001.c1", "Neurologic deficit documented.")],
                )
                for n, code in ((1, "70551"), (2, "70553"))
            ],
        ),
        slm_output=SLMOutput(
            lines=[
                SLMLine(
                    line_no=n,
                    decision=d,
                    benefit_category="ADVANCED_IMAGING",
                    criteria=[
                        CriterionResult(
                            criterion_id="POL-IMG-001.c1",
                            status="MET" if d is APPROVE else "NOT_DOCUMENTED",
                            evidence=evidence if d is APPROVE else "Not documented in the notes.",
                        )
                    ],
                    reasons=[],
                    missing_information=["Neurologic exam findings"] if d is PEND else [],
                )
                for n, d in ((1, APPROVE), (2, PEND))
            ],
            complexity="LOW",
        ),
        line_decisions=decisions,
        claim_decision="APPROVE",
        amounts=amounts,
        review_tier="STANDARD",
        review=review,
        versions=Versions(
            rules_version="2.1.0",
            model_name="claimsense-decision:v1",
            prompt_version="decision_v3",
            policy_versions={"POL-IMG-001": "v2@2026-01-01"},
        ),
        timestamps=Timestamps(received=date(2026, 10, 1)),
    )


def final(line_no: int, decision: LineDecision, source: str = "MODEL") -> FinalLineDecision:
    codes = {APPROVE: [], DENY: ["DN_NOT_MEDICALLY_NECESSARY"], PEND: ["PD_MISSING_DOCUMENTATION"]}
    return FinalLineDecision(
        line_no=line_no,
        decision=decision,
        benefit_category="ADVANCED_IMAGING",
        source=source,  # type: ignore[arg-type]
        reason_codes=codes[decision],
    )


def accept(*overrides: LineOverride) -> ReviewAction:
    return ReviewAction(
        claim_id="CLM-EXP-00001",
        reviewer_id="reviewer-7",
        action="OVERRIDE" if overrides else "ACCEPT",
        line_overrides=list(overrides),
        timestamp=datetime(2026, 10, 2, 9, 30, tzinfo=UTC),
    )


APPROVED = record(
    ClaimStatus.FINAL_APPROVED,
    [final(1, APPROVE), final(2, APPROVE)],
    breakdown(line_amounts(1, 123456, 98765, 79012, 19753), line_amounts(2, 5000, 4000, 4000, 0)),
    accept(),
)
PENDED = record(
    ClaimStatus.FINAL_PENDED,
    [final(1, APPROVE), final(2, PEND)],
    breakdown(line_amounts(1, 123456, 98765, 79012, 19753), line_amounts(2, 5000, 0, 0, 0)),
    accept(),
)
OVERRIDDEN = record(
    ClaimStatus.FINAL_PARTIAL,
    [final(1, APPROVE), final(2, DENY, "REVIEWER")],
    breakdown(line_amounts(1, 123456, 98765, 79012, 19753), line_amounts(2, 5000, 0, 0, 0)),
    accept(LineOverride(line_no=2, decision=DENY, reason="Repeat scan within 30 days, no change.")),
)
REJECTED = DecisionRecord(
    claim_id="CLM-EXP-00002",
    status=ClaimStatus.REJECTED,
    rules_outcome=RulesOutcome(
        claim_outcome="REJECT",
        rule_results=[
            RuleResult(
                rule_id="R02",
                passed=False,
                outcome="REJECT",
                reason_code="RJ_INVALID_CODE",
                detail="Procedure code 9999X is not a valid code",
                fields_used=["service_lines[0].procedure_code"],
                line_no=1,
            )
        ],
        line_outcomes=[],
    ),
    versions=Versions(rules_version="2.1.0"),
    timestamps=Timestamps(received=date(2026, 10, 1)),
)
CODED_NOTE = "Repeat scan within 30 days, no change."
OVERRIDDEN_WITH_CODE = record(  # D-REV-9: the reviewer's reason code is the line's reason code
    ClaimStatus.FINAL_PARTIAL,
    [final(1, APPROVE), final(2, DENY, "REVIEWER")],
    breakdown(line_amounts(1, 123456, 98765, 79012, 19753), line_amounts(2, 5000, 0, 0, 0)),
    accept(
        LineOverride(
            line_no=2, decision=DENY, reason=CODED_NOTE, reason_code="DN_NOT_MEDICALLY_NECESSARY"
        )
    ),
)
RECORDS = {
    "approved": APPROVED,
    "pended": PENDED,
    "overridden": OVERRIDDEN,
    "overridden_with_code": OVERRIDDEN_WITH_CODE,
    "rejected": REJECTED,
}


def test_staff_see_the_override_code_and_note_and_a_provider_neither_note_nor_reviewer() -> None:
    """D-REV-9: the provider's record has no review, so the explanation shows the line's plain
    reason and CARC but never the reviewer, the note or the comment."""
    from app.api.claims import without_review

    staff = render(OVERRIDDEN_WITH_CODE, "text")
    shown = without_review(OVERRIDDEN_WITH_CODE)

    assert "Line 2 changed to Denied, reason DN_NOT_MEDICALLY_NECESSARY (not medically" in staff
    assert CODED_NOTE in staff and "reviewer-7" in staff
    assert shown.review is None
    assert shown.line_decisions == OVERRIDDEN_WITH_CODE.line_decisions
    for body in (render(shown, "text"), render(shown, "html")):
        assert CODED_NOTE not in body and "reviewer-7" not in body
        assert "not medically necessary under the coverage criteria" in body
        assert "CARC 50" in body


@pytest.mark.parametrize("name", RECORDS)
def test_every_amount_and_reason_matches_the_record(name: str) -> None:
    text = render(RECORDS[name], "text")

    assert mismatches(RECORDS[name], text) == []
    assert html_mismatches(render(RECORDS[name], "html"), text) == []


def test_the_check_finds_a_changed_amount_or_reason() -> None:
    text = render(OVERRIDDEN, "text")

    assert mismatches(OVERRIDDEN, text.replace("$987.65", "$987.66", 1))
    assert mismatches(OVERRIDDEN, text.replace("DN_NOT_MEDICALLY_NECESSARY", "DN_EXCLUDED", 1))


def test_money_is_formatted_from_integer_cents() -> None:
    assert [money(c) for c in (0, 5, 100, 123456, 100000000, -250)] == [
        "$0.00",
        "$0.05",
        "$1.00",
        "$1,234.56",
        "$1,000,000.00",
        "-$2.50",
    ]


def test_a_final_pended_claim_lists_processed_and_awaiting_lines() -> None:
    text = render(PENDED, "text")
    shown = view(PENDED)

    assert [line.line_no for line in shown["processed"]] == [1]
    assert [line.line_no for line in shown["awaiting"]] == [2]
    assert "Lines processed\n  Line 1 (70551): Approved" in text
    assert "Lines awaiting documentation\n  Line 2 (70553): Needs information" in text
    assert "    Needs: POL-IMG-001.c1: Neurologic deficit documented." in text
    assert "Neurologic exam findings" not in text  # the model's own missing_information text
    assert "Lines processed" not in render(APPROVED, "text")


def test_lines_show_criteria_with_evidence_and_policy_citation() -> None:
    text = render(APPROVED, "text")

    assert "Criterion POL-IMG-001.c1 (POL-IMG-001, Brain MRI): met" in text
    assert "Evidence: Headache for 6 weeks with new focal weakness." in text
    assert "Criterion: Neurologic deficit documented." in text
    assert "Model: claimsense-decision:v1" in text and "Policy POL-IMG-001: v2@2026-01-01" in text


def test_a_rule_outcome_shows_the_failed_rule_and_no_lines() -> None:
    text = render(REJECTED, "text")

    assert "R02 failed (REJECT), line 1: Procedure code 9999X is not a valid code" in text
    assert "Reason: RJ_INVALID_CODE (a code is not valid)" in text
    assert "No line decisions." in text and "Totals" not in text


def test_record_text_is_escaped_in_html_and_kept_on_one_line_in_text() -> None:
    shown = record(
        ClaimStatus.FINAL_APPROVED,
        [final(1, APPROVE), final(2, APPROVE)],
        APPROVED.amounts,
        accept(),
        evidence="<script>alert(1)</script>\nsecond line",
    )

    assert "<script>" not in render(shown, "html")
    assert "&lt;script&gt;" in render(shown, "html")
    assert "Evidence: <script>alert(1)</script> second line" in render(shown, "text")
