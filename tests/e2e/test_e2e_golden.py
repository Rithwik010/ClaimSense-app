"""P2.5: every golden end-to-end claim (tests/golden/e2e/cases.json) through the pipeline as it
now runs: the full v1 rules engine on the database (P2.1, P2.5) and the full calculator (P2.4),
with the model stubbed by the case's answer. Expected values are the golden ones; never change one
to make a test pass (H12).

JSON claims go through POST /v1/claims/intake; scanned and digital-PDF claims through
`intake_claim_data` with their field confidences (file upload is P5.1). The cases record no
retrieval, so the stub retriever returns, for a line's procedure code, the curated criteria the
case's answer cites for that line (P5.6 rebuilds the cases for real retrieval). Each case runs on a
fresh database with its reference additions and claims on file.

The 18 cases with a review action then go through POST /v1/claims/{id}/review (P5.3): the final
status, claim decision, line decisions, amounts and accumulators are the golden ones, for every
final status.
"""

import json
from datetime import date
from typing import Any

import pytest
from sqlalchemy.orm import Session

from app.db.models import Accumulator
from app.domain.contracts import DecisionRecord, SourceFormat
from app.workflow.pipeline import intake_claim_data
from tests.e2e.support import E2E_CASES, REVIEWER, CaseRetriever, StubModel, audit

CASES = sorted(E2E_CASES.values(), key=lambda case: case["case_id"])
REVIEWED = [case for case in CASES if case["given"].get("review_action")]


def _failures(record: DecisionRecord) -> list[dict[str, Any]]:
    return [
        {
            "rule_id": r.rule_id,
            "outcome": r.outcome.value,
            "reason_code": r.reason_code,
            "line_no": r.line_no,
        }
        for r in record.rules_outcome.rule_results
        if not r.passed
    ]


def differences(record: DecisionRecord, expected: dict[str, Any]) -> list[str]:
    """Every expected value the record does not match."""
    found = []

    def check(name: str, got: Any, want: Any) -> None:
        if got != want:
            found.append(f"{name}: got {got!r}, expected {want!r}")

    check("status", record.status.value, expected["status_after_processing"])
    rules = expected["rules"]
    check("rules claim_outcome", record.rules_outcome.claim_outcome.value, rules["claim_outcome"])
    if "failures" in rules:
        check("rules failures", _failures(record), rules["failures"])
    if "line_outcomes" in rules:
        check(
            "rules line_outcomes",
            [o.model_dump(mode="json") for o in record.rules_outcome.line_outcomes],
            rules["line_outcomes"],
        )
    if "flags" in rules:
        check("rules flags", record.rules_outcome.flags, rules["flags"])
    recommendation = expected["recommendation"]
    if recommendation is None:
        check("recommendation", record.line_decisions, [])
        return found
    check("output_valid", record.output_errors == [], recommendation["output_valid"])
    check(
        "line_decisions",
        [
            d.model_dump(mode="json", include={"line_no", "decision", "source", "reason_codes"})
            for d in record.line_decisions
        ],
        recommendation["line_decisions"],
    )
    check(
        "claim_decision",
        record.claim_decision.value if record.claim_decision else None,
        recommendation["claim_decision"],
    )
    check(
        "review_tier",
        record.review_tier.value if record.review_tier else None,
        recommendation["review_tier"],
    )
    check(
        "amounts",
        record.amounts.model_dump() if record.amounts else None,
        recommendation["amounts"],
    )
    return found


def final_differences(
    record: DecisionRecord,
    finalized: dict[str, Any],
    stored: dict[str, int],
    expected: dict[str, Any],
) -> list[str]:
    """Every expected final value (golden `final`) the finalized claim does not match."""
    found = []

    def check(name: str, got: Any, want: Any) -> None:
        if got != want:
            found.append(f"{name}: got {got!r}, expected {want!r}")

    check("final status", record.status.value, expected["status"])
    check("final claim_decision", record.claim_decision.value, expected["claim_decision"])
    check(
        "final line_decisions",
        [
            line.model_dump(mode="json", include={"line_no", "decision", "source", "reason_codes"})
            for line in record.line_decisions
        ],
        expected["line_decisions"],
    )
    check("final amounts", record.amounts.model_dump(mode="json"), expected["amounts"])
    after = {k: v for k, v in expected["accumulators_after"].items() if k != "network"}
    accumulators = finalized["accumulators"]
    check(
        "accumulators network", accumulators["network"], expected["accumulators_after"]["network"]
    )
    check("accumulators after (FINALIZED)", accumulators["after"], after)
    check("accumulators after (stored)", stored, after)
    return found


def stored_accumulators(engine, member_id: str, finalized: dict[str, Any]) -> dict[str, int]:  # noqa: ANN001
    accumulators = finalized["accumulators"]
    key = (member_id, date.fromisoformat(accumulators["period_start"]), accumulators["network"])
    with Session(engine) as session:
        row = session.get(Accumulator, key)
    if row is None:
        return {"deductible_met_cents": 0, "oop_met_cents": 0}
    return {"deductible_met_cents": row.deductible_met_cents, "oop_met_cents": row.oop_met_cents}


def test_the_golden_review_cases_cover_every_final_status() -> None:
    statuses = {case["expected"]["final"]["status"] for case in REVIEWED}

    assert len(REVIEWED) == 18
    assert statuses == {"FINAL_APPROVED", "FINAL_DENIED", "FINAL_PENDED", "FINAL_PARTIAL"}
    rule_outcomes = [c["expected"] for c in CASES if c not in REVIEWED]
    assert all(e["final"]["status"] == e["status_after_processing"] for e in rule_outcomes)


@pytest.mark.parametrize("case", CASES, ids=[case["case_id"] for case in CASES])
def test_golden_end_to_end_case(api, load_case_reference, engine, case: dict[str, Any]) -> None:  # noqa: ANN001
    given = case["given"]
    load_case_reference(case)
    answer = given.get("model_answer")
    model = StubModel(json.dumps(answer) if answer is not None else "unused")
    client = api(model, CaseRetriever(case))
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
            )

    response = client.post(f"/v1/claims/{claim['claim_id']}/process")

    assert response.status_code == 200, response.text
    record = DecisionRecord.model_validate(response.json())
    assert differences(record, case["expected"]) == [], record.output_errors
    if case["expected"]["recommendation"] is None:
        assert model.prompts == []  # a rule outcome never reaches the model
    action = given.get("review_action")
    if action is None:  # a rule outcome: final as processed, never reviewed (§8.8)
        accept = {
            "claim_id": claim["claim_id"],
            "reviewer_id": "reviewer-golden",
            "action": "ACCEPT",
            "timestamp": "2026-12-20T10:00:00Z",
        }
        refused = client.post(
            f"/v1/claims/{claim['claim_id']}/review", json=accept, headers=REVIEWER
        )
        assert refused.status_code == 409
        return

    reviewed = client.post(f"/v1/claims/{claim['claim_id']}/review", json=action, headers=REVIEWER)

    assert reviewed.status_code == 200, reviewed.text
    final = DecisionRecord.model_validate(reviewed.json())
    events = audit(client, claim["claim_id"])
    finalized = next(e for e in reversed(events) if e["event_type"] == "FINALIZED")
    assert events[-1]["event_type"] == "EXPLANATION_BUILT"  # of the final record
    stored = stored_accumulators(engine, claim["member_id"], finalized["payload"])
    assert final_differences(final, finalized["payload"], stored, case["expected"]["final"]) == []
