"""Digital PDF intake (INSTRUCTIONS.md §8.2): PyMuPDF text extraction from the known box coordinates
of our synthetic form (`layout.py`). Confidence is 1.0 for a field that was read and passes its
format check, 0.0 otherwise. Long notes go on to continuation pages (pages 3 on, D-DOC-3): their
notes are read in page order after page 2's.
"""

from typing import Any

import pymupdf

from app.intake.form_codec import from_form_values
from app.intake.layout import (
    ALL_PAGE_ONE_BOXES,
    FORM_PAGES,
    NOTES_BOX,
    PRIMARY_PAID_BOXES,
    TITLE_BAND,
    Box,
    check_continuation,
    notes_box,
)

Word = tuple[float, float, float, float, str]


def _words_in(words: list[Word], box: Box) -> list[Word]:
    inside = []
    for x0, y0, x1, y1, text in words:
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        if box.x0 <= cx <= box.x1 and box.y0 <= cy <= box.y1:
            inside.append((x0, y0, x1, y1, text))
    return sorted(inside, key=lambda w: (round(w[1]), w[0]))


def page_words(page: pymupdf.Page) -> list[Word]:
    """The words of a PDF page's text layer, with their boxes."""
    return [(w[0], w[1], w[2], w[3], w[4]) for w in page.get_text("words")]


def box_values(words: list[Word], boxes: list[Box]) -> dict[str, str]:
    """Text found inside each of `boxes` on one page, keyed by field path (empty boxes omitted)."""
    values: dict[str, str] = {}
    for box in boxes:
        text = " ".join(w[4] for w in _words_in(words, box))
        if text:
            values[box.field] = text
    return values


def words_title(words: list[Word]) -> str:
    """A page's printed title from its text layer, upper case."""
    _, top, _, bottom = TITLE_BAND
    return " ".join(w[4] for w in words if top <= w[1] and w[3] <= bottom).upper()


def continued_notes(pages: list[list[Word]]) -> list[str]:
    """The notes of each continuation page (pages 3 on, D-DOC-3), in page order; the pages' titles
    are checked first (`check_continuation`, which raises `PageOrderError`). None for a PDF whose
    page 1 has no text layer: a scan, read by OCR (`ocr.py`), which checks its titles itself."""
    if not pages or not pages[0]:
        return []
    if len(pages) >= FORM_PAGES:
        check_continuation([words_title(words) for words in pages])
    if len(pages) <= FORM_PAGES:
        return []
    return [
        text
        for index, words in enumerate(pages)
        if index >= FORM_PAGES
        and (text := box_values(words, [notes_box(index)]).get(NOTES_BOX.field))
    ]


def read_form_values(pdf: bytes) -> dict[str, str]:
    """Text found inside every layout box, keyed by field path (empty boxes are omitted)."""
    with pymupdf.open(stream=pdf, filetype="pdf") as doc:
        pages = [page_words(page) for page in doc]
    boxes = ALL_PAGE_ONE_BOXES + [NOTES_BOX] + PRIMARY_PAID_BOXES
    values: dict[str, str] = {}
    for index, words in enumerate(pages):
        values |= box_values(words, [box for box in boxes if box.page == index])
    more = continued_notes(pages)
    if more:
        values[NOTES_BOX.field] = " ".join([values.get(NOTES_BOX.field, ""), *more]).strip()
    return values


def parse_digital_pdf(pdf: bytes) -> dict[str, Any]:
    """The claim dictionary read from a digital PDF (validate it with `IntakeClaim`)."""
    return from_form_values(read_form_values(pdf))
