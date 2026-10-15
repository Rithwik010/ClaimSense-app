"""D-DOC-1: the original claim file, kept with the claim it creates and served back by
GET /v1/claims/{id}/document: to the provider who filed it (another provider's is 404), to every
reviewer and admin, never without a session (401); inline, with its own content type and nosniff;
byte for byte what was uploaded (its SHA-256). A file refused at upload keeps nothing, a TIFF
scan is read but not kept, and `make demo-reset` deletes every stored file.

D-DOC-2: one claim from its form's pages in several files (POST /v1/claims/intake/files): each
page read by its text layer or by OCR, every file kept in page order and served by
GET /v1/claims/{id}/document/{n}; JSON, TIFF, more than two pages or page 2 first are refused,
keeping nothing."""

import base64
import hashlib
import io
import json
import random
import shutil

import pymupdf
import pytest
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from app.db.models import ClaimDocument
from app.domain.contracts import IntakeClaim
from app.intake.form_codec import to_form_values
from scripts.demo.reset import reset_database
from tests.database import alembic_config
from tests.e2e.support import (
    ADMIN,
    E2E_CASES,
    NO_SESSION,
    PROVIDER,
    REVIEWER,
    CaseRetriever,
    StubModel,
    bearer,
)
from training.generate.forms import render_pdf, render_scan

CASE = E2E_CASES["E2E-14"]
CLAIM = CASE["given"]["claim"]
CLAIM_ID = CLAIM["claim_id"]
TESSERACT = pytest.mark.skipif(shutil.which("tesseract") is None, reason="needs Tesseract")


def client_for(api, load_case_reference):  # noqa: ANN001, ANN201
    load_case_reference(CASE)
    return api(StubModel(json.dumps(CASE["given"]["model_answer"])), CaseRetriever(CASE))


def stored(engine: Engine) -> int:
    with Session(engine) as session:
        return session.scalar(select(func.count()).select_from(ClaimDocument)) or 0


def scan_page(kind: str, claim_id: str = CLAIM_ID) -> bytes:
    """Page one of a scanned copy of the case's claim, as a PNG, JPEG or TIFF image."""
    claim = IntakeClaim.model_validate({**CLAIM, "claim_id": claim_id})
    page = render_scan(to_form_values(claim), random.Random(5), value_noise_rate=0.0).pages[0]
    out = io.BytesIO()
    page.convert("L").save(out, format=kind, dpi=(150, 150))
    return out.getvalue()


def test_a_json_claim_keeps_the_body_as_sent_and_each_role_gets_it(
    api, load_case_reference
) -> None:  # noqa: ANN001
    client = client_for(api, load_case_reference)
    body = json.dumps(CLAIM, indent=2).encode()

    filed = client.post(
        "/v1/claims/intake",
        content=body,
        headers={"Content-Type": "application/json", "X-File-Name": "my%20claim%20%2301.json"},
    )

    assert filed.status_code == 201, filed.text
    url = f"/v1/claims/{CLAIM_ID}/document"
    for who in (PROVIDER, REVIEWER, ADMIN):
        served = client.get(url, headers=who)
        assert served.status_code == 200, served.text
        assert served.headers["content-type"] == "application/json"
        assert served.headers["content-disposition"] == 'inline; filename="my claim _01.json"'
        assert served.headers["x-content-type-options"] == "nosniff"
        assert hashlib.sha256(served.content).hexdigest() == hashlib.sha256(body).hexdigest()
    assert client.get(url, headers=bearer("provider-other")).status_code == 404
    assert client.get(url, headers=NO_SESSION).status_code == 401
    shown = client.get(f"/v1/claims/{CLAIM_ID}", headers=PROVIDER).json()["documents"]
    assert shown == [
        {
            "file_no": 1,
            "file_name": "my claim _01.json",
            "content_type": "application/json",
            "size_bytes": len(body),
        }
    ]
    assert client.get(f"/v1/claims/{CLAIM_ID}", headers=REVIEWER).json()["documents"] == shown
    assert client.get(f"{url}/1", headers=PROVIDER).content == body  # the same file, by number


def test_a_pdf_keeps_its_bytes_and_type(api, load_case_reference) -> None:  # noqa: ANN001
    client = client_for(api, load_case_reference)
    pdf = render_pdf(to_form_values(IntakeClaim.model_validate(CLAIM)))

    filed = client.post(
        "/v1/claims/intake/file",
        content=pdf,
        headers={"Content-Type": "application/pdf", "X-File-Name": "../../etc/claim.pdf"},
    )

    assert filed.status_code == 201, filed.text
    served = client.get(f"/v1/claims/{CLAIM_ID}/document", headers=REVIEWER)
    assert served.headers["content-type"] == "application/pdf"
    assert served.headers["content-disposition"] == 'inline; filename="claim.pdf"'
    assert hashlib.sha256(served.content).hexdigest() == hashlib.sha256(pdf).hexdigest()


