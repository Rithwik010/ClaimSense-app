"""P5.3: ACCEPT and finalization (§8.8, §8.6) through the API and the workflow, on golden end-to-end
claims: the final status, the amounts recomputed against the stored accumulators, the stored
accumulators, the audit trail, and the errors (403, 404, 409, 422).

The lock tests use thread events and the database's own lock waits (pg_stat_activity), never
sleeps: a finalization paused right after taking a lock, and a second one that must wait for it."""

import copy
import json
import threading
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import Engine, delete, text
from sqlalchemy.orm import Session

from app.db.models import FeeScheduleEntry, VisitUsage
from app.domain.contracts import ReviewAction
from app.workflow import finalize
from app.workflow.finalize import finalize_review
from app.workflow.states import InvalidTransition
from tests.e2e.support import (
    E2E_CASES,
    REVIEWER,
    CaseRetriever,
    StubModel,
    audit,
    process_case,
    stored_accumulators,
)


def accept(claim_id: str, reviewer: str = "reviewer-1") -> dict[str, Any]:
    return {
        "claim_id": claim_id,
        "reviewer_id": reviewer,
        "action": "ACCEPT",
        "line_overrides": [],
        "reason": None,
        "timestamp": datetime.now(UTC).isoformat(),
    }


def test_accept_finalizes_the_claim_with_amounts_accumulators_and_audit(
    api, load_case_reference, engine: Engine
) -> None:
    case = E2E_CASES["E2E-14"]
    client = process_case(api, load_case_reference, "E2E-14")
    final = case["expected"]["final"]

    response = client.post(
        "/v1/claims/CLM-E2E-14/review", json=accept("CLM-E2E-14"), headers=REVIEWER
    )

    assert response.status_code == 200, response.text
    record = response.json()
    assert record["status"] == final["status"] == "FINAL_APPROVED"
    assert record["claim_decision"] == final["claim_decision"]
    assert record["amounts"] == final["amounts"]
    assert record["review"]["action"] == "ACCEPT" and record["timestamps"]["finalized"]
    assert [d["source"] for d in record["line_decisions"]] == ["MODEL"]
    member = case["given"]["claim"]["member_id"]
    expected_after = {k: v for k, v in final["accumulators_after"].items() if k != "network"}
    assert stored_accumulators(engine, member) == expected_after
    events = audit(client, "CLM-E2E-14")
    assert [e["event_type"] for e in events[-3:]] == [
        "REVIEW_ACCEPTED",
        "FINALIZED",
        "EXPLANATION_BUILT",
    ]
    assert {e["actor"] for e in events[-3:-1]} == {"reviewer-1"}  # the explanation: system
    finalized = events[-2]["payload"]
    assert finalized["status"] == "FINAL_APPROVED" and finalized["accumulators_updated"]
    assert finalized["accumulators"]["after"] == expected_after
    assert finalized["amounts_changed_since_review"] is False
    assert finalized["visit_usage"] == {}  # office visits have no visit limit
    accepted = events[-3]["payload"]
    assert (accepted["opened_at"], accepted["review_seconds"]) == (None, None)  # never opened
    assert finalized["calculator_version"] and events[-2]["rules_version"] == "2.1.0"
    assert client.get("/v1/claims/CLM-E2E-14").json()["record"] == record


def visits_used(engine: Engine, member_id: str, category: str) -> int:
    with Session(engine) as session:
        row = session.get(VisitUsage, (member_id, date(2026, 1, 1), category))
        return row.visits_used if row else 0


def test_finalization_counts_a_therapy_session_as_one_visit(
    api, load_case_reference, engine: Engine
) -> None:  # noqa: ANN001
    """E2E-22: two therapy codes on one date, line 1 approved and line 2 denied by a rule (MUE):
    one visit (D-REV-8)."""
    case = E2E_CASES["E2E-22"]
    member = case["given"]["claim"]["member_id"]
    client = process_case(api, load_case_reference, "E2E-22")
    before = visits_used(engine, member, "REHAB_THERAPY")

    response = client.post(
        "/v1/claims/CLM-E2E-22/review", json=case["given"]["review_action"], headers=REVIEWER
    )

    assert response.status_code == 200, response.text
    assert visits_used(engine, member, "REHAB_THERAPY") == before + 1
    finalized = audit(client, "CLM-E2E-22")[-2]["payload"]
    assert finalized["visit_usage"] == {"REHAB_THERAPY": {"before": before, "after": before + 1}}


