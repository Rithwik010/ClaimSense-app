"""Is this page our form, the right way up and in place? (B5) Before any box is read, the form's
fixed printed labels (`layout.py`: each page's title and several box captions, spread over the
page) must sit where the layout prints them. A file that is not our form, or our form tilted or
shifted beyond what the reader handles, is refused with a plain message that names the page and
what was expected, instead of being read into confidently wrong values. A scan turned a quarter,
half or three quarters around is turned upright first (`ocr.py`).

This module holds what both readers share: the labels and where they belong, the tolerances, the
verdict and its messages, and the check of a page's text layer (digital PDF). The scanned page is
measured in `ocr.py` (Tesseract and the page image).

Tolerances: the box reader reads well up to about 4 points off sideways and 2 points off downward
(measured on the development scans, `scripts/verify/foreign_documents.py`), so a label more than
3.5 points off sideways or 2.5 points off up or down is not where the form prints it.
"""

import difflib
import re
from dataclasses import dataclass

import pymupdf

from app.intake.digital_pdf import Word
from app.intake.layout import (
    ALL_PAGE_ONE_BOXES,
    CAPTION_FONT,
    CAPTION_INDENT,
    CAPTION_RISE,
    CAPTION_SIZE,
    CHECKED_CAPTIONS,
    NOTES_BOX,
    PAGE_TITLES,
    TITLE_BAND,
    Title,
)

SKEW_LIMIT = 2.0  # degrees: the scanned-page reader straightens up to this (ocr.SKEW_RANGE)
TITLE_MATCH = 0.8  # a title band's text counts as a title when it holds the words this closely
LABEL_MATCH = 0.6  # a caption read counts when it is this similar to the printed caption
TOLERANCE_X, TOLERANCE_Y = 3.5, 2.5  # points a label may be off and still be where expected
# Labels that must be where the form prints them: page 1, the title and 8 captions; page 2, the
# title and the clinical notes' caption (page 2 prints only that caption on every claim).
REQUIRED = (6, 1)
MARGIN, ABOVE, BELOW = 6.0, 4.0, 2.6  # points searched around a label (below: from its baseline)
CAP_HEIGHT = 0.718  # Helvetica's capital height, per point of size
WORD_CENTRE = 0.385  # a text-layer word box's centre above the baseline, per point of size
FONT_NAMES = {"Helvetica": "helv", "Helvetica-Bold": "hebo"}  # PyMuPDF's names for the fonts


class NotOurForm(ValueError):
    """The page is not our form's page, or not where the layout puts it; the message says which
    page and what was expected."""


@dataclass(frozen=True)
class Label:
    """A fixed printed label and where the form prints it (PDF points from the top left)."""

    text: str
    x: float  # left end
    baseline: float
    size: float
    font: str
    read: bool  # its text is read where it is; a title is read by its band instead

    @property
    def width(self) -> float:
        font = FONT_NAMES[self.font]
        return pymupdf.get_text_length(self.text, fontname=font, fontsize=self.size)

    @property
    def cap_top(self) -> float:
        return self.baseline - CAP_HEIGHT * self.size

    @property
    def search(self) -> tuple[float, float, float, float]:
        """The area searched for the label: its place with a margin on every side."""
        return (
            self.x - MARGIN,
            self.cap_top - ABOVE,
            self.x + self.width + MARGIN,
            self.baseline + BELOW,
        )


def _title_label(title: Title) -> Label:
    return Label(title.words, title.x, title.baseline, title.size, title.font, read=False)


BOXES = {box.field: box for box in [*ALL_PAGE_ONE_BOXES, NOTES_BOX]}


def page_labels(index: int) -> list[Label]:
    """The labels checked on page `index` (0: the claim, 1: its attachments): the title, then the
    checked captions, each just above its box."""
    captions = [
        Label(
            BOXES[field].label,
            BOXES[field].x0 + CAPTION_INDENT,
            BOXES[field].y0 - CAPTION_RISE,
            CAPTION_SIZE,
            CAPTION_FONT,
            read=True,
        )
        for field in CHECKED_CAPTIONS[index]
    ]
    return [_title_label(PAGE_TITLES[index]), *captions]


@dataclass(frozen=True)
class Seen:
    """What was found where a label belongs: how close the text read is to the label (None: not
    read there), and how far (points) the label's ink or words are from its place (None: no ink)."""

    label: Label
    similarity: float | None
    dx: float | None
    dy: float | None

    @property
    def in_place(self) -> bool:
        if self.dx is None or self.dy is None:
            return False
        if self.similarity is not None and self.similarity < LABEL_MATCH:
            return False
        return abs(self.dx) <= TOLERANCE_X and abs(self.dy) <= TOLERANCE_Y


