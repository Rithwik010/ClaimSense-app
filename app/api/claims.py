"""Claim endpoints (INSTRUCTIONS.md §8.10): JSON intake, processing, review (P5.3), the decision
record and the audit trail. A JSON claim that fails the contract is still filed when rules R01 to
R03 report every error (A-R8); processing then rejects it (P2.5). The explanation is rendered from
the latest decision record only (P5.4, H15).

Who may do what (D-AUTH-1): a provider files and processes claims and reads their own (those filed
under their provider ID; another provider's claim is 404), with the decision only once it is final
(until then "IN_REVIEW"); a reviewer reads every claim and its audit trail and reviews, as
themselves; an admin reads everything and changes nothing.

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

from app.api.deps import (
    AnyUser,
    ProviderUser,
    ReviewerUser,
    StaffUser,
    get_decision_model,
    get_retriever,
    get_session,
)
from app.audit.events import list_events
from app.auth import Role
from app.auth.users import AuthUser
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
from app.explain.codes import adjustments, procedure_codes
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


class CodeView(BaseModel):
    kind: str  # CARC or RARC
    code: str
    description: str | None


class AdjustmentView(BaseModel):
    """External reason codes of a DENY or REJECT reason (D-CARC-2); line_no None: the claim."""

    line_no: int | None
    reason_code: str
    group_code: str
    codes: list[CodeView]
    billing_article: str | None
    lcds: list[str]


class ClaimView(BaseModel):
    claim_id: str
    status: ClaimStatus
    source_format: SourceFormat
    intake: IntakeResult | None  # None when the claim failed the contract at intake
    received: dict[str, Any]  # the claim as stored at intake
    field_confidences: dict[str, float]  # as stored at intake (none listed: 1.0)
    record: DecisionRecord | None
    adjustments: list[AdjustmentView] = []  # CARC/RARC of the record's DENY and REJECT reasons


# A provider sees a claim's decision once it is final; a rule outcome is final at once.
FINAL_STATUSES = frozenset(
    {
        ClaimStatus.REJECTED,
        ClaimStatus.DENIED_BY_RULE,
        ClaimStatus.PENDED_BY_RULE,
        ClaimStatus.FINAL_APPROVED,
        ClaimStatus.FINAL_PARTIAL,
        ClaimStatus.FINAL_DENIED,
        ClaimStatus.FINAL_PENDED,
    }
)
IN_REVIEW = "IN_REVIEW"


def provider_status(claim_status: ClaimStatus) -> str:
    """RECEIVED, IN_REVIEW (awaiting review) or the final status."""
    return IN_REVIEW if claim_status is ClaimStatus.AWAITING_REVIEW else claim_status.value


class ProviderClaimView(BaseModel):
    """A provider's own claim (D-AUTH-1): as filed, with its status; the decision record and its
    reason codes only once final, nothing of a recommendation still in review."""

    claim_id: str
    status: str  # RECEIVED, IN_REVIEW or a final status
    final: bool
    source_format: SourceFormat
    received: dict[str, Any]
    field_confidences: dict[str, float]
    filed_by: str | None
    record: DecisionRecord | None  # final claims only
    adjustments: list[AdjustmentView] = []  # final claims only
    # The pipeline steps the claim went through (audit event types in order, nothing else), for
    # the stage strip while it is in review.
    stages: list[str] = []


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


def _own_claim(session: Session, claim_id: str, user: AuthUser) -> Claim:
    """The claim, if this user may see it: a provider only their own (404 otherwise, the same
    answer as a claim that does not exist)."""
    row = _claim_row(session, claim_id)
    if user.role is Role.PROVIDER and row.provider_id != user.provider_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"claim {claim_id} not found")
    return row


def _adjustments(row: Claim, record: DecisionRecord | None) -> list[AdjustmentView]:
    return [
        AdjustmentView.model_validate(asdict(a))
        for a in (adjustments(record, procedure_codes(row.intake)) if record else [])
    ]


def _provider_view(session: Session, row: Claim) -> ProviderClaimView:
    claim_status = ClaimStatus(row.status)
    final = claim_status in FINAL_STATUSES
    record = latest_record(session, row.claim_id) if final else None
    return ProviderClaimView(
        claim_id=row.claim_id,
        status=provider_status(claim_status),
        final=final,
        source_format=SourceFormat(row.source_format),
        received=row.intake,
        field_confidences=row.field_confidences or {},
        filed_by=row.filed_by,
        record=record,
        adjustments=_adjustments(row, record),
        stages=[event.event_type for event in list_events(session, row.claim_id)],
    )


def _file(
    claim: dict[str, Any],
    confidences: dict[str, float],
    source: SourceFormat,
    session: Session,
    settings: Settings,
    user: AuthUser,
) -> IntakeResult | FiledWithErrors:
    try:
        result, errors = intake_claim_data(
            session,
            claim,
            confidences,
            source,
            settings.extraction_confidence_min,
            provider_id=user.provider_id,
            filed_by=user.username,
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
    claim: Annotated[dict[str, Any], Body()],
    session: SessionDep,
    settings: SettingsDep,
    user: ProviderUser,
) -> IntakeResult | FiledWithErrors:
    """A JSON claim: every field has confidence 1.0, so no field is listed (§8.2). A claim that
    fails the contract is filed with its errors when rules R01 to R03 report them all. Filed under
    the provider's ID."""
    return _file(claim, {}, SourceFormat.JSON, session, settings, user)


