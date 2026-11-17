"""Reviewer feedback as training data (D-FBK-1).

After finalizing a claim, its reviewer can correct the model's criteria on a line: the status each
criterion should have had and, for MET or NOT_MET, the quote from the clinical notes that shows it
(copied exactly, as the evidence guard checks quotes, D-EVID-1). Each correction is audited as
REVIEWER_FEEDBACK with IDs, statuses and, for a quote, only where it is in the notes (its start and
length in the notes with their spaces collapsed): the quote is clinical text, so it never enters the
audit trail; the export reads it back from the notes.

The admin's export turns the reviewed claims into examples in the decision dataset's format: the
system and user messages the model was given (rebuilt from the decision record, as the pipeline
builds them) and, as the answer, the model's own answer with the reviewer's corrections. Each line's
decision is derived from the corrected criteria, as the pipeline derives it (D-DEC-1); an example is
ready for training only when every derived decision is the decision the reviewer made, so an
override without the criteria that explain it is exported for reading, never as a label.
"""

import json
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit.events import EventType, record_event
from app.db.models import AuditEvent, Claim
from app.domain.contracts import (
    ClaimStatus,
    CriterionResult,
    CriterionStatus,
    DecisionRecord,
    SLMLine,
    SLMOutput,
)
from app.ml.derive import derive_line
from app.ml.prompt import NOT_APPLICABLE, NOT_DOCUMENTED, render_user_message, system_prompt
from app.workflow.pipeline import ClaimNotFound, latest_record, load_intake, prompt_lookups

QUOTED = frozenset({CriterionStatus.MET, CriterionStatus.NOT_MET})
FIXED_EVIDENCE = {
    CriterionStatus.NOT_DOCUMENTED: NOT_DOCUMENTED,
    CriterionStatus.NOT_APPLICABLE: NOT_APPLICABLE,
}
QUOTE_MAX = 600


class FeedbackRefused(ValueError):
    """The feedback does not fit the claim (HTTP 422)."""


@dataclass(frozen=True)
class CriterionCorrection:
    criterion_id: str
    status: CriterionStatus
    quote: str | None = None


@dataclass(frozen=True)
class LineFeedback:
    line_no: int
    criteria: list[CriterionCorrection]


def _final_reviewed(session: Session, claim_id: str) -> tuple[Claim, DecisionRecord]:
    row = session.get(Claim, claim_id)
    if row is None:
        raise ClaimNotFound(f"claim {claim_id} not found")
    record = latest_record(session, claim_id)
    if record is None or record.review is None or record.slm_output is None:
        raise FeedbackRefused(f"claim {claim_id} has no reviewed model recommendation")
    return row, record


def _same_text(text: str) -> str:
    return " ".join(text.split())


def record_feedback(
    session: Session, claim_id: str, reviewer: str, lines: list[LineFeedback]
) -> int:
    """Audit the reviewer's corrections of the model's criteria; returns how many criteria
    changed. Only the reviewer who finalized the claim may correct its criteria."""
    row, record = _final_reviewed(session, claim_id)
    if record.review is None or record.review.reviewer_id != reviewer:
        raise FeedbackRefused("only the reviewer who finalized the claim can correct its criteria")
    answers = {line.line_no: line for line in record.slm_output.lines} if record.slm_output else {}
    notes = _same_text(str(row.intake.get("clinical_notes") or ""))
    corrected: list[dict[str, Any]] = []
    for line in lines:
        answer = answers.get(line.line_no)
        if answer is None:
            raise FeedbackRefused(f"line {line.line_no} has no model recommendation")
        statuses = {c.criterion_id: c.status for c in answer.criteria}
        changed = []
        for correction in line.criteria:
            if correction.criterion_id not in statuses:
                raise FeedbackRefused(
                    f"line {line.line_no}: {correction.criterion_id} is not one of its criteria"
                )
            if correction.status in QUOTED:
                quote = _same_text(correction.quote or "")
                if not quote:
                    raise FeedbackRefused(
                        f"line {line.line_no}, {correction.criterion_id}: met or not met needs "
                        "the quote from the clinical notes that shows it"
                    )
                if len(quote) > QUOTE_MAX or quote not in notes:
                    raise FeedbackRefused(
                        f"line {line.line_no}, {correction.criterion_id}: copy the quote exactly "
                        "from the clinical notes"
                    )
            entry: dict[str, Any] = {
                "criterion_id": correction.criterion_id,
                "model_status": statuses[correction.criterion_id].value,
                "status": correction.status.value,
            }
            if correction.status in QUOTED:
                quote = _same_text(correction.quote or "")
                entry |= {"quote_start": notes.index(quote), "quote_length": len(quote)}
            elif correction.status is statuses[correction.criterion_id]:
                continue
            changed.append(entry)
        if changed:
            corrected.append({"line_no": line.line_no, "criteria": changed})
    if not corrected:
        raise FeedbackRefused("no criterion was changed")
    record_event(
        session,
        claim_id,
        EventType.REVIEWER_FEEDBACK,
        {"lines": corrected},
        record.versions,
        actor=reviewer,
    )
    session.commit()
    return sum(len(line["criteria"]) for line in corrected)


