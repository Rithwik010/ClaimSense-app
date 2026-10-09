"""Load reference data into the database (P1.5, P2.1).

Loads, in order:
1. Curated data (committed): plans, benefits, exclusions, referral rules, reason codes, and the
   in-scope procedure codes with team-written descriptions.
2. Public code files, when `data/raw/` is present: the fee schedule for the in-scope codes (D6)
   and the rule tables (P2.1): place-of-service codes, the full procedure code table (PFS RVU26A
   and HCPCS October 2026; codes outside the scope get no description, H10), ICD-10-CM FY2027,
   and the practitioner MUE limits and NCCI PTP edits in full. Each rule table records its
   source files and their SHA-256 from data/raw_manifest.csv in `reference_sources` (D-DATA-1).
3. Generated reference data, when present: `data/generated/reference/*.jsonl` and the extra
   authorizations the claim corpus needs (`data/generated/claims/authorizations_extra.jsonl`).

Running it again is safe: rows are upserted by primary key, and the NCCI table is replaced in one
transaction (TRUNCATE, then COPY in the published order).

    uv run python -m app.db.seed
"""

import argparse
import hashlib
import json
import time
from collections.abc import Callable, Iterable, Iterator, Mapping
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy import Date, delete, func, insert, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.calculator.fee_schedule import allowed_amounts
from app.db import raw
from app.db.base import Base
from app.db.curated import CuratedData, billing_articles, load_curated
from app.db.models import (
    Accumulator,
    ArticleIcd10Covered,
    Authorization,
    Benefit,
    FeeScheduleEntry,
    Icd10Code,
    Member,
    MueLimit,
    NcciPtpEdit,
    OtherCoverage,
    PlaceOfServiceCode,
    Plan,
    PlanExclusion,
    PlanReferralRule,
    ProcedureCode,
    Provider,
    ProviderNetwork,
    ReasonCode,
    ReferenceSource,
    VisitUsage,
)
from app.db.session import get_engine

ROOT = Path(__file__).resolve().parents[2]
GENERATED_DIR = ROOT / "data" / "generated"
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


# --- Rule tables (P2.1) -------------------------------------------------------------------------

NCCI_COLUMNS = (
    "column1_code",
    "column2_code",
    "effective_date",
    "deletion_date",
    "modifier_indicator",
    "source_order",
)
RULE_TABLES = (
    PlaceOfServiceCode,
    ProcedureCode,
    Icd10Code,
    MueLimit,
    NcciPtpEdit,
    ArticleIcd10Covered,
)


@dataclass(frozen=True)
class Source:
    path: str  # relative to the repository root
    sha256: str


@dataclass(frozen=True)
class RuleTableData:
    """The rule tables' rows and their sources: from data/raw/ (`raw_rule_tables`) or, in tests
    and CI, from a committed fixture of the rows the golden cases need (D-CI-1)."""

    place_of_service: Mapping[str, str]  # code -> name
    procedure_codes: Iterable[str]
    icd10: Mapping[int, Mapping[str, str]]  # fiscal year -> code -> description
    mue: Mapping[str, tuple[int, str]]  # code -> (maximum units, adjudication indicator)
    mue_effective: date
    ncci_rows: Callable[[], Iterator[raw.NcciEditRow]]  # in the published order
    # billing article -> (version, covered group -> ICD-10-CM codes), for R15
    article_covered: Mapping[str, tuple[str, Mapping[int, Iterable[str]]]]
    global_days: Mapping[str, str]  # procedure code -> PFS global days, for R11 (D-RULE-8)
    sources: Mapping[str, tuple[Source, ...]]  # table name -> source files


def code_system(code: str) -> str:
    """Level II HCPCS codes start with a letter; CPT codes (categories I to III) with a digit."""
    return "HCPCS" if code[0].isalpha() else "CPT"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def raw_sources(paths: Iterable[Path]) -> tuple[Source, ...]:
    """The files with their SHA-256 from data/raw_manifest.csv; a file that differs from the
    manifest is not loaded (D-DATA-1)."""
    listed = raw.manifest_sha256()
    sources = []
    for path in paths:
        key = path.relative_to(raw.RAW_DIR).as_posix()
        if key not in listed:
            raise ValueError(f"{key} is not in {raw.MANIFEST_CSV.name}")
        if file_sha256(path) != listed[key]:
            raise ValueError(f"{key} differs from {raw.MANIFEST_CSV.name} (D-DATA-1)")
        sources.append(Source(path.relative_to(ROOT).as_posix(), listed[key]))
    return tuple(sources)


def raw_rule_tables() -> RuleTableData:
    mue = raw.read_mue()
    articles = raw.read_article_diagnoses(billing_articles(load_curated()))
    return RuleTableData(
        place_of_service=raw.read_place_of_service_codes(),
        procedure_codes=raw.read_procedure_code_table(),
        icd10={ICD10_FISCAL_YEAR: raw.read_icd10_codes()},
        mue={code: (entry.max_units, entry.adjudication_indicator) for code, entry in mue.items()},
        mue_effective=raw.MUE_EFFECTIVE,
        ncci_rows=raw.read_ncci_edits,
        article_covered={a: (found.version, found.covered) for a, found in articles.items()},
        global_days=raw.read_pfs_global_days(),
        sources={
            "place_of_service_codes": raw_sources([raw.POS_PDF]),
            "procedure_codes": raw_sources([raw.PFS_CSV, raw.HCPCS_TXT]),
            "icd10_codes": raw_sources([raw.ICD10_ZIP]),
            "mue_limits": raw_sources([raw.MUE_CSV]),
            "ncci_ptp_edits": raw_sources(raw.ncci_sources()),
            "article_icd10_covered": raw_sources([raw.MCD_ARTICLES_ZIP]),
        },
    )


