"""Load reference data into the database. Walking skeleton (P1.5); P2.1 adds the NCCI, MUE,
place-of-service and full HCPCS tables and reports row counts against the source files.

Loads, in order:
1. Curated data (committed): plans, benefits, exclusions, referral rules, reason codes, and the
   in-scope procedure codes with team-written descriptions.
2. Public code files, when `data/raw/` is present: ICD-10-CM FY2027 and the fee schedule for the
   in-scope codes (D6).
3. Generated reference data, when present: `data/generated/reference/*.jsonl` and the extra
   authorizations the claim corpus needs (`data/generated/claims/authorizations_extra.jsonl`).

Rows are upserted by primary key, so running it again is safe.

    uv run python -m app.db.seed
"""

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy import Date, func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.calculator.fee_schedule import allowed_amounts
from app.db import raw
from app.db.base import Base
from app.db.curated import CuratedData, load_curated
from app.db.models import (
    Accumulator,
    Authorization,
    Benefit,
    FeeScheduleEntry,
    Icd10Code,
    Member,
    OtherCoverage,
    Plan,
    PlanExclusion,
    PlanReferralRule,
    ProcedureCode,
    Provider,
    ProviderNetwork,
    ReasonCode,
    VisitUsage,
)
from app.db.session import get_engine

GENERATED_DIR = Path(__file__).resolve().parents[2] / "data" / "generated"
ICD10_FISCAL_YEAR = 2027  # DECISIONS.md R1
CHUNK_ROWS = 5000

# File stem -> table, in foreign-key order.
REFERENCE_TABLES: tuple[tuple[str, type[Base]], ...] = (
    ("members", Member),
    ("providers", Provider),
    ("provider_networks", ProviderNetwork),
    ("authorizations", Authorization),
    ("other_coverage", OtherCoverage),
    ("accumulators", Accumulator),
    ("visit_usage", VisitUsage),
)


def upsert(session: Session, model: type[Base], rows: list[dict[str, Any]]) -> int:
    """Insert rows, replacing any row with the same primary key. ISO date strings are parsed."""
    if not rows:
        return 0
    table = model.__table__
    keys = [column.name for column in table.primary_key.columns]
    dates = {column.name for column in table.columns if isinstance(column.type, Date)}
    rows = [
        {k: date.fromisoformat(v) if k in dates and isinstance(v, str) else v for k, v in r.items()}
        for r in rows
    ]
    statement = pg_insert(table)
    updates = {name: statement.excluded[name] for name in rows[0] if name not in keys}
    statement = (
        statement.on_conflict_do_update(index_elements=keys, set_=updates)
        if updates
        else statement.on_conflict_do_nothing(index_elements=keys)
    )
    for start in range(0, len(rows), CHUNK_ROWS):
        session.execute(statement, rows[start : start + CHUNK_ROWS])
    if model is OtherCoverage:  # explicit ids: move the sequence past them
        session.execute(
            text("SELECT setval(pg_get_serial_sequence('other_coverage', 'id'), :value)"),
            {"value": session.scalar(select(func.max(OtherCoverage.id)))},
        )
    return len(rows)


def curated_rows(curated: CuratedData) -> list[tuple[type[Base], list[dict[str, Any]]]]:
    plans = []
    for plan in curated.plans.values():
        oon = plan.out_of_network
        plans.append(
            {
                "plan_id": plan.plan_id,
                "name": plan.name,
                "plan_type": plan.plan_type,
                "effective_date": plan.effective_date,
                "filing_window_inn_days": plan.filing_window_inn_days,
                "filing_window_oon_days": plan.filing_window_oon_days,
                "oon_covered": plan.oon_covered,
                "inn_deductible_cents": plan.in_network.deductible_cents,
                "inn_coinsurance_bps": plan.in_network.coinsurance_bps,
                "inn_oop_max_cents": plan.in_network.oop_max_cents,
                "oon_deductible_cents": oon.deductible_cents if oon else None,
                "oon_coinsurance_bps": oon.coinsurance_bps if oon else None,
                "oon_oop_max_cents": oon.oop_max_cents if oon else None,
            }
        )
    return [
        (Plan, plans),
        (
            Benefit,
            [
                {
                    "plan_id": b.plan_id,
                    "benefit_category": b.benefit_category,
                    "covered": b.covered,
                    "auth_required": b.auth_required,
                    "visit_limit": b.visit_limit,
                    "cost_share_rule": b.cost_share_rule,
                    "copay_cents": b.copay_cents,
                }
                for b in curated.benefits.values()
            ],
        ),
        (
            PlanExclusion,
            [
                {"plan_id": e.plan_id, "procedure_code": e.procedure_code, "reason": e.reason}
                for e in curated.exclusions
            ],
        ),
        (
            PlanReferralRule,
            [
                {"plan_id": plan.plan_id, "provider_type": provider_type}
                for plan in curated.plans.values()
                for provider_type in sorted(plan.referral_required_provider_types)
            ],
        ),
        (
            ReasonCode,
            [
                {
                    "internal_code": r.internal_code,
                    "outcome": r.outcome,
                    "group_code": r.group_code,
                    "carc": r.carc,
                    "rarc": r.rarc,
                    "notes": r.notes,
                }
                for r in curated.reason_codes.values()
            ],
        ),
        (
            ProcedureCode,
            [
                {
                    "code": code,
                    "code_system": entry.code_system,
                    "description": curated.descriptions[code],
                    "in_scope": True,
                }
                for code, entry in curated.scope.items()
            ],
        ),
    ]


