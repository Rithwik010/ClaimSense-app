"""Alembic migrations on a fresh database (INSTRUCTIONS.md §11, P1.3).

Uses a throwaway database (`claimsense_test` by default) next to the dev database. Skipped when
Postgres is not reachable, unless CLAIMSENSE_REQUIRE_DB=1 (set in CI), in which case it fails.
"""

import os
from collections.abc import Iterator
from datetime import date

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import Engine, create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError, OperationalError

from app.core.settings import get_settings
from app.db import models  # noqa: F401  (registers every table)
from app.db.base import Base

TEST_DB_NAME = "claimsense_test"


def test_database_url() -> str:
    explicit = os.environ.get("TEST_DATABASE_URL")
    if explicit:
        return explicit
    return (
        make_url(get_settings().database_url)
        .set(database=TEST_DB_NAME)
        .render_as_string(hide_password=False)
    )


test_database_url.__test__ = False  # a helper, not a test


@pytest.fixture(scope="module")
def db_url() -> Iterator[str]:
    url = make_url(test_database_url())
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{url.database}" WITH (FORCE)'))
            conn.execute(text(f'CREATE DATABASE "{url.database}"'))
    except OperationalError as exc:
        if os.environ.get("CLAIMSENSE_REQUIRE_DB") == "1":
            raise
        pytest.skip(f"Postgres not reachable ({type(exc).__name__}); run `docker compose up -d`")
    yield url.render_as_string(hide_password=False)
    with admin.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{url.database}" WITH (FORCE)'))
    admin.dispose()


def alembic_config(url: str) -> Config:
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", url)
    config.attributes["configure_logger"] = False
    return config


@pytest.fixture
def migrated(db_url: str) -> Iterator[Engine]:
    config = alembic_config(db_url)
    command.upgrade(config, "head")
    engine = create_engine(db_url)
    yield engine
    engine.dispose()
    command.downgrade(config, "base")


def test_upgrade_creates_every_table(migrated: Engine) -> None:
    tables = set(inspect(migrated).get_table_names())

    assert tables == set(Base.metadata.tables) | {"alembic_version"}


def test_models_and_migration_match(migrated: Engine) -> None:
    with migrated.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)

    assert diff == []


def test_money_is_bigint_cents_and_rates_are_integer_bps(migrated: Engine) -> None:
    columns = [
        (table, column["name"], str(column["type"]))
        for table in Base.metadata.tables
        for column in inspect(migrated).get_columns(table)
    ]

    cents = [(t, c, ty) for t, c, ty in columns if c.endswith("_cents")]
    bps = [(t, c, ty) for t, c, ty in columns if c.endswith("_bps")]
    assert cents and all(ty == "BIGINT" for _, _, ty in cents)
    assert bps and all(ty == "INTEGER" for _, _, ty in bps)


def test_downgrade_removes_everything(db_url: str) -> None:
    config = alembic_config(db_url)
    command.upgrade(config, "head")
    command.downgrade(config, "base")
    engine = create_engine(db_url)
    with engine.connect() as conn:
        tables = set(inspect(conn).get_table_names())
        functions = conn.execute(
            text("SELECT count(*) FROM pg_proc WHERE proname = 'audit_events_append_only'")
        ).scalar_one()
    engine.dispose()

    assert tables <= {"alembic_version"}
    assert functions == 0


def insert_claim(conn, claim_id: str = "CLM-TEST-1") -> None:
    conn.execute(
        text(
            "INSERT INTO claims (claim_id, member_id, received_date, source_format, status, "
            "intake, field_confidences) VALUES (:id, 'MBR-1', :d, 'JSON', 'RECEIVED', '{}', '{}')"
        ),
        {"id": claim_id, "d": date(2026, 10, 5)},
    )


def test_audit_events_are_append_only(migrated: Engine) -> None:
    with migrated.begin() as conn:
        insert_claim(conn)
        conn.execute(
            text(
                "INSERT INTO audit_events (claim_id, event_type, actor, payload) "
                "VALUES ('CLM-TEST-1', 'INTAKE_COMPLETED', 'system', '{}')"
            )
        )

    for statement in ("UPDATE audit_events SET actor = 'someone'", "DELETE FROM audit_events"):
        with pytest.raises(DBAPIError, match="append-only"), migrated.begin() as conn:
            conn.execute(text(statement))

    with migrated.connect() as conn:
        rows = conn.execute(text("SELECT actor FROM audit_events")).scalars().all()
    assert rows == ["system"]


def test_claim_status_must_be_a_known_value(migrated: Engine) -> None:
    with pytest.raises(DBAPIError, match="ck_claims_status_allowed"), migrated.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO claims (claim_id, member_id, received_date, source_format, status, "
                "intake, field_confidences) "
                "VALUES ('CLM-X', 'MBR-1', '2026-10-05', 'JSON', 'MAYBE', '{}', '{}')"
            )
        )


def test_out_of_network_terms_must_match_coverage_flag(migrated: Engine) -> None:
    with pytest.raises(DBAPIError, match="oon_terms_match_coverage"), migrated.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO plans (plan_id, name, plan_type, effective_date, "
                "filing_window_inn_days, filing_window_oon_days, oon_covered, "
                "inn_deductible_cents, inn_coinsurance_bps, inn_oop_max_cents) "
                "VALUES ('P1', 'Plan', 'PPO', '2026-01-01', 90, 180, true, 50000, 2000, 300000)"
            )
        )