def copy_ncci(session: Session, rows: Iterable[raw.NcciEditRow]) -> int:
    """Replace every NCCI edit with `rows`, numbered in order, in the session's transaction."""
    session.execute(text("TRUNCATE ncci_ptp_edits RESTART IDENTITY"))
    driver = session.connection().connection.driver_connection
    count = 0
    statement = f"COPY ncci_ptp_edits ({', '.join(NCCI_COLUMNS)}) FROM STDIN"
    with driver.cursor() as cursor, cursor.copy(statement) as copy:
        for count, row in enumerate(rows, start=1):
            copy.write_row((*row, count - 1))
    return count


def load_rule_tables(session: Session, data: RuleTableData) -> dict[str, int]:
    """Load the rule tables and record their provenance. Procedure codes already on file (the
    curated in-scope codes) keep their description."""
    counts = {
        "place_of_service_codes": upsert(
            session,
            PlaceOfServiceCode,
            [{"code": code, "name": name} for code, name in sorted(data.place_of_service.items())],
        )
    }
    codes = sorted(data.procedure_codes)
    insert_new = pg_insert(ProcedureCode).on_conflict_do_nothing(index_elements=["code"])
    for start in range(0, len(codes), CHUNK_ROWS):
        session.execute(
            insert_new,
            [
                {
                    "code": code,
                    "code_system": code_system(code),
                    "description": None,
                    "in_scope": False,
                }
                for code in codes[start : start + CHUNK_ROWS]
            ],
        )
    counts["procedure_codes"] = len(codes)
    known = set(codes)
    days = [
        {"code": code, "global_days": value}
        for code, value in sorted(data.global_days.items())
        if code in known
    ]
    for start in range(0, len(days), CHUNK_ROWS):
        session.execute(update(ProcedureCode), days[start : start + CHUNK_ROWS])
    counts["icd10_codes"] = upsert(
        session,
        Icd10Code,
        [
            {"code": code, "fiscal_year": year, "description": description}
            for year, entries in sorted(data.icd10.items())
            for code, description in sorted(entries.items())
        ],
    )
    counts["mue_limits"] = upsert(
        session,
        MueLimit,
        [
            {
                "procedure_code": code,
                "effective_date": data.mue_effective,
                "max_units": units,
                "adjudication_indicator": indicator,
            }
            for code, (units, indicator) in sorted(data.mue.items())
        ],
    )
    counts["ncci_ptp_edits"] = copy_ncci(session, data.ncci_rows())
    session.execute(delete(ArticleIcd10Covered))
    covered = [
        {
            "article_id": article,
            "covered_group": group,
            "icd10_code": code,
            "article_version": version,
        }
        for article, (version, groups) in sorted(data.article_covered.items())
        for group, codes in sorted(groups.items())
        for code in sorted(codes)
    ]
    for start in range(0, len(covered), CHUNK_ROWS):
        session.execute(insert(ArticleIcd10Covered), covered[start : start + CHUNK_ROWS])
    counts["article_icd10_covered"] = len(covered)
    session.execute(delete(ReferenceSource).where(ReferenceSource.table_name.in_(data.sources)))
    session.add_all(
        ReferenceSource(
            table_name=table,
            source_path=source.path,
            sha256=source.sha256,
            row_count=counts[table],
        )
        for table, sources in data.sources.items()
        for source in sources
    )
    session.flush()
    return counts


def table_sizes(session: Session) -> dict[str, int]:
    """Bytes on disk per rule table, indexes included."""
    return {
        model.__tablename__: session.scalar(
            text("SELECT pg_total_relation_size(:table)"), {"table": model.__tablename__}
        )
        for model in RULE_TABLES
    }


def seed(session: Session, reference_dir: Path | None) -> dict[str, int]:
    counts = seed_curated(session)
    if raw.raw_available():
        counts["fee_schedule"] = upsert(session, FeeScheduleEntry, fee_rows(load_curated()))
        counts |= load_rule_tables(session, raw_rule_tables())
    if reference_dir is not None and reference_dir.exists():
        counts |= load_reference(session, reference_records(reference_dir))
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--reference-dir", type=Path, default=GENERATED_DIR / "reference")
    parser.add_argument("--no-reference", action="store_true", help="skip generated data")
    args = parser.parse_args()
    started = time.perf_counter()
    with Session(get_engine()) as session:
        counts = seed(session, None if args.no_reference else args.reference_dir)
        session.commit()
        sizes = table_sizes(session)
    if not raw.raw_available():
        print("data/raw/ not found: fee schedule and rule tables not loaded")
    for table, count in counts.items():
        size = f"  {sizes[table] / 1e6:8.1f} MB" if table in sizes else ""
        print(f"{table:24} {count:>9,}{size}")
    print(f"seeded in {time.perf_counter() - started:.1f} s")


if __name__ == "__main__":
    main()
