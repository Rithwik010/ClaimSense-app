"""Form renderer (P3.4, INSTRUCTIONS.md §9.4): a digital PDF and a scanned-style image of one claim,
both from the single layout in `app/intake/layout.py`.

- Digital PDF: typed values; parses back to the original claim exactly
  (`app/intake/digital_pdf.py`).
- `continued=True` (long notes, the v3 renders of 25 Oct): notes that overflow page 2's notes box
  go on as many further attachment pages as they need, each with the same box under the title
  "ATTACHMENTS FOR CLAIM <id> (CONTINUED, PAGE n OF m)", counting the claim's pages. Without it
  the form keeps its two pages
  (the notes box holds `notes_capacity()` lines) and the output is unchanged.
- Scanned: the same form with hand-filled-looking values (per-character jitter in built-in fonts),
  rasterized and degraded with skew, blur, speckle and JPEG compression. Optional value noise
  (a typo or a missing box) is applied before rendering and recorded in a noise log, so the expected
  intake result is known.
"""

import io
import random
from dataclasses import dataclass, field
from typing import Any

import pymupdf
from PIL import Image, ImageEnhance, ImageFilter
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import simpleSplit
from reportlab.pdfgen import canvas

from app.intake.layout import (
    ALL_PAGE_ONE_BOXES,
    CAPTION_FONT,
    CAPTION_INDENT,
    CAPTION_RISE,
    CAPTION_SIZE,
    LINE_BOXES,
    NOTES_BOX,
    PAGE_HEIGHT,
    PAGE_TITLES,
    PRIMARY_PAID_BOXES,
    Box,
)

TYPED_FONT, TYPED_SIZE = "Helvetica", 9
NOTES_FONT, NOTES_SIZE, NOTES_LEADING = "Helvetica", 8.5, 11
HAND_FONTS = ("Courier-Oblique", "Helvetica-Oblique", "Times-Italic")
SCAN_DPI = 150
HAND_MARGIN = 2.0  # points kept clear of a box's right border by hand-filled text

# Value noise for scanned copies: fields a clerk might leave blank or mistype.
MISSING_FIELDS = (
    "member_id",
    "patient.date_of_birth",
    "service_lines.0.procedure_code",
    "billing_npi",
)
TYPO_FIELDS = ("billing_npi", "service_lines.0.rendering_npi", "service_lines.0.date_of_service")


@dataclass
class ScanResult:
    pages: list[Image.Image]
    values: dict[str, str]  # what was written on the scanned form
    noise: dict[str, Any] = field(default_factory=dict)


def _y(top: float) -> float:
    return PAGE_HEIGHT - top


def _draw_box(pdf: canvas.Canvas, box: Box, label: str | None = None) -> None:
    pdf.setLineWidth(0.5)
    pdf.rect(box.x0, _y(box.y1), box.x1 - box.x0, box.y1 - box.y0)
    pdf.setFont(CAPTION_FONT, CAPTION_SIZE)
    pdf.drawString(
        box.x0 + CAPTION_INDENT, _y(box.y0) + CAPTION_RISE, box.label if label is None else label
    )


def _typed(pdf: canvas.Canvas, box: Box, text: str) -> None:
    pdf.setFont(TYPED_FONT, TYPED_SIZE)
    pdf.drawString(box.x0 + 3, _y(box.y1) + 6, text)


def _hand(pdf: canvas.Canvas, box: Box, text: str, rng: random.Random) -> None:
    """Hand-filled-looking text: per-character size, baseline and slant jitter. Text that would
    run past the box is written smaller, so it stays inside its box as a person writes in a small
    box (D-OCR-1); the random draws are the same either way."""
    x = box.x0 + 3 + rng.uniform(0, 3)
    base = _y(box.y1) + 5 + rng.uniform(-1, 1.5)
    font = rng.choice(HAND_FONTS)
    chars = []
    for char in text:
        size = rng.uniform(9.5, 10.8)
        rise = rng.uniform(-0.8, 0.8)
        angle = rng.uniform(-4, 4)
        gap = rng.uniform(0.2, 1.0)
        chars.append((char, size, rise, angle, pdf.stringWidth(char, font, size) + gap))
    room = box.x1 - HAND_MARGIN - x
    fit = min(1.0, room / sum(advance for *_, advance in chars)) if chars else 1.0
    for char, size, rise, angle, advance in chars:
        pdf.saveState()
        pdf.translate(x, base + rise)
        pdf.rotate(angle)
        pdf.setFont(font, size * fit)
        pdf.drawString(0, 0, char)
        pdf.restoreState()
        x += advance * fit