def _corrections(
    session: Session, claim_id: str, notes: str
) -> dict[tuple[int, str], tuple[CriterionStatus, str | None]]:
    """The latest status each corrected criterion got, by (line, criterion ID), with its quote read
    back from the notes (spaces collapsed) for MET and NOT_MET."""
    found: dict[tuple[int, str], tuple[CriterionStatus, str | None]] = {}
    for event in session.scalars(
        select(AuditEvent)
        .where(
            AuditEvent.claim_id == claim_id,
            AuditEvent.event_type == EventType.REVIEWER_FEEDBACK.value,
        )
        .order_by(AuditEvent.id)
    ):
        for line in event.payload.get("lines", []):
            for c in line.get("criteria", []):
                start, length = c.get("quote_start"), c.get("quote_length")
                quote = (
                    notes[int(start) : int(start) + int(length)]
                    if start is not None and length
                    else None
                )
                found[(int(line["line_no"]), str(c["criterion_id"]))] = (
                    CriterionStatus(c["status"]),
                    quote or None,
                )
    return found


def _reviewed_claims(session: Session) -> list[str]:
    """Claims with an override or reviewer feedback, oldest event first."""
    seen: dict[str, None] = {}
    for claim_id in session.scalars(
        select(AuditEvent.claim_id)
        .where(
            AuditEvent.event_type.in_(
                (EventType.REVIEW_OVERRIDDEN.value, EventType.REVIEWER_FEEDBACK.value)
            )
        )
        .order_by(AuditEvent.id)
    ):
        seen.setdefault(claim_id, None)
    return list(seen)


def training_examples(session: Session, policy_set: str) -> list[dict[str, Any]]:
    """One example per finalized claim a reviewer overrode or corrected (see the module text)."""
    examples = []
    for claim_id in _reviewed_claims(session):
        row = session.get(Claim, claim_id)
        record = latest_record(session, claim_id)
        intake = load_intake(row) if row is not None else None
        if (
            row is None
            or intake is None
            or record is None
            or record.review is None
            or record.slm_output is None
            or record.context_refs is None
            or ClaimStatus(row.status) is ClaimStatus.AWAITING_REVIEW
        ):
            continue
        corrections = _corrections(
            session, claim_id, _same_text(str(row.intake.get("clinical_notes") or ""))
        )
        final = {line.line_no: line.decision for line in record.line_decisions}
        contexts = {c.line_no: c for c in record.context_refs.lines}
        flags = {o.line_no: o.flags for o in record.rules_outcome.line_outcomes}
        lines: list[SLMLine] = []
        labels = []
        for answer in record.slm_output.lines:
            criteria = []
            changed = []
            for result in answer.criteria:
                status, quote = corrections.get(
                    (answer.line_no, result.criterion_id), (result.status, None)
                )
                if status is result.status and quote is None:
                    criteria.append(result)
                    continue
                evidence = FIXED_EVIDENCE.get(status) or quote or result.evidence
                criteria.append(
                    CriterionResult(
                        criterion_id=result.criterion_id, status=status, evidence=evidence
                    )
                )
                changed.append(
                    {
                        "criterion_id": result.criterion_id,
                        "model_status": result.status.value,
                        "status": status.value,
                    }
                )
            corrected = answer.model_copy(update={"criteria": criteria})
            context = contexts.get(answer.line_no)
            derived = derive_line(
                corrected, context.criteria if context else [], flags.get(answer.line_no, [])
            )
            lines.append(
                corrected.model_copy(
                    update={
                        "decision": derived.decision,
                        "reasons": derived.reasons,
                        "missing_information": derived.missing_information,
                    }
                )
            )
            labels.append(
                {
                    "line_no": answer.line_no,
                    "model_decision": answer.decision.value,
                    "final_decision": final[answer.line_no].value
                    if answer.line_no in final
                    else None,
                    "derived_decision": derived.decision.value,
                    "criteria_corrected": changed,
                }
            )
        ready = all(
            label["final_decision"] is None or label["derived_decision"] == label["final_decision"]
            for label in labels
        )
        version = record.versions.prompt_version or "decision_v3"
        answer_json = SLMOutput(lines=lines, complexity=record.slm_output.complexity).model_dump(
            mode="json"
        )
        examples.append(
            {
                "messages": [
                    {"role": "system", "content": system_prompt(version)},
                    {
                        "role": "user",
                        "content": render_user_message(
                            intake.claim,
                            record.rules_outcome,
                            record.context_refs,
                            prompt_lookups(session, intake.claim, policy_set),
                            version,
                        ),
                    },
                    {
                        "role": "assistant",
                        "content": json.dumps(answer_json, separators=(",", ":")),
                    },
                ],
                "metadata": {
                    "claim_id": claim_id,
                    "source": "reviewer",
                    "reviewer_id": record.review.reviewer_id,
                    "prompt_version": version,
                    "model_name": record.versions.model_name,
                    "rules_version": record.versions.rules_version,
                    "status": row.status,
                    "ready_for_training": ready,
                    "lines": labels,
                },
            }
        )
    return examples
