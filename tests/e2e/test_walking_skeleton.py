"""P1.5 walking skeleton, end to end through the API with the model stubbed.

Golden cases the skeleton covers: E2E-14 (office visit approved, QUICK review) and E2E-05 (not
eligible, R05 DENY). Each claim goes in through POST /v1/claims/intake and is processed through
POST /v1/claims/{id}/process on a fresh database. Expected values are the golden ones; the review
and finalization parts of the cases are checked in P5.6.
"""

import json
from typing import Any

from sqlalchemy import Engine, delete, func, select
from sqlalchemy.orm import Session

from app.calculator import CALCULATOR_VERSION
from app.db.models import FeeScheduleEntry, Plan
from app.db.seed import seed_curated, upsert
from app.domain.contracts import DecisionRecord
from app.ml.client import ModelUnavailable
from app.ml.prompt import PROMPT_VERSION, system_prompt
from app.rules import SKELETON_RULES_VERSION
from tests.e2e.support import E2E_CASES, StubModel, golden_fee_rows


def line_decisions(record: DecisionRecord) -> list[dict[str, Any]]:
    return [
        d.model_dump(mode="json", include={"line_no", "decision", "source", "reason_codes"})
        for d in record.line_decisions
    ]


def audit_types(client, claim_id: str) -> list[str]:
    response = client.get(f"/v1/claims/{claim_id}/audit")
    assert response.status_code == 200
    return [event["event_type"] for event in response.json()]


def test_office_visit_runs_end_to_end(api, load_case_reference) -> None:
    case = E2E_CASES["E2E-14"]
    load_case_reference(case)
    model = StubModel(json.dumps(case["given"]["model_answer"]))
    client = api(model)
    claim = case["given"]["claim"]
    claim_id = claim["claim_id"]

    received = client.post("/v1/claims/intake", json=claim)
    processed = client.post(f"/v1/claims/{claim_id}/process")

    assert received.status_code == 201
    assert received.json()["source_format"] == "JSON"
    assert processed.status_code == 200, processed.text
    record = DecisionRecord.model_validate(processed.json())
    expected = case["expected"]
    recommendation = expected["recommendation"]
    assert record.status.value == expected["status_after_processing"]
    assert record.rules_outcome.claim_outcome.value == expected["rules"]["claim_outcome"]
    assert [o.model_dump(mode="json") for o in record.rules_outcome.line_outcomes] == expected[
        "rules"
    ]["line_outcomes"]
    assert record.output_errors == []
    assert line_decisions(record) == recommendation["line_decisions"]
    assert record.claim_decision.value == recommendation["claim_decision"]
    assert record.review_tier.value == recommendation["review_tier"]
    assert record.amounts.model_dump() == recommendation["amounts"]
    assert record.versions.model_dump() == {
        "rules_version": SKELETON_RULES_VERSION,
        "model_name": "stub-model",
        "prompt_version": PROMPT_VERSION,
        "policy_versions": {},
    }
    assert record.context_refs.lines[0].candidate_benefits[0].benefit_category == "OFFICE_VISIT_PCP"

    [(system, user)] = model.prompts
    assert system == system_prompt()
    assert "LINES TO DECIDE: 1" in user
    assert claim["patient"]["last_name"] not in user  # no patient name in the prompt

    view = client.get(f"/v1/claims/{claim_id}").json()
    assert view["status"] == "AWAITING_REVIEW"
    assert DecisionRecord.model_validate(view["record"]) == record
    assert audit_types(client, claim_id) == [
        "INTAKE_COMPLETED",
        "RULES_EVALUATED",
        "CONTEXT_ASSEMBLED",
        "SLM_RECOMMENDED",
        "CALCULATED",
    ]
    events = client.get(f"/v1/claims/{claim_id}/audit").json()
    payloads = json.dumps([e["payload"] for e in events])
    assert claim["patient"]["last_name"] not in payloads
    assert claim["clinical_notes"][:30] not in payloads
    assert events[-1]["payload"]["calculator_version"] == CALCULATOR_VERSION


