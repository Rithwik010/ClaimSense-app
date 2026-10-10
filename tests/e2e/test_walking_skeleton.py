"""The pipeline end to end through the API with the model stubbed (P1.5 walking skeleton; the full
v1 rules engine since P2.5, the full calculator since P2.4).

Golden cases used here: E2E-14 (office visit approved, QUICK review), E2E-05 (not eligible, R05
DENY) and E2E-15. Each claim goes in through POST /v1/claims/intake and is processed through
POST /v1/claims/{id}/process on a fresh database. Expected values are the golden ones; every
golden end-to-end case runs in test_e2e_golden.py.
"""

import copy
import json
from typing import Any

import pytest
from sqlalchemy import Engine, delete, func, select
from sqlalchemy.orm import Session

from app.calculator import CALCULATOR_VERSION
from app.calculator.engine import CalculationError
from app.db.models import FeeScheduleEntry, Member, Plan, ProviderNetwork
from app.db.seed import seed_curated, upsert
from app.domain.contracts import DecisionRecord, IntakeClaim, Network
from app.ml.client import ModelUnavailable
from app.ml.prompt import PROMPT_VERSION, system_prompt
from app.rules import RULES_VERSION
from app.workflow.pipeline import _calculate
from tests.e2e.support import E2E_CASES, StubModel, audit, e2e_fee_rows


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
        "rules_version": RULES_VERSION,
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
    """A copy of a golden case's claim under a new claim ID (deep: tests change lines)."""
    return {**copy.deepcopy(E2E_CASES[case_id]["given"]["claim"]), "claim_id": claim_id}


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
            upsert(session, FeeScheduleEntry, e2e_fee_rows())
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


def test_out_of_network_care_on_a_plan_without_out_of_network_cover_is_denied_by_r08(
    api, load_case_reference, engine: Engine
) -> None:
    """P2.5: with the full rules engine, R08 denies out-of-network care on a plan that does not
    cover it (EPO) before the claim reaches the model or the calculator. (In P2.4, without R08,
    such a claim reached the calculator; that guard is checked directly below.)"""
    case = E2E_CASES["E2E-15"]
    load_case_reference(case)
    claim = new_claim("E2E-15", "CLM-RULE-OON")
    with Session(engine) as session:
        session.get(ProviderNetwork, (claim["billing_npi"], "PLN-EPO")).in_network = False
        session.commit()
    model = StubModel(json.dumps(case["given"]["model_answer"]))
    client = api(model)

    client.post("/v1/claims/intake", json=claim)
    processed = client.post("/v1/claims/CLM-RULE-OON/process")

    assert processed.status_code == 200, processed.text
    record = DecisionRecord.model_validate(processed.json())
    assert record.status.value == "DENIED_BY_RULE"
    assert [
        (r.rule_id, r.reason_code) for r in record.rules_outcome.rule_results if not r.passed
    ] == [("R08", "DN_OUT_OF_NETWORK")]
    assert audit_types(client, "CLM-RULE-OON") == [
        "INTAKE_COMPLETED",
        "RULES_EVALUATED",
        "AUTO_OUTCOME",
    ]
    assert model.prompts == []


def test_the_calculator_guard_for_a_plan_without_out_of_network_terms(
    load_case_reference, engine: Engine
) -> None:
    """P2.4: should out-of-network care on a plan without out-of-network terms ever reach the
    calculation, it is a CalculationError (CALCULATION_FAILED, FULL review), not a crash."""
    case = E2E_CASES["E2E-15"]
    load_case_reference(case)
    claim = IntakeClaim.model_validate(case["given"]["claim"])
    with Session(engine) as session:
        member = session.get(Member, claim.member_id)
        with pytest.raises(CalculationError, match="plan PLN-EPO has no out-of-network terms"):
            _calculate(session, claim, member, Network.OUT_OF_NETWORK, [])


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
    no_member = {key: value for key, value in claim.items() if key != "member_id"}
    assert client.post("/v1/claims/intake", json=no_member).status_code == 422
    zero_units = {**claim, "claim_id": "CLM-SKEL-UNITS"}
    zero_units["service_lines"] = [{**claim["service_lines"][0], "units": 0}]
    refused = client.post("/v1/claims/intake", json=zero_units)
    assert refused.status_code == 422 and "units" in refused.json()["detail"]
    assert client.get("/v1/claims/CLM-SKEL-UNITS").status_code == 404  # nothing filed


