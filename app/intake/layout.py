"""Form layout for ClaimSense's synthetic CMS-1500-style claim forms (INSTRUCTIONS.md §8.2, §9.4).

Every box is defined once here and used by both the renderer (`training/generate/forms.py`) and the
parsers in `app/intake/`. Coordinates are PDF points on a US Letter page (612 x 792), measured from
the top-left corner, as PyMuPDF reports them.

Limitation: these coordinates describe our own generated layout only. They are NOT valid for the
official printed CMS-1500 (02/12) form.
"""

from dataclasses import dataclass

PAGE_WIDTH, PAGE_HEIGHT = 612.0, 792.0
MAX_LINES_PER_FORM = 6  # like the CMS-1500, six service lines per page
MAX_DIAGNOSES = 12


@dataclass(frozen=True)
class Box:
    field: str  # claim field path, e.g. "patient.last_name" or "service_lines.0.units"
    label: str  # printed caption (CMS-1500 box number and name)
    x0: float
    y0: float
    x1: float
    y1: float
    page: int = 0

    @property
    def rect(self) -> tuple[float, float, float, float]:
        return (self.x0, self.y0, self.x1, self.y1)


def _box(field: str, label: str, x0: float, y0: float, x1: float, y1: float, page: int = 0) -> Box:
    return Box(field, label, x0, y0, x1, y1, page)


HEADER_BOXES = [
    _box("claim_id", "CLAIM CONTROL NO.", 30, 62, 250, 82),
    _box("received_date", "DATE RECEIVED", 420, 62, 582, 82),
]
PATIENT_BOXES = [
    _box("member_id", "1a. INSURED'S ID NUMBER", 330, 100, 582, 120),
    _box("patient.last_name", "2. PATIENT LAST NAME", 30, 138, 180, 158),
    _box("patient.first_name", "2. FIRST NAME", 185, 138, 330, 158),
    _box("patient.date_of_birth", "3. BIRTH DATE", 335, 138, 460, 158),
    _box("patient.sex", "3. SEX", 465, 138, 582, 158),
    _box("patient.address.line1", "5. PATIENT ADDRESS", 30, 176, 330, 196),
    _box("patient.address.city", "CITY", 335, 176, 470, 196),
    _box("patient.address.state", "STATE", 475, 176, 515, 196),
    _box("patient.address.zip_code", "ZIP CODE", 520, 176, 582, 196),
    _box("subscriber_is_patient", "6. RELATIONSHIP (SELF / OTHER)", 30, 214, 180, 234),
    _box("other_coverage.payer_name", "9d. OTHER INSURANCE PLAN NAME", 185, 214, 582, 234),
    _box("referring_npi", "17b. REFERRING NPI", 30, 252, 180, 272),
    _box("frequency_code", "22. CLAIM FREQUENCY", 185, 252, 330, 272),
    _box("prior_auth_number", "23. PRIOR AUTHORIZATION NUMBER", 335, 252, 582, 272),
]
DIAGNOSIS_BOXES = [
    _box(
        f"diagnoses.{i}",
        f"21{'ABCDEFGHIJKL'[i]}.",
        30 + (i % 4) * 138,
        290 + (i // 4) * 24,
        160 + (i % 4) * 138,
        308 + (i // 4) * 24,
    )
    for i in range(MAX_DIAGNOSES)
]
# Box 24 columns: (field suffix, caption, x0, x1)
LINE_COLUMNS = [
    ("date_of_service", "24A. DATE", 30, 98),
    ("place_of_service", "24B. POS", 100, 128),
    ("procedure_code", "24D. CPT/HCPCS", 130, 184),
    ("modifiers", "MODIFIERS", 186, 262),
    ("diagnosis_pointers", "24E. PTR", 264, 310),
    ("charge_cents", "24F. CHARGES", 312, 392),
    ("units", "24G. UNITS", 394, 432),
    ("rendering_npi", "24J. RENDERING NPI", 434, 582),
]
LINES_TOP, LINE_HEIGHT = 386, 26
LINE_BOXES = [
    [
        _box(
            f"service_lines.{row}.{name}",
            caption,
            x0,
            LINES_TOP + row * LINE_HEIGHT,
            x1,
            LINES_TOP + row * LINE_HEIGHT + 20,
        )
        for name, caption, x0, x1 in LINE_COLUMNS
    ]
    for row in range(MAX_LINES_PER_FORM)
]
PROVIDER_BOXES = [
    _box("billing_tin", "25. FEDERAL TAX ID", 30, 560, 250, 580),
    _box("billing_npi", "33a. BILLING PROVIDER NPI", 255, 560, 582, 580),
]
# Page 2: attachments (clinical notes and the primary payer's payments for coordination of benefits)
NOTES_BOX = _box("clinical_notes", "ATTACHMENT A: CLINICAL NOTES", 30, 70, 582, 560, page=1)
PRIMARY_PAID_BOXES = [
    _box(
        f"other_coverage.primary_paid.{row}",
        "ATTACHMENT B: PRIMARY PAYER PAID (LINE / AMOUNT)",
        30,
        600 + row * 22,
        300,
        618 + row * 22,
        page=1,
    )
    for row in range(MAX_LINES_PER_FORM)
]

SIMPLE_BOXES = HEADER_BOXES + PATIENT_BOXES + PROVIDER_BOXES
ALL_PAGE_ONE_BOXES = SIMPLE_BOXES + DIAGNOSIS_BOXES + [box for row in LINE_BOXES for box in row]
DATE_FORMAT = "%m/%d/%Y"