@TESSERACT
@pytest.mark.parametrize(("kind", "content_type"), [("PNG", "image/png"), ("JPEG", "image/jpeg")])
def test_an_image_keeps_its_bytes_and_type(
    api, load_case_reference, kind: str, content_type: str
) -> None:  # noqa: ANN001
    client = client_for(api, load_case_reference)
    image = scan_page(kind)

    filed = client.post("/v1/claims/intake/file", content=image)

    assert filed.status_code == 201, filed.text
    served = client.get(f"/v1/claims/{CLAIM_ID}/document", headers=PROVIDER)
    assert served.headers["content-type"] == content_type
    assert hashlib.sha256(served.content).hexdigest() == hashlib.sha256(image).hexdigest()
    (shown,) = client.get(f"/v1/claims/{CLAIM_ID}", headers=REVIEWER).json()["documents"]
    name = shown["file_name"]
    assert name == f"{CLAIM_ID}{'.png' if kind == 'PNG' else '.jpg'}"  # no name sent


@TESSERACT
def test_a_tiff_scan_is_read_but_not_kept(api, load_case_reference, engine) -> None:  # noqa: ANN001
    client = client_for(api, load_case_reference)

    filed = client.post("/v1/claims/intake/file", content=scan_page("TIFF"))

    assert filed.status_code == 201, filed.text
    assert client.get(f"/v1/claims/{CLAIM_ID}/document").status_code == 404
    assert client.get(f"/v1/claims/{CLAIM_ID}").json()["documents"] == []
    assert stored(engine) == 0


def test_a_refused_file_or_a_duplicate_keeps_nothing_new(api, load_case_reference, engine) -> None:  # noqa: ANN001
    client = client_for(api, load_case_reference)

    assert client.post("/v1/claims/intake/file", content=b"not a claim").status_code == 422
    assert client.post("/v1/claims/intake", json={"member_id": "MBR-1"}).status_code == 422
    assert stored(engine) == 0
    first = json.dumps(CLAIM).encode()
    assert (
        client.post(
            "/v1/claims/intake", content=first, headers={"Content-Type": "application/json"}
        ).status_code
        == 201
    )
    again = client.post("/v1/claims/intake", json={**CLAIM, "member_id": "MBR-SOMEONE"})

    assert again.status_code == 409
    assert stored(engine) == 1
    served = client.get(f"/v1/claims/{CLAIM_ID}/document")
    assert served.content == first  # the first upload, untouched


def test_demo_reset_deletes_every_stored_file(api, load_case_reference, engine) -> None:  # noqa: ANN001
    client = client_for(api, load_case_reference)
    assert client.post("/v1/claims/intake", json=CLAIM).status_code == 201
    assert stored(engine) == 1
    url = engine.url.render_as_string(hide_password=False)

    deleted = reset_database(alembic_config(url), url)

    assert deleted == 1
    assert stored(engine) == 0


# --- One claim from several files (D-DOC-2) ------------------------------------------------------


def page_pdfs(pdf: bytes) -> list[bytes]:
    """Each page of a PDF as its own one-page PDF."""
    found = []
    with pymupdf.open(stream=pdf, filetype="pdf") as doc:
        for index in range(doc.page_count):
            with pymupdf.open() as one:
                one.insert_pdf(doc, from_page=index, to_page=index)
                found.append(one.tobytes())
    return found


def scan_pages(kind: str = "PNG") -> list[bytes]:
    """Both pages of a scanned copy of the case's claim, each as its own image."""
    claim = IntakeClaim.model_validate(CLAIM)
    pages = render_scan(to_form_values(claim), random.Random(5), value_noise_rate=0.0).pages
    found = []
    for page in pages:
        out = io.BytesIO()
        page.convert("L").save(out, format=kind, dpi=(150, 150))
        found.append(out.getvalue())
    return found


def files(*parts: tuple[bytes, str]) -> dict:
    return {
        "files": [
            {"name": name, "content_base64": base64.b64encode(data).decode()}
            for data, name in parts
        ]
    }


def test_a_digital_pdf_in_two_page_files_files_the_same_claim(api, load_case_reference) -> None:  # noqa: ANN001
    client = client_for(api, load_case_reference)
    pdf = render_pdf(to_form_values(IntakeClaim.model_validate(CLAIM)))
    first, second = page_pdfs(pdf)

    filed = client.post(
        "/v1/claims/intake/files", json=files((first, "page 1.pdf"), (second, "page 2.pdf"))
    )

    assert filed.status_code == 201, filed.text
    assert filed.json()["source_format"] == "DIGITAL_PDF"
    assert IntakeClaim.model_validate(filed.json()["claim"]) == IntakeClaim.model_validate(CLAIM)
    shown = client.get(f"/v1/claims/{CLAIM_ID}", headers=PROVIDER).json()["documents"]
    assert [(d["file_no"], d["file_name"], d["content_type"]) for d in shown] == [
        (1, "page 1.pdf", "application/pdf"),
        (2, "page 2.pdf", "application/pdf"),
    ]
    for number, data in ((1, first), (2, second)):
        for who in (PROVIDER, REVIEWER, ADMIN):
            served = client.get(f"/v1/claims/{CLAIM_ID}/document/{number}", headers=who)
            assert hashlib.sha256(served.content).hexdigest() == hashlib.sha256(data).hexdigest()
        url = f"/v1/claims/{CLAIM_ID}/document/{number}"
        assert client.get(url, headers=bearer("provider-other")).status_code == 404
        assert client.get(url, headers=NO_SESSION).status_code == 401
    assert client.get(f"/v1/claims/{CLAIM_ID}/document/3", headers=REVIEWER).status_code == 404
    assert client.post(f"/v1/claims/{CLAIM_ID}/process").status_code == 200


