"""B5: files that are not our form, or our form turned, tilted or shifted, through
POST /v1/claims/intake/file and /intake/files. Each ends with a clear message: refused at upload
(422, a plain message naming the page and what was expected; nothing filed or kept) or read
correctly; never a 500 and never a claim read into confidently wrong values. A scan turned a
quarter around is turned upright and files the same claim as the upright scan."""

import base64
import json
import re
import shutil

import pytest
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from app.db.models import Claim, ClaimDocument
from app.domain.contracts import IntakeClaim
from app.intake.files import read_claim_file
from app.intake.form_codec import to_form_values
from scripts.verify.foreign_documents import (
    image_bytes,
    scan,
    shifted,
    tilted,
    turned,
    unrelated_page_image,
    unrelated_pdf,
)
from scripts.verify.ocr_accuracy import scanned_pdf
from tests.e2e.support import E2E_CASES, CaseRetriever, StubModel

CASE = E2E_CASES["E2E-14"]
CLAIM = IntakeClaim.model_validate(CASE["given"]["claim"])
TESSERACT = pytest.mark.skipif(shutil.which("tesseract") is None, reason="needs Tesseract")


def client_for(api, load_case_reference):  # noqa: ANN001, ANN201
    load_case_reference(CASE)
    return api(StubModel(json.dumps(CASE["given"]["model_answer"])), CaseRetriever(CASE))


def nothing_filed(engine: Engine) -> bool:
    with Session(engine) as session:
        claims = session.scalar(select(func.count()).select_from(Claim)) or 0
        files = session.scalar(select(func.count()).select_from(ClaimDocument)) or 0
    return claims == 0 and files == 0


def as_files(*parts: bytes) -> dict:
    return {
        "files": [
            {"name": f"page-{n}", "content_base64": base64.b64encode(data).decode()}
            for n, data in enumerate(parts, start=1)
        ]
    }


@pytest.fixture(scope="module")
def pages() -> tuple:
    first, second = scan(CLAIM).pages
    return first.convert("L"), second.convert("L")


def test_a_pdf_that_is_not_our_form_is_refused_with_a_plain_message(
    api, load_case_reference, engine
) -> None:  # noqa: ANN001
    client = client_for(api, load_case_reference)

    refused = client.post("/v1/claims/intake/file", content=unrelated_pdf())

    assert refused.status_code == 422, refused.text
    detail = refused.json()["detail"]
    assert detail.startswith("page 1 of the PDF is not page 1 of the ClaimSense claim form")
    assert '"HEALTH INSURANCE CLAIM FORM"' in detail and '"2. PATIENT LAST NAME"' in detail
    assert nothing_filed(engine)


@TESSERACT
@pytest.mark.parametrize("kind", ["PNG", "JPEG"])
def test_an_image_that_is_not_our_form_is_refused(
    api, load_case_reference, engine, kind: str
) -> None:  # noqa: ANN001
    client = client_for(api, load_case_reference)

    refused = client.post(
        "/v1/claims/intake/file", content=image_bytes(unrelated_page_image(), kind)
    )

    assert refused.status_code == 422, refused.text
    assert refused.json()["detail"].startswith(
        "page 1 is not page 1 of the ClaimSense claim form: the title"
    )
    assert nothing_filed(engine)


@TESSERACT
def test_our_scan_turned_90_degrees_files_the_same_claim_as_the_upright_scan(
    api, load_case_reference, pages
) -> None:  # noqa: ANN001
    client = client_for(api, load_case_reference)
    upright = read_claim_file(image_bytes(pages[0]))

    filed = client.post("/v1/claims/intake/file", content=image_bytes(turned(pages[0], 90)))

    assert filed.status_code == 201, filed.text
    body = filed.json()
    assert body["source_format"] == "SCANNED"
    if "claim" in body:  # every box read passed: filed as a valid claim
        assert IntakeClaim.model_validate(body["claim"]) == IntakeClaim.model_validate(upright[0])
    else:  # filed with its contract errors for the rules
        assert body["received"] == json.loads(json.dumps(upright[0], default=str))
    assert body["field_confidences"] == upright[1]
    assert (body.get("claim") or body["received"])["claim_id"] == CLAIM.claim_id


