"""P5.4 acceptance: the explanation of every golden end-to-end case, after processing and after
the review, through GET /v1/claims/{id}/explanation. Every amount and reason it shows matches the
decision record (tests/explain_support.py), in plain text and in HTML; a FINAL_PENDED claim lists
its processed and awaiting lines (D-REV-7)."""

import json
from typing import Any

import pytest
from sqlalchemy.orm import Session

from app.domain.contracts import DecisionRecord, SourceFormat
from app.workflow.pipeline import intake_claim_data
from scripts.verify.e2e_v2_cases import v2_retriever
from tests.e2e.support import (
    E2E_CASES,
    E2E_V2_CASES,
    FILED_BY_TEST_PROVIDER,
    CaseRetriever,
    StubModel,
    process_record,
    record_of,
)
from tests.explain_support import html_mismatches, mismatches

CASES = [E2E_CASES[k] for k in sorted(E2E_CASES)] + [E2E_V2_CASES[k] for k in sorted(E2E_V2_CASES)]


def explained(client, claim_id: str, record: DecisionRecord) -> str:  # noqa: ANN001
    text = client.get(f"/v1/claims/{claim_id}/explanation", params={"format": "text"})
    html = client.get(f"/v1/claims/{claim_id}/explanation")
    assert text.status_code == 200 and html.status_code == 200
    assert text.headers["content-type"].startswith("text/plain")
    assert html.headers["content-type"].startswith("text/html")
    assert mismatches(record, text.text) == []
    assert html_mismatches(html.text, text.text) == []
    return text.text


@pytest.mark.parametrize("case", CASES, ids=[case["case_id"] for case in CASES])
def test_the_explanation_matches_the_record(
    api, load_case_reference, engine, case: dict[str, Any]
) -> None:  # noqa: ANN001, E501
    given = case["given"]
    load_case_reference(case)
    answer = given.get("model_answer")
    model = StubModel(json.dumps(answer) if answer is not None else "unused")
    v2 = case["case_id"] in E2E_V2_CASES
    client = api(model, v2_retriever(), policy_set="v2") if v2 else api(model, CaseRetriever(case))
    claim = given["claim"]
    claim_id = claim["claim_id"]
    if given["source_format"] == "JSON":
        assert client.post("/v1/claims/intake", json=claim).status_code == 201
    else:
        with Session(engine) as session:
            intake_claim_data(
                session,
                claim,
                given["field_confidences"],
                SourceFormat(given["source_format"]),
                0.85,
                **FILED_BY_TEST_PROVIDER,
            )
    assert client.get(f"/v1/claims/{claim_id}/explanation").status_code == 404

    processed = client.post(f"/v1/claims/{claim_id}/process")
    assert processed.status_code == 200, processed.text
    explained(client, claim_id, record_of(client, claim_id))
    action = given.get("review_action")
    if action is None:
        return

    reviewed = client.post(f"/v1/claims/{claim_id}/review", json=action)
    assert reviewed.status_code == 200, reviewed.text
    final = DecisionRecord.model_validate(reviewed.json())
    text = explained(client, claim_id, final)
    assert f"Reviewer: {action['reviewer_id']}" in text
    if final.status.value == "FINAL_PENDED":
        assert "Lines awaiting documentation" in text


def test_an_unknown_claim_has_no_explanation(api) -> None:  # noqa: ANN001
    client = api(StubModel("unused"), CaseRetriever(E2E_CASES[sorted(E2E_CASES)[0]]))

    assert client.get("/v1/claims/CLM-NOPE-00000/explanation").status_code == 404


def test_a_met_quote_not_in_the_notes_pends_the_line_and_is_explained(  # D-EVID-1
    api, load_case_reference
) -> None:  # noqa: ANN001
    import copy

    case = copy.deepcopy(E2E_CASES["E2E-15"])
    answer = case["given"]["model_answer"]
    met = next(c for c in answer["lines"][0]["criteria"] if c["status"] == "MET")
    met["evidence"] = "A sentence the clinical notes do not contain."
    load_case_reference(case)
    client = api(StubModel(json.dumps(answer)), CaseRetriever(case))
    claim_id = case["given"]["claim"]["claim_id"]
    assert client.post("/v1/claims/intake", json=case["given"]["claim"]).status_code == 201

    record = process_record(client, claim_id)
    text = explained(client, claim_id, record)

    assert record.output_errors == [f"EVIDENCE_NOT_IN_NOTES: line 1 {met['criterion_id']}"]
    assert record.line_decisions[0].decision.value == "PEND"  # MET counted as not documented
    assert record.slm_output.lines[0].criteria[0].status.value == "MET"  # the model's answer kept
    assert "Evidence checks" in text and "could not be used" not in text
    assert "met per the model, counted as not documented" in text
