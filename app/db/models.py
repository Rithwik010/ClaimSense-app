"""Database tables (INSTRUCTIONS.md §5, §8.3, §8.6, §8.9, §9.2; DECISIONS.md 2026-09-21).

Money is integer cents (BIGINT) and percentages are integer basis points (H2). Status-like columns
are text limited by CHECK constraints rather than database enum types, so values can change with a
plain migration. Claims and decision records are stored as JSON documents that follow the frozen
contracts in `app/domain/contracts.py`.
"""

from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

PLAN_TYPES = ("PPO", "HMO", "EPO")
COST_SHARE_RULES = ("COPAY", "DEDUCTIBLE_COINSURANCE")
NETWORKS = ("IN_NETWORK", "OUT_OF_NETWORK")
ENROLLMENT_STATUSES = ("ENROLLED", "PENDING")
SEXES = ("F", "M", "U")
CODE_SYSTEMS = ("CPT", "HCPCS")
REASON_OUTCOMES = ("REJECT", "DENY", "PEND")
SOURCE_FORMATS = ("JSON", "DIGITAL_PDF", "SCANNED")
CLAIM_STATUSES = (
    "RECEIVED",
    "REJECTED",
    "DENIED_BY_RULE",
    "PENDED_BY_RULE",
    "AWAITING_REVIEW",
    "FINAL_APPROVED",
    "FINAL_PARTIAL",
    "FINAL_DENIED",
    "FINAL_PENDED",
)
AUDIT_EVENT_TYPES = (
    "INTAKE_COMPLETED",
    "RULES_EVALUATED",
    "CONTEXT_ASSEMBLED",
    "SLM_RECOMMENDED",
    "OUTPUT_INVALID",
    "CALCULATED",
    "CALCULATION_FAILED",
    "EXPLANATION_BUILT",
    "REVIEW_OPENED",
    "REVIEW_ACCEPTED",
    "REVIEW_OVERRIDDEN",
    "FINALIZED",
    "AUTO_OUTCOME",
)


def one_of(column: str, values: tuple[str, ...]) -> CheckConstraint:
    allowed = ", ".join(f"'{value}'" for value in values)
    return CheckConstraint(f"{column} IN ({allowed})", name=f"{column}_allowed")


def non_negative(column: str) -> CheckConstraint:
    return CheckConstraint(f"{column} >= 0", name=f"{column}_non_negative")


# --- Plans -----------------------------------------------------------------------------------


class Plan(Base):
    __tablename__ = "plans"
    __table_args__ = (
        one_of("plan_type", PLAN_TYPES),
        non_negative("inn_deductible_cents"),
        non_negative("inn_oop_max_cents"),
        CheckConstraint("inn_coinsurance_bps BETWEEN 0 AND 10000", name="inn_coinsurance_range"),
        CheckConstraint(
            "oon_covered = (oon_deductible_cents IS NOT NULL "
            "AND oon_coinsurance_bps IS NOT NULL AND oon_oop_max_cents IS NOT NULL)",
            name="oon_terms_match_coverage",
        ),
        CheckConstraint(
            "oon_coinsurance_bps IS NULL OR oon_coinsurance_bps BETWEEN 0 AND 10000",
            name="oon_coinsurance_range",
        ),
        CheckConstraint("filing_window_inn_days > 0", name="filing_window_inn_positive"),
        CheckConstraint("filing_window_oon_days > 0", name="filing_window_oon_positive"),
    )

    plan_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    plan_type: Mapped[str] = mapped_column(String(8))
    effective_date: Mapped[date] = mapped_column(Date)
    filing_window_inn_days: Mapped[int] = mapped_column(Integer)
    filing_window_oon_days: Mapped[int] = mapped_column(Integer)
    oon_covered: Mapped[bool] = mapped_column(Boolean)
    inn_deductible_cents: Mapped[int] = mapped_column(BigInteger)
    inn_coinsurance_bps: Mapped[int] = mapped_column(Integer)
    inn_oop_max_cents: Mapped[int] = mapped_column(BigInteger)
    oon_deductible_cents: Mapped[int | None] = mapped_column(BigInteger)
    oon_coinsurance_bps: Mapped[int | None] = mapped_column(Integer)
    oon_oop_max_cents: Mapped[int | None] = mapped_column(BigInteger)


