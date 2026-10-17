"""Shared contracts (INSTRUCTIONS.md §8.1; DECISIONS.md 2026-09-21 and 2026-09-22).

Approved by the team on 2026-09-22 (task P1.4) and frozen: do not add, remove or rename fields
without approval (H11). The model output and the context shown to the model are part of the trained
model's interface, so changing them means regenerating the dataset and retraining.

Conventions: money is integer cents (`*_cents`, strict int, never float); every model rejects
unknown fields; codes are validated for format only (whether a code exists is rule R02's job).
The claim carries only CMS-1500 data: eligibility, network status and coverage are looked up.
"""

import re
from datetime import date, datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)

# --- Enumerations --------------------------------------------------------------------------------


class SourceFormat(StrEnum):
    JSON = "JSON"
    DIGITAL_PDF = "DIGITAL_PDF"
    SCANNED = "SCANNED"


class Sex(StrEnum):
    F = "F"
    M = "M"
    U = "U"


class RuleOutcomeValue(StrEnum):
    PASS = "PASS"
    REJECT = "REJECT"
    DENY = "DENY"
    PEND = "PEND"


class LineDecision(StrEnum):
    APPROVE = "APPROVE"
    PEND = "PEND"
    DENY = "DENY"


class CriterionStatus(StrEnum):
    """How one retrieved coverage criterion applies to a line (DECISIONS.md 2026-09-22)."""

    MET = "MET"  # the notes show it is satisfied
    NOT_MET = "NOT_MET"  # the notes show it is not satisfied
    NOT_DOCUMENTED = "NOT_DOCUMENTED"  # it applies, but the notes say nothing about it
    NOT_APPLICABLE = "NOT_APPLICABLE"  # another policy's criterion, or a situation not in the claim


