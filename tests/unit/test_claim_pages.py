"""D-DOC-2: one claim from its form's pages in several files (app/intake/files.py
read_claim_files). A digital PDF split into its two pages reads as the whole PDF does; the pages
must be the claim form's page 1 then page 2; JSON, TIFF and more than two pages are refused."""

import io
import json
import random

import pymupdf
import pytest

from app.domain.contracts import SourceFormat
from app.intake.files import UnreadableFile, read_claim_file, read_claim_files
from app.intake.form_codec import to_form_values
from tests.unit.test_forms import full_claim
from training.generate.forms import render_pdf, render_scan


def split(pdf: bytes) -> list[bytes]:
    found = []
    with pymupdf.open(stream=pdf, filetype="pdf") as doc:
        for index in range(doc.page_count):
            with pymupdf.open() as one:
                one.insert_pdf(doc, from_page=index, to_page=index)
                found.append(one.tobytes())
    return found


PDF = render_pdf(to_form_values(full_claim()))
FIRST, SECOND = split(PDF)


def test_a_digital_pdf_split_into_its_pages_reads_as_the_whole_pdf() -> None:
    assert read_claim_files([FIRST, SECOND]) == read_claim_file(PDF)
    claim, _, source = read_claim_files([FIRST, SECOND])
    assert source is SourceFormat.DIGITAL_PDF and claim["clinical_notes"]


def test_one_file_reads_as_before() -> None:
    assert read_claim_files([PDF]) == read_claim_file(PDF)


def test_page_one_alone_is_a_claim_without_its_attachments() -> None:
    claim, _, _ = read_claim_files([FIRST])

    assert claim["claim_id"] == full_claim().claim_id and not claim.get("clinical_notes")


def tiff_page() -> bytes:
    page = render_scan(to_form_values(full_claim()), random.Random(1), value_noise_rate=0).pages[1]
    out = io.BytesIO()
    page.save(out, format="TIFF")
    return out.getvalue()


@pytest.mark.parametrize(
    ("files", "message"),
    [
        ([json.dumps({"claim_id": "X"}).encode(), SECOND], "a JSON claim is a whole claim"),
        ([FIRST, PDF], "a claim form has 2 pages"),
        ([SECOND, FIRST], "the first file is page 2 of the claim form"),
        ([FIRST, FIRST], "the second file is another page 1"),
        ([FIRST, b""], "file 2 is empty"),
        ([FIRST, b"%PDF-1.7 broken"], "file 2: the PDF cannot be read"),
        ([FIRST, b"plain text"], "file 2 is not a PDF, PNG or JPEG"),
        ([], "no file was sent"),
    ],
    ids=["json", "three pages", "swapped", "page 1 twice", "empty", "broken", "text", "none"],
)
def test_files_that_are_not_one_claim_form_s_pages_are_refused(
    files: list[bytes], message: str
) -> None:
    with pytest.raises(UnreadableFile, match=message):
        read_claim_files(files)


def test_a_tiff_page_is_refused_among_several_files() -> None:
    with pytest.raises(UnreadableFile, match="a TIFF scan can be uploaded on its own"):
        read_claim_files([FIRST, tiff_page()])
