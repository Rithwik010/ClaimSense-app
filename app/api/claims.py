"""Claim endpoints (INSTRUCTIONS.md §8.10): JSON intake, processing, review (P5.3), the decision
record and the audit trail. A JSON claim that fails the contract is still filed when rules R01 to
R03 report every error (A-R8); processing then rejects it (P2.5). The review endpoints need the
reviewer role (X-Role header); the others do not check roles yet (P5.5). The explanation is
rendered from the latest decision record only (P5.4, H15).

Not yet: file upload (P5.1).
"""

from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from fastapi.responses import HTMLResponse, PlainTextResponse
from pydantic import BaseModel, StringConstraints
from sqlalchemy.orm import Session

from app.api.deps import ReviewerRole, get_decision_model, get_retriever, get_session
from app.audit.events import list_events
from app.core.settings import Settings, get_settings
from app.db.models import Claim
from app.domain.contracts import (
    ClaimStatus,
    DecisionRecord,
    IntakeResult,
    ReviewAction,
    SourceFormat,
)
from app.explain.render import render
from app.ml.client import DecisionModel, ModelUnavailable
from app.rag.retrieve import RetrievalUnavailable, Retriever
from app.review.actions import ReviewRefused
from app.workflow.finalize import ReviewBusy, finalize_review
from app.workflow.pipeline import (
    ClaimNotFound,
    DuplicateClaim,
    IntakeRefused,
    PipelineError,
    ReferenceDataUnavailable,
    intake_claim_data,
    latest_record,
    load_intake,
    process_claim,
)
from app.workflow.review import REVIEWER_ID_MAX, open_review
from app.workflow.states import InvalidTransition

router = APIRouter(prefix="/v1/claims", tags=["claims"])

SessionDep = Annotated[Session, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


class ClaimView(BaseModel):
    claim_id: str
    status: ClaimStatus
    intake: IntakeResult | None  # None when the claim failed the contract at intake
    received: dict[str, Any]  # the claim as stored at intake
    record: DecisionRecord | None


class FiledWithErrors(BaseModel):
    """A claim filed although it fails the contract; the rules will reject it (A-R8)."""

    claim_id: str
    status: ClaimStatus
    source_format: SourceFormat
    contract_errors: list[str]


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


class ReviewOpen(BaseModel):
    reviewer_id: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=REVIEWER_ID_MAX)
    ]


class ReviewOpened(BaseModel):
    claim_id: str
    reviewer_id: str
    opened: datetime


def _claim_row(session: Session, claim_id: str) -> Claim:
    row = session.get(Claim, claim_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"claim {claim_id} not found")
    return row


@router.post("/intake", status_code=status.HTTP_201_CREATED)
def intake(
    claim: Annotated[dict[str, Any], Body()], session: SessionDep, settings: SettingsDep
) -> IntakeResult | FiledWithErrors:
    """A JSON claim: every field has confidence 1.0, so no field is listed (§8.2). A claim that
    fails the contract is filed with its errors when rules R01 to R03 report them all."""
    try:
        result, errors = intake_claim_data(
            session, claim, {}, SourceFormat.JSON, settings.extraction_confidence_min
        )
    except IntakeRefused as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    except DuplicateClaim as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    if result is not None:
        return result
    return FiledWithErrors(
        claim_id=claim["claim_id"],
        status=ClaimStatus.RECEIVED,
        source_format=SourceFormat.JSON,
        contract_errors=errors,
    )


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
    except (ModelUnavailable, RetrievalUnavailable, ReferenceDataUnavailable) as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc


@router.post("/{claim_id}/review/open")
def open_for_review(
    claim_id: str, body: ReviewOpen, session: SessionDep, _role: ReviewerRole
) -> ReviewOpened:
    """A reviewer opens a claim awaiting review (REVIEW_OPENED): their review time runs from their
    latest opening to their action (D-REV-6)."""
    try:
        opened = open_review(session, claim_id, body.reviewer_id)
    except ClaimNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except InvalidTransition as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    return ReviewOpened(claim_id=claim_id, reviewer_id=body.reviewer_id, opened=opened)


@router.post("/{claim_id}/review")
def review(
    claim_id: str, action: ReviewAction, session: SessionDep, _role: ReviewerRole
) -> DecisionRecord:
    """A reviewer's ACCEPT or OVERRIDE (§8.8); returns the finalized decision record. Reviewers
    never enter amounts: the calculator recomputes them against the stored accumulators."""
    try:
        return finalize_review(session, claim_id, action)
    except ClaimNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except (InvalidTransition, ReviewBusy) as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except ReviewRefused as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc


@router.get("/{claim_id}")
def get_claim(claim_id: str, session: SessionDep) -> ClaimView:
    row = _claim_row(session, claim_id)
    return ClaimView(
        claim_id=row.claim_id,
        status=ClaimStatus(row.status),
        intake=load_intake(row),
        received=row.intake,
        record=latest_record(session, claim_id),
    )


@router.get("/{claim_id}/audit")
def get_audit(claim_id: str, session: SessionDep) -> list[AuditEventView]:
    _claim_row(session, claim_id)
    return [
        AuditEventView.model_validate(event, from_attributes=True)
        for event in list_events(session, claim_id)
    ]


@router.get("/{claim_id}/explanation", response_class=HTMLResponse, response_model=None)
def get_explanation(
    claim_id: str,
    session: SessionDep,
    fmt: Annotated[Literal["html", "text"], Query(alias="format")] = "html",
) -> HTMLResponse | PlainTextResponse:
    """The explanation of the claim's latest decision record: an HTML fragment or plain text."""
    _claim_row(session, claim_id)
    record = latest_record(session, claim_id)
    if record is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"claim {claim_id} has no decision yet")
    body = render(record, fmt)
    return HTMLResponse(body) if fmt == "html" else PlainTextResponse(body)
