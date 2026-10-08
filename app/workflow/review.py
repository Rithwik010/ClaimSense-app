"""Human decision review (INSTRUCTIONS.md §8.8): the review queue. Rule outcomes (REJECTED,
DENIED_BY_RULE, PENDED_BY_RULE) are final and never in it."""

from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Claim
from app.domain.contracts import ClaimDecision, ClaimStatus, ReviewTier
from app.workflow.pipeline import latest_record

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
