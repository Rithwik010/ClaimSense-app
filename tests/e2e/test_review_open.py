"""P5.3: a reviewer opening a claim (REVIEW_OPENED) and the review time (D-REV-6): from the acting
reviewer's latest opening before the action to the action, not from the first opening by anyone."""

from datetime import UTC, datetime
from typing import Any

from tests.e2e.support import E2E_CASES, REVIEWER, audit, process_case


def open_review(client, claim_id: str, reviewer: str):  # noqa: ANN001, ANN201
    return client.post(
        f"/v1/claims/{claim_id}/review/open", json={"reviewer_id": reviewer}, headers=REVIEWER
    )


def accept(claim_id: str, reviewer: str) -> dict[str, Any]:
    return {
        "claim_id": claim_id,
        "reviewer_id": reviewer,
        "action": "ACCEPT",
        "timestamp": datetime.now(UTC).isoformat(),
    }


def test_opening_a_claim_awaiting_review_is_audited(api, load_case_reference) -> None:  # noqa: ANN001
    client = process_case(api, load_case_reference, "E2E-14")
    process_case(api, load_case_reference, "E2E-05")  # DENIED_BY_RULE
    url = "/v1/claims/CLM-E2E-14/review/open"

    assert client.post(url, json={"reviewer_id": "reviewer-1"}).status_code == 403
    assert client.post(url, json={"reviewer_id": "  "}, headers=REVIEWER).status_code == 422
    assert client.post(url, json={"reviewer_id": "r" * 65}, headers=REVIEWER).status_code == 422
    assert open_review(client, "CLM-NOPE", "reviewer-1").status_code == 404
    denied = E2E_CASES["E2E-05"]["given"]["claim"]["claim_id"]
    assert open_review(client, denied, "reviewer-1").status_code == 409  # never reviewed

    response = open_review(client, "CLM-E2E-14", "reviewer-1")

    assert response.status_code == 200, response.text
    opened = audit(client, "CLM-E2E-14")[-1]
    assert (opened["event_type"], opened["actor"]) == ("REVIEW_OPENED", "reviewer-1")
    assert opened["payload"] == {"reviewer_id": "reviewer-1"}
    assert datetime.fromisoformat(response.json()["opened"]) == datetime.fromisoformat(
        opened["created_at"]
    )
    assert client.get("/v1/claims/CLM-E2E-14").json()["status"] == "AWAITING_REVIEW"
    review = client.post("/v1/claims/CLM-E2E-14/review", json=accept("CLM-E2E-14", "reviewer-1"))
    assert review.status_code == 403
    finalized = client.post(
        "/v1/claims/CLM-E2E-14/review", json=accept("CLM-E2E-14", "reviewer-1"), headers=REVIEWER
    )
    assert finalized.status_code == 200
    assert open_review(client, "CLM-E2E-14", "reviewer-1").status_code == 409  # final


def test_review_time_runs_from_the_acting_reviewers_latest_opening(
    api, load_case_reference
) -> None:  # noqa: ANN001
    client = process_case(api, load_case_reference, "E2E-14")
    for reviewer in ("reviewer-b", "reviewer-a", "reviewer-a", "reviewer-b"):
        assert open_review(client, "CLM-E2E-14", reviewer).status_code == 200
    openings = [e for e in audit(client, "CLM-E2E-14") if e["event_type"] == "REVIEW_OPENED"]
    latest_by_a = openings[2]  # not the first by anyone, the first by A, or the latest by anyone

    response = client.post(
        "/v1/claims/CLM-E2E-14/review", json=accept("CLM-E2E-14", "reviewer-a"), headers=REVIEWER
    )

    assert response.status_code == 200, response.text
    accepted = next(e for e in audit(client, "CLM-E2E-14") if e["event_type"] == "REVIEW_ACCEPTED")
    payload = accepted["payload"]
    assert datetime.fromisoformat(payload["opened_at"]) == datetime.fromisoformat(
        latest_by_a["created_at"]
    )
    assert isinstance(payload["review_seconds"], int) and payload["review_seconds"] >= 0
    assert len({e["created_at"] for e in openings}) == 4  # four distinct opening times
