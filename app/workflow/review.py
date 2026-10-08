"""Human decision review (INSTRUCTIONS.md §8.8): the review queue, and a reviewer opening a claim
(REVIEW_OPENED, the start of their review time, D-REV-6). Rule outcomes (REJECTED, DENIED_BY_RULE,
PENDED_BY_RULE) are final and never in the queue."""

from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit.events import EventType, record_event
from app.db.models import AuditEvent, Claim
from app.domain.contracts import ClaimDecision, ClaimStatus, ReviewTier
from app.workflow.pipeline import ClaimNotFound, latest_record
from app.workflow.states import InvalidTransition

REVIEWER_ID_MAX = 64  # audit_events.actor

TIER_ORDER = {ReviewTier.FULL: 0, ReviewTier.STANDARD: 1, ReviewTier.QUICK: 2}


class QueueSort(StrEnum):
    TIER = "tier"  # most work first (FULL, STANDARD, QUICK), then the oldest
    PROCESSED = "processed"  # the oldest first


@dataclass(frozen=True)
class QueueItem:
    claim_id: str
    review_tier: ReviewTier
    claim_decision: ClaimDecision | None
    total_allowed_cents: int | None  # None when the calculation failed
    received_date: date
    processed: datetime | None


def review_queue(
    session: Session, tier: ReviewTier | None = None, sort: QueueSort = QueueSort.TIER
) -> list[QueueItem]:
    """Every claim AWAITING_REVIEW, optionally of one tier."""
    items = []
    for row in session.scalars(
        select(Claim).where(Claim.status == ClaimStatus.AWAITING_REVIEW.value)
    ):
        record = latest_record(session, row.claim_id)
        if record is None or record.review_tier is None:
            continue
        if tier is not None and record.review_tier is not tier:
            continue
        items.append(
            QueueItem(
                claim_id=row.claim_id,
                review_tier=record.review_tier,
                claim_decision=record.claim_decision,
                total_allowed_cents=record.amounts.totals.allowed_cents if record.amounts else None,
                received_date=row.received_date,
                processed=record.timestamps.processed,
            )
        )
    oldest = datetime.min.replace(tzinfo=None)

    def processed(item: QueueItem) -> tuple[datetime, str]:
        return (item.processed.replace(tzinfo=None) if item.processed else oldest, item.claim_id)

    if sort is QueueSort.TIER:
        return sorted(items, key=lambda item: (TIER_ORDER[item.review_tier], *processed(item)))
    return sorted(items, key=processed)


def latest_opening(
    session: Session, claim_id: str, reviewer_id: str, before: datetime
) -> datetime | None:
    """When the reviewer last opened the claim before the given time (their latest REVIEW_OPENED),
    or None; other reviewers' openings do not count (D-REV-6)."""
    return session.scalar(
        select(AuditEvent.created_at)
        .where(
            AuditEvent.claim_id == claim_id,
            AuditEvent.event_type == EventType.REVIEW_OPENED.value,
            AuditEvent.actor == reviewer_id,
            AuditEvent.created_at <= before,
        )
        .order_by(AuditEvent.id.desc())
        .limit(1)
    )


def open_review(session: Session, claim_id: str, reviewer_id: str) -> datetime:
    """A reviewer opens a claim awaiting review: audited as REVIEW_OPENED with the reviewer as
    actor. Returns the time it was opened (the database clock, as every audit time)."""
    row = session.get(Claim, claim_id)
    if row is None:
        raise ClaimNotFound(f"claim {claim_id} not found")
    if row.status != ClaimStatus.AWAITING_REVIEW.value:
        raise InvalidTransition(
            f"claim {claim_id} is {row.status}; only AWAITING_REVIEW is reviewed"
        )
    record = latest_record(session, claim_id)
    record_event(
        session,
        claim_id,
        EventType.REVIEW_OPENED,
        {"reviewer_id": reviewer_id},
        record.versions if record else None,
        actor=reviewer_id,
    )
    opened = session.scalar(
        select(AuditEvent.created_at)
        .where(AuditEvent.claim_id == claim_id)
        .order_by(AuditEvent.id.desc())
        .limit(1)
    )
    session.commit()
    return opened