def notes_capacity() -> int:
    """Lines of notes one notes box holds."""
    return int((NOTES_BOX.y1 - NOTES_BOX.y0 - 14) // NOTES_LEADING) + 1


def notes_lines(notes: str) -> list[str]:
    return simpleSplit(notes, NOTES_FONT, NOTES_SIZE, NOTES_BOX.x1 - NOTES_BOX.x0 - 8)


def _notes_box(pdf: canvas.Canvas, lines: list[str]) -> None:
    _draw_box(pdf, NOTES_BOX)
    y = _y(NOTES_BOX.y0) - 14
    pdf.setFont(NOTES_FONT, NOTES_SIZE)
    for text_line in lines:
        pdf.drawString(NOTES_BOX.x0 + 4, y, text_line)
        y -= NOTES_LEADING


def render_pdf(
    values: dict[str, str],
    style: str = "typed",
    rng: random.Random | None = None,
    continued: bool = False,
) -> bytes:
    """Render the form: page 1 the claim, page 2 its attachments (more pages for long notes with
    `continued`). `style` is "typed" (digital) or "hand" (for scanned copies)."""
    rng = rng or random.Random(0)
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter, invariant=1)
    pdf.setTitle("ClaimSense synthetic claim form")
    first, second = PAGE_TITLES
    pdf.setFont(first.font, first.size)
    pdf.drawString(first.x, _y(first.baseline), first.text)
    pdf.setFont("Helvetica", 6.5)
    pdf.drawString(30, _y(372), "24. SERVICE LINES")
    for box in ALL_PAGE_ONE_BOXES:
        is_line = any(box in row for row in LINE_BOXES[1:])
        _draw_box(pdf, box, None if not is_line else "")
        text = values.get(box.field)
        if text:
            (_typed(pdf, box, text) if style == "typed" else _hand(pdf, box, text, rng))
    pdf.showPage()

    claim_id = values.get("claim_id", "")
    lines = notes_lines(values.get("clinical_notes", ""))
    size = notes_capacity()
    chunks = [lines[i : i + size] for i in range(0, len(lines), size)] if continued else [lines]
    chunks = chunks or [[]]
    pdf.setFont(second.font, second.size)
    pdf.drawString(second.x, _y(second.baseline), f"{second.text} {claim_id}")
    _notes_box(pdf, chunks[0])
    for row, box in enumerate(PRIMARY_PAID_BOXES):  # one caption above the first row only
        text = values.get(box.field)
        if text:
            _draw_box(pdf, box, None if row == 0 else "")
            _typed(pdf, box, text)
    pdf.showPage()
    for number, chunk in enumerate(chunks[1:], start=2):
        pdf.setFont(second.font, second.size)
        pdf.drawString(
            second.x,
            _y(second.baseline),
            f"{second.text} {claim_id} (CONTINUED, PAGE {number + 1} OF {len(chunks) + 1})",
        )
        _notes_box(pdf, chunk)
        pdf.showPage()
    pdf.save()
    return buffer.getvalue()


def _apply_value_noise(
    values: dict[str, str], rng: random.Random, rate: float
) -> tuple[dict[str, str], dict]:
    noisy = dict(values)
    roll = rng.random()
    if roll < rate / 2:
        field = rng.choice([f for f in MISSING_FIELDS if f in noisy])
        original = noisy.pop(field)
        return noisy, {"kind": "missing_box", "field": field, "original": original, "written": None}
    if roll < rate:
        field = rng.choice([f for f in TYPO_FIELDS if f in noisy])
        original = noisy[field]
        if field.endswith("date_of_service"):
            written = "13" + original[2:]  # month 13: fails the date format check
        else:
            digits = list(original)
            position = rng.randrange(len(digits))
            digits[position] = str((int(digits[position]) + rng.randint(1, 9)) % 10)
            written = "".join(digits)  # a changed NPI digit fails the check digit
        noisy[field] = written
        return noisy, {"kind": "typo", "field": field, "original": original, "written": written}
    return noisy, {}


def render_scan(
    values: dict[str, str],
    rng: random.Random,
    value_noise_rate: float = 0.2,
    continued: bool = False,
) -> ScanResult:
    """Scanned-style page images plus the values written on them and a noise log."""
    written, value_noise = _apply_value_noise(values, rng, value_noise_rate)
    pdf = render_pdf(written, style="hand", rng=rng, continued=continued)
    visual = {
        "skew_degrees": round(rng.uniform(-1.2, 1.2), 2),
        "blur_radius": round(rng.uniform(0.3, 0.9), 2),
        "speckle_per_page": rng.randint(200, 1500),
        "contrast": round(rng.uniform(0.8, 1.1), 2),
        "jpeg_quality": rng.randint(55, 80),
        "dpi": SCAN_DPI,
    }
    pages = []
    with pymupdf.open(stream=pdf, filetype="pdf") as doc:
        for page in doc:
            pix = page.get_pixmap(dpi=SCAN_DPI, colorspace=pymupdf.csGRAY)
            image = Image.frombytes("L", (pix.width, pix.height), pix.samples)
            image = image.rotate(
                visual["skew_degrees"], resample=Image.Resampling.BILINEAR, fillcolor=255
            )
            image = image.filter(ImageFilter.GaussianBlur(visual["blur_radius"]))
            image = ImageEnhance.Contrast(image).enhance(visual["contrast"])
            pixels = image.load()
            for _ in range(visual["speckle_per_page"]):
                px, py = rng.randrange(image.width), rng.randrange(image.height)
                pixels[px, py] = rng.choice((0, 90, 255))
            buffer = io.BytesIO()
            image.save(buffer, format="JPEG", quality=visual["jpeg_quality"])
            pages.append(Image.open(io.BytesIO(buffer.getvalue())))
    noise = {"visual": visual}
    if value_noise:
        noise["value"] = value_noise
    return ScanResult(pages=pages, values=written, noise=noise)
