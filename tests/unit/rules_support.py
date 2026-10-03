"""A small synthetic reference for the rules unit tests, which also run in CI (no data/raw/)."""

from dataclasses import replace
from datetime import date
from typing import Any

from app.rules.reference import MemberRef, NcciEdit, PlanRef, ProviderRef, RulesReference
from tests.unit.test_contracts import claim_data, line

__all__ = ["BYPASS", "claim_data", "line", "ncci", "reference"]

PCP = "1234567893"  # billing and rendering NPI of claim_data()
SPECIALIST = "1245319599"
BYPASS = frozenset({"XE", "XP", "XS", "XU"})

PLAN = PlanRef(
    plan_id="PLN-A",
    filing_window_inn_days=90,
    filing_window_oon_days=180,
    oon_covered=True,
    referral_provider_types=frozenset({"PAIN_MEDICINE"}),
    auth_required_codes=frozenset({"62323"}),
    excluded_codes=frozenset({"97140"}),
)


def ncci(column1: str, column2: str, indicator: str, deleted: date | None = None) -> NcciEdit:
    return NcciEdit(column1, column2, date(2020, 1, 1), deleted, indicator)


def reference(**overrides: Any) -> RulesReference:
    base = RulesReference(
        members={"MBR-000123": MemberRef("MBR-000123", "PLN-A", date(2026, 1, 1), None)},
        providers={
            PCP: ProviderRef(PCP, "PRIMARY_CARE", "ENROLLED"),
            SPECIALIST: ProviderRef(SPECIALIST, "PAIN_MEDICINE", "ENROLLED"),
        },
        networks={(PCP, "PLN-A"): True, (SPECIALIST, "PLN-A"): True},
        plans={"PLN-A": PLAN},
        authorizations=(),
        existing_claims=(),
        icd10_codes={2027: frozenset({"M5416", "M5417"})},
        procedure_codes=frozenset({"99213", "99214", "62323", "97110", "97140", "11042", "97597"}),
        place_of_service_codes=frozenset({"11", "22"}),
        ncci={},
        mue={"97110": 6},
        bypass_modifiers=BYPASS,
    )
    return replace(base, **overrides)
