"""B5: the form's printed labels are checked before any box is read (app/intake/form_check.py,
ocr.checked_page, files.py). A file that is not our form, or our form tilted or shifted beyond
what the reader handles, is refused with a message naming the page and what was expected; our
form scanned on its side or upside down is turned upright and read as the upright scan is. The
OCR tests need the Tesseract program (CI installs it)."""

import shutil

import pymupdf
import pytest

from app.intake.files import UnreadableFile, read_claim_file, read_claim_files
from app.intake.form_check import (
    REQUIRED,
    TOLERANCE_X,
    TOLERANCE_Y,
    NotOurForm,
    Seen,
    check_text_page,
    form_page_of,
    holds,
    page_labels,
    verdict,
)
from app.intake.form_codec import to_form_values
from app.intake.layout import CHECKED_CAPTIONS, PAGE_HEIGHT, PAGE_WIDTH
from app.intake.ocr import checked_page, read_page, straighten, turn_upright
from scripts.verify.foreign_documents import (
    image_bytes,
    scan,
    shifted,
    shifted_pdf,
    tilted,
    turned,
    unrelated_page_image,
    unrelated_pdf,
)
from scripts.verify.ocr_accuracy import scanned_pdf
from tests.unit.test_forms import full_claim
from training.generate.forms import render_pdf

needs_tesseract = pytest.mark.skipif(
    shutil.which("tesseract") is None, reason="the Tesseract program is not installed"
)
PDF = render_pdf(to_form_values(full_claim()))


def words(pdf: bytes) -> list[list[tuple]]:
    with pymupdf.open(stream=pdf, filetype="pdf") as doc:
        return [[w[:5] for w in page.get_text("words")] for page in doc]


# --- The labels and the verdict (no OCR) ------------------------------------------------------


def test_each_page_checks_its_title_and_captions_spread_over_the_page() -> None:
    first, second = page_labels(0), page_labels(1)

    assert [label.text for label in first[:2]] == [
        "HEALTH INSURANCE CLAIM FORM",
        "1a. INSURED'S ID NUMBER",
    ]
    assert len(first) == 1 + len(CHECKED_CAPTIONS[0]) == 9
    assert [label.text for label in second] == [
        "ATTACHMENTS FOR CLAIM",
        "ATTACHMENT A: CLINICAL NOTES",
    ]
    for label in first + second:
        x0, y0, x1, y1 = label.search
        assert 0 <= x0 < x1 <= PAGE_WIDTH and 0 <= y0 < y1 <= PAGE_HEIGHT
    tops = [label.baseline for label in first]
    lefts = [label.x for label in first]
    assert min(tops) < 100 and max(tops) > 550  # top and bottom of the page
    assert min(lefts) <= 31 and max(lefts) > 400  # left and right


@pytest.mark.parametrize(
    ("text", "page"),
    [
        ("HEALTH INSURANCE CLAIM FORM (CLAIMSENSE SYNTHETIC LAYOUT, NOT THE CMS-1500)", 0),
        ("HEALTH INSURANCE CLAIM FORM (CLAIMSENSE SYNTHETIC LAYOUT, NOT THE CMS-1 500) . CLAIM", 0),
        ("EALTH INSURANCE CIAIM FORM (CLAIMSENSE", 0),  # OCR slips
        ("ATTACHMENTS FOR CLAIM CLM-FORM-0001 ATTACHMENT A: CLINICAL NOTES", 1),
        ("GARDEN COMMITTEE NEWSLETTER", None),
        ("", None),
        ("ATTACHMENT A: CLINICAL NOTES", None),  # the caption alone is not page 2's title
    ],
)
def test_a_title_band_tells_which_page_of_our_form_it_is(text: str, page: int | None) -> None:
    assert form_page_of(text) == page


def test_holds_finds_words_inside_a_longer_text_allowing_ocr_slips() -> None:
    assert holds("xx HEALTH INSURANCE CLAIM FORM yy", "HEALTH INSURANCE CLAIM FORM") == 1.0
    assert 0.8 <= holds("HEALTH lNSURANCE CLAlM FORM", "HEALTH INSURANCE CLAIM FORM") < 1.0
    assert holds("NOTHING ALIKE AT ALL HERE", "HEALTH INSURANCE CLAIM FORM") < 0.6


