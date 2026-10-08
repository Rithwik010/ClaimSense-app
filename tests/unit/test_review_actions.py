"""P5.3: review actions and finalization, pure parts (app/review/actions.py)."""

from datetime import UTC, date, datetime

import pytest

from app.calculator.engine import (
    Accumulators,
    CalcLine,
    CostShareTerms,
    FeeEntry,
    NetworkTerms,
    calculate,
)
from app.domain.contracts import (
    BenefitFact,
    ClaimStatus,
    ContextPackage,
    CostShareRule,
    DecisionRecord,
    FinalLineDecision,
    LineContext,
    LineDecision,
    Network,
    ReviewAction,
    RulesOutcome,
    Timestamps,
    Versions,
)
from app.review.actions import (
    ReviewRefused,
    changes,
    finalization,
    review_decisions,
    visit_counts,
)

APPROVE, DENY, PEND = LineDecision.APPROVE, LineDecision.DENY, LineDecision.PEND
TERMS = NetworkTerms(deductible_cents=50000, coinsurance_bps=2000, oop_max_cents=300000)
IMAGING = CostShareTerms(CostShareRule.DEDUCTIBLE_COINSURANCE, None)
FEES = {"70551": FeeEntry(24425, 19540)}


def decision(line_no: int, value: LineDecision, source: str = "MODEL") -> FinalLineDecision:
    reasons = {
        APPROVE: [],
        DENY: ["DN_NOT_MEDICALLY_NECESSARY"],
        PEND: ["PD_MISSING_DOCUMENTATION"],
    }
    return FinalLineDecision(
        line_no=line_no,
        decision=value,
        benefit_category="ADVANCED_IMAGING",
        source=source,  # type: ignore[arg-type]
        reason_codes=reasons[value],
    )


def run(decisions: list[FinalLineDecision], before: Accumulators):
    lines = [
        CalcLine(d.line_no, "70551", 1, 39000, d.decision, d.benefit_category) for d in decisions
    ]
    calculation = calculate(
        lines, Network.IN_NETWORK, TERMS, {"ADVANCED_IMAGING": IMAGING}, FEES, before
    )
    return calculation, finalization(decisions, calculation)


@pytest.mark.parametrize(
    ("values", "status"),
    [
        ([APPROVE, APPROVE], ClaimStatus.FINAL_APPROVED),
        ([DENY, DENY], ClaimStatus.FINAL_DENIED),
        ([APPROVE, DENY], ClaimStatus.FINAL_PARTIAL),
        ([APPROVE, PEND], ClaimStatus.FINAL_PENDED),
        ([DENY, PEND], ClaimStatus.FINAL_PENDED),
        ([PEND], ClaimStatus.FINAL_PENDED),
    ],
)
def test_the_final_status_follows_the_claim_decision_rule(
    values: list[LineDecision], status: ClaimStatus
) -> None:
    decisions = [decision(n, value) for n, value in enumerate(values, start=1)]

    _, outcome = run(decisions, Accumulators(0, 0))

    assert outcome.status is status


def test_a_pended_claim_counts_its_approved_line_only() -> None:
    """D-REV-7: approved lines on a FINAL_PENDED claim count toward the accumulators; the pended
    line carries no amounts and changes nothing."""
    before = Accumulators(deductible_met_cents=10000, oop_met_cents=10000)

    calculation, outcome = run([decision(1, APPROVE), decision(2, PEND)], before)

    approved, pended = calculation.amounts.lines
    share = approved.deductible_cents + approved.copay_cents + approved.coinsurance_cents
    assert outcome.status is ClaimStatus.FINAL_PENDED
    assert outcome.accumulators_updated
    assert outcome.accumulators_after == Accumulators(
        before.deductible_met_cents + approved.deductible_cents, before.oop_met_cents + share
    )
    assert (pended.allowed_cents, pended.member_pays_cents) == (0, 0)


def test_no_approved_line_changes_no_accumulator() -> None:
    before = Accumulators(deductible_met_cents=10000, oop_met_cents=10000)

    _, outcome = run([decision(1, DENY), decision(2, PEND)], before)

    assert not outcome.accumulators_updated
    assert outcome.accumulators_after == before


def _fact(category: str, visit_limit: int | None = None) -> BenefitFact:
    return BenefitFact(
        benefit_category=category,
        covered=True,
        auth_required=False,
        visit_limit=visit_limit,
        visits_used=0,
        cost_share_rule=CostShareRule.DEDUCTIBLE_COINSURANCE,
    )


# Line 1 imaging (one candidate); line 2 colonoscopy (two); line 3 imaging.
CANDIDATES = {1: ["ADVANCED_IMAGING"], 2: ["ENDOSCOPY", "PREVENTIVE_CARE"], 3: ["ADVANCED_IMAGING"]}


