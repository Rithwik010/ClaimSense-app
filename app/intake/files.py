"""Claim files (INSTRUCTIONS.md §8.2, P5.1): a JSON claim, a digital PDF of our form, or a scanned
form (an image-only PDF, or an image: PNG, JPEG or TIFF, one page per frame) becomes the claim
dictionary, each field's confidence and the source format.

- JSON: every field has confidence 1.0, so none is listed.
- Digital PDF: a PDF with text in the form's boxes; 1.0 for a field read that passes its format
  check, 0.0 for one that fails it.
- Scanned: OCR (`ocr.py`): lowest word confidence / 100, 0.0 when the format check fails.
"""

import io
import json
from typing import Any

from PIL import Image, UnidentifiedImageError

from app.domain.contracts import SourceFormat
from app.intake.digital_pdf import read_form_values
from app.intake.field_formats import format_ok
from app.intake.form_codec import from_form_values
from app.intake.layout import ALL_PAGE_ONE_BOXES
from app.intake.ocr import parse_scan

MAX_FILE_BYTES = 20 * 1024 * 1024
PAGE_ONE_FIELDS = {box.field for box in ALL_PAGE_ONE_BOXES}


class UnreadableFile(ValueError):
    """The file is not a claim this intake can read."""


def read_claim_file(data: bytes) -> tuple[dict[str, Any], dict[str, float], SourceFormat]:
    """(claim dictionary, field confidences, source format) of an uploaded claim file."""
    if not data:
        raise UnreadableFile("the file is empty")
    if len(data) > MAX_FILE_BYTES:
        raise UnreadableFile(f"the file is larger than {MAX_FILE_BYTES // (1024 * 1024)} MB")
    if data.lstrip()[:1] == b"{":
        try:
            claim = json.loads(data)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise UnreadableFile(f"the JSON claim cannot be read: {exc}") from exc
        return claim, {}, SourceFormat.JSON
    if data[:5] == b"%PDF-":
        try:
            values = read_form_values(data)
        except RuntimeError as exc:  # PyMuPDF: not a readable PDF
            raise UnreadableFile(f"the PDF cannot be read: {exc}") from exc
        if PAGE_ONE_FIELDS & set(values):
            confidences = {f: 1.0 if format_ok(f, text) else 0.0 for f, text in values.items()}
            return from_form_values(values), confidences, SourceFormat.DIGITAL_PDF
    else:
        try:
            Image.open(io.BytesIO(data)).verify()
        except (UnidentifiedImageError, OSError) as exc:
            raise UnreadableFile("the file is not JSON, a PDF or an image") from exc
    claim, confidences = parse_scan(data)
    return claim, confidences, SourceFormat.SCANNED
