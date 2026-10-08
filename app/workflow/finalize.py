"""Finalization (INSTRUCTIONS.md §8.8, §8.6): a reviewer's ACCEPT or OVERRIDE turns a claim awaiting
review into a FINAL_* claim, in one transaction.

1. Lock the claim row (a second review of the same claim waits, then finds it final: 409), then
   the member row (two finalizations for the same member run one after the other, even when the
   member has no accumulator row yet). A lock not granted within LOCK_TIMEOUT is ReviewBusy.
2. The final line decisions (app/review/actions.py) and the amounts, recomputed by the calculator
   against the stored accumulators read under the lock. A calculation that fails refuses the
   review: the cause must be fixed or the line pended (D-REV-5).
3. The stored accumulators for the claim's network and benefit year become the calculator's
   working accumulators after the claim (approved lines only).
4. Audit REVIEW_ACCEPTED or REVIEW_OVERRIDDEN, then FINALIZED (final amounts, accumulators before
   and after, whether the amounts differ from those shown at review, versions).
5. A new decision record version with the review, the final lines and amounts.
"""

from datetime import UTC, date, datetime

from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.audit.events import EventType, record_event
from app.calculator import CALCULATOR_VERSION
from app.calculator.engine import CalculationError
from app.core.logging import get_logger
from app.db import lookups
from app.db.models import Accumulator, Claim, Member
from app.domain.contracts import (
    ClaimStatus,
    CostBreakdown,
    DecisionRecord,
    ReviewAction,
    ReviewActionType,
)
from app.review.actions import ReviewRefused, changes, finalization, review_decisions
from app.workflow.pipeline import ClaimNotFound, _calculate, _save, latest_record, load_intake
from app.workflow.states import InvalidTransition

log = get_logger(__name__)

LOCK_TIMEOUT = "5s"


class ReviewBusy(RuntimeError):
    """Another finalization holds the claim or the member; try again (HTTP 409)."""


def _lock_claim(session: Session, claim_id: str) -> Claim | None:
    return session.get(Claim, claim_id, with_for_update=True)


def _lock_member(session: Session, member_id: str) -> Member | None:
    return session.get(Member, member_id, with_for_update=True)


def _changed_totals(shown: CostBreakdown | None, final: CostBreakdown) -> list[str]:
    if shown is None:
        return sorted(final.totals.model_dump())
    before, after = shown.totals.model_dump(), final.totals.model_dump()
    return sorted(name for name in after if before[name] != after[name])


def finalize_review(session: Session, claim_id: str, action: ReviewAction) -> DecisionRecord:
    session.execute(text(f"SET LOCAL lock_timeout = '{LOCK_TIMEOUT}'"))
    try:
        return _finalize(session, claim_id, action)
    except OperationalError as exc:
        session.rollback()
        if "lock timeout" in str(exc).lower():
            raise ReviewBusy(f"claim {claim_id} is being finalized; try again") from exc
        raise


def _finalize(session: Session, claim_id: str, action: ReviewAction) -> DecisionRecord:
    row = _lock_claim(session, claim_id)
    if row is None:
        raise ClaimNotFound(f"claim {claim_id} not found")
    if row.status != ClaimStatus.AWAITING_REVIEW.value:
        raise InvalidTransition(
            f"claim {claim_id} is {row.status}; only AWAITING_REVIEW is reviewed"
        )
    record = latest_record(session, claim_id)
    intake = load_intake(row)
    if record is None or record.context_refs is None or intake is None:
        raise ReviewRefused(f"claim {claim_id} has no recommendation to review")
    decisions = review_decisions(record, action)
    member = _lock_member(session, row.member_id)
    if member is None:
        raise ReviewRefused(f"member {row.member_id} not found")
    network = record.context_refs.network
    first_day = min(line.date_of_service for line in intake.claim.service_lines)
    period_start = lookups.benefit_year_start(first_day)
    try:
        calculation = _calculate(session, intake.claim, member, network, decisions)
    except CalculationError as exc:
        raise ReviewRefused(
            f"the amounts cannot be calculated ({exc}): fix the cause, for example a missing fee "
            "row (a data problem, not a coverage reason), or pend the line"
        ) from exc
    outcome = finalization(decisions, calculation)
    stored = session.get(Accumulator, (row.member_id, period_start, network.value))
    before = (stored.deductible_met_cents, stored.oop_met_cents) if stored else (0, 0)
    after = outcome.accumulators_after
    if outcome.accumulators_updated:
        if stored is None:
            stored = Accumulator(
                member_id=row.member_id,
                period_start=period_start,
                network=network.value,
                period_end=date(period_start.year, 12, 31),
            )
            session.add(stored)
        stored.deductible_met_cents = after.deductible_met_cents
        stored.oop_met_cents = after.oop_met_cents

    reviewer = action.reviewer_id
    event = (
        EventType.REVIEW_ACCEPTED
        if action.action is ReviewActionType.ACCEPT
        else EventType.REVIEW_OVERRIDDEN
    )
    record_event(
        session,
        claim_id,
        event,
        {
            "reviewer_id": reviewer,
            "timestamp": action.timestamp.isoformat(),
            "reason": action.reason,
            "changes": changes(record, action, decisions),
        },
        record.versions,
        actor=reviewer,
    )
    changed = _changed_totals(record.amounts, calculation.amounts)
    record_event(
        session,
        claim_id,
        EventType.FINALIZED,
        {
            "status": outcome.status.value,
            "claim_decision": outcome.claim_decision.value,
            "totals": calculation.amounts.totals.model_dump(),
            "accumulators": {
                "network": network.value,
                "period_start": period_start.isoformat(),
                "before": {"deductible_met_cents": before[0], "oop_met_cents": before[1]},
                "after": {
                    "deductible_met_cents": after.deductible_met_cents,
                    "oop_met_cents": after.oop_met_cents,
                }
                if outcome.accumulators_updated
                else {"deductible_met_cents": before[0], "oop_met_cents": before[1]},
            },
            "accumulators_updated": outcome.accumulators_updated,
            "amounts_changed_since_review": bool(changed),
            "changed_totals": changed,
            "calculator_version": CALCULATOR_VERSION,
        },
        record.versions,
        actor=reviewer,
    )
    final = DecisionRecord.model_validate(
        {
            **record.model_dump(),
            "status": outcome.status,
            "line_decisions": [d.model_dump() for d in decisions],
            "claim_decision": outcome.claim_decision,
            "amounts": calculation.amounts.model_dump(),
            "review": action.model_dump(),
            "timestamps": {**record.timestamps.model_dump(), "finalized": datetime.now(UTC)},
        }
    )
    _save(session, row, final)
    log.info(
        "claim_finalized",
        claim_id=claim_id,
        status=outcome.status.value,
        reviewer_id=reviewer,
        action=action.action.value,
    )
    return final
