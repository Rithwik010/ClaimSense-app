"""Audit search (D-AUD-1): the admin finds audit events across claims by claim, by who acted, by
event type and by date. Read only; the trail stays insert-only (§8.9)."""

from datetime import date, datetime, time, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.api.deps import AdminUser, SessionDep
from app.audit.events import SEARCH_LIMIT, EventType, search_events

router = APIRouter(prefix="/v1/audit", tags=["audit"])


class AuditSearchHit(BaseModel):
    id: int
    claim_id: str
    event_type: str
    actor: str
    payload: dict[str, Any]
    rules_version: str | None
    model_name: str | None
    prompt_version: str | None
    request_id: str | None = None
    created_at: datetime


class AuditSearch(BaseModel):
    events: list[AuditSearchHit]
    limit: int
    event_types: list[str]  # every type, for the page's filter


def _start(day: date | None) -> datetime | None:
    return datetime.combine(day, time.min).astimezone() if day else None


@router.get("/events")
def events(
    session: SessionDep,
    _admin: AdminUser,
    claim_id: Annotated[str | None, Query(max_length=48)] = None,
    actor: Annotated[str | None, Query(max_length=64)] = None,
    event_type: EventType | None = None,
    since: date | None = None,
    until: date | None = None,
    limit: Annotated[int, Query(ge=1, le=SEARCH_LIMIT)] = 200,
) -> AuditSearch:
    """Newest first. `since` and `until` are days, both included."""
    found = search_events(
        session,
        claim_id=(claim_id or "").strip() or None,
        actor=(actor or "").strip() or None,
        event_type=event_type.value if event_type else None,
        since=_start(since),
        until=_start(until + timedelta(days=1)) if until else None,
        limit=limit,
    )
    return AuditSearch(
        events=[AuditSearchHit.model_validate(e, from_attributes=True) for e in found],
        limit=limit,
        event_types=[t.value for t in EventType],
    )
