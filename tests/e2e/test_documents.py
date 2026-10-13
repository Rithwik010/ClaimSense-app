"""D-DOC-1: the original claim file, kept with the claim it creates and served back by
GET /v1/claims/{id}/document: to the provider who filed it (another provider's is 404), to every
reviewer and admin, never without a session (401); inline, with its own content type and nosniff;
byte for byte what was uploaded (its SHA-256). A file refused at upload keeps nothing, a TIFF
scan is read but not kept, and `make demo-reset` deletes every stored file."""

import hashlib
import io
import json
import random
import shutil

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
    shown = client.get(f"/v1/claims/{CLAIM_ID}", headers=PROVIDER).json()["document"]
    assert shown == {
        "file_name": "my claim _01.json",
        "content_type": "application/json",
        "size_bytes": len(body),
    }
    assert client.get(f"/v1/claims/{CLAIM_ID}", headers=REVIEWER).json()["document"] == shown


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
    name = client.get(f"/v1/claims/{CLAIM_ID}", headers=REVIEWER).json()["document"]["file_name"]
    assert name == f"{CLAIM_ID}{'.png' if kind == 'PNG' else '.jpg'}"  # no name sent


@TESSERACT
def test_a_tiff_scan_is_read_but_not_kept(api, load_case_reference, engine) -> None:  # noqa: ANN001
    client = client_for(api, load_case_reference)

    filed = client.post("/v1/claims/intake/file", content=scan_page("TIFF"))

    assert filed.status_code == 201, filed.text
    assert client.get(f"/v1/claims/{CLAIM_ID}/document").status_code == 404
    assert client.get(f"/v1/claims/{CLAIM_ID}").json()["document"] is None
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
