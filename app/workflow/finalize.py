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
   Visit-limited categories gain one visit per distinct date of service of their approved lines
   (D-REV-8).
4. Audit REVIEW_ACCEPTED or REVIEW_OVERRIDDEN (with the review time, from the acting reviewer's
   latest REVIEW_OPENED to the action, D-REV-6), then FINALIZED (final amounts, accumulators and
   visit usage before and after, whether the amounts differ from those shown at review, versions).
5. A new decision record version with the review, the final lines and amounts.
"""

from datetime import UTC, date, datetime

from sqlalchemy import func, select, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.audit.events import EventType, record_event
from app.calculator import CALCULATOR_VERSION
from app.calculator.engine import CalculationError
from app.core.logging import get_logger
from app.db import lookups
from app.db.models import Accumulator, Claim, Member, VisitUsage
from app.domain.contracts import (
    ClaimStatus,
    CostBreakdown,
    DecisionRecord,
    ReviewAction,
    ReviewActionType,
)
from app.review.actions import (
    ReviewRefused,
    changes,
    finalization,
    review_decisions,
    visit_counts,
)
from app.workflow.followup import (
    FollowUpRefused,
    check_appeal_reviewer,
    decide_appeal,
    open_appeal,
)
from app.workflow.pipeline import ClaimNotFound, _calculate, _save, latest_record, load_intake
from app.workflow.review import REVIEWER_ID_MAX, latest_opening
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


def _count_visits(
    session: Session, member_id: str, period_start: date, visits: dict[str, int]
) -> dict[str, dict[str, int]]:
    """Add the claim's visits to the stored visit usage; each category's count before and after.
    The table stores counts, not dates: a date already counted by another claim counts again
    (D-REV-8, a known limitation)."""
    usage = {}
    for category, added in visits.items():
        stored = session.get(VisitUsage, (member_id, period_start, category))
        if stored is None:
            stored = VisitUsage(
                member_id=member_id,
                period_start=period_start,
                benefit_category=category,
                visits_used=0,
            )
            session.add(stored)
        usage[category] = {"before": stored.visits_used, "after": stored.visits_used + added}
        stored.visits_used += added
    return usage


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
    if len(action.reviewer_id) > REVIEWER_ID_MAX:
        raise ReviewRefused(f"reviewer_id is longer than {REVIEWER_ID_MAX} characters")
    acted = session.scalar(select(func.now()))  # the action, on the database clock
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
    appeal = open_appeal(session, claim_id)  # D-APL-1: decided by another reviewer
    try:
        check_appeal_reviewer(appeal, action.reviewer_id)
    except FollowUpRefused as exc:
        raise ReviewRefused(str(exc)) from exc
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
    dates = {line.line_no: line.date_of_service for line in intake.claim.service_lines}
    visit_usage = _count_visits(
        session, row.member_id, period_start, visit_counts(record, decisions, dates)
    )

    reviewer = action.reviewer_id
    opened = latest_opening(session, claim_id, reviewer, acted)
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
            "opened_at": opened.isoformat() if opened else None,
            "review_seconds": int((acted - opened).total_seconds()) if opened else None,
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
            "visit_usage": visit_usage,
            "amounts_changed_since_review": bool(changed),
            "changed_totals": changed,
            "calculator_version": CALCULATOR_VERSION,
        },
        record.versions,
        actor=reviewer,
    )
    if appeal is not None:
        decide_appeal(session, appeal, reviewer, record.line_decisions, decisions, acted, record)
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
