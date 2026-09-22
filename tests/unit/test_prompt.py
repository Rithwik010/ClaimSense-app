"""Decision prompt decision_v2 (INSTRUCTIONS.md §8.5): sections, lines to decide, no money (H1)."""

import re
from datetime import date

from app.domain.contracts import (
    BenefitFact,
    ContextPackage,
    CostShareRule,
    CriterionStatus,
    IntakeClaim,
    LineContext,
    LineRuleOutcome,
    Network,
    RetrievedCriterion,
    RuleOutcomeValue,
    RulesOutcome,
)
from app.ml.prompt import (
    NOT_APPLICABLE,
    NOT_DOCUMENTED,
    PROMPT_VERSION,
    PromptLookups,
    age_on,
    lines_to_decide,
    render_user_message,
    system_prompt,
)
from tests.unit.test_contracts import claim_data, line

LOOKUPS = PromptLookups(
    icd10_descriptions={"M5416": "Radiculopathy, lumbar region"},
    procedure_descriptions={"99213": "Office visit", "62323": "Epidural injection, lower back"},
    policy_codes={"POL-PAIN-001": ["62321", "62323", "64483"]},
)


def sample() -> tuple[IntakeClaim, RulesOutcome, ContextPackage]:
    claim = IntakeClaim.model_validate(
        claim_data(
            diagnoses=["M5416"],
            service_lines=[
                line(procedure_code="62323", charge_cents=987654),
                line(line_no=2, procedure_code="99213", charge_cents=123456),
            ],
        )
    )
    rules = RulesOutcome(
        claim_outcome=RuleOutcomeValue.PASS,
        rule_results=[],
        line_outcomes=[
            LineRuleOutcome(line_no=1, outcome="PASS", flags=["NCCI_BYPASS"]),
            LineRuleOutcome(line_no=2, outcome="DENY", reason_codes=["DN_NCCI_BUNDLED"]),
        ],
        flags=["OON"],
    )
    criterion = RetrievedCriterion(
        criterion_id="POL-PAIN-001.c3",
        policy_id="POL-PAIN-001",
        policy_title="Epidural steroid injections",
        text="The pain must have lasted at least 4 weeks.",
        source="LCD L33906 v75, Covered indications.",
        effective_date=date(2026, 1, 1),
    )
    context = ContextPackage(
        claim_id=claim.claim_id,
        plan_id="PLN-PPO-GOLD",
        plan_type="PPO",
        network=Network.OUT_OF_NETWORK,
        excluded_codes=[],
        lines=[
            LineContext(
                line_no=1,
                procedure_code="62323",
                candidate_benefits=[
                    BenefitFact(
                        benefit_category="PAIN_MANAGEMENT",
                        covered=True,
                        auth_required=True,
                        visit_limit=None,
                        visits_used=0,
                        cost_share_rule=CostShareRule.DEDUCTIBLE_COINSURANCE,
                    )
                ],
                criteria=[criterion],
                rule_flags=["NCCI_BYPASS"],
            )
        ],
    )
    return claim, rules, context


def test_system_prompt_is_versioned_and_forbids_amounts() -> None:
    text = system_prompt()
    assert PROMPT_VERSION == "decision_v2"
    assert "Never state or estimate any dollar amount" in text
    for reason in (
        "DN_CONDITIONAL_EXCLUSION",
        "DN_NOT_MEDICALLY_NECESSARY",
        "PD_MISSING_DOCUMENTATION",
    ):
        assert reason in text


def test_system_prompt_names_every_criterion_status_and_the_fixed_evidence() -> None:
    text = system_prompt()
    for status in CriterionStatus:
        assert f"- {status.value}:" in text
    assert f'"{NOT_DOCUMENTED}"' in text
    assert f'"{NOT_APPLICABLE}"' in text


def test_user_message_sections_in_order() -> None:
    message = render_user_message(*sample(), LOOKUPS)
    positions = [
        message.index(s) for s in ("CLAIM", "RULES_RESULT", "PLAN_BENEFITS", "COVERAGE_CRITERIA")
    ]
    assert positions == sorted(positions)
    assert message.rstrip().endswith("LINES TO DECIDE: 1")
    assert "M54.16 Radiculopathy, lumbar region" in message
    assert "[POL-PAIN-001.c3]" in message and "covers 62321, 62323, 64483" in message
    assert "Line 2: DENIED by rule (DN_NCCI_BUNDLED)" in message
    assert "flag NCCI_BYPASS" in message and "claim flags: OON" in message


def test_user_message_has_no_money_and_no_patient_name() -> None:
    claim, rules, context = sample()
    message = render_user_message(claim, rules, context, LOOKUPS)
    assert "$" not in message and "9876" not in message and "1234" not in message
    assert not re.search(r"charge|cents|amount", message, re.IGNORECASE)
    assert claim.patient.first_name not in message and claim.patient.last_name not in message


def test_lines_to_decide_and_age() -> None:
    _, rules, _ = sample()
    assert lines_to_decide(rules) == [1]
    assert age_on(date(1981, 4, 2), date(2026, 4, 1)) == 44
    assert age_on(date(1981, 4, 2), date(2026, 4, 2)) == 45