async def _body(request: Request) -> bytes:
    return await request.body()


@router.post("/intake/file", status_code=status.HTTP_201_CREATED)
def intake_file(
    data: Annotated[bytes, Depends(_body)],
    session: SessionDep,
    settings: SettingsDep,
    user: ProviderUser,
) -> IntakeResult | FiledWithErrors:
    """A claim file as the request body (P5.1): a JSON claim, a digital PDF of our form, or a
    scanned form (image-only PDF, PNG, JPEG or TIFF), read with each field's confidence (§8.2)."""
    try:
        claim, confidences, source = read_claim_file(data)
    except UnreadableFile as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    if not isinstance(claim, dict):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "the claim must be an object")
    return _file(claim, confidences, source, session, settings, user)


@router.post("/{claim_id}/process")
def process(
    claim_id: str,
    session: SessionDep,
    settings: SettingsDep,
    model: Annotated[DecisionModel, Depends(get_decision_model)],
    retriever: Annotated[Retriever, Depends(get_retriever)],
    user: ProviderUser,
) -> ProviderClaimView:
    """Rules -> context (with retrieval) -> model -> calculator, for one of the provider's own
    claims; answers with the provider's view (IN_REVIEW, or the rules' final outcome)."""
    row = _own_claim(session, claim_id, user)
    try:
        process_claim(session, claim_id, model, settings, retriever)
        session.refresh(row)
        return _provider_view(session, row)
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
    claim_id: str, body: ReviewOpen, session: SessionDep, user: ReviewerUser
) -> ReviewOpened:
    """A reviewer opens a claim awaiting review (REVIEW_OPENED): their review time runs from their
    latest opening to their action (D-REV-6). The reviewer ID must be the logged-in reviewer's."""
    _same_reviewer(body.reviewer_id, user)
    try:
        opened = open_review(session, claim_id, body.reviewer_id)
    except ClaimNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except InvalidTransition as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    return ReviewOpened(claim_id=claim_id, reviewer_id=body.reviewer_id, opened=opened)


@router.post("/{claim_id}/review")
def review(
    claim_id: str, action: ReviewAction, session: SessionDep, user: ReviewerUser
) -> DecisionRecord:
    """A reviewer's ACCEPT or OVERRIDE (§8.8); returns the finalized decision record. Reviewers
    never enter amounts: the calculator recomputes them against the stored accumulators. The
    action's reviewer ID must be the logged-in reviewer's, who is the audit actor."""
    _same_reviewer(action.reviewer_id, user)
    try:
        return finalize_review(session, claim_id, action)
    except ClaimNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except (InvalidTransition, ReviewBusy) as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except ReviewRefused as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc


