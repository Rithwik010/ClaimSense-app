"""Contract validators (INSTRUCTIONS.md §8.1, P1.4): formats, money types and cross-field rules."""

from datetime import date
from typing import Any

import pytest
from pydantic import ValidationError

from app.domain.contracts import (
    CriterionStatus,
    IntakeClaim,
    ReviewAction,
    SLMOutput,
    npi_is_valid,
)


def claim_data(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "claim_id": "CLM-0001",
        "member_id": "MBR-000123",
        "patient": {
            "first_name": "Asha",
            "last_name": "Rao",
            "date_of_birth": "1981-04-02",
            "sex": "F",
            "address": {"line1": "12 Elm St", "city": "Austin", "state": "TX", "zip_code": "78701"},
        },
        "subscriber_is_patient": True,
        "billing_npi": "1234567893",
        "billing_tin": "123456789",
        "referring_npi": None,
        "prior_auth_number": None,
        "diagnoses": ["M54.16", "M5416"],
        "service_lines": [
            {
                "line_no": 1,
                "date_of_service": "2026-10-05",
                "place_of_service": "11",
                "procedure_code": "99213",
                "modifiers": [],
                "diagnosis_pointers": ["A"],
                "units": 1,
                "charge_cents": 15000,
                "rendering_npi": "1234567893",
            }
        ],
        "clinical_notes": "Low back pain radiating to the left leg for six weeks.",
        "received_date": "2026-10-12",
        "frequency_code": "1",
        "other_coverage": None,
    }
    data.update(overrides)
    return data


def line(**overrides: Any) -> dict[str, Any]:
    base = claim_data()["service_lines"][0]
    return {**base, **overrides}


# --- NPI check digit ---------------------------------------------------------------------------


@pytest.mark.parametrize("npi", ["1234567893", "1245319599"])
def test_valid_npi_check_digits(npi: str) -> None:
    assert npi_is_valid(npi)


@pytest.mark.parametrize("npi", ["1234567890", "123456789", "12345678931", "12345678A3"])
def test_invalid_npis(npi: str) -> None:
    assert not npi_is_valid(npi)


def test_claim_rejects_bad_billing_npi() -> None:
    with pytest.raises(ValidationError, match="NPI"):
        IntakeClaim.model_validate(claim_data(billing_npi="1234567890"))


# --- Codes -------------------------------------------------------------------------------------


def test_diagnoses_are_normalized_without_dots() -> None:
    claim = IntakeClaim.model_validate(claim_data(diagnoses=["m54.16"]))
    assert claim.diagnoses == ["M5416"]


@pytest.mark.parametrize("code", ["54.16", "M5", "MM5416", "M5416XXXX"])
def test_malformed_diagnoses_are_rejected(code: str) -> None:
    with pytest.raises(ValidationError):
        IntakeClaim.model_validate(claim_data(diagnoses=[code]))


def test_diagnosis_count_is_one_to_twelve() -> None:
    with pytest.raises(ValidationError):
        IntakeClaim.model_validate(claim_data(diagnoses=[]))
    with pytest.raises(ValidationError):
        IntakeClaim.model_validate(claim_data(diagnoses=["M5416"] * 13))


@pytest.mark.parametrize("code", ["99213", "0591T", "G0121", "E0601"])
def test_procedure_code_formats_accepted(code: str) -> None:
    IntakeClaim.model_validate(claim_data(service_lines=[line(procedure_code=code)]))


@pytest.mark.parametrize("code", ["9921", "992131", "99-13", "g0121"])
def test_procedure_code_formats_rejected(code: str) -> None:
    with pytest.raises(ValidationError):
        IntakeClaim.model_validate(claim_data(service_lines=[line(procedure_code=code)]))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("place_of_service", "1"),
        ("modifiers", ["2"]),
        ("modifiers", ["25", "59", "XS", "LT", "RT"]),
    ],
)
def test_line_code_formats_rejected(field: str, value: Any) -> None:
    with pytest.raises(ValidationError):
        IntakeClaim.model_validate(claim_data(service_lines=[line(**{field: value})]))


# --- Money -------------------------------------------------------------------------------------


@pytest.mark.parametrize("charge", [-1, 150.5, "15000"])
def test_charge_must_be_non_negative_integer_cents(charge: Any) -> None:
    with pytest.raises(ValidationError):
        IntakeClaim.model_validate(claim_data(service_lines=[line(charge_cents=charge)]))


def test_units_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        IntakeClaim.model_validate(claim_data(service_lines=[line(units=0)]))


# --- Cross-field rules -------------------------------------------------------------------------


