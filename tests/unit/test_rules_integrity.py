"""Group A (R01 to R04, duplicates) on synthetic claims (§8.3, A-R6 to A-R8). The golden cases
are in test_rules_golden.py."""

from datetime import date

import pytest

from app.domain.contracts import RuleOutcomeValue, RuleResult
from app.rules.integrity import InvalidClaimData, check_group_a, icd10_fiscal_year
from app.rules.reference import ExistingClaimLine, MissingReference
from tests.unit.rules_support import PCP, claim_data, line, reference


def failures(results: list[RuleResult]) -> list[tuple[str, str | None]]:
    return [(r.rule_id, r.reason_code) for r in results if not r.passed]


def test_a_clean_claim_passes_every_group_a_rule_in_order() -> None:
    claim, results = check_group_a(claim_data(), reference())

    assert claim is not None
    assert [r.rule_id for r in results] == ["R01", "R02", "R03", "R04", "DUP"]
    assert all(r.passed and r.outcome is RuleOutcomeValue.PASS for r in results)


@pytest.mark.parametrize(
    ("overrides", "missing"),
    [
        ({"member_id": None}, "member_id"),
        ({"member_id": "   "}, "member_id"),
        ({"diagnoses": []}, "diagnoses"),
        ({"service_lines": [line(procedure_code=None)]}, "service_lines.0.procedure_code"),
    ],
)
def test_a_missing_or_blank_field_fails_r01_and_names_the_field(
    overrides: dict, missing: str
) -> None:
    claim, results = check_group_a(claim_data(**overrides), reference())

    assert claim is None
    r01 = results[0]
    assert (r01.rule_id, r01.outcome, r01.reason_code) == (
        "R01",
        RuleOutcomeValue.REJECT,
        "RJ_MISSING_FIELD",
    )
    assert r01.fields_used == [missing]


def test_a_field_absent_from_the_claim_fails_r01() -> None:
    data = claim_data()
    del data["received_date"]

    _, results = check_group_a(data, reference())

    assert failures(results)[0] == ("R01", "RJ_MISSING_FIELD")


def test_malformed_codes_fail_r02_with_the_r02_fields() -> None:
    two_lines = [line(), line(line_no=2, modifiers=["5"])]
    data = claim_data(diagnoses=["54.16"], service_lines=two_lines)

    _, results = check_group_a(data, reference())

    r02 = next(r for r in results if r.rule_id == "R02")
    assert (r02.passed, r02.reason_code) == (False, "RJ_INVALID_CODE")
    assert r02.fields_used == [
        "diagnoses",
        "service_lines.0.procedure_code",
        "service_lines.1.procedure_code",
        "service_lines.0.place_of_service",
        "service_lines.1.place_of_service",
        "service_lines.0.modifiers",
        "service_lines.1.modifiers",
        "service_lines.0.date_of_service",
        "service_lines.1.date_of_service",
    ]


def test_contract_failures_are_reported_together_and_r04_still_runs() -> None:
    data = claim_data(member_id="MBR-UNKNOWN", billing_npi="1234567890")
    del data["received_date"]

    claim, results = check_group_a(data, reference())

    assert claim is None
    assert failures(results) == [
        ("R01", "RJ_MISSING_FIELD"),
        ("R03", "RJ_INVALID_NPI"),
        ("R04", "RJ_MEMBER_NOT_FOUND"),
    ]
    assert next(r for r in results if r.rule_id == "R03").fields_used == [
        "billing_npi",
        "service_lines.0.rendering_npi",
        "referring_npi",
    ]


def test_a_validation_error_outside_r01_to_r03_is_not_a_rule_failure() -> None:
    with pytest.raises(InvalidClaimData, match="units"):
        check_group_a(claim_data(service_lines=[line(units=0)]), reference())


@pytest.mark.parametrize(
    ("overrides", "problem"),
    [
        ({"diagnoses": ["M541"]}, "diagnosis M541 (FY2027)"),
        ({"service_lines": [line(procedure_code="99999")]}, "procedure code 99999"),
        ({"service_lines": [line(place_of_service="00")]}, "place of service 00"),
    ],
)
def test_codes_missing_from_the_code_tables_fail_r02(overrides: dict, problem: str) -> None:
    _, results = check_group_a(claim_data(**overrides), reference())

    r02 = next(r for r in results if r.rule_id == "R02")
    assert not r02.passed and problem in r02.detail


def test_icd10_fiscal_years_start_on_1_october() -> None:
    assert icd10_fiscal_year(date(2026, 9, 30)) == 2026
    assert icd10_fiscal_year(date(2026, 10, 1)) == 2027


def test_a_date_of_service_in_a_fiscal_year_with_no_code_set_is_a_reference_gap() -> None:
    with pytest.raises(MissingReference, match="FY2026"):
        check_group_a(claim_data(service_lines=[line(date_of_service="2026-09-30")]), reference())


def test_an_unknown_member_fails_r04() -> None:
    _, results = check_group_a(claim_data(member_id="MBR-999999"), reference())

    assert failures(results) == [("R04", "RJ_MEMBER_NOT_FOUND")]


def _on_file(status: str = "AWAITING_REVIEW", claim_id: str = "CLM-OLD") -> ExistingClaimLine:
    return ExistingClaimLine(claim_id, "MBR-000123", PCP, date(2026, 10, 5), "99213", status)


def test_a_line_repeating_a_claim_on_file_is_a_duplicate() -> None:
    _, results = check_group_a(claim_data(), reference(existing_claims=(_on_file(),)))

    assert failures(results) == [("DUP", "RJ_DUPLICATE")]
    assert "line 1 repeats claim CLM-OLD" in results[-1].detail


@pytest.mark.parametrize(
    "existing",
    [_on_file(status="REJECTED"), _on_file(claim_id="CLM-0001")],
    ids=["rejected-claim", "the-claim-itself"],
)
def test_rejected_claims_and_the_claim_itself_are_not_duplicates(
    existing: ExistingClaimLine,
) -> None:
    _, results = check_group_a(claim_data(), reference(existing_claims=(existing,)))

    assert failures(results) == []
