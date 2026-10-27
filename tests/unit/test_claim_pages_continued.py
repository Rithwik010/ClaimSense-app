"""D-DOC-3: long notes on continuation pages (app/intake). A claim of up to 5 pages, in one PDF or
as several files: the notes of pages 3 on are read after page 2's, in page order; continuation
pages missing, repeated or out of order, and more than 5 pages, are refused. Two-page claims are
covered, unchanged, by test_claim_pages.py."""

import io
import random

import pymupdf
import pytest

from app.domain.contracts import IntakeClaim, SourceFormat
from app.intake.files import UnreadableFile, read_claim_file, read_claim_files
from app.intake.form_codec import to_form_values
from app.intake.layout import MAX_FORM_PAGES, check_continuation, continuation
from tests.unit.test_claim_pages import split
from tests.unit.test_forms import full_claim
from training.generate.forms import notes_capacity, notes_lines, render_pdf, render_scan

SENTENCES = [
    "Low back pain for {n} months, worse with standing, better with rest.",
    "Physical therapy twice a week for {n} weeks without lasting relief.",
    "Exam today: tenderness over the lower lumbar facets, straight leg raise negative.",
    "Medications reviewed; ibuprofen {n} mg as needed, no new allergies.",
    "Imaging from visit {n} shows facet arthropathy at L4-L5 and L5-S1.",
]


def long_claim(lines_wanted: int) -> IntakeClaim:
    """The test claim with notes long enough for `lines_wanted` rendered lines."""
    claim = full_claim()
    parts, n = [], 1
    while len(notes_lines(" ".join(parts))) < lines_wanted:
        parts.append(SENTENCES[n % len(SENTENCES)].format(n=n))
        n += 1
    return claim.model_copy(update={"clinical_notes": " ".join(parts)})


THREE = long_claim(notes_capacity() + 10)  # page 2 full, page 3 partly
PDF3 = render_pdf(to_form_values(THREE), continued=True)
P1, P2, P3 = split(PDF3)


def words(text: str) -> list[str]:
    return text.split()


def test_continuation_titles() -> None:
    assert continuation("ATTACHMENTS FOR CLAIM X (CONTINUED, PAGE 3 OF 4)") == (3, 4)
    assert continuation("ATTACHMENTS FOR CLAIM X CONTINUED PAGE 3 0F 4") == (3, 4)  # OCR slips
    assert continuation("ATTACHMENTS FOR CLAIM X (CONTINUED, PAGE 3. OF 3)") == (3, 3)
    assert continuation("ATTACHMENTS FOR CLAIM X") is None
    check_continuation(["A", "B"])  # two pages: D-DOC-2's own checks


def test_a_three_page_pdf_reads_every_note() -> None:
    claim, confidences, source = read_claim_file(PDF3)
    assert source is SourceFormat.DIGITAL_PDF
    assert words(claim["clinical_notes"]) == words(THREE.clinical_notes)
    assert confidences["clinical_notes"] == 1.0


def test_its_pages_as_three_files_read_as_the_pdf() -> None:
    assert read_claim_files([P1, P2, P3]) == read_claim_file(PDF3)
    assert read_claim_files([P1 + b"", P2]) != read_claim_file(PDF3)  # page 3's notes count


def test_a_scan_of_three_pages_as_three_pngs() -> None:
    scan = render_scan(to_form_values(THREE), random.Random(3), 0.0, continued=True)
    assert len(scan.pages) == 3
    files = []
    for page in scan.pages:
        out = io.BytesIO()
        page.save(out, format="PNG")
        files.append(out.getvalue())
    claim, confidences, source = read_claim_files(files)
    assert source is SourceFormat.SCANNED
    read = words(claim["clinical_notes"])
    expected = words(THREE.clinical_notes)
    assert len(read) > 0.9 * len(expected)  # page 3 is read too
    assert read[-3:] == expected[-3:]  # the notes end as they end on page 3
    assert 0 <= confidences["clinical_notes"] <= 1


def scanned_pdf(pages: list) -> bytes:
    """An image-only PDF of scanned pages, as a scanner writes it (scripts/verify/ocr_accuracy)."""
    out = io.BytesIO()
    first, *rest = [page.convert("L") for page in pages]
    first.save(out, format="PDF", save_all=True, append_images=rest, resolution=150)
    return out.getvalue()


def test_a_typed_claim_with_scanned_notes_in_one_pdf_is_read_page_by_page() -> None:
    scan = render_scan(to_form_values(THREE), random.Random(3), 0.0, continued=True)
    notes = scanned_pdf(scan.pages[1:])
    with pymupdf.open(stream=P1, filetype="pdf") as mixed:
        with pymupdf.open(stream=notes, filetype="pdf") as scanned:
            mixed.insert_pdf(scanned)
        pdf = mixed.tobytes()
    claim, confidences, source = read_claim_file(pdf)
    assert (claim, confidences, source) == read_claim_files([P1, notes])  # as its pages in files
    assert source is SourceFormat.SCANNED
    typed, _, _ = read_claim_file(PDF3)
    assert {k: v for k, v in claim.items() if k != "clinical_notes"} == {
        k: v for k, v in typed.items() if k != "clinical_notes"
    }  # page 1 read from its text layer
    assert confidences["claim_id"] == 1.0
    read, expected = words(claim["clinical_notes"]), words(THREE.clinical_notes)
    page_two = words(" ".join(notes_lines(THREE.clinical_notes)[: notes_capacity()]))
    assert len(read) > 0.9 * len(expected) and len(read) > len(page_two)  # pages 2 and 3 by OCR


@pytest.mark.parametrize(
    ("files", "message"),
    [
        ([P1, P3, P2], "page 2, the first attachments page, is missing"),
        ([P1, P2, P3, P3], "page 3 is titled page 3 of 3"),
        ([P1, P2, P2], "page 3 is not a continuation page"),
        ([P1, P3], "the second file is another page 1|page 2"),
    ],
    ids=["out of order", "repeated", "not a continuation", "page 2 missing"],
)
def test_continuation_pages_out_of_order_or_missing_are_refused(
    files: list[bytes], message: str
) -> None:
    with pytest.raises(UnreadableFile, match=message):
        read_claim_files(files)


def test_more_than_five_pages_are_refused() -> None:
    six = long_claim(notes_capacity() * (MAX_FORM_PAGES - 1) + 5)
    pdf = render_pdf(to_form_values(six), continued=True)
    assert len(split(pdf)) == MAX_FORM_PAGES + 1
    with pytest.raises(UnreadableFile, match=f"these hold {MAX_FORM_PAGES + 1} pages"):
        read_claim_file(pdf)
    with pytest.raises(UnreadableFile, match="and these files hold more"):
        read_claim_files(split(pdf))
    five = long_claim(notes_capacity() * (MAX_FORM_PAGES - 1) - 5)
    claim, _, _ = read_claim_file(render_pdf(to_form_values(five), continued=True))
    assert words(claim["clinical_notes"]) == words(five.clinical_notes)
