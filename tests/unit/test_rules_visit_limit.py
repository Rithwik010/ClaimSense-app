"""R21, the yearly visit limit (D-RULE-10): one visit per date of service in a visit-limited
benefit category; the visits used before the claim count first, then the claim's dates in date
order; every line of the category on a date beyond the limit is denied DN_VISIT_LIMIT. A date
whose lines an earlier rule denies uses no visit; a benefit without a limit always passes; a
low-confidence date of service or procedure code makes the failure a REJECT (H5). Synthetic
reference, runs in CI.
"""

from dataclasses import replace
from datetime import date

from app.domain.contracts import IntakeClaim, LineRuleOutcome, RuleOutcomeValue, RuleResult
from app.rules.engine import evaluate
from app.rules.line_edits import check_line_edits
from app.rules.reference import RulesReference
from app.rules.visit_limits import benefit_year_start
from tests.unit.rules_support import PLAN, claim_data, line, reference

THERAPY = "REHAB_THERAPY"
MEMBER = "MBR-000123"
YEAR_2026 = date(2026, 1, 1)
LIMITED_PLAN = replace(PLAN, visit_limits={THERAPY: 20})
CATEGORIES = {
    "97110": (THERAPY,),
    "97140": (THERAPY,),  # on PLN-A's exclusion list (rules_support), so R13 denies it
    "97530": (THERAPY,),
    "99213": ("OFFICE_VISIT_PCP", "OFFICE_VISIT_SPECIALIST"),
}


def therapy_reference(used: int | None, period: date = YEAR_2026, **overrides) -> RulesReference:
    visits = {} if used is None else {(MEMBER, THERAPY, period): used}
    return reference(
        plans={"PLN-A": LIMITED_PLAN},
        benefit_categories=CATEGORIES,
        visits_used=visits,
        procedure_codes=frozenset({*CATEGORIES, "62323"}),
        **overrides,
    )


def therapy(line_no: int, day: str, code: str = "97110") -> dict:
    return line(line_no=line_no, date_of_service=day, procedure_code=code, diagnosis_pointers=["A"])


def run(lines: list[dict], ref: RulesReference, plan=LIMITED_PLAN):
    claim = IntakeClaim.model_validate(claim_data(service_lines=lines))
    return check_line_edits(claim, plan, ref)


def outcomes(found: list[LineRuleOutcome]) -> list[tuple]:
    return [(o.line_no, o.outcome, o.reason_codes) for o in found]


def r21(results: list[RuleResult]) -> list[RuleResult]:
    return [r for r in results if r.rule_id == "R21"]


def test_a_visit_under_the_limit_passes() -> None:
    results, found = run([therapy(1, "2026-10-05")], therapy_reference(used=10))

    assert outcomes(found) == [(1, "PASS", [])]
    assert [(r.passed, r.line_no) for r in r21(results)] == [(True, None)]


def test_the_visit_that_reaches_the_limit_passes_and_the_next_is_denied() -> None:
    _, twentieth = run([therapy(1, "2026-10-05")], therapy_reference(used=19))
    results, twenty_first = run([therapy(1, "2026-10-05")], therapy_reference(used=20))

    assert outcomes(twentieth) == [(1, "PASS", [])]
    assert outcomes(twenty_first) == [(1, "DENY", ["DN_VISIT_LIMIT"])]
    [failure] = r21(results)
    assert (failure.passed, failure.outcome, failure.reason_code, failure.line_no) == (
        False,
        RuleOutcomeValue.DENY,
        "DN_VISIT_LIMIT",
        1,
    )
    assert "visit 21" in failure.detail and "limit of 20" in failure.detail


def test_two_lines_on_one_date_are_one_visit() -> None:
    lines = [therapy(1, "2026-10-05"), therapy(2, "2026-10-05", "97530")]

    _, found = run(lines, therapy_reference(used=19))

    assert outcomes(found) == [(1, "PASS", []), (2, "PASS", [])]


def test_a_claim_crossing_the_limit_pays_the_first_date_and_denies_the_rest() -> None:
    """19 used and three new dates, listed out of date order: the earliest date is visit 20."""
    lines = [
        therapy(1, "2026-10-19"),
        therapy(2, "2026-10-05"),
        therapy(3, "2026-10-12"),
        therapy(4, "2026-10-12", "97530"),
    ]

    results, found = run(lines, therapy_reference(used=19))

    assert outcomes(found) == [
        (1, "DENY", ["DN_VISIT_LIMIT"]),
        (2, "PASS", []),
        (3, "DENY", ["DN_VISIT_LIMIT"]),
        (4, "DENY", ["DN_VISIT_LIMIT"]),
    ]
    assert [(r.line_no, r.reason_code) for r in r21(results)] == [
        (1, "DN_VISIT_LIMIT"),
        (3, "DN_VISIT_LIMIT"),
        (4, "DN_VISIT_LIMIT"),
    ]


def test_a_date_whose_lines_another_rule_denies_uses_no_visit() -> None:
    """97140 is on the plan's exclusion list (R13): its date is no visit, so the next date is the
    20th visit and passes."""
    lines = [therapy(1, "2026-10-05", "97140"), therapy(2, "2026-10-12")]

    _, found = run(lines, therapy_reference(used=19))

    assert outcomes(found) == [(1, "DENY", ["DN_EXCLUDED"]), (2, "PASS", [])]


