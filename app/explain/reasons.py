"""The reason table (D-UI-6): plain words for every internal reason code the system can produce.

Each entry has a short reason (one line, at most 60 characters), a provider sentence (one or two
plain sentences, with no rule IDs, internal codes or jargon) and what to check (items that may name
a claim field; the provider's view shows the value the claim carries next to it). It is the single
source for the claim lists' Reason column, the provider's explanation and billing, and the claim
summary (app/explain/provider.py, app/explain/summary.py). The reviewer's explanation keeps its own
labels (render.py, D-EXPL-1).

The codes come from the rules (R01 to R16, R18, R19 and R21, the duplicate check, and the
low-confidence conversion H5), the model's line derivation (app/ml/derive.py) and output validation
(MODEL_OUTPUT_INVALID). R17 and R20 only flag lines, as do R11's NCCI bypass and R19's two-region
check: they produce no reason code. A line a reviewer denies or pends carries the reason code the
reviewer chose (D-REV-9, app/review/actions.py), worded by its entry here; two keys of this table
only, RV_DENIED_ON_REVIEW and RV_PENDED_ON_REVIEW, explain a reviewer's line without a code (a
record from before D-REV-9); they never enter a decision record and have no CARC/RARC mapping. A
CARC or RARC itself is shown with its official description (app/explain/codes.py). The wording is
team-written; nothing is copied from AMA CPT descriptors or payer documents.
"""

from dataclasses import dataclass
from typing import Literal

from app.domain.contracts import ClaimStatus, DecisionRecord, LineDecision

# What a "what to check" item adds besides its fixed text (app/explain/provider.py fills it in).
Detail = Literal[
    "missing_fields",  # the fields a failed rule found missing
    "codes",  # every code on the claim
    "invalid_npis",  # the NPIs that fail the check digit
    "low_confidence",  # the fields read below the confidence threshold, and what was read
    "line_diagnoses",  # the diagnoses a line points to
    "not_met",  # the coverage criteria the notes show are not met
    "exclusions",  # the coverage exclusions that apply
    "not_documented",  # the coverage criteria the notes do not document
]


@dataclass(frozen=True)
class Check:
    """One "what to check" item. `field` names a claim field; `{i}` in it is the line's index on
    the claim and `{line}` in the text its line number."""

    text: str
    field: str | None = None


@dataclass(frozen=True)
class ReasonText:
    code: str
    rules: tuple[str, ...]  # the rules that produce it; () for the model, validation or a reviewer
    short: str  # one line, at most 60 characters
    provider: str  # one or two plain sentences: no rule IDs, internal codes or jargon
    check: tuple[Check, ...] = ()
    detail: Detail | None = None


REVIEWER_DENIED = "RV_DENIED_ON_REVIEW"
REVIEWER_PENDED = "RV_PENDED_ON_REVIEW"
FLAG_ONLY_RULES = ("R17", "R20")  # rules that flag lines and never deny or reject

_MEMBER = Check("Member ID on the claim", "member_id")
_BILLING_NPI = Check("Billing provider NPI on the claim", "billing_npi")
_RENDERING_NPI = Check("Rendering provider NPI on line {line}", "service_lines.{i}.rendering_npi")
_DATE = Check("Date of service on line {line}", "service_lines.{i}.date_of_service")
_CODE = Check("Procedure code on line {line}", "service_lines.{i}.procedure_code")
_MODIFIERS = Check("Modifiers on line {line}", "service_lines.{i}.modifiers")
_UNITS = Check("Units on line {line}", "service_lines.{i}.units")
_NOTES = Check("The clinical notes for this service.")

