"""The provider's view of a final claim (D-UI-6): the outcome in plain words, why it was not paid
as billed, what to check on the claim, the standard reason codes, and the billing of paid claims.

Built deterministically from the decision record, the claim as stored at intake and the reason
table (app/explain/reasons.py), never by the model (H15). It shows no rule IDs, internal reason
codes, rule checks, criterion IDs, model output, confidence scores or versions: what a pended
line needs is the criterion's own text from the context package, and a field read with low
confidence is shown with what was read. Every amount is the calculator's (H1); the sentences only
name the amounts the record holds, skipping zeros. Billed minus the reductions to the allowed
amount gives the allowed amount, and the allowed amount is what the plan pays plus what the
patient pays plus what another plan paid first.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from app.calculator.money import apply_bps
from app.domain.contracts import (
    CriterionStatus,
    DecisionRecord,
    LineAmounts,
    LineDecision,
    RetrievedCriterion,
    npi_is_valid,
)
from app.explain.codes import adjustments, procedure_codes
from app.explain.fields import (
    NOT_ON_CLAIM,
    field_label,
    line_diagnoses,
    line_index,
    line_numbers,
    lookup,
    shown,
)
from app.explain.reasons import Check, ClaimReason, claim_reasons
from app.explain.render import guarded, money

HEADINGS = {
    "APPROVED": "Claim approved",
    "PARTLY_APPROVED": "Claim partly approved",
    "PENDED": "Claim on hold: more information needed",
    "DENIED": "Claim denied",
    "REJECTED": "Claim rejected",
}
PAID_OUTCOMES = ("APPROVED", "PARTLY_APPROVED")
NPI_FIELD_NAMES = ("billing_npi", "referring_npi", "rendering_npi")


@dataclass(frozen=True)
class Item:
    line_no: int | None  # None: the whole claim
    text: str


@dataclass(frozen=True)
class CodeChip:
    kind: str  # CARC or RARC
    code: str
    description: str | None


@dataclass(frozen=True)
class CodeGroup:
    line_no: int | None
    codes: list[CodeChip]
    billing_article: str | None
    lcds: list[str]


@dataclass(frozen=True)
class Reduction:
    """One plain sentence under a billing line. `kind` says what it is: allowed_amount,
    out_of_network and not_paid take the billed amount down to the allowed amount; deductible,
    copay, coinsurance and other_plan are the parts of the allowed amount the plan does not pay;
    a note carries no amount."""

    kind: str
    amount_cents: int | None
    text: str


@dataclass(frozen=True)
class BillingLine:
    line_no: int
    procedure_code: str
    paid: bool
    billed_cents: int
    allowed_cents: int
    deductible_cents: int
    copay_cents: int
    coinsurance_cents: int
    plan_pays_cents: int
    patient_pays_cents: int
    other_plan_paid_cents: int
    reductions: list[Reduction] = field(default_factory=list)


@dataclass(frozen=True)
class BillingTotals:
    billed_cents: int
    allowed_cents: int
    deductible_cents: int
    copay_cents: int
    coinsurance_cents: int
    plan_pays_cents: int
    patient_pays_cents: int
    other_plan_paid_cents: int


@dataclass(frozen=True)
class Billing:
    lines: list[BillingLine]
    totals: BillingTotals


@dataclass(frozen=True)
class ProviderExplanation:
    outcome: str
    heading: str
    why: list[Item]
    review: list[Item]  # "Please review the following details"
    codes: list[CodeGroup]
    billing: Billing | None


# --- What to check -------------------------------------------------------------------------------


def line_criteria(
    record: DecisionRecord, line_no: int
) -> list[tuple[str, RetrievedCriterion | None, CriterionStatus]]:
    """(criterion ID, the retrieved criterion, status) of a model line's criteria, as the
    derivation counted them: a MET whose quote is not in the notes counts as not documented
    (D-EVID-1)."""
    contexts = record.context_refs.lines if record.context_refs else []
    context = next((c for c in contexts if c.line_no == line_no), None)
    cited = {c.criterion_id: c for c in (context.criteria if context else [])}
    answers = record.slm_output.lines if record.slm_output else []
    answer = next((a for a in answers if a.line_no == line_no), None)
    checked = guarded(record.output_errors)
    return [
        (
            result.criterion_id,
            cited.get(result.criterion_id),
            CriterionStatus.NOT_DOCUMENTED
            if (line_no, result.criterion_id) in checked
            else result.status,
        )
        for result in (answer.criteria if answer else [])
    ]


BYPASS_FLAG = "NCCI_BYPASS"
BYPASS_DOCUMENTATION = (
    "Documentation that this service was separate and distinct from the other service billed "
    "on the same date, as its modifier states."
)


def bypass_flagged(record: DecisionRecord, line_no: int) -> bool:
    """A line whose NCCI edit a modifier bypassed: the notes must show the distinct service."""
    return any(
        o.line_no == line_no and BYPASS_FLAG in o.flags for o in record.rules_outcome.line_outcomes
    )


def _criteria_items(record: DecisionRecord, reason: ClaimReason, detail: str) -> list[str]:
    """The coverage criteria behind a model line's reason, in their own words (never their IDs).
    Criteria of policy set v1 have no type, so a line's not-met criteria stand for both kinds."""
    if reason.line_no is None:
        return []
    criteria = [(c, s) for _, c, s in line_criteria(record, reason.line_no) if c is not None]
    if detail == "not_documented":
        found = [
            f"Documentation that shows: {c.text}"
            for c, s in criteria
            if s is CriterionStatus.NOT_DOCUMENTED
        ]
        if not found and bypass_flagged(record, reason.line_no):
            found.append(BYPASS_DOCUMENTATION)
        return found or ["Documentation that supports the service."]
    not_met = [c for c, s in criteria if s is CriterionStatus.NOT_MET]
    exclusions = [c for c in not_met if c.criterion_type == "exclusion"]
    if detail == "exclusions" and exclusions:
        return [f"Exclusion that applies: {c.text}" for c in exclusions]
    others = [c for c in not_met if c.criterion_type != "exclusion"]
    return [f"Coverage criterion not met: {c.text}" for c in others or not_met]


