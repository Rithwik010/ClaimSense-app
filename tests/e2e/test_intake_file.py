"""P5.1: claim files through POST /v1/claims/intake/file. A digital PDF of a golden case's claim
files the same claim as its JSON and is processed to the case's golden status; a scanned copy is
read by OCR with each field's confidence, kept with the claim (GET /v1/claims/{id}) and processed;
a file that is not a claim is refused."""

import json
import random
import shutil

import pytest

from app.domain.contracts import IntakeClaim
from app.intake.form_codec import to_form_values
from scripts.verify.ocr_accuracy import scanned_pdf
from tests.e2e.support import E2E_CASES, CaseRetriever, StubModel, record_of
from training.generate.forms import render_pdf, render_scan

CASE = E2E_CASES["E2E-14"]


def client_for(api, load_case_reference):  # noqa: ANN001, ANN201
    load_case_reference(CASE)
    answer = CASE["given"]["model_answer"]
    return api(StubModel(json.dumps(answer)), CaseRetriever(CASE))


def test_a_digital_pdf_files_the_same_claim_as_its_json(api, load_case_reference) -> None:  # noqa: ANN001
    client = client_for(api, load_case_reference)
    claim = IntakeClaim.model_validate(CASE["given"]["claim"])

    filed = client.post(
        "/v1/claims/intake/file",
        content=render_pdf(to_form_values(claim)),
        headers={"Content-Type": "application/pdf"},
    )
    processed = client.post(f"/v1/claims/{claim.claim_id}/process")

    assert filed.status_code == 201, filed.text
    assert filed.json()["source_format"] == "DIGITAL_PDF"
    assert IntakeClaim.model_validate(filed.json()["claim"]) == claim
    assert processed.status_code == 200, processed.text
    assert record_of(client, claim.claim_id).status == CASE["expected"]["status_after_processing"]


@pytest.mark.skipif(shutil.which("tesseract") is None, reason="Tesseract is not installed")
def test_a_scanned_form_is_read_with_confidences_and_processed(api, load_case_reference) -> None:  # noqa: ANN001
    client = client_for(api, load_case_reference)
    claim = IntakeClaim.model_validate(CASE["given"]["claim"])
    scan = render_scan(to_form_values(claim), random.Random(5), value_noise_rate=0.0)

    filed = client.post(
        "/v1/claims/intake/file",
        content=scanned_pdf(scan.pages),
        headers={"Content-Type": "application/pdf"},
    )

    assert filed.status_code == 201, filed.text
    assert filed.json()["source_format"] == "SCANNED"
    confidences = filed.json()["field_confidences"]
    assert confidences and all(0.0 <= value <= 1.0 for value in confidences.values())
    shown = client.get(f"/v1/claims/{claim.claim_id}").json()
    assert shown["source_format"] == "SCANNED" and shown["field_confidences"] == confidences
    assert client.post(f"/v1/claims/{claim.claim_id}/process").status_code == 200


def test_a_file_that_is_not_a_claim_is_refused(api, load_case_reference) -> None:  # noqa: ANN001
    client = client_for(api, load_case_reference)

    refused = client.post("/v1/claims/intake/file", content=b"hello")

    assert refused.status_code == 422
    assert "not JSON, a PDF or an image" in refused.json()["detail"]


def test_a_json_file_is_filed_like_a_json_claim(api, load_case_reference) -> None:  # noqa: ANN001
    client = client_for(api, load_case_reference)
    body = json.dumps(CASE["given"]["claim"]).encode()

    filed = client.post("/v1/claims/intake/file", content=body)
    again = client.post("/v1/claims/intake/file", content=body)

    assert filed.status_code == 201 and filed.json()["source_format"] == "JSON"
    assert again.status_code == 409


@pytest.mark.skipif(shutil.which("tesseract") is None, reason="Tesseract is not installed")
def test_a_scanned_value_that_fails_its_format_check_files_the_claim_for_the_rules(
    api, load_case_reference
) -> None:  # noqa: ANN001
    client = client_for(api, load_case_reference)
    claim = IntakeClaim.model_validate(CASE["given"]["claim"])
    values = to_form_values(claim)
    values["billing_tin"] = "12345678"  # eight digits: fails the tax ID check
    scan = render_scan(values, random.Random(5), value_noise_rate=0.0)

    filed = client.post("/v1/claims/intake/file", content=scanned_pdf(scan.pages))
    processed = client.post(f"/v1/claims/{claim.claim_id}/process")

    assert filed.status_code == 201, filed.text
    assert filed.json()["field_confidences"]["billing_tin"] == 0.0
    assert "billing_tin" not in filed.json()["received"]
    assert any("billing_tin" in error for error in filed.json()["contract_errors"])
    assert processed.json()["status"] == "REJECTED"  # final at once: the provider sees it
    failed = [
        r for r in processed.json()["record"]["rules_outcome"]["rule_results"] if not r["passed"]
    ]
    assert [(r["rule_id"], r["outcome"], r["reason_code"]) for r in failed] == [
        ("R01", "REJECT", "RJ_LOW_CONFIDENCE_FIELD")  # H5: the rule failed on a field read at 0.0
    ]
