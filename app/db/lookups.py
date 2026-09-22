"""Read-only queries for reference data used while processing a claim."""

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


def procedure_descriptions(session: Session, codes: list[str]) -> dict[str, str]:
    rows = session.execute(
        select(ProcedureCode.code, ProcedureCode.description).where(ProcedureCode.code.in_(codes))
    )
    return {code: description for code, description in rows if description}
