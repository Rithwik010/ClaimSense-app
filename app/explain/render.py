"""Explanations (INSTRUCTIONS.md §8.7, P5.4): rendered with Jinja2 from the DecisionRecord only
(H15). Sections: summary, rule checks, each line's decision with its criteria, evidence and policy
citations, amounts per line and totals, the review and the versions. On a FINAL_PENDED claim the
lines already processed are listed apart from those awaiting documentation (D-REV-7).

Every amount comes from the record's calculator breakdown (integer cents, formatted here); every
reason is a reason code the record holds, with a fixed plain-language label. The only model text
shown is the evidence the record keeps for each criterion (quoted from the clinical notes or the
fixed wording for NOT_DOCUMENTED and NOT_APPLICABLE).
"""

from dataclasses import dataclass, field
from typing import Any

from jinja2 import Environment, PackageLoader, StrictUndefined, select_autoescape

from app.domain.contracts import (
    ClaimStatus,
    CriterionStatus,
    DecisionRecord,
    LineAmounts,
    LineDecision,
)

REASON_LABELS = {
    "RJ_MISSING_FIELD": "a required field is missing",
    "RJ_INVALID_CODE": "a code is not valid",
    "RJ_INVALID_NPI": "the provider NPI is not valid",
    "RJ_MEMBER_NOT_FOUND": "the member was not found",
    "RJ_PROVIDER_NOT_FOUND": "the provider was not found",
    "RJ_DUPLICATE": "the claim duplicates one already filed",
    "RJ_LOW_CONFIDENCE_FIELD": "a rule failed on a field read with low confidence",
    "DN_NOT_ELIGIBLE": "the member was not covered on the date of service",
    "DN_LATE_FILING": "the claim was filed after the plan's filing window",
    "DN_OUT_OF_NETWORK": "out-of-network care that the plan does not cover",
    "DN_MISSING_REFERRAL": "a required referral is missing",
    "DN_NO_AUTH": "a required prior authorization is missing",
    "DN_NCCI_BUNDLED": "the service is bundled into another service on the claim (NCCI)",
    "DN_MUE_EXCEEDED": "more units than the medically unlikely edit allows",
    "DN_EXCLUDED": "the plan excludes this service",
    "DN_MULTIPLE_BLOCKS": "another block on the same day (epidural steroid injection policy)",
    "DN_DX_NOT_SUPPORTED": "the diagnoses do not support the service (billing article)",
    "DN_HOME_TEST_PARASOMNIA": "a home sleep test billed for a parasomnia",
    "DN_ESI_LEVELS": "more epidural injection levels than the policy allows",
    "DN_FACET_LEVELS": "more facet levels than the policy allows",
    "DN_NOT_MEDICALLY_NECESSARY": "not medically necessary under the coverage criteria",
    "DN_CONDITIONAL_EXCLUSION": "a coverage policy excludes the service in this situation",
    "PD_PROVIDER_ENROLLMENT": "the provider's enrollment needs checking",
    "PD_MISSING_DOCUMENTATION": "documentation is missing",
    "MODEL_OUTPUT_INVALID": "the recommendation could not be used and needs a full review",
}
DECISION_LABELS = {
    LineDecision.APPROVE: "Approved",
    LineDecision.DENY: "Denied",
    LineDecision.PEND: "Needs information",
}
STATUS_LABELS = {
    ClaimStatus.FINAL_APPROVED: "Approved",
    ClaimStatus.FINAL_DENIED: "Denied",
    ClaimStatus.FINAL_PENDED: "Needs information",
    ClaimStatus.FINAL_PARTIAL: "Partly approved",
    ClaimStatus.REJECTED: "Rejected",
    ClaimStatus.DENIED_BY_RULE: "Denied by a rule",
    ClaimStatus.PENDED_BY_RULE: "Needs information (a rule)",
    ClaimStatus.AWAITING_REVIEW: "Awaiting review",
}
CRITERION_LABELS = {
    CriterionStatus.MET: "met",
    CriterionStatus.NOT_MET: "not met",
    CriterionStatus.NOT_DOCUMENTED: "not documented",
    CriterionStatus.NOT_APPLICABLE: "does not apply",
}
SOURCE_LABELS = {
    "RULE": "a rule",
    "MODEL": "the model's recommendation",
    "REVIEWER": "the reviewer",
    "VALIDATION": "output validation",
}
AMOUNT_FIELDS = (
    ("billed_cents", "Billed"),
    ("allowed_cents", "Allowed"),
    ("contractual_adjustment_cents", "Contractual adjustment"),
    ("deductible_cents", "Deductible"),
    ("copay_cents", "Copay"),
    ("coinsurance_cents", "Coinsurance"),
    ("cob_primary_paid_cents", "Paid by the primary plan"),
    ("plan_pays_cents", "Plan pays"),
    ("member_pays_cents", "Member pays"),
    ("balance_bill_exposure_cents", "Balance-bill exposure"),
)


