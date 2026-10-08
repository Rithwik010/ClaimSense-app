"""P5.3: the review queue (§8.8) and reviewer access (§8.10: the X-Role header).

Golden end-to-end claims of every tier go through intake and processing: E2E-14 (QUICK), E2E-16
(STANDARD), E2E-19 (FULL) and E2E-05 (DENIED_BY_RULE, never in the queue)."""

import json
from typing import Any

from fastapi.testclient import TestClient

from tests.e2e.support import E2E_CASES, CaseRetriever, StubModel

REVIEWER = {"X-Role": "reviewer"}


def process_cases(api, load_case_reference, case_ids: list[str]) -> TestClient:  # noqa: ANN001
    """Each case through intake and processing with its own stub model; returns the last client."""
    client = None
    for case_id in case_ids:
        case = E2E_CASES[case_id]
        load_case_reference(case)
        answer = case["given"].get("model_answer")
        client = api(StubModel(json.dumps(answer) if answer else "unused"), CaseRetriever(case))
        claim = case["given"]["claim"]
        assert client.post("/v1/claims/intake", json=claim).status_code == 201
        assert client.post(f"/v1/claims/{claim['claim_id']}/process").status_code == 200
    assert client is not None
    return client


def queue(client: TestClient, **params: Any) -> list[dict[str, Any]]:
    response = client.get("/v1/review/queue", params=params, headers=REVIEWER)
    assert response.status_code == 200, response.text
    return response.json()


def test_only_reviewers_and_admins_see_the_queue(api) -> None:  # noqa: ANN001
    client = api(StubModel("unused"))

    assert client.get("/v1/review/queue").status_code == 403
    assert client.get("/v1/review/queue", headers={"X-Role": "provider"}).status_code == 403
    assert client.get("/v1/review/queue", headers={"X-Role": "nobody"}).status_code == 403
    assert client.get("/v1/review/queue", headers=REVIEWER).status_code == 200
    assert client.get("/v1/review/queue", headers={"X-Role": "admin"}).status_code == 200


def test_the_queue_lists_claims_awaiting_review_by_tier(api, load_case_reference) -> None:  # noqa: ANN001
    client = process_cases(api, load_case_reference, ["E2E-14", "E2E-16", "E2E-19", "E2E-05"])

    items = queue(client)

    assert [(i["claim_id"], i["review_tier"]) for i in items] == [
        ("CLM-E2E-19", "FULL"),
        ("CLM-E2E-16", "STANDARD"),
        ("CLM-E2E-14", "QUICK"),
    ]  # most work first; the rule outcome (E2E-05, DENIED_BY_RULE) is not in it
    first = items[0]
    assert first["claim_decision"] == "DENY" and first["total_allowed_cents"] == 0
    assert first["received_date"] == E2E_CASES["E2E-19"]["given"]["claim"]["received_date"]
    assert first["processed"] is not None
    assert [i["claim_id"] for i in queue(client, tier="STANDARD")] == ["CLM-E2E-16"]
    assert [i["claim_id"] for i in queue(client, sort="processed")] == [
        "CLM-E2E-14",
        "CLM-E2E-16",
        "CLM-E2E-19",
    ]  # oldest first
    assert client.get("/v1/review/queue?tier=SOON", headers=REVIEWER).status_code == 422