def test_diagnosis_pointer_must_reference_a_listed_diagnosis() -> None:
    with pytest.raises(ValidationError, match="pointer"):
        IntakeClaim.model_validate(claim_data(service_lines=[line(diagnosis_pointers=["C"])]))


def test_line_numbers_must_be_sequential_from_one() -> None:
    with pytest.raises(ValidationError, match="line_no"):
        IntakeClaim.model_validate(claim_data(service_lines=[line(line_no=2)]))


def test_only_original_claims_are_in_scope() -> None:
    with pytest.raises(ValidationError):
        IntakeClaim.model_validate(claim_data(frequency_code="7"))


def test_other_coverage_must_reference_existing_lines() -> None:
    other = {"payer_name": "Acme Health", "primary_paid": [{"line_no": 2, "paid_cents": 5000}]}
    with pytest.raises(ValidationError, match="line_no"):
        IntakeClaim.model_validate(claim_data(other_coverage=other))


def test_valid_claim_round_trips_through_json() -> None:
    claim = IntakeClaim.model_validate(claim_data())
    assert IntakeClaim.model_validate_json(claim.model_dump_json()) == claim
    assert claim.service_lines[0].date_of_service == date(2026, 10, 5)


def test_unknown_fields_are_rejected() -> None:
    with pytest.raises(ValidationError):
        IntakeClaim.model_validate(claim_data(covered_service=True))


# --- SLM output --------------------------------------------------------------------------------


def slm_output(**line_overrides: Any) -> dict[str, Any]:
    slm_line = {
        "line_no": 1,
        "decision": "APPROVE",
        "benefit_category": "OFFICE_VISIT_PCP",
        "criteria": [],
        "reasons": [],
        "missing_information": [],
    }
    slm_line.update(line_overrides)
    return {"lines": [slm_line], "complexity": "LOW"}


def test_slm_output_schema_is_strict_and_has_no_money_fields() -> None:
    schema = SLMOutput.model_json_schema()
    objects = [schema, *schema["$defs"].values()]
    fields = {name for obj in objects for name in obj.get("properties", {})}

    assert all(obj["additionalProperties"] is False for obj in objects if obj["type"] == "object")
    assert not [f for f in fields if "cents" in f or "amount" in f or "pay" in f]


def test_slm_output_rejects_money_fields() -> None:
    with pytest.raises(ValidationError):
        SLMOutput.model_validate(slm_output(plan_pays_cents=1000))


def test_criterion_ids_must_look_like_policy_criteria() -> None:
    bad = [{"criterion_id": "c1", "status": "MET", "evidence": "notes"}]
    with pytest.raises(ValidationError):
        SLMOutput.model_validate(slm_output(criteria=bad))
    good = [{"criterion_id": "POL-IMG-001.c2", "status": "MET", "evidence": "notes"}]
    SLMOutput.model_validate(slm_output(criteria=good))


def test_criterion_status_has_four_values_and_no_boolean() -> None:
    assert [s.value for s in CriterionStatus] == [
        "MET",
        "NOT_MET",
        "NOT_DOCUMENTED",
        "NOT_APPLICABLE",
    ]
    old = [{"criterion_id": "POL-IMG-001.c2", "met": True, "evidence": "notes"}]
    with pytest.raises(ValidationError):
        SLMOutput.model_validate(slm_output(criteria=old))


# --- Review action -----------------------------------------------------------------------------


def review(**overrides: Any) -> dict[str, Any]:
    data = {
        "claim_id": "CLM-0001",
        "reviewer_id": "reviewer-1",
        "action": "ACCEPT",
        "line_overrides": [],
        "timestamp": "2026-10-20T10:00:00Z",
    }
    data.update(overrides)
    return data


def test_accept_has_no_overrides() -> None:
    ReviewAction.model_validate(review())
    with pytest.raises(ValidationError):
        ReviewAction.model_validate(
            review(line_overrides=[{"line_no": 1, "decision": "DENY", "reason": "No notes"}])
        )


def test_override_needs_at_least_one_line_with_a_reason() -> None:
    with pytest.raises(ValidationError):
        ReviewAction.model_validate(review(action="OVERRIDE"))
    with pytest.raises(ValidationError):
        ReviewAction.model_validate(
            review(
                action="OVERRIDE",
                line_overrides=[{"line_no": 1, "decision": "DENY", "reason": " "}],
            )
        )
    ReviewAction.model_validate(
        review(
            action="OVERRIDE",
            line_overrides=[
                {"line_no": 1, "decision": "DENY", "reason": "Notes do not show 6 weeks of therapy"}
            ],
        )
    )
