"""Task G1: the golden-case checks find planted errors, the samples are reproducible and the
review sheet is built from the given inputs only. In-memory cases; no data/raw/ needed."""

import copy
from typing import Any

from app.db.curated import load_curated
from scripts.verify.golden_checks import (
    CANDIDATE_TRIGGERS,
    CHECKS_FILE,
    INSTRUCTIONS_MD,
    SITUATIONS,
    Finding,
    blind_view,
    candidate_reviews,
    check_calculator_case,
    check_rules_case,
    cob_total_differs,
    decision_conflicts,
    parse_instructions,
    sample_calculator,
    sample_rules,
    shown_cases,
    situations,
)

SPEC = parse_instructions(INSTRUCTIONS_MD.read_text(encoding="utf-8"))
GOLD = load_curated().plans["PLN-PPO-GOLD"]  # in network: deductible 50000, OOP max 300000

# --- calculator -------------------------------------------------------------------------------

FIELDS = (
    "billed_cents",
    "allowed_cents",
    "contractual_adjustment_cents",
    "deductible_cents",
    "copay_cents",
    "coinsurance_cents",
    "cob_primary_paid_cents",
    "plan_pays_cents",
    "member_pays_cents",
    "balance_bill_exposure_cents",
)


def _amounts(**values: int) -> dict[str, int]:
    return {"line_no": 1, **dict.fromkeys(FIELDS, 0), **values}


def _calc(line: dict[str, int], decision: str = "APPROVE", met: tuple[int, int] = (0, 0)) -> dict:
    totals = {f: line[f] for f in FIELDS}
    cost_share = line["deductible_cents"] + line["copay_cents"] + line["coinsurance_cents"]
    return {
        "case_id": "C-T",
        "title": "secret title",
        "assumptions": [],
        "given": {
            "plan_id": "PLN-PPO-GOLD",
            "network": "IN_NETWORK",
            "accumulators": {"deductible_met_cents": met[0], "oop_met_cents": met[1]},
            "fee_schedule": {"70551": {"inn_allowed_cents": 24425, "oon_allowed_cents": 19540}},
            "lines": [
                {
                    "line_no": 1,
                    "procedure_code": "70551",
                    "units": 1,
                    "billed_cents": line["billed_cents"],
                    "decision": decision,
                    "benefit_category": "ADVANCED_IMAGING",
                }
            ],
            "other_coverage": None,
        },
        "expected": {
            "amounts": {"lines": [line], "totals": totals},
            "accumulators_after": {
                "deductible_met_cents": met[0] + line["deductible_cents"],
                "oop_met_cents": met[1] + cost_share,
            },
        },
        "worked_steps": ["secret step"],
    }


CLEAN = _amounts(
    billed_cents=39000,
    allowed_cents=24425,
    contractual_adjustment_cents=14575,
    deductible_cents=24425,
    member_pays_cents=24425,
)


def _checks(case: dict) -> set[str]:
    return {f.check for f in check_calculator_case(case, GOLD)}


def test_a_consistent_calculator_case_has_no_findings() -> None:
    assert check_calculator_case(_calc(CLEAN), GOLD) == []


def test_each_calculator_rule_catches_its_planted_error() -> None:
    cases = {
        "plan pays + member pays = max(0, allowed - primary paid)": _calc(
            {**CLEAN, "plan_pays_cents": 100}
        ),
        "allowed <= billed": _calc({**CLEAN, "allowed_cents": 40000}),
        "no negative amounts": _calc({**CLEAN, "contractual_adjustment_cents": -1}),
        "integer cents only": _calc({**CLEAN, "deductible_cents": 24425.0}),
        "deductible applied <= remaining deductible": _calc(CLEAN, met=(40000, 40000)),
        "member pays <= remaining out-of-pocket maximum": _calc(CLEAN, met=(0, 290000)),
        "copay <= allowed": _calc(
            {**CLEAN, "deductible_cents": 0, "copay_cents": 30000, "member_pays_cents": 24425}
        ),
        "denied or pended lines pay 0": _calc(CLEAN, decision="DENY"),
    }
    for check, case in cases.items():
        assert check in _checks(case), check


def test_totals_and_accumulators_after_must_follow_the_lines() -> None:
    case = _calc(CLEAN)
    case["expected"]["amounts"]["totals"]["allowed_cents"] += 1
    case["expected"]["accumulators_after"]["oop_met_cents"] += 1

    found = _checks(case)

    assert "totals = sum of lines (A8)" in found
    assert "accumulators after = before + the claim's cost share (A5)" in found


