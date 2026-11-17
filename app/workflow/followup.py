"""Follow-ups after a decision (D-FUP-1, D-APL-1): what a provider or member can do once a claim is
decided, without changing a contract or touching money already counted.

- Correct and resubmit: a claim the automatic checks returned, denied or put on hold (REJECTED,
  DENIED_BY_RULE, PENDED_BY_RULE) goes back to RECEIVED for its provider to correct its boxes
  (any source, a JSON claim included) and process again. A claim rejected only as a duplicate has
  nothing to correct and is refused.
- Send documentation: a claim on hold for documentation (FINAL_PENDED with no approved line, or
  PENDED_BY_RULE) gets the provider's documentation added to its clinical notes and goes back to
  RECEIVED, to be processed again (rules, model, a reviewer).
- Appeal: a denied claim (FINAL_DENIED, every line denied) goes back to AWAITING_REVIEW for a
  reviewer other than the one who decided it; that reviewer's finalization decides the appeal
  (upheld when every line keeps its decision, changed otherwise). A claim is appealed once: the
  second reviewer's decision is the plan's last word here.

Each one reopens a claim that paid nothing: approved lines are the only ones that count toward the
member's accumulators and visits (D-REV-7, D-REV-8), and these claims have none, so processing or
finalizing again counts nothing twice. A claim with an approved line is never reopened. Rule
outcomes stay automatic: correcting the claim's data and running the rules again is not a person
overriding a rule. The audit trail keeps IDs, codes and counts only: the documentation and the
appeal's reason may hold clinical detail, so they are never in it (the appeal's reason stays in
the appeals table; the documentation in the claim's notes).
"""

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.audit.events import EventType, record_event
from app.core.settings import Settings
from app.db.models import Appeal, Claim, DecisionRecordRow
from app.domain.contracts import (
    ClaimStatus,
    DecisionRecord,
    FinalLineDecision,
    IntakeClaim,
    LineDecision,
)
from app.workflow.corrections import was_reopened
from app.workflow.pipeline import (
    ClaimNotFound,
    IntakeRefused,
    check_prompt_fits,
    explanation_built,
    latest_record,
)
from app.workflow.states import InvalidTransition, check_follow_up

CORRECTABLE = frozenset(
    {ClaimStatus.REJECTED, ClaimStatus.DENIED_BY_RULE, ClaimStatus.PENDED_BY_RULE}
)
DOCUMENTABLE = frozenset({ClaimStatus.FINAL_PENDED, ClaimStatus.PENDED_BY_RULE})
APPEALABLE = frozenset({ClaimStatus.FINAL_DENIED})
DUPLICATE = "RJ_DUPLICATE"
DOCUMENTATION_MAX = 8000  # characters added at a time
REASON_MIN, REASON_MAX = 10, 2000


class FollowUpRefused(ValueError):
    """The follow-up does not apply to this claim as it is (HTTP 409 or 422)."""


@dataclass(frozen=True)
class FollowUps:
    """What can be done with a claim now, for the dashboards' buttons."""

    correct: bool  # correct and resubmit
    documentation: bool  # send documentation
    appeal: bool  # appeal the decision
    reopened: bool  # reopened at least once (its boxes can be corrected, whatever the source)


@dataclass(frozen=True)
class AppealView:
    appeal_id: int
    status: str  # OPEN or DECIDED
    outcome: str | None  # UPHELD or CHANGED once decided
    filed_by: str
    filed_role: str
    filed_at: datetime
    previous_status: str
    previous_reviewer: str | None
    decided_by: str | None
    decided_at: datetime | None
    reason: str | None  # for reviewers and the person who filed it; None for anyone else


def _nothing_approved(record: DecisionRecord | None) -> bool:
    return record is not None and not any(
        line.decision is LineDecision.APPROVE for line in record.line_decisions
    )


def _only_duplicate(record: DecisionRecord | None) -> bool:
    failed = [r for r in (record.rules_outcome.rule_results if record else []) if not r.passed]
    return bool(failed) and all(r.reason_code == DUPLICATE for r in failed)


def was_appealed(session: Session, claim_id: str) -> bool:
    """Whether the claim has an appeal on file, open or decided (a claim is appealed once)."""
    return session.scalar(select(Appeal.id).where(Appeal.claim_id == claim_id).limit(1)) is not None


def open_appeal(session: Session, claim_id: str) -> Appeal | None:
    return session.scalar(
        select(Appeal).where(Appeal.claim_id == claim_id, Appeal.status == "OPEN")
    )


