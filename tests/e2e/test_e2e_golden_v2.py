"""Policies v2, checkpoint 4 (D-GOLD-8, D-GOLD-9): the golden end-to-end claims on policy set v2.

- The 21 v1 cases that cite no retired criterion run on policy set v2 with the same expected
  values: the criteria they cite are kept in v2 with the same IDs and texts.
- The v2 versions of the other 10 (tests/golden/e2e_v2/cases.json) run on policy set v2 with the
  real exact lookup (in-memory Qdrant built from the v2 files). Their expected values are
  engine-derived (scripts/verify/e2e_v2_cases.py), so this test guards against unnoticed change.
"""

import json
from typing import Any

import pytest
from sqlalchemy.orm import Session

from app.domain.contracts import DecisionRecord, SourceFormat
from app.workflow.pipeline import intake_claim_data
from scripts.verify.e2e_v2_cases import cases_to_version, v2_retriever
from tests.e2e.support import (
    E2E_CASES,
    E2E_V2_CASES,
    FILED_BY_TEST_PROVIDER,
    CaseRetriever,
    StubModel,
    audit,
    record_of,
)
from tests.e2e.test_e2e_golden import differences, final_differences, stored_accumulators

VERSIONED = {case["case_id"] for case in cases_to_version()}
UNCHANGED = [E2E_CASES[k] for k in sorted(E2E_CASES) if k not in VERSIONED]
V2 = [E2E_V2_CASES[k] for k in sorted(E2E_V2_CASES)]


def run(api, load_case_reference, engine, case: dict[str, Any], retriever) -> None:  # noqa: ANN001
    given = case["given"]
    load_case_reference(case)
    answer = given.get("model_answer")
    model = StubModel(json.dumps(answer) if answer is not None else "unused")
    client = api(model, retriever, policy_set="v2")
    claim = given["claim"]
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

    response = client.post(f"/v1/claims/{claim['claim_id']}/process")

    assert response.status_code == 200, response.text
    record = record_of(client, claim["claim_id"])
    assert differences(record, case["expected"]) == [], record.output_errors
    if record.context_refs is not None:
        context = next(
            e for e in audit(client, claim["claim_id"]) if e["event_type"] == "CONTEXT_ASSEMBLED"
        )
        assert context["payload"]["policy_set"] == "v2"
        assert all(v.startswith("v2@") for v in record.versions.policy_versions.values())
    action = given.get("review_action")
    if action is None:
        return
    reviewed = client.post(f"/v1/claims/{claim['claim_id']}/review", json=action)
    assert reviewed.status_code == 200, reviewed.text
    final = DecisionRecord.model_validate(reviewed.json())
    events = audit(client, claim["claim_id"])
    finalized = next(e for e in reversed(events) if e["event_type"] == "FINALIZED")
    assert events[-1]["event_type"] == "EXPLANATION_BUILT"  # of the final record
    stored = stored_accumulators(engine, claim["member_id"], finalized["payload"])
    assert final_differences(final, finalized["payload"], stored, case["expected"]["final"]) == []


def test_the_cases_split_into_21_unchanged_and_10_versioned() -> None:
    assert len(UNCHANGED) == 21 and len(V2) == 10
    assert {case["v1_case"] for case in V2} == VERSIONED


@pytest.mark.parametrize("case", UNCHANGED, ids=[case["case_id"] for case in UNCHANGED])
def test_unchanged_case_gives_the_same_results_on_v2(
    api, load_case_reference, engine, case
) -> None:  # noqa: ANN001
    run(api, load_case_reference, engine, case, CaseRetriever(case, "v2"))


@pytest.mark.parametrize("case", V2, ids=[case["case_id"] for case in V2])
def test_v2_version_through_the_exact_lookup(api, load_case_reference, engine, case) -> None:  # noqa: ANN001
    run(api, load_case_reference, engine, case, v2_retriever())