def _same_reviewer(reviewer_id: str, user: AuthUser) -> None:
    if reviewer_id.strip() != user.username:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            f"the reviewer ID {reviewer_id!r} is not the logged-in reviewer ({user.username})",
        )


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
    adjustments: list[AdjustmentView] = []  # CARC/RARC of its DENY and REJECT reasons


class ProviderClaimSummary(BaseModel):
    """A provider's own claim in a list: the decision and amounts only once final."""

    claim_id: str
    status: str  # RECEIVED, IN_REVIEW or a final status
    final: bool
    source_format: SourceFormat
    received_date: date
    updated: datetime
    claim_decision: ClaimDecision | None
    total_billed_cents: int | None
    total_allowed_cents: int | None
    plan_pays_cents: int | None
    failed_rules: list[FailedRuleView]


def _provider_summary(item: Any) -> ProviderClaimSummary:
    final = item.status in FINAL_STATUSES
    return ProviderClaimSummary(
        claim_id=item.claim_id,
        status=provider_status(item.status),
        final=final,
        source_format=SourceFormat(item.source_format),
        received_date=item.received_date,
        updated=item.updated,
        claim_decision=item.claim_decision if final else None,
        total_billed_cents=item.total_billed_cents if final else None,
        total_allowed_cents=item.total_allowed_cents if final else None,
        plan_pays_cents=item.plan_pays_cents if final else None,
        failed_rules=[FailedRuleView.model_validate(asdict(r)) for r in item.failed_rules]
        if final
        else [],
    )


@router.get("")
def list_claims(
    session: SessionDep,
    user: AnyUser,
    status_in: Annotated[list[ClaimStatus] | None, Query(alias="status")] = None,
) -> list[ClaimSummaryView] | list[ProviderClaimSummary]:
    """Every claim, newest first, or those of the statuses given (?status=REJECTED&status=...),
    with the totals and failed rules of each one's latest decision record. A provider gets only
    their own claims, with the decision only once final."""
    if user.role is Role.PROVIDER:
        return [
            _provider_summary(item)
            for item in claim_summaries(session, status_in, provider_id=user.provider_id)
        ]
    return [
        ClaimSummaryView.model_validate(asdict(item))
        for item in claim_summaries(session, status_in)
    ]


@router.get("/{claim_id}")
def get_claim(claim_id: str, session: SessionDep, user: AnyUser) -> ClaimView | ProviderClaimView:
    row = _own_claim(session, claim_id, user)
    if user.role is Role.PROVIDER:
        return _provider_view(session, row)
    record = latest_record(session, claim_id)
    return ClaimView(
        claim_id=row.claim_id,
        status=ClaimStatus(row.status),
        source_format=SourceFormat(row.source_format),
        intake=load_intake(row),
        received=row.intake,
        field_confidences=row.field_confidences or {},
        record=record,
        adjustments=_adjustments(row, record),
    )


@router.get("/{claim_id}/audit")
def get_audit(claim_id: str, session: SessionDep, _user: StaffUser) -> list[AuditEventView]:
    _claim_row(session, claim_id)
    return [
        AuditEventView.model_validate(event, from_attributes=True)
        for event in list_events(session, claim_id)
    ]


@router.get("/{claim_id}/explanation", response_class=HTMLResponse, response_model=None)
def get_explanation(
    claim_id: str,
    session: SessionDep,
    user: AnyUser,
    fmt: Annotated[Literal["html", "text"], Query(alias="format")] = "html",
) -> HTMLResponse | PlainTextResponse:
    """The explanation of the claim's latest decision record: an HTML fragment or plain text. A
    provider gets it for their own claim once it is final (409 while it is in review)."""
    row = _own_claim(session, claim_id, user)
    if user.role is Role.PROVIDER and ClaimStatus(row.status) not in FINAL_STATUSES:
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"claim {claim_id} is in review; it is explained once final"
        )
    record = latest_record(session, claim_id)
    if record is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"claim {claim_id} has no decision yet")
    body = render(record, fmt, procedure_codes(row.intake))
    return HTMLResponse(body) if fmt == "html" else PlainTextResponse(body)
