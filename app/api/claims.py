"""Claim endpoints (INSTRUCTIONS.md §8.10): JSON intake, processing, review (P5.3), the decision
record and the audit trail. A JSON claim that fails the contract is still filed when rules R01 to
R03 report every error (A-R8); processing then rejects it (P2.5). The explanation is rendered from
the latest decision record only (P5.4, H15).

Who may do what (D-AUTH-1): a provider files and processes claims and reads their own (those filed
under their provider ID; another provider's claim is 404), with the decision only once it is final
(until then "IN_REVIEW"); a reviewer reads every claim and its audit trail and reviews, as
themselves; an admin reads everything and changes nothing.

`POST /v1/claims/intake/file` takes a claim file as the request body (P5.1): JSON, a digital PDF
or a scanned form, read with each field's confidence. Both intake routes keep the original file
(JSON, PDF, PNG or JPEG) with the claim they create, named by the X-File-Name header when given
(D-DOC-1); `GET /v1/claims/{id}/document` serves it back to whoever may open the claim.

A provider's claim carries no rule IDs, internal reason codes, rule checks, criterion IDs, model
output, confidence scores or versions: once final, the provider's explanation and billing built
from the record and the reason table (D-UI-6). Reviewers and admins get the record, a summary and
each claim's reasons.
"""

from dataclasses import asdict
from datetime import date, datetime
from typing import Annotated, Any, Literal

from fastapi import (
    APIRouter,
    Body,
    Depends,
    Header,
    HTTPException,
    Query,
    Request,
    Response,
    status,
)
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
from app.db.models import DOCUMENT_TYPES, Claim, ClaimDocument, Plan
from app.domain.contracts import (
    ClaimDecision,
    ClaimStatus,
    DecisionRecord,
    IntakeResult,
    Network,
    ReviewAction,
    ReviewTier,
    SourceFormat,
)
from app.explain.codes import adjustments, procedure_codes
from app.explain.provider import ProviderExplanation, provider_explanation
from app.explain.reasons import ClaimReason, claim_outcome, provider_outcome
from app.explain.render import render
from app.explain.summary import ClaimSummary as Summary
from app.explain.summary import claim_summary
from app.intake.documents import original_file
from app.intake.files import UnreadableFile, read_claim_file
from app.ml.client import DecisionModel, ModelUnavailable
from app.rag.retrieve import RetrievalUnavailable, Retriever
from app.review.actions import ReviewRefused
from app.workflow.finalize import ReviewBusy, finalize_review
from app.workflow.listing import ClaimSummary, claim_summaries
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


class DocumentInfo(BaseModel):
    """The original file kept with a claim (D-DOC-1); GET /v1/claims/{id}/document serves it."""

    file_name: str
    content_type: str
    size_bytes: int


class ReasonView(BaseModel):
    """One reason a claim or line was not paid as billed (the reason table, D-UI-6). Reviewers
    and admins only: it names the internal code and the rule."""

    code: str
    rule_id: str | None
    line_no: int | None
    short: str


class ClaimView(BaseModel):
    claim_id: str
    status: ClaimStatus
    source_format: SourceFormat
    intake: IntakeResult | None  # None when the claim failed the contract at intake
    received: dict[str, Any]  # the claim as stored at intake
    field_confidences: dict[str, float]  # as stored at intake (none listed: 1.0)
    record: DecisionRecord | None
    adjustments: list[AdjustmentView] = []  # CARC/RARC of the record's DENY and REJECT reasons
    outcome: str  # the label key every dashboard shows (D-UI-6)
    summary: Summary  # a few short lines from the record (D-UI-6)
    document: DocumentInfo | None  # the original file, when one was kept (D-DOC-1)


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
    """A provider's own claim (D-AUTH-1): as filed, with its status and, once final, the
    provider's explanation and billing (D-UI-6). Nothing of a recommendation still in review, and
    no rule IDs, internal codes, rule checks, criterion IDs, model output, confidence scores or
    versions."""

    claim_id: str
    status: str  # RECEIVED, IN_REVIEW or a final status
    outcome: str  # the label key; a claim not processed yet is IN_REVIEW to its provider
    final: bool
    source_format: SourceFormat
    received: dict[str, Any]
    filed_by: str | None
    explanation: ProviderExplanation | None  # final claims only
    # The pipeline steps the claim went through (audit event types in order, nothing else), for
    # the stage strip.
    stages: list[str] = []
    document: DocumentInfo | None = None


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


