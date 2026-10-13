"""Claim lists for the UI (P5.5): every claim, or the claims of some statuses, newest first, with
the figures and reasons of each one's latest decision record (left out when it was stored under an
older contract and no longer validates). Each claim also carries what the lists search and filter
on (D-UI-6): its member ID, billing provider (NPI and name), its label key and, for a claim not
paid as billed, its reasons from the reason table."""

from dataclasses import dataclass, field
from datetime import date, datetime

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Claim, Provider
from app.domain.contracts import ClaimDecision, ClaimStatus, ReviewTier
from app.explain.codes import Adjustment, adjustments, procedure_codes
from app.explain.reasons import ClaimReason, claim_outcome, shown_reasons
from app.workflow.pipeline import latest_record


@dataclass(frozen=True)
class FailedRule:
    rule_id: str
    outcome: str
    reason_code: str | None
    detail: str
    line_no: int | None


@dataclass(frozen=True)
class ClaimSummary:
    claim_id: str
    status: ClaimStatus
    source_format: str
    received_date: date
    updated: datetime
    claim_decision: ClaimDecision | None
    review_tier: ReviewTier | None
    total_billed_cents: int | None
    total_allowed_cents: int | None
    plan_pays_cents: int | None
    failed_rules: list[FailedRule] = field(default_factory=list)
    # CARC/RARC codes of the record's DENY and REJECT reasons (D-CARC-2), for the lists' codes.
    adjustments: list[Adjustment] = field(default_factory=list)
    member_id: str = ""
    provider_npi: str | None = None  # the billing NPI as filed
    provider_name: str | None = None  # when the reference data knows it
    outcome: str = "NOT_PROCESSED"  # app.explain.reasons.claim_outcome
    reasons: list[ClaimReason] = field(default_factory=list)  # shown_reasons


def claim_summaries(
    session: Session, statuses: list[ClaimStatus] | None = None, provider_id: str | None = None
) -> list[ClaimSummary]:
    """`provider_id`: only the claims filed under it (a provider's own claims, D-AUTH-1)."""
    query = select(Claim).order_by(Claim.updated_at.desc(), Claim.claim_id)
    if statuses:
        query = query.where(Claim.status.in_([s.value for s in statuses]))
    if provider_id is not None:
        query = query.where(Claim.provider_id == provider_id)
    found = []
    for row in session.scalars(query):
        try:
            record = latest_record(session, row.claim_id)
        except ValidationError:  # a record stored under an older contract: listed without it
            record = None
        totals = record.amounts.totals if record and record.amounts else None
        npi = row.intake.get("billing_npi")
        npi = npi if isinstance(npi, str) else None
        provider = session.get(Provider, npi) if npi else None
        status = ClaimStatus(row.status)
        outcome = claim_outcome(status, record)
        found.append(
            ClaimSummary(
                claim_id=row.claim_id,
                status=status,
                source_format=row.source_format,
                received_date=row.received_date,
                updated=row.updated_at,
                claim_decision=record.claim_decision if record else None,
                review_tier=record.review_tier if record else None,
                total_billed_cents=totals.billed_cents if totals else None,
                total_allowed_cents=totals.allowed_cents if totals else None,
                plan_pays_cents=totals.plan_pays_cents if totals else None,
                failed_rules=[
                    FailedRule(r.rule_id, r.outcome.value, r.reason_code, r.detail, r.line_no)
                    for r in (record.rules_outcome.rule_results if record else [])
                    if not r.passed
                ],
                adjustments=adjustments(record, procedure_codes(row.intake)) if record else [],
                member_id=row.member_id,
                provider_npi=npi,
                provider_name=provider.name if provider else None,
                outcome=outcome,
                reasons=shown_reasons(outcome, record),
            )
        )
    return found