def _detail_items(
    record: DecisionRecord,
    reason: ClaimReason,
    claim: Mapping[str, Any],
    confidences: Mapping[str, float],
    threshold: float,
) -> list[str]:
    detail = reason.text.detail
    if detail == "missing_fields":
        return [f"{field_label(path)}: {NOT_ON_CLAIM}" for path in reason.fields_used]
    if detail == "codes":
        items = [f"Diagnosis codes on the claim: {shown('diagnoses', claim.get('diagnoses'))}"]
        for line_no in line_numbers(claim):
            i = line_index(claim, line_no)
            for name in ("procedure_code", "place_of_service"):
                path = f"service_lines.{i}.{name}"
                items.append(f"{field_label(path)}: {shown(path, lookup(claim, path))}")
        return items
    if detail == "invalid_npis":
        items = []
        for path in reason.fields_used:
            value = lookup(claim, path)
            if path.split(".")[-1] in NPI_FIELD_NAMES and isinstance(value, str):
                if not npi_is_valid(value):
                    items.append(f"{field_label(path)} on the claim: {value} (not a valid NPI)")
        return items
    if detail == "low_confidence":
        items = []
        for path in sorted(confidences):
            if confidences[path] >= threshold:
                continue
            if not any(path == f or path.startswith(f"{f}.") for f in reason.fields_used):
                continue
            value = lookup(claim, path)
            items.append(
                f"{field_label(path)}: could not be read"
                if value in (None, "", [])
                else f"{field_label(path)}, read as: {shown(path, value)}"
            )
        return items
    if detail == "line_diagnoses" and reason.line_no is not None:
        codes = line_diagnoses(claim, reason.line_no)
        return [f"Diagnoses for line {reason.line_no}: {', '.join(codes) or NOT_ON_CLAIM}"]
    if detail in ("not_met", "exclusions", "not_documented"):
        return _criteria_items(record, reason, detail)
    return []