def test_review_errors(api, load_case_reference) -> None:  # noqa: ANN001
    client = process_case(api, load_case_reference, "E2E-14")
    process_case(api, load_case_reference, "E2E-05")  # DENIED_BY_RULE
    url = "/v1/claims/CLM-E2E-14/review"
    override_without_lines = {**accept("CLM-E2E-14"), "action": "OVERRIDE"}
    blank_reason = {
        **override_without_lines,
        "line_overrides": [{"line_no": 1, "decision": "DENY", "reason": "   "}],
    }
    accept_with_lines = {
        **accept("CLM-E2E-14"),
        "line_overrides": [{"line_no": 1, "decision": "DENY", "reason": "x"}],
    }

    assert client.post(url, json=accept("CLM-E2E-14")).status_code == 403
    for body in (accept_with_lines, override_without_lines, blank_reason):
        assert client.post(url, json=body, headers=REVIEWER).status_code == 422
    assert client.post(url, json=accept("CLM-OTHER"), headers=REVIEWER).status_code == 422
    assert (
        client.post(
            "/v1/claims/CLM-NOPE/review", json=accept("CLM-NOPE"), headers=REVIEWER
        ).status_code
        == 404
    )
    denied = E2E_CASES["E2E-05"]["given"]["claim"]["claim_id"]
    rule_outcome = client.post(f"/v1/claims/{denied}/review", json=accept(denied), headers=REVIEWER)
    assert rule_outcome.status_code == 409  # rule outcomes are final and never reviewed
    assert client.post(url, json=accept("CLM-E2E-14"), headers=REVIEWER).status_code == 200
    again = client.post(url, json=accept("CLM-E2E-14"), headers=REVIEWER)
    assert again.status_code == 409 and "FINAL_APPROVED" in again.json()["detail"]


def test_a_claim_whose_calculation_failed_is_refused_until_the_cause_is_fixed(
    api, load_case_reference, engine: Engine
) -> None:
    case = E2E_CASES["E2E-14"]
    code = case["given"]["claim"]["service_lines"][0]["procedure_code"]
    with Session(engine) as session:
        session.execute(delete(FeeScheduleEntry).where(FeeScheduleEntry.procedure_code == code))
        session.commit()
    client = process_case(api, load_case_reference, "E2E-14")
    before = [e["event_type"] for e in audit(client, "CLM-E2E-14")]
    assert before[-2:] == ["CALCULATION_FAILED", "EXPLANATION_BUILT"]

    response = client.post(
        "/v1/claims/CLM-E2E-14/review", json=accept("CLM-E2E-14"), headers=REVIEWER
    )

    assert response.status_code == 422
    assert (
        "fix the cause" in response.json()["detail"]
        and "pend the line" in response.json()["detail"]
    )
    assert client.get("/v1/claims/CLM-E2E-14").json()["status"] == "AWAITING_REVIEW"
    assert [e["event_type"] for e in audit(client, "CLM-E2E-14")] == before  # nothing written


# --- Locks ---------------------------------------------------------------------------------------


class Worker(threading.Thread):
    def __init__(self, name: str, work: Callable[[], Any]) -> None:
        super().__init__(name=name, daemon=True)
        self.work, self.result, self.error = work, None, None

    def run(self) -> None:
        try:
            self.result = self.work()
        except Exception as exc:  # noqa: BLE001 - the test inspects it
            self.error = exc


def pause_after(
    monkeypatch, lock: str, thread_name: str
) -> tuple[threading.Event, threading.Event]:  # noqa: ANN001
    """Pause the named thread right after it takes the lock, until released."""
    original = getattr(finalize, lock)
    locked, release = threading.Event(), threading.Event()

    def paused(session: Session, key: str):  # noqa: ANN202
        found = original(session, key)
        if threading.current_thread().name == thread_name:
            locked.set()
            assert release.wait(30)
        return found

    monkeypatch.setattr(finalize, lock, paused)
    return locked, release


def wait_until_a_lock_is_awaited(engine: Engine) -> None:
    """Until another connection to this database waits for a lock (Postgres's own state)."""
    done = threading.Event()
    with engine.connect() as conn:
        for _ in range(3000):
            waiting = conn.execute(
                text(
                    "SELECT count(*) FROM pg_stat_activity "
                    "WHERE datname = current_database() AND wait_event_type = 'Lock'"
                )
            ).scalar_one()
            if waiting:
                return
            done.wait(0.01)
    raise AssertionError("no finalization waited for the lock")


def finalize_with(engine: Engine, claim_id: str) -> Callable[[], Any]:
    def work() -> Any:
        with Session(engine) as session:
            action = ReviewAction.model_validate(accept(claim_id, reviewer="reviewer-lock"))
            return finalize_review(session, claim_id, action)

    return work