def seen(similarity: float | None, dx: float | None, dy: float | None) -> Seen:
    return Seen(page_labels(0)[1], similarity, dx, dy)


@pytest.mark.parametrize(
    ("label", "in_place"),
    [
        (seen(0.9, 0.2, -0.4), True),
        (seen(0.9, TOLERANCE_X, -TOLERANCE_Y), True),
        (seen(0.9, TOLERANCE_X + 0.1, 0.0), False),  # moved sideways
        (seen(0.9, 0.0, TOLERANCE_Y + 0.1), False),  # moved down
        (seen(0.4, 0.0, 0.0), False),  # in place, but another text
        (seen(None, 0.0, 0.0), True),  # a title: its text is read by the band
        (seen(0.0, None, None), False),  # no ink there
    ],
)
def test_a_label_is_in_place_when_read_close_enough_where_the_form_prints_it(
    label: Seen, in_place: bool
) -> None:
    assert label.in_place is in_place


def test_the_verdict_needs_enough_labels_in_place_and_names_the_page() -> None:
    good, bad = seen(1.0, 0.0, 0.0), seen(0.1, 9.0, 9.0)

    assert verdict([good] * REQUIRED[0] + [bad] * 3, 0, "page 1") is None
    message = verdict([good] * (REQUIRED[0] - 1) + [bad] * 4, 0, "page 1")
    assert message and message.startswith("page 1 does not line up with page 1 of the ClaimSense")
    assert f"only {REQUIRED[0] - 1} of the 9 printed labels" in message
    assert '"HEALTH INSURANCE CLAIM FORM"' in message and '"2. PATIENT LAST NAME"' in message


# --- Pages with a text layer (digital PDF) ------------------------------------------------------


def test_our_digital_pdf_has_every_label_in_place() -> None:
    first, second = words(PDF)

    check_text_page(first, 0, "page 1")
    check_text_page(second, 1, "page 2")


def test_a_pdf_with_unrelated_text_is_refused_naming_the_page_and_what_was_expected() -> None:
    with pytest.raises(UnreadableFile) as refused:
        read_claim_file(unrelated_pdf())

    message = str(refused.value)
    assert message.startswith("page 1 of the PDF is not page 1 of the ClaimSense claim form")
    assert "0 of 9 found" in message and '"HEALTH INSURANCE CLAIM FORM"' in message


def test_our_digital_pdf_shifted_down_is_refused_and_a_small_shift_is_read() -> None:
    with pytest.raises(UnreadableFile, match="page 1 of the PDF is not page 1"):
        read_claim_file(shifted_pdf(PDF, 0, 8))

    claim, _, _ = read_claim_file(shifted_pdf(PDF, 1, 1))
    assert claim["claim_id"] == full_claim().claim_id


def test_a_digital_page_2_sent_as_page_1_is_refused() -> None:
    _, second = words(PDF)

    with pytest.raises(NotOurForm, match="is page 2 of the claim form"):
        check_text_page(second, 0, "page 1")


def test_a_second_pdf_page_that_is_not_our_page_2_is_refused() -> None:
    with pymupdf.open(stream=PDF, filetype="pdf") as ours, pymupdf.open() as mixed:
        mixed.insert_pdf(ours, from_page=0, to_page=0)
        with pymupdf.open(stream=unrelated_pdf(), filetype="pdf") as other:
            mixed.insert_pdf(other)
        data = mixed.tobytes()

    with pytest.raises(UnreadableFile, match="page 2 of the PDF is not page 2"):
        read_claim_file(data)


def test_a_password_protected_pdf_is_refused() -> None:
    with pymupdf.open(stream=PDF, filetype="pdf") as doc:
        locked = doc.tobytes(encryption=pymupdf.PDF_ENCRYPT_AES_256, owner_pw="o", user_pw="u")

    with pytest.raises(UnreadableFile, match="protected by a password"):
        read_claim_file(locked)
    with pytest.raises(UnreadableFile, match="file 2: the PDF is protected by a password"):
        read_claim_files([PDF, locked])


def test_a_pdf_page_far_larger_than_a_form_page_is_refused() -> None:
    with pymupdf.open() as doc:
        doc.new_page(width=5000, height=5000)
        huge = doc.tobytes()

    with pytest.raises(UnreadableFile, match="far larger than a claim form page"):
        read_claim_file(huge)


# --- Scanned pages (OCR) ---------------------------------------------------------------------

