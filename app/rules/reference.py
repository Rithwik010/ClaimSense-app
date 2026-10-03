"""Reference records the rules read, as plain values. The caller loads them (from the database, or
from the curated and raw files in tests), so the rules stay pure functions with no database access
of their own (§8.3)."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class MemberRef:
    member_id: str
    plan_id: str
    coverage_start: date
    coverage_end: date | None  # inclusive; None = open-ended

    def covers(self, day: date) -> bool:
        return self.coverage_start <= day and (
            self.coverage_end is None or day <= self.coverage_end
        )


@dataclass(frozen=True)
class ProviderRef:
    npi: str
    provider_type: str
    enrollment_status: str  # ENROLLED | PENDING


@dataclass(frozen=True)
class PlanRef:
    """What the rules need from a plan's configuration (data/curated/plans.yaml, benefits.csv,
    exclusions.csv). `auth_required_codes` lists the in-scope codes whose benefit category needs
    prior authorization."""

    plan_id: str
    filing_window_inn_days: int
    filing_window_oon_days: int
    oon_covered: bool
    referral_provider_types: frozenset[str]
    auth_required_codes: frozenset[str]
    excluded_codes: frozenset[str]


@dataclass(frozen=True)
class AuthorizationRef:
    auth_number: str
    member_id: str
    provider_npi: str
    procedure_code: str
    start_date: date
    end_date: date  # inclusive

    def matches(self, member_id: str, npi: str, procedure_code: str, day: date) -> bool:
        return (
            self.member_id == member_id
            and self.provider_npi == npi
            and self.procedure_code == procedure_code
            and self.start_date <= day <= self.end_date
        )


@dataclass(frozen=True)
class ExistingClaimLine:
    """One service line of a claim already on file, for the duplicate check (A-R6)."""

    claim_id: str
    member_id: str
    billing_npi: str
    date_of_service: date
    procedure_code: str
    status: str


@dataclass(frozen=True)
class NcciEdit:
    """One NCCI procedure-to-procedure edit: column 2 is bundled into column 1."""

    column1: str
    column2: str
    effective_date: date
    deletion_date: date | None  # inclusive; None = still active
    modifier_indicator: str  # 0 = no bypass allowed, 1 = bypass allowed, 9 = not applicable

    def active_on(self, day: date) -> bool:
        return self.effective_date <= day and (
            self.deletion_date is None or self.deletion_date >= day
        )


@dataclass(frozen=True)
class RulesReference:
    members: Mapping[str, MemberRef]
    providers: Mapping[str, ProviderRef]
    networks: Mapping[tuple[str, str], bool]  # (NPI, plan ID) -> in network
    plans: Mapping[str, PlanRef]
    authorizations: tuple[AuthorizationRef, ...]
    existing_claims: tuple[ExistingClaimLine, ...]
    icd10_codes: Mapping[int, frozenset[str]]  # ICD-10-CM fiscal year -> billable codes, no dots
    procedure_codes: frozenset[str]  # the code table: PFS RVU file and HCPCS file codes
    place_of_service_codes: frozenset[str]
    ncci: Mapping[tuple[str, str], tuple[NcciEdit, ...]]  # (column 1, column 2) -> edits
    mue: Mapping[str, int]  # procedure code -> maximum units per date of service
    bypass_modifiers: frozenset[str]

    def in_network(self, npi: str, plan_id: str) -> bool:
        """A-R1: no network row for the plan means out of network."""
        return self.networks.get((npi, plan_id), False)

    def ncci_indicator(self, column1: str, column2: str, day: date) -> str | None:
        """The modifier indicator of the first edit active on `day`, or None when none is."""
        for edit in self.ncci.get((column1, column2), ()):
            if edit.active_on(day):
                return edit.modifier_indicator
        return None


class MissingReference(LookupError):
    """The reference data needed to evaluate a rule is not loaded (not a claim problem)."""