def follow_ups(session: Session, row: Claim, record: DecisionRecord | None) -> FollowUps:
    status = ClaimStatus(row.status)
    return FollowUps(
        correct=status in CORRECTABLE and not _only_duplicate(record),
        documentation=status in DOCUMENTABLE
        and (status is ClaimStatus.PENDED_BY_RULE or _nothing_approved(record)),
        appeal=status in APPEALABLE
        and _nothing_approved(record)
        and not was_appealed(session, row.claim_id),
        reopened=was_reopened(session, row.claim_id),
    )


def _locked(session: Session, claim_id: str) -> Claim:
    row = session.get(Claim, claim_id, with_for_update=True)
    if row is None:
        raise ClaimNotFound(f"claim {claim_id} not found")
    return row


def reopen_for_correction(session: Session, claim_id: str, actor: str) -> None:
    """A returned, rule-denied or rule-pended claim back to RECEIVED for its provider to correct
    and process again. Raises InvalidTransition (another status) or FollowUpRefused (a claim
    rejected only as a duplicate)."""
    row = _locked(session, claim_id)
    status = ClaimStatus(row.status)
    if status not in CORRECTABLE:
        raise InvalidTransition(
            f"claim {claim_id} is {status.value}; only a claim the checks returned, denied or "
            "put on hold can be corrected and resubmitted"
        )
    record = latest_record(session, claim_id)
    if _only_duplicate(record):
        raise FollowUpRefused(
            "this claim repeats a claim already on file, so there is nothing to correct"
        )
    check_follow_up(status, ClaimStatus.RECEIVED)
    row.status = ClaimStatus.RECEIVED.value
    record_event(
        session,
        claim_id,
        EventType.CLAIM_REOPENED,
        {"previous_status": status.value, "purpose": "correction"},
        actor=actor,
    )
    session.commit()


def add_documentation(
    session: Session, claim_id: str, actor: str, text: str, settings: Settings | None = None
) -> None:
    """The provider's documentation added to the claim's clinical notes. A claim on hold
    (FINAL_PENDED with no approved line, or PENDED_BY_RULE) goes back to RECEIVED; a claim
    already reopened and not processed yet takes it as it is. Raises InvalidTransition,
    FollowUpRefused (empty or too long, or the notes would no longer fit the model's prompt)."""
    added = text.strip()
    if not added:
        raise FollowUpRefused("the documentation is empty")
    if len(added) > DOCUMENTATION_MAX:
        raise FollowUpRefused(f"the documentation is longer than {DOCUMENTATION_MAX} characters")
    row = _locked(session, claim_id)
    status = ClaimStatus(row.status)
    record = latest_record(session, claim_id)
    reopening = status in DOCUMENTABLE
    if reopening and status is ClaimStatus.FINAL_PENDED and not _nothing_approved(record):
        raise FollowUpRefused(
            "a line of this claim was approved and paid, so it cannot be processed again; "
            "file a new claim for the services waiting for documentation"
        )
    if not reopening and not (status is ClaimStatus.RECEIVED and was_reopened(session, claim_id)):
        raise InvalidTransition(
            f"claim {claim_id} is {status.value}; documentation is added to a claim on hold"
        )
    day = datetime.now(UTC).date().isoformat()
    notes = str(row.intake.get("clinical_notes") or "")
    joined = f"{notes.rstrip()}\n\nADDITIONAL DOCUMENTATION ({day}):\n{added}".lstrip()
    data = {**row.intake, "clinical_notes": joined}
    if settings is not None:
        try:
            check_prompt_fits(session, IntakeClaim.model_validate(data), settings)
        except IntakeRefused as exc:
            raise FollowUpRefused(str(exc)) from exc
        except ValueError:
            pass  # a claim failing the contract is refused by the rules when processed
    row.intake = data
    if reopening:
        check_follow_up(status, ClaimStatus.RECEIVED)
        row.status = ClaimStatus.RECEIVED.value
        record_event(
            session,
            claim_id,
            EventType.CLAIM_REOPENED,
            {"previous_status": status.value, "purpose": "documentation"},
            actor=actor,
        )
    record_event(
        session,
        claim_id,
        EventType.DOCUMENTATION_ADDED,
        {"characters": len(added), "sha256": hashlib.sha256(added.encode()).hexdigest()},
        actor=actor,
    )
    session.commit()