@TESSERACT
@pytest.mark.parametrize("degrees", [10, -10])
def test_our_scan_tilted_10_degrees_is_refused(
    api, load_case_reference, engine, pages, degrees: int
) -> None:  # noqa: ANN001
    client = client_for(api, load_case_reference)

    refused = client.post(
        "/v1/claims/intake/file", content=image_bytes(tilted(pages[0], degrees), "JPEG")
    )

    assert refused.status_code == 422, refused.text
    detail = refused.json()["detail"]
    assert detail.startswith("page 1 ") and re.search(r"tilted by about \d+ degrees", detail)
    assert "straightened by at most 2 degrees" in detail
    assert nothing_filed(engine)


@TESSERACT
def test_our_scan_shifted_off_its_place_is_refused(api, load_case_reference, engine, pages) -> None:  # noqa: ANN001
    client = client_for(api, load_case_reference)

    refused = client.post("/v1/claims/intake/file", content=image_bytes(shifted(pages[0], 8, 0)))

    assert refused.status_code == 422, refused.text
    assert refused.json()["detail"].startswith("page 1 does not line up with page 1")
    assert nothing_filed(engine)


@TESSERACT
def test_a_two_page_scan_pdf_turned_90_degrees_reads_both_pages(
    api, load_case_reference, pages
) -> None:  # noqa: ANN001
    client = client_for(api, load_case_reference)

    filed = client.post(
        "/v1/claims/intake/file", content=scanned_pdf([turned(page, 90) for page in pages])
    )

    assert filed.status_code == 201, filed.text
    claim = filed.json().get("claim") or filed.json()["received"]
    assert claim["claim_id"] == CLAIM.claim_id and len(claim["clinical_notes"]) > 20


@TESSERACT
def test_several_files_each_page_checked_and_turned(
    api, load_case_reference, engine, pages
) -> None:  # noqa: ANN001
    client = client_for(api, load_case_reference)
    first, second = pages

    foreign = client.post(
        "/v1/claims/intake/files",
        json=as_files(image_bytes(first), image_bytes(unrelated_page_image())),
    )
    tilted_second = client.post(
        "/v1/claims/intake/files",
        json=as_files(image_bytes(first), image_bytes(tilted(second, 10))),
    )

    assert foreign.status_code == 422 and tilted_second.status_code == 422
    assert foreign.json()["detail"].startswith("file 2 is not page 2 of the ClaimSense")
    assert tilted_second.json()["detail"].startswith("file 2 ")
    assert re.search(r"tilted by about \d+ degrees", tilted_second.json()["detail"])
    assert nothing_filed(engine)

    filed = client.post(
        "/v1/claims/intake/files",
        json=as_files(image_bytes(turned(first, 270)), image_bytes(second)),
    )
    assert filed.status_code == 201, filed.text
    claim = filed.json().get("claim") or filed.json()["received"]
    assert claim["claim_id"] == CLAIM.claim_id and len(claim["clinical_notes"]) > 20


def test_an_unreadable_pdf_never_fails_the_server(api, load_case_reference, engine) -> None:  # noqa: ANN001
    import pymupdf

    client = client_for(api, load_case_reference)
    with pymupdf.open(stream=unrelated_pdf(), filetype="pdf") as doc:
        locked = doc.tobytes(encryption=pymupdf.PDF_ENCRYPT_AES_256, owner_pw="o", user_pw="u")
    sent = {
        "password": locked,
        "truncated": unrelated_pdf()[:300],
        "pdf header only": b"%PDF-1.7\n",
    }
    for name, data in sent.items():
        refused = client.post("/v1/claims/intake/file", content=data)
        assert refused.status_code == 422, (name, refused.text)
        again = client.post("/v1/claims/intake/files", json=as_files(to_pdf(), data))
        assert again.status_code == 422, (name, again.text)
    assert nothing_filed(engine)


def to_pdf() -> bytes:
    """Page 1 of the case's claim as a digital PDF of our form."""
    import pymupdf

    from training.generate.forms import render_pdf

    with pymupdf.open(stream=render_pdf(to_form_values(CLAIM)), filetype="pdf") as doc:
        with pymupdf.open() as one:
            one.insert_pdf(doc, from_page=0, to_page=0)
            return one.tobytes()
