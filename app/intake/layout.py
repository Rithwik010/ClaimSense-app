"""Form layout for ClaimSense's synthetic CMS-1500-style claim forms (INSTRUCTIONS.md §8.2, §9.4).

Every box is defined once here and used by both the renderer (`training/generate/forms.py`) and the
parsers in `app/intake/`. Coordinates are PDF points on a US Letter page (612 x 792), measured from
the top-left corner, as PyMuPDF reports them.

Limitation: these coordinates describe our own generated layout only. They are NOT valid for the
official printed CMS-1500 (02/12) form.

Long notes (D-DOC-3): the notes box of page 2 holds about 44 lines; notes that need more go on to
further attachment pages, each with the same box under the title "ATTACHMENTS FOR CLAIM <id>
(CONTINUED, PAGE n OF m)", n and m counting the claim's pages. A claim has at most
`MAX_FORM_PAGES` pages. Limitation: continuation pages are found by our own "PAGE n OF m" title,
which real attachments will not always have.
"""

import re
from dataclasses import dataclass, replace

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

# Long notes go on to further attachment pages (D-DOC-3): the prompt of a 5-page claim still fits
# the model's context with its answer (8,192 tokens; scripts/verify/v3_prompt_tokens.py)
FORM_PAGES = 2  # page 1: the claim; page 2: its attachments
MAX_FORM_PAGES = 5
TITLE_BAND = (25.0, 15.0, 590.0, 66.0)  # points: the band holding a page's printed title
# "(CONTINUED, PAGE 3 OF 4)", allowing for an OCR reading 0 for O, or dropping or adding punctuation
# ("PAGE 3. OF 3": a rendered v3 claim's scan, 25 Oct)
CONTINUED = re.compile(r"CONTINUED\W*PAGE\W*([0-9]+)\W*[O0]F\W*([0-9]+)")


class PageOrderError(ValueError):
    """The pages are not the claim form's pages in order (D-DOC-2, D-DOC-3)."""


def notes_box(page: int) -> Box:
    """The notes box on attachment page `page` (index 1 is page 2; index 2 on, continuation)."""
    return replace(NOTES_BOX, page=page)


def continuation(title: str) -> tuple[int, int] | None:
    """(n, m) of a continuation page's title "... (CONTINUED, PAGE n OF m)", else None."""
    found = CONTINUED.search(title.upper())
    return (int(found.group(1)), int(found.group(2))) if found else None


def check_continuation(titles: list[str]) -> None:
    """Pages 3 on of a claim are its notes' continuation pages, in order: page n of m at position
    n, m the number of pages, at most `MAX_FORM_PAGES`; and page 2 is never a continuation page
    (a claim of two pages is otherwise checked by D-DOC-2's own rules)."""
    pages = len(titles)
    rule = (
        f"a claim form has {FORM_PAGES} pages, or up to {MAX_FORM_PAGES} when its notes go on to"
        ' further attachment pages titled "CONTINUED, PAGE n OF m"'
    )
    if pages >= FORM_PAGES and continuation(titles[1]) is not None:
        raise PageOrderError(f"{rule}: page 2, the first attachments page, is missing")
    if pages <= FORM_PAGES:
        return
    if pages > MAX_FORM_PAGES:
        raise PageOrderError(f"{rule}: these hold {pages} pages")
    for index in range(FORM_PAGES, pages):
        found = continuation(titles[index])
        if found is None:
            raise PageOrderError(f"{rule}: page {index + 1} is not a continuation page")
        if found != (index + 1, pages):
            raise PageOrderError(
                f"{rule}: page {index + 1} is titled page {found[0]} of {found[1]}, so a page is"
                " missing, repeated or out of order"
            )


SIMPLE_BOXES = HEADER_BOXES + PATIENT_BOXES + PROVIDER_BOXES
ALL_PAGE_ONE_BOXES = SIMPLE_BOXES + DIAGNOSIS_BOXES + [box for row in LINE_BOXES for box in row]
DATE_FORMAT = "%m/%d/%Y"

# --- Printed labels: what every copy of the form prints, whatever the claim -----------------------
# The intake checks that these sit where the layout puts them before it reads any box
# (`form_check.py`), so a file that is not our form, or our form turned, tilted or shifted, is
# refused instead of read wrong.


@dataclass(frozen=True)
class Title:
    """A page's printed title: bold text at (x, baseline). `words` is the fixed part the checks
    look for (page 2 adds the claim control number after it)."""

    words: str
    text: str
    x: float
    baseline: float
    size: float
    font: str = "Helvetica-Bold"


PAGE_TITLES = (
    Title(
        "HEALTH INSURANCE CLAIM FORM",
        "HEALTH INSURANCE CLAIM FORM (ClaimSense synthetic layout, not the CMS-1500)",
        30,
        40,
        12,
    ),
    Title("ATTACHMENTS FOR CLAIM", "ATTACHMENTS FOR CLAIM", 30, 45, 11),
)
# A box's caption is printed in this font just above the box: at (x0 + CAPTION_INDENT,
# y0 - CAPTION_RISE), the baseline.
CAPTION_FONT, CAPTION_SIZE = "Helvetica", 5.5
CAPTION_INDENT, CAPTION_RISE = 1.0, 2.0
# The captions checked on each page: spread over the page (top, middle and bottom; left and right)
# and long enough to read reliably. Page 2 prints only the clinical notes' caption every time.
CHECKED_CAPTIONS = (
    (
        "member_id",
        "patient.last_name",
        "subscriber_is_patient",
        "prior_auth_number",
        "service_lines.0.date_of_service",
        "service_lines.0.rendering_npi",
        "billing_tin",
        "billing_npi",
    ),
    ("clinical_notes",),
)