def fee_rows(curated: CuratedData) -> list[dict[str, Any]]:
    """Allowed amounts per unit for every in-scope code (D6), from the PFS file in `data/raw/`."""
    rule = curated.fee_rule
    entries = raw.read_pfs(set(curated.scope))
    missing = sorted(set(curated.scope) - set(entries))
    if missing:
        raise ValueError(f"no fee schedule entry in {rule.source_file} for {missing}")
    rows = []
    for code, entry in sorted(entries.items()):
        if entry.conversion_factor != rule.conversion_factor:
            raise ValueError(f"{code}: conversion factor {entry.conversion_factor} in the file")
        inn, oon = allowed_amounts(
            entry.nonfacility_total_rvu,
            rule.conversion_factor,
            rule.in_network_bps,
            rule.out_of_network_bps,
        )
        rows.append(
            {
                "procedure_code": code,
                "modifier": "",
                "effective_date": rule.effective_date,
                "inn_allowed_cents": inn,
                "oon_allowed_cents": oon,
                "source": f"{rule.source_file}: {rule.rvu_column} x {rule.conversion_factor}",
            }
        )
    return rows


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def reference_records(reference_dir: Path) -> dict[str, list[dict[str, Any]]]:
    records = {
        stem: read_jsonl(reference_dir / f"{stem}.jsonl")
        for stem, _ in REFERENCE_TABLES
        if (reference_dir / f"{stem}.jsonl").exists()
    }
    extra = reference_dir.parent / "claims" / "authorizations_extra.jsonl"
    if extra.exists():
        records["authorizations"] = records.get("authorizations", []) + read_jsonl(extra)
    return records


def load_reference(session: Session, records: dict[str, list[dict[str, Any]]]) -> dict[str, int]:
    """Members, providers, networks, authorizations, other coverage, accumulators, visit usage."""
    return {stem: upsert(session, model, records.get(stem, [])) for stem, model in REFERENCE_TABLES}


def seed_curated(session: Session, curated: CuratedData | None = None) -> dict[str, int]:
    curated = curated or load_curated()
    return {
        model.__tablename__: upsert(session, model, rows) for model, rows in curated_rows(curated)
    }


def seed(session: Session, reference_dir: Path | None) -> dict[str, int]:
    counts = seed_curated(session)
    if raw.raw_available():
        counts["fee_schedule"] = upsert(session, FeeScheduleEntry, fee_rows(load_curated()))
        counts["icd10_codes"] = upsert(
            session,
            Icd10Code,
            [
                {"code": code, "fiscal_year": ICD10_FISCAL_YEAR, "description": description}
                for code, description in raw.read_icd10_codes().items()
            ],
        )
    if reference_dir is not None and reference_dir.exists():
        counts |= load_reference(session, reference_records(reference_dir))
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--reference-dir", type=Path, default=GENERATED_DIR / "reference")
    parser.add_argument("--no-reference", action="store_true", help="skip generated data")
    args = parser.parse_args()
    with Session(get_engine()) as session:
        counts = seed(session, None if args.no_reference else args.reference_dir)
        session.commit()
    if not raw.raw_available():
        print("data/raw/ not found: fee schedule and ICD-10-CM codes not loaded")
    for table, count in counts.items():
        print(f"{table:24} {count:>7}")


if __name__ == "__main__":
    main()