class Complexity(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class ClaimDecision(StrEnum):
    APPROVE = "APPROVE"
    PEND = "PEND"
    DENY = "DENY"
    PARTIAL = "PARTIAL"


class ClaimStatus(StrEnum):
    RECEIVED = "RECEIVED"
    REJECTED = "REJECTED"
    DENIED_BY_RULE = "DENIED_BY_RULE"
    PENDED_BY_RULE = "PENDED_BY_RULE"
    AWAITING_REVIEW = "AWAITING_REVIEW"
    FINAL_APPROVED = "FINAL_APPROVED"
    FINAL_PARTIAL = "FINAL_PARTIAL"
    FINAL_DENIED = "FINAL_DENIED"
    FINAL_PENDED = "FINAL_PENDED"


class ReviewTier(StrEnum):
    QUICK = "QUICK"
    STANDARD = "STANDARD"
    FULL = "FULL"


class ReviewActionType(StrEnum):
    ACCEPT = "ACCEPT"
    OVERRIDE = "OVERRIDE"


class Network(StrEnum):
    IN_NETWORK = "IN_NETWORK"
    OUT_OF_NETWORK = "OUT_OF_NETWORK"


class CostShareRule(StrEnum):
    COPAY = "COPAY"
    DEDUCTIBLE_COINSURANCE = "DEDUCTIBLE_COINSURANCE"


# --- Field types ---------------------------------------------------------------------------------


def npi_is_valid(npi: str) -> bool:
    """NPI check digit: Luhn over the 10 digits prefixed with 80840 (the US health card prefix)."""
    if not re.fullmatch(r"[0-9]{10}", npi):
        return False
    total = 0
    for position, char in enumerate(reversed("80840" + npi)):
        digit = int(char)
        if position % 2 == 1:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0


def _check_npi(value: str) -> str:
    if not npi_is_valid(value):
        raise ValueError("NPI must be 10 digits with a valid check digit")
    return value


def _normalize_icd10(value: object) -> object:
    return value.replace(".", "").strip().upper() if isinstance(value, str) else value


Npi = Annotated[str, AfterValidator(_check_npi)]
Tin = Annotated[str, StringConstraints(pattern=r"^[0-9]{9}$")]
Cents = Annotated[int, Field(ge=0, strict=True)]
Icd10Code = Annotated[
    str,
    BeforeValidator(_normalize_icd10),
    StringConstraints(pattern=r"^[A-TV-Z][0-9][0-9AB][0-9A-Z]{0,4}$"),
]
ProcedureCode = Annotated[str, StringConstraints(pattern=r"^([0-9]{4}[0-9A-Z]|[A-Z][0-9]{4})$")]
Modifier = Annotated[str, StringConstraints(pattern=r"^[0-9A-Z]{2}$")]
PlaceOfService = Annotated[str, StringConstraints(pattern=r"^[0-9]{2}$")]
DiagnosisPointer = Literal["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L"]
CriterionId = Annotated[str, StringConstraints(pattern=r"^POL-[A-Z]+-[0-9]{3}\.c[0-9]+$")]
BenefitCategory = Annotated[str, StringConstraints(pattern=r"^[A-Z][A-Z_]*$", max_length=48)]
NonBlank = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


# --- Intake --------------------------------------------------------------------------------------


class Address(Contract):
    line1: NonBlank
    city: NonBlank
    state: Annotated[str, StringConstraints(pattern=r"^[A-Z]{2}$")]
    zip_code: Annotated[str, StringConstraints(pattern=r"^[0-9]{5}(-[0-9]{4})?$")]


class Patient(Contract):
    first_name: NonBlank
    last_name: NonBlank
    date_of_birth: date
    sex: Sex
    address: Address


class ServiceLine(Contract):
    """One CMS-1500 service line (Box 24)."""

    line_no: Annotated[int, Field(ge=1)]
    date_of_service: date
    place_of_service: PlaceOfService
    procedure_code: ProcedureCode
    modifiers: Annotated[list[Modifier], Field(max_length=4)] = []
    diagnosis_pointers: Annotated[list[DiagnosisPointer], Field(min_length=1, max_length=4)]
    units: Annotated[int, Field(ge=1, strict=True)]
    charge_cents: Cents
    rendering_npi: Npi


class PrimaryPayment(Contract):
    line_no: Annotated[int, Field(ge=1)]
    paid_cents: Cents


class OtherCoverage(Contract):
    """Another plan paid first (coordination of benefits, Boxes 9 and 11d)."""

    payer_name: NonBlank
    primary_paid: list[PrimaryPayment]


class IntakeClaim(Contract):
    """A CMS-1500 professional claim, original claims only (frequency code 1)."""

    claim_id: NonBlank
    member_id: NonBlank
    patient: Patient
    subscriber_is_patient: bool
    billing_npi: Npi
    billing_tin: Tin
    referring_npi: Npi | None = None
    prior_auth_number: NonBlank | None = None
    diagnoses: Annotated[list[Icd10Code], Field(min_length=1, max_length=12)]
    service_lines: Annotated[list[ServiceLine], Field(min_length=1, max_length=50)]
    clinical_notes: str = ""
    received_date: date
    frequency_code: Literal["1"] = "1"
    other_coverage: OtherCoverage | None = None

    @model_validator(mode="after")
    def _check_references(self) -> "IntakeClaim":
        numbers = [line.line_no for line in self.service_lines]
        if numbers != list(range(1, len(numbers) + 1)):
            raise ValueError("service line line_no values must run 1, 2, 3, ... in order")
        for line in self.service_lines:
            for pointer in line.diagnosis_pointers:
                if ord(pointer) - ord("A") >= len(self.diagnoses):
                    raise ValueError(
                        f"line {line.line_no}: diagnosis pointer {pointer} has no diagnosis"
                    )
        if self.other_coverage:
            for payment in self.other_coverage.primary_paid:
                if payment.line_no not in numbers:
                    raise ValueError(f"other coverage refers to unknown line_no {payment.line_no}")
        return self


class IntakeResult(Contract):
    claim: IntakeClaim
    field_confidences: dict[str, Annotated[float, Field(ge=0.0, le=1.0)]]
    source_format: SourceFormat


# --- Rules ---------------------------------------------------------------------------------------


class RuleResult(Contract):
    rule_id: Annotated[str, StringConstraints(pattern=r"^(R[0-9]{2}|DUP)$")]
    passed: bool
    outcome: RuleOutcomeValue
    reason_code: str | None = None
    detail: str
    fields_used: list[str]
    line_no: int | None = None


class LineRuleOutcome(Contract):
    """Result of the line-level rules (R11–R13) for one line; DENY lines skip the model."""

    line_no: Annotated[int, Field(ge=1)]
    outcome: Literal["PASS", "DENY"]
    reason_codes: list[str] = []
    flags: list[str] = []


class RulesOutcome(Contract):
    claim_outcome: RuleOutcomeValue
    rule_results: list[RuleResult]
    line_outcomes: list[LineRuleOutcome]
    flags: list[str] = []


# --- Context -------------------------------------------------------------------------------------


class BenefitFact(Contract):
    benefit_category: BenefitCategory
    covered: bool
    auth_required: bool
    visit_limit: int | None
    visits_used: int
    cost_share_rule: CostShareRule


class RetrievedCriterion(Contract):
    criterion_id: CriterionId
    policy_id: str
    policy_title: str
    text: str
    source: str
    effective_date: date
    # Policy set v2 only (D-POL-5, approved H11 change): the criterion's type and indication group
    # (D-POL-3). None for v1 criteria, and then left out when dumped, so v1 records and datasets
    # serialize exactly as before.
    criterion_type: Literal["requirement", "exclusion", "conditional"] | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    group: Literal["indication"] | None = Field(default=None, exclude_if=lambda v: v is None)


class LineContext(Contract):
    line_no: Annotated[int, Field(ge=1)]
    procedure_code: ProcedureCode
    candidate_benefits: list[BenefitFact]
    criteria: list[RetrievedCriterion]
    rule_flags: list[str] = []


class ContextPackage(Contract):
    """What the model sees besides the claim (§8.4): plan facts from the database and coverage
    criteria from retrieval, each with its ID and source. Contains no money amounts."""

    claim_id: str
    plan_id: str
    plan_type: str
    network: Network
    excluded_codes: list[str]
    lines: list[LineContext]


# --- Model output --------------------------------------------------------------------------------


class CriterionResult(Contract):
    """MET and NOT_MET quote the notes; NOT_DOCUMENTED and NOT_APPLICABLE use fixed evidence."""

    criterion_id: CriterionId
    status: CriterionStatus
    evidence: str


class SLMLine(Contract):
    line_no: Annotated[int, Field(ge=1)]
    decision: LineDecision
    benefit_category: BenefitCategory
    criteria: list[CriterionResult]
    reasons: list[str]
    missing_information: list[str]


class SLMOutput(Contract):
    """The model's recommendation. It never contains amounts (H1)."""

    lines: list[SLMLine]
    complexity: Complexity


# --- Amounts -------------------------------------------------------------------------------------


class LineAmounts(Contract):
    line_no: Annotated[int, Field(ge=1)]
    billed_cents: Cents
    allowed_cents: Cents
    contractual_adjustment_cents: Cents
    deductible_cents: Cents
    copay_cents: Cents
    coinsurance_cents: Cents
    cob_primary_paid_cents: Cents
    plan_pays_cents: Cents
    member_pays_cents: Cents
    balance_bill_exposure_cents: Cents


class AmountTotals(Contract):
    billed_cents: Cents
    allowed_cents: Cents
    contractual_adjustment_cents: Cents
    deductible_cents: Cents
    copay_cents: Cents
    coinsurance_cents: Cents
    cob_primary_paid_cents: Cents
    plan_pays_cents: Cents
    member_pays_cents: Cents
    balance_bill_exposure_cents: Cents


class CostBreakdown(Contract):
    lines: list[LineAmounts]
    totals: AmountTotals


# --- Review and decision record ------------------------------------------------------------------


class LineOverride(Contract):
    line_no: Annotated[int, Field(ge=1)]
    decision: LineDecision
    reason: NonBlank
    # D-REV-4 (approved change, 2026-10-08): the benefit category for an APPROVE override, one of
    # the line's candidate categories; checked by app/review/actions.py.
    benefit_category: BenefitCategory | None = None
    # D-REV-9 (approved change, 2026-10-17): the internal reason code of a DENY or PEND override,
    # one of the allowed override reasons; checked by app/review/actions.py.
    reason_code: NonBlank | None = None


class ReviewAction(Contract):
    claim_id: str
    reviewer_id: NonBlank
    action: ReviewActionType
    line_overrides: list[LineOverride] = []
    reason: str | None = None  # overall comment; each override carries its own required reason
    timestamp: datetime

    @model_validator(mode="after")
    def _overrides_match_action(self) -> "ReviewAction":
        if self.action is ReviewActionType.ACCEPT and self.line_overrides:
            raise ValueError("ACCEPT cannot include line overrides")
        if self.action is ReviewActionType.OVERRIDE and not self.line_overrides:
            raise ValueError("OVERRIDE needs at least one line override with a reason")
        return self


class FinalLineDecision(Contract):
    """The decision for one line after rules, model and review; `source` says who decided."""

    line_no: Annotated[int, Field(ge=1)]
    decision: LineDecision
    benefit_category: BenefitCategory | None
    source: Literal["RULE", "MODEL", "REVIEWER", "VALIDATION"]
    reason_codes: list[str]


class Versions(Contract):
    rules_version: str
    model_name: str | None = None
    prompt_version: str | None = None
    policy_versions: dict[str, str] = {}


class Timestamps(Contract):
    received: date
    processed: datetime | None = None
    finalized: datetime | None = None


class DecisionRecord(Contract):
    claim_id: str
    status: ClaimStatus
    rules_outcome: RulesOutcome
    context_refs: ContextPackage | None = None
    slm_output: SLMOutput | None = None
    output_errors: list[str] = []
    line_decisions: list[FinalLineDecision] = []
    claim_decision: ClaimDecision | None = None
    amounts: CostBreakdown | None = None
    review_tier: ReviewTier | None = None
    review: ReviewAction | None = None
    versions: Versions
    timestamps: Timestamps
