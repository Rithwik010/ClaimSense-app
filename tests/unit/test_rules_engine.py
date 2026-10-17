"""The engine's flow (D8) and the H5 conversion on synthetic claims (§8.3, A-R9). The golden cases
are in test_rules_golden.py."""

from dataclasses import replace

import pytest

from app.domain.contracts import RuleOutcomeValue, RuleResult
from app.rules.confidence import apply_h5, low_confidence_fields
from app.rules.engine import evaluate
from app.rules.reference import RulesReference
from app.rules.results import failed
from tests.unit.rules_support import PCP, PLAN, claim_data, line, reference

THRESHOLD = 0.85


def run(data: dict, ref: RulesReference | None = None, confidences: dict | None = None):
    return evaluate(data, confidences or {}, ref or reference(), confidence_min=THRESHOLD)


def failures(results: list[RuleResult]) -> list[tuple]:
    return [(r.rule_id, r.outcome.value, r.reason_code, r.line_no) for r in results if not r.passed]


# --- H5 ------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("path", "value", "low"),
    [
        ("service_lines.0.units", 0.5, True),
        ("service_lines.0.units", 0.85, False),  # at the threshold is not below it
        ("service_lines.1.units", 0.5, False),  # another line
        ("diagnoses.0", 0.5, True),  # inside a listed field
        ("patient.last_name", 0.1, False),  # not used by the rule
    ],
)
def test_a_confidence_counts_when_strictly_below_the_threshold_on_a_used_field(
    path: str, value: float, low: bool
) -> None:
    fields = ["service_lines.0.units", "diagnoses"]

    assert low_confidence_fields(fields, {path: value}, THRESHOLD) == ([path] if low else [])


def test_h5_turns_a_failure_on_a_low_confidence_field_into_reject() -> None:
    result = failed("R05", RuleOutcomeValue.DENY, "DN_NOT_ELIGIBLE", "Outside coverage.", ["x"])

    converted = apply_h5(result, {"x": 0.6}, THRESHOLD)

    assert (converted.outcome, converted.reason_code) == (
        RuleOutcomeValue.REJECT,
        "RJ_LOW_CONFIDENCE_FIELD",
    )
    assert "x (0.60)" in converted.detail and "DN_NOT_ELIGIBLE" in converted.detail
    assert apply_h5(result, {"y": 0.1}, THRESHOLD) == result


# --- Flow (D8) -----------------------------------------------------------------------------------


def test_a_clean_claim_passes_with_every_rule_and_one_outcome_per_line() -> None:
    outcome = run(claim_data(service_lines=[line(), line(line_no=2, procedure_code="99214")]))

    assert outcome.claim_outcome is RuleOutcomeValue.PASS
    assert [r.rule_id for r in outcome.rule_results] == [
        "R01", "R02", "R03", "R04", "DUP", "R05", "R06", "R07", "R08", "R09", "R10",
        "R11", "R12", "R13", "R14", "R15", "R16", "R17", "R18", "R19", "R20", "R21",
    ]  # fmt: skip
    assert [o.outcome for o in outcome.line_outcomes] == ["PASS", "PASS"]
    assert outcome.flags == []


def test_group_a_failure_rejects_and_stops() -> None:
    outcome = run(claim_data(member_id="MBR-999999"))

    assert outcome.claim_outcome is RuleOutcomeValue.REJECT
    assert outcome.rule_results[-1].rule_id == "DUP"
    assert outcome.line_outcomes == []


def test_group_b_failure_stops_before_group_c_and_keeps_the_oon_flag() -> None:
    outcome = run(claim_data(received_date="2027-06-01"), reference(networks={}))

    assert outcome.claim_outcome is RuleOutcomeValue.DENY
    assert failures(outcome.rule_results) == [("R07", "DENY", "DN_LATE_FILING", None)]
    assert outcome.line_outcomes == [] and outcome.flags == ["OON"]
    assert "R11" not in {r.rule_id for r in outcome.rule_results}


def test_every_line_denied_by_group_c_denies_the_claim() -> None:
    outcome = run(claim_data(service_lines=[line(procedure_code="97140")]))

    assert outcome.claim_outcome is RuleOutcomeValue.DENY
    assert [o.reason_codes for o in outcome.line_outcomes] == [["DN_EXCLUDED"]]


def test_one_line_left_keeps_the_claim_going() -> None:
    outcome = run(claim_data(service_lines=[line(procedure_code="97140"), line(line_no=2)]))

    assert outcome.claim_outcome is RuleOutcomeValue.PASS
    assert [o.outcome for o in outcome.line_outcomes] == ["DENY", "PASS"]


def test_low_confidence_group_c_failure_rejects_the_claim_with_no_line_outcomes() -> None:
    data = claim_data(service_lines=[line(procedure_code="97110", units=7)])

    outcome = run(data, confidences={"service_lines.0.units": 0.5})

    assert outcome.claim_outcome is RuleOutcomeValue.REJECT
    assert failures(outcome.rule_results) == [("R12", "REJECT", "RJ_LOW_CONFIDENCE_FIELD", 1)]
    assert outcome.line_outcomes == []


def test_low_confidence_group_b_failure_rejects_instead_of_denying() -> None:
    ref = reference(plans={"PLN-A": replace(PLAN, oon_covered=False)}, networks={})

    outcome = run(claim_data(), ref, {"billing_npi": 0.7})

    assert outcome.claim_outcome is RuleOutcomeValue.REJECT
    assert failures(outcome.rule_results) == [("R08", "REJECT", "RJ_LOW_CONFIDENCE_FIELD", None)]


def test_a_low_confidence_field_alone_does_not_stop_a_claim() -> None:
    outcome = run(claim_data(), confidences={"patient.address.line1": 0.4, "billing_npi": 0.3})

    assert outcome.claim_outcome is RuleOutcomeValue.PASS
    assert PCP in next(r for r in outcome.rule_results if r.rule_id == "R08").detail