def file_appeal(session: Session, claim_id: str, actor: str, role: str, reason: str) -> Appeal:
    """A denied claim back to AWAITING_REVIEW for another reviewer, with the appeal on file.
    The claim's latest decision record is saved again as a new version awaiting review (its final
    line decisions become the ones under appeal). Raises InvalidTransition or FollowUpRefused."""
    text = reason.strip()
    if not REASON_MIN <= len(text) <= REASON_MAX:
        raise FollowUpRefused(
            f"say why in {REASON_MIN} to {REASON_MAX} characters (what the decision missed)"
        )
    row = _locked(session, claim_id)
    status = ClaimStatus(row.status)
    if status not in APPEALABLE:
        raise InvalidTransition(
            f"claim {claim_id} is {status.value}; only a denied claim is appealed"
        )
    if open_appeal(session, claim_id) is not None:
        raise FollowUpRefused("this claim already has an appeal waiting for a reviewer")
    if was_appealed(session, claim_id):
        raise FollowUpRefused("this claim was appealed already; a claim is appealed once")
    record = latest_record(session, claim_id)
    if record is None or not _nothing_approved(record) or record.context_refs is None:
        raise FollowUpRefused("this claim has no denied recommendation to decide again")
    previous_reviewer = record.review.reviewer_id if record.review else None
    appeal = Appeal(
        claim_id=claim_id,
        filed_by=actor,
        filed_role=role,
        reason=text,
        previous_status=status.value,
        previous_reviewer=previous_reviewer,
    )
    session.add(appeal)
    session.flush()
    reopened = DecisionRecord.model_validate(
        {
            **record.model_dump(),
            "status": ClaimStatus.AWAITING_REVIEW,
            "review": None,
            "timestamps": {**record.timestamps.model_dump(), "finalized": None},
        }
    )
    version = session.scalar(
        select(func.coalesce(func.max(DecisionRecordRow.version), 0)).where(
            DecisionRecordRow.claim_id == claim_id
        )
    )
    session.add(
        DecisionRecordRow(
            claim_id=claim_id, version=version + 1, record=reopened.model_dump(mode="json")
        )
    )
    check_follow_up(status, ClaimStatus.AWAITING_REVIEW)
    row.status = ClaimStatus.AWAITING_REVIEW.value
    record_event(
        session,
        claim_id,
        EventType.APPEAL_FILED,
        {
            "appeal_id": appeal.id,
            "filed_role": role,
            "previous_status": status.value,
            "previous_reviewer": previous_reviewer,
        },
        record.versions,
        actor=actor,
    )
    explanation_built(session, row, reopened, version + 1)
    session.commit()
    return appeal


def check_appeal_reviewer(appeal: Appeal | None, reviewer: str) -> None:
    """An appeal is decided by another reviewer than the one who made the decision."""
    if appeal is not None and appeal.previous_reviewer == reviewer:
        raise FollowUpRefused(
            f"{reviewer} made the decision under appeal; another reviewer must decide the appeal"
        )


def decide_appeal(
    session: Session,
    appeal: Appeal,
    reviewer: str,
    before: list[FinalLineDecision],
    after: list[FinalLineDecision],
    acted: datetime,
    record: DecisionRecord,
) -> str:
    """The appeal decided by the reviewer's finalization: UPHELD when every line keeps its
    decision, CHANGED otherwise. Written in the finalization's transaction."""
    kept = {line.line_no: line.decision for line in before}
    outcome = (
        "UPHELD" if all(kept.get(line.line_no) == line.decision for line in after) else "CHANGED"
    )
    appeal.status = "DECIDED"
    appeal.outcome = outcome
    appeal.decided_by = reviewer
    appeal.decided_at = acted
    record_event(
        session,
        appeal.claim_id,
        EventType.APPEAL_DECIDED,
        {"appeal_id": appeal.id, "outcome": outcome},
        record.versions,
        actor=reviewer,
    )
    return outcome


def claim_appeals(
    session: Session, claim_id: str, viewer: str | None, staff: bool
) -> list[AppealView]:
    """The claim's appeals, newest first. The reason is shown to reviewers and admins and to the
    person who filed it."""
    rows = session.scalars(
        select(Appeal).where(Appeal.claim_id == claim_id).order_by(Appeal.id.desc())
    )
    return [
        AppealView(
            appeal_id=a.id,
            status=a.status,
            outcome=a.outcome,
            filed_by=a.filed_by,
            filed_role=a.filed_role,
            filed_at=a.filed_at,
            previous_status=a.previous_status,
            previous_reviewer=a.previous_reviewer if staff else None,
            decided_by=a.decided_by if staff else None,
            decided_at=a.decided_at,
            reason=a.reason if staff or a.filed_by == viewer else None,
        )
        for a in rows
    ]


def open_appeal_ids(session: Session) -> set[str]:
    """The claims with an appeal waiting for a reviewer (the queue's Appeal flag)."""
    return set(session.scalars(select(Appeal.claim_id).where(Appeal.status == "OPEN")))