def test_an_unknown_member_is_rejected_by_r04_without_the_model(api) -> None:
    model = StubModel("unused")
    client = api(model)
    claim = new_claim("E2E-14", "CLM-SKEL-UNKNOWN")
    claim["member_id"] = "MBR-NOT-LOADED"

    client.post("/v1/claims/intake", json=claim)
    response = client.post("/v1/claims/CLM-SKEL-UNKNOWN/process")

    assert response.status_code == 200, response.text
    record = DecisionRecord.model_validate(response.json())
    assert record.status.value == "REJECTED"
    assert [
        (r.rule_id, r.reason_code) for r in record.rules_outcome.rule_results if not r.passed
    ] == [("R04", "RJ_MEMBER_NOT_FOUND")]
    assert audit_types(client, "CLM-SKEL-UNKNOWN") == [
        "INTAKE_COMPLETED",
        "RULES_EVALUATED",
        "AUTO_OUTCOME",
    ]
    assert model.prompts == []


def test_a_claim_failing_the_contract_is_filed_and_rejected_by_the_rules(
    api, load_case_reference
) -> None:
    """P2.5 decision 3: the contract errors go into INTAKE_COMPLETED, R01 rejects the claim, and it
    never reaches context or the model."""
    case = E2E_CASES["E2E-14"]
    load_case_reference(case)
    model = StubModel(json.dumps(case["given"]["model_answer"]))
    client = api(model)
    claim = new_claim("E2E-14", "CLM-SKEL-CONTRACT")
    del claim["service_lines"][0]["procedure_code"]

    received = client.post("/v1/claims/intake", json=claim)
    processed = client.post("/v1/claims/CLM-SKEL-CONTRACT/process")

    errors = ["R01: Required field missing: service_lines.0.procedure_code."]
    assert received.status_code == 201
    assert received.json() == {
        "claim_id": "CLM-SKEL-CONTRACT",
        "status": "RECEIVED",
        "source_format": "JSON",
        "contract_errors": errors,
    }
    assert processed.status_code == 200, processed.text
    record = DecisionRecord.model_validate(processed.json())
    assert record.status.value == "REJECTED"
    assert [
        (r.rule_id, r.reason_code) for r in record.rules_outcome.rule_results if not r.passed
    ] == [("R01", "RJ_MISSING_FIELD")]
    events = client.get("/v1/claims/CLM-SKEL-CONTRACT/audit").json()
    assert [e["event_type"] for e in events] == [
        "INTAKE_COMPLETED",
        "RULES_EVALUATED",
        "AUTO_OUTCOME",
    ]
    assert events[0]["payload"]["contract_errors"] == errors
    assert events[-1]["payload"] == {"status": "REJECTED", "reason_codes": ["RJ_MISSING_FIELD"]}
    assert model.prompts == []
    view = client.get("/v1/claims/CLM-SKEL-CONTRACT").json()
    assert view["intake"] is None and "procedure_code" not in view["received"]["service_lines"][0]


