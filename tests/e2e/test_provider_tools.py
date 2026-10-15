"""The provider's tools before processing and the request ID (D-FIX-1, D-CHK-1, D-OBS-1).

- A claim read from a digital PDF with a misread billing NPI: the check says it would be rejected
  for a box read unclearly and names the box; the provider corrects it (the box as the form prints
  it); FIELD_CORRECTED records the box, its confidence before and the text before and after, with
  the provider as actor; the box is then provider-entered (confidence 1.0); the check says the
  claim is ready, and processing sends it to review like the same claim filed as JSON.
- Refused corrections change nothing: a box that cannot be corrected, a value that fails its
  format check, a JSON claim, a processed claim.
- Every response carries an X-Request-ID, which the audit events it wrote keep; the rules event
  names the reference data versions.
"""

import json
import re

import pytest
from sqlalchemy.orm import Session

from app.db.models import Claim
from app.domain.contracts import IntakeClaim
from app.intake.form_codec import to_form_values
from tests.e2e.support import (
    E2E_CASES,
    PROVIDER,
    REVIEWER,
    CaseRetriever,
    StubModel,
    audit,
)
from training.generate.forms import render_pdf

CASE = E2E_CASES["E2E-14"]  # clean claim, awaiting QUICK review after processing
CLAIM = CASE["given"]["claim"]
CLAIM_ID = CLAIM["claim_id"]
NPI = CLAIM["billing_npi"]
MISREAD = NPI[:-1] + str((int(NPI[-1]) + 1) % 10)  # one digit off: fails the check digit
HEX = re.compile(r"^[0-9a-f]{32}$")


def client_for(api, load_case_reference):  # noqa: ANN001, ANN201
    load_case_reference(CASE)
    return api(StubModel(json.dumps(CASE["given"]["model_answer"])), CaseRetriever(CASE))


def file_misread_pdf(client) -> dict:  # noqa: ANN001
    """The case's claim as a digital PDF whose billing NPI box holds a misread number."""
    values = to_form_values(IntakeClaim.model_validate(CLAIM))
    values["billing_npi"] = MISREAD
    filed = client.post(
        "/v1/claims/intake/file",
        content=render_pdf(values),
        headers={**PROVIDER, "X-File-Name": "claim.pdf"},
    )
    assert filed.status_code == 201, filed.text
    return filed.json()


def form_of(client) -> dict:  # noqa: ANN001
    return client.get(f"/v1/claims/{CLAIM_ID}/form", headers=PROVIDER).json()


def box(form: dict, field: str) -> dict:
    return next(b for b in form["boxes"] if b["field"] == field)


def correct(client, field: str, value: str):  # noqa: ANN001, ANN201
    return client.post(
        f"/v1/claims/{CLAIM_ID}/corrections",
        json={"corrections": [{"field": field, "value": value}]},
        headers=PROVIDER,
    )


def test_a_misread_box_is_checked_corrected_and_audited(api, load_case_reference) -> None:  # noqa: ANN001
    client = client_for(api, load_case_reference)
    filed = file_misread_pdf(client)
    assert filed["field_confidences"]["billing_npi"] == 0.0

    form = form_of(client)
    assert form["correctable"] is True and form["source_format"] == "DIGITAL_PDF"
    assert box(form, "billing_npi") | {"confidence": None} == {
        "field": "billing_npi",
        "text": MISREAD,
        "confidence": None,
        "correctable": True,
        "corrected": False,
    }
    assert box(form, "claim_id")["correctable"] is False
    assert box(form, "clinical_notes")["correctable"] is False

    check = client.get(f"/v1/claims/{CLAIM_ID}/check", headers=PROVIDER).json()
    assert check["outcome"] == "REJECTED"
    assert check["heading"] == "The claim would be rejected"
    [problem] = check["problems"]
    assert problem["fields"] == ["billing_npi"]  # the box at fault, not every NPI the rule read
    assert "could not be read clearly" in problem["text"]
    assert f"Billing provider NPI, read as: {MISREAD}" in problem["checks"]
    assert check["coverage"] is None  # the rules stop the claim, so no criteria are looked up

    response = correct(client, "billing_npi", f" {NPI} ")

    assert response.status_code == 200, response.text
    corrected = box(response.json(), "billing_npi")
    assert (corrected["text"], corrected["confidence"], corrected["corrected"]) == (NPI, 1.0, True)
    assert response.json()["contract_errors"] == []
    events = audit(client, CLAIM_ID)
    event = events[-1]
    assert (event["event_type"], event["actor"]) == ("FIELD_CORRECTED", "provider-test")
    assert event["payload"]["fields"] == [
        {"field": "billing_npi", "confidence_before": 0.0, "before": MISREAD, "after": NPI}
    ]
    assert event["request_id"] == response.headers["X-Request-ID"]
    assert HEX.match(event["request_id"])

    check = client.get(f"/v1/claims/{CLAIM_ID}/check", headers=PROVIDER).json()
    assert check["outcome"] == "READY" and check["problems"] == []
    assert [line["line_no"] for line in check["coverage"]] == [1]
    assert len(audit(client, CLAIM_ID)) == len(events)  # the check writes nothing

    processed = client.post(f"/v1/claims/{CLAIM_ID}/process", headers=PROVIDER)
    assert processed.status_code == 200, processed.text
    assert processed.json()["status"] == "IN_REVIEW"
    view = client.get(f"/v1/claims/{CLAIM_ID}", headers=REVIEWER).json()
    assert view["record"]["review_tier"] == CASE["expected"]["recommendation"]["review_tier"]
    assert correct(client, "billing_npi", NPI).status_code == 409  # processed: no more corrections
    assert form_of(client)["correctable"] is False


