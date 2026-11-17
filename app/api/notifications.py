"""Notifications (D-NTF-1): what happened lately on the claims a user works with, newest first,
read from the audit trail. Nothing is stored for them: which ones a user has seen is kept in their
own browser, by the newest event ID they opened.

- A provider: their claims' final outcomes (a reviewer's finalization or a rule outcome) and
  appeal decisions.
- A member: the same, on the claims in which they are the patient. A claim in review shows
  nothing until it is final (D-MEM-2): only final events are listed.
- A reviewer: claims ready for review (the model's recommendation, or output that failed the
  checks) and appeals filed.
- An admin: appeals filed and processing problems (output that failed the checks, a failed
  calculation).

Each item carries the claim ID, the event, the claim's outcome key when the event is a decision
(as the dashboards label it) and its time; never a payload's amounts, codes or notes.
"""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import select

from app.api.deps import LoggedInUser, SessionDep
from app.audit.events import EventType
from app.auth import Role
from app.db.models import AuditEvent, Claim
from app.domain.contracts import ClaimStatus
from app.explain.member import DUPLICATE, DUPLICATE_CODE
from app.explain.reasons import claim_outcome

router = APIRouter(prefix="/v1/notifications", tags=["notifications"])
LIMIT = 20

DECIDED = (EventType.FINALIZED, EventType.AUTO_OUTCOME, EventType.APPEAL_DECIDED)
EVENTS: dict[Role, tuple[EventType, ...]] = {
    Role.PROVIDER: DECIDED,
    Role.MEMBER: DECIDED,
    Role.REVIEWER: (EventType.SLM_RECOMMENDED, EventType.OUTPUT_INVALID, EventType.APPEAL_FILED),
    Role.ADMIN: (EventType.APPEAL_FILED, EventType.OUTPUT_INVALID, EventType.CALCULATION_FAILED),
}


class Notification(BaseModel):
    id: int  # the audit event's ID: higher is newer
    claim_id: str
    event_type: str
    outcome: str | None  # the decision's label key (APPROVED, DENIED, ...) for a final outcome
    appeal_outcome: str | None  # UPHELD or CHANGED for a decided appeal
    created_at: datetime


class Notifications(BaseModel):
    items: list[Notification]
    latest_id: int | None  # the newest event ID listed


def _outcome(event: AuditEvent, role: Role) -> str | None:
    value = event.payload.get("status") if isinstance(event.payload, dict) else None
    try:
        status = ClaimStatus(value) if isinstance(value, str) else None
    except ValueError:
        return None
    if status is None:
        return None
    reasons = event.payload.get("reason_codes") or []
    if (
        role is Role.MEMBER
        and status is ClaimStatus.REJECTED
        and reasons
        and all(code == DUPLICATE_CODE for code in reasons)
    ):
        return DUPLICATE  # as the member's claim reads (app/explain/member.py)
    # A pended claim with a paid line reads as partly approved on the claim itself; the event
    # names its status only, so it shows as pended here.
    return claim_outcome(status, None)


@router.get("")
def notifications(
    session: SessionDep,
    user: LoggedInUser,
    after: Annotated[int | None, Query(ge=0)] = None,
) -> Notifications:
    """Up to 20 of the user's notifications, newest first; `after`: only events newer than it."""
    kinds = [kind.value for kind in EVENTS[user.role]]
    query = (
        select(AuditEvent)
        .join(Claim, Claim.claim_id == AuditEvent.claim_id)
        .where(AuditEvent.event_type.in_(kinds))
    )
    if user.role is Role.PROVIDER:
        query = query.where(Claim.provider_id == user.provider_id)
    elif user.role is Role.MEMBER:
        query = query.where(Claim.member_id == user.member_id)
    if after is not None:
        query = query.where(AuditEvent.id > after)
    events = list(session.scalars(query.order_by(AuditEvent.id.desc()).limit(LIMIT)))
    items = [
        Notification(
            id=event.id,
            claim_id=event.claim_id,
            event_type=event.event_type,
            outcome=_outcome(event, user.role)
            if event.event_type in (EventType.FINALIZED.value, EventType.AUTO_OUTCOME.value)
            else None,
            appeal_outcome=event.payload.get("outcome")
            if event.event_type == EventType.APPEAL_DECIDED.value
            else None,
            created_at=event.created_at,
        )
        for event in events
    ]
    return Notifications(items=items, latest_id=items[0].id if items else None)
