"""Claim files (INSTRUCTIONS.md §8.2, P5.1): a JSON claim, a digital PDF of our form, or a scanned
form (an image-only PDF, or an image: PNG, JPEG or TIFF, one page per frame) becomes the claim
dictionary, each field's confidence and the source format.

- JSON: every field has confidence 1.0, so none is listed.
- Digital PDF: a PDF with text in the form's boxes; 1.0 for a field read that passes its format
  check, 0.0 for one that fails it.
- Scanned: OCR (`ocr.py`): lowest word confidence / 100, 0.0 when the format check fails.

Before any box is read, each page's printed labels must be where our form prints them
(`form_check.py`, B5): a PDF page by its text layer, a scanned page by OCR (turned upright first
when it was scanned on its side or upside down). Anything else is refused with a plain message
naming the page and what was expected, never read into confidently wrong values.

Long notes go on to continuation pages (pages 3 on, at most `MAX_FORM_PAGES` pages; D-DOC-3), in one
file or as further files; each is checked as page 2 is (it prints the same labels), their notes are
read after page 2's, in page order, and pages out of order, missing or repeated are refused. A
claim of one or two pages is read exactly as before.
"""

import io
import json
from dataclasses import dataclass, replace
from typing import Any

import pymupdf
from PIL import Image, ImageOps, UnidentifiedImageError

from app.domain.contracts import SourceFormat
from app.intake.digital_pdf import Word, box_values, page_words
from app.intake.documents import content_type
from app.intake.field_formats import format_ok
from app.intake.form_check import NotOurForm, band_text, check_text_page, form_page_of
from app.intake.form_codec import from_form_values
from app.intake.layout import (
    ALL_PAGE_ONE_BOXES,
    MAX_FORM_PAGES,
    NOTES_BOX,
    PageOrderError,
    check_continuation,
)
from app.intake.ocr import (
    FORM_BOXES,
    RENDER_DPI,
    FieldRead,
    joined_notes,
    page_title,
    parse_scan,
    read_page,
    turn_upright,
)

MAX_FILE_BYTES = 20 * 1024 * 1024
PAGE_ONE_FIELDS = {box.field for box in ALL_PAGE_ONE_BOXES}
NOTES = NOTES_BOX.field
FORM_PAGES = 2  # page 1: the claim; page 2: its attachments (layout.py); more: D-DOC-3
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
        pages = _pdf_words(data)
        if any(pages) and not all(pages):  # typed pages and scanned ones: page by page (D-DOC-3)
            return _read_pages(_file_pages(1, data))
        if pages[0]:  # a text layer on every page: a digital PDF of our form
            return _digital_pdf(pages)
    else:
        try:
            with Image.open(io.BytesIO(data)) as image:
                _check_pixels(image, "the image")
                image.verify()
        except (UnidentifiedImageError, OSError) as exc:
            raise UnreadableFile("the file is not JSON, a PDF or an image") from exc
        except Image.DecompressionBombError as exc:
            raise UnreadableFile(f"the image {TOO_MANY_PIXELS}") from exc
    try:
        claim, confidences = parse_scan(data)
    except (NotOurForm, PageOrderError) as exc:  # B5; D-DOC-3
        raise UnreadableFile(str(exc)) from exc
    except Image.DecompressionBombError as exc:
        raise UnreadableFile(f"the image {TOO_MANY_PIXELS}") from exc
    return claim, confidences, SourceFormat.SCANNED


def _digital_pdf(pages: list[list[Word]]) -> tuple[dict[str, Any], dict[str, float], SourceFormat]:
    """A PDF with a text layer on every page: pages 1 and 2 read once their printed labels are
    found where our form prints them, then the notes of any continuation pages (D-DOC-3), each
    checked as page 2 is, after page 2's."""
    values: dict[str, str] = {}
    for index, words in enumerate(pages[:FORM_PAGES]):
        values |= _text_page_values(words, index, f"page {index + 1} of the PDF")
    try:
        check_continuation([band_text(words) for words in pages])
    except PageOrderError as exc:
        raise UnreadableFile(str(exc)) from exc
    more = [
        text
        for index, words in enumerate(pages[FORM_PAGES:], start=FORM_PAGES)
        if (text := _text_page_values(words, 1, f"page {index + 1} of the PDF").get(NOTES))
    ]
    if more:
        values[NOTES_BOX.field] = " ".join([values.get(NOTES_BOX.field, ""), *more]).strip()
    confidences = {f: 1.0 if format_ok(f, text) else 0.0 for f, text in values.items()}
    return from_form_values(values), confidences, SourceFormat.DIGITAL_PDF