def money(cents: int) -> str:
    """Integer cents as dollars, with no float on the way (H2)."""
    sign = "-" if cents < 0 else ""
    dollars, rest = divmod(abs(cents), 100)
    return f"{sign}${dollars:,}.{rest:02d}"


def reason(code: str) -> str:
    label = REASON_LABELS.get(code)
    return f"{code} ({label})" if label else code


@dataclass
class CriterionView:
    criterion_id: str
    status: str
    evidence: str
    policy_id: str
    policy_title: str
    text: str


@dataclass
class LineView:
    line_no: int
    procedure_code: str
    decision: str
    decision_label: str
    source: str
    benefit_category: str | None
    reasons: list[str]
    criteria: list[CriterionView] = field(default_factory=list)
    missing_information: list[str] = field(default_factory=list)
    amounts: list[tuple[str, str]] = field(default_factory=list)


def _amounts(line: LineAmounts | None) -> list[tuple[str, str]]:
    if line is None:
        return []
    return [(label, money(getattr(line, name))) for name, label in AMOUNT_FIELDS]


def view(record: DecisionRecord) -> dict[str, Any]:
    """Everything the templates show, taken from the record alone."""
    context = {c.line_no: c for c in (record.context_refs.lines if record.context_refs else [])}
    model = {line.line_no: line for line in (record.slm_output.lines if record.slm_output else [])}
    amounts = {a.line_no: a for a in (record.amounts.lines if record.amounts else [])}
    lines = []
    for final in sorted(record.line_decisions, key=lambda d: d.line_no):
        ctx = context.get(final.line_no)
        criteria_by_id = {c.criterion_id: c for c in (ctx.criteria if ctx else [])}
        answer = model.get(final.line_no)
        criteria = []
        if final.source in ("MODEL", "REVIEWER") and answer is not None:
            for result in answer.criteria:
                cited = criteria_by_id.get(result.criterion_id)
                criteria.append(
                    CriterionView(
                        result.criterion_id,
                        CRITERION_LABELS[result.status],
                        result.evidence,
                        cited.policy_id if cited else result.criterion_id.split(".")[0],
                        cited.policy_title if cited else "",
                        cited.text if cited else "",
                    )
                )
        lines.append(
            LineView(
                line_no=final.line_no,
                procedure_code=ctx.procedure_code if ctx else "",
                decision=final.decision.value,
                decision_label=DECISION_LABELS[final.decision],
                source=SOURCE_LABELS[final.source],
                benefit_category=final.benefit_category,
                reasons=[reason(code) for code in final.reason_codes],
                criteria=criteria,
                missing_information=(
                    list(answer.missing_information)
                    if answer is not None and final.decision is LineDecision.PEND
                    else []
                ),
                amounts=_amounts(amounts.get(final.line_no)),
            )
        )
    pended_claim = record.status is ClaimStatus.FINAL_PENDED
    review = record.review
    return {
        "claim_id": record.claim_id,
        "status": record.status.value,
        "status_label": STATUS_LABELS.get(record.status, record.status.value),
        "claim_decision": record.claim_decision.value if record.claim_decision else None,
        "review_tier": record.review_tier.value if record.review_tier else None,
        "timestamps": record.timestamps,
        "rules": [
            {
                "rule_id": r.rule_id,
                "result": "passed" if r.passed else "failed",
                "outcome": r.outcome.value,
                "reason": reason(r.reason_code) if r.reason_code else "",
                "detail": r.detail,
                "line_no": r.line_no,
            }
            for r in record.rules_outcome.rule_results
        ],
        "lines": lines,
        "processed": [ln for ln in lines if ln.decision != "PEND"] if pended_claim else [],
        "awaiting": [ln for ln in lines if ln.decision == "PEND"] if pended_claim else [],
        "totals": (
            [(label, money(getattr(record.amounts.totals, name))) for name, label in AMOUNT_FIELDS]
            if record.amounts
            else []
        ),
        "output_errors": list(record.output_errors),
        "review": (
            {
                "reviewer_id": review.reviewer_id,
                "action": review.action.value,
                "timestamp": review.timestamp,
                "reason": review.reason or "",
                "overrides": [
                    {
                        "line_no": o.line_no,
                        "decision": DECISION_LABELS[o.decision],
                        "reason": o.reason,
                        "benefit_category": o.benefit_category,
                    }
                    for o in review.line_overrides
                ],
            }
            if review
            else None
        ),
        "versions": record.versions,
    }


_ENV = Environment(
    loader=PackageLoader("app.explain", "templates"),
    autoescape=select_autoescape(("html",)),
    undefined=StrictUndefined,
    trim_blocks=True,
    lstrip_blocks=True,
)
# Free text (rule details, evidence, needs) on one line, so the text layout stays line-based.
_ENV.filters["oneline"] = lambda value: " ".join(str(value).split())


def render(record: DecisionRecord, fmt: str = "html") -> str:
    """The explanation as an HTML fragment ("html") or plain text ("text")."""
    template = _ENV.get_template(f"explanation.{'html' if fmt == 'html' else 'txt'}")
    return template.render(**view(record))
