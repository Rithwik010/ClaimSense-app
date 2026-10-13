"""Review endpoints (INSTRUCTIONS.md §8.8, §8.10). The queue is for reviewers and admins (read
only, D-AUTH-1); the review actions themselves are in claims.py, for reviewers."""

from dataclasses import asdict
from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import StaffUser, get_session
from app.core.settings import Settings, get_settings
from app.domain.contracts import ClaimDecision, ReviewTier
from app.workflow.review import QueueSort, review_queue

router = APIRouter(prefix="/v1/review", tags=["review"])
SessionDep = Annotated[Session, Depends(get_session)]


class QueueItemView(BaseModel):
    claim_id: str
    review_tier: ReviewTier
    claim_decision: ClaimDecision | None
    total_allowed_cents: int | None
    received_date: date
    processed: datetime | None
    provider_npi: str | None
    provider_name: str | None
    service_date: date | None
    total_billed_cents: int | None
    lines: int
    flags: list[str]  # app.workflow.review.queue_flags
    member_id: str


@router.get("/queue")
def queue(
    session: SessionDep,
    settings: Annotated[Settings, Depends(get_settings)],
    _user: StaffUser,
    tier: ReviewTier | None = None,
    sort: QueueSort = QueueSort.TIER,
) -> list[QueueItemView]:
    """Claims awaiting review, most work first by default (FULL, STANDARD, QUICK; then the
    oldest), or oldest first with sort=processed; tier filters to one tier."""
    items = review_queue(
        session,
        tier,
        sort,
        confidence_min=settings.extraction_confidence_min,
        high_dollar_cents=settings.review_high_dollar_cents,
    )
    return [QueueItemView(**asdict(item)) for item in items]