MAX_PAGE_POINTS = 2000.0  # a PDF page wider or taller than this is not a claim form page
MAX_PIXELS = 50_000_000  # nor an image with more pixels (a letter page at 600 dpi has 34 million)
TOO_MANY_PIXELS = "has too many pixels to be a scan of a claim form page"


def _check_pixels(image: Image.Image, what: str) -> None:
    if image.width * image.height > MAX_PIXELS:
        raise UnreadableFile(f"{what} {TOO_MANY_PIXELS}")


def _open_pdf(data: bytes, what: str) -> pymupdf.Document:
    """The PDF, refused when it cannot be read, needs a password, has no pages or a page far
    larger than a claim form page."""
    try:
        doc = pymupdf.open(stream=data, filetype="pdf")
    except RuntimeError as exc:  # PyMuPDF: not a readable PDF
        raise UnreadableFile(f"{what} cannot be read: {exc}") from exc
    problem = None
    if doc.needs_pass:
        problem = f"{what} is protected by a password"
    elif doc.page_count == 0:
        problem = f"{what} has no pages"
    elif any(max(page.rect.width, page.rect.height) > MAX_PAGE_POINTS for page in doc):
        problem = f"{what} has a page far larger than a claim form page"
    if problem:
        doc.close()
        raise UnreadableFile(problem)
    return doc


def _pdf_words(data: bytes) -> list[list[Word]]:
    """The words of each page's text layer (an empty list for a page without one)."""
    with _open_pdf(data, "the PDF") as doc:
        try:
            return [page_words(page) for page in doc]
        except (RuntimeError, ValueError) as exc:  # PyMuPDF: a page that cannot be read
            raise UnreadableFile(f"the PDF cannot be read: {exc}") from exc


def _text_page_values(words: list[Word], index: int, where: str) -> dict[str, str]:
    """The boxes of page `index` read from its text layer, once its printed labels are found
    where our form prints them (UnreadableFile otherwise); a page without text gives nothing."""
    if not words:
        return {}
    try:
        check_text_page(words, index, where)
    except NotOurForm as exc:
        raise UnreadableFile(str(exc)) from exc
    return box_values(words, [box for box in FORM_BOXES if box.page == index])


@dataclass(frozen=True)
class Page:
    """One page of a claim in several files: its text layer (a PDF page with one), or its image
    (an image file, or a PDF page without text, rendered for OCR); where it is, for messages
    ("file 2", or "page 3 of file 1" in a file of several pages); and, once titled, its printed
    title and the page of our form that title names (0 or 1; None when it names neither)."""

    words: list[Word] | None
    image: Image.Image | None
    where: str = ""
    form_page: int | None = None
    title: str = ""


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
        with _open_pdf(data, f"file {number}: the PDF") as doc:
            try:
                for page in doc:
                    words = page_words(page)
                    if words:
                        pages.append(Page(words, None))
                        continue
                    pix = page.get_pixmap(dpi=RENDER_DPI, colorspace=pymupdf.csGRAY)
                    image = Image.frombytes("L", (pix.width, pix.height), pix.samples)
                    pages.append(Page(None, image))
            except (RuntimeError, ValueError) as exc:  # PyMuPDF: a page that cannot be read
                raise UnreadableFile(f"file {number}: the PDF cannot be read: {exc}") from exc
        if len(pages) == 1:
            return [replace(pages[0], where=f"file {number}")]
        return [replace(p, where=f"page {i} of file {number}") for i, p in enumerate(pages, 1)]
    try:
        image = Image.open(io.BytesIO(data))
        _check_pixels(image, f"file {number}: the image")
        image.load()
    except (UnidentifiedImageError, OSError) as exc:
        raise UnreadableFile(f"file {number}: the image cannot be read") from exc
    except Image.DecompressionBombError as exc:
        raise UnreadableFile(f"file {number}: {TOO_MANY_PIXELS}") from exc
    return [Page(None, ImageOps.exif_transpose(image).convert("L"), f"file {number}")]


def _titled(page: Page) -> Page:
    """The page with its printed title and the form page that title names: from its text layer, or
    by OCR of its title band, turned upright when the title reads only that way (B5)."""
    if page.words is not None:
        title = band_text(page.words)
        return replace(page, form_page=form_page_of(title), title=title)
    if page.image is None:
        return page
    upright, found = turn_upright(page.image)
    return replace(page, image=upright, form_page=found, title=page_title(upright))


