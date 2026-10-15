"""Check a claim before it is processed (D-CHK-1).

The provider asks what processing would find before running it: the rules run on the claim as it
stands, exactly as processing runs them (the same `evaluate`, reference data and threshold), and
nothing is written: no status change, no decision record, no audit event. What a failed rule means
and what to check come from the reason table in plain words (app/explain/reasons.py,
app/explain/provider.py), with the boxes involved so the provider can correct a misread one
(D-FIX-1). Lines the rules would pass also get their coverage criteria from the policy lookup
processing uses (the same retriever, plan and date of service), so the provider sees what the
clinical notes must show; the model is not run, so the check never says whether they show it.

Outcomes: READY (the rules pass every line), LINES_DENIED (the rules deny some lines; the others
go on), REJECTED, DENIED or PENDED (the rules would stop the claim).
"""

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.core.settings import Settings
from app.db import lookups
from app.db.models import Claim
from app.db.rules_reference import reference_for_claim
from app.domain.contracts import (
    ClaimStatus,
    DecisionRecord,
    IntakeClaim,
    RetrievedCriterion,
    RuleOutcomeValue,
    RulesOutcome,
    Timestamps,
    Versions,
    npi_is_valid,
)
from app.explain.fields import field_label, lookup
from app.explain.provider import BYPASS_FLAG, NPI_FIELD_NAMES, review_items
from app.explain.reasons import ClaimReason
from app.intake.corrections import form_text
from app.rag.retrieve import RetrievalUnavailable, Retriever, line_query
from app.rules import RULES_VERSION
from app.rules.confidence import low_confidence_fields
from app.rules.engine import evaluate
from app.rules.integrity import InvalidClaimData
from app.rules.reference import MissingReference
from app.workflow.pipeline import (
    ClaimNotFound,
    PipelineError,
    ReferenceDataUnavailable,
    prompt_lookups,
)
from app.workflow.states import InvalidTransition

STOPPED = {
    RuleOutcomeValue.REJECT: "REJECTED",
    RuleOutcomeValue.DENY: "DENIED",
    RuleOutcomeValue.PEND: "PENDED",
}
HEADINGS = {
    "READY": "No problems found by the claim checks",
    "LINES_DENIED": "Some lines would not be paid",
    "REJECTED": "The claim would be rejected",
    "DENIED": "The claim would be denied",
    "PENDED": "The claim would be put on hold",
}
BYPASS_NOTE = (
    "The clinical notes must show that this service was separate and distinct from the other "
    "service billed on the same date, as its modifier states; the reviewer checks this."
)
LOW_CONFIDENCE_NOTE = (
    "Some boxes were read with low confidence. If a check fails on one of them, the claim is "
    "rejected rather than denied, so correct any that were read wrong before processing."
)
COVERAGE_UNAVAILABLE = (
    "The coverage policy lookup is not available right now. Processing needs it too; try again "
    "once it is running."
)


@dataclass(frozen=True)
class CheckItem:
    line_no: int | None  # None: the whole claim
    text: str  # plain words
    checks: list[str] = field(default_factory=list)  # what to check, with what the claim shows
    fields: list[str] = field(default_factory=list)  # the boxes involved, to correct


@dataclass(frozen=True)
class CoverageLine:
    """What the coverage policy for a line asks of the clinical notes, by kind of criterion."""

    line_no: int
    procedure_code: str
    policies: list[str]  # the policy titles
    needed: list[str]  # requirements
    one_of: list[str]  # alternative covered indications: one is enough
    applies_when: list[str]  # conditions that apply only in the situation they name
    not_covered: list[str]  # exclusions


@dataclass(frozen=True)
class ClaimCheck:
    claim_id: str
    outcome: str
    heading: str
    problems: list[CheckItem]
    notes: list[CheckItem]
    coverage: list[CoverageLine] | None  # None: not looked up
    coverage_note: str | None


def _outcome(rules: RulesOutcome) -> str:
    if rules.claim_outcome is not RuleOutcomeValue.PASS:
        return STOPPED[rules.claim_outcome]
    if any(o.outcome == "DENY" for o in rules.line_outcomes):
        return "LINES_DENIED"
    return "READY"


def _problems(
    rules: RulesOutcome,
    record: DecisionRecord,
    claim: dict,
    confidences: dict[str, float],
    threshold: float,
) -> list[CheckItem]:
    found: list[CheckItem] = []
    seen: set[tuple[str, int | None]] = set()
    for result in rules.rule_results:
        if result.passed or result.reason_code is None:
            continue
        if (result.reason_code, result.line_no) in seen:
            continue
        seen.add((result.reason_code, result.line_no))
        reason = ClaimReason(
            result.reason_code, result.rule_id, result.line_no, tuple(result.fields_used)
        )
        found.append(
            CheckItem(
                line_no=result.line_no,
                text=reason.text.provider,
                checks=[
                    item.text
                    for item in review_items(record, [reason], claim, confidences, threshold)
                ],
                fields=_at_fault(reason, claim, confidences, threshold),
            )
        )
    return found


