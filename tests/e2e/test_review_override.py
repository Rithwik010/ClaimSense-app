"""P5.3: OVERRIDE (§8.8) through the API, on golden end-to-end claims: the before and after of each
overridden line in the audit trail, the calculator re-run, the benefit category (D-REV-4), and the
refusals (422) that leave the claim awaiting review with nothing written.

E2E-24 (APPROVE -> DENY), E2E-25 (DENY -> APPROVE) and E2E-26 (PEND -> APPROVE, a colonoscopy code
with two candidate categories, ENDOSCOPY and PREVENTIVE_CARE) carry golden review actions."""

import json
from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy import Engine

from app.workflow import finalize
from tests.e2e.support import (
    E2E_CASES,
    REVIEWER,
    CaseRetriever,
    StubModel,
    audit,
    process_case,
    stored_accumulators,
)

LINE_FIELDS = ("line_no", "decision", "source", "reason_codes")


def override(claim_id: str, *lines: dict[str, Any]) -> dict[str, Any]:
    return {
        "claim_id": claim_id,
        "reviewer_id": "reviewer-1",
        "action": "OVERRIDE",
        "line_overrides": [{"reason": "Reviewed the clinical notes", **line} for line in lines],
        "reason": None,
        "timestamp": datetime.now(UTC).isoformat(),
    }


def golden_lines(record: dict[str, Any]) -> list[dict[str, Any]]:
    return [{k: line[k] for k in LINE_FIELDS} for line in record["line_decisions"]]


def without_network(accumulators: dict[str, Any]) -> dict[str, int]:
    return {k: v for k, v in accumulators.items() if k != "network"}


class RecordingLogger:
    def __init__(self) -> None:
        self.entries: list[tuple[str, dict[str, Any]]] = []

    def info(self, event: str, **fields: Any) -> None:
        self.entries.append((event, fields))


def test_an_override_is_audited_line_by_line_and_its_reason_is_never_logged(
    api, load_case_reference, monkeypatch
) -> None:  # noqa: ANN001
    case = E2E_CASES["E2E-24"]
    action, final = case["given"]["review_action"], case["expected"]["final"]
    reason = action["line_overrides"][0]["reason"]
    client = process_case(api, load_case_reference, "E2E-24")
    logger = RecordingLogger()
    monkeypatch.setattr(finalize, "log", logger)

    response = client.post("/v1/claims/CLM-E2E-24/review", json=action, headers=REVIEWER)

    assert response.status_code == 200, response.text
    record = response.json()
    assert (record["status"], record["claim_decision"]) == (
        final["status"],
        final["claim_decision"],
    )
    assert golden_lines(record) == final["line_decisions"]
    assert record["amounts"] == final["amounts"]
    events = audit(client, "CLM-E2E-24")
    assert [e["event_type"] for e in events[-2:]] == ["REVIEW_OVERRIDDEN", "FINALIZED"]
    overridden = events[-2]
    assert overridden["actor"] == action["reviewer_id"]
    assert overridden["payload"]["changes"] == [
        {
            "line_no": 1,
            "reason": reason,
            "before": {
                "decision": "APPROVE",
                "benefit_category": "DIAGNOSTIC_TESTS",
                "source": "MODEL",
                "reason_codes": [],
            },
            "after": {
                "decision": "DENY",
                "benefit_category": "DIAGNOSTIC_TESTS",
                "source": "REVIEWER",
                "reason_codes": [],
            },
        }
    ]
    finalized = events[-1]["payload"]
    assert finalized["accumulators_updated"] is False  # no approved line
    assert finalized["accumulators"]["after"] == without_network(final["accumulators_after"])
    assert finalized["amounts_changed_since_review"] is True  # the approved amounts are gone
    assert [event for event, _ in logger.entries] == ["claim_finalized"]
    assert reason not in json.dumps(logger.entries)  # IDs only (§8.9)


def test_an_approve_override_reruns_the_calculator(
    api, load_case_reference, engine: Engine
) -> None:  # noqa: ANN001
    case = E2E_CASES["E2E-25"]
    final = case["expected"]["final"]
    client = process_case(api, load_case_reference, "E2E-25")
    shown = client.get("/v1/claims/CLM-E2E-25").json()["record"]["amounts"]["totals"]
    assert shown["allowed_cents"] == 0  # a denied line carries no amounts

    response = client.post(
        "/v1/claims/CLM-E2E-25/review", json=case["given"]["review_action"], headers=REVIEWER
    )

    assert response.status_code == 200, response.text
    record = response.json()
    assert record["status"] == final["status"] == "FINAL_APPROVED"
    assert golden_lines(record) == final["line_decisions"]
    assert record["line_decisions"][0]["benefit_category"] == "DIAGNOSTIC_TESTS"  # the model's
    assert record["amounts"] == final["amounts"]
    member = case["given"]["claim"]["member_id"]
    assert stored_accumulators(engine, member) == without_network(final["accumulators_after"])
    finalized = audit(client, "CLM-E2E-25")[-1]["payload"]
    assert finalized["amounts_changed_since_review"] is True
    assert "allowed_cents" in finalized["changed_totals"]


