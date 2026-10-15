"""D-FIX-1: corrections to a claim read from our form, as the form prints each box, checked by the
box's format check and parsed by the same parser as a reading."""

import json
from pathlib import Path

import pytest

from app.domain.contracts import IntakeClaim
from app.intake.corrections import (
    CORRECTABLE,
    CorrectionRefused,
    apply_corrections,
    corrected_text,
    form_text,
)
from app.intake.form_codec import from_form_values, to_form_values
from app.intake.layout import MAX_LINES_PER_FORM

ROOT = Path(__file__).resolve().parents[2]
CASES = json.loads((ROOT / "tests" / "golden" / "e2e" / "cases.json").read_text())["cases"]
DEMO = sorted((ROOT / "demo" / "claims").glob("*.json"))
VALID_NPI = "1234567893"


def claims() -> list[IntakeClaim]:
    found = [c["given"]["claim"] for c in CASES]
    found += [json.loads(path.read_text()) for path in DEMO]
    valid = []
    for data in found:
        try:
            claim = IntakeClaim.model_validate(data)
        except ValueError:
            continue
        if len(claim.service_lines) <= MAX_LINES_PER_FORM:
            valid.append(claim)
    return valid


def demo_claim() -> IntakeClaim:
    return IntakeClaim.model_validate(json.loads(DEMO[0].read_text()))


def test_form_text_is_what_the_form_prints_for_every_valid_claim() -> None:
    found = claims()
    assert len(found) >= 20
    for claim in found:
        boxes = form_text(claim.model_dump(mode="json"))
        assert boxes == to_form_values(claim), claim.claim_id
        assert IntakeClaim.model_validate(from_form_values(boxes)) == claim


def test_a_claim_that_failed_the_contract_round_trips_as_read() -> None:
    values = to_form_values(demo_claim())
    values["billing_npi"] = "1234567890"  # fails the check digit
    values["service_lines.0.units"] = "1O"  # a letter read for a digit
    raw = from_form_values(values)
    assert from_form_values(form_text(raw)) == raw


def test_a_misread_npi_is_corrected_and_the_claim_then_validates() -> None:
    values = to_form_values(demo_claim())
    values["billing_npi"] = "1234567890"
    raw = from_form_values(values)
    with pytest.raises(ValueError):
        IntakeClaim.model_validate(raw)

    fixed = apply_corrections(raw, {"billing_npi": f" {VALID_NPI} "})

    claim = IntakeClaim.model_validate(fixed)
    assert claim.billing_npi == VALID_NPI
    assert claim.model_dump(exclude={"billing_npi"}) == demo_claim().model_dump(
        exclude={"billing_npi"}
    )


def test_corrections_are_written_as_the_form_prints_them() -> None:
    claim = demo_claim().model_dump(mode="json")
    fixed = apply_corrections(
        claim,
        {
            "service_lines.0.modifiers": "59xu",
            "diagnoses.0": "m54.5",
            "service_lines.0.date_of_service": "11/27/2026",
            "service_lines.0.charge_cents": "140.00",
        },
    )
    line = fixed["service_lines"][0]
    assert line["modifiers"] == ["59", "XU"]
    assert fixed["diagnoses"][0] == "M54.5"
    assert line["date_of_service"] == "2026-11-27"
    assert line["charge_cents"] == 14000
    assert IntakeClaim.model_validate(fixed).diagnoses[0] == "M545"


def test_an_empty_correction_clears_the_box() -> None:
    claim = demo_claim().model_dump(mode="json")
    claim["referring_npi"] = VALID_NPI
    assert apply_corrections(claim, {"referring_npi": "  "})["referring_npi"] is None


@pytest.mark.parametrize("field", ["claim_id", "frequency_code", "clinical_notes", "no_such_box"])
def test_boxes_that_cannot_be_corrected(field: str) -> None:
    assert field not in CORRECTABLE
    with pytest.raises(CorrectionRefused, match="cannot be corrected"):
        corrected_text(field, "X")


@pytest.mark.parametrize(
    ("field", "text", "hint"),
    [
        ("billing_npi", "1234567890", "check digit"),
        ("service_lines.0.date_of_service", "2026-11-27", "MM/DD/YYYY"),
        ("service_lines.0.charge_cents", "$140", "dollars and cents"),
        ("service_lines.0.units", "0", "whole number"),
        ("diagnoses.1", "54.5", "ICD-10-CM"),
    ],
)
def test_a_correction_must_pass_the_box_format_check(field: str, text: str, hint: str) -> None:
    with pytest.raises(CorrectionRefused, match=hint) as refused:
        apply_corrections(demo_claim().model_dump(mode="json"), {field: text})
    assert refused.value.field == field


def test_every_box_but_the_claim_number_frequency_and_notes_can_be_corrected() -> None:
    assert "billing_npi" in CORRECTABLE
    assert "member_id" in CORRECTABLE
    assert f"service_lines.{MAX_LINES_PER_FORM - 1}.rendering_npi" in CORRECTABLE
    assert "other_coverage.primary_paid.0" in CORRECTABLE
