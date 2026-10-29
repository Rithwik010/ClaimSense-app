"""Scanned-form intake (INSTRUCTIONS.md §8.2, P5.1): OCR of our synthetic claim form.

Each page is rendered to a grayscale image (PyMuPDF for a PDF; an uploaded image is used as it is),
the page is straightened, each box of `layout.py` is cropped by its coordinates and read with
`pytesseract.image_to_data`, restricted to the characters the box may hold (`field_formats.py`).
A field's confidence is its lowest word confidence / 100, and 0 when the text fails the field's
format check. Blank boxes are left out, as in the digital-PDF reader, so the contract check reports
a missing required field (rule R01). A value that fails its format check is unreadable and is left
out too, keeping its confidence 0: the claim is then filed and the rules reject it (R01, or H5 on
a rule that uses the field) instead of the intake refusing it (§8.2: a low-confidence field does
not stop a claim by itself; D-OCR-1).

Before any box is read, the page's printed labels are checked (`form_check.py`, B5): the page is
turned upright by its title (a quarter, half or three quarters around), and refused when it is
tilted beyond what the straightening handles or when its title and box captions are not where the
form prints them.

Limitation: the coordinates fit our own synthetic layout only, not the official CMS-1500 form.
"""

import html
import io
import re
from dataclasses import dataclass
from typing import Any

import pymupdf
import pytesseract
from PIL import Image, ImageFilter, ImageOps

from app.intake.field_formats import ALPHABETS, canonical, format_ok, kind
from app.intake.form_check import (
    SKEW_LIMIT,
    Label,
    NotOurForm,
    Seen,
    also_tilted,
    form_page_of,
    not_our_form,
    page_labels,
    similarity,
    tilted,
    verdict,
    wrong_page,
)
from app.intake.form_codec import from_form_values
from app.intake.layout import (
    ALL_PAGE_ONE_BOXES,
    FORM_PAGES,
    NOTES_BOX,
    PAGE_WIDTH,
    PRIMARY_PAID_BOXES,
    TITLE_BAND,
    Box,
    check_continuation,
)

RENDER_DPI = 300  # a PDF page is rendered at this resolution for OCR
TARGET_SCALE = 300 / 72  # crops smaller than 300 dpi are enlarged to it before OCR
INSET = 1.5  # points kept clear of each box's printed border
SKEW_RANGE, SKEW_STEP = SKEW_LIMIT, 0.1  # degrees searched when straightening a page
TILT_RANGE = 15.0  # degrees searched to tell a page tilted beyond SKEW_RANGE (refused)
TURNS = (0, 90, 270, 180)  # degrees a page is turned (counter-clockwise) to find its title
INK_ABOVE_CAP = 0.5  # points the ink of a scanned label reaches above its capitals (blur)
EDGE_SHARE = 0.02  # a label's top: where its first 2% of ink is (a speck above it is ignored)
EDGE_COLUMN = 0.2  # a label's left end: its first column inked over 20% of the line's height
DARK_LEVEL = 200  # gray level below which a pixel counts as ink
RULE_SHARE = 0.6  # a row or column this dark is a printed rule, not writing
RULE_EDGE = 4.0  # points from a crop's side within which such a row or column is a border
BLANK_PIXELS = 60  # a box with fewer ink pixels (at 300 dpi, specks removed) is blank
SPECK, KEEP = 3, 7  # pixels: dark spots narrower than SPECK are specks; margin kept around ink
WORD_GAP, LINE_GAP, PAD = 9.0, 3.0, 2.0  # points: ink this close is one cluster; margin kept
# Characters allowed at each position of a code read by position (None: any of the field's).
# ICD-10: letter, digit, digit or A or B, point. Procedure (CPT or HCPCS): positions 2-4 digits.
POSITIONS = {
    "diagnosis": ("ABCDEFGHIJKLMNOPQRSTVWXYZ", "0123456789", "0123456789AB", "."),
    "procedure": (None, "0123456789", "0123456789", "0123456789", None),
}
# Page segmentation modes tried, in order, for boxes of one or a few characters (default: 7).
SHORT_MODES = {
    "sex": (10, 8, 7),
    "frequency": (10, 8, 7),
    "units": (7, 8, 10),
    "pointers": (7, 8, 10),
    "place": (7, 8, 10),
    "state": (7, 8, 10),
}


