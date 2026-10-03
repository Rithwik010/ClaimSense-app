"""Build the rules engine's reference (`app.rules.reference.RulesReference`) from the curated
files, the public files in `data/raw/` and reference records (members, providers, network rows,
authorizations, claims on file) given as dicts in the shape of `data/generated/reference/*.jsonl`.

Used by the golden and parity tests (P2.3a). The pipeline still runs the R05-only path until P2.1
loads NCCI, MUE, place of service and the full code table into the database.

NCCI edits and MUE limits are read for the in-scope procedure codes only, as the generator's rule
mirror reads them (training/generate/codebook.py).
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from functools import cache
from typing import Any

from app.db import raw
from app.db.curated import CuratedData
from app.rules.reference import (
    AuthorizationRef,
    ExistingClaimLine,
    MemberRef,
    NcciEdit,
    PlanRef,
    ProviderRef,
    RulesReference,
)


@dataclass(frozen=True)
class CodeTables:
    icd10_codes: Mapping[int, frozenset[str]]
    procedure_codes: frozenset[str]
    place_of_service_codes: frozenset[str]
    ncci: Mapping[tuple[str, str], tuple[NcciEdit, ...]]
    mue: Mapping[str, int]


@cache
def load_code_tables(scope: frozenset[str]) -> CodeTables:
    """The code tables from `data/raw/` (slow: the NCCI table has 2.6 million rows)."""
    ncci: dict[tuple[str, str], list[NcciEdit]] = {}
    for pair in raw.read_ncci_pairs(set(scope)):
        ncci.setdefault((pair.column1, pair.column2), []).append(
            NcciEdit(
                column1=pair.column1,
                column2=pair.column2,
                effective_date=pair.effective_date,
                deletion_date=pair.deletion_date,
                modifier_indicator=pair.modifier_indicator,
            )
        )
    return CodeTables(
        icd10_codes={raw.ICD10_FISCAL_YEAR: frozenset(raw.read_icd10_codes())},
        procedure_codes=raw.read_procedure_code_table(),
        place_of_service_codes=frozenset(raw.read_place_of_service_codes()),
        ncci={key: tuple(edits) for key, edits in ncci.items()},
        mue={code: entry.max_units for code, entry in raw.read_mue(set(scope)).items()},
    )


def _day(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


def plan_refs(curated: CuratedData) -> dict[str, PlanRef]:
    return {
        plan_id: PlanRef(
            plan_id=plan_id,
            filing_window_inn_days=plan.filing_window_inn_days,
            filing_window_oon_days=plan.filing_window_oon_days,
            oon_covered=plan.oon_covered,
            referral_provider_types=plan.referral_required_provider_types,
            auth_required_codes=frozenset(
                code for code in curated.scope if curated.auth_required(plan_id, code)
            ),
            excluded_codes=curated.excluded_codes(plan_id),
        )
        for plan_id, plan in curated.plans.items()
    }


def build_reference(
    curated: CuratedData,
    codes: CodeTables,
    members: Iterable[Mapping[str, Any]],
    providers: Iterable[Mapping[str, Any]],
    provider_networks: Iterable[Mapping[str, Any]],
    authorizations: Iterable[Mapping[str, Any]] = (),
    existing_claims: Iterable[Mapping[str, Any]] = (),
) -> RulesReference:
    """`existing_claims` holds one dict per claim line on file: claim_id, member_id, billing_npi,
    date_of_service, procedure_code, status."""
    return RulesReference(
        members={
            m["member_id"]: MemberRef(
                m["member_id"],
                m["plan_id"],
                date.fromisoformat(m["coverage_start"]),
                _day(m["coverage_end"]),
            )
            for m in members
        },
        providers={
            p["npi"]: ProviderRef(p["npi"], p["provider_type"], p["enrollment_status"])
            for p in providers
        },
        networks={(n["npi"], n["plan_id"]): n["in_network"] for n in provider_networks},
        plans=plan_refs(curated),
        authorizations=tuple(
            AuthorizationRef(
                auth_number=a["auth_number"],
                member_id=a["member_id"],
                provider_npi=a["provider_npi"],
                procedure_code=a["procedure_code"],
                start_date=date.fromisoformat(a["start_date"]),
                end_date=date.fromisoformat(a["end_date"]),
            )
            for a in authorizations
        ),
        existing_claims=tuple(
            ExistingClaimLine(
                claim_id=c["claim_id"],
                member_id=c["member_id"],
                billing_npi=c["billing_npi"],
                date_of_service=date.fromisoformat(c["date_of_service"]),
                procedure_code=c["procedure_code"],
                status=c["status"],
            )
            for c in existing_claims
        ),
        icd10_codes=codes.icd10_codes,
        procedure_codes=codes.procedure_codes,
        place_of_service_codes=codes.place_of_service_codes,
        ncci=codes.ncci,
        mue=codes.mue,
        bypass_modifiers=curated.bypass_modifiers,
    )
