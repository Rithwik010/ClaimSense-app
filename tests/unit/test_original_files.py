"""D-DOC-1: which uploaded claim files are kept (by their first bytes, not the name the browser
sent) and the safe file name kept with them."""

import hashlib

import pytest

from app.intake.documents import MAX_NAME, content_type, original_file, safe_name


@pytest.mark.parametrize(
    ("data", "kind"),
    [
        (b'{"claim_id": "X"}', "application/json"),
        (b'\xef\xbb\xbf  \n{"claim_id": "X"}', "application/json"),
        (b"%PDF-1.7\n...", "application/pdf"),
        (b"\x89PNG\r\n\x1a\n....", "image/png"),
        (b"\xff\xd8\xff\xe0....", "image/jpeg"),
        (b"II*\x00....", None),  # TIFF: read, not kept
        (b"MM\x00*....", None),
        (b"<html>", None),
        (b"", None),
    ],
)
def test_the_kept_type_comes_from_the_first_bytes(data: bytes, kind: str | None) -> None:
    assert content_type(data) == kind


@pytest.mark.parametrize(
    ("name", "kind", "expected"),
    [
        ("claim.json", "application/json", "claim.json"),
        ("../../etc/passwd", "application/json", "passwd.json"),
        ("C:\\scans\\form 1.PDF", "application/pdf", "form 1.PDF"),
        ("my%20claim%20%2301.json", "application/json", "my claim _01.json"),
        ("photo.jpeg", "image/jpeg", "photo.jpeg"),
        ("photo", "image/jpeg", "photo.jpg"),
        ('a"b<script>.png', "image/png", "a_b_script_.png"),
        ("", "image/png", "CLM-1.png"),
        (None, "application/pdf", "CLM-1.pdf"),
        ("...", "application/pdf", "CLM-1.pdf"),
    ],
)
def test_the_file_name_is_a_safe_base_name_with_the_type_s_extension(
    name: str | None, kind: str, expected: str
) -> None:
    assert safe_name(name, "CLM-1", kind) == expected


def test_a_long_name_is_cut_and_keeps_its_extension() -> None:
    name = safe_name("x" * 400 + ".pdf", "CLM-1", "application/pdf")

    assert len(name) == MAX_NAME and name.endswith(".pdf")


def test_the_original_file_keeps_the_bytes_with_their_size_and_hash() -> None:
    kept = original_file(b"%PDF-1.7 body", "form.pdf", "CLM-1")

    assert kept is not None
    assert (kept.file_name, kept.content_type, kept.size_bytes) == (
        "form.pdf",
        "application/pdf",
        13,
    )
    assert kept.sha256 == hashlib.sha256(b"%PDF-1.7 body").hexdigest()
    assert original_file(b"II*\x00tiff", "scan.tif", "CLM-1") is None