def _letters(text: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", text.upper())


def similarity(read: str, printed: str) -> float:
    """How close a text read is to a printed label (letters and digits only, 0 to 1)."""
    return difflib.SequenceMatcher(None, _letters(read), _letters(printed)).ratio()


def holds(text: str, words: str) -> float:
    """How closely `text` holds `words` somewhere (1.0: exactly; OCR slips lower it)."""
    found, wanted = _letters(text), _letters(words)
    if not found or not wanted:
        return 0.0
    if wanted in found:
        return 1.0
    starts = range(max(1, len(found) - len(wanted) + 1))
    return max(similarity(found[i : i + len(wanted)], wanted) for i in starts)


def form_page_of(title: str) -> int | None:
    """The page of our form whose title the text of a title band holds (0 or 1), or None."""
    scores = [holds(title, page.words) for page in PAGE_TITLES]
    best = max(range(len(scores)), key=lambda i: scores[i])
    return best if scores[best] >= TITLE_MATCH else None


# --- A page with a text layer (digital PDF) --------------------------------------------------


def text_label(words: list[Word], label: Label) -> Seen:
    """The words of a text layer in a label's search area, compared with the label."""
    x0, y0, x1, y1 = label.search
    inside = [
        w
        for w in words
        if x0 <= (w[0] + w[2]) / 2 <= x1 and y0 <= (w[1] + w[3]) / 2 <= y1 and w[4].strip()
    ]
    if not inside:
        return Seen(label, 0.0, None, None)
    inside.sort(key=lambda w: w[0])
    read = " ".join(w[4] for w in inside)
    dx = min(w[0] for w in inside) - label.x
    centre = sum((w[1] + w[3]) / 2 for w in inside) / len(inside)
    dy = centre - (label.baseline - WORD_CENTRE * label.size)
    return Seen(label, similarity(read, label.text), round(dx, 2), round(dy, 2))


def check_text_page(words: list[Word], index: int, where: str) -> None:
    """Refuse (NotOurForm) a text-layer page whose labels are not where page `index` of our form
    prints them."""
    found = form_page_of(band_text(words))
    if found is not None and found != index:
        raise NotOurForm(wrong_page(where, found, index))
    seen = [text_label(words, label) for label in page_labels(index)]
    problem = verdict(seen, index, where, digital=True)
    if problem:
        raise NotOurForm(problem)


def band_text(words: list[Word]) -> str:
    """The text of a text-layer page's title band, upper case."""
    _, top, _, bottom = TITLE_BAND
    return " ".join(w[4] for w in words if top <= w[1] and w[3] <= bottom).upper()


# --- Verdict and messages --------------------------------------------------------------------


def verdict(seen: list[Seen], index: int, where: str, digital: bool = False) -> str | None:
    """None when enough labels are in place for page `index`; otherwise the refusal message."""
    found = sum(s.in_place for s in seen)
    if found >= REQUIRED[index]:
        return None
    return misplaced(where, index, found, len(seen), digital)


def _examples(index: int) -> str:
    labels = page_labels(index)
    captions = [label.text for label in labels if label.read]
    chosen = [captions[1], captions[-2]] if len(captions) > 2 else captions
    return " and ".join(f'"{text}"' for text in chosen)


def not_our_form(where: str, index: int) -> str:
    title = PAGE_TITLES[index].words
    return (
        f"{where} is not page {index + 1} of the ClaimSense claim form: the title "
        f'"{title}" that the form prints at the top of that page was not found, the right way '
        "up or turned. Upload the claim form's own PDF, or a scan or photo of the whole page."
    )


def wrong_page(where: str, found: int, index: int) -> str:
    if found == 1:
        return (
            f"{where} is page 2 of the claim form (its attachments): page 1, the claim, must come"
            " first"
        )
    return f"{where} is another page 1 of the claim form: page {index + 1} must be its attachments"


def tilted(where: str, degrees: float) -> str:
    return (
        f"{where} is tilted by about {abs(degrees):.0f} degrees, and a scan is straightened by at"
        f" most {SKEW_LIMIT:g} degrees: scan the page straight and upload it again"
    )


def also_tilted(degrees: float) -> str:
    return (
        f"The page also looks tilted by about {abs(degrees):.0f} degrees, and a scan is"
        f" straightened by at most {SKEW_LIMIT:g} degrees: scan it straight."
    )


def misplaced(where: str, index: int, found: int, total: int, digital: bool) -> str:
    expected = (
        f'the title "{PAGE_TITLES[index].words}" at the top of the page and box captions such as'
        f" {_examples(index)} just above their boxes"
    )
    if digital:
        return (
            f"{where} is not page {index + 1} of the ClaimSense claim form: its text"
            f" does not have the form's printed labels where the form prints them ({found} of"
            f" {total} found; expected {expected}). Only a PDF of the ClaimSense form can be read."
        )
    return (
        f"{where} does not line up with page {index + 1} of the ClaimSense claim form: only"
        f" {found} of the {total} printed labels checked are where the form prints them (expected"
        f" {expected}). The page may be another form, or cropped, scaled or shifted: upload a"
        " scan of the whole page at its full size."
    )
