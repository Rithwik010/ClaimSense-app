"""Group C (R11 to R13) on synthetic claims (§8.3, A-R3, A-R4, A-R11). The golden cases are in
test_rules_golden.py; agreement with the generator's rule mirror is in test_rules_parity.py."""

from datetime import date

import pytest

from app.domain.contracts import IntakeClaim, LineRuleOutcome, RuleResult
from app.rules.line_edits import check_line_edits
from app.rules.reference import RulesReference
from tests.unit.rules_support import PLAN, claim_data, line, ncci, reference

DEBRIDEMENT = {("11042", "97597"): (ncci("11042", "97597", "1"),)}


def run(lines: list[dict], ref: RulesReference | None = None):
    claim = IntakeClaim.model_validate(claim_data(service_lines=lines))
    return check_line_edits(claim, PLAN, ref or reference(ncci=DEBRIDEMENT))


def outcomes(found: list[LineRuleOutcome]) -> list[tuple]:
    return [(o.line_no, o.outcome, o.reason_codes, o.flags) for o in found]


def failures(results: list[RuleResult]) -> list[tuple]:
    return [(r.rule_id, r.reason_code, r.line_no) for r in results if not r.passed]


def test_clean_lines_pass_and_each_rule_reports_a_pass() -> None:
    results, found = run([line(), line(line_no=2, procedure_code="99214")])

    assert outcomes(found) == [(1, "PASS", [], []), (2, "PASS", [], [])]
    assert [(r.rule_id, r.passed, r.line_no) for r in results] == [
        ("R11", True, None),
        ("R12", True, None),
        ("R13", True, None),
        *((f"R{n}", True, None) for n in range(14, 21)),  # rules v2 (P2.3b)
        ("R21", True, None),  # the visit limit (D-RULE-10)
    ]


def test_the_column_2_line_is_denied_whatever_its_position() -> None:
    _, first = run([line(procedure_code="11042"), line(line_no=2, procedure_code="97597")])
    _, second = run([line(procedure_code="97597"), line(line_no=2, procedure_code="11042")])

    assert outcomes(first) == [(1, "PASS", [], []), (2, "DENY", ["DN_NCCI_BUNDLED"], [])]
    assert outcomes(second) == [(1, "DENY", ["DN_NCCI_BUNDLED"], []), (2, "PASS", [], [])]


@pytest.mark.parametrize("on_line", [1, 2])
def test_a_bypass_modifier_on_either_line_passes_the_column_2_line_with_a_flag(
    on_line: int,
) -> None:
    lines = [
        line(procedure_code="11042", modifiers=["XS"] if on_line == 1 else []),
        line(line_no=2, procedure_code="97597", modifiers=["XS"] if on_line == 2 else []),
    ]

    results, found = run(lines)

    assert outcomes(found) == [(1, "PASS", [], []), (2, "PASS", [], ["NCCI_BYPASS"])]
    assert failures(results) == []


@pytest.mark.parametrize("modifier", ["59", "RT"])
def test_modifiers_outside_the_v1_bypass_list_do_not_bypass(modifier: str) -> None:
    """D-GOLD-3: modifier 59 is added in v2; v1 keeps XE, XP, XS, XU."""
    lines = [line(procedure_code="11042"), line(line_no=2, procedure_code="97597")]
    lines[1]["modifiers"] = [modifier]

    _, found = run(lines)

    assert found[1].reason_codes == ["DN_NCCI_BUNDLED"]


def test_indicator_0_denies_even_with_a_bypass_modifier_and_indicator_9_is_no_edit() -> None:
    lines = [
        line(procedure_code="11042", modifiers=["XS"]),
        line(line_no=2, procedure_code="97597"),
    ]
    no_bypass = reference(ncci={("11042", "97597"): (ncci("11042", "97597", "0"),)})
    not_applicable = reference(ncci={("11042", "97597"): (ncci("11042", "97597", "9"),)})

    assert run(lines, no_bypass)[1][1].reason_codes == ["DN_NCCI_BUNDLED"]
    assert run(lines, not_applicable)[1][1].outcome == "PASS"


def test_only_edits_active_on_the_date_of_service_apply_and_the_first_one_wins() -> None:
    lines = [line(procedure_code="11042"), line(line_no=2, procedure_code="97597")]
    deleted = reference(
        ncci={("11042", "97597"): (ncci("11042", "97597", "0", deleted=date(2026, 1, 1)),)}
    )
    first_wins = reference(
        ncci={("11042", "97597"): (ncci("11042", "97597", "9"), ncci("11042", "97597", "0"))}
    )

    assert run(lines, deleted)[1][1].outcome == "PASS"
    assert run(lines, first_wins)[1][1].outcome == "PASS"


def test_lines_on_different_dates_are_not_paired() -> None:
    lines = [
        line(procedure_code="11042"),
        line(line_no=2, procedure_code="97597", date_of_service="2026-10-06"),
    ]

    _, found = run(lines)

    assert [o.outcome for o in found] == ["PASS", "PASS"]


def test_units_of_one_code_on_one_day_add_up_against_the_mue() -> None:
    lines = [
        line(procedure_code="97110", units=4),
        line(line_no=2, procedure_code="97110", units=3),
        line(line_no=3, procedure_code="97110", units=6, date_of_service="2026-10-06"),
    ]

    results, found = run(lines)

    assert outcomes(found) == [
        (1, "DENY", ["DN_MUE_EXCEEDED"], []),
        (2, "DENY", ["DN_MUE_EXCEEDED"], []),
        (3, "PASS", [], []),
    ]
    r12 = [r for r in results if r.rule_id == "R12"]
    assert r12[0].fields_used == [
        "service_lines.0.units",
        "service_lines.0.procedure_code",
        "service_lines.0.date_of_service",
    ]


def test_an_excluded_code_is_denied() -> None:
    results, found = run([line(procedure_code="97140"), line(line_no=2)])

    assert outcomes(found) == [(1, "DENY", ["DN_EXCLUDED"], []), (2, "PASS", [], [])]
    assert failures(results) == [("R13", "DN_EXCLUDED", 1)]
    assert next(r for r in results if r.rule_id == "R13" and not r.passed).fields_used == [
        "service_lines.0.procedure_code",
        "member_id",
    ]


def test_a_line_failing_several_rules_lists_reasons_in_rule_order_and_failures_by_line() -> None:
    ref = reference(ncci=DEBRIDEMENT, mue={"97597": 1})
    lines = [line(procedure_code="97140"), line(line_no=2, procedure_code="11042")]
    lines.append(line(line_no=3, procedure_code="97597", units=2))

    results, found = run(lines, ref)

    assert found[2].reason_codes == ["DN_NCCI_BUNDLED", "DN_MUE_EXCEEDED"]
    assert failures(results) == [
        ("R13", "DN_EXCLUDED", 1),
        ("R11", "DN_NCCI_BUNDLED", 3),
        ("R12", "DN_MUE_EXCEEDED", 3),
    ]