def _record(
    decisions: list[FinalLineDecision],
    candidates: dict[int, list[str]] = CANDIDATES,
    limits: dict[str, int] | None = None,
) -> DecisionRecord:
    return DecisionRecord(
        claim_id="CLM-1",
        status=ClaimStatus.AWAITING_REVIEW,
        rules_outcome=RulesOutcome(claim_outcome="PASS", rule_results=[], line_outcomes=[]),
        context_refs=ContextPackage(
            claim_id="CLM-1",
            plan_id="PLN-PPO-GOLD",
            plan_type="PPO",
            network=Network.IN_NETWORK,
            excluded_codes=[],
            lines=[
                LineContext(
                    line_no=n,
                    procedure_code="45378" if n == 2 else "70551",
                    candidate_benefits=[_fact(c, (limits or {}).get(c)) for c in categories],
                    criteria=[],
                )
                for n, categories in candidates.items()
            ],
        ),
        line_decisions=decisions,
        versions=Versions(rules_version="1.0.0"),
        timestamps=Timestamps(received=date(2026, 10, 20)),
    )


def test_accept_keeps_every_line_with_its_source_and_reason_codes() -> None:
    decisions = [decision(1, APPROVE), decision(2, DENY, "RULE"), decision(3, PEND, "VALIDATION")]
    action = ReviewAction(
        claim_id="CLM-1", reviewer_id="r1", action="ACCEPT", timestamp=datetime.now(UTC)
    )

    assert review_decisions(_record(decisions), action) == decisions


def test_a_review_for_another_claim_is_refused() -> None:
    action = ReviewAction(
        claim_id="CLM-2", reviewer_id="r1", action="ACCEPT", timestamp=datetime.now(UTC)
    )

    with pytest.raises(ReviewRefused, match="CLM-2"):
        review_decisions(_record([decision(1, APPROVE)]), action)


# --- OVERRIDE ------------------------------------------------------------------------------------


def override(*lines: dict) -> ReviewAction:
    return ReviewAction(
        claim_id="CLM-1",
        reviewer_id="r1",
        action="OVERRIDE",
        line_overrides=[{"reason": "Reviewed the notes", **line} for line in lines],
        timestamp=datetime.now(UTC),
    )


def with_category(line: FinalLineDecision, category: str | None) -> FinalLineDecision:
    return line.model_copy(update={"benefit_category": category})


MODEL_APPROVE = decision(1, APPROVE)
MODEL_DENY = decision(1, DENY)
VALIDATION_PEND = with_category(decision(2, PEND, "VALIDATION"), None)


def test_an_override_gets_source_reviewer_and_no_reason_codes_others_keep_theirs() -> None:
    lines = [MODEL_DENY, decision(3, PEND)]

    final = review_decisions(_record(lines), override({"line_no": 1, "decision": "APPROVE"}))

    assert final[0] == FinalLineDecision(
        line_no=1,
        decision=APPROVE,
        benefit_category="ADVANCED_IMAGING",  # the model's
        source="REVIEWER",
        reason_codes=[],
    )
    assert final[1] == lines[1]


def test_deny_and_pend_overrides_keep_the_line_category() -> None:
    final = review_decisions(_record([MODEL_APPROVE]), override({"line_no": 1, "decision": "DENY"}))

    assert (final[0].decision, final[0].benefit_category, final[0].source) == (
        DENY,
        "ADVANCED_IMAGING",
        "REVIEWER",
    )


def test_rule_outcomes_cannot_be_overridden() -> None:
    record = _record([MODEL_APPROVE, decision(3, DENY, "RULE")])

    with pytest.raises(ReviewRefused, match="rule outcomes are automatic"):
        review_decisions(record, override({"line_no": 3, "decision": "APPROVE"}))


def test_a_model_line_with_an_ncci_bypass_flag_can_be_overridden() -> None:
    """NCCI_BYPASS lines pass the rules and the model decides them (D-REV-2)."""
    final = review_decisions(_record([MODEL_APPROVE]), override({"line_no": 1, "decision": "PEND"}))

    assert final[0].source == "REVIEWER"


def test_approving_without_a_model_category_takes_the_only_candidate() -> None:
    record = _record([with_category(decision(1, PEND, "VALIDATION"), None)])

    final = review_decisions(record, override({"line_no": 1, "decision": "APPROVE"}))

    assert final[0].benefit_category == "ADVANCED_IMAGING"


def test_approving_with_several_candidates_and_no_category_asks_for_one() -> None:
    with pytest.raises(
        ReviewRefused, match="choose the benefit category.*ENDOSCOPY, PREVENTIVE_CARE"
    ):
        review_decisions(
            _record([VALIDATION_PEND]), override({"line_no": 2, "decision": "APPROVE"})
        )


