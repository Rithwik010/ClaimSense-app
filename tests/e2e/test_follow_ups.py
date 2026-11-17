"""Follow-ups after a decision, appeals and reviewer feedback (D-FUP-1, D-APL-1, D-FBK-1), through
the API on golden end-to-end claims.

- E2E-03 (returned: a billing NPI with a bad check digit) is reopened, corrected and processed
  again; E2E-02 (returned only as a duplicate) cannot be reopened, and its member reads it as a
  copy, not as returned.
- E2E-26 (the model pends the line; the reviewer accepts) gets documentation added: back to
  RECEIVED, its notes extended, the audit trail keeping counts and a hash, never the text.
- E2E-24 (the reviewer denies) is appealed: back to review with the Appeal flag, refused to the
  reviewer who denied it, decided by another (upheld or changed), and appealed once only; a member
  can appeal their own denied claim.
- E2E-15 (approved) gets the reviewer's criterion corrections: only the reviewer who finalized it,
  only quotes from the notes, positions in the audit trail, and a training example with the
  corrected criteria.
"""

import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Engine

from tests.e2e.support import (
    E2E_CASES,
    PROVIDER,
    REVIEWER,
    add_member_user,
    audit,
    bearer,
    process_case,
    stored_accumulators,
)

ADMIN = bearer("admin-test")
REASON = "The notes show the test was ordered for a new symptom, not repeated."


def review(claim_id: str, reviewer: str, *overrides: dict[str, Any]) -> dict[str, Any]:
    return {
        "claim_id": claim_id,
        "reviewer_id": reviewer,
        "action": "OVERRIDE" if overrides else "ACCEPT",
        "line_overrides": [{"reason": "Reviewed the clinical notes", **o} for o in overrides],
        "reason": None,
        "timestamp": datetime.now(UTC).isoformat(),
    }


def provider_view(client, claim_id: str) -> dict[str, Any]:  # noqa: ANN001
    response = client.get(f"/v1/claims/{claim_id}", headers=PROVIDER)
    assert response.status_code == 200, response.text
    return response.json()


# --- Correct and resubmit ------------------------------------------------------------------------


def test_a_returned_claim_is_reopened_corrected_and_processed_again(
    api, load_case_reference
) -> None:  # noqa: ANN001, E501
    load_case_reference(E2E_CASES["E2E-14"])  # its billing provider is enrolled
    enrolled = E2E_CASES["E2E-14"]["given"]["claim"]["billing_npi"]
    client = process_case(api, load_case_reference, "E2E-03")
    before = provider_view(client, "CLM-E2E-03")
    assert before["status"] == "REJECTED"
    assert before["follow_ups"] == {
        "correct": True,
        "documentation": False,
        "appeal": False,
        "reopened": False,
    }

    reopened = client.post("/v1/claims/CLM-E2E-03/reopen", headers=PROVIDER)

    assert reopened.status_code == 200, reopened.text
    assert (reopened.json()["status"], reopened.json()["final"]) == ("RECEIVED", False)
    event = audit(client, "CLM-E2E-03")[-1]
    assert (event["event_type"], event["actor"]) == ("CLAIM_REOPENED", "provider-test")
    assert event["payload"] == {"previous_status": "REJECTED", "purpose": "correction"}
    # The staff see no stale recommendation while it waits for its provider.
    assert client.get("/v1/claims/CLM-E2E-03", headers=REVIEWER).json()["record"] is None

    fixed = client.post(
        "/v1/claims/CLM-E2E-03/corrections",
        json={"corrections": [{"field": "billing_npi", "value": enrolled}]},
        headers=PROVIDER,
    )
    assert fixed.status_code == 200, fixed.text
    processed = client.post("/v1/claims/CLM-E2E-03/process", headers=PROVIDER)
    assert processed.status_code == 200, processed.text
    assert processed.json()["status"] != "REJECTED"
    types = [e["event_type"] for e in audit(client, "CLM-E2E-03")]
    assert types.index("CLAIM_REOPENED") < types.index("FIELD_CORRECTED")
    assert types.count("RULES_EVALUATED") == 2