def test_ineligible_member_is_denied_by_rule_without_the_model(api, load_case_reference) -> None:
    case = E2E_CASES["E2E-05"]
    load_case_reference(case)
    model = StubModel("unused")
    client = api(model)
    claim_id = case["given"]["claim"]["claim_id"]

    client.post("/v1/claims/intake", json=case["given"]["claim"])
    processed = client.post(f"/v1/claims/{claim_id}/process")

    assert processed.status_code == 200, processed.text
    record = DecisionRecord.model_validate(processed.json())
    assert record.status.value == case["expected"]["status_after_processing"]
    assert record.rules_outcome.claim_outcome.value == case["expected"]["rules"]["claim_outcome"]
    assert [
        r.model_dump(mode="json", include={"rule_id", "outcome", "reason_code", "line_no"})
        for r in record.rules_outcome.rule_results
        if not r.passed
    ] == case["expected"]["rules"]["failures"]
    assert record.slm_output is None and record.amounts is None and record.review_tier is None
    assert model.prompts == []
    assert audit_types(client, claim_id) == ["INTAKE_COMPLETED", "RULES_EVALUATED", "AUTO_OUTCOME"]


def new_claim(case_id: str, claim_id: str) -> dict[str, Any]:
    return {**E2E_CASES[case_id]["given"]["claim"], "claim_id": claim_id}


def test_a_calculation_error_sends_the_claim_to_full_review(
    api, load_case_reference, engine: Engine
) -> None:
    """P2.4: an approved line whose code has no fee cannot be calculated. The claim is not lost:
    CALCULATION_FAILED is audited with the error and the claim waits for FULL review, with the
    reason in the decision record and no amounts."""
    case = E2E_CASES["E2E-14"]
    load_case_reference(case)
    claim = new_claim("E2E-14", "CLM-CALC-FAILED")
    code = claim["service_lines"][0]["procedure_code"]
    with Session(engine) as session:
        session.execute(delete(FeeScheduleEntry).where(FeeScheduleEntry.procedure_code == code))
        session.commit()
    try:
        client = api(StubModel(json.dumps(case["given"]["model_answer"])))
        client.post("/v1/claims/intake", json=claim)
        processed = client.post("/v1/claims/CLM-CALC-FAILED/process")
    finally:
        with Session(engine) as session:
            upsert(session, FeeScheduleEntry, golden_fee_rows())
            session.commit()

    assert processed.status_code == 200, processed.text
    record = DecisionRecord.model_validate(processed.json())
    error = f"line 1: no fee for {code}"
    assert record.status.value == "AWAITING_REVIEW"
    assert record.review_tier.value == "FULL"
    assert record.amounts is None
    assert record.output_errors == [f"CALCULATION_FAILED: {error}"]
    assert line_decisions(record) == case["expected"]["recommendation"]["line_decisions"]
    events = client.get("/v1/claims/CLM-CALC-FAILED/audit").json()
    assert [e["event_type"] for e in events] == [
        "INTAKE_COMPLETED",
        "RULES_EVALUATED",
        "CONTEXT_ASSEMBLED",
        "SLM_RECOMMENDED",
        "CALCULATION_FAILED",
    ]
    assert events[-1]["payload"] == {"error": error, "calculator_version": CALCULATOR_VERSION}


def test_invalid_model_output_pends_the_claim_for_full_review(api, load_case_reference) -> None:
    load_case_reference(E2E_CASES["E2E-14"])
    client = api(StubModel("The visit looks fine to me."))
    claim = new_claim("E2E-14", "CLM-SKEL-INVALID")

    client.post("/v1/claims/intake", json=claim)
    record = DecisionRecord.model_validate(
        client.post("/v1/claims/CLM-SKEL-INVALID/process").json()
    )

    assert record.status.value == "AWAITING_REVIEW"
    assert record.slm_output is None
    assert record.output_errors and "does not parse as SLMOutput" in record.output_errors[0]
    assert line_decisions(record) == [
        {
            "line_no": 1,
            "decision": "PEND",
            "source": "VALIDATION",
            "reason_codes": ["MODEL_OUTPUT_INVALID"],
        }
    ]
    assert record.claim_decision.value == "PEND"
    assert record.review_tier.value == "FULL"
    assert record.amounts.totals.billed_cents == 23600
    assert record.amounts.totals.allowed_cents == 0
    assert "OUTPUT_INVALID" in audit_types(client, "CLM-SKEL-INVALID")


def test_request_errors(api, load_case_reference) -> None:
    case = E2E_CASES["E2E-14"]
    load_case_reference(case)
    client = api(StubModel(json.dumps(case["given"]["model_answer"])))
    claim = new_claim("E2E-14", "CLM-SKEL-ERRORS")

    assert client.post("/v1/claims/intake", json=claim).status_code == 201
    assert client.post("/v1/claims/intake", json=claim).status_code == 409
    assert client.post("/v1/claims/CLM-SKEL-ERRORS/process").status_code == 200
    assert client.post("/v1/claims/CLM-SKEL-ERRORS/process").status_code == 409
    assert client.post("/v1/claims/CLM-NOPE/process").status_code == 404
    assert client.get("/v1/claims/CLM-NOPE").status_code == 404
    assert client.get("/v1/claims/CLM-NOPE/audit").status_code == 404
    assert client.post("/v1/claims/intake", json={"claim_id": "x"}).status_code == 422


