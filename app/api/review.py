"""Review endpoints (INSTRUCTIONS.md §8.8, §8.10). Every one needs the reviewer or admin role."""

from dataclasses import asdict
from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import ReviewerRole, get_session
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


@router.get("/queue")
def queue(
    session: SessionDep,
    _role: ReviewerRole,
    tier: ReviewTier | None = None,
    sort: QueueSort = QueueSort.TIER,
) -> list[QueueItemView]:
    """Claims awaiting review, most work first by default (FULL, STANDARD, QUICK; then the
    oldest), or oldest first with sort=processed; tier filters to one tier."""
    return [QueueItemView(**asdict(item)) for item in review_queue(session, tier, sort)]