def _check_order(pages: list[Page]) -> None:
    """Page 1 (the claim) first and page 2 (its attachments) second, told apart by the title each
    page prints, so the attachments page is never read as a claim; pages 3 on, the notes'
    continuation pages in order (D-DOC-3)."""
    try:
        check_continuation([page.title for page in pages])
    except PageOrderError as exc:
        raise UnreadableFile(str(exc)) from exc
    if pages[0].form_page == 1:
        raise UnreadableFile(
            "the first file is page 2 of the claim form (its attachments): page 1, the claim,"
            " must come first"
        )
    if len(pages) > 1 and pages[1].form_page == 0:
        raise UnreadableFile(
            "the second file is another page 1: it must be page 2 of the same claim form (its"
            " attachments)"
        )


def _read(page: Page, index: int) -> tuple[dict[str, str], dict[str, float], bool]:
    """(values, confidences, read from a text layer) of page `index` of the form, read as the
    single-file readers read it: every value and 1.0 or 0.0 from a text layer; from OCR, only
    the values that pass their format check, with the OCR confidence. Its printed labels are
    checked first (UnreadableFile naming the file when they are not where our form prints them)."""
    where = page.where
    if page.words is not None:
        values = _text_page_values(page.words, index, where)
        return values, {f: 1.0 if format_ok(f, text) else 0.0 for f, text in values.items()}, True
    try:
        reads = read_page(page.image, index, where) if page.image is not None else {}
    except NotOurForm as exc:
        raise UnreadableFile(str(exc)) from exc
    values = {field: read.text for field, read in reads.items() if format_ok(field, read.text)}
    return values, {field: read.confidence for field, read in reads.items()}, False


def _continued(page: Page) -> FieldRead | None:
    """The notes of a continuation page (D-DOC-3), from its text layer or by OCR, once its printed
    labels are found where page 2's are (it prints the same)."""
    found, read_with, _ = _read(page, 1)
    text = found.get(NOTES_BOX.field)
    return FieldRead(text, read_with[NOTES_BOX.field]) if text else None


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
        if len(pages) > MAX_FORM_PAGES:
            raise UnreadableFile(
                f"a claim form has {FORM_PAGES} pages, or up to {MAX_FORM_PAGES} when its notes go"
                " on to further attachment pages, and these files hold more: send page 1 (the"
                " claim), page 2 (its attachments) and any continuation pages, in order"
            )
    return _read_pages(pages)


def _read_pages(pages: list[Page]) -> tuple[dict[str, Any], dict[str, float], SourceFormat]:
    """A claim from its form's pages in order, each read by its text layer or by OCR: the pages
    of several files (D-DOC-2), or of one PDF with typed pages and scanned ones (D-DOC-3)."""
    if len(pages) > MAX_FORM_PAGES:
        raise UnreadableFile(
            f"a claim form has {FORM_PAGES} pages, or up to {MAX_FORM_PAGES} when its notes go on"
            f" to further attachment pages, and this one holds {len(pages)}"
        )
    pages = [_titled(page) for page in pages]
    _check_order(pages)
    values: dict[str, str] = {}
    confidences: dict[str, float] = {}
    digital = True
    continued: list[FieldRead] = []
    for index, page in enumerate(pages):
        if index >= FORM_PAGES:  # a continuation page: its notes (D-DOC-3)
            if (read := _continued(page)) is not None:
                continued.append(read)
            digital = digital and page.words is not None
            continue
        found, read_with, from_text = _read(page, index)
        if index == 0 and not PAGE_ONE_FIELDS & set(read_with):
            raise UnreadableFile(
                "no claim field was found on the first file's page: the first file must be page 1"
                " of the claim form"
            )
        values |= found
        confidences |= read_with
        digital = digital and from_text
    if continued:
        first = values.get(NOTES_BOX.field)
        page_two = FieldRead(first, confidences.get(NOTES_BOX.field, 1.0)) if first else None
        notes = joined_notes(page_two, continued)
        if notes is not None:
            values[NOTES_BOX.field] = notes.text
            confidences[NOTES_BOX.field] = notes.confidence
    return (
        from_form_values(values),
        confidences,
        SourceFormat.DIGITAL_PDF if digital else SourceFormat.SCANNED,
    )
