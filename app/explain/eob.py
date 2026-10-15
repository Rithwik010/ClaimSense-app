"""The patient's explanation of benefits (EOB, D-EOB-1): what the plan did with each service on a
final claim, for the provider to print or hand to the patient. It is not a bill.

Built deterministically from the decision record, the claim as stored at intake and the reason
table, like the provider's view (app/explain/provider.py, H15): every amount is the calculator's
(H1), each line's sentences are the provider view's billing sentences, and a line not paid carries
its plain reason and its standard codes (CARC/RARC). A claim the rules denied has no calculation:
its lines show what was billed (the claim's own charges) and why nothing was paid, with no other
amount. The year-to-date deductible and out-of-pocket amounts are the ones stored when the claim
was finalized (the FINALIZED audit event), against the plan's limits for the claim's network.

An EOB exists for a claim a reviewer finalized and for one the rules denied. A rejected claim was
returned to the provider without being processed, and a claim the rules put on hold was not
decided, so neither has one.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from app.domain.contracts import ClaimStatus, DecisionRecord, LineDecision
from app.explain.codes import adjustments, procedure_codes
from app.explain.fields import line_index, line_numbers, lookup
from app.explain.provider import billing
from app.explain.reasons import ClaimReason, claim_reasons

EOB_STATUSES = frozenset(
    {
        ClaimStatus.FINAL_APPROVED,
        ClaimStatus.FINAL_PARTIAL,
        ClaimStatus.FINAL_DENIED,
        ClaimStatus.FINAL_PENDED,
        ClaimStatus.DENIED_BY_RULE,
    }
)
LINE_STATUS = {
    LineDecision.APPROVE: "PAID",
    LineDecision.DENY: "NOT_PAID",
    LineDecision.PEND: "PENDING",
}
NOT_A_BILL = "This is not a bill."
NO_CALCULATION = (
    "The plan did not pay this claim, so no allowed amount was worked out for it. The billed "
    "amounts are the provider's charges."
)
PENDING_NOTE = (
    "Some services are waiting for information from the provider and are not paid yet; they will "
    "be decided once it arrives."
)


@dataclass(frozen=True)
class EobLine:
    line_no: int
    date_of_service: str | None  # YYYY-MM-DD
    procedure_code: str
    service: str | None  # the team-written short description of the code
    status: str  # PAID, NOT_PAID or PENDING
    billed_cents: int | None
    allowed_cents: int | None  # None: no calculation (a claim the rules denied)
    plan_pays_cents: int | None
    patient_pays_cents: int | None
    other_plan_paid_cents: int | None
    notes: list[str] = field(default_factory=list)
    codes: list[str] = field(default_factory=list)  # e.g. "CO-236", "N115"


@dataclass(frozen=True)
class EobTotals:
    billed_cents: int
    allowed_cents: int
    plan_pays_cents: int
    patient_pays_cents: int
    other_plan_paid_cents: int


@dataclass(frozen=True)
class YearToDate:
    """The patient's deductible and out-of-pocket amounts so far this benefit year, as stored
    when the claim was finalized, and the plan's limits for the claim's network."""

    network: str
    period_start: str  # YYYY-MM-DD
    deductible_met_cents: int
    deductible_cents: int
    oop_met_cents: int
    oop_max_cents: int


@dataclass(frozen=True)
class PatientEob:
    claim_id: str
    outcome: str  # the label key (reasons.claim_outcome)
    patient_name: str | None
    member_id: str | None
    plan_name: str | None
    provider_name: str | None
    provider_npi: str | None
    network: str | None
    received: str  # YYYY-MM-DD
    processed: str | None  # YYYY-MM-DD: finalized, or decided by the rules
    lines: list[EobLine]
    totals: EobTotals | None  # None: no calculation
    year_to_date: YearToDate | None
    notes: list[str]  # for the whole claim; the first is always "This is not a bill."
    codes: list[str]  # standard codes for the whole claim


def _codes(record: DecisionRecord, claim: Mapping[str, Any]) -> dict[int | None, list[str]]:
    found: dict[int | None, list[str]] = {}
    for item in adjustments(record, procedure_codes(claim)):
        codes = found.setdefault(item.line_no, [])
        for code in item.codes:
            text = f"{item.group_code}-{code.code}" if code.kind == "CARC" else code.code
            if text not in codes:
                codes.append(text)
    return found


def _patient_name(claim: Mapping[str, Any]) -> str | None:
    names = [lookup(claim, "patient.first_name"), lookup(claim, "patient.last_name")]
    shown = [str(name) for name in names if isinstance(name, str) and name.strip()]
    return " ".join(shown) or None


def _not_paid(reasons: list[ClaimReason]) -> list[str]:
    return [f"Not paid: {r.text.short[:1].lower()}{r.text.short[1:]}." for r in reasons]


def patient_eob(
    status: ClaimStatus,
    outcome: str,
    record: DecisionRecord,
    claim: Mapping[str, Any],
    *,
    plan_name: str | None,
    provider_name: str | None,
    descriptions: Mapping[str, str],
    year_to_date: YearToDate | None,
    coinsurance_bps: int | None = None,
) -> PatientEob:
    """The EOB of a final claim (`status` in EOB_STATUSES; the caller checks)."""
    decisions = {d.line_no: d.decision for d in record.line_decisions}
    reasons = claim_reasons(record)
    codes = _codes(record, claim)
    by_line: dict[int, list[ClaimReason]] = {}
    for reason in reasons:
        if reason.line_no is not None:
            by_line.setdefault(reason.line_no, []).append(reason)
    lines: list[EobLine] = []
    bill = billing(record, claim, coinsurance_bps)

    def base(line_no: int) -> tuple[str | None, str]:
        i = line_index(claim, line_no)
        day = lookup(claim, f"service_lines.{i}.date_of_service")
        code = lookup(claim, f"service_lines.{i}.procedure_code")
        return (day if isinstance(day, str) else None), (code if isinstance(code, str) else "")

    if bill is not None:
        for line in bill.lines:
            day, code = base(line.line_no)
            decision = decisions.get(line.line_no)
            lines.append(
                EobLine(
                    line_no=line.line_no,
                    date_of_service=day,
                    procedure_code=line.procedure_code or code,
                    service=descriptions.get(line.procedure_code or code),
                    status=LINE_STATUS[decision] if decision else "NOT_PAID",
                    billed_cents=line.billed_cents,
                    allowed_cents=line.allowed_cents,
                    plan_pays_cents=line.plan_pays_cents,
                    patient_pays_cents=line.patient_pays_cents,
                    other_plan_paid_cents=line.other_plan_paid_cents,
                    notes=[r.text for r in line.reductions],
                    codes=codes.get(line.line_no, []),
                )
            )
    else:
        for line_no in line_numbers(claim):
            day, code = base(line_no)
            charge = lookup(claim, f"service_lines.{line_index(claim, line_no)}.charge_cents")
            lines.append(
                EobLine(
                    line_no=line_no,
                    date_of_service=day,
                    procedure_code=code,
                    service=descriptions.get(code),
                    status="NOT_PAID",
                    billed_cents=charge if isinstance(charge, int) else None,
                    allowed_cents=None,
                    plan_pays_cents=None,
                    patient_pays_cents=None,
                    other_plan_paid_cents=None,
                    notes=_not_paid(by_line.get(line_no, [])),
                    codes=codes.get(line_no, []),
                )
            )
    notes = [NOT_A_BILL]
    for reason in reasons:
        if reason.line_no is None and reason.text.provider not in notes:
            notes.append(reason.text.provider)
    if bill is None:
        notes.append(NO_CALCULATION)
    if any(line.status == "PENDING" for line in lines):
        notes.append(PENDING_NOTE)
    totals = (
        EobTotals(
            billed_cents=bill.totals.billed_cents,
            allowed_cents=bill.totals.allowed_cents,
            plan_pays_cents=bill.totals.plan_pays_cents,
            patient_pays_cents=bill.totals.patient_pays_cents,
            other_plan_paid_cents=bill.totals.other_plan_paid_cents,
        )
        if bill is not None
        else None
    )
    decided = record.timestamps.finalized or record.timestamps.processed
    npi = claim.get("billing_npi")
    member = claim.get("member_id")
    return PatientEob(
        claim_id=record.claim_id,
        outcome=outcome,
        patient_name=_patient_name(claim),
        member_id=member if isinstance(member, str) else None,
        plan_name=plan_name,
        provider_name=provider_name,
        provider_npi=npi if isinstance(npi, str) else None,
        network=record.context_refs.network.value if record.context_refs else None,
        received=record.timestamps.received.isoformat(),
        processed=decided.date().isoformat() if decided else None,
        lines=lines,
        totals=totals,
        year_to_date=year_to_date,
        notes=notes,
        codes=codes.get(None, []),
    )
