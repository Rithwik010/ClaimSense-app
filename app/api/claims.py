"""Claim endpoints (INSTRUCTIONS.md §8.10). Walking skeleton (P1.5): JSON intake, processing, the
decision record and the audit trail.

Not yet: file upload (P5.1), the rendered explanation (P5.4), review (P5.3) and the role header.
"""

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_decision_model, get_retriever, get_session
from app.audit.events import list_events
from app.core.settings import Settings, get_settings
from app.db.models import Claim
from app.domain.contracts import (
    ClaimStatus,
    DecisionRecord,
    IntakeClaim,
    IntakeResult,
    SourceFormat,
)
from app.ml.client import DecisionModel, ModelUnavailable
from app.rag.retrieve import RetrievalUnavailable, Retriever
from app.workflow.pipeline import (
    ClaimNotFound,
    DuplicateClaim,
    PipelineError,
    intake_claim,
    latest_record,
    load_intake,
    process_claim,
)
from app.workflow.states import InvalidTransition

router = APIRouter(prefix="/v1/claims", tags=["claims"])

SessionDep = Annotated[Session, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


class ClaimView(BaseModel):
    claim_id: str
    status: ClaimStatus
    intake: IntakeResult
    record: DecisionRecord | None


class AuditEventView(BaseModel):
    id: int
    event_type: str
    actor: str
    payload: dict[str, Any]
    rules_version: str | None
    model_name: str | None
    prompt_version: str | None
    policy_versions: dict[str, Any] | None
    created_at: datetime


def _claim_row(session: Session, claim_id: str) -> Claim:
    row = session.get(Claim, claim_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"claim {claim_id} not found")
    return row


@router.post("/intake", status_code=status.HTTP_201_CREATED)
def intake(claim: IntakeClaim, session: SessionDep, settings: SettingsDep) -> IntakeResult:
    """A JSON claim: every field has confidence 1.0, so no field is listed (§8.2)."""
    result = IntakeResult(claim=claim, field_confidences={}, source_format=SourceFormat.JSON)
    try:
        intake_claim(session, result, settings.extraction_confidence_min)
    except DuplicateClaim as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    return result


@router.post("/{claim_id}/process")
def process(
    claim_id: str,
    session: SessionDep,
    settings: SettingsDep,
    model: Annotated[DecisionModel, Depends(get_decision_model)],
    retriever: Annotated[Retriever, Depends(get_retriever)],
) -> DecisionRecord:
    """Rules -> context (with retrieval) -> model -> calculator; returns the decision record."""
    try:
        return process_claim(session, claim_id, model, settings, retriever)
    except ClaimNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except InvalidTransition as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except PipelineError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    except (ModelUnavailable, RetrievalUnavailable) as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc


@router.get("/{claim_id}")
def get_claim(claim_id: str, session: SessionDep) -> ClaimView:
    row = _claim_row(session, claim_id)
    return ClaimView(
        claim_id=row.claim_id,
        status=ClaimStatus(row.status),
        intake=load_intake(row),
        record=latest_record(session, claim_id),
    )


@router.get("/{claim_id}/audit")
def get_audit(claim_id: str, session: SessionDep) -> list[AuditEventView]:
    _claim_row(session, claim_id)
    return [
        AuditEventView.model_validate(event, from_attributes=True)
        for event in list_events(session, claim_id)
    ]
