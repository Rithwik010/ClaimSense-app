"""How claim fields are written on our synthetic form and read back (layout in `layout.py`).

`to_form_values` is used by the form renderer; `from_form_values` by the parsers. Round trip:
`from_form_values(to_form_values(claim))` validates to the same `IntakeClaim`. Blank required boxes
are left out of the result so contract validation reports them as missing (rule R01).
Amounts are parsed from their digits, never through float (H2).
"""

import re
from datetime import date, datetime
from typing import Any

from app.domain.contracts import IntakeClaim
from app.intake.layout import DATE_FORMAT, LINE_COLUMNS, MAX_DIAGNOSES, MAX_LINES_PER_FORM

PRIMARY_PAID = re.compile(r"^Line ([0-9]+): ([0-9]+)\.([0-9]{2})$")
AMOUNT = re.compile(r"^([0-9]+)\.([0-9]{2})$")


def format_date(value: date) -> str:
    return value.strftime(DATE_FORMAT)


def format_amount(cents: int) -> str:
    return f"{cents // 100}.{cents % 100:02d}"


def format_icd10(code: str) -> str:
    return f"{code[:3]}.{code[3:]}" if len(code) > 3 else code


def to_form_values(claim: IntakeClaim) -> dict[str, str]:
    """Every box's printed value, keyed by the layout field path (blank boxes are omitted)."""
    if len(claim.service_lines) > MAX_LINES_PER_FORM:
        raise ValueError(f"the form holds at most {MAX_LINES_PER_FORM} service lines")
    patient = claim.patient
    values = {
        "claim_id": claim.claim_id,
        "received_date": format_date(claim.received_date),
        "member_id": claim.member_id,
        "patient.last_name": patient.last_name,
        "patient.first_name": patient.first_name,
        "patient.date_of_birth": format_date(patient.date_of_birth),
        "patient.sex": patient.sex.value,
        "patient.address.line1": patient.address.line1,
        "patient.address.city": patient.address.city,
        "patient.address.state": patient.address.state,
        "patient.address.zip_code": patient.address.zip_code,
        "subscriber_is_patient": "SELF" if claim.subscriber_is_patient else "OTHER",
        "frequency_code": claim.frequency_code,
        "billing_tin": claim.billing_tin,
        "billing_npi": claim.billing_npi,
        "clinical_notes": claim.clinical_notes,
    }
    if claim.referring_npi:
        values["referring_npi"] = claim.referring_npi
    if claim.prior_auth_number:
        values["prior_auth_number"] = claim.prior_auth_number
    for i, code in enumerate(claim.diagnoses):
        values[f"diagnoses.{i}"] = format_icd10(code)
    for row, line in enumerate(claim.service_lines):
        prefix = f"service_lines.{row}."
        values[prefix + "date_of_service"] = format_date(line.date_of_service)
        values[prefix + "place_of_service"] = line.place_of_service
        values[prefix + "procedure_code"] = line.procedure_code
        if line.modifiers:
            values[prefix + "modifiers"] = " ".join(line.modifiers)
        values[prefix + "diagnosis_pointers"] = "".join(line.diagnosis_pointers)
        values[prefix + "charge_cents"] = format_amount(line.charge_cents)
        values[prefix + "units"] = str(line.units)
        values[prefix + "rendering_npi"] = line.rendering_npi
    if claim.other_coverage:
        values["other_coverage.payer_name"] = claim.other_coverage.payer_name
        for row, payment in enumerate(claim.other_coverage.primary_paid):
            values[f"other_coverage.primary_paid.{row}"] = (
                f"Line {payment.line_no}: {format_amount(payment.paid_cents)}"
            )
    return {k: v for k, v in values.items() if v != ""}


def _date(text: str) -> str | None:
    try:
        return datetime.strptime(text, DATE_FORMAT).date().isoformat()
    except ValueError:
        return None


def _amount(text: str) -> int | None:
    match = AMOUNT.match(text)
    return int(match.group(1)) * 100 + int(match.group(2)) if match else None


def _int(text: str) -> int | None:
    return int(text) if text.isdigit() else None


def from_form_values(values: dict[str, str]) -> dict[str, Any]:
    """Rebuild the claim dictionary from box values. Unreadable values are kept as text so the
    contract validator (and rules R01–R03) can report them."""

    def get(field: str) -> str | None:
        text = values.get(field, "").strip()
        return text or None

    def put(target: dict[str, Any], key: str, value: Any) -> None:
        if value is not None:
            target[key] = value

    claim: dict[str, Any] = {}
    for field in ("claim_id", "member_id", "billing_tin", "billing_npi"):
        put(claim, field, get(field))
    put(claim, "received_date", _date(get("received_date") or "") or get("received_date"))
    claim["referring_npi"] = get("referring_npi")
    claim["prior_auth_number"] = get("prior_auth_number")
    claim["frequency_code"] = get("frequency_code") or "1"
    claim["clinical_notes"] = get("clinical_notes") or ""
    relationship = get("subscriber_is_patient")
    if relationship is not None:
        claim["subscriber_is_patient"] = {"SELF": True, "OTHER": False}.get(
            relationship, relationship
        )

    patient: dict[str, Any] = {}
    for name in ("first_name", "last_name", "sex"):
        put(patient, name, get(f"patient.{name}"))
    dob = get("patient.date_of_birth")
    put(patient, "date_of_birth", (_date(dob) or dob) if dob else None)
    address: dict[str, Any] = {}
    for name in ("line1", "city", "state", "zip_code"):
        put(address, name, get(f"patient.address.{name}"))
    if address:
        patient["address"] = address
    if patient:
        claim["patient"] = patient

    claim["diagnoses"] = [d for i in range(MAX_DIAGNOSES) if (d := get(f"diagnoses.{i}"))]

    lines = []
    for row in range(MAX_LINES_PER_FORM):
        prefix = f"service_lines.{row}."
        raw = {name: get(prefix + name) for name, _, _, _ in LINE_COLUMNS}
        if not any(raw.values()):
            continue
        line: dict[str, Any] = {"line_no": row + 1}
        if raw["date_of_service"]:
            line["date_of_service"] = _date(raw["date_of_service"]) or raw["date_of_service"]
        put(line, "place_of_service", raw["place_of_service"])
        put(line, "procedure_code", raw["procedure_code"])
        line["modifiers"] = raw["modifiers"].split() if raw["modifiers"] else []
        if raw["diagnosis_pointers"]:
            line["diagnosis_pointers"] = list(raw["diagnosis_pointers"])
        if raw["charge_cents"]:
            amount = _amount(raw["charge_cents"])
            line["charge_cents"] = amount if amount is not None else raw["charge_cents"]
        if raw["units"]:
            units = _int(raw["units"])
            line["units"] = units if units is not None else raw["units"]
        put(line, "rendering_npi", raw["rendering_npi"])
        lines.append(line)
    claim["service_lines"] = lines

    payer = get("other_coverage.payer_name")
    if payer:
        paid = []
        for row in range(MAX_LINES_PER_FORM):
            match = PRIMARY_PAID.match(get(f"other_coverage.primary_paid.{row}") or "")
            if match:
                paid.append(
                    {
                        "line_no": int(match.group(1)),
                        "paid_cents": int(match.group(2)) * 100 + int(match.group(3)),
                    }
                )
        claim["other_coverage"] = {"payer_name": payer, "primary_paid": paid}
    else:
        claim["other_coverage"] = None
    return claim
