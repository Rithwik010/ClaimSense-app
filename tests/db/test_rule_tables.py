"""P2.1: the rule tables load into Postgres with provenance, and loading again changes nothing.

The fixture load runs everywhere (CI has Postgres, D-CI-1); the full load from data/raw/ is
skipped where data/raw/ is absent."""

from collections.abc import Iterator

import pytest
from alembic import command
from sqlalchemy import Engine, create_engine, func, select
from sqlalchemy.orm import Session

from app.db import raw
from app.db.models import (
    Icd10Code,
    MueLimit,
    NcciPtpEdit,
    PlaceOfServiceCode,
    ProcedureCode,
    ReferenceSource,
)
from app.db.seed import load_rule_tables, raw_rule_tables, seed_curated
from tests.database import alembic_config, fresh_database
from tests.rule_tables import fixture_rule_tables

TABLES = (PlaceOfServiceCode, ProcedureCode, Icd10Code, MueLimit, NcciPtpEdit)


@pytest.fixture
def engine() -> Iterator[Engine]:
    with fresh_database("claimsense_rule_tables") as url:
        command.upgrade(alembic_config(url), "head")
        engine = create_engine(url)
        with Session(engine) as session:
            seed_curated(session)
            session.commit()
        yield engine
        engine.dispose()


def counts(session: Session) -> dict[str, int]:
    return {m.__tablename__: session.scalar(select(func.count()).select_from(m)) for m in TABLES}


def snapshot(session: Session) -> list[tuple]:
    edits = session.execute(
        select(
            NcciPtpEdit.id,
            NcciPtpEdit.column1_code,
            NcciPtpEdit.column2_code,
            NcciPtpEdit.effective_date,
            NcciPtpEdit.deletion_date,
            NcciPtpEdit.modifier_indicator,
            NcciPtpEdit.source_order,
        ).order_by(NcciPtpEdit.source_order)
    ).all()
    procedures = session.execute(
        select(ProcedureCode.code, ProcedureCode.description, ProcedureCode.in_scope).order_by(
            ProcedureCode.code
        )
    ).all()
    return [*edits, *procedures]


def test_the_fixture_loads_with_provenance_and_again_changes_nothing(engine: Engine) -> None:
    data = fixture_rule_tables()
    with Session(engine) as session:
        curated_descriptions = dict(
            session.execute(select(ProcedureCode.code, ProcedureCode.description)).all()
        )
        loaded = load_rule_tables(session, data)
        session.commit()
        first = (counts(session), snapshot(session))
        load_rule_tables(session, data)
        session.commit()
        second = (counts(session), snapshot(session))
        sources = session.execute(
            select(ReferenceSource.table_name, ReferenceSource.source_path, ReferenceSource.sha256)
        ).all()
        kept = dict(
            session.execute(
                select(ProcedureCode.code, ProcedureCode.description).where(ProcedureCode.in_scope)
            ).all()
        )

    rows = list(data.ncci_rows())
    assert loaded["ncci_ptp_edits"] == len(rows) and loaded["mue_limits"] == len(data.mue)
    assert first == second
    edits = [row[1:6] for row in first[1][: len(rows)]]
    assert edits == rows  # published order kept
    assert {table for table, _, _ in sources} == {m.__tablename__ for m in TABLES}
    assert {path for _, path, _ in sources} == {"tests/golden/rules/raw_subset.json"}
    assert kept == curated_descriptions  # in-scope descriptions are not overwritten


@pytest.mark.skipif(not raw.raw_available(), reason="data/raw/ not present")
def test_data_raw_loads_in_full_with_the_manifest_hashes(engine: Engine) -> None:
    data = raw_rule_tables()
    manifest = raw.manifest_sha256()
    with Session(engine) as session:
        load_rule_tables(session, data)
        session.commit()
        loaded = counts(session)
        sources = session.execute(
            select(ReferenceSource.table_name, ReferenceSource.source_path, ReferenceSource.sha256)
        ).all()
        load_rule_tables(session, data)
        session.commit()
        again = counts(session)
        out_of_scope = session.scalar(
            select(func.count())
            .select_from(ProcedureCode)
            .where(~ProcedureCode.in_scope, ProcedureCode.description.is_not(None))
        )

    assert loaded == {
        "place_of_service_codes": 52,
        "procedure_codes": 20591,
        "icd10_codes": 74879,
        "mue_limits": 15212,
        "ncci_ptp_edits": 2637645,
    }
    assert again == loaded
    assert out_of_scope == 0  # no description outside the scope (H10)
    assert len(sources) == 9  # 1 + 2 + 1 + 1 + the 4 NCCI part files
    for _, path, sha256 in sources:
        assert manifest[path.removeprefix("data/raw/")] == sha256
