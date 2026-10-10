"""Format checks for values read from our synthetic form (INSTRUCTIONS.md §8.2): a field whose
text fails its check gets confidence 0. Also the characters each box may hold, which the OCR
restricts recognition to (`ocr.py`).

Fields are layout field paths (`layout.py`); the kind of a field comes from its path.
"""

import re
from datetime import datetime

from app.domain.contracts import Sex, npi_is_valid
from app.intake.form_codec import PRIMARY_PAID
from app.intake.layout import DATE_FORMAT

DIGITS = "0123456789"
UPPER = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
IDENTIFIER = re.compile(r"^[A-Z0-9]+(?:-[A-Z0-9]+)*$")
PATTERNS = {
    "identifier": IDENTIFIER,
    "tin": re.compile(r"^[0-9]{9}$"),
    "zip": re.compile(r"^[0-9]{5}(?:-[0-9]{4})?$"),
    "state": re.compile(r"^[A-Z]{2}$"),
    "relationship": re.compile(r"^(?:SELF|OTHER)$"),
    "frequency": re.compile(r"^1$"),
    "diagnosis": re.compile(r"^[A-TV-Z][0-9][0-9AB](?:\.[0-9A-Z]{1,4})?$"),
    "procedure": re.compile(r"^(?:[0-9]{4}[0-9A-Z]|[A-Z][0-9]{4})$"),
    "modifiers": re.compile(r"^[0-9A-Z]{2}(?: [0-9A-Z]{2}){0,3}$"),
    "pointers": re.compile(r"^[A-L]{1,4}$"),
    "amount": re.compile(r"^[0-9]+\.[0-9]{2}$"),
    "units": re.compile(r"^[1-9][0-9]*$"),
    "place": re.compile(r"^[0-9]{2}$"),
    "primary_paid": PRIMARY_PAID,
    "sex": re.compile(rf"^(?:{'|'.join(s.value for s in Sex)})$"),
    "text": re.compile(r"\S"),
}
# Characters each kind of box may hold; None: any (names, addresses, notes).
ALPHABETS: dict[str, str | None] = {
    "identifier": UPPER + DIGITS + "-",
    "tin": DIGITS,
    "npi": DIGITS,
    "zip": DIGITS + "-",
    "state": UPPER,
    "relationship": UPPER,
    "frequency": DIGITS,
    "date": DIGITS + "/",
    "diagnosis": UPPER + DIGITS + ".",
    "procedure": UPPER + DIGITS,
    "modifiers": UPPER + DIGITS,
    "pointers": "ABCDEFGHIJKL",
    "amount": DIGITS + ".",
    "units": DIGITS,
    "place": DIGITS,
    "primary_paid": "Line" + DIGITS + ":.",
    "sex": "".join(s.value for s in Sex),
    "text": None,
}
PAID_LOOSE = re.compile(r"^Line\s*([0-9]+)\s*:\s*([0-9]+\.[0-9]{2})$")
# Kinds whose value never holds a space: spaces read inside them are dropped.
NO_SPACES = {k for k in ALPHABETS if k not in ("modifiers", "primary_paid", "text")}


def kind(field: str) -> str:
    """The kind of a layout field path, e.g. `service_lines.0.units` -> `units`."""
    name = field.split(".")[-1]
    if field.startswith("diagnoses."):
        return "diagnosis"
    if field.startswith("other_coverage.primary_paid."):
        return "primary_paid"
    if name.endswith("npi"):
        return "npi"
    if name in ("received_date", "date_of_birth", "date_of_service"):
        return "date"
    return {
        "claim_id": "identifier",
        "member_id": "identifier",
        "prior_auth_number": "identifier",
        "billing_tin": "tin",
        "zip_code": "zip",
        "state": "state",
        "subscriber_is_patient": "relationship",
        "frequency_code": "frequency",
        "procedure_code": "procedure",
        "modifiers": "modifiers",
        "diagnosis_pointers": "pointers",
        "charge_cents": "amount",
        "units": "units",
        "place_of_service": "place",
        "sex": "sex",
    }.get(name, "text")


def canonical(field: str, text: str) -> str:
    """The text read for a field in the form's own spacing: no spaces in a code or number, two-
    character modifiers one space apart, `Line N: 0.00` for a primary payment."""
    found = kind(field)
    if found in NO_SPACES:
        return text.replace(" ", "")
    if found == "modifiers":
        joined = text.replace(" ", "")
        if len(joined) % 2 == 0:
            return " ".join(joined[i : i + 2] for i in range(0, len(joined), 2))
    if found == "primary_paid":
        match = PAID_LOOSE.match(text)
        if match:
            return f"Line {match.group(1)}: {match.group(2)}"
    return text


def format_ok(field: str, text: str) -> bool:
    """Does the text read for a field pass the field's format check?"""
    found = kind(field)
    if found == "npi":
        return npi_is_valid(text)
    if found == "date":
        try:
            datetime.strptime(text, DATE_FORMAT)
        except ValueError:
            return False
        return True
    pattern = PATTERNS[found]
    return bool(pattern.search(text) if found == "text" else pattern.match(text))