def test_a_reviewer_may_approve_under_another_candidate_category(
    api, load_case_reference, engine: Engine
) -> None:  # noqa: ANN001
    """E2E-26's colonoscopy approved as PREVENTIVE_CARE instead of the model's ENDOSCOPY: the plan's
    preventive care has a zero copay and no deductible (data/curated/benefits.yaml), so the member
    pays nothing and the accumulators do not move."""
    case = E2E_CASES["E2E-26"]
    golden_totals = case["expected"]["final"]["amounts"]["totals"]
    client = process_case(api, load_case_reference, "E2E-26")
    member = case["given"]["claim"]["member_id"]
    before = stored_accumulators(engine, member)
    line = {"line_no": 1, "decision": "APPROVE", "benefit_category": "PREVENTIVE_CARE"}

    response = client.post(
        "/v1/claims/CLM-E2E-26/review", json=override("CLM-E2E-26", line), headers=REVIEWER
    )

    assert response.status_code == 200, response.text
    record = response.json()
    final_line = record["line_decisions"][0]
    assert (final_line["benefit_category"], final_line["source"]) == ("PREVENTIVE_CARE", "REVIEWER")
    totals = record["amounts"]["totals"]
    assert totals["allowed_cents"] == golden_totals["allowed_cents"]  # same fee row
    assert totals["member_pays_cents"] == 0
    assert totals["plan_pays_cents"] == totals["allowed_cents"]
    assert stored_accumulators(engine, member) == before
    change = audit(client, "CLM-E2E-26")[-2]["payload"]["changes"][0]
    assert (change["before"]["decision"], change["after"]["decision"]) == ("PEND", "APPROVE")
    assert (change["before"]["benefit_category"], change["after"]["benefit_category"]) == (
        "ENDOSCOPY",
        "PREVENTIVE_CARE",
    )


def test_approving_a_line_the_model_left_undecided_needs_a_category_when_several_fit(
    api, load_case_reference
) -> None:  # noqa: ANN001
    """With invalid model output, E2E-26's line is a VALIDATION PEND with no category; approving it
    needs the reviewer's category, and under ENDOSCOPY the amounts are the golden ones."""
    case = E2E_CASES["E2E-26"]
    load_case_reference(case)
    client = api(StubModel("not json"), CaseRetriever(case))
    assert client.post("/v1/claims/intake", json=case["given"]["claim"]).status_code == 201
    assert client.post("/v1/claims/CLM-E2E-26/process").status_code == 200
    shown = client.get("/v1/claims/CLM-E2E-26").json()["record"]["line_decisions"][0]
    assert (shown["source"], shown["benefit_category"]) == ("VALIDATION", None)
    url, approve = "/v1/claims/CLM-E2E-26/review", {"line_no": 1, "decision": "APPROVE"}

    refused = client.post(url, json=override("CLM-E2E-26", approve), headers=REVIEWER)

    assert refused.status_code == 422
    assert "choose the benefit category" in refused.json()["detail"]
    assert "ENDOSCOPY, PREVENTIVE_CARE" in refused.json()["detail"]
    chosen = {**approve, "benefit_category": "ENDOSCOPY"}
    response = client.post(url, json=override("CLM-E2E-26", chosen), headers=REVIEWER)
    assert response.status_code == 200, response.text
    assert response.json()["amounts"] == case["expected"]["final"]["amounts"]


@pytest.mark.parametrize(
    ("case_id", "lines", "message"),
    [
        ("E2E-22", [{"line_no": 2, "decision": "APPROVE"}], "rule outcomes are automatic"),
        (
            "E2E-26",
            [{"line_no": 1, "decision": "DENY", "benefit_category": "ENDOSCOPY"}],
            "APPROVE decision only",
        ),
        (
            "E2E-26",
            [{"line_no": 1, "decision": "APPROVE", "benefit_category": "ADVANCED_IMAGING"}],
            "not one of the line's candidate categories",
        ),
        ("E2E-26", [{"line_no": 1, "decision": "APPROVE", "benefit_category": "SPA"}], None),
        ("E2E-14", [{"line_no": 1, "decision": "APPROVE"}], "changes neither"),
        ("E2E-14", [{"line_no": 2, "decision": "DENY"}], "not on the claim"),
        (
            "E2E-14",
            [{"line_no": 1, "decision": "DENY"}, {"line_no": 1, "decision": "PEND"}],
            "overridden twice",
        ),
    ],
)
def test_a_refused_override_leaves_the_claim_awaiting_review(
    api, load_case_reference, case_id: str, lines: list[dict[str, Any]], message: str | None
) -> None:  # noqa: ANN001
    client = process_case(api, load_case_reference, case_id)
    claim_id = E2E_CASES[case_id]["given"]["claim"]["claim_id"]
    before = audit(client, claim_id)

    response = client.post(
        f"/v1/claims/{claim_id}/review", json=override(claim_id, *lines), headers=REVIEWER
    )

    assert response.status_code == 422
    if message is not None:
        assert message in response.json()["detail"]
    assert client.get(f"/v1/claims/{claim_id}").json()["status"] == "AWAITING_REVIEW"
    assert audit(client, claim_id) == before