_TABLE = (
    ReasonText(
        "RJ_MISSING_FIELD",
        ("R01",),
        "A required field is missing",
        "The claim is missing information that every claim must include, so it could not be "
        "processed.",
        (Check("That every required box of the claim form is filled in."),),
        "missing_fields",
    ),
    ReasonText(
        "RJ_INVALID_CODE",
        ("R02",),
        "A code on the claim is not valid",
        "A diagnosis, procedure or place-of-service code on the claim is not a valid code, so the "
        "claim could not be processed.",
        (Check("That each code is current on the date of service and written in full."),),
        "codes",
    ),
    ReasonText(
        "RJ_INVALID_NPI",
        ("R03",),
        "A provider NPI is not valid",
        "A National Provider Identifier (NPI) on the claim is not a valid NPI, so the claim could "
        "not be processed.",
        (Check("That each NPI has 10 digits and is copied exactly."),),
        "invalid_npis",
    ),
    ReasonText(
        "RJ_MEMBER_NOT_FOUND",
        ("R04",),
        "Member not found",
        "The member ID on the claim does not match any member of the plan, so the claim could not "
        "be processed.",
        (
            _MEMBER,
            Check("Patient last name on the claim", "patient.last_name"),
            Check("Patient date of birth on the claim", "patient.date_of_birth"),
            Check("That the member ID matches the one on the member's insurance card."),
        ),
    ),
    ReasonText(
        "RJ_DUPLICATE",
        ("DUP",),
        "Duplicate of a claim already on file",
        "Another claim on file already has the same member, provider, date of service and "
        "procedure code, so this claim was not processed.",
        (
            _MEMBER,
            _BILLING_NPI,
            _DATE,
            _CODE,
            Check("Whether this service was already billed on an earlier claim."),
        ),
    ),
    ReasonText(
        "RJ_PROVIDER_NOT_FOUND",
        ("R06",),
        "Provider not found",
        "A provider NPI on the claim does not match any provider in the plan's records, so the "
        "claim could not be processed.",
        (
            _BILLING_NPI,
            _RENDERING_NPI,
            Check("That each NPI belongs to a provider who works with the plan."),
        ),
    ),
    ReasonText(
        "RJ_LOW_CONFIDENCE_FIELD",
        (),  # any failing rule that used a field read below the threshold (H5)
        "Part of the claim could not be read clearly",
        "Some details on the claim form could not be read clearly, and the claim could not be "
        "checked without them, so it could not be processed.",
        (Check("That the form is complete and clearly legible."),),
        "low_confidence",
    ),
    ReasonText(
        "DN_NOT_ELIGIBLE",
        ("R05",),
        "Member not covered on the date of service",
        "The member's coverage was not active on the date of service, so the plan does not pay "
        "for this claim.",
        (_MEMBER, _DATE, Check("The member's coverage dates.")),
    ),
    ReasonText(
        "PD_PROVIDER_ENROLLMENT",
        ("R06",),
        "Provider enrollment is pending",
        "A provider on the claim has an enrollment with the plan that is still pending, so the "
        "claim is on hold.",
        (_BILLING_NPI, _RENDERING_NPI, Check("The provider's enrollment status with the plan.")),
    ),
    ReasonText(
        "DN_LATE_FILING",
        ("R07",),
        "Received after the filing time limit",
        "The claim was received after the plan's time limit for filing, counted from the date of "
        "service.",
        (
            Check("Date received on the claim", "received_date"),
            _DATE,
            Check("The plan's time limit for filing claims."),
        ),
    ),
    ReasonText(
        "DN_OUT_OF_NETWORK",
        ("R08",),
        "Out-of-network provider not covered",
        "The billing provider is not in the member's plan network, and the plan does not cover "
        "out-of-network care.",
        (_BILLING_NPI, _MEMBER, Check("Whether the provider is in the member's plan network.")),
    ),
    ReasonText(
        "DN_MISSING_REFERRAL",
        ("R09",),
        "Required referral missing",
        "The member's plan needs a referral for this type of care, and the claim does not name a "
        "referring provider.",
        (
            Check("Referring provider NPI on the claim", "referring_npi"),
            _RENDERING_NPI,
            Check("Whether the member was referred for this care."),
        ),
    ),
    ReasonText(
        "DN_NO_AUTH",
        ("R10",),
        "Required prior authorization missing",
        "A service on this claim needs prior authorization under the member's plan, and no "
        "authorization was found for this member, provider, service and date.",
        (
            Check("Prior authorization number on the claim", "prior_auth_number"),
            _CODE,
            _RENDERING_NPI,
            _DATE,
        ),
    ),
    ReasonText(
        "DN_NCCI_BUNDLED",
        ("R11",),
        "Included in another service on the claim",
        "This service is normally part of another service billed on the same date, so it is not "
        "paid separately.",
        (_CODE, _MODIFIERS, _DATE, Check("The other services billed on the same date.")),
    ),
    ReasonText(
        "DN_MUE_EXCEEDED",
        ("R12",),
        "More units than allowed on one date",
        "The units billed for this service on one date are more than the most that is normally "
        "billed for one patient on one day.",
        (_UNITS, _CODE, _DATE),
    ),
    ReasonText(
        "DN_EXCLUDED",
        ("R13",),
        "Service not covered by the member's plan",
        "The member's plan does not cover this service.",
        (_CODE, Check("The services the member's plan excludes.")),
    ),
    ReasonText(
        "DN_MULTIPLE_BLOCKS",
        ("R14",),
        "Another spinal injection on the same date",
        "This epidural steroid injection was billed on the same date as another kind of spinal "
        "injection, which its coverage policy does not cover.",
        (_CODE, _DATE, Check("The other injections billed on the same date.")),
    ),
    ReasonText(
        "DN_DX_NOT_SUPPORTED",
        ("R15",),
        "Diagnoses do not support the service",
        "The diagnoses this service points to are not among the diagnoses that support it under "
        "its coverage policy.",
        (_CODE, Check("That each service points to the diagnoses it treats.")),
        "line_diagnoses",
    ),
    ReasonText(
        "DN_HOME_TEST_PARASOMNIA",
        ("R16",),
        "Home sleep test billed for a parasomnia",
        "A home sleep test is not covered when its diagnosis is a parasomnia, a sleep disorder "
        "with unusual behavior during sleep.",
        (_CODE,),
        "line_diagnoses",
    ),
    ReasonText(
        "DN_ESI_LEVELS",
        ("R18",),
        "More injection levels than covered",
        "More spinal levels or sides were billed for these epidural steroid injections on one "
        "date than their coverage policy covers.",
        (_CODE, _MODIFIERS, _UNITS, _DATE),
    ),
    ReasonText(
        "DN_FACET_LEVELS",
        ("R19",),
        "More facet joint levels than covered",
        "The coverage policy for facet joint procedures does not cover a third spinal level on "
        "one date.",
        (_CODE, _DATE),
    ),
    ReasonText(
        "DN_VISIT_LIMIT",
        ("R21",),
        "Yearly visit limit used up",
        "The member's plan covers a set number of these visits each year, and they have already "
        "been used for this benefit year.",
        (_CODE, _DATE),
    ),
    ReasonText(
        "DN_NOT_MEDICALLY_NECESSARY",
        (),
        "Coverage criteria not met",
        "Based on the clinical notes, this service does not meet the coverage criteria for it.",
        (_NOTES,),
        "not_met",
    ),
    ReasonText(
        "DN_CONDITIONAL_EXCLUSION",
        (),
        "Excluded by its coverage policy in this case",
        "Based on the clinical notes, the coverage policy for this service excludes it in this "
        "situation.",
        (_NOTES,),
        "exclusions",
    ),
    ReasonText(
        "PD_MISSING_DOCUMENTATION",
        (),
        "More documentation needed",
        "The clinical notes do not show everything the coverage policy for this service asks "
        "for, so this service is on hold.",
        (),
        "not_documented",
    ),
    ReasonText(
        "MODEL_OUTPUT_INVALID",
        (),
        "Could not be assessed automatically",
        "This service could not be assessed automatically from the claim, so it is on hold.",
        (_NOTES, _CODE),
    ),
    ReasonText(
        REVIEWER_DENIED,
        (),
        "Denied on review",
        "A reviewer decided that the plan does not pay for this service.",
        (_NOTES,),
    ),
    ReasonText(
        REVIEWER_PENDED,
        (),
        "On hold after review",
        "A reviewer put this service on hold because more information is needed.",
        (_NOTES,),
    ),
)
REASONS: dict[str, ReasonText] = {entry.code: entry for entry in _TABLE}