def test_cob_when_the_primary_paid_more_than_the_allowed_amount() -> None:
    """A6 with primary paid > allowed: max(0, allowed - primary paid) = 0, so the plan and the
    member pay nothing; the normal cost share still counts toward the accumulators."""
    line = _amounts(
        billed_cents=39000,
        allowed_cents=24425,
        contractual_adjustment_cents=14575,
        deductible_cents=24425,
        cob_primary_paid_cents=30000,
    )
    assert check_calculator_case(_calc(line), GOLD) == []

    wrong = _calc({**line, "member_pays_cents": 24425})
    assert "plan pays + member pays = max(0, allowed - primary paid)" in _checks(wrong)


def test_the_total_cob_identity_differs_only_when_lines_mix() -> None:
    def case(*lines: tuple[int, int]) -> dict:
        """lines: (allowed, primary paid), all approved."""
        return {
            "given": {"lines": [{"line_no": n, "decision": "APPROVE"} for n in range(1, 3)]},
            "expected": {
                "amounts": {
                    "lines": [
                        {"line_no": n, "allowed_cents": a, "cob_primary_paid_cents": p}
                        for n, (a, p) in enumerate(lines, start=1)
                    ]
                }
            },
        }

    assert not cob_total_differs(case((24425, 30000), (10000, 15000)))  # both paid more
    assert not cob_total_differs(case((24425, 5000), (10000, 0)))  # both paid less
    assert cob_total_differs(case((24425, 30000), (10000, 0)))  # 10000 versus 4425


def test_accumulators_after_must_be_whole_cents() -> None:
    case = _calc(CLEAN)
    case["expected"]["accumulators_after"]["oop_met_cents"] = 24425.0

    assert "integer cents only" in _checks(case)


# --- rules ------------------------------------------------------------------------------------


def _rules(
    failures: list[tuple[str, str, str, int | None]],
    outcome: str,
    status: str,
    targets: tuple[str, ...] = ("R10",),
    confidences: dict[str, float] | None = None,
    line_outcomes: list[dict[str, Any]] | None = None,
) -> dict:
    return {
        "case_id": "T-01",
        "title": "secret",
        "rules": list(targets),
        "given": {
            "claim": {"service_lines": [{"line_no": 1}, {"line_no": 2}]},
            "source_format": "JSON",
            "field_confidences": confidences or {},
            "reference_additions": {},
        },
        "expected": {
            "claim_outcome": outcome,
            "status": status,
            "failures": [
                {"rule_id": r, "outcome": o, "reason_code": c, "line_no": n}
                for r, o, c, n in failures
            ],
            "line_outcomes": line_outcomes,
            "flags": [],
        },
    }


def _rule_checks(case: dict) -> set[str]:
    return {f.check for f in check_rules_case(case, SPEC)}


def test_section_8_3_is_read_from_instructions() -> None:
    assert set(SPEC.rules) == {f"R{n:02d}" for n in range(1, 14)} | {"DUP"}
    assert SPEC.rules["R06"].outcomes == {"REJECT", "PEND"}
    assert SPEC.rules["R13"].outcomes == {"DENY"}
    assert "RJ_DUPLICATE" in SPEC.rules["DUP"].reasons
    assert "R11–R13" in SPEC.order[2]  # item 3, fixed to match the rules table and D8
    assert "RJ_LOW_CONFIDENCE_FIELD" in SPEC.h5
    assert any("ROUND_HALF_UP" in paragraph for paragraph in SPEC.calc_intro)  # coinsurance
    assert SPEC.calc_steps[1].startswith("**Allowed amount**")
    assert set(SPEC.cost_share) == {"COPAY", "DEDUCTIBLE_COINSURANCE", "OUT_OF_NETWORK"}


def test_a_well_formed_rules_case_has_no_findings() -> None:
    case = _rules([("R10", "DENY", "DN_NO_AUTH", None)], "DENY", "DENIED_BY_RULE")
    assert check_rules_case(case, SPEC) == []


def test_outcome_status_and_targets_are_checked() -> None:
    assert "status matches the outcome" in _rule_checks(
        _rules([("R10", "DENY", "DN_NO_AUTH", None)], "DENY", "REJECTED")
    )
    assert "exactly one expected outcome" in _rule_checks(
        _rules([("R10", "DENY", "DN_NO_AUTH", None)], "MAYBE", "DENIED_BY_RULE")
    )
    assert "targeted rule exists in section 8.3" in _rule_checks(
        _rules([("R10", "DENY", "DN_NO_AUTH", None)], "DENY", "DENIED_BY_RULE", ("R99",))
    )
    assert "failure matches section 8.3" in _rule_checks(
        _rules([("R10", "PEND", "DN_NO_AUTH", None)], "PEND", "PENDED_BY_RULE")
    )