def test_a_date_of_service_before_fy2027_leaves_the_claim_received_with_a_503(
    api, load_case_reference
) -> None:
    """P2.5 decision 2: only ICD-10-CM FY2027 is loaded, so a date of service before 2026-10-01
    cannot be checked. Nothing is written, the claim stays RECEIVED and can run once FY2026 is
    loaded."""
    case = E2E_CASES["E2E-14"]
    load_case_reference(case)
    model = StubModel(json.dumps(case["given"]["model_answer"]))
    client = api(model)
    claim = new_claim("E2E-14", "CLM-SKEL-FY2026")
    claim["service_lines"][0]["date_of_service"] = "2026-09-15"

    client.post("/v1/claims/intake", json=claim)
    first = client.post("/v1/claims/CLM-SKEL-FY2026/process")
    again = client.post("/v1/claims/CLM-SKEL-FY2026/process")

    for response in (first, again):
        assert response.status_code == 503
        assert response.json()["detail"] == "reference data not loaded: ICD-10-CM FY2026"
    assert client.get("/v1/claims/CLM-SKEL-FY2026").json()["status"] == "RECEIVED"
    assert audit_types(client, "CLM-SKEL-FY2026") == ["INTAKE_COMPLETED"]
    assert model.prompts == []


def test_model_unavailable_returns_503_and_the_claim_can_run_later(api, load_case_reference):
    case = E2E_CASES["E2E-14"]
    load_case_reference(case)

    class DownModel(StubModel):
        def complete(self, system: str, user: str, attempt: int = 1) -> str:
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
    assert record.versions.policy_versions == {"POL-BH-001": "v1@2026-01-01"}
    context_event = next(
        e for e in audit(client, "CLM-SKEL-RAG") if e["event_type"] == "CONTEXT_ASSEMBLED"
    )
    assert context_event["payload"]["policy_set"] == "v1"
    assert context_event["payload"]["knowledge_version"] == "36cfc77305a5"  # model v1 (D-POL-2)


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


class SecondTimeModel(StubModel):
    """Answers `first` on attempt 1 and the stored answer on the retry; records the attempts."""

    def __init__(self, answer: str, first: str) -> None:
        super().__init__(answer)
        self.first = first
        self.attempts: list[int] = []

    def complete(self, system: str, user: str, attempt: int = 1) -> str:
        self.attempts.append(attempt)
        self.prompts.append((system, user))
        return self.first if attempt == 1 else self.answer


def test_an_invalid_first_answer_is_retried_once(api, load_case_reference) -> None:
    """D-DEC-1: one retry with another fixed seed; a valid retry is used."""
    case = E2E_CASES["E2E-14"]
    load_case_reference(case)
    model = SecondTimeModel(json.dumps(case["given"]["model_answer"]), "not json")
    client = api(model)
    claim = new_claim("E2E-14", "CLM-SKEL-RETRY")
    client.post("/v1/claims/intake", json=claim)

    record = DecisionRecord.model_validate(client.post("/v1/claims/CLM-SKEL-RETRY/process").json())

    assert model.attempts == [1, 2]
    assert record.output_errors == [] and record.claim_decision.value == "APPROVE"
    event = next(e for e in audit(client, "CLM-SKEL-RETRY") if e["event_type"] == "SLM_RECOMMENDED")
    assert event["payload"]["attempts"] == 2 and event["payload"]["earlier_errors"][0]
    assert event["payload"]["lines"][0]["derived_decision"] == "APPROVE"


def test_two_invalid_answers_pend_for_full_review(api, load_case_reference) -> None:
    case = E2E_CASES["E2E-14"]
    load_case_reference(case)
    model = SecondTimeModel("still not json", "not json")
    client = api(model)
    client.post("/v1/claims/intake", json=new_claim("E2E-14", "CLM-SKEL-TWICE"))

    record = DecisionRecord.model_validate(client.post("/v1/claims/CLM-SKEL-TWICE/process").json())

    assert model.attempts == [1, 2]
    assert record.review_tier.value == "FULL"
    assert [d.reason_codes for d in record.line_decisions] == [["MODEL_OUTPUT_INVALID"]]
    event = next(e for e in audit(client, "CLM-SKEL-TWICE") if e["event_type"] == "OUTPUT_INVALID")
    assert event["payload"]["attempts"] == 2