@TESSERACT
def test_scanned_pages_as_two_images_file_one_claim_with_its_note(api, load_case_reference) -> None:  # noqa: ANN001
    client = client_for(api, load_case_reference)
    first, second = scan_pages("PNG")

    filed = client.post(
        "/v1/claims/intake/files", json=files((first, "scan-1.png"), (second, "scan-2.png"))
    )

    assert filed.status_code == 201, filed.text
    body = filed.json()
    claim = body.get("claim") or body["received"]
    assert body["source_format"] == "SCANNED" and claim["claim_id"] == CLAIM_ID
    note = claim["clinical_notes"]
    assert len(note) > 20 and note.split()[0] in CLAIM["clinical_notes"]  # read from page 2
    assert all(0.0 <= v <= 1.0 for v in body["field_confidences"].values())
    shown = client.get(f"/v1/claims/{CLAIM_ID}").json()["documents"]
    assert [d["content_type"] for d in shown] == ["image/png", "image/png"]


@TESSERACT
def test_a_digital_page_one_and_a_scanned_page_two_read_each_its_own_way(
    api, load_case_reference
) -> None:  # noqa: ANN001
    client = client_for(api, load_case_reference)
    first, _ = page_pdfs(render_pdf(to_form_values(IntakeClaim.model_validate(CLAIM))))
    _, second = scan_pages("JPEG")

    filed = client.post(
        "/v1/claims/intake/files", json=files((first, "claim.pdf"), (second, "notes.jpg"))
    )

    assert filed.status_code == 201, filed.text
    body = filed.json()
    claim = body.get("claim") or body["received"]
    assert body["source_format"] == "SCANNED"  # part of it was read by OCR
    assert body["field_confidences"]["claim_id"] == 1.0  # page 1 from its text layer
    assert len(claim["clinical_notes"]) > 20  # page 2 by OCR


@pytest.mark.parametrize(
    ("parts", "message"),
    [
        ("json", "a JSON claim is a whole claim"),
        ("tiff", "is not a PDF, PNG or JPEG"),
        ("three", "a claim form has 2 pages"),
        ("swapped", "the first file is page 2 of the claim form"),
        ("twice", "the second file is another page 1"),
        ("empty", "file 2 is empty"),
    ],
)
def test_several_files_that_are_not_a_claim_s_pages_are_refused_and_nothing_is_kept(
    api, load_case_reference, engine, parts: str, message: str
) -> None:  # noqa: ANN001
    client = client_for(api, load_case_reference)
    pdf = render_pdf(to_form_values(IntakeClaim.model_validate(CLAIM)))
    first, second = page_pdfs(pdf)
    tiff = io.BytesIO()
    render_scan(
        to_form_values(IntakeClaim.model_validate(CLAIM)), random.Random(5), value_noise_rate=0.0
    ).pages[1].save(tiff, format="TIFF")
    sent = {
        "json": [(json.dumps(CLAIM).encode(), "claim.json"), (second, "p2.pdf")],
        "tiff": [(first, "p1.pdf"), (tiff.getvalue(), "p2.tif")],
        "three": [(first, "p1.pdf"), (pdf, "both.pdf")],
        "swapped": [(second, "p2.pdf"), (first, "p1.pdf")],
        "twice": [(first, "p1.pdf"), (first, "p1 again.pdf")],
        "empty": [(first, "p1.pdf"), (b"", "p2.pdf")],
    }[parts]

    refused = client.post("/v1/claims/intake/files", json=files(*sent))

    assert refused.status_code == 422, refused.text
    assert message in refused.json()["detail"]
    assert stored(engine) == 0
    assert client.get(f"/v1/claims/{CLAIM_ID}").status_code == 404  # no claim either


def test_files_that_are_not_base64_are_refused(api, load_case_reference) -> None:  # noqa: ANN001
    client = client_for(api, load_case_reference)
    body = {"files": [{"name": "a.pdf", "content_base64": "not base64!"}]}

    refused = client.post("/v1/claims/intake/files", json=body)

    assert refused.status_code == 422 and "base64" in refused.json()["detail"]


@TESSERACT
def test_scanned_pages_in_the_wrong_order_are_refused(api, load_case_reference, engine) -> None:  # noqa: ANN001
    client = client_for(api, load_case_reference)
    first, second = scan_pages("PNG")

    refused = client.post(
        "/v1/claims/intake/files", json=files((second, "scan-2.png"), (first, "scan-1.png"))
    )

    assert refused.status_code == 422
    assert "the first file is page 2 of the claim form" in refused.json()["detail"]
    assert stored(engine) == 0