def test_group_order_and_precedence() -> None:
    a_then_b = _rules(
        [("R04", "REJECT", "RJ_MEMBER_NOT_FOUND", None), ("R10", "DENY", "DN_NO_AUTH", None)],
        "REJECT",
        "REJECTED",
    )
    assert "Group A stops the claim" in _rule_checks(a_then_b)

    deny_and_pend = [
        ("R06", "PEND", "PD_PROVIDER_ENROLLMENT", None),
        ("R10", "DENY", "DN_NO_AUTH", None),
    ]
    assert "outcome follows the group order" in _rule_checks(
        _rules(deny_and_pend, "PEND", "PENDED_BY_RULE")
    )
    assert check_rules_case(_rules(deny_and_pend, "DENY", "DENIED_BY_RULE"), SPEC) == []

    line_rule_without_line = _rules(
        [("R13", "DENY", "DN_EXCLUDED", None)],
        "PASS",
        "RECEIVED",
        ("R13",),
        line_outcomes=[{"line_no": 1, "outcome": "PASS"}, {"line_no": 2, "outcome": "PASS"}],
    )
    assert "line number matches the rule's group" in _rule_checks(line_rule_without_line)


def test_h5_conversion() -> None:
    low = {"service_lines.0.procedure_code": 0.8}
    not_converted = _rules(
        [("R10", "DENY", "DN_NO_AUTH", None)], "DENY", "DENIED_BY_RULE", confidences=low
    )
    converted = _rules(
        [("R10", "REJECT", "RJ_LOW_CONFIDENCE_FIELD", None)],
        "REJECT",
        "REJECTED",
        ("R10", "H5"),
        confidences=low,
    )
    without_low_field = _rules(
        [("R10", "REJECT", "RJ_LOW_CONFIDENCE_FIELD", None)],
        "REJECT",
        "REJECTED",
        ("R10", "H5"),
        confidences={"service_lines.0.procedure_code": 0.9},
    )

    assert "H5: a failure on a low-confidence field becomes REJECT" in _rule_checks(not_converted)
    assert check_rules_case(converted, SPEC) == []
    assert "H5 applied without a low-confidence field the rule uses" in _rule_checks(
        without_low_field
    )


def test_h5_on_a_line_rule_looks_only_at_the_failing_line() -> None:
    def case(path: str) -> dict:
        return _rules(
            [("R12", "DENY", "DN_MUE_EXCEEDED", 2)],
            "PASS",
            "RECEIVED",
            ("R12",),
            confidences={path: 0.5},
            line_outcomes=[
                {"line_no": 1, "outcome": "PASS"},
                {"line_no": 2, "outcome": "DENY"},
            ],
        )

    assert check_rules_case(case("service_lines.0.units"), SPEC) == []  # line 1: not used
    assert "H5: a failure on a low-confidence field becomes REJECT" in _rule_checks(
        case("service_lines.1.units")
    )


def _claim_case(lines: list[tuple[str, str]], outcomes: list[str]) -> dict:
    """lines: (procedure code, date of service)."""
    return {
        "case_id": "T-02",
        "rules": ["R01-R13"],
        "given": {
            "claim": {
                "diagnoses": ["M5416"],
                "clinical_notes": "",
                "service_lines": [
                    {
                        "line_no": n,
                        "procedure_code": code,
                        "date_of_service": day,
                        "diagnosis_pointers": ["A"],
                    }
                    for n, (code, day) in enumerate(lines, start=1)
                ],
            },
        },
        "expected": {
            "claim_outcome": "PASS",
            "line_outcomes": [
                {"line_no": n, "outcome": o} for n, o in enumerate(outcomes, start=1)
            ],
        },
    }


def test_later_decisions_r14_and_r15_flag_lines_expected_to_pass() -> None:
    same_day = _claim_case([("62323", "2026-10-06"), ("64493", "2026-10-06")], ["PASS", "PASS"])

    def supported(code: str, diagnoses: tuple[str, ...]) -> bool | None:
        return code != "64493"

    found = {(f.check, f.line_no) for f in decision_conflicts(same_day, supported)}

    assert ("R14 (D-ESI-3) would deny this ESI line", 1) in found
    assert ("R15 (D-DX-1) would deny this line", 2) in found
    other_day = _claim_case([("62323", "2026-10-06"), ("64493", "2026-10-07")], ["PASS", "DENY"])
    assert decision_conflicts(other_day, lambda code, dx: True) == []