class Benefit(Base):
    __tablename__ = "benefits"
    __table_args__ = (
        one_of("cost_share_rule", COST_SHARE_RULES),
        CheckConstraint(
            "(cost_share_rule = 'COPAY') = (copay_cents IS NOT NULL)", name="copay_matches_rule"
        ),
        CheckConstraint("copay_cents IS NULL OR copay_cents >= 0", name="copay_non_negative"),
        CheckConstraint("visit_limit IS NULL OR visit_limit > 0", name="visit_limit_positive"),
    )

    plan_id: Mapped[str] = mapped_column(ForeignKey("plans.plan_id"), primary_key=True)
    benefit_category: Mapped[str] = mapped_column(String(48), primary_key=True)
    covered: Mapped[bool] = mapped_column(Boolean)
    auth_required: Mapped[bool] = mapped_column(Boolean)
    visit_limit: Mapped[int | None] = mapped_column(Integer)
    cost_share_rule: Mapped[str] = mapped_column(String(32))
    copay_cents: Mapped[int | None] = mapped_column(BigInteger)


class PlanExclusion(Base):
    __tablename__ = "plan_exclusions"

    plan_id: Mapped[str] = mapped_column(ForeignKey("plans.plan_id"), primary_key=True)
    procedure_code: Mapped[str] = mapped_column(String(5), primary_key=True)
    reason: Mapped[str] = mapped_column(Text)


class PlanReferralRule(Base):
    __tablename__ = "plan_referral_rules"

    plan_id: Mapped[str] = mapped_column(ForeignKey("plans.plan_id"), primary_key=True)
    provider_type: Mapped[str] = mapped_column(String(48), primary_key=True)


class FeeScheduleEntry(Base):
    __tablename__ = "fee_schedule"
    __table_args__ = (non_negative("inn_allowed_cents"), non_negative("oon_allowed_cents"))

    procedure_code: Mapped[str] = mapped_column(String(5), primary_key=True)
    modifier: Mapped[str] = mapped_column(String(2), primary_key=True, default="")
    effective_date: Mapped[date] = mapped_column(Date, primary_key=True)
    inn_allowed_cents: Mapped[int] = mapped_column(BigInteger)
    oon_allowed_cents: Mapped[int] = mapped_column(BigInteger)
    source: Mapped[str] = mapped_column(Text)


# --- Members and providers -------------------------------------------------------------------


class Member(Base):
    __tablename__ = "members"
    __table_args__ = (
        one_of("sex", SEXES),
        CheckConstraint(
            "coverage_end IS NULL OR coverage_end >= coverage_start", name="coverage_dates_ordered"
        ),
    )

    member_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    plan_id: Mapped[str] = mapped_column(ForeignKey("plans.plan_id"), index=True)
    first_name: Mapped[str] = mapped_column(Text)
    last_name: Mapped[str] = mapped_column(Text)
    date_of_birth: Mapped[date] = mapped_column(Date)
    sex: Mapped[str] = mapped_column(String(1))
    address_line: Mapped[str] = mapped_column(Text)
    city: Mapped[str] = mapped_column(Text)
    state: Mapped[str] = mapped_column(String(2))
    zip_code: Mapped[str] = mapped_column(String(10))
    coverage_start: Mapped[date] = mapped_column(Date)
    coverage_end: Mapped[date | None] = mapped_column(Date)


class Provider(Base):
    __tablename__ = "providers"
    __table_args__ = (
        one_of("enrollment_status", ENROLLMENT_STATUSES),
        CheckConstraint("npi ~ '^[0-9]{10}$'", name="npi_ten_digits"),
        CheckConstraint("tin ~ '^[0-9]{9}$'", name="tin_nine_digits"),
    )

    npi: Mapped[str] = mapped_column(String(10), primary_key=True)
    tin: Mapped[str] = mapped_column(String(9))
    name: Mapped[str] = mapped_column(Text)
    provider_type: Mapped[str] = mapped_column(String(48))
    enrollment_status: Mapped[str] = mapped_column(String(16))


class ProviderNetwork(Base):
    __tablename__ = "provider_networks"

    npi: Mapped[str] = mapped_column(ForeignKey("providers.npi"), primary_key=True)
    plan_id: Mapped[str] = mapped_column(ForeignKey("plans.plan_id"), primary_key=True)
    in_network: Mapped[bool] = mapped_column(Boolean)


class Authorization(Base):
    __tablename__ = "authorizations"
    __table_args__ = (
        CheckConstraint("end_date >= start_date", name="dates_ordered"),
        CheckConstraint("units_approved IS NULL OR units_approved > 0", name="units_positive"),
    )

    auth_number: Mapped[str] = mapped_column(String(32), primary_key=True)
    member_id: Mapped[str] = mapped_column(ForeignKey("members.member_id"), index=True)
    provider_npi: Mapped[str] = mapped_column(ForeignKey("providers.npi"))
    procedure_code: Mapped[str] = mapped_column(String(5))
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    units_approved: Mapped[int | None] = mapped_column(Integer)


