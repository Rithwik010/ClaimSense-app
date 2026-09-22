"""Deterministic validation of the model output (§8.5; DECISIONS.md D3 and 2026-09-22): every
failure path."""

import json
from datetime import date

import pytest

from app.domain.contracts import (
    BenefitFact,
    ContextPackage,
    CostShareRule,
    LineContext,
    LineRuleOutcome,
    RetrievedCriterion,
    RuleOutcomeValue,
    RulesOutcome,
)
from app.ml.validate import validate_output

RULES = RulesOutcome(
    claim_outcome=RuleOutcomeValue.PASS,
    rule_results=[],
    line_outcomes=[
        LineRuleOutcome(line_no=1, outcome="PASS"),
        LineRuleOutcome(line_no=2, outcome="PASS"),
        LineRuleOutcome(line_no=3, outcome="DENY", reason_codes=["DN_EXCLUDED"]),
    ],
)


def fact(category: str) -> BenefitFact:
    return BenefitFact(
        benefit_category=category,
        covered=True,
        auth_required=False,
        visit_limit=None,
        visits_used=0,
        cost_share_rule=CostShareRule.COPAY,
    )


def criterion(number: int) -> RetrievedCriterion:
    return RetrievedCriterion(
        criterion_id=f"POL-IMG-001.c{number}",
        policy_id="POL-IMG-001",
        policy_title="Imaging",
        text="A criterion.",
        source="L37373",
        effective_date=date(2026, 1, 1),
    )


CONTEXT = ContextPackage(
    claim_id="CLM-V",
    plan_id="PLN-PPO-GOLD",
    plan_type="PPO",
    network="IN_NETWORK",
    excluded_codes=[],
    lines=[
        LineContext(
            line_no=1,
            procedure_code="99213",
            candidate_benefits=[fact("OFFICE_VISIT_PCP")],
            criteria=[],
        ),
        LineContext(
            line_no=2,
            procedure_code="70551",
            candidate_benefits=[fact("ADVANCED_IMAGING")],
            criteria=[criterion(1), criterion(2)],
        ),
    ],
)


def answer() -> dict:
    return {
        "lines": [
            {
                "line_no": 1,
                "decision": "APPROVE",
                "benefit_category": "OFFICE_VISIT_PCP",
                "criteria": [],
                "reasons": [],
                "missing_information": [],
            },
            {
                "line_no": 2,
                "decision": "PEND",
                "benefit_category": "ADVANCED_IMAGING",
                "criteria": [
                    {"criterion_id": "POL-IMG-001.c1", "status": "MET", "evidence": "Seen."},
                    {
                        "criterion_id": "POL-IMG-001.c2",
                        "status": "NOT_DOCUMENTED",
                        "evidence": "Not documented in the clinical notes.",
                    },
                ],
                "reasons": ["PD_MISSING_DOCUMENTATION"],
                "missing_information": ["Duration of symptoms"],
            },
        ],
        "complexity": "MEDIUM",
    }


def run(payload: dict | str):
    text = payload if isinstance(payload, str) else json.dumps(payload)
    return validate_output(text, RULES, CONTEXT)


def test_valid_answer_passes() -> None:
    result = run(answer())

    assert result.valid
    assert result.errors == ()
    assert result.output is not None and [line.line_no for line in result.output.lines] == [1, 2]


@pytest.mark.parametrize(
    "text",
    ["", "not json", '{"lines": []}', json.dumps({**answer(), "complexity": "EXTREME"})],
    ids=["empty", "not-json", "missing-complexity", "bad-enum"],
)
def test_output_that_does_not_parse_is_invalid(text: str) -> None:
    result = run(text)

    assert not result.valid
    assert result.output is None
    assert "does not parse as SLMOutput" in result.errors[0]


def test_amounts_in_the_output_are_rejected() -> None:
    payload = answer()
    payload["lines"][0]["plan_pays_cents"] = 1000  # H1: the model never produces amounts

    result = run(payload)

    assert not result.valid and result.output is None


def test_missing_line_is_invalid() -> None:
    payload = answer()
    payload["lines"].pop(0)

    result = run(payload)

    assert result.errors == ("line 1 is missing from the output",)
    assert result.output is not None  # kept for the record


def test_duplicate_line_is_invalid() -> None:
    payload = answer()
    payload["lines"].append(payload["lines"][0])

    assert run(payload).errors == ("line 1 appears 2 times",)


def test_line_denied_by_rules_must_not_be_decided() -> None:
    payload = answer()
    payload["lines"].append({**payload["lines"][0], "line_no": 3})

    assert run(payload).errors == ("line 3 is not a line to decide",)


def test_criterion_not_retrieved_for_the_line_is_invalid() -> None:
    payload = answer()
    payload["lines"][0]["criteria"] = [
        {"criterion_id": "POL-IMG-001.c1", "status": "MET", "evidence": "x"}  # line 2's
    ]
    payload["lines"][1]["criteria"].append(
        {"criterion_id": "POL-ZZZ-001.c9", "status": "MET", "evidence": "invented"}
    )

    assert run(payload).errors == (
        "line 1: criterion POL-IMG-001.c1 was not retrieved for this line",
        "line 2: criterion POL-ZZZ-001.c9 was not retrieved for this line",
    )


def test_benefit_category_must_be_a_candidate() -> None:
    payload = answer()
    payload["lines"][0]["benefit_category"] = "OFFICE_VISIT_SPECIALIST"

    assert run(payload).errors == (
        "line 1: benefit category OFFICE_VISIT_SPECIALIST is not a candidate category",
    )


@pytest.mark.parametrize("decision", ["DENY", "PEND"])
def test_deny_and_pend_need_a_reason(decision: str) -> None:
    payload = answer()
    payload["lines"][1]["decision"] = decision
    payload["lines"][1]["reasons"] = []

    assert f"line 2: {decision} needs at least one reason" in run(payload).errors


def test_pend_needs_missing_information() -> None:
    payload = answer()
    payload["lines"][1]["missing_information"] = []

    assert run(payload).errors == ("line 2: PEND needs the missing information",)


def test_every_retrieved_criterion_must_be_listed() -> None:
    payload = answer()
    payload["lines"][1]["criteria"].pop()

    assert run(payload).errors == ("line 2: criterion POL-IMG-001.c2 is missing from the output",)


def test_a_criterion_listed_twice_is_invalid() -> None:
    payload = answer()
    payload["lines"][1]["criteria"].append(payload["lines"][1]["criteria"][0])

    assert run(payload).errors == ("line 2: criterion POL-IMG-001.c1 appears 2 times",)


@pytest.mark.parametrize("status", ["NOT_MET", "NOT_DOCUMENTED"])
def test_approve_cannot_have_unmet_or_undocumented_criteria(status: str) -> None:
    payload = answer()
    line = payload["lines"][1]
    line.update(decision="APPROVE", reasons=[], missing_information=[])
    line["criteria"][1]["status"] = status

    assert run(payload).errors == (f"line 2: APPROVE with criterion POL-IMG-001.c2 {status}",)


def test_not_applicable_criteria_allow_approval() -> None:
    payload = answer()
    line = payload["lines"][1]
    line.update(decision="APPROVE", reasons=[], missing_information=[])
    line["criteria"][1].update(status="NOT_APPLICABLE", evidence="Does not apply to this service.")

    assert run(payload).valid
