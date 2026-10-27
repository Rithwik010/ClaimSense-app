"""Read-only queries for reference data used while processing a claim."""

import hashlib
from collections import defaultdict
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Accumulator,
    Benefit,
    FeeScheduleEntry,
    Icd10Code,
    Member,
    Plan,
    PlanExclusion,
    ProcedureCode,
    Provider,
    ProviderNetwork,
    ReferenceSource,
    VisitUsage,
)


def benefit_year_start(day: date) -> date:
    """Deductibles and out-of-pocket totals reset every 1 January (D7)."""
    return date(day.year, 1, 1)


def icd10_fiscal_year(day: date) -> int:
    """ICD-10-CM fiscal years start on 1 October (FY2027 = 2026-10-01 to 2027-09-30)."""
    return day.year + 1 if day.month >= 10 else day.year


def get_member(session: Session, member_id: str) -> Member | None:
    return session.get(Member, member_id)


def get_provider(session: Session, npi: str) -> Provider | None:
    return session.get(Provider, npi)


def get_plan(session: Session, plan_id: str) -> Plan:
    plan = session.get(Plan, plan_id)
    if plan is None:
        raise LookupError(f"plan {plan_id} is not loaded")
    return plan


def is_in_network(session: Session, npi: str, plan_id: str) -> bool:
    """Golden assumption A-R1: no network row means out of network."""
    row = session.get(ProviderNetwork, (npi, plan_id))
    return bool(row and row.in_network)


def get_benefits(session: Session, plan_id: str) -> dict[str, Benefit]:
    rows = session.scalars(select(Benefit).where(Benefit.plan_id == plan_id))
    return {row.benefit_category: row for row in rows}


def get_excluded_codes(session: Session, plan_id: str) -> list[str]:
    rows = session.scalars(
        select(PlanExclusion.procedure_code).where(PlanExclusion.plan_id == plan_id)
    )
    return sorted(rows)


def get_visits_used(session: Session, member_id: str, period_start: date) -> dict[str, int]:
    rows = session.scalars(
        select(VisitUsage).where(
            VisitUsage.member_id == member_id, VisitUsage.period_start == period_start
        )
    )
    return {row.benefit_category: row.visits_used for row in rows}


def get_fee(session: Session, procedure_code: str, day: date) -> FeeScheduleEntry | None:
    """The fee schedule row (no modifier) in effect on the date of service."""
    return session.scalars(
        select(FeeScheduleEntry)
        .where(
            FeeScheduleEntry.procedure_code == procedure_code,
            FeeScheduleEntry.modifier == "",
            FeeScheduleEntry.effective_date <= day,
        )
        .order_by(FeeScheduleEntry.effective_date.desc())
        .limit(1)
    ).first()


def get_accumulator(
    session: Session, member_id: str, period_start: date, network: str
) -> Accumulator | None:
    return session.get(Accumulator, (member_id, period_start, network))


def icd10_descriptions(session: Session, codes: list[str], fiscal_year: int) -> dict[str, str]:
    rows = session.execute(
        select(Icd10Code.code, Icd10Code.description).where(
            Icd10Code.code.in_(codes), Icd10Code.fiscal_year == fiscal_year
        )
    )
    return {code: description for code, description in rows}


def icd10_longest_descriptions(session: Session, codes: list[str]) -> dict[str, str]:
    """Each code's longest description over the fiscal years loaded (the largest prompt a claim
    can get, D-DOC-3: its date's year may not be loaded yet when it is filed)."""
    longest: dict[str, str] = {}
    rows = session.execute(
        select(Icd10Code.code, Icd10Code.description).where(Icd10Code.code.in_(codes))
    )
    for code, description in rows:
        if len(description) > len(longest.get(code, "")):
            longest[code] = description
    return longest


def procedure_descriptions(session: Session, codes: list[str]) -> dict[str, str]:
    rows = session.execute(
        select(ProcedureCode.code, ProcedureCode.description).where(ProcedureCode.code.in_(codes))
    )
    return {code: description for code, description in rows if description}


def reference_versions(session: Session) -> dict[str, str]:
    """Per rule table, twelve hex characters naming the source files it was loaded from (their
    SHA-256 in `reference_sources`, D-DATA-1), recorded with every rules run (D-OBS-1): ICD-10-CM,
    the procedure code table, NCCI, MUE, the billing articles and place of service."""
    rows = session.execute(
        select(
            ReferenceSource.table_name, ReferenceSource.source_path, ReferenceSource.sha256
        ).order_by(ReferenceSource.table_name, ReferenceSource.source_path)
    ).all()
    sources: defaultdict[str, list[str]] = defaultdict(list)
    for table, path, sha in rows:
        sources[table].append(f"{path} {sha}")
    return {
        table: hashlib.sha256("\n".join(lines).encode()).hexdigest()[:12]
        for table, lines in sources.items()
    }