def test_the_reviewer_category_comes_first_and_must_be_a_candidate() -> None:
    record = _record([VALIDATION_PEND])
    chosen = {"line_no": 2, "decision": "APPROVE", "benefit_category": "PREVENTIVE_CARE"}

    final = review_decisions(record, override(chosen))

    assert final[0].benefit_category == "PREVENTIVE_CARE"
    with pytest.raises(ReviewRefused, match="not one of the line's candidate categories"):
        review_decisions(record, override({**chosen, "benefit_category": "ADVANCED_IMAGING"}))


def test_a_category_goes_with_an_approve_decision_only() -> None:
    with pytest.raises(ReviewRefused, match="APPROVE decision only"):
        review_decisions(
            _record([MODEL_APPROVE]),
            override({"line_no": 1, "decision": "DENY", "benefit_category": "ADVANCED_IMAGING"}),
        )


def test_an_override_may_change_only_the_category() -> None:
    record = _record([with_category(decision(2, APPROVE), "ENDOSCOPY")])

    final = review_decisions(
        record,
        override({"line_no": 2, "decision": "APPROVE", "benefit_category": "PREVENTIVE_CARE"}),
    )

    assert (final[0].decision, final[0].benefit_category, final[0].source) == (
        APPROVE,
        "PREVENTIVE_CARE",
        "REVIEWER",
    )


@pytest.mark.parametrize(
    "line",
    [
        {"line_no": 1, "decision": "APPROVE"},
        {"line_no": 1, "decision": "APPROVE", "benefit_category": "ADVANCED_IMAGING"},
    ],
)
def test_an_override_that_changes_nothing_is_refused(line: dict) -> None:
    with pytest.raises(ReviewRefused, match="changes neither"):
        review_decisions(_record([MODEL_APPROVE]), override(line))


def test_unknown_and_repeated_lines_are_refused() -> None:
    record = _record([MODEL_APPROVE])

    with pytest.raises(ReviewRefused, match="not on the claim"):
        review_decisions(record, override({"line_no": 9, "decision": "DENY"}))
    with pytest.raises(ReviewRefused, match="overridden twice"):
        review_decisions(
            record,
            override({"line_no": 1, "decision": "DENY"}, {"line_no": 1, "decision": "PEND"}),
        )


def test_the_audit_changes_hold_before_after_and_reason() -> None:
    record = _record([MODEL_APPROVE])
    action = override({"line_no": 1, "decision": "DENY"})

    found = changes(record, action, review_decisions(record, action))

    assert found == [
        {
            "line_no": 1,
            "reason": "Reviewed the notes",
            "before": {
                "decision": "APPROVE",
                "benefit_category": "ADVANCED_IMAGING",
                "source": "MODEL",
                "reason_codes": [],
            },
            "after": {
                "decision": "DENY",
                "benefit_category": "ADVANCED_IMAGING",
                "source": "REVIEWER",
                "reason_codes": [],
            },
        }
    ]


# --- Visits --------------------------------------------------------------------------------------

THERAPY = "REHAB_THERAPY"
OCT_16, OCT_17, OCT_18 = date(2026, 10, 16), date(2026, 10, 17), date(2026, 10, 18)


def therapy(line_no: int, value: LineDecision) -> FinalLineDecision:
    return with_category(decision(line_no, value), THERAPY)


def test_visits_count_one_per_date_of_service_of_approved_lines() -> None:
    """D-REV-8: two codes on one date are one visit, two dates two visits, and a denied line on a
    third date no visit."""
    record = _record([], {n: [THERAPY] for n in (1, 2, 3, 4)}, {THERAPY: 30})
    lines = [therapy(1, APPROVE), therapy(2, APPROVE), therapy(3, APPROVE), therapy(4, DENY)]
    dates = {1: OCT_16, 2: OCT_16, 3: OCT_17, 4: OCT_18}

    assert visit_counts(record, lines[:2], dates) == {THERAPY: 1}
    assert visit_counts(record, lines[:3], dates) == {THERAPY: 2}
    assert visit_counts(record, lines, dates) == {THERAPY: 2}


def test_a_pended_claim_counts_the_visits_of_its_approved_lines_only() -> None:
    record = _record([], {1: [THERAPY], 2: [THERAPY], 3: ["ADVANCED_IMAGING"]}, {THERAPY: 30})
    lines = [therapy(1, APPROVE), therapy(2, PEND), decision(3, APPROVE)]

    found = visit_counts(record, lines, {1: OCT_16, 2: OCT_17, 3: OCT_18})

    assert found == {THERAPY: 1}  # the pended line adds none; imaging has no visit limit
