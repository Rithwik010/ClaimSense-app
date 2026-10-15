"""Append-only audit trail (INSTRUCTIONS.md §8.9).

There is no update or delete code path, and a database trigger rejects both. Payloads carry IDs,
codes, decisions and amounts only: never names, addresses, dates of birth or clinical notes. Each
event keeps the ID of the API request that wrote it (D-OBS-1).
"""

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


def list_events(session: Session, claim_id: str) -> list[AuditEvent]:
    return list(
        session.scalars(
            select(AuditEvent).where(AuditEvent.claim_id == claim_id).order_by(AuditEvent.id)
        )
    )