def _at_fault(
    reason: ClaimReason, claim: dict, confidences: dict[str, float], threshold: float
) -> list[str]:
    """The boxes to correct for a failed rule: those read with low confidence when that is why
    (H5); the NPIs that fail the check digit for an invalid NPI; otherwise every field it used."""
    fields = list(reason.fields_used)
    low = low_confidence_fields(fields, confidences, threshold)
    if low:
        return low
    if reason.text.detail == "invalid_npis":
        return sorted(
            path
            for path in fields
            if path.split(".")[-1] in NPI_FIELD_NAMES
            and isinstance(value := lookup(claim, path), str)
            and not npi_is_valid(value)
        )
    return sorted(fields)


def _notes(
    rules: RulesOutcome,
    problems: list[CheckItem],
    claim: dict,
    confidences: dict[str, float],
    threshold: float,
) -> list[CheckItem]:
    notes = [
        CheckItem(line_no=o.line_no, text=BYPASS_NOTE)
        for o in rules.line_outcomes
        if BYPASS_FLAG in o.flags
    ]
    named = {path for problem in problems for path in problem.fields}
    low = sorted(
        path for path, value in confidences.items() if value < threshold and path not in named
    )
    if low:
        boxes = form_text(claim)
        notes.append(
            CheckItem(
                line_no=None,
                text=LOW_CONFIDENCE_NOTE,
                checks=[
                    f"{field_label(path)}, read as: {boxes[path]}"
                    if path in boxes
                    else f"{field_label(path)}: could not be read"
                    for path in low
                ],
                fields=low,
            )
        )
    return notes


def _coverage_line(line_no: int, code: str, criteria: list[RetrievedCriterion]) -> CoverageLine:
    def texts(kind: str) -> list[str]:
        return [c.text for c in criteria if _kind(c) == kind]

    return CoverageLine(
        line_no=line_no,
        procedure_code=code,
        policies=sorted({c.policy_title for c in criteria}),
        needed=texts("needed"),
        one_of=texts("one_of"),
        applies_when=texts("applies_when"),
        not_covered=texts("not_covered"),
    )


def _kind(criterion: RetrievedCriterion) -> str:
    if criterion.group == "indication":
        return "one_of"
    if criterion.criterion_type == "exclusion":
        return "not_covered"
    if criterion.criterion_type == "conditional":
        return "applies_when"
    return "needed"


def _coverage(
    session: Session,
    claim: IntakeClaim,
    rules: RulesOutcome,
    settings: Settings,
    retriever: Retriever,
) -> list[CoverageLine]:
    """The criteria processing would retrieve for each line the rules pass."""
    member = lookups.get_member(session, claim.member_id)
    if member is None:  # R04 passed, so the member is on file
        return []
    claim_lookups = prompt_lookups(session, claim, settings.policy_set)
    lines = {line.line_no: line for line in claim.service_lines}
    found = []
    for outcome in rules.line_outcomes:
        if outcome.outcome != "PASS":
            continue
        line = lines[outcome.line_no]
        criteria = retriever.retrieve(
            line_query(
                claim,
                line.line_no,
                claim_lookups.procedure_descriptions,
                claim_lookups.icd10_descriptions,
            ),
            member.plan_id,
            line.date_of_service,
            line.procedure_code,
        )
        found.append(_coverage_line(line.line_no, line.procedure_code, criteria))
    return found


def check_claim(
    session: Session, claim_id: str, settings: Settings, retriever: Retriever | None
) -> ClaimCheck:
    """What processing would find on the claim's rules, and each passing line's coverage
    criteria. Raises ClaimNotFound, InvalidTransition (the claim was processed),
    ReferenceDataUnavailable or PipelineError, as processing does."""
    row = session.get(Claim, claim_id)
    if row is None:
        raise ClaimNotFound(f"claim {claim_id} not found")
    if row.status != ClaimStatus.RECEIVED.value:
        raise InvalidTransition(
            f"claim {claim_id} is {row.status}; only a claim not processed yet is checked"
        )
    confidences = dict(row.field_confidences or {})
    threshold = settings.extraction_confidence_min
    try:
        rules = evaluate(
            row.intake,
            confidences,
            reference_for_claim(session, row.intake),
            confidence_min=threshold,
        )
    except MissingReference as exc:
        raise ReferenceDataUnavailable(f"reference data not loaded: {exc}") from exc
    except InvalidClaimData as exc:
        raise PipelineError(f"claim {claim_id} cannot be checked: {exc}") from exc
    record = DecisionRecord(
        claim_id=claim_id,
        status=ClaimStatus.RECEIVED,
        rules_outcome=rules,
        versions=Versions(rules_version=RULES_VERSION),
        timestamps=Timestamps(received=row.received_date),
    )
    claim = dict(row.intake)
    problems = _problems(rules, record, claim, confidences, threshold)
    notes = _notes(rules, problems, claim, confidences, threshold)
    outcome = _outcome(rules)
    coverage: list[CoverageLine] | None = None
    coverage_note = None
    if rules.claim_outcome is RuleOutcomeValue.PASS and retriever is not None:
        try:
            coverage = _coverage(
                session, IntakeClaim.model_validate(row.intake), rules, settings, retriever
            )
        except RetrievalUnavailable:
            coverage_note = COVERAGE_UNAVAILABLE
    session.rollback()  # nothing is written
    return ClaimCheck(
        claim_id=claim_id,
        outcome=outcome,
        heading=HEADINGS[outcome],
        problems=problems,
        notes=notes,
        coverage=coverage,
        coverage_note=coverage_note,
    )