def test_d_rule_1_triggers_cover_the_9_single_claim_candidates() -> None:
    from scripts.verify.policy_sources import FINDINGS, RULE

    single_claim = {
        f.finding_id
        for f in FINDINGS
        if f.kind == RULE and "history" not in f.change and "dates" not in f.change
    }
    assert set(CANDIDATE_TRIGGERS) == single_claim and len(single_claim) == 9
    scope = load_curated().scope
    for finding_id, (codes, _) in CANDIDATE_TRIGGERS.items():
        policy = finding_id.rsplit(".", 1)[0]
        assert all(scope[c].policy_id == policy for c in codes), finding_id

    two_regions = _claim_case([("64493", "2026-10-06"), ("64635", "2026-10-06")], ["PASS"] * 2)
    one_line = _claim_case([("64635", "2026-10-06")], ["PASS"])
    assert {f.check for f in candidate_reviews(two_regions)} == {
        "D-RULE-1 candidate POL-PAIN-002.F9 may change this case"
    }
    assert candidate_reviews(one_line) == []


# --- coverage and samples ---------------------------------------------------------------------


def _benefit(category: str) -> tuple[str, int | None]:
    return ("COPAY", 2500) if category == "OFFICE_VISIT_PCP" else ("DEDUCTIBLE_COINSURANCE", None)


def test_situations_are_read_from_the_case() -> None:
    partly = _calc({**CLEAN, "deductible_cents": 24425, "coinsurance_cents": 0}, met=(10000, 10000))
    found = situations(partly, GOLD, _benefit)
    assert "deductible partly met" in found and "copay only" not in found

    copay = _calc(_amounts(billed_cents=15000, allowed_cents=9000, copay_cents=2500))
    copay["given"]["lines"][0]["benefit_category"] = "OFFICE_VISIT_PCP"
    assert "copay only" in situations(copay, GOLD, _benefit)


def _named(case_id: str, targets: list[str]) -> dict:
    return {"case_id": case_id, "rules": targets}


def test_the_rules_sample_has_one_h5_case_and_otherwise_different_rules() -> None:
    cases = [_named(f"{r}-0{n}", [r]) for r in ("R04", "R05", "R07", "R10", "R11") for n in (1, 2)]
    cases += [_named(f"{r}-01", [r]) for r in ("R01", "R02", "R03", "R06", "R08", "R09", "R12")]
    cases += [_named("H5-01", ["R07", "H5"]), _named("H5-02", ["R10", "H5"])]

    picked = sample_rules(cases, seed=42)
    again = sample_rules(list(reversed(cases)), seed=42)

    assert [c["case_id"] for c in picked] == [c["case_id"] for c in again]
    h5 = [c for c in picked if "H5" in c["rules"]]
    others = [c["rules"][0] for c in picked if "H5" not in c["rules"]]
    assert len(picked) == 10 and len(h5) == 1
    assert len(set(others)) == 9 and h5[0]["rules"][0] not in others


def test_the_calculator_sample_takes_one_case_per_situation() -> None:
    found = {f"C{n:02d}": {situation} for n, situation in enumerate(SITUATIONS)}
    found["C99"] = set(SITUATIONS[:3])
    del found["C09"]  # no case for the last situation

    picked, short = sample_calculator(found, seed=42)

    assert len(picked) == len(set(picked)) == len(SITUATIONS) - 1
    assert short == [SITUATIONS[9]]
    assert picked == sample_calculator(dict(reversed(list(found.items()))), seed=42)[0]


def test_the_blind_view_keeps_only_the_inputs() -> None:
    case = _calc(CLEAN)
    view = blind_view(copy.deepcopy(case))

    assert set(view) == {"case_id", "rules", "assumptions", "given"}
    assert "expected" not in view and "worked_steps" not in view and "title" not in view
    assert view["given"] == case["given"]


def test_findings_on_sampled_cases_are_counted_not_named() -> None:
    """A violation or conflict comes from expected values: naming a sampled case would leak."""
    items = [
        Finding("conflict", "R15 (D-DX-1) would deny this line", "R11-02", 1),
        Finding("conflict", "R15 (D-DX-1) would deny this line", "R11-03", 2),
        Finding("review", "D-RULE-1 candidate POL-PAIN-001.F6 may change this case", "R10-01"),
    ]

    shown = shown_cases(items, hidden={"R11-03", "R10-01"})

    assert shown == f"R11-02 (line 1), R10-01, 1 in this sheet's sample (named in {CHECKS_FILE})"
    assert shown_cases([], hidden=set()) == "-"
