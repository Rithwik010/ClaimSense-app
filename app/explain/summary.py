"""The claim summary for reviewers and admins (D-UI-6): a few short lines, built deterministically
from the decision record and the reason table, never by the model (H15).

- At a glance: the number of lines, the billed total, and the review tier with why (the reason
  review_tier in app/review/tiers.py picked it, read back from the record).
- Checks: all passed, or where the claim stopped, with the short reason and the rule ID.
- Each line: its code, the recommended (or final) decision and its key reason.
- Amounts: what the plan and the patient pay if the recommendation is accepted, or once final.
- Flags, only those present: low-confidence fields, a high amount, out of network, NCCI bypass.
- The outcome, for a claim the rules decided or a final one.
The billed total of a claim without amounts adds the charges as filed, as the review queue does.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from app.domain.contracts import (
    ClaimStatus,
    Complexity,
    CriterionStatus,
    DecisionRecord,
    FinalLineDecision,
    LineDecision,
    ReviewActionType,
)
from app.explain.codes import procedure_codes
from app.explain.provider import bypass_flagged, line_criteria
from app.explain.reasons import (
    OUTCOME_LABELS,
    RULE_STATUSES,
    ClaimReason,
    claim_outcome,
    claim_reasons,
)
from app.explain.render import GUARD_NOTE, money

TIERS = {"QUICK": "Quick", "STANDARD": "Standard", "FULL": "Full"}
RECOMMENDED = {
    LineDecision.APPROVE: "Approve",
    LineDecision.PEND: "Pend",
    LineDecision.DENY: "Deny",
}
FINAL = {
    LineDecision.APPROVE: "Approved",
    LineDecision.PEND: "Pended",
    LineDecision.DENY: "Denied",
}
OON_FLAG, BYPASS_FLAG = "OON", "NCCI_BYPASS"


@dataclass(frozen=True)
class SummaryItem:
    kind: str  # glance, checks, line, amounts, flags or outcome
    text: str
    line_no: int | None = None


@dataclass(frozen=True)
class ClaimSummary:
    outcome: str  # the claim's label key (reasons.claim_outcome)
    outcome_label: str
    items: list[SummaryItem]


def answer_errors(record: DecisionRecord) -> list[str]:
    """The output-validation errors: not the evidence guard's notes or a failed calculation."""
    return [
        e
        for e in record.output_errors
        if not GUARD_NOTE.match(e) and not e.startswith("CALCULATION_FAILED")
    ]


def tier_reason(record: DecisionRecord, low_confidence: list[str], high_dollar_cents: int) -> str:
    """Why the claim got its review tier, in the order app/review/tiers.py decides it."""
    if any(e.startswith("CALCULATION_FAILED") for e in record.output_errors):
        return "the amounts could not be calculated"
    output = record.slm_output
    if output is None or answer_errors(record):
        return "the model's answer could not be used"
    decisions = {line.decision for line in output.lines}
    if LineDecision.DENY in decisions:
        return "a line recommended for denial"
    if output.complexity is Complexity.HIGH:
        return "a high-complexity case"
    if LineDecision.PEND in decisions:
        return "a line recommended to pend"
    if output.complexity is Complexity.MEDIUM:
        return "a medium-complexity case"
    allowed = record.amounts.totals.allowed_cents if record.amounts else 0
    if allowed >= high_dollar_cents:
        return "a high amount"
    if low_confidence:
        return "fields read with low confidence"
    return "every line recommended for approval"


def _billed(record: DecisionRecord | None, claim: Mapping[str, Any]) -> int:
    if record is not None and record.amounts is not None:
        return record.amounts.totals.billed_cents
    lines = [ln for ln in claim.get("service_lines") or [] if isinstance(ln, Mapping)]
    return sum(c for ln in lines if isinstance(c := ln.get("charge_cents"), int))


def _glance(
    status: ClaimStatus,
    record: DecisionRecord | None,
    claim: Mapping[str, Any],
    low_confidence: list[str],
    high_dollar_cents: int,
) -> str:
    count = len([ln for ln in claim.get("service_lines") or [] if isinstance(ln, Mapping)])
    head = f"{count} line{'' if count == 1 else 's'}, {money(_billed(record, claim))} billed"
    if record is None:
        return f"{head}; not processed yet."
    if status in RULE_STATUSES:
        return f"{head}; decided by the automatic checks, with no review."
    if record.review_tier is None:
        return f"{head}."
    tier = TIERS[record.review_tier.value]
    return f"{head}; {tier} review: {tier_reason(record, low_confidence, high_dollar_cents)}."


def _reason_text(reason: ClaimReason) -> str:
    rule = f" ({reason.rule_id})" if reason.rule_id else ""
    return f"{reason.text.short}{rule}"


def _checks(status: ClaimStatus, record: DecisionRecord | None) -> str:
    if record is None:
        return "Checks not run yet."
    failed = [r for r in record.rules_outcome.rule_results if not r.passed]
    if status in RULE_STATUSES:
        reasons = claim_reasons(record)
        if not reasons:
            return "Stopped at the checks."
        first = reasons[0]
        where = f", line {first.line_no}" if first.line_no else ""
        more = f" and {len(reasons) - 1} more" if len(reasons) > 1 else ""
        return f"Stopped at the checks: {_reason_text(first)}{where}{more}."
    if not failed:
        return "All checks passed."
    lines = sorted({r.line_no for r in failed if r.line_no is not None})
    first = next(r for r in failed if r.reason_code)
    short = ClaimReason(first.reason_code or "", first.rule_id, first.line_no)
    which = ", ".join(str(n) for n in lines)
    return (
        f"Checks passed for the claim; line{'s' if len(lines) > 1 else ''} {which} denied by a "
        f"check: {_reason_text(short)}."
    )


