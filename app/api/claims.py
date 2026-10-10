"""Claim endpoints (INSTRUCTIONS.md §8.10): JSON intake, processing, review (P5.3), the decision
record and the audit trail. A JSON claim that fails the contract is still filed when rules R01 to
R03 report every error (A-R8); processing then rejects it (P2.5). The review endpoints need the
reviewer role (X-Role header); the others do not check roles yet (P5.5). The explanation is
rendered from the latest decision record only (P5.4, H15).

`POST /v1/claims/intake/file` takes a claim file as the request body (P5.1): JSON, a digital PDF
or a scanned form, read with each field's confidence.
"""

from dataclasses import asdict
from datetime import date, datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, PlainTextResponse
from pydantic import BaseModel, Field, StringConstraints
from sqlalchemy.orm import Session

from app.api.deps import ReviewerRole, get_decision_model, get_retriever, get_session
from app.audit.events import list_events
from app.core.settings import Settings, get_settings
from app.db.models import Claim
from app.domain.contracts import (
    ClaimDecision,
    ClaimStatus,
    DecisionRecord,
    IntakeResult,
    ReviewAction,
    ReviewTier,
    SourceFormat,
)
from app.explain.render import render
from app.intake.files import UnreadableFile, read_claim_file
from app.ml.client import DecisionModel, ModelUnavailable
from app.rag.retrieve import RetrievalUnavailable, Retriever
from app.review.actions import ReviewRefused
from app.workflow.finalize import ReviewBusy, finalize_review
from app.workflow.listing import claim_summaries
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
    source_format: SourceFormat
    intake: IntakeResult | None  # None when the claim failed the contract at intake
    received: dict[str, Any]  # the claim as stored at intake
    field_confidences: dict[str, float]  # as stored at intake (none listed: 1.0)
    record: DecisionRecord | None


class FiledWithErrors(BaseModel):
    """A claim filed although it fails the contract; the rules will reject it (A-R8)."""

    claim_id: str
    status: ClaimStatus
    source_format: SourceFormat
    contract_errors: list[str]
    # A file upload also returns the claim as read and each field's confidence.
    received: dict[str, Any] | None = Field(default=None, exclude_if=lambda v: v is None)
    field_confidences: dict[str, float] | None = Field(default=None, exclude_if=lambda v: v is None)


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


def _file(
    claim: dict[str, Any],
    confidences: dict[str, float],
    source: SourceFormat,
    session: Session,
    settings: Settings,
) -> IntakeResult | FiledWithErrors:
    try:
        result, errors = intake_claim_data(
            session, claim, confidences, source, settings.extraction_confidence_min
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
        source_format=source,
        contract_errors=errors,
        received=claim if source is not SourceFormat.JSON else None,
        field_confidences=confidences if source is not SourceFormat.JSON else None,
    )


@router.post("/intake", status_code=status.HTTP_201_CREATED)
def intake(
    claim: Annotated[dict[str, Any], Body()], session: SessionDep, settings: SettingsDep
) -> IntakeResult | FiledWithErrors:
    """A JSON claim: every field has confidence 1.0, so no field is listed (§8.2). A claim that
    fails the contract is filed with its errors when rules R01 to R03 report them all."""
    return _file(claim, {}, SourceFormat.JSON, session, settings)


async def _body(request: Request) -> bytes:
    return await request.body()


@router.post("/intake/file", status_code=status.HTTP_201_CREATED)
def intake_file(
    data: Annotated[bytes, Depends(_body)], session: SessionDep, settings: SettingsDep
) -> IntakeResult | FiledWithErrors:
    """A claim file as the request body (P5.1): a JSON claim, a digital PDF of our form, or a
    scanned form (image-only PDF, PNG, JPEG or TIFF), read with each field's confidence (§8.2)."""
    try:
        claim, confidences, source = read_claim_file(data)
    except UnreadableFile as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    if not isinstance(claim, dict):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "the claim must be an object")
    return _file(claim, confidences, source, session, settings)


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


class FailedRuleView(BaseModel):
    rule_id: str
    outcome: str
    reason_code: str | None
    detail: str
    line_no: int | None


class ClaimSummaryView(BaseModel):
    claim_id: str
    status: ClaimStatus
    source_format: SourceFormat
    received_date: date
    updated: datetime
    claim_decision: ClaimDecision | None
    review_tier: ReviewTier | None
    total_billed_cents: int | None
    total_allowed_cents: int | None
    plan_pays_cents: int | None
    failed_rules: list[FailedRuleView]


@router.get("")
def list_claims(
    session: SessionDep,
    status_in: Annotated[list[ClaimStatus] | None, Query(alias="status")] = None,
) -> list[ClaimSummaryView]:
    """Every claim, newest first, or those of the statuses given (?status=REJECTED&status=...),
    with the totals and failed rules of each one's latest decision record."""
    return [
        ClaimSummaryView.model_validate(asdict(item))
        for item in claim_summaries(session, status_in)
    ]


@router.get("/{claim_id}")
def get_claim(claim_id: str, session: SessionDep) -> ClaimView:
    row = _claim_row(session, claim_id)
    return ClaimView(
        claim_id=row.claim_id,
        status=ClaimStatus(row.status),
        source_format=SourceFormat(row.source_format),
        intake=load_intake(row),
        received=row.intake,
        field_confidences=row.field_confidences or {},
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