def _check_items(check: Check, reason: ClaimReason, claim: Mapping[str, Any]) -> list[str]:
    if check.field is None:
        return [check.text]
    if "{i}" not in check.field:
        return [f"{check.text}: {shown(check.field, lookup(claim, check.field))}"]
    lines = [reason.line_no] if reason.line_no is not None else line_numbers(claim)
    items = []
    for line_no in lines:
        path = check.field.format(i=line_index(claim, line_no))
        items.append(f"{check.text.format(line=line_no)}: {shown(path, lookup(claim, path))}")
    return items


def review_items(
    record: DecisionRecord,
    reasons: list[ClaimReason],
    claim: Mapping[str, Any],
    confidences: Mapping[str, float],
    threshold: float,
) -> list[Item]:
    found: list[Item] = []
    for reason in reasons:
        texts = _detail_items(record, reason, claim, confidences, threshold)
        for check in reason.text.check:
            texts += _check_items(check, reason, claim)
        for text in texts:
            if all(item.text != text for item in found):
                found.append(Item(reason.line_no, text))
    return found


# --- Billing -------------------------------------------------------------------------------------


def _coinsurance(line: LineAmounts, rate_bps: int | None) -> str:
    """The coinsurance sentence: the plan's rate when the amount is that rate of the allowed amount
    after the deductible (no out-of-pocket cap reached), otherwise the share without a rate."""
    amount = money(line.coinsurance_cents)
    base = line.allowed_cents - line.deductible_cents
    if rate_bps is not None and base >= 0 and apply_bps(base, rate_bps) == line.coinsurance_cents:
        whole, rest = divmod(rate_bps, 100)
        rate = f"{whole}.{rest:02d}".rstrip("0").rstrip(".") + "%"
        return (
            f"Coinsurance: the patient pays {rate} of the allowed amount after the deductible "
            f"({amount})."
        )
    return (
        f"Coinsurance: the patient's share of the allowed amount after the deductible ({amount}), "
        "limited by the plan's out-of-pocket maximum."
    )


def _reductions(
    line: LineAmounts, decision: LineDecision | None, short: str, rate_bps: int | None
) -> list[Reduction]:
    if decision is not LineDecision.APPROVE:
        lead = "Not paid yet" if decision is LineDecision.PEND else "Not paid"
        return [
            Reduction("not_paid", line.billed_cents, f"{lead}: {short[:1].lower()}{short[1:]}.")
        ]
    found = []
    if line.contractual_adjustment_cents:
        found.append(
            Reduction(
                "allowed_amount",
                line.contractual_adjustment_cents,
                f"Reduced by {money(line.contractual_adjustment_cents)} to the plan's allowed "
                "amount for this service.",
            )
        )
    if line.balance_bill_exposure_cents:
        found.append(
            Reduction(
                "out_of_network",
                line.balance_bill_exposure_cents,
                f"{money(line.balance_bill_exposure_cents)} above the plan's allowed amount for an "
                "out-of-network provider; the plan does not pay this part.",
            )
        )
    if line.deductible_cents:
        found.append(
            Reduction(
                "deductible",
                line.deductible_cents,
                f"{money(line.deductible_cents)} applied to the patient's deductible: the amount "
                "the patient pays before the plan starts paying.",
            )
        )
    if line.copay_cents:
        found.append(
            Reduction(
                "copay",
                line.copay_cents,
                f"{money(line.copay_cents)} copay under the patient's plan.",
            )
        )
    if line.coinsurance_cents:
        found.append(Reduction("coinsurance", line.coinsurance_cents, _coinsurance(line, rate_bps)))
    if line.cob_primary_paid_cents:
        found.append(
            Reduction(
                "other_plan",
                line.cob_primary_paid_cents,
                f"{money(line.cob_primary_paid_cents)} paid first by the patient's other plan.",
            )
        )
        share = line.deductible_cents + line.copay_cents + line.coinsurance_cents
        if line.member_pays_cents != share:
            found.append(
                Reduction(
                    "note",
                    None,
                    f"After the other plan's payment, the patient pays "
                    f"{money(line.member_pays_cents)}.",
                )
            )
    return found


