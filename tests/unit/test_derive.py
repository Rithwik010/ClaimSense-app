"""Line decisions derived from the criterion statuses (Part 2 step 1; D-POL-3, D-DEC-1): the same
code decides the pipeline's lines and the v2 training labels."""

from datetime import date

import pytest

from app.domain.contracts import (
    CriterionResult,
    CriterionStatus,
    LineDecision,
    RetrievedCriterion,
    SLMLine,
)
from app.ml.derive import NO_INDICATION, derive_line

S = CriterionStatus


def retrieved(number: int, kind: str | None = None, group: str | None = None) -> RetrievedCriterion:
    return RetrievedCriterion(
        criterion_id=f"POL-FOOT-001.c{number}",
        policy_id="POL-FOOT-001",
        policy_title="Foot care",
        text=f"Criterion {number}.",
        source="LCD",
        effective_date=date(2026, 1, 1),
        criterion_type=kind,
        group=group,
    )


V1 = [retrieved(1), retrieved(2), retrieved(3)]
V2 = [
    retrieved(1, "conditional", "indication"),
    retrieved(2, "conditional", "indication"),
    retrieved(5, "conditional", "indication"),
    retrieved(6, "exclusion"),
    retrieved(7, "requirement"),
]


def line(decision: str, statuses: dict[int, S], reasons=None, missing=None) -> SLMLine:  # noqa: ANN001
    return SLMLine(
        line_no=1,
        decision=LineDecision(decision),
        benefit_category="PODIATRY",
        criteria=[
            CriterionResult(criterion_id=f"POL-FOOT-001.c{n}", status=s, evidence="e")
            for n, s in statuses.items()
        ],
        reasons=reasons if reasons is not None else [],
        missing_information=missing if missing is not None else [],
    )


@pytest.mark.parametrize(
    ("statuses", "expected"),
    [
        ({1: S.MET, 2: S.MET, 3: S.MET}, "APPROVE"),
        ({1: S.MET, 2: S.NOT_APPLICABLE, 3: S.MET}, "APPROVE"),
        ({1: S.MET, 2: S.NOT_DOCUMENTED, 3: S.MET}, "PEND"),
        ({1: S.NOT_MET, 2: S.NOT_DOCUMENTED, 3: S.MET}, "DENY"),
        ({}, "APPROVE"),  # an office visit: no criteria
    ],
)
def test_v1_criteria_follow_the_prompt_rule(statuses, expected) -> None:  # noqa: ANN001
    derived = derive_line(line("APPROVE", statuses), V1, [])

    assert derived.decision.value == expected


def test_a_model_pend_its_statuses_contradict_is_corrected() -> None:
    approve = derive_line(line("PEND", {1: S.MET, 2: S.MET, 3: S.MET}, ["X"], ["m"]), V1, [])
    deny = derive_line(line("PEND", {1: S.NOT_MET, 2: S.MET, 3: S.MET}, ["X"], ["m"]), V1, [])

    assert (approve.decision, approve.reasons, approve.missing_information) == (
        LineDecision.APPROVE,
        [],
        [],
    )
    assert (deny.decision, deny.reasons) == (LineDecision.DENY, ["DN_NOT_MEDICALLY_NECESSARY"])
    assert deny.missing_information == []


def test_the_ncci_bypass_pend_is_kept() -> None:
    """The bypass documentation is not a criterion: a PEND under NCCI_BYPASS with every criterion
    MET stays PEND (the v1 labels' rule)."""
    statuses = {1: S.MET, 2: S.MET, 3: S.MET}
    with_flag = derive_line(line("PEND", statuses, ["PD"], ["distinct"]), V1, ["NCCI_BYPASS"])
    approve = derive_line(line("APPROVE", statuses), V1, ["NCCI_BYPASS"])

    assert (with_flag.decision, with_flag.reasons, with_flag.missing_information) == (
        LineDecision.PEND,
        ["PD"],
        ["distinct"],
    )
    assert approve.decision is LineDecision.APPROVE


def test_an_unchanged_decision_keeps_the_model_reasons() -> None:
    derived = derive_line(
        line("DENY", {1: S.NOT_MET, 2: S.MET, 3: S.MET}, ["DN_CONDITIONAL_EXCLUSION"]), V1, []
    )

    assert derived.reasons == ["DN_CONDITIONAL_EXCLUSION"] and derived.changed is False


def test_a_satisfied_group_ignores_the_other_members() -> None:
    """D-POL-3: one MET member satisfies the group; another member's NOT_MET or NOT_DOCUMENTED
    never decides the line."""
    statuses = {1: S.NOT_MET, 2: S.NOT_DOCUMENTED, 5: S.MET, 6: S.NOT_APPLICABLE, 7: S.MET}

    assert derive_line(line("APPROVE", statuses), V2, []).decision is LineDecision.APPROVE


def test_an_unsatisfied_group_pends_with_no_covered_indication() -> None:
    statuses = {1: S.NOT_MET, 2: S.NOT_APPLICABLE, 5: S.NOT_APPLICABLE, 6: S.NOT_APPLICABLE}
    derived = derive_line(line("APPROVE", statuses | {7: S.MET}), V2, [])

    assert derived.decision is LineDecision.PEND and derived.changed
    assert derived.reasons == ["PD_MISSING_DOCUMENTATION"]
    assert derived.missing_information == [NO_INDICATION]


def test_precedence_not_met_outside_then_group_then_not_documented() -> None:
    group_met = {1: S.MET, 2: S.NOT_APPLICABLE, 5: S.NOT_APPLICABLE}
    group_open = {1: S.NOT_APPLICABLE, 2: S.NOT_APPLICABLE, 5: S.NOT_APPLICABLE}

    excluded = derive_line(
        line("PEND", group_open | {6: S.NOT_MET, 7: S.MET}, ["X"], ["m"]), V2, []
    )
    missing = derive_line(
        line("APPROVE", group_met | {6: S.NOT_APPLICABLE, 7: S.NOT_DOCUMENTED}), V2, []
    )

    assert excluded.decision is LineDecision.DENY
    assert excluded.reasons == ["DN_CONDITIONAL_EXCLUSION"]  # a NOT_MET exclusion
    assert missing.decision is LineDecision.PEND
    assert missing.missing_information == ["POL-FOOT-001.c7: Criterion 7."]


def test_criteria_without_group_tags_never_form_a_group() -> None:
    """The group rule applies only when the criteria carry group tags (policy set v2)."""
    statuses = {1: S.NOT_APPLICABLE, 2: S.NOT_APPLICABLE, 3: S.NOT_APPLICABLE}

    assert derive_line(line("APPROVE", statuses), V1, []).decision is LineDecision.APPROVE
