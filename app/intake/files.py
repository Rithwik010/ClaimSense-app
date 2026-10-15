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
from dataclasses import dataclass
from typing import Any

import pymupdf
from PIL import Image, ImageOps, UnidentifiedImageError

from app.domain.contracts import SourceFormat
from app.intake.digital_pdf import Word, box_values, page_words, read_form_values
from app.intake.documents import content_type
from app.intake.field_formats import format_ok
from app.intake.form_codec import from_form_values
from app.intake.layout import ALL_PAGE_ONE_BOXES
from app.intake.ocr import FORM_BOXES, RENDER_DPI, TITLE_BAND, page_title, parse_scan, read_page

MAX_FILE_BYTES = 20 * 1024 * 1024
PAGE_ONE_FIELDS = {box.field for box in ALL_PAGE_ONE_BOXES}
FORM_PAGES = 2  # page 1: the claim; page 2: its attachments (layout.py)
PAGE_TYPES = ("application/pdf", "image/png", "image/jpeg")  # what a page file may be


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


@dataclass(frozen=True)
class Page:
    """One page of a claim in several files: its text layer (a PDF page with one), or its image
    (an image file, or a PDF page without text, rendered for OCR)."""

    words: list[Word] | None
    image: Image.Image | None


def _file_pages(number: int, data: bytes) -> list[Page]:
    if not data:
        raise UnreadableFile(f"file {number} is empty")
    if len(data) > MAX_FILE_BYTES:
        raise UnreadableFile(f"file {number} is larger than {MAX_FILE_BYTES // (1024 * 1024)} MB")
    kind = content_type(data)
    if kind == "application/json":
        raise UnreadableFile("a JSON claim is a whole claim: upload it on its own")
    if kind not in PAGE_TYPES:
        raise UnreadableFile(
            f"file {number} is not a PDF, PNG or JPEG (a TIFF scan can be uploaded on its own)"
        )
    if kind == "application/pdf":
        pages = []
        try:
            with pymupdf.open(stream=data, filetype="pdf") as doc:
                for page in doc:
                    words = page_words(page)
                    if words:
                        pages.append(Page(words, None))
                        continue
                    pix = page.get_pixmap(dpi=RENDER_DPI, colorspace=pymupdf.csGRAY)
                    image = Image.frombytes("L", (pix.width, pix.height), pix.samples)
                    pages.append(Page(None, image))
        except RuntimeError as exc:  # PyMuPDF: not a readable PDF
            raise UnreadableFile(f"file {number}: the PDF cannot be read: {exc}") from exc
        return pages
    try:
        image = Image.open(io.BytesIO(data))
        image.load()
    except (UnidentifiedImageError, OSError) as exc:
        raise UnreadableFile(f"file {number}: the image cannot be read") from exc
    return [Page(None, ImageOps.exif_transpose(image).convert("L"))]


def _title(page: Page) -> str:
    """The page's printed title, upper case: from its text layer, or by OCR."""
    if page.words is not None:
        _, top, _, bottom = TITLE_BAND
        return " ".join(w[4] for w in page.words if top <= w[1] and w[3] <= bottom).upper()
    return page_title(page.image) if page.image is not None else ""


def _check_order(pages: list[Page]) -> None:
    """Page 1 (the claim) first and page 2 (its attachments) second, told apart by the title each
    page prints, so the attachments page is never read as a claim."""
    titles = [_title(page) for page in pages]
    if "ATTACHMENTS" in titles[0]:
        raise UnreadableFile(
            "the first file is page 2 of the claim form (its attachments): page 1, the claim,"
            " must come first"
        )
    if len(titles) > 1 and "CLAIM FORM" in titles[1] and "ATTACHMENTS" not in titles[1]:
        raise UnreadableFile(
            "the second file is another page 1: it must be page 2 of the same claim form (its"
            " attachments)"
        )


def _read(page: Page, index: int) -> tuple[dict[str, str], dict[str, float], bool]:
    """(values, confidences, read from a text layer) of page `index` of the form, read as the
    single-file readers read it: every value and 1.0 or 0.0 from a text layer; from OCR, only
    the values that pass their format check, with the OCR confidence."""
    if page.words is not None:
        values = box_values(page.words, [box for box in FORM_BOXES if box.page == index])
        return values, {f: 1.0 if format_ok(f, text) else 0.0 for f, text in values.items()}, True
    reads = read_page(page.image, index) if page.image is not None else {}
    values = {field: read.text for field, read in reads.items() if format_ok(field, read.text)}
    return values, {field: read.confidence for field, read in reads.items()}, False


def read_claim_files(files: list[bytes]) -> tuple[dict[str, Any], dict[str, float], SourceFormat]:
    """(claim dictionary, field confidences, source format) of a claim uploaded as one file, or as
    its form's pages in several files (PDF, PNG or JPEG, in page order; D-DOC-2)."""
    if not files:
        raise UnreadableFile("no file was sent")
    if len(files) == 1:
        return read_claim_file(files[0])
    pages: list[Page] = []
    for number, data in enumerate(files, start=1):
        pages += _file_pages(number, data)
        if len(pages) > FORM_PAGES:
            raise UnreadableFile(
                f"a claim form has {FORM_PAGES} pages, and these files hold more: send page 1"
                " (the claim) and page 2 (its attachments)"
            )
    _check_order(pages)
    values: dict[str, str] = {}
    confidences: dict[str, float] = {}
    digital = True
    for index, page in enumerate(pages):
        found, read_with, from_text = _read(page, index)
        if index == 0 and not PAGE_ONE_FIELDS & set(read_with):
            raise UnreadableFile(
                "no claim field was found on the first file's page: the first file must be page 1"
                " of the claim form"
            )
        values |= found
        confidences |= read_with
        digital = digital and from_text
    return (
        from_form_values(values),
        confidences,
        SourceFormat.DIGITAL_PDF if digital else SourceFormat.SCANNED,
    )
