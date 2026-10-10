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


# --- decision_v3 (model v2) ----------------------------------------------------------------------


def v3_lookups() -> PromptLookups:
    from app.workflow.pipeline import bypass_keys

    return PromptLookups(
        icd10_descriptions=LOOKUPS.icd10_descriptions,
        procedure_descriptions=LOOKUPS.procedure_descriptions,
        policy_codes=LOOKUPS.policy_codes,
        bypass_keys=bypass_keys(),
    )


def with_modifiers(claim: IntakeClaim, first: list[str], second: list[str]) -> IntakeClaim:
    lines = [
        claim.service_lines[0].model_copy(update={"modifiers": first}),
        claim.service_lines[1].model_copy(update={"modifiers": second}),
    ]
    return claim.model_copy(update={"service_lines": lines})


def test_v3_shows_type_and_group_and_no_source() -> None:
    from app.ml.prompt import PROMPT_V3

    claim, rules, context = sample()
    grouped = (
        context.lines[0]
        .criteria[0]
        .model_copy(update={"criterion_type": "conditional", "group": "indication"})
    )
    context = context.model_copy(
        update={"lines": [context.lines[0].model_copy(update={"criteria": [grouped]})]}
    )

    text = render_user_message(claim, rules, context, v3_lookups(), PROMPT_V3)

    assert (
        "    [POL-PAIN-001.c3] (conditional; indication group) The pain must have lasted at "
        "least 4 weeks."
    ) in text
    assert "LCD L33906" not in text
    assert "decision_v3" not in text and system_prompt(PROMPT_V3) != system_prompt()


def test_v3_words_the_bypass_by_modifier() -> None:
    from app.ml.prompt import BYPASS_PHRASES, PROMPT_V3

    claim, rules, context = sample()
    lookups = v3_lookups()
    cases = {
        (("59",), ()): BYPASS_PHRASES["DISTINCT"],
        (("XS",), ()): BYPASS_PHRASES["DISTINCT"],
        ((), ("25",)): BYPASS_PHRASES["SEPARATE_EM"],
        ((), ("57",)): BYPASS_PHRASES["SURGERY_DECISION"],
        (("RT",), ("LT",)): BYPASS_PHRASES["SITES"],
        (("58",), ()): BYPASS_PHRASES["OTHER"],
    }
    for (first, second), phrase in cases.items():
        text = render_user_message(
            with_modifiers(claim, list(first), list(second)), rules, context, lookups, PROMPT_V3
        )
        rule_line = next(t for t in text.splitlines() if t.startswith("Line 1: PASS"))
        assert rule_line.startswith("Line 1: PASS, flag NCCI_BYPASS (modifier "), rule_line
        assert phrase in rule_line, (first, second, rule_line)


def test_v3_explains_the_new_flags_and_v2_never_shows_them() -> None:
    from app.ml.prompt import PROMPT_V3

    claim, rules, context = sample()
    flags = ["NCS_WITHOUT_EMG", "FACET_TWO_REGIONS", "EXTENDED_TESTING"]
    rules = rules.model_copy(
        update={"line_outcomes": [LineRuleOutcome(line_no=1, outcome="PASS", flags=flags)]}
    )

    v3 = render_user_message(claim, rules, context, v3_lookups(), PROMPT_V3)
    v2 = render_user_message(claim, rules, context, v3_lookups())

    assert "flag NCS_WITHOUT_EMG (a nerve conduction study with no needle EMG" in v3
    assert "flag FACET_TWO_REGIONS (" in v3 and "flag EXTENDED_TESTING (" in v3
    assert "Line 1: PASS\n" in v2 + "\n"  # model v1 never saw these flags (D-RULE-6)


def test_v3_shares_one_criteria_block_for_lines_with_the_same_criteria() -> None:
    from app.ml.prompt import PROMPT_V3

    claim, rules, context = sample()
    first = context.lines[0]
    second = first.model_copy(update={"line_no": 2, "procedure_code": "64483"})
    context = context.model_copy(update={"lines": [first, second]})

    v3 = render_user_message(claim, rules, context, v3_lookups(), PROMPT_V3)
    v2 = render_user_message(claim, rules, context, v3_lookups())

    assert "Lines 1 (62323), 2 (64483):" in v3 and v3.count("[POL-PAIN-001.c3]") == 1
    assert v2.count("[POL-PAIN-001.c3]") == 2  # decision_v2 unchanged for model v1