def test_unsupported_claim_stays_received_with_only_the_intake_event(api) -> None:
    client = api(StubModel("unused"))
    claim = new_claim("E2E-14", "CLM-SKEL-UNKNOWN")
    claim["member_id"] = "MBR-NOT-LOADED"

    client.post("/v1/claims/intake", json=claim)
    response = client.post("/v1/claims/CLM-SKEL-UNKNOWN/process")

    assert response.status_code == 422
    assert "R04" in response.json()["detail"]
    assert client.get("/v1/claims/CLM-SKEL-UNKNOWN").json()["status"] == "RECEIVED"
    assert audit_types(client, "CLM-SKEL-UNKNOWN") == ["INTAKE_COMPLETED"]


def test_model_unavailable_returns_503_and_the_claim_can_run_later(api, load_case_reference):
    case = E2E_CASES["E2E-14"]
    load_case_reference(case)

    class DownModel(StubModel):
        def complete(self, system: str, user: str) -> str:
            raise ModelUnavailable("model stub-model unavailable (ConnectError)")

    claim = new_claim("E2E-14", "CLM-SKEL-DOWN")
    down = api(DownModel("unused"))
    down.post("/v1/claims/intake", json=claim)

    assert down.post("/v1/claims/CLM-SKEL-DOWN/process").status_code == 503
    assert audit_types(down, "CLM-SKEL-DOWN") == ["INTAKE_COMPLETED"]

    up = api(StubModel(json.dumps(case["given"]["model_answer"])))
    assert up.post("/v1/claims/CLM-SKEL-DOWN/process").status_code == 200


def test_seeding_again_is_safe(engine: Engine) -> None:
    with Session(engine) as session:
        seed_curated(session)
        session.commit()
        assert session.scalar(select(func.count()).select_from(Plan)) == 5


def test_retrieved_criteria_reach_the_prompt_and_the_record(api, load_case_reference) -> None:
    from datetime import date

    from app.domain.contracts import RetrievedCriterion
    from tests.e2e.support import StubRetriever

    case = E2E_CASES["E2E-14"]
    load_case_reference(case)
    criterion = RetrievedCriterion(
        criterion_id="POL-BH-001.c1",
        policy_id="POL-BH-001",
        policy_title="Psychological and neuropsychological testing",
        text="Testing is covered when ...",
        source="LCD L34520 v32, Indications.",
        effective_date=date(2026, 1, 1),
    )
    answer = json.loads(json.dumps(case["given"]["model_answer"]))
    answer["lines"][0]["criteria"] = [
        {
            "criterion_id": "POL-BH-001.c1",
            "status": "NOT_APPLICABLE",
            "evidence": "Does not apply to this service.",
        }
    ]
    model, retriever = StubModel(json.dumps(answer)), StubRetriever([criterion])
    client = api(model, retriever)
    claim = new_claim("E2E-14", "CLM-SKEL-RAG")

    client.post("/v1/claims/intake", json=claim)
    record = DecisionRecord.model_validate(client.post("/v1/claims/CLM-SKEL-RAG/process").json())

    assert retriever.queries[0].startswith("Office visit")
    assert claim["clinical_notes"] in retriever.queries[0]
    assert "[POL-BH-001.c1]" in model.prompts[0][1]
    assert record.output_errors == [] and record.claim_decision.value == "APPROVE"
    assert record.context_refs.lines[0].criteria == [criterion]
    assert record.versions.policy_versions == {"POL-BH-001": "2026-01-01"}


def test_retrieval_unavailable_returns_503(api, load_case_reference) -> None:
    from app.rag.retrieve import RetrievalUnavailable
    from tests.e2e.support import StubRetriever

    class DownRetriever(StubRetriever):
        def retrieve(self, query, plan_id, day, procedure_code=None, exclude_policies=()):  # noqa: ANN001, ANN201
            raise RetrievalUnavailable("retrieval unavailable (ConnectError)")

    load_case_reference(E2E_CASES["E2E-14"])
    client = api(StubModel("unused"), DownRetriever())
    client.post("/v1/claims/intake", json=new_claim("E2E-14", "CLM-SKEL-NORAG"))

    assert client.post("/v1/claims/CLM-SKEL-NORAG/process").status_code == 503
    assert client.get("/v1/claims/CLM-SKEL-NORAG").json()["status"] == "RECEIVED"