def test_a_duplicate_is_not_reopened_and_its_member_reads_it_as_a_copy(
    api, load_case_reference, engine: Engine
) -> None:  # noqa: ANN001
    client = process_case(api, load_case_reference, "E2E-02")
    assert provider_view(client, "CLM-E2E-02")["follow_ups"]["correct"] is False

    refused = client.post("/v1/claims/CLM-E2E-02/reopen", headers=PROVIDER)

    assert refused.status_code == 422, refused.text
    assert provider_view(client, "CLM-E2E-02")["status"] == "REJECTED"
    member_id = E2E_CASES["E2E-02"]["given"]["claim"]["member_id"]
    member = add_member_user(engine, member_id)
    shown = client.get("/v1/member/claims/CLM-E2E-02", headers=member).json()
    assert (shown["outcome"], shown["heading"]) == ("DUPLICATE", "This claim was a copy")
    assert "correct and send again" not in shown["message"]


def test_a_claim_in_review_is_neither_reopened_nor_documented(api, load_case_reference) -> None:  # noqa: ANN001
    client = process_case(api, load_case_reference, "E2E-14")
    assert client.post("/v1/claims/CLM-E2E-14/reopen", headers=PROVIDER).status_code == 409
    added = client.post(
        "/v1/claims/CLM-E2E-14/documentation", json={"text": "More notes."}, headers=PROVIDER
    )
    assert added.status_code == 409
    assert [e["event_type"] for e in audit(client, "CLM-E2E-14")].count("CLAIM_REOPENED") == 0


# --- Send documentation --------------------------------------------------------------------------

DOCUMENTATION = "Colonoscopy report attached: two polyps removed by snare; pathology pending."


def test_documentation_reopens_a_pended_claim_and_the_audit_keeps_no_text(
    api, load_case_reference
) -> None:  # noqa: ANN001
    client = process_case(api, load_case_reference, "E2E-26")
    finalized = client.post("/v1/claims/CLM-E2E-26/review", json=review("CLM-E2E-26", "reviewer-1"))
    assert finalized.status_code == 200, finalized.text
    assert finalized.json()["status"] == "FINAL_PENDED"
    assert provider_view(client, "CLM-E2E-26")["follow_ups"]["documentation"] is True

    added = client.post(
        "/v1/claims/CLM-E2E-26/documentation", json={"text": DOCUMENTATION}, headers=PROVIDER
    )

    assert added.status_code == 200, added.text
    assert added.json()["status"] == "RECEIVED"
    notes = added.json()["received"]["clinical_notes"]
    assert notes.endswith(DOCUMENTATION) and "ADDITIONAL DOCUMENTATION (" in notes
    reopened, documented = audit(client, "CLM-E2E-26")[-2:]
    assert reopened["payload"] == {"previous_status": "FINAL_PENDED", "purpose": "documentation"}
    assert documented["event_type"] == "DOCUMENTATION_ADDED"
    assert documented["payload"]["characters"] == len(DOCUMENTATION)
    assert len(documented["payload"]["sha256"]) == 64
    assert "polyps" not in json.dumps(audit(client, "CLM-E2E-26"))

    processed = client.post("/v1/claims/CLM-E2E-26/process", headers=PROVIDER)
    assert processed.status_code == 200, processed.text
    assert client.get("/v1/claims/CLM-E2E-26").json()["status"] == "AWAITING_REVIEW"


def test_empty_documentation_is_refused(api, load_case_reference) -> None:  # noqa: ANN001
    client = process_case(api, load_case_reference, "E2E-12")  # pended by a rule
    refused = client.post(
        "/v1/claims/CLM-E2E-11/documentation", json={"text": "   "}, headers=PROVIDER
    )
    assert refused.status_code == 422
    assert provider_view(client, "CLM-E2E-11")["status"] == "PENDED_BY_RULE"


# --- Appeals -------------------------------------------------------------------------------------


def denied(api, load_case_reference):  # noqa: ANN001, ANN201
    """E2E-24 finalized as its golden review denies it (reviewer-golden)."""
    client = process_case(api, load_case_reference, "E2E-24")
    action = E2E_CASES["E2E-24"]["given"]["review_action"]
    response = client.post("/v1/claims/CLM-E2E-24/review", json=action)
    assert response.json()["status"] == "FINAL_DENIED", response.text
    return client