def _document(session: Session, claim_id: str) -> DocumentInfo | None:
    document = session.get(ClaimDocument, claim_id)
    if document is None:
        return None
    return DocumentInfo(
        file_name=document.file_name,
        content_type=document.content_type,
        size_bytes=document.size_bytes,
    )


def _coinsurance_bps(session: Session, record: DecisionRecord) -> int | None:
    """The plan's coinsurance rate for the claim's network (the provider's coinsurance sentence)."""
    if record.context_refs is None:
        return None
    plan = session.get(Plan, record.context_refs.plan_id)
    if plan is None:
        return None
    if record.context_refs.network is Network.IN_NETWORK:
        return plan.inn_coinsurance_bps
    return plan.oon_coinsurance_bps


def _provider_view(session: Session, row: Claim, settings: Settings) -> ProviderClaimView:
    claim_status = ClaimStatus(row.status)
    final = claim_status in FINAL_STATUSES
    record = latest_record(session, row.claim_id) if final else None
    outcome = claim_outcome(claim_status, record)
    return ProviderClaimView(
        claim_id=row.claim_id,
        status=provider_status(claim_status),
        outcome=provider_outcome(outcome) if final else "IN_REVIEW",
        final=final,
        source_format=SourceFormat(row.source_format),
        received=row.intake,
        filed_by=row.filed_by,
        explanation=provider_explanation(
            outcome,
            record,
            row.intake,
            row.field_confidences or {},
            settings.extraction_confidence_min,
            _coinsurance_bps(session, record),
        )
        if record is not None
        else None,
        stages=[event.event_type for event in list_events(session, row.claim_id)],
        document=_document(session, row.claim_id),
    )


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


FILE_NAME_HEADER = "X-File-Name"  # the uploaded file's name, percent-encoded (D-DOC-1)


async def _body(request: Request) -> bytes:
    return await request.body()


def _file(
    claim: dict[str, Any],
    confidences: dict[str, float],
    source: SourceFormat,
    session: Session,
    settings: Settings,
    user: AuthUser,
    data: bytes,
    file_name: str | None,
) -> IntakeResult | FiledWithErrors:
    claim_id = claim.get("claim_id")
    try:
        result, errors = intake_claim_data(
            session,
            claim,
            confidences,
            source,
            settings.extraction_confidence_min,
            provider_id=user.provider_id,
            filed_by=user.username,
            document=original_file(data, file_name, claim_id if isinstance(claim_id, str) else ""),
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


FileName = Annotated[str | None, Header(alias=FILE_NAME_HEADER)]


@router.post("/intake", status_code=status.HTTP_201_CREATED)
def intake(
    claim: Annotated[dict[str, Any], Body()],
    data: Annotated[bytes, Depends(_body)],
    session: SessionDep,
    settings: SettingsDep,
    user: ProviderUser,
    file_name: FileName = None,
) -> IntakeResult | FiledWithErrors:
    """A JSON claim: every field has confidence 1.0, so no field is listed (§8.2). A claim that
    fails the contract is filed with its errors when rules R01 to R03 report them all. Filed under
    the provider's ID, with the body as sent kept as its original file."""
    return _file(claim, {}, SourceFormat.JSON, session, settings, user, data, file_name)


@router.post("/intake/file", status_code=status.HTTP_201_CREATED)
def intake_file(
    data: Annotated[bytes, Depends(_body)],
    session: SessionDep,
    settings: SettingsDep,
    user: ProviderUser,
    file_name: FileName = None,
) -> IntakeResult | FiledWithErrors:
    """A claim file as the request body (P5.1): a JSON claim, a digital PDF of our form, or a
    scanned form (image-only PDF, PNG, JPEG or TIFF), read with each field's confidence (§8.2).
    The file is kept with the claim it creates (JSON, PDF, PNG or JPEG; D-DOC-1)."""
    try:
        claim, confidences, source = read_claim_file(data)
    except UnreadableFile as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    if not isinstance(claim, dict):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "the claim must be an object")
    return _file(claim, confidences, source, session, settings, user, data, file_name)


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
        return _provider_view(session, row, settings)
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
    # What the lists search and filter on (D-UI-6).
    member_id: str
    provider_npi: str | None
    provider_name: str | None
    outcome: str
    reasons: list[ReasonView]  # rejected, denied, pended and partly approved claims only


