"""P5.1: claim files and the scanned-form OCR (app/intake/files.py, ocr.py, field_formats.py).
Field accuracy on held-out scans is measured by scripts/verify/ocr_accuracy.py; these tests check
the behaviour on a few rendered forms. The OCR tests need the Tesseract program (CI installs it)."""

import io
import json
import random
import shutil

import pytest
from PIL import Image

from app.domain.contracts import IntakeClaim, SourceFormat
from app.intake.field_formats import format_ok, kind
from app.intake.files import UnreadableFile, read_claim_file
from app.intake.form_codec import to_form_values
from app.intake.layout import ALL_PAGE_ONE_BOXES, PRIMARY_PAID_BOXES
from app.intake.ocr import page_images, page_title, read_scan, skew_angle
from scripts.verify.ocr_accuracy import scanned_pdf
from tests.unit.test_forms import full_claim
from training.generate.forms import render_pdf, render_scan

needs_tesseract = pytest.mark.skipif(
    shutil.which("tesseract") is None, reason="the Tesseract program is not installed"
)
FIELDS = [box.field for box in ALL_PAGE_ONE_BOXES + PRIMARY_PAID_BOXES]


@pytest.mark.parametrize(
    ("field", "text", "ok"),
    [
        ("billing_npi", "1245319599", True),
        ("billing_npi", "1245319598", False),  # check digit
        ("service_lines.0.date_of_service", "10/05/2026", True),
        ("service_lines.0.date_of_service", "13/05/2026", False),
        ("diagnoses.3", "Z79.01", True),
        ("diagnoses.3", "279.01", False),
        ("service_lines.2.modifiers", "XS RT", True),
        ("service_lines.1.charge_cents", "265.05", True),
        ("service_lines.1.charge_cents", "265.5", False),
        ("patient.sex", "F", True),
        ("patient.sex", "FF", False),
        ("other_coverage.primary_paid.1", "Line 4: 0.07", True),
        ("patient.address.city", "Salt Lake City", True),
    ],
)
def test_format_checks(field: str, text: str, ok: bool) -> None:
    assert format_ok(field, text) is ok


def test_every_layout_field_has_a_kind() -> None:
    assert {kind(field) for field in FIELDS} >= {"npi", "date", "diagnosis", "amount", "text"}


def test_a_json_file_is_read_as_json() -> None:
    claim = full_claim().model_dump(mode="json")

    assert read_claim_file(json.dumps(claim).encode()) == (claim, {}, SourceFormat.JSON)


def test_a_digital_pdf_is_read_exactly_with_full_confidence() -> None:
    claim = full_claim()

    data, confidences, source = read_claim_file(render_pdf(to_form_values(claim)))

    assert source is SourceFormat.DIGITAL_PDF
    assert IntakeClaim.model_validate(data) == claim
    assert set(confidences.values()) == {1.0}


def test_a_digital_pdf_field_that_fails_its_format_check_gets_confidence_0() -> None:
    values = to_form_values(full_claim())
    values["billing_npi"] = "1245319598"

    _, confidences, _ = read_claim_file(render_pdf(values))

    assert confidences["billing_npi"] == 0.0 and confidences["claim_id"] == 1.0


@pytest.mark.parametrize("data", [b"", b"not a claim", b"%PDF-1.7 broken", b"{not json"])
def test_an_unreadable_file_is_refused(data: bytes) -> None:
    with pytest.raises(UnreadableFile):
        read_claim_file(data)


def test_a_multi_page_tiff_gives_one_image_per_page() -> None:
    pages = [Image.new("L", (100, 120), 255), Image.new("L", (100, 120), 0)]
    buffer = io.BytesIO()
    pages[0].save(buffer, format="TIFF", save_all=True, append_images=pages[1:])

    assert [page.getpixel((0, 0)) for page in page_images(buffer.getvalue())] == [255, 0]


def test_the_skew_of_a_scanned_page_is_found() -> None:
    scan = render_scan(to_form_values(full_claim()), random.Random(3), value_noise_rate=0.0)

    found = skew_angle(scan.pages[0])

    assert abs(found + scan.noise["visual"]["skew_degrees"]) <= 0.15


@needs_tesseract
@pytest.mark.parametrize("seed", [1, 2])
def test_a_scanned_form_is_read_with_confidences(seed: int) -> None:
    scan = render_scan(to_form_values(full_claim()), random.Random(seed), value_noise_rate=0.0)

    data, confidences, source = read_claim_file(scanned_pdf(scan.pages))
    reads = read_scan(page_images(scanned_pdf(scan.pages)))

    assert source is SourceFormat.SCANNED and data["claim_id"] == "CLM-FORM-0001"
    written = [f for f in FIELDS if scan.values.get(f)]
    correct = [f for f in written if f in reads and reads[f].text == scan.values[f]]
    assert len(correct) / len(written) >= 0.8  # CI has an older Tesseract than the measured one
    assert not [f for f in FIELDS if f not in scan.values and f in reads]  # blank stays blank
    assert all(0.0 <= value <= 1.0 for value in confidences.values())
    assert all(confidences[f] == 0.0 for f in confidences if not format_ok(f, reads[f].text))


@pytest.mark.skipif(shutil.which("tesseract") is None, reason="Tesseract is not installed")
def test_a_scanned_page_s_title_tells_page_1_from_page_2() -> None:
    """D-DOC-2: the title band is read without straightening, so the pages of a claim sent as
    separate files are put in order by what they print."""
    claim = full_claim()
    scan = render_scan(to_form_values(claim), random.Random(7), value_noise_rate=0.0)

    first, second = (page_title(page.convert("L")) for page in scan.pages)

    assert "CLAIM FORM" in first and "ATTACHMENTS" not in first
    assert "ATTACHMENTS" in second
