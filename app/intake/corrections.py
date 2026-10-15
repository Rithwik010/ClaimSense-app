"""Corrections to a claim read from our form, before it is processed (D-FIX-1).

A provider corrects what the reading got wrong in the boxes of the form: a misread NPI, a code, a
date. A correction is the box's text as the form prints it (dates MM/DD/YYYY, charges 132.00,
diagnoses M54.5, modifiers "25 59", pointers "AB"), checked by the same format check as a value
read from the form (`field_formats.py`), and the claim is rebuilt from the boxes by the same
parser (`form_codec.from_form_values`), so a corrected claim is exactly the claim the form would
have given. An empty text clears the box. The claim control number cannot be corrected (it names
the claim), nor the claim frequency (always 1, original claims only) or the clinical notes (the
attachment is evidence, and the original file is kept as sent).
"""

from collections.abc import Mapping
from datetime import date
from typing import Any

from app.intake.field_formats import canonical, format_ok, kind
from app.intake.form_codec import (
    format_amount,
    format_date,
    format_icd10,
    from_form_values,
)
from app.intake.layout import ALL_PAGE_ONE_BOXES, MAX_LINES_PER_FORM, PRIMARY_PAID_BOXES

FIXED = frozenset({"claim_id", "frequency_code"})
CORRECTABLE = frozenset(box.field for box in ALL_PAGE_ONE_BOXES + PRIMARY_PAID_BOXES) - FIXED
UPPER_KINDS = frozenset(
    {
        "identifier",
        "state",
        "relationship",
        "diagnosis",
        "procedure",
        "modifiers",
        "pointers",
        "sex",
    }
)
HINTS = {
    "identifier": "letters, digits and hyphens",
    "tin": "9 digits",
    "npi": "a 10-digit NPI with a valid check digit",
    "zip": "5 digits, or 5 digits, a hyphen and 4 digits",
    "state": "a two-letter state code",
    "relationship": "SELF or OTHER",
    "date": "a date as MM/DD/YYYY",
    "diagnosis": "an ICD-10-CM code such as M54.5",
    "procedure": "a five-character procedure code",
    "modifiers": "up to four two-character modifiers, one space apart",
    "pointers": "one to four diagnosis letters, A to L, such as AB",
    "amount": "dollars and cents, such as 132.00",
    "units": "a whole number from 1",
    "place": "a two-digit place of service code",
    "primary_paid": "Line N: dollars and cents, such as Line 1: 40.00",
    "sex": "F, M or U",
    "text": "some text",
}


class CorrectionRefused(ValueError):
    """A correction that cannot be made: `field` names the box."""

    def __init__(self, field: str, problem: str) -> None:
        super().__init__(f"{field}: {problem}")
        self.field = field
        self.problem = problem


def _text(value: object) -> str | None:
    if value is None or value == "":
        return None
    return str(value)


def _date_text(value: object) -> str | None:
    if isinstance(value, str):
        try:
            return format_date(date.fromisoformat(value))
        except ValueError:
            return value or None
    return _text(value)


def _amount_text(value: object) -> str | None:
    if isinstance(value, int) and not isinstance(value, bool):
        return format_amount(value)
    return _text(value)


def _diagnosis_text(value: object) -> str | None:
    if isinstance(value, str) and value and "." not in value:
        return format_icd10(value)
    return _text(value)