def billing(
    record: DecisionRecord, claim: Mapping[str, Any], rate_bps: int | None
) -> Billing | None:
    """Every line with the calculator's amounts: paid lines with a sentence per reduction, the
    others marked not paid with their short reason, so the lines add up to the stored totals."""
    if record.amounts is None:
        return None
    decisions = {d.line_no: d for d in record.line_decisions}
    reasons: dict[int, ClaimReason] = {}
    for found in claim_reasons(record):
        if found.line_no is not None:
            reasons.setdefault(found.line_no, found)
    codes = procedure_codes(claim)
    lines = []
    for amounts in sorted(record.amounts.lines, key=lambda a: a.line_no):
        decision = decisions.get(amounts.line_no)
        reason = reasons.get(amounts.line_no)
        short = reason.text.short if reason else "Not paid as billed"
        lines.append(
            BillingLine(
                line_no=amounts.line_no,
                procedure_code=str(codes.get(amounts.line_no, "")),
                paid=decision is not None and decision.decision is LineDecision.APPROVE,
                billed_cents=amounts.billed_cents,
                allowed_cents=amounts.allowed_cents,
                deductible_cents=amounts.deductible_cents,
                copay_cents=amounts.copay_cents,
                coinsurance_cents=amounts.coinsurance_cents,
                plan_pays_cents=amounts.plan_pays_cents,
                patient_pays_cents=amounts.member_pays_cents,
                other_plan_paid_cents=amounts.cob_primary_paid_cents,
                reductions=_reductions(
                    amounts, decision.decision if decision else None, short, rate_bps
                ),
            )
        )
    t = record.amounts.totals
    return Billing(
        lines=lines,
        totals=BillingTotals(
            billed_cents=t.billed_cents,
            allowed_cents=t.allowed_cents,
            deductible_cents=t.deductible_cents,
            copay_cents=t.copay_cents,
            coinsurance_cents=t.coinsurance_cents,
            plan_pays_cents=t.plan_pays_cents,
            patient_pays_cents=t.member_pays_cents,
            other_plan_paid_cents=t.cob_primary_paid_cents,
        ),
    )


# --- The view ------------------------------------------------------------------------------------


def provider_explanation(
    outcome: str,
    record: DecisionRecord,
    claim: Mapping[str, Any],
    confidences: Mapping[str, float],
    threshold: float,
    coinsurance_bps: int | None = None,
) -> ProviderExplanation:
    """The provider's view of a final claim. `outcome` is the claim's label key
    (reasons.claim_outcome); `coinsurance_bps` the plan's coinsurance rate for the claim's network,
    when known, for the coinsurance sentence."""
    reasons = claim_reasons(record) if outcome != "APPROVED" else []
    why: list[Item] = []
    for reason in reasons:
        text = reason.text.provider
        if all((item.line_no, item.text) != (reason.line_no, text) for item in why):
            why.append(Item(reason.line_no, text))
    groups = [
        CodeGroup(
            line_no=a.line_no,
            codes=[CodeChip(c.kind, c.code, c.description) for c in a.codes],
            billing_article=a.billing_article,
            lcds=list(a.lcds),
        )
        for a in (adjustments(record, procedure_codes(claim)) if reasons else [])
    ]
    return ProviderExplanation(
        outcome=outcome,
        heading=HEADINGS.get(outcome, "Claim decided"),
        why=why,
        review=review_items(record, reasons, claim, confidences, threshold),
        codes=groups,
        billing=billing(record, claim, coinsurance_bps) if outcome in PAID_OUTCOMES else None,
    )
