"""Append-only audit trail (INSTRUCTIONS.md §8.9).

There is no update or delete code path, and a database trigger rejects both. Payloads carry IDs,
codes, decisions and amounts only: never names, addresses, dates of birth or clinical notes. Each
event keeps the ID of the API request that wrote it (D-OBS-1).
"""

from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import current_request_id
from app.db.models import AuditEvent
from app.domain.contracts import Versions

SYSTEM_ACTOR = "system"


class EventType(StrEnum):
    INTAKE_COMPLETED = "INTAKE_COMPLETED"
    RULES_EVALUATED = "RULES_EVALUATED"
    CONTEXT_ASSEMBLED = "CONTEXT_ASSEMBLED"
    SLM_RECOMMENDED = "SLM_RECOMMENDED"
    OUTPUT_INVALID = "OUTPUT_INVALID"
    CALCULATED = "CALCULATED"
    CALCULATION_FAILED = "CALCULATION_FAILED"
    EXPLANATION_BUILT = "EXPLANATION_BUILT"
    REVIEW_OPENED = "REVIEW_OPENED"
    REVIEW_ACCEPTED = "REVIEW_ACCEPTED"
    REVIEW_OVERRIDDEN = "REVIEW_OVERRIDDEN"
    FINALIZED = "FINALIZED"
    AUTO_OUTCOME = "AUTO_OUTCOME"
    FIELD_CORRECTED = "FIELD_CORRECTED"  # a provider corrected a box before processing (D-FIX-1)
    # Follow-ups after a decision (D-FUP-1, D-APL-1) and reviewer feedback (D-FBK-1).
    CLAIM_REOPENED = "CLAIM_REOPENED"  # back to its provider to correct or add documentation
    DOCUMENTATION_ADDED = "DOCUMENTATION_ADDED"  # the provider added to the clinical notes
    APPEAL_FILED = "APPEAL_FILED"  # a provider or member asked another reviewer to decide again
    APPEAL_DECIDED = "APPEAL_DECIDED"  # that reviewer finalized it: upheld or changed
    REVIEWER_FEEDBACK = "REVIEWER_FEEDBACK"  # a reviewer corrected the model's criteria


def record_event(
    session: Session,
    claim_id: str,
    event_type: EventType,
    payload: dict[str, Any],
    versions: Versions | None = None,
    actor: str = SYSTEM_ACTOR,
) -> None:
    session.add(
        AuditEvent(
            claim_id=claim_id,
            event_type=event_type.value,
            actor=actor,
            payload=payload,
            rules_version=versions.rules_version if versions else None,
            model_name=versions.model_name if versions else None,
            prompt_version=versions.prompt_version if versions else None,
            policy_versions=dict(versions.policy_versions) if versions else None,
            request_id=current_request_id(),
        )
    )
    session.flush()  # the id orders events; flush so it follows insertion order


SEARCH_LIMIT = 500


def search_events(
    session: Session,
    *,
    claim_id: str | None = None,
    actor: str | None = None,
    event_type: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    limit: int = 200,
) -> list[AuditEvent]:
    """Events across claims (the admin's audit search, D-AUD-1), newest first: any of a claim ID
    (exact), an actor (exact), an event type, and a time window [since, until)."""
    query = select(AuditEvent)
    if claim_id:
        query = query.where(AuditEvent.claim_id == claim_id)
    if actor:
        query = query.where(AuditEvent.actor == actor)
    if event_type:
        query = query.where(AuditEvent.event_type == event_type)
    if since is not None:
        query = query.where(AuditEvent.created_at >= since)
    if until is not None:
        query = query.where(AuditEvent.created_at < until)
    query = query.order_by(AuditEvent.id.desc()).limit(max(1, min(limit, SEARCH_LIMIT)))
    return list(session.scalars(query))


def list_events(session: Session, claim_id: str) -> list[AuditEvent]:
    return list(
        session.scalars(
            select(AuditEvent).where(AuditEvent.claim_id == claim_id).order_by(AuditEvent.id)
        )
    )