def test_a_patient_box_is_corrected_without_its_text_in_the_audit_trail(
    api, load_case_reference
) -> None:  # noqa: ANN001
    client = client_for(api, load_case_reference)
    file_misread_pdf(client)

    response = correct(client, "patient.address.city", "Springfield")

    assert response.status_code == 200, response.text
    fields = audit(client, CLAIM_ID)[-1]["payload"]["fields"]
    assert fields == [{"field": "patient.address.city", "confidence_before": 1.0}]
    assert "Springfield" not in json.dumps(audit(client, CLAIM_ID))


@pytest.mark.parametrize(
    ("field", "value", "detail"),
    [
        ("claim_id", "CLM-NEW", "Claim control number: this box cannot be corrected"),
        ("clinical_notes", "More notes", "Clinical notes: this box cannot be corrected"),
        ("billing_npi", "1234567890", "Billing provider NPI: enter a 10-digit NPI"),
        ("service_lines.0.date_of_service", "2026-13-01", "Date of service on line 1: enter"),
        ("member_id", "", "a claim needs a member_id"),
    ],
)
def test_a_refused_correction_changes_nothing(
    api, load_case_reference, engine, field: str, value: str, detail: str
) -> None:  # noqa: ANN001
    client = client_for(api, load_case_reference)
    file_misread_pdf(client)
    with Session(engine) as session:
        before = dict(session.get(Claim, CLAIM_ID).intake)
    events = len(audit(client, CLAIM_ID))

    response = correct(client, field, value)

    assert response.status_code == 422, response.text
    assert response.json()["detail"].startswith(detail)
    with Session(engine) as session:
        assert session.get(Claim, CLAIM_ID).intake == before
    assert len(audit(client, CLAIM_ID)) == events


def test_a_json_claim_has_nothing_to_correct(api, load_case_reference) -> None:  # noqa: ANN001
    client = client_for(api, load_case_reference)
    assert client.post("/v1/claims/intake", json=CLAIM, headers=PROVIDER).status_code == 201

    response = correct(client, "billing_npi", NPI)

    assert response.status_code == 409
    assert "read exactly" in response.json()["detail"]
    assert form_of(client)["correctable"] is False


def test_every_response_and_audit_event_carries_its_request_id(api, load_case_reference) -> None:  # noqa: ANN001
    client = client_for(api, load_case_reference)
    filed = client.post("/v1/claims/intake", json=CLAIM, headers=PROVIDER)
    processed = client.post(f"/v1/claims/{CLAIM_ID}/process", headers=PROVIDER)
    health = client.get("/health")

    ids = [r.headers["X-Request-ID"] for r in (filed, processed, health)]
    assert all(HEX.match(i) for i in ids) and len(set(ids)) == 3
    events = audit(client, CLAIM_ID)
    assert events[0]["request_id"] == ids[0]  # INTAKE_COMPLETED
    assert {e["request_id"] for e in events[1:]} == {ids[1]}  # everything processing wrote
    rules = next(e for e in events if e["event_type"] == "RULES_EVALUATED")
    reference = rules["payload"]["reference_data"]
    assert re.match(r"^[0-9a-f]{12}$", reference["curated"])
    assert set(reference["tables"]) >= {"icd10_codes", "ncci_ptp_edits", "procedure_codes"}
    assert all(re.match(r"^[0-9a-f]{12}$", v) for v in reference["tables"].values())