def test_an_appeal_goes_to_another_reviewer_who_upholds_it(api, load_case_reference) -> None:  # noqa: ANN001
    client = denied(api, load_case_reference)
    assert provider_view(client, "CLM-E2E-24")["follow_ups"]["appeal"] is True
    assert (
        client.post(
            "/v1/claims/CLM-E2E-24/appeal", json={"reason": "short"}, headers=PROVIDER
        ).status_code
        == 422
    )

    filed = client.post("/v1/claims/CLM-E2E-24/appeal", json={"reason": REASON}, headers=PROVIDER)

    assert filed.status_code == 200, filed.text
    assert (filed.json()["status"], filed.json()["final"]) == ("IN_REVIEW", False)
    event = audit(client, "CLM-E2E-24")[-2]
    assert (event["event_type"], event["actor"]) == ("APPEAL_FILED", "provider-test")
    assert event["payload"]["previous_reviewer"] == "reviewer-golden"
    assert REASON not in json.dumps(audit(client, "CLM-E2E-24"))
    queue = client.get("/v1/review/queue", headers=REVIEWER).json()
    item = next(i for i in queue if i["claim_id"] == "CLM-E2E-24")
    assert "APPEAL" in item["flags"]

    same = client.post("/v1/claims/CLM-E2E-24/review", json=review("CLM-E2E-24", "reviewer-golden"))
    assert same.status_code == 422 and "another reviewer" in same.text

    upheld = client.post("/v1/claims/CLM-E2E-24/review", json=review("CLM-E2E-24", "reviewer-a"))

    assert upheld.status_code == 200, upheld.text
    assert upheld.json()["status"] == "FINAL_DENIED"
    decided = next(e for e in audit(client, "CLM-E2E-24") if e["event_type"] == "APPEAL_DECIDED")
    assert (decided["actor"], decided["payload"]["outcome"]) == ("reviewer-a", "UPHELD")
    appeals = client.get("/v1/claims/CLM-E2E-24", headers=REVIEWER).json()["appeals"]
    assert [(a["status"], a["outcome"], a["reason"]) for a in appeals] == [
        ("DECIDED", "UPHELD", REASON)
    ]
    # Appealed once: the second reviewer's decision stands.
    assert provider_view(client, "CLM-E2E-24")["follow_ups"]["appeal"] is False
    again = client.post("/v1/claims/CLM-E2E-24/appeal", json={"reason": REASON}, headers=PROVIDER)
    assert again.status_code == 422


def test_an_appeal_that_changes_the_decision_pays_the_line(
    api, load_case_reference, engine: Engine
) -> None:  # noqa: ANN001
    client = denied(api, load_case_reference)
    member_id = E2E_CASES["E2E-24"]["given"]["claim"]["member_id"]
    assert stored_accumulators(engine, member_id) is None or stored_accumulators(
        engine, member_id
    ) == {"deductible_met_cents": 0, "oop_met_cents": 0}
    client.post("/v1/claims/CLM-E2E-24/appeal", json={"reason": REASON}, headers=PROVIDER)

    changed = client.post(
        "/v1/claims/CLM-E2E-24/review",
        json=review("CLM-E2E-24", "reviewer-a", {"line_no": 1, "decision": "APPROVE"}),
    )

    assert changed.status_code == 200, changed.text
    assert changed.json()["status"] == "FINAL_APPROVED"
    decided = next(e for e in audit(client, "CLM-E2E-24") if e["event_type"] == "APPEAL_DECIDED")
    assert decided["payload"]["outcome"] == "CHANGED"
    assert changed.json()["amounts"]["totals"]["plan_pays_cents"] >= 0
    assert stored_accumulators(engine, member_id) is not None


def test_a_member_appeals_their_denied_claim(api, load_case_reference, engine: Engine) -> None:  # noqa: ANN001
    load_case_reference(E2E_CASES["E2E-03"])  # another member on file: MBR-000121
    client = denied(api, load_case_reference)
    member = add_member_user(engine, E2E_CASES["E2E-24"]["given"]["claim"]["member_id"])
    before = client.get("/v1/member/claims/CLM-E2E-24", headers=member).json()
    assert (before["outcome"], before["can_appeal"], before["appeal"]) == ("DENIED", True, None)
    assert before["services"] and all(isinstance(s, str) and s for s in before["services"])

    filed = client.post(
        "/v1/member/claims/CLM-E2E-24/appeal", json={"reason": REASON}, headers=member
    )

    assert filed.status_code == 201, filed.text
    shown = filed.json()
    assert (shown["final"], shown["heading"]) == (False, "Your appeal is being reviewed")
    assert shown["appeal"]["status"] == "OPEN" and shown["appeal"]["filed_by_you"] is True
    assert shown["can_appeal"] is False
    # The provider sees the appeal, not the member's reason.
    appeals = provider_view(client, "CLM-E2E-24")["appeals"]
    assert [(a["filed_role"], a["reason"]) for a in appeals] == [("member", None)]
    # Another member's claim is not theirs to appeal.
    other = add_member_user(engine, "MBR-000121", username="member-other")
    assert (
        client.post(
            "/v1/member/claims/CLM-E2E-24/appeal", json={"reason": REASON}, headers=other
        ).status_code
        == 404
    )


