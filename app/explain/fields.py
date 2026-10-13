"""Claim fields in plain words, for the provider's "what to check" list: a field path's label
("service_lines.1.procedure_code" -> "Procedure code on line 2") and the value the claim carries,
formatted as on the form (dates MM/DD/YYYY, diagnoses with their dot, charges in dollars). The
claim is the dictionary stored at intake, which may fail the contract, so every lookup is
defensive: a value that is not there reads as "not on the claim"."""

import re
from collections.abc import Mapping
from typing import Any

from app.explain.render import money

NOT_ON_CLAIM = "not on the claim"
CLAIM_FIELDS = {
    "claim_id": "Claim control number",
    "member_id": "Member ID",
    "received_date": "Date received",
    "billing_npi": "Billing provider NPI",
    "billing_tin": "Billing provider tax ID",
    "referring_npi": "Referring provider NPI",
    "prior_auth_number": "Prior authorization number",
    "subscriber_is_patient": "Patient is the insured",
    "frequency_code": "Claim frequency code",
    "clinical_notes": "Clinical notes",
    "diagnoses": "Diagnosis codes",
    "service_lines": "Service lines",
    "patient": "Patient",
    "patient.first_name": "Patient first name",
    "patient.last_name": "Patient last name",
    "patient.date_of_birth": "Patient date of birth",
    "patient.sex": "Patient sex",
    "patient.address": "Patient address",
    "patient.address.line1": "Patient street address",
    "patient.address.city": "Patient city",
    "patient.address.state": "Patient state",
    "patient.address.zip_code": "Patient ZIP code",
    "other_coverage": "Other insurance",
    "other_coverage.payer_name": "Other insurance plan name",
    "other_coverage.primary_paid": "Other insurance payments",
}
LINE_FIELDS = {
    "date_of_service": "Date of service",
    "place_of_service": "Place of service",
    "procedure_code": "Procedure code",
    "modifiers": "Modifiers",
    "diagnosis_pointers": "Diagnosis pointers",
    "units": "Units",
    "charge_cents": "Charge",
    "rendering_npi": "Rendering provider NPI",
    "line_no": "Line number",
}
LINE_PATH = re.compile(r"^service_lines\.(\d+)(?:\.(\w+))?")
DIAGNOSIS_PATH = re.compile(r"^diagnoses\.(\d+)$")
LETTERS = "ABCDEFGHIJKL"
DATE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")


def field_label(path: str) -> str:
    if found := LINE_PATH.match(path):
        index, name = int(found.group(1)), found.group(2)
        label = LINE_FIELDS.get(name or "", (name or "Service").replace("_", " ").capitalize())
        return f"{label} on line {index + 1}" if name else f"Service line {index + 1}"
    if found := DIAGNOSIS_PATH.match(path):
        index = int(found.group(1))
        return f"Diagnosis {LETTERS[index] if index < len(LETTERS) else index + 1}"
    if path.startswith("other_coverage.primary_paid."):
        return "Other insurance payment"
    return CLAIM_FIELDS.get(path, path.split(".")[-1].replace("_", " ").capitalize())


def lookup(claim: Mapping[str, Any], path: str) -> Any:  # noqa: ANN401
    """The value at a dotted path (0-based list indexes), or None."""
    value: Any = claim
    for part in path.split("."):
        if isinstance(value, Mapping):
            value = value.get(part)
        elif isinstance(value, list) and part.isdigit() and int(part) < len(value):
            value = value[int(part)]
        else:
            return None
    return value


def diagnosis(code: object) -> str:
    """An ICD-10-CM code as printed: the dot after the third character (E119 -> E11.9)."""
    text = str(code).strip().upper()
    return f"{text[:3]}.{text[3:]}" if len(text) > 3 and "." not in text else text


def shown(path: str, value: object) -> str:
    """A field's value as the claim form shows it."""
    if value == []:
        return "none"
    if value is None or value == "":
        return NOT_ON_CLAIM
    name = path.split(".")[-1]
    if isinstance(value, bool):
        return "yes" if value else "no"
    if name in ("charge_cents", "paid_cents") and isinstance(value, int):
        return money(value)
    if path == "diagnoses" and isinstance(value, list):
        return ", ".join(diagnosis(code) for code in value)
    if DIAGNOSIS_PATH.match(path):
        return diagnosis(value)
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    if isinstance(value, str) and (found := DATE.match(value)):
        return f"{found.group(2)}/{found.group(3)}/{found.group(1)}"
    return str(value)


def line_index(claim: Mapping[str, Any], line_no: int) -> int:
    """The position on the claim of the service line with this line number."""
    lines = claim.get("service_lines")
    if isinstance(lines, list):
        for index, line in enumerate(lines):
            if isinstance(line, Mapping) and line.get("line_no") == line_no:
                return index
    return line_no - 1


def line_numbers(claim: Mapping[str, Any]) -> list[int]:
    lines = claim.get("service_lines")
    if not isinstance(lines, list):
        return []
    return [
        line["line_no"] if isinstance(line, Mapping) and isinstance(line.get("line_no"), int) else i
        for i, line in enumerate(lines, start=1)
    ]


def line_diagnoses(claim: Mapping[str, Any], line_no: int) -> list[str]:
    """The diagnoses a line points to (its pointers, A to L), as printed."""
    line = lookup(claim, f"service_lines.{line_index(claim, line_no)}")
    codes = claim.get("diagnoses")
    if not isinstance(line, Mapping) or not isinstance(codes, list):
        return []
    found = []
    for pointer in line.get("diagnosis_pointers") or []:
        index = LETTERS.find(str(pointer))
        if 0 <= index < len(codes):
            found.append(diagnosis(codes[index]))
    return found