SCAN = scan(full_claim())
FIRST, SECOND = (page.convert("L") for page in SCAN.pages)


@needs_tesseract
def test_our_scanned_pages_pass_and_are_straightened_as_before() -> None:
    assert checked_page(FIRST, 0).tobytes() == straighten(FIRST).tobytes()
    assert checked_page(SECOND, 1).tobytes() == straighten(SECOND).tobytes()


@needs_tesseract
@pytest.mark.parametrize("degrees", [90, 180, 270])
def test_a_page_scanned_on_its_side_or_upside_down_is_turned_upright(degrees: int) -> None:
    upright, page = turn_upright(turned(FIRST, degrees))

    assert page == 0 and upright.tobytes() == FIRST.tobytes()


@needs_tesseract
def test_a_page_turned_90_degrees_reads_as_the_upright_page() -> None:
    assert read_page(turned(FIRST, 90), 0) == read_page(FIRST, 0)


@needs_tesseract
@pytest.mark.parametrize("degrees", [10, -10, 4])
def test_a_page_tilted_beyond_2_degrees_is_refused(degrees: float) -> None:
    with pytest.raises(NotOurForm, match=r"page 1 is tilted by about \d+ degrees"):
        checked_page(tilted(FIRST, degrees), 0)


@needs_tesseract
@pytest.mark.parametrize(("dx", "dy"), [(8, 0), (-6, 0), (0, 4), (0, -4)])
def test_a_page_shifted_beyond_what_the_reader_handles_is_refused(dx: float, dy: float) -> None:
    with pytest.raises(NotOurForm, match="page 1 does not line up with page 1"):
        checked_page(shifted(FIRST, dx, dy), 0)


@needs_tesseract
def test_a_page_shifted_slightly_is_read() -> None:
    checked_page(shifted(FIRST, 1.5, 1), 0)


@needs_tesseract
def test_an_image_of_an_unrelated_page_is_refused() -> None:
    with pytest.raises(UnreadableFile) as refused:
        read_claim_file(image_bytes(unrelated_page_image(), "JPEG"))

    assert str(refused.value).startswith("page 1 is not page 1 of the ClaimSense claim form")
    assert '"HEALTH INSURANCE CLAIM FORM"' in str(refused.value)


@needs_tesseract
def test_page_2_alone_is_refused_as_a_claim() -> None:
    with pytest.raises(UnreadableFile, match="page 1 is page 2 of the claim form"):
        read_claim_file(image_bytes(SECOND))


@needs_tesseract
def test_a_two_page_scan_with_an_unrelated_second_page_is_refused() -> None:
    with pytest.raises(UnreadableFile, match="page 2 is not page 2 of the ClaimSense"):
        read_claim_file(scanned_pdf([FIRST, unrelated_page_image()]))


@needs_tesseract
def test_among_several_files_each_page_is_checked_and_turned() -> None:
    with pytest.raises(UnreadableFile, match="file 2 is not page 2 of the ClaimSense"):
        read_claim_files([image_bytes(FIRST), image_bytes(unrelated_page_image())])
    with pytest.raises(UnreadableFile, match="the first file is page 2 of the claim form"):
        read_claim_files([image_bytes(turned(SECOND, 90)), image_bytes(FIRST)])

    claim, _, _ = read_claim_files([image_bytes(turned(FIRST, 270)), image_bytes(SECOND)])
    assert claim["claim_id"] == full_claim().claim_id and claim["clinical_notes"]


def test_an_image_with_too_many_pixels_is_refused() -> None:
    from PIL import Image

    big = image_bytes(Image.new("L", (8000, 7000), 255))

    with pytest.raises(UnreadableFile, match="too many pixels"):
        read_claim_file(big)
    with pytest.raises(UnreadableFile, match="file 2: the image has too many pixels"):
        read_claim_files([PDF, big])


def test_a_foreign_pdf_among_several_files_is_refused_naming_the_file() -> None:
    with pymupdf.open(stream=PDF, filetype="pdf") as ours, pymupdf.open() as first:
        first.insert_pdf(ours, from_page=0, to_page=0)
        page_one = first.tobytes()

    with pytest.raises(UnreadableFile) as refused:
        read_claim_files([page_one, unrelated_pdf()])

    assert str(refused.value).startswith("file 2 is not page 2 of the ClaimSense claim form: its")