def _criteria_reason(record: DecisionRecord, line: FinalLineDecision) -> str:
    """The key reason of a model line from its criteria: an indication group counts as one
    criterion, met when any of its members is (D-POL-3); NOT_APPLICABLE ones do not count."""
    statuses = line_criteria(record, line.line_no)
    grouped = [s for s in statuses if s[1] is not None and s[1].group]
    single = [s for s in statuses if not (s[1] is not None and s[1].group)]
    applicable = [s for s in single if s[2] is not CriterionStatus.NOT_APPLICABLE]
    met = sum(1 for s in applicable if s[2] is CriterionStatus.MET)
    total = len(applicable)
    group_met = any(s[2] is CriterionStatus.MET for s in grouped)
    if grouped:
        total += 1
        met += int(group_met)
    if line.decision is LineDecision.APPROVE:
        return f"{met} of {total} criteria met" if total else "no coverage criteria apply"
    if line.decision is LineDecision.DENY:
        return ""
    if grouped and not group_met:
        return "Not documented: a covered reason for the service"
    missing = next((s for s in applicable if s[2] is CriterionStatus.NOT_DOCUMENTED), None)
    if missing is None and bypass_flagged(record, line.line_no):
        return "Not documented: a separate, distinct service for the NCCI bypass modifier"
    if missing is None:
        return "Not documented: documentation that supports the service"
    text = missing[1].text if missing[1] else missing[0]
    return f"Not documented: {text}"


def _line_item(
    record: DecisionRecord, line: FinalLineDecision, code: str, final: bool
) -> SummaryItem:
    words = (FINAL if final else RECOMMENDED)[line.decision]
    head = f"Line {line.line_no}" + (f", {code}" if code else "")
    reasons = [r for r in claim_reasons(record) if r.line_no == line.line_no]
    if line.source == "REVIEWER":
        why = "Changed by the reviewer"
    elif line.decision is LineDecision.APPROVE:
        why = _criteria_reason(record, line)
    elif line.decision is LineDecision.DENY or line.source in ("RULE", "VALIDATION"):
        why = _reason_text(reasons[0]) if reasons else ""
    else:
        why = _criteria_reason(record, line)
    why = f"{why[:1].upper()}{why[1:]}".rstrip(".")
    return SummaryItem("line", f"{head}: {words}." + (f" {why}." if why else ""), line.line_no)


def _flags(
    record: DecisionRecord | None, low_confidence: list[str], high_dollar_cents: int
) -> str | None:
    found = []
    if low_confidence:
        n = len(low_confidence)
        found.append(f"{n} field{'' if n == 1 else 's'} read with low confidence")
    if record is not None:
        if record.amounts and record.amounts.totals.allowed_cents >= high_dollar_cents:
            found.append("a high amount")
        network = record.context_refs.network.value if record.context_refs else None
        if OON_FLAG in record.rules_outcome.flags or network == "OUT_OF_NETWORK":
            found.append("an out-of-network provider")
        bypass = [o.line_no for o in record.rules_outcome.line_outcomes if BYPASS_FLAG in o.flags]
        if bypass:
            lines = ", ".join(str(n) for n in bypass)
            found.append(f"an NCCI bypass modifier on line{'s' if len(bypass) > 1 else ''} {lines}")
    return f"Flags: {'; '.join(found)}." if found else None


def _outcome(status: ClaimStatus, record: DecisionRecord | None, outcome: str) -> str | None:
    label = OUTCOME_LABELS[outcome].lower()
    if record is None or status is ClaimStatus.AWAITING_REVIEW:
        return None
    if status in RULE_STATUSES:
        return f"Outcome: {label} by the automatic checks."
    review = record.review
    if review is None:
        return f"Outcome: {label}."
    if review.action is ReviewActionType.ACCEPT:
        how = f"{review.reviewer_id} accepted the recommendation"
    else:
        n = len(review.line_overrides)
        how = f"{review.reviewer_id} changed {n} line{'' if n == 1 else 's'}"
    return f"Outcome: {label} after review; {how}."


def claim_summary(
    status: ClaimStatus,
    record: DecisionRecord | None,
    claim: Mapping[str, Any],
    confidences: Mapping[str, float],
    threshold: float,
    high_dollar_cents: int,
) -> ClaimSummary:
    """The summary of a claim as it stands (`record` None before processing)."""
    outcome = claim_outcome(status, record)
    low = sorted(path for path, value in confidences.items() if value < threshold)
    items = [
        SummaryItem("glance", _glance(status, record, claim, low, high_dollar_cents)),
        SummaryItem("checks", _checks(status, record)),
    ]
    if record is not None:
        codes = procedure_codes(claim)
        final = status is not ClaimStatus.AWAITING_REVIEW
        items += [
            _line_item(record, line, str(codes.get(line.line_no, "")), final)
            for line in sorted(record.line_decisions, key=lambda d: d.line_no)
        ]
        if record.amounts is not None and record.line_decisions:
            t = record.amounts.totals
            lead = "If accepted" if status is ClaimStatus.AWAITING_REVIEW else "Final"
            items.append(
                SummaryItem(
                    "amounts",
                    f"{lead}: plan pays {money(t.plan_pays_cents)}, patient pays "
                    f"{money(t.member_pays_cents)}.",
                )
            )
        elif any(e.startswith("CALCULATION_FAILED") for e in record.output_errors):
            items.append(SummaryItem("amounts", "No amounts: the calculation could not run."))
    if (flags := _flags(record, low, high_dollar_cents)) is not None:
        items.append(SummaryItem("flags", flags))
    if (text := _outcome(status, record, outcome)) is not None:
        items.append(SummaryItem("outcome", text))
    return ClaimSummary(outcome, OUTCOME_LABELS[outcome], items)