class OtherCoverage(Base):
    __tablename__ = "other_coverage"
    __table_args__ = (
        CheckConstraint(
            "coverage_end IS NULL OR coverage_end >= coverage_start", name="coverage_dates_ordered"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    member_id: Mapped[str] = mapped_column(ForeignKey("members.member_id"), index=True)
    payer_name: Mapped[str] = mapped_column(Text)
    policy_number: Mapped[str] = mapped_column(String(32))
    is_primary: Mapped[bool] = mapped_column(Boolean)
    coverage_start: Mapped[date] = mapped_column(Date)
    coverage_end: Mapped[date | None] = mapped_column(Date)


class Accumulator(Base):
    """Deductible and out-of-pocket amounts used in a benefit period, per network."""

    __tablename__ = "accumulators"
    __table_args__ = (
        one_of("network", NETWORKS),
        non_negative("deductible_met_cents"),
        non_negative("oop_met_cents"),
        CheckConstraint("period_end >= period_start", name="period_ordered"),
    )

    member_id: Mapped[str] = mapped_column(ForeignKey("members.member_id"), primary_key=True)
    period_start: Mapped[date] = mapped_column(Date, primary_key=True)
    network: Mapped[str] = mapped_column(String(16), primary_key=True)
    period_end: Mapped[date] = mapped_column(Date)
    deductible_met_cents: Mapped[int] = mapped_column(BigInteger, default=0)
    oop_met_cents: Mapped[int] = mapped_column(BigInteger, default=0)


class VisitUsage(Base):
    """Visits used against a benefit category's visit limit in a benefit period."""

    __tablename__ = "visit_usage"
    __table_args__ = (non_negative("visits_used"),)

    member_id: Mapped[str] = mapped_column(ForeignKey("members.member_id"), primary_key=True)
    period_start: Mapped[date] = mapped_column(Date, primary_key=True)
    benefit_category: Mapped[str] = mapped_column(String(48), primary_key=True)
    visits_used: Mapped[int] = mapped_column(Integer, default=0)


# --- Code tables -----------------------------------------------------------------------------


class Icd10Code(Base):
    __tablename__ = "icd10_codes"

    code: Mapped[str] = mapped_column(String(7), primary_key=True)
    fiscal_year: Mapped[int] = mapped_column(Integer, primary_key=True)
    description: Mapped[str] = mapped_column(Text)


class ProcedureCode(Base):
    """Procedure codes. `description` is team-written for in-scope codes (never AMA text, H10)."""

    __tablename__ = "procedure_codes"
    __table_args__ = (one_of("code_system", CODE_SYSTEMS),)

    code: Mapped[str] = mapped_column(String(5), primary_key=True)
    code_system: Mapped[str] = mapped_column(String(8))
    description: Mapped[str | None] = mapped_column(Text)
    in_scope: Mapped[bool] = mapped_column(Boolean, default=False)
    # PFS global days (000, 010, 090, XXX, YYY, ZZZ, MMM); R11 reads them for modifiers 25 and 57
    global_days: Mapped[str | None] = mapped_column(String(3))


class PlaceOfServiceCode(Base):
    __tablename__ = "place_of_service_codes"

    code: Mapped[str] = mapped_column(String(2), primary_key=True)
    name: Mapped[str] = mapped_column(Text)


class NcciPtpEdit(Base):
    """One NCCI procedure-to-procedure edit row as published (column 2 is bundled into column 1).

    The published table repeats a (column 1, column 2, effective date) key in 261 rows (same-day
    deletions), so a row has a surrogate id. `source_order` is the row's position in the published
    files, part f1 to f4: among a pair's edits active on a date, the first in that order applies,
    as in the file-backed reference (P2.1, migration 0003)."""

    __tablename__ = "ncci_ptp_edits"
    __table_args__ = (
        CheckConstraint("modifier_indicator IN ('0', '1', '9')", name="modifier_indicator_allowed"),
        Index("ix_ncci_ptp_edits_pair", "column1_code", "column2_code"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    column1_code: Mapped[str] = mapped_column(String(5))
    column2_code: Mapped[str] = mapped_column(String(5))
    effective_date: Mapped[date] = mapped_column(Date)
    deletion_date: Mapped[date | None] = mapped_column(Date)
    modifier_indicator: Mapped[str] = mapped_column(String(1))
    source_order: Mapped[int] = mapped_column(Integer)


class MueLimit(Base):
    __tablename__ = "mue_limits"
    __table_args__ = (non_negative("max_units"),)

    procedure_code: Mapped[str] = mapped_column(String(5), primary_key=True)
    effective_date: Mapped[date] = mapped_column(Date, primary_key=True)
    max_units: Mapped[int] = mapped_column(Integer)
    adjudication_indicator: Mapped[str] = mapped_column(Text)


class ArticleIcd10Covered(Base):
    """A billing article's covered ICD-10-CM codes by group (MCD current articles), for R15
    (D-DX-1, D-RULE-4): the articles of the in-scope codes (data/curated/diagnosis_support.csv)."""

    __tablename__ = "article_icd10_covered"

    article_id: Mapped[str] = mapped_column(String(8), primary_key=True)
    covered_group: Mapped[int] = mapped_column(Integer, primary_key=True)
    icd10_code: Mapped[str] = mapped_column(String(7), primary_key=True)
    article_version: Mapped[str] = mapped_column(String(8))


class ReferenceSource(Base):
    """Where a loaded reference table came from (P2.1): each source file with its SHA-256, as
    listed in data/raw_manifest.csv (D-DATA-1) or computed for a committed fixture."""

    __tablename__ = "reference_sources"

    table_name: Mapped[str] = mapped_column(String(64), primary_key=True)
    source_path: Mapped[str] = mapped_column(Text, primary_key=True)
    sha256: Mapped[str] = mapped_column(String(64))
    row_count: Mapped[int] = mapped_column(Integer)
    loaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ReasonCode(Base):
    __tablename__ = "reason_codes"
    __table_args__ = (one_of("outcome", REASON_OUTCOMES),)

    internal_code: Mapped[str] = mapped_column(String(48), primary_key=True)
    outcome: Mapped[str] = mapped_column(String(8))
    group_code: Mapped[str] = mapped_column(String(2))
    carc: Mapped[str] = mapped_column(String(8))
    rarc: Mapped[str | None] = mapped_column(String(8))
    notes: Mapped[str | None] = mapped_column(Text)


# --- Processing ------------------------------------------------------------------------------


class Claim(Base):
    __tablename__ = "claims"
    __table_args__ = (one_of("status", CLAIM_STATUSES), one_of("source_format", SOURCE_FORMATS))

    claim_id: Mapped[str] = mapped_column(String(48), primary_key=True)
    member_id: Mapped[str] = mapped_column(String(32), index=True)  # may be unknown: rule R04
    received_date: Mapped[date] = mapped_column(Date)
    source_format: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(24))
    intake: Mapped[dict[str, Any]] = mapped_column(JSONB)
    field_confidences: Mapped[dict[str, Any]] = mapped_column(JSONB)
    # The provider account that filed the claim (D-AUTH-1): a provider user sees only the claims
    # filed under their provider ID. None for claims filed before logins existed.
    provider_id: Mapped[str | None] = mapped_column(String(10), index=True)
    filed_by: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


USER_ROLES = ("provider", "reviewer", "admin")


class User(Base):
    """A person who logs in (D-AUTH-1). The role decides what they may do; a provider user also
    has the provider ID (an NPI from the demo data) their claims are filed under."""

    __tablename__ = "users"
    __table_args__ = (
        one_of("role", USER_ROLES),
        CheckConstraint(
            "(role = 'provider') = (provider_id IS NOT NULL)", name="provider_id_for_providers"
        ),
        CheckConstraint("provider_id ~ '^[0-9]{10}$'", name="provider_id_ten_digits"),
    )

    username: Mapped[str] = mapped_column(String(64), primary_key=True)  # the review actor
    display_name: Mapped[str] = mapped_column(Text)
    password_hash: Mapped[str] = mapped_column(Text)  # Argon2 (pwdlib)
    role: Mapped[str] = mapped_column(String(16))
    provider_id: Mapped[str | None] = mapped_column(String(10))
    active: Mapped[bool] = mapped_column(Boolean, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DecisionRecordRow(Base):
    """One row per version of a claim's decision record (a reviewer override adds a version)."""

    __tablename__ = "decision_records"
    __table_args__ = (UniqueConstraint("claim_id", "version", name="uq_decision_records_version"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    claim_id: Mapped[str] = mapped_column(ForeignKey("claims.claim_id"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    record: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuditEvent(Base):
    """Append-only audit trail (§8.9). A database trigger rejects UPDATE and DELETE."""

    __tablename__ = "audit_events"
    __table_args__ = (one_of("event_type", AUDIT_EVENT_TYPES),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    claim_id: Mapped[str] = mapped_column(ForeignKey("claims.claim_id"), index=True)
    event_type: Mapped[str] = mapped_column(String(32))
    actor: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    rules_version: Mapped[str | None] = mapped_column(String(32))
    model_name: Mapped[str | None] = mapped_column(String(64))
    prompt_version: Mapped[str | None] = mapped_column(String(32))
    policy_versions: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