def form_text(claim: Mapping[str, Any]) -> dict[str, str]:
    """The claim's boxes as the form prints them: the inverse of `from_form_values`, for a claim
    as stored at intake (a validated claim, or the raw values of one that failed the contract, so
    every value is read defensively). A service line goes in the form row of its line number."""
    values: dict[str, str | None] = {
        "claim_id": _text(claim.get("claim_id")),
        "received_date": _date_text(claim.get("received_date")),
        "member_id": _text(claim.get("member_id")),
        "billing_tin": _text(claim.get("billing_tin")),
        "billing_npi": _text(claim.get("billing_npi")),
        "referring_npi": _text(claim.get("referring_npi")),
        "prior_auth_number": _text(claim.get("prior_auth_number")),
        "frequency_code": _text(claim.get("frequency_code")),
        "clinical_notes": _text(claim.get("clinical_notes")),
    }
    relationship = claim.get("subscriber_is_patient")
    values["subscriber_is_patient"] = (
        {True: "SELF", False: "OTHER"}[relationship]
        if isinstance(relationship, bool)
        else _text(relationship)
    )
    patient = claim.get("patient")
    if isinstance(patient, Mapping):
        for name in ("first_name", "last_name", "sex"):
            values[f"patient.{name}"] = _text(patient.get(name))
        values["patient.date_of_birth"] = _date_text(patient.get("date_of_birth"))
        address = patient.get("address")
        if isinstance(address, Mapping):
            for name in ("line1", "city", "state", "zip_code"):
                values[f"patient.address.{name}"] = _text(address.get(name))
    diagnoses = claim.get("diagnoses")
    for i, code in enumerate(diagnoses if isinstance(diagnoses, list) else []):
        values[f"diagnoses.{i}"] = _diagnosis_text(code)
    lines = claim.get("service_lines")
    for i, line in enumerate(lines if isinstance(lines, list) else []):
        if not isinstance(line, Mapping):
            continue
        number = line.get("line_no")
        row = number - 1 if isinstance(number, int) and 1 <= number <= MAX_LINES_PER_FORM else i
        prefix = f"service_lines.{row}."
        modifiers, pointers = line.get("modifiers"), line.get("diagnosis_pointers")
        values[prefix + "date_of_service"] = _date_text(line.get("date_of_service"))
        values[prefix + "place_of_service"] = _text(line.get("place_of_service"))
        values[prefix + "procedure_code"] = _text(line.get("procedure_code"))
        values[prefix + "modifiers"] = (
            " ".join(str(m) for m in modifiers) if isinstance(modifiers, list) else None
        ) or None
        values[prefix + "diagnosis_pointers"] = (
            "".join(str(p) for p in pointers) if isinstance(pointers, list) else _text(pointers)
        ) or None
        values[prefix + "charge_cents"] = _amount_text(line.get("charge_cents"))
        values[prefix + "units"] = _text(line.get("units"))
        values[prefix + "rendering_npi"] = _text(line.get("rendering_npi"))
    other = claim.get("other_coverage")
    if isinstance(other, Mapping):
        values["other_coverage.payer_name"] = _text(other.get("payer_name"))
        paid = other.get("primary_paid")
        for row, payment in enumerate(paid if isinstance(paid, list) else []):
            if isinstance(payment, Mapping):
                values[f"other_coverage.primary_paid.{row}"] = (
                    f"Line {payment.get('line_no')}: {_amount_text(payment.get('paid_cents'))}"
                )
    return {field: text for field, text in values.items() if text}


def corrected_text(field: str, text: str) -> str:
    """The correction as the form prints it, or `CorrectionRefused`. Codes are upper-cased and
    spaced as the form spaces them; an empty text clears the box."""
    if field not in CORRECTABLE:
        raise CorrectionRefused(field, "this box cannot be corrected")
    found = kind(field)
    cleaned = " ".join(text.split()) if found != "text" else text.strip()
    if found in UPPER_KINDS:
        cleaned = cleaned.upper()
    cleaned = canonical(field, cleaned)
    if cleaned and not format_ok(field, cleaned):
        raise CorrectionRefused(field, f"enter {HINTS[found]}")
    return cleaned


def apply_corrections(claim: Mapping[str, Any], corrections: Mapping[str, str]) -> dict[str, Any]:
    """The claim rebuilt from its boxes with the corrections made (each checked first)."""
    values = form_text(claim)
    for field, text in corrections.items():
        cleaned = corrected_text(field, text)
        if cleaned:
            values[field] = cleaned
        else:
            values.pop(field, None)
    return from_form_values(values)