def reason_text(code: str) -> ReasonText:
    """The table's entry; a code missing from it (which a unit test rules out) gets plain
    wording rather than an error, so a page never breaks on it."""
    return REASONS.get(code) or ReasonText(
        code, (), "Not paid as billed", "This service was not paid as billed."
    )


# --- Outcomes: one label set for every dashboard -------------------------------------------------

OUTCOME_LABELS = {
    "NOT_PROCESSED": "Not processed",
    "IN_REVIEW": "In review",
    "APPROVED": "Approved",
    "PARTLY_APPROVED": "Partly approved",
    "PENDED": "Pended",
    "DENIED": "Denied",
    "REJECTED": "Rejected",
}
STATUS_OUTCOMES = {
    ClaimStatus.RECEIVED: "NOT_PROCESSED",
    ClaimStatus.AWAITING_REVIEW: "IN_REVIEW",
    ClaimStatus.FINAL_APPROVED: "APPROVED",
    ClaimStatus.FINAL_PARTIAL: "PARTLY_APPROVED",
    ClaimStatus.FINAL_PENDED: "PENDED",  # PARTLY_APPROVED when a line was approved (paid)
    ClaimStatus.FINAL_DENIED: "DENIED",
    ClaimStatus.REJECTED: "REJECTED",
    ClaimStatus.DENIED_BY_RULE: "DENIED",
    ClaimStatus.PENDED_BY_RULE: "PENDED",
}
RULE_STATUSES = frozenset(
    {ClaimStatus.REJECTED, ClaimStatus.DENIED_BY_RULE, ClaimStatus.PENDED_BY_RULE}
)
REASONED_OUTCOMES = frozenset({"REJECTED", "DENIED", "PENDED", "PARTLY_APPROVED"})


