"""Live numbers from the claims on file (D-QLT-1): how reviewers use the model's recommendations
(the admin's Review quality page) and the Overview's money, times and trend. Read only; every
number comes from the decision records, the audit trail and the appeals as stored. Rates are
integer basis points (10000 = 100%), as everywhere else in the project.

A review is a decision record awaiting review followed by the record its reviewer finalized (an
appeal's second review counts as another review). A model line is a line the model or the output
validation decided; it was overridden when the reviewer's finalization gave it source REVIEWER.
"""

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from statistics import median

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit.events import EventType
from app.calculator.progress import total_cents
from app.db.models import Appeal, AuditEvent, Claim, DecisionRecordRow
from app.domain.contracts import ClaimStatus, DecisionRecord
from app.workflow.listing import claim_summaries

MODEL_SOURCES = ("MODEL", "VALIDATION")
REVIEWED_STATUSES = frozenset(
    {
        ClaimStatus.FINAL_APPROVED,
        ClaimStatus.FINAL_PARTIAL,
        ClaimStatus.FINAL_PENDED,
        ClaimStatus.FINAL_DENIED,
    }
)
DECIDED_EVENTS = (EventType.FINALIZED.value, EventType.AUTO_OUTCOME.value)


def bps(part: int, whole: int) -> int | None:
    """part of whole in basis points, or None for nothing to divide."""
    return part * 10000 // whole if whole else None