@dataclass(frozen=True)
class FieldRead:
    text: str
    confidence: float  # lowest word confidence / 100; 0 when the format check fails


def page_images(data: bytes) -> list[Image.Image]:
    """Grayscale page images of an uploaded PDF or image (every frame of a multi-page TIFF)."""
    if data[:5] == b"%PDF-":
        pages = []
        with pymupdf.open(stream=data, filetype="pdf") as doc:
            for page in doc:
                pix = page.get_pixmap(dpi=RENDER_DPI, colorspace=pymupdf.csGRAY)
                pages.append(Image.frombytes("L", (pix.width, pix.height), pix.samples))
        return pages
    image = Image.open(io.BytesIO(data))
    pages = []
    for index in range(getattr(image, "n_frames", 1)):
        image.seek(index)
        pages.append(ImageOps.exif_transpose(image).convert("L"))
    return pages


def _row_profile_score(dark: Image.Image, angle: float) -> float:
    rotated = dark.rotate(angle, resample=Image.Resampling.BILINEAR, fillcolor=0)
    rows = list(rotated.resize((1, rotated.height), Image.Resampling.BOX).getdata())
    mean = sum(rows) / len(rows)
    return sum((r - mean) ** 2 for r in rows)


def skew_angle(page: Image.Image) -> float:
    """The rotation (degrees) that makes the page's printed rules and text rows horizontal: the
    angle whose row profile of dark pixels varies most. A coarse search on a quarter-size page,
    then a fine one on a half-size page."""
    angle = 0.0
    for divisor, span, step in ((4, SKEW_RANGE, 0.2), (2, 0.2, 0.025)):
        small = page.resize((page.width // divisor, page.height // divisor))
        dark = small.filter(ImageFilter.MedianFilter(3)).point(lambda v: 255 if v < 200 else 0)
        steps = round(span / step)
        candidates = [angle + n * step for n in range(-steps, steps + 1)]
        angle = max(candidates, key=lambda a: _row_profile_score(dark, a))
    return round(angle, 3)


def straighten(page: Image.Image) -> Image.Image:
    angle = skew_angle(page)
    if angle == 0:
        return page
    return page.rotate(angle, resample=Image.Resampling.BICUBIC, fillcolor=255)


def _clear_rules(crop: Image.Image, edge: int) -> Image.Image:
    """Whiten rows and columns within `edge` pixels of the crop's sides that are mostly dark:
    remnants of the box's printed border (a dense line of writing further in is kept)."""
    dark = crop.point(lambda v: 255 if v < DARK_LEVEL else 0)
    rows = list(dark.resize((1, crop.height), Image.Resampling.BOX).getdata())
    cols = list(dark.resize((crop.width, 1), Image.Resampling.BOX).getdata())
    cleared = crop.copy()
    for y, level in enumerate(rows):
        if level > RULE_SHARE * 255 and min(y, crop.height - 1 - y) < edge:
            cleared.paste(255, (0, y, crop.width, y + 1))
    for x, level in enumerate(cols):
        if level > RULE_SHARE * 255 and min(x, crop.width - 1 - x) < edge:
            cleared.paste(255, (x, 0, x + 1, crop.height))
    return cleared


def _runs(levels: list[int], gap: int) -> list[tuple[int, int, int]]:
    """(start, end, ink) of the runs of inked positions, joining runs at most `gap` apart."""
    runs: list[list[int]] = []
    for position, level in enumerate(levels):
        if not level:
            continue
        if runs and position - runs[-1][1] <= gap:
            runs[-1][1] = position + 1
            runs[-1][2] += level
        else:
            runs.append([position, position + 1, level])
    return [(a, b, ink) for a, b, ink in runs]


def _crop(page: Image.Image, box: Box) -> Image.Image | None:
    """The writing in a box, ready for OCR; None when the box is blank. The box's inside is
    enlarged to 300 dpi, cleaned of speckle and border remnants, cut down to its ink (one line:
    the row band with the most ink), and everything but that ink (and a margin around it) is
    whitened."""
    scale = page.width / PAGE_WIDTH
    rect = (
        round((box.x0 + INSET) * scale),
        round((box.y0 + INSET) * scale),
        round((box.x1 - INSET) * scale),
        round((box.y1 - INSET) * scale),
    )
    crop = page.crop(rect)
    if scale < TARGET_SCALE:
        factor = TARGET_SCALE / scale
        crop = crop.resize(
            (round(crop.width * factor), round(crop.height * factor)), Image.Resampling.LANCZOS
        )
        scale = TARGET_SCALE
    crop = _clear_rules(crop.filter(ImageFilter.MedianFilter(3)), round(RULE_EDGE * scale))
    # Ink without specks: an opening removes dark spots narrower than the kernel.
    ink = crop.point(lambda v: 255 if v < DARK_LEVEL else 0)
    ink = ink.filter(ImageFilter.MinFilter(SPECK)).filter(ImageFilter.MaxFilter(SPECK))
    if ink.histogram()[255] < BLANK_PIXELS:
        return None
    if box.field != NOTES_BOX.field:
        cols = list(ink.resize((crop.width, 1), Image.Resampling.BOX).getdata())
        runs = _runs(cols, round(WORD_GAP * scale))
        x0, x1 = runs[0][0], runs[-1][1]
        band = ink.crop((x0, 0, x1, crop.height))
        rows = list(band.resize((1, crop.height), Image.Resampling.BOX).getdata())
        y0, y1, _ = max(_runs(rows, round(LINE_GAP * scale)), key=lambda run: run[2])
        pad = round(PAD * scale)
        cut = (
            max(0, x0 - pad),
            max(0, y0 - pad),
            min(crop.width, x1 + pad),
            min(crop.height, y1 + pad),
        )
        crop, ink = crop.crop(cut), ink.crop(cut)
    keep = ink.filter(ImageFilter.MaxFilter(KEEP))
    crop = Image.composite(crop, Image.new("L", crop.size, 255), keep)
    return ImageOps.expand(crop, border=20, fill=255)


def _words(image: Image.Image, psm: int, alphabet: str | None) -> list[tuple[str, float]]:
    config = f"--psm {psm}"
    if alphabet:
        config += f" -c tessedit_char_whitelist={alphabet}"
    data = pytesseract.image_to_data(image, config=config, output_type=pytesseract.Output.DICT)
    return [
        (text.strip(), float(conf))
        for text, conf in zip(data["text"], data["conf"], strict=True)
        if text.strip() and float(conf) >= 0
    ]


def _read(crop: Image.Image, field: str, psm: int) -> FieldRead | None:
    found = kind(field)
    words = _words(crop, psm, ALPHABETS[found])
    if not words:
        return None
    text = canonical(field, " ".join(word for word, _ in words))
    confidence = min(conf for _, conf in words) / 100
    return FieldRead(text, round(confidence, 4) if format_ok(field, text) else 0.0)


WORD = re.compile(r"class='ocrx_word'[^>]*x_wconf (?P<conf>[0-9.]+)'>(?P<text>[^<\n]*)")
GROUP = re.compile(r"id='lstm_choices_[^']*'>(?P<body>.*?)</span></span>", re.S)
CHOICE = re.compile(r"id='choice_[^']*' title='x_confs (?P<conf>[0-9.]+)'>(?P<char>[^<]*)")


def _characters(crop: Image.Image, alphabet: str) -> tuple[list[tuple[str, list]], float]:
    """Each character Tesseract read in a one-line crop with its alternatives [(character,
    confidence)] (hOCR with lstm_choice_mode 2), and the lowest word confidence."""
    config = f"--psm 7 -c tessedit_char_whitelist={alphabet} -c lstm_choice_mode=2"
    hocr = pytesseract.image_to_pdf_or_hocr(crop, extension="hocr", config=config).decode()
    words = [(m.group("text").strip(), float(m.group("conf"))) for m in WORD.finditer(hocr)]
    text = "".join(html.unescape(word) for word, _ in words)
    groups = [
        [
            (html.unescape(c.group("char")), float(c.group("conf")))
            for c in CHOICE.finditer(g["body"])
        ]
        for g in GROUP.finditer(hocr)
    ]
    if len(groups) != len(text):  # choices that do not line up with the text are not used
        groups = [[] for _ in text]
    return list(zip(text, groups, strict=True)), min((c for _, c in words), default=0.0)


def _read_by_position(crop: Image.Image, field: str) -> FieldRead | None:
    """A code whose characters are fixed by position (an ICD-10 code: letter, digit, digit or A
    or B, point): a character that breaks its position's rule is replaced by Tesseract's most
    likely alternative that keeps it; the field's confidence is then at most that alternative's."""
    rules = POSITIONS[kind(field)]
    chars, confidence = _characters(crop, ALPHABETS[kind(field)] or "")
    if not chars:
        return None
    text = []
    for index, (char, alternatives) in enumerate(chars):
        allowed = rules[index] if index < len(rules) else None
        fits = [(conf, alt) for alt, conf in alternatives if allowed and alt in allowed]
        if allowed is None or char in allowed or not fits:
            text.append(char)
            continue
        conf, alt = max(fits)
        text.append(alt)
        confidence = min(confidence, conf)
    value = canonical(field, "".join(text))
    return FieldRead(value, round(confidence / 100, 4) if format_ok(field, value) else 0.0)


def read_box(page: Image.Image, box: Box) -> FieldRead | None:
    """The text in one box and its confidence; None for a blank box. A box of one or a few
    characters is read in several Tesseract page segmentation modes (one character, one word,
    one line) and the first reading that passes the field's format check is kept. A code with
    fixed character positions that fails its check is read again by position."""
    crop = _crop(page, box)
    if crop is None:
        return None
    if box.field == NOTES_BOX.field:
        return _read(crop, box.field, 6)
    found = kind(box.field)
    modes = SHORT_MODES.get(found, (7,))
    reads = [read for psm in modes if (read := _read(crop, box.field, psm)) is not None]
    if found in POSITIONS and not any(read.confidence > 0 for read in reads):
        again = _read_by_position(crop, box.field)
        reads = [again, *reads] if again is not None else reads
    passing = [read for read in reads if read.confidence > 0]
    return (passing or reads or [None])[0]


FORM_BOXES = [*ALL_PAGE_ONE_BOXES, NOTES_BOX, *PRIMARY_PAID_BOXES]


def page_title(page: Image.Image) -> str:
    """The printed title at the top of a scanned page, upper case ("HEALTH INSURANCE CLAIM FORM
    ..." on page 1, "ATTACHMENTS FOR CLAIM ..." on page 2), read without straightening: the band
    is tall enough for the skew a scan has."""
    scale = page.width / PAGE_WIDTH
    x0, y0, x1, y1 = (round(v * scale) for v in TITLE_BAND)
    crop = page.crop((x0, y0, x1, y1))
    if scale < TARGET_SCALE:
        size = (round(crop.width * TARGET_SCALE / scale), round(crop.height * TARGET_SCALE / scale))
        crop = crop.resize(size, Image.Resampling.LANCZOS)
    return " ".join(pytesseract.image_to_string(crop, config="--psm 6").split()).upper()


# --- Is it our form's page, upright and in place? (B5, form_check.py) ----------------------------


def turn_upright(page: Image.Image) -> tuple[Image.Image, int | None]:
    """The page turned so that its title band reads as one of our form's titles, and that page
    (0 or 1); the page as it is and None when no turn gives a title of our form."""
    for turn in TURNS:
        turned = page if turn == 0 else page.rotate(turn, expand=True)
        found = form_page_of(page_title(turned))
        if found is not None:
            return turned, found
    return page, None


def tilt_angle(page: Image.Image) -> float:
    """The rotation (degrees) that makes the page's rules and text rows horizontal, searched
    within TILT_RANGE: a coarse search on the page about 320 pixels wide, then a fine one about
    640 wide. Only used to refuse a page tilted beyond SKEW_RANGE; straightening uses
    skew_angle."""
    angle = 0.0
    for width, span, step in ((320, TILT_RANGE, 1.0), (640, 1.5, 0.1)):
        divisor = max(1, page.width // width)
        small = page.resize((max(1, page.width // divisor), max(1, page.height // divisor)))
        dark = small.filter(ImageFilter.MedianFilter(3)).point(lambda v: 255 if v < 200 else 0)
        steps = round(span / step)
        candidates = [angle + n * step for n in range(-steps, steps + 1)]
        angle = max(candidates, key=lambda a: _row_profile_score(dark, a))
    return round(angle, 2)


def _without_rules(crop: Image.Image) -> tuple[Image.Image, Image.Image]:
    """(the crop, its ink) with the rows of printed rules whitened: rows mostly dark, as a box
    border is and a line of text is not."""
    cleaned = crop.filter(ImageFilter.MedianFilter(3))
    ink = cleaned.point(lambda v: 255 if v < DARK_LEVEL else 0)
    rows = list(ink.resize((1, ink.height), Image.Resampling.BOX).getdata())
    for y, level in enumerate(rows):
        if level > 0.8 * 255:
            cleaned.paste(255, (0, y, cleaned.width, y + 1))
            ink.paste(0, (0, y, ink.width, y + 1))
    return cleaned, ink


def _edge(levels: list[int]) -> int:
    """The position where the first EDGE_SHARE of the ink is reached."""
    total, running = sum(levels), 0
    for position, level in enumerate(levels):
        running += level
        if running >= EDGE_SHARE * total:
            return position
    return 0


def _label_seen(page: Image.Image, label: Label) -> Seen:
    """Where the ink of a label is, against where the form prints it, and (for a caption) how
    close the text read there is: the line of ink with the most ink in the label's search area,
    its left end and its top."""
    scale = page.width / PAGE_WIDTH
    x0, y0, x1, y1 = (round(v * scale) for v in label.search)
    cleaned, ink = _without_rules(page.crop((x0, y0, x1, y1)))
    rows = list(ink.resize((1, ink.height), Image.Resampling.BOX).getdata())
    lines = _runs(rows, max(1, round(0.5 * scale)))
    if not lines:
        return Seen(label, 0.0 if label.read else None, None, None)
    top, bottom, _ = max(lines, key=lambda run: run[2])
    line = ink.crop((0, top, ink.width, bottom))
    cols = list(line.resize((line.width, 1), Image.Resampling.BOX).getdata())
    left_px = next((x for x, level in enumerate(cols) if level >= EDGE_COLUMN * 255), 0)
    top_px = top + _edge(list(line.resize((1, line.height), Image.Resampling.BOX).getdata()))
    dx = (x0 + left_px) / scale - label.x
    dy = (y0 + top_px) / scale - (label.cap_top - INK_ABOVE_CAP)
    match = None
    if label.read:
        factor = 2 * TARGET_SCALE / scale
        size = (round(cleaned.width * factor), round(cleaned.height * factor))
        big = ImageOps.autocontrast(cleaned.resize(size, Image.Resampling.LANCZOS), cutoff=1)
        text = pytesseract.image_to_string(
            ImageOps.expand(big, border=20, fill=255), config="--psm 13"
        )
        match = round(similarity(text, label.text), 3)
    return Seen(label, match, round(dx, 2), round(dy, 2))


def labels_seen(page: Image.Image, index: int) -> list[Seen]:
    """Each label of page `index` as found on a straightened page."""
    return [_label_seen(page, label) for label in page_labels(index)]


def checked_page(page: Image.Image, index: int, where: str | None = None) -> Image.Image:
    """Page `index` of a scanned form (0: the claim, 1: its attachments), turned upright and
    straightened, once its printed labels are found where the form prints them; NotOurForm
    otherwise, with a message naming the page (`where`, "page 1" by default)."""
    where = where or f"page {index + 1}"
    upright, found = turn_upright(page)
    if found is None:
        tilt = tilt_angle(page)
        if abs(tilt) <= SKEW_RANGE:
            raise NotOurForm(not_our_form(where, index))
        turned = page.rotate(tilt, resample=Image.Resampling.BICUBIC, fillcolor=255)
        if form_page_of(page_title(turned)) is not None:
            raise NotOurForm(tilted(where, tilt))
        # The title may be cut off at a corner of a tilted scan: say both.
        raise NotOurForm(f"{not_our_form(where, index)} {also_tilted(tilt)}")
    if found != index:
        raise NotOurForm(wrong_page(where, found, index))
    tilt = tilt_angle(upright)
    if abs(tilt) > SKEW_RANGE:
        raise NotOurForm(tilted(where, tilt))
    straight = straighten(upright)
    problem = verdict(labels_seen(straight, index), index, where)
    if problem:
        raise NotOurForm(problem)
    return straight


def read_page(page: Image.Image, index: int, where: str | None = None) -> dict[str, FieldRead]:
    """Every non-blank box of page `index` (0: the claim, 1: its attachments) of a scanned form,
    keyed by layout field path; the page is checked, turned upright and straightened first
    (NotOurForm when it is not our form's page `index` or not where the layout puts it)."""
    straight = checked_page(page, index, where)
    found = {}
    for box in FORM_BOXES:
        if box.page == index and (read := read_box(straight, box)) is not None:
            found[box.field] = read
    return found


def continued_notes(pages: list[Image.Image]) -> list[FieldRead]:
    """The notes read from each continuation page of a scan (pages 3 on, D-DOC-3), in page order;
    the titles of pages 2 on are read (each page turned upright first) and checked first
    (`check_continuation`), and each continuation page is checked as page 2 is (`read_page`): it
    prints the same labels."""
    if len(pages) < FORM_PAGES:
        return []
    upright = [turn_upright(page)[0] for page in pages[1:]]  # page 1's title is not needed
    check_continuation(["", *(page_title(page) for page in upright)])
    reads = []
    for index in range(FORM_PAGES, len(pages)):
        read = read_page(upright[index - 1], 1, f"page {index + 1}").get(NOTES_BOX.field)
        if read is not None:
            reads.append(read)
    return reads


def joined_notes(first: FieldRead | None, more: list[FieldRead]) -> FieldRead | None:
    """Page 2's notes and the continuation pages' as one read, at the lowest confidence."""
    reads = [read for read in (first, *more) if read is not None]
    if not reads or not more:
        return first
    return FieldRead(" ".join(r.text for r in reads), min(r.confidence for r in reads))


def read_scan(pages: list[Image.Image]) -> dict[str, FieldRead]:
    """Every non-blank box of a scanned form, keyed by layout field path."""
    found: dict[str, FieldRead] = {}
    for index, page in enumerate(pages):
        if any(box.page == index for box in FORM_BOXES):
            found |= read_page(page, index)
    notes = joined_notes(found.get(NOTES_BOX.field), continued_notes(pages))
    if notes is not None:
        found[NOTES_BOX.field] = notes
    return found


def parse_scan(data: bytes) -> tuple[dict[str, Any], dict[str, float]]:
    """The claim dictionary read from a scanned PDF or image (a value that fails its format check
    left out), and each field's confidence."""
    reads = read_scan(page_images(data))
    readable = {field: read.text for field, read in reads.items() if format_ok(field, read.text)}
    return from_form_values(readable), {field: read.confidence for field, read in reads.items()}