def claim_outcome(status: ClaimStatus, record: DecisionRecord | None) -> str:
    """The claim's label key. Mixed line outcomes count as partly approved: a pended claim with an
    approved (paid) line (D-REV-7) is PARTLY_APPROVED, like FINAL_PARTIAL."""
    if (
        status is ClaimStatus.FINAL_PENDED
        and record is not None
        and any(line.decision is LineDecision.APPROVE for line in record.line_decisions)
    ):
        return "PARTLY_APPROVED"
    return STATUS_OUTCOMES[status]


def provider_outcome(outcome: str) -> str:
    """What a provider sees: a claim not processed yet is in review to them."""
    return "IN_REVIEW" if outcome == "NOT_PROCESSED" else outcome


# --- A claim's reasons ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ClaimReason:
    """One reason a claim, or one of its lines, was not paid as billed."""

    code: str
    rule_id: str | None  # the rule that produced it; None for the model, validation or a reviewer
    line_no: int | None  # None: the whole claim
    fields_used: tuple[str, ...] = ()  # the failed rule's fields (A-R9)

    @property
    def text(self) -> ReasonText:
        return reason_text(self.code)


def claim_reasons(record: DecisionRecord | None) -> list[ClaimReason]:
    """Why the claim, or its lines, were not paid as billed: for a claim the rules decided, each
    failed rule in rule order; otherwise each line not approved, in line order, with its reason
    codes (a reviewer's denial or pend, which has none, gets the RV_ key)."""
    if record is None:
        return []
    failed = [
        r for r in record.rules_outcome.rule_results if not r.passed and r.reason_code is not None
    ]
    found: list[ClaimReason] = []

    def add(reason: ClaimReason) -> None:
        if all((r.code, r.line_no) != (reason.code, reason.line_no) for r in found):
            found.append(reason)

    if record.status in RULE_STATUSES:
        for r in failed:
            add(ClaimReason(r.reason_code or "", r.rule_id, r.line_no, tuple(r.fields_used)))
        return found
    for line in sorted(record.line_decisions, key=lambda d: d.line_no):
        if line.decision is LineDecision.APPROVE:
            continue
        codes = line.reason_codes or [
            REVIEWER_DENIED if line.decision is LineDecision.DENY else REVIEWER_PENDED
        ]
        for code in codes:
            rule = next(
                (r for r in failed if r.reason_code == code and r.line_no == line.line_no), None
            )
            if line.source == "RULE" and rule is not None:
                add(ClaimReason(code, rule.rule_id, line.line_no, tuple(rule.fields_used)))
            else:
                add(ClaimReason(code, None, line.line_no))
    return found


def shown_reasons(outcome: str, record: DecisionRecord | None) -> list[ClaimReason]:
    """The reasons a list shows: for rejected, denied, pended and partly approved claims only."""
    return claim_reasons(record) if outcome in REASONED_OUTCOMES else []