# --- Reviewer feedback ---------------------------------------------------------------------------

QUOTE = "Vital signs are stable."  # in E2E-15's notes, but not the criterion's evidence


def approved(api, load_case_reference):  # noqa: ANN001, ANN201
    client = process_case(api, load_case_reference, "E2E-15")
    action = E2E_CASES["E2E-15"]["given"]["review_action"]  # reviewer-golden accepts
    assert client.post("/v1/claims/CLM-E2E-15/review", json=action).status_code == 200
    return client


def fix(status: str, quote: str | None = None) -> dict[str, Any]:
    return {
        "lines": [
            {
                "line_no": 1,
                "criteria": [{"criterion_id": "POL-IMG-001.c1", "status": status, "quote": quote}],
            }
        ]
    }


def test_the_reviewers_corrections_become_a_training_example(api, load_case_reference) -> None:  # noqa: ANN001
    client = approved(api, load_case_reference)
    url = "/v1/claims/CLM-E2E-15/feedback"
    assert (
        client.post(url, json=fix("NOT_MET", QUOTE), headers=bearer("reviewer-a")).status_code
        == 422
    )
    assert client.post(url, json=fix("NOT_MET", "Not in the notes.")).status_code == 422
    assert client.post(url, json=fix("NOT_MET")).status_code == 422  # NOT_MET needs a quote

    saved = client.post(url, json=fix("NOT_MET", "Vital  signs are\nstable."))

    assert saved.status_code == 200, saved.text
    assert saved.json() == {"claim_id": "CLM-E2E-15", "criteria_corrected": 1}
    event = audit(client, "CLM-E2E-15")[-1]
    assert (event["event_type"], event["actor"]) == ("REVIEWER_FEEDBACK", "reviewer-golden")
    corrected = event["payload"]["lines"][0]["criteria"][0]
    assert {k: corrected[k] for k in ("criterion_id", "model_status", "status")} == {
        "criterion_id": "POL-IMG-001.c1",
        "model_status": "MET",
        "status": "NOT_MET",
    }
    assert "Vital" not in json.dumps(event)  # a position in the notes, never the text

    export = client.get("/v1/metrics/training-examples", headers=ADMIN)

    assert export.status_code == 200
    assert export.headers["content-type"].startswith("application/x-ndjson")
    examples = [json.loads(line) for line in export.text.splitlines()]
    example = next(e for e in examples if e["metadata"]["claim_id"] == "CLM-E2E-15")
    assert [m["role"] for m in example["messages"]] == ["system", "user", "assistant"]
    answer = json.loads(example["messages"][2]["content"])
    criterion = answer["lines"][0]["criteria"][0]
    assert (criterion["status"], criterion["evidence"]) == ("NOT_MET", QUOTE)
    assert example["metadata"]["lines"][0]["final_decision"] == "APPROVE"


def test_feedback_needs_a_finalized_claim(api, load_case_reference) -> None:  # noqa: ANN001
    client = process_case(api, load_case_reference, "E2E-15")  # awaiting review
    response = client.post("/v1/claims/CLM-E2E-15/feedback", json=fix("NOT_DOCUMENTED"))
    assert response.status_code in (409, 422)


def test_documentation_never_takes_the_prompt_past_the_models_budget(
    api, load_case_reference
) -> None:  # noqa: ANN001
    """Added documentation goes into the clinical notes, so into the model's prompt when the claim
    is processed again: each addition is checked against the prompt budget (PROMPT_BUDGET,
    D-DOC-3) like a new claim, and refused (422, nothing added) once it would not fit."""
    client = process_case(api, load_case_reference, "E2E-12")  # pended by a rule
    page = ("Follow-up visit note with exam findings and history reviewed in detail. " * 105)[:7900]
    sizes = []
    for _ in range(8):
        response = client.post(
            "/v1/claims/CLM-E2E-11/documentation", json={"text": page}, headers=PROVIDER
        )
        notes = provider_view(client, "CLM-E2E-11")["received"]["clinical_notes"]
        if response.status_code == 422:
            assert "too long for the decision model" in response.json()["detail"]
            assert len(notes) == sizes[-1]  # the refused page was not added
            break
        assert response.status_code == 200, response.text
        sizes.append(len(notes))
    else:
        raise AssertionError("eight pages of documentation were all accepted")
    assert sizes  # at least one page fitted
