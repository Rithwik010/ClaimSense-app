"""Human decision review (INSTRUCTIONS.md §8.8): the review queue, and a reviewer opening a claim
(REVIEW_OPENED, the start of their review time, D-REV-6). Rule outcomes (REJECTED, DENIED_BY_RULE,
PENDED_BY_RULE) are final and never in the queue."""

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit.events import EventType, record_event
from app.db.models import AuditEvent, Claim, Provider
from app.domain.contracts import ClaimDecision, ClaimStatus, DecisionRecord, ReviewTier
from app.ml.evidence import GUARD
from app.workflow.pipeline import ClaimNotFound, latest_record
from app.workflow.states import InvalidTransition

REVIEWER_ID_MAX = 64  # audit_events.actor

TIER_ORDER = {ReviewTier.FULL: 0, ReviewTier.STANDARD: 1, ReviewTier.QUICK: 2}


class QueueSort(StrEnum):
    TIER = "tier"  # most work first (FULL, STANDARD, QUICK), then the oldest
    PROCESSED = "processed"  # the oldest first


@dataclass(frozen=True)
class QueueItem:
    claim_id: str
    review_tier: ReviewTier
    claim_decision: ClaimDecision | None
    total_allowed_cents: int | None  # None when the calculation failed
    received_date: date
    processed: datetime | None
    # For the queue's columns (P8 UI pass): read from the claim as filed and its latest record.
    provider_npi: str | None = None
    provider_name: str | None = None  # the billing provider, when the reference data knows it
    service_date: date | None = None  # the first date of service
    total_billed_cents: int | None = None
    lines: int = 0
    flags: list[str] = field(default_factory=list)


def queue_flags(
    record: DecisionRecord, confidences: dict[str, float], confidence_min: float, high_dollar: int
) -> list[str]:
    """What a reviewer should look at, as facts the record holds (computed by code, not a model
    score): an unusable model answer, a quote not in the note, a calculation that failed,
    low-confidence fields, a high dollar amount, a line a rule decided."""
    flags = []
    if record.slm_output is None:
        flags.append("MODEL_ANSWER_UNUSABLE")
    if any(e.startswith(GUARD) for e in record.output_errors):
        flags.append("QUOTE_NOT_IN_NOTE")
    if any(e.startswith("CALCULATION_FAILED") for e in record.output_errors):
        flags.append("CALCULATION_FAILED")
    if any(value < confidence_min for value in confidences.values()):
        flags.append("LOW_CONFIDENCE_FIELDS")
    if record.amounts and record.amounts.totals.allowed_cents >= high_dollar:
        flags.append("HIGH_DOLLAR")
    if any(line.source == "RULE" for line in record.line_decisions):
        flags.append("LINE_DECIDED_BY_RULE")
    return flags


def review_queue(
    session: Session,
    tier: ReviewTier | None = None,
    sort: QueueSort = QueueSort.TIER,
    confidence_min: float = 0.85,
    high_dollar_cents: int = 100_000,
) -> list[QueueItem]:
    """Every claim AWAITING_REVIEW, optionally of one tier (a decision record stored under an older
    contract, which no longer validates, is left out)."""
    items = []
    for row in session.scalars(
        select(Claim).where(Claim.status == ClaimStatus.AWAITING_REVIEW.value)
    ):
        try:
            record = latest_record(session, row.claim_id)
        except ValidationError:  # stored under an older contract: it cannot be reviewed here
            continue
        if record is None or record.review_tier is None:
            continue
        if tier is not None and record.review_tier is not tier:
            continue
        claim = row.intake
        lines = [line for line in claim.get("service_lines") or [] if isinstance(line, dict)]
        dates = sorted(str(ln["date_of_service"]) for ln in lines if ln.get("date_of_service"))
        npi = claim.get("billing_npi")
        provider = session.get(Provider, npi) if isinstance(npi, str) else None
        items.append(
            QueueItem(
                claim_id=row.claim_id,
                review_tier=record.review_tier,
                claim_decision=record.claim_decision,
                total_allowed_cents=record.amounts.totals.allowed_cents if record.amounts else None,
                received_date=row.received_date,
                processed=record.timestamps.processed,
                provider_npi=npi if isinstance(npi, str) else None,
                provider_name=provider.name if provider else None,
                service_date=date.fromisoformat(dates[0]) if dates else None,
                total_billed_cents=record.amounts.totals.billed_cents
                if record.amounts
                else sum(int(line.get("charge_cents") or 0) for line in lines),
                lines=len(lines),
                flags=queue_flags(
                    record, row.field_confidences or {}, confidence_min, high_dollar_cents
                ),
            )
        )
    oldest = datetime.min.replace(tzinfo=None)

    def processed(item: QueueItem) -> tuple[datetime, str]:
        return (item.processed.replace(tzinfo=None) if item.processed else oldest, item.claim_id)

    if sort is QueueSort.TIER:
        return sorted(items, key=lambda item: (TIER_ORDER[item.review_tier], *processed(item)))
    return sorted(items, key=processed)


def latest_opening(
    session: Session, claim_id: str, reviewer_id: str, before: datetime
) -> datetime | None:
    """When the reviewer last opened the claim before the given time (their latest REVIEW_OPENED),
    or None; other reviewers' openings do not count (D-REV-6)."""
    return session.scalar(
        select(AuditEvent.created_at)
        .where(
            AuditEvent.claim_id == claim_id,
            AuditEvent.event_type == EventType.REVIEW_OPENED.value,
            AuditEvent.actor == reviewer_id,
            AuditEvent.created_at <= before,
        )
        .order_by(AuditEvent.id.desc())
        .limit(1)
    )


def open_review(session: Session, claim_id: str, reviewer_id: str) -> datetime:
    """A reviewer opens a claim awaiting review: audited as REVIEW_OPENED with the reviewer as
    actor. Returns the time it was opened (the database clock, as every audit time)."""
    row = session.get(Claim, claim_id)
    if row is None:
        raise ClaimNotFound(f"claim {claim_id} not found")
    if row.status != ClaimStatus.AWAITING_REVIEW.value:
        raise InvalidTransition(
            f"claim {claim_id} is {row.status}; only AWAITING_REVIEW is reviewed"
        )
    record = latest_record(session, claim_id)
    record_event(
        session,
        claim_id,
        EventType.REVIEW_OPENED,
        {"reviewer_id": reviewer_id},
        record.versions if record else None,
        actor=reviewer_id,
    )
    opened = session.scalar(
        select(AuditEvent.created_at)
        .where(AuditEvent.claim_id == claim_id)
        .order_by(AuditEvent.id.desc())
        .limit(1)
    )
    session.commit()
    return opened