class ProviderClaimSummary(BaseModel):
    """A provider's own claim in a list: the decision and amounts only once final; no rule IDs
    or internal codes (D-UI-6)."""

    claim_id: str
    status: str  # RECEIVED, IN_REVIEW or a final status
    outcome: str  # the label key; IN_REVIEW until final
    final: bool
    source_format: SourceFormat
    received_date: date
    updated: datetime
    claim_decision: ClaimDecision | None
    total_billed_cents: int | None
    total_allowed_cents: int | None
    plan_pays_cents: int | None


def _reason_views(reasons: list[ClaimReason]) -> list[ReasonView]:
    return [
        ReasonView(code=r.code, rule_id=r.rule_id, line_no=r.line_no, short=r.text.short)
        for r in reasons
    ]


def _provider_summary(item: ClaimSummary) -> ProviderClaimSummary:
    final = item.status in FINAL_STATUSES
    return ProviderClaimSummary(
        claim_id=item.claim_id,
        status=provider_status(item.status),
        outcome=provider_outcome(item.outcome) if final else "IN_REVIEW",
        final=final,
        source_format=SourceFormat(item.source_format),
        received_date=item.received_date,
        updated=item.updated,
        claim_decision=item.claim_decision if final else None,
        total_billed_cents=item.total_billed_cents if final else None,
        total_allowed_cents=item.total_allowed_cents if final else None,
        plan_pays_cents=item.plan_pays_cents if final else None,
    )


def _staff_summary(item: ClaimSummary) -> ClaimSummaryView:
    fields = asdict(item)
    fields["reasons"] = _reason_views(item.reasons)
    return ClaimSummaryView.model_validate(fields)


@router.get("")
def list_claims(
    session: SessionDep,
    user: AnyUser,
    status_in: Annotated[list[ClaimStatus] | None, Query(alias="status")] = None,
) -> list[ClaimSummaryView] | list[ProviderClaimSummary]:
    """Every claim, newest first, or those of the statuses given (?status=REJECTED&status=...),
    with the totals, failed rules and reasons of each one's latest decision record. A provider
    gets only their own claims, with the decision only once final."""
    if user.role is Role.PROVIDER:
        return [
            _provider_summary(item)
            for item in claim_summaries(session, status_in, provider_id=user.provider_id)
        ]
    return [_staff_summary(item) for item in claim_summaries(session, status_in)]


@router.get("/{claim_id}")
def get_claim(
    claim_id: str, session: SessionDep, settings: SettingsDep, user: AnyUser
) -> ClaimView | ProviderClaimView:
    row = _own_claim(session, claim_id, user)
    if user.role is Role.PROVIDER:
        return _provider_view(session, row, settings)
    record = latest_record(session, claim_id)
    claim_status = ClaimStatus(row.status)
    return ClaimView(
        claim_id=row.claim_id,
        status=claim_status,
        source_format=SourceFormat(row.source_format),
        intake=load_intake(row),
        received=row.intake,
        field_confidences=row.field_confidences or {},
        record=record,
        adjustments=_adjustments(row, record),
        outcome=claim_outcome(claim_status, record),
        summary=claim_summary(
            claim_status,
            record,
            row.intake,
            row.field_confidences or {},
            settings.extraction_confidence_min,
            settings.review_high_dollar_cents,
        ),
        document=_document(session, claim_id),
    )


@router.get("/{claim_id}/document", response_class=Response, response_model=None)
def get_document(claim_id: str, session: SessionDep, user: AnyUser) -> Response:
    """The original file the claim was filed from (D-DOC-1), shown inline: a provider's own claims
    only (another provider's is 404), every claim for reviewers and admins. 404 when no file was
    kept (a TIFF scan, or a claim filed before files were kept)."""
    _own_claim(session, claim_id, user)
    document = session.get(ClaimDocument, claim_id)
    if document is None or document.content_type not in DOCUMENT_TYPES:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"claim {claim_id} has no original file")
    return Response(
        content=document.content,
        media_type=document.content_type,
        headers={
            "Content-Disposition": f'inline; filename="{document.file_name}"',
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
        },
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