def test_two_finalizations_for_one_member_run_one_after_the_other(
    api, load_case_reference, engine: Engine, monkeypatch
) -> None:
    """The second waits for the first's member lock, then computes against the accumulators the
    first wrote, and says its amounts differ from those shown at review."""
    case = copy.deepcopy(E2E_CASES["E2E-15"])
    member = case["given"]["claim"]["member_id"]
    for row in case["given"]["reference_additions"]["accumulators"]:
        row["deductible_met_cents"] = row["oop_met_cents"] = 80000  # near the deductible's end
    load_case_reference(case)
    second = copy.deepcopy(case["given"]["claim"])
    second["claim_id"] = "CLM-E2E-15-B"
    day = date.fromisoformat(second["service_lines"][0]["date_of_service"]) - timedelta(days=1)
    second["service_lines"][0]["date_of_service"] = day.isoformat()
    client = api(StubModel(json.dumps(case["given"]["model_answer"])), CaseRetriever(case))
    for claim in (case["given"]["claim"], second):
        assert client.post("/v1/claims/intake", json=claim).status_code == 201
        assert client.post(f"/v1/claims/{claim['claim_id']}/process").status_code == 200
    locked, release = pause_after(monkeypatch, "_lock_member", "first")
    first = Worker("first", finalize_with(engine, "CLM-E2E-15"))
    later = Worker("later", finalize_with(engine, "CLM-E2E-15-B"))

    first.start()
    assert locked.wait(30)
    later.start()
    wait_until_a_lock_is_awaited(engine)
    release.set()
    first.join(30)
    later.join(30)

    assert first.error is None and later.error is None
    assert first.result.status.value == later.result.status.value == "FINAL_APPROVED"
    finalized = {
        claim_id: next(e for e in audit(client, claim_id) if e["event_type"] == "FINALIZED")
        for claim_id in ("CLM-E2E-15", "CLM-E2E-15-B")
    }
    assert finalized["CLM-E2E-15"]["payload"]["amounts_changed_since_review"] is False
    assert finalized["CLM-E2E-15-B"]["payload"]["amounts_changed_since_review"] is True
    assert (
        finalized["CLM-E2E-15-B"]["payload"]["accumulators"]["before"]
        == finalized["CLM-E2E-15"]["payload"]["accumulators"]["after"]
    )
    totals = [r.amounts.totals for r in (first.result, later.result)]
    shares = sum(t.deductible_cents + t.copay_cents + t.coinsurance_cents for t in totals)
    assert stored_accumulators(engine, member)["oop_met_cents"] == 80000 + shares


def test_a_second_review_of_the_same_claim_at_the_same_time_gets_409(
    api, load_case_reference, engine: Engine, monkeypatch
) -> None:
    process_case(api, load_case_reference, "E2E-14")
    locked, release = pause_after(monkeypatch, "_lock_claim", "first")
    first = Worker("first", finalize_with(engine, "CLM-E2E-14"))
    second = Worker("second", finalize_with(engine, "CLM-E2E-14"))

    first.start()
    assert locked.wait(30)
    second.start()
    wait_until_a_lock_is_awaited(engine)
    release.set()
    first.join(30)
    second.join(30)

    assert first.error is None and first.result.status.value == "FINAL_APPROVED"
    assert isinstance(second.error, InvalidTransition)  # the API answers 409
    with Session(engine) as session:
        statuses = session.scalars(
            text("SELECT status FROM claims WHERE claim_id = 'CLM-E2E-14'")
        ).all()
    assert statuses == ["FINAL_APPROVED"]


@pytest.mark.parametrize("lock", ["_lock_claim", "_lock_member"])
def test_a_lock_held_too_long_is_busy_not_a_hang(
    api, load_case_reference, engine: Engine, monkeypatch, lock: str
) -> None:
    process_case(api, load_case_reference, "E2E-14")
    monkeypatch.setattr(finalize, "LOCK_TIMEOUT", "100ms")
    locked, release = pause_after(monkeypatch, lock, "first")
    first = Worker("first", finalize_with(engine, "CLM-E2E-14"))
    first.start()
    assert locked.wait(30)
    try:
        with Session(engine) as session, pytest.raises(finalize.ReviewBusy):
            action = ReviewAction.model_validate(accept("CLM-E2E-14"))
            finalize_review(session, "CLM-E2E-14", action)
    finally:
        release.set()
        first.join(30)
    assert first.error is None
