"""A provider corrects boxes of their claim before it is processed (D-FIX-1).

Only a claim read from our form (a digital PDF or a scan) and not processed yet (RECEIVED) can be
corrected: a JSON claim is read exactly. Each correction is checked and the claim rebuilt as the
form reading would have built it (`app.intake.corrections`); the claim then goes through the same
contract check as at intake (A-R8): a claim that still fails it only on what rules R01 to R03
report is kept with its errors (the rules reject it when it is processed), any other failure
refuses the correction and changes nothing.

A corrected box was entered by the provider, not read, so its confidence becomes 1.0, as every
field of a JSON claim (§8.2): rule H5 turns a rule failure into REJECT only for a field extracted
below the threshold. FIELD_CORRECTED records, with the provider as actor, each corrected box with
its confidence before, and the text before and after for every box but the patient's (names,
date of birth and address stay out of the audit trail, §8.9); the original file stays as sent.
"""

from collections.abc import Mapping
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit.events import EventType, record_event
from app.db.models import AuditEvent, Claim
from app.domain.contracts import ClaimStatus, IntakeResult, SourceFormat
from app.intake.corrections import (
    CORRECTABLE,
    CorrectionRefused,
    apply_corrections,
    form_text,
)
from app.intake.layout import ALL_PAGE_ONE_BOXES, NOTES_BOX, PRIMARY_PAID_BOXES
from app.rules.integrity import InvalidClaimData, contract_failures
from app.workflow.pipeline import (
    ClaimNotFound,
    IntakeRefused,
    filing_fields,
)
from app.workflow.states import InvalidTransition

FORM_SOURCES = frozenset({SourceFormat.DIGITAL_PDF, SourceFormat.SCANNED})
ENTERED = 1.0  # the confidence of a box the provider entered, as a JSON claim's fields
PERSONAL = "patient."  # boxes whose text the audit trail does not keep


class CorrectionNotAllowed(ValueError):
    """This claim cannot be corrected: it was not read from a form."""


@dataclass(frozen=True)
class FormBox:
    field: str  # the layout field path, e.g. "service_lines.0.rendering_npi"
    text: str | None  # as the form prints it; None: blank or unreadable
    confidence: float | None  # as read (1.0 once corrected); None: no reading kept
    correctable: bool
    corrected: bool  # the provider corrected it (FIELD_CORRECTED)


@dataclass(frozen=True)
class ClaimForm:
    """A claim read from our form, box by box in the form's order (D-FIX-1)."""

    claim_id: str
    status: str
    source_format: SourceFormat
    correctable: bool  # not processed yet and read from a form
    boxes: list[FormBox]
    contract_errors: list[str]  # what rules R01 to R03 will reject it for, if anything


BOX_ORDER = [box.field for box in [*ALL_PAGE_ONE_BOXES, NOTES_BOX, *PRIMARY_PAID_BOXES]]


def correctable(row: Claim) -> bool:
    return (
        row.status == ClaimStatus.RECEIVED.value and SourceFormat(row.source_format) in FORM_SOURCES
    )


def correct_claim(
    session: Session,
    claim_id: str,
    corrections: Mapping[str, str],
    actor: str,
    threshold: float,
) -> tuple[IntakeResult | None, list[str]]:
    """Make the corrections and audit them. Returns the claim (None while it fails the contract)
    and its contract errors, as intake does. Raises ClaimNotFound, InvalidTransition (not
    RECEIVED), CorrectionNotAllowed (a JSON claim), CorrectionRefused (a box that cannot be
    corrected or a text that fails its format check) or IntakeRefused (a claim the contract check
    refuses, or without a member ID or received date)."""
    row = session.get(Claim, claim_id, with_for_update=True)
    if row is None:
        raise ClaimNotFound(f"claim {claim_id} not found")
    if row.status != ClaimStatus.RECEIVED.value:
        raise InvalidTransition(
            f"claim {claim_id} is {row.status}; only a claim not processed yet can be corrected"
        )
    source = SourceFormat(row.source_format)
    if source not in FORM_SOURCES:
        raise CorrectionNotAllowed(
            "a JSON claim is read exactly, so it has nothing to correct; file a new claim instead"
        )
    if not corrections:
        raise IntakeRefused("no correction was sent")
    before = form_text(row.intake)
    data = apply_corrections(row.intake, corrections)
    _, member_id, received_date = filing_fields(data)
    try:
        claim, failures = contract_failures(data)
    except InvalidClaimData as exc:
        raise IntakeRefused(str(exc)) from exc
    errors = [f"{failure.rule_id}: {failure.detail}" for failure in failures]
    after = form_text(data)
    confidences = dict(row.field_confidences or {})
    changed = []
    for field in sorted(corrections):
        if before.get(field) == after.get(field):
            continue
        entry: dict[str, object] = {"field": field, "confidence_before": confidences.get(field)}
        if not field.startswith(PERSONAL):
            entry |= {"before": before.get(field), "after": after.get(field)}
        changed.append(entry)
        confidences[field] = ENTERED
    if changed:
        row.intake = claim.model_dump(mode="json") if claim else dict(data)
        row.field_confidences = confidences
        row.member_id = member_id
        row.received_date = received_date
        record_event(
            session,
            claim_id,
            EventType.FIELD_CORRECTED,
            {
                "fields": changed,
                "low_confidence_fields": sorted(
                    path for path, value in confidences.items() if value < threshold
                ),
                "contract_errors": errors,
            },
            actor=actor,
        )
        session.commit()
    else:
        session.rollback()
    result = (
        IntakeResult(claim=claim, field_confidences=confidences, source_format=source)
        if claim
        else None
    )
    return result, errors


def corrected_fields(session: Session, claim_id: str) -> set[str]:
    """The boxes the provider corrected, from the claim's FIELD_CORRECTED events."""
    payloads = session.scalars(
        select(AuditEvent.payload).where(
            AuditEvent.claim_id == claim_id,
            AuditEvent.event_type == EventType.FIELD_CORRECTED.value,
        )
    )
    return {
        entry["field"]
        for payload in payloads
        for entry in payload.get("fields", [])
        if isinstance(entry, dict) and isinstance(entry.get("field"), str)
    }


def claim_form(session: Session, row: Claim) -> ClaimForm:
    """The claim's boxes as the form prints them, each with its confidence, in the form's order:
    every box with a value or a reading (a box read but unreadable has a confidence and no text)."""
    texts = form_text(row.intake)
    confidences = row.field_confidences or {}
    can_correct = correctable(row)
    corrected = corrected_fields(session, row.claim_id)
    try:
        _, failures = contract_failures(row.intake)
        errors = [f"{failure.rule_id}: {failure.detail}" for failure in failures]
    except InvalidClaimData as exc:  # intake refuses such claims
        errors = [str(exc)]
    return ClaimForm(
        claim_id=row.claim_id,
        status=row.status,
        source_format=SourceFormat(row.source_format),
        correctable=can_correct,
        boxes=[
            FormBox(
                field=name,
                text=texts.get(name),
                confidence=confidences.get(name),
                correctable=can_correct and name in CORRECTABLE,
                corrected=name in corrected,
            )
            for name in BOX_ORDER
            if name in texts or name in confidences
        ],
        contract_errors=errors,
    )


__all__ = [
    "ClaimForm",
    "CorrectionNotAllowed",
    "CorrectionRefused",
    "FormBox",
    "claim_form",
    "correct_claim",
    "correctable",
]
