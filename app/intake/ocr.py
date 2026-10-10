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
from app.intake.form_codec import from_form_values
from app.intake.layout import (
    ALL_PAGE_ONE_BOXES,
    NOTES_BOX,
    PAGE_WIDTH,
    PRIMARY_PAID_BOXES,
    Box,
)

RENDER_DPI = 300  # a PDF page is rendered at this resolution for OCR
TARGET_SCALE = 300 / 72  # crops smaller than 300 dpi are enlarged to it before OCR
INSET = 1.5  # points kept clear of each box's printed border
SKEW_RANGE, SKEW_STEP = 2.0, 0.1  # degrees searched when straightening a page
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


def read_scan(pages: list[Image.Image]) -> dict[str, FieldRead]:
    """Every non-blank box of a scanned form, keyed by layout field path."""
    straight = [straighten(page) for page in pages]
    boxes = list(ALL_PAGE_ONE_BOXES) + [NOTES_BOX, *PRIMARY_PAID_BOXES]
    found = {}
    for box in boxes:
        if box.page >= len(straight):
            continue
        read = read_box(straight[box.page], box)
        if read is not None:
            found[box.field] = read
    return found


def parse_scan(data: bytes) -> tuple[dict[str, Any], dict[str, float]]:
    """The claim dictionary read from a scanned PDF or image (a value that fails its format check
    left out), and each field's confidence."""
    reads = read_scan(page_images(data))
    readable = {field: read.text for field, read in reads.items() if format_ok(field, read.text)}
    return from_form_values(readable), {field: read.confidence for field, read in reads.items()}
