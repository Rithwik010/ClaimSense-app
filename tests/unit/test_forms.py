"""P3.4 forms: the digital PDF re-parses to the original claim exactly; scanned copies record their
value noise (INSTRUCTIONS.md §9.4, §11)."""

import random
from typing import Any

import pytest
from pydantic import ValidationError

from app.domain.contracts import IntakeClaim
from app.intake.digital_pdf import parse_digital_pdf, read_form_values
from app.intake.form_codec import from_form_values, to_form_values
from app.intake.layout import ALL_PAGE_ONE_BOXES, NOTES_BOX, PAGE_HEIGHT, PAGE_WIDTH
from training.generate.forms import render_pdf, render_scan


def full_claim(**overrides: Any) -> IntakeClaim:
    lines = [
        {
            "line_no": n,
            "date_of_service": f"2026-10-{n + 4:02d}",
            "place_of_service": "11",
            "procedure_code": code,
            "modifiers": mods,
            "diagnosis_pointers": ptrs,
            "units": units,
            "charge_cents": charge,
            "rendering_npi": "1234567893",
        }
        for n, (code, mods, ptrs, units, charge) in enumerate(
            [
                ("99213", [], ["A"], 1, 15000),
                ("11042", [], ["B", "C"], 1, 26505),
                ("97597", ["XS", "RT"], ["B"], 1, 20500),
                ("97110", [], ["A", "B", "C", "D"], 4, 24000),
                ("G0121", [], ["L"], 1, 99999),
                ("29581", ["LT"], ["A"], 2, 1),
            ],
            start=1,
        )
    ]
    data: dict[str, Any] = {
        "claim_id": "CLM-FORM-0001",
        "member_id": "MBR-000123",
        "patient": {
            "first_name": "Mary Ann",
            "last_name": "O'Neil-Smith",
            "date_of_birth": "1951-12-31",
            "sex": "F",
            "address": {
                "line1": "12 Elm St Apt. 4, Unit B",
                "city": "Salt Lake City",
                "state": "UT",
                "zip_code": "84101-1234",
            },
        },
        "subscriber_is_patient": False,
        "billing_npi": "1245319599",
        "billing_tin": "123456789",
        "referring_npi": "1234567893",
        "prior_auth_number": "AUTH-2026-00042",
        "diagnoses": [
            "M5416",
            "L97412",
            "E11621",
            "Z7901",
            "J069",
            "I10",
            "M1711",
            "R519",
            "G4733",
            "H2511",
            "K921",
            "Z860101",
        ],
        "service_lines": lines,
        "clinical_notes": "Ulcer on the right heel, 3 cm, down to the fat layer. "
        "Pain 7/10; (A1c 8.2%). " * 12,
        "received_date": "2026-10-20",
        "frequency_code": "1",
        "other_coverage": {
            "payer_name": "Northwind Health Plan",
            "primary_paid": [{"line_no": 1, "paid_cents": 5000}, {"line_no": 4, "paid_cents": 7}],
        },
    }
    data["clinical_notes"] = data["clinical_notes"].strip()
    data.update(overrides)
    return IntakeClaim.model_validate(data)


def test_digital_pdf_round_trips_exactly() -> None:
    claim = full_claim()
    assert IntakeClaim.model_validate(parse_digital_pdf(render_pdf(to_form_values(claim)))) == claim


def test_minimal_claim_round_trips() -> None:
    claim = full_claim(
        referring_npi=None,
        prior_auth_number=None,
        other_coverage=None,
        subscriber_is_patient=True,
        clinical_notes="",
        diagnoses=["M5416"],
        service_lines=[full_claim().service_lines[0].model_dump()],
    )
    assert IntakeClaim.model_validate(parse_digital_pdf(render_pdf(to_form_values(claim)))) == claim


def test_blank_required_box_is_reported_missing() -> None:
    values = to_form_values(full_claim())
    del values["member_id"]
    with pytest.raises(ValidationError) as error:
        IntakeClaim.model_validate(from_form_values(values))
    assert any(e["type"] == "missing" and e["loc"] == ("member_id",) for e in error.value.errors())


def test_every_box_fits_on_the_page_and_boxes_do_not_overlap() -> None:
    boxes = ALL_PAGE_ONE_BOXES
    for box in boxes + [NOTES_BOX]:
        assert 0 <= box.x0 < box.x1 <= PAGE_WIDTH and 0 <= box.y0 < box.y1 <= PAGE_HEIGHT
    for i, a in enumerate(boxes):
        for b in boxes[i + 1 :]:
            overlap = a.x0 < b.x1 and b.x0 < a.x1 and a.y0 < b.y1 and b.y0 < a.y1
            assert not overlap, (a.field, b.field)


def test_scan_without_value_noise_keeps_values() -> None:
    values = to_form_values(full_claim())
    scan = render_scan(values, random.Random(1), value_noise_rate=0.0)
    assert scan.values == values and "value" not in scan.noise
    assert len(scan.pages) == 2 and scan.pages[0].mode == "L"


@pytest.mark.parametrize("seed", range(12))
def test_scan_value_noise_is_logged_and_breaks_validation(seed: int) -> None:
    values = to_form_values(full_claim())
    scan = render_scan(values, random.Random(seed), value_noise_rate=1.0)
    noise = scan.noise["value"]
    assert values[noise["field"]] == noise["original"]
    assert scan.values.get(noise["field"]) == noise["written"]
    with pytest.raises(ValidationError):
        IntakeClaim.model_validate(from_form_values(scan.values))


def test_rendering_is_deterministic() -> None:
    values = to_form_values(full_claim())
    assert render_pdf(values) == render_pdf(values)
    assert read_form_values(render_pdf(values))["claim_id"] == "CLM-FORM-0001"