def test_a_date_with_one_payable_line_is_a_visit_and_its_denied_line_lists_both_reasons() -> None:
    lines = [therapy(1, "2026-10-05", "97140"), therapy(2, "2026-10-05")]

    _, found = run(lines, therapy_reference(used=20))

    assert outcomes(found) == [
        (1, "DENY", ["DN_EXCLUDED", "DN_VISIT_LIMIT"]),
        (2, "DENY", ["DN_VISIT_LIMIT"]),
    ]


def test_the_count_resets_at_the_new_benefit_year() -> None:
    """20 used in 2026: a December visit is the 21st, a January visit the first of 2027."""
    full_2026 = therapy_reference(used=20)

    _, december = run([therapy(1, "2026-12-28")], full_2026)
    _, january = run([therapy(1, "2027-01-11")], full_2026)
    _, january_2027_full = run([therapy(1, "2027-01-11")], therapy_reference(20, date(2027, 1, 1)))

    assert outcomes(december) == [(1, "DENY", ["DN_VISIT_LIMIT"])]
    assert outcomes(january) == [(1, "PASS", [])]
    assert outcomes(january_2027_full) == [(1, "DENY", ["DN_VISIT_LIMIT"])]
    assert benefit_year_start(date(2027, 1, 11)) == date(2027, 1, 1)


def test_a_benefit_without_a_limit_always_passes() -> None:
    unlimited = therapy_reference(used=500)

    _, found = run([therapy(1, "2026-10-05"), line(line_no=2)], unlimited, plan=PLAN)
    _, office = run([line(), line(line_no=2, date_of_service="2026-10-06")], unlimited)

    assert outcomes(found) == [(1, "PASS", []), (2, "PASS", [])]
    assert outcomes(office) == [(1, "PASS", []), (2, "PASS", [])]


def test_another_members_visits_do_not_count() -> None:
    ref = therapy_reference(used=None)
    ref = replace(ref, visits_used={("MBR-000999", THERAPY, YEAR_2026): 20})

    _, found = run([therapy(1, "2026-10-05")], ref)

    assert outcomes(found) == [(1, "PASS", [])]


# --- Through the engine: claim outcome and H5 -----------------------------------------------------


def evaluate_claim(lines: list[dict], confidences: dict[str, float], used: int = 20):
    return evaluate(
        claim_data(service_lines=lines),
        confidences,
        therapy_reference(used=used),
        confidence_min=0.85,
    )


def test_every_line_over_the_limit_denies_the_claim() -> None:
    outcome = evaluate_claim([therapy(1, "2026-10-05"), therapy(2, "2026-10-12")], {})

    assert outcome.claim_outcome is RuleOutcomeValue.DENY
    assert [o.outcome for o in outcome.line_outcomes] == ["DENY", "DENY"]


def test_a_claim_with_a_line_under_the_limit_goes_on_to_the_model() -> None:
    outcome = evaluate_claim([therapy(1, "2026-10-05"), therapy(2, "2026-10-12")], {}, used=19)

    assert outcome.claim_outcome is RuleOutcomeValue.PASS
    assert [o.outcome for o in outcome.line_outcomes] == ["PASS", "DENY"]


def test_a_low_confidence_date_of_service_rejects_instead_of_denying() -> None:
    outcome = evaluate_claim([therapy(1, "2026-10-05")], {"service_lines.0.date_of_service": 0.42})

    assert outcome.claim_outcome is RuleOutcomeValue.REJECT
    [failure] = [r for r in outcome.rule_results if r.rule_id == "R21"]
    assert (failure.outcome, failure.reason_code) == (
        RuleOutcomeValue.REJECT,
        "RJ_LOW_CONFIDENCE_FIELD",
    )
    assert "DN_VISIT_LIMIT becomes RJ_LOW_CONFIDENCE_FIELD" in failure.detail


def test_a_low_confidence_procedure_code_rejects_instead_of_denying() -> None:
    outcome = evaluate_claim([therapy(1, "2026-10-05")], {"service_lines.0.procedure_code": 0.5})

    assert outcome.claim_outcome is RuleOutcomeValue.REJECT


def test_a_low_confidence_earlier_date_the_count_relies_on_rejects_the_later_line() -> None:
    """Line 2's date is visit 21 only because line 1's date counts first."""
    outcome = evaluate_claim(
        [therapy(1, "2026-10-05"), therapy(2, "2026-10-12")],
        {"service_lines.0.date_of_service": 0.5},
        used=19,
    )

    assert outcome.claim_outcome is RuleOutcomeValue.REJECT


def test_a_low_confidence_field_the_rule_does_not_use_keeps_the_denial() -> None:
    outcome = evaluate_claim(
        [therapy(1, "2026-10-05")], {"service_lines.0.charge_cents": 0.3, "diagnoses.0": 0.3}
    )

    assert outcome.claim_outcome is RuleOutcomeValue.DENY
    assert outcome.line_outcomes[0].reason_codes == ["DN_VISIT_LIMIT"]