def _seconds(values: list[float]) -> dict[str, float | int | None]:
    ordered = sorted(values)
    return {
        "count": len(ordered),
        "median": median(ordered) if ordered else None,
        "p90": ordered[min(len(ordered) - 1, (len(ordered) * 9) // 10)] if ordered else None,
    }


@dataclass
class _Tally:
    lines: int = 0
    overridden: int = 0
    reviews: int = 0
    seconds: list[float] = field(default_factory=list)

    def view(self) -> dict[str, object]:
        return {
            "reviews": self.reviews,
            "lines": self.lines,
            "overridden": self.overridden,
            "override_rate_bp": bps(self.overridden, self.lines),
            "review_seconds": _seconds(self.seconds),
        }


def _records(session: Session) -> dict[str, list[DecisionRecord]]:
    found: dict[str, list[DecisionRecord]] = defaultdict(list)
    for row in session.scalars(
        select(DecisionRecordRow).order_by(DecisionRecordRow.claim_id, DecisionRecordRow.version)
    ):
        try:
            found[row.claim_id].append(DecisionRecord.model_validate(row.record))
        except ValidationError:  # stored under an older contract: left out
            continue
    return found


def _reviews(records: list[DecisionRecord]) -> list[tuple[DecisionRecord, DecisionRecord]]:
    """(awaiting review, finalized) pairs, in order."""
    pairs = []
    for before, after in zip(records, records[1:], strict=False):
        if before.status is ClaimStatus.AWAITING_REVIEW and after.review is not None:
            pairs.append((before, after))
    return pairs


def review_quality(session: Session) -> dict[str, object]:
    """How reviewers use the model's recommendations, from every review on file."""
    overall, by_tier = _Tally(), defaultdict(_Tally)
    by_reviewer: dict[str, _Tally] = defaultdict(_Tally)
    by_policy: dict[str, _Tally] = defaultdict(_Tally)
    titles: dict[str, str] = {}
    matrix: dict[str, Counter[str]] = defaultdict(Counter)
    for records in _records(session).values():
        for before, after in _reviews(records):
            reviewer = after.review.reviewer_id if after.review else "unknown"
            tier = before.review_tier.value if before.review_tier else "NONE"
            final = {line.line_no: line for line in after.line_decisions}
            contexts = {
                c.line_no: c for c in (before.context_refs.lines if before.context_refs else [])
            }
            for tally in (overall, by_tier[tier], by_reviewer[reviewer]):
                tally.reviews += 1
            for line in before.line_decisions:
                if line.source not in MODEL_SOURCES:
                    continue
                decided = final.get(line.line_no)
                overridden = decided is not None and decided.source == "REVIEWER"
                matrix[line.decision.value][(decided or line).decision.value] += 1
                context = contexts.get(line.line_no)
                policy = context.criteria[0].policy_id if context and context.criteria else "none"
                if context and context.criteria:
                    titles[policy] = context.criteria[0].policy_title
                for tally in (overall, by_tier[tier], by_reviewer[reviewer], by_policy[policy]):
                    tally.lines += 1
                    tally.overridden += int(overridden)
    events = list(
        session.scalars(
            select(AuditEvent).where(
                AuditEvent.event_type.in_(
                    (
                        EventType.REVIEW_ACCEPTED.value,
                        EventType.REVIEW_OVERRIDDEN.value,
                        EventType.REVIEWER_FEEDBACK.value,
                    )
                )
            )
        )
    )
    tiers_by_claim = {
        claim_id: (records[-1].review_tier.value if records and records[-1].review_tier else "NONE")
        for claim_id, records in _records(session).items()
    }
    feedback_lines = feedback_criteria = 0
    for event in events:
        if event.event_type == EventType.REVIEWER_FEEDBACK.value:
            lines = event.payload.get("lines", [])
            feedback_lines += len(lines)
            feedback_criteria += sum(len(line.get("criteria", [])) for line in lines)
            continue
        seconds = event.payload.get("review_seconds")
        if seconds is None:
            continue
        overall.seconds.append(float(seconds))
        by_reviewer[event.actor].seconds.append(float(seconds))
        by_tier[tiers_by_claim.get(event.claim_id, "NONE")].seconds.append(float(seconds))
    appeals = Counter((a.status, a.outcome) for a in session.scalars(select(Appeal)))
    return {
        "overall": overall.view(),
        "acceptance_rate_bp": bps(overall.lines - overall.overridden, overall.lines),
        "matrix": {model: dict(finals) for model, finals in sorted(matrix.items())},
        "by_tier": {tier: tally.view() for tier, tally in sorted(by_tier.items())},
        "by_reviewer": [
            {"reviewer": name, **tally.view()} for name, tally in sorted(by_reviewer.items())
        ],
        "by_policy": [
            {"policy_id": policy, "title": titles.get(policy), **tally.view()}
            for policy, tally in sorted(
                by_policy.items(), key=lambda kv: (-kv[1].overridden, -kv[1].lines, kv[0])
            )
        ],
        "feedback": {"lines": feedback_lines, "criteria": feedback_criteria},
        "appeals": {
            "open": appeals[("OPEN", None)],
            "upheld": appeals[("DECIDED", "UPHELD")],
            "changed": appeals[("DECIDED", "CHANGED")],
        },
    }


@dataclass(frozen=True)
class OverviewExtras:
    billed_cents: int
    plan_paid_cents: int
    member_owes_cents: int
    decided_claims: int  # final claims with amounts, behind the three sums
    review_wait_seconds: float | None  # median, processing to finalization
    review_seconds: float | None  # median time a reviewer spent, opening to finalization
    override_rate_bp: int | None
    top_reasons: list[dict[str, object]]
    daily: list[dict[str, object]]


def overview_extras(session: Session, today: date | None = None, days: int = 14) -> OverviewExtras:
    """The Overview's money, times, reasons and trend over the claims on file."""
    stored = []  # the calculator's totals of each decided claim, as its record keeps them
    waits: list[float] = []
    lines = overridden = 0
    for records in _records(session).values():
        last = records[-1]
        if last.status in REVIEWED_STATUSES and last.amounts is not None:
            stored.append(last.amounts.totals)
        for before, after in _reviews(records):
            if after.timestamps.finalized and before.timestamps.processed:
                waits.append(
                    (after.timestamps.finalized - before.timestamps.processed).total_seconds()
                )
            final = {line.line_no: line for line in after.line_decisions}
            for line in before.line_decisions:
                if line.source in MODEL_SOURCES:
                    lines += 1
                    overridden += int(
                        line.line_no in final and final[line.line_no].source == "REVIEWER"
                    )
    seconds = [
        float(event.payload["review_seconds"])
        for event in session.scalars(
            select(AuditEvent).where(
                AuditEvent.event_type.in_(
                    (EventType.REVIEW_ACCEPTED.value, EventType.REVIEW_OVERRIDDEN.value)
                )
            )
        )
        if event.payload.get("review_seconds") is not None
    ]
    reasons: Counter[str] = Counter()
    for summary in claim_summaries(session):
        for reason in summary.reasons:
            reasons[reason.text.short] += 1
    end = today or datetime.now(UTC).date()
    start = end - timedelta(days=days - 1)
    received: Counter[date] = Counter(
        created.date()
        for created in session.scalars(select(Claim.created_at))
        if created is not None and created.date() >= start
    )
    decided_days: Counter[date] = Counter(
        created.date()
        for created in session.scalars(
            select(AuditEvent.created_at).where(AuditEvent.event_type.in_(DECIDED_EVENTS))
        )
        if created is not None and created.date() >= start
    )
    return OverviewExtras(
        billed_cents=total_cents(t.billed_cents for t in stored),
        plan_paid_cents=total_cents(t.plan_pays_cents for t in stored),
        member_owes_cents=total_cents(t.member_pays_cents for t in stored),
        decided_claims=len(stored),
        review_wait_seconds=median(waits) if waits else None,
        review_seconds=median(seconds) if seconds else None,
        override_rate_bp=bps(overridden, lines),
        top_reasons=[{"reason": text, "claims": n} for text, n in reasons.most_common(5)],
        daily=[
            {
                "date": (start + timedelta(days=i)).isoformat(),
                "received": received[start + timedelta(days=i)],
                "decided": decided_days[start + timedelta(days=i)],
            }
            for i in range(days)
        ],
    )
