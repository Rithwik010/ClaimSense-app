"""Alembic migrations on a fresh database (INSTRUCTIONS.md §11, P1.3).

Uses a throwaway database (`claimsense_test`) next to the dev database (see tests/database.py).
"""

from collections.abc import Iterator
from datetime import date

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import Engine, create_engine, inspect, text
from sqlalchemy.exc import DBAPIError

from app.db import models  # noqa: F401  (registers every table)
from app.db.base import Base
from tests.database import alembic_config, fresh_database

TEST_DB_NAME = "claimsense_test"


@pytest.fixture(scope="module")
def db_url() -> Iterator[str]:
    with fresh_database(TEST_DB_NAME) as url:
        yield url


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


def test_a_failed_calculation_can_be_audited_and_unknown_event_types_cannot(
    migrated: Engine,
) -> None:
    """Migration 0002 (P2.4): CALCULATION_FAILED joins the audit event types."""
    with migrated.begin() as conn:
        insert_claim(conn, "CLM-TEST-CALC")
        conn.execute(
            text(
                "INSERT INTO audit_events (claim_id, event_type, actor, payload) "
                "VALUES ('CLM-TEST-CALC', 'CALCULATION_FAILED', 'system', '{}')"
            )
        )
    with (
        pytest.raises(DBAPIError, match="ck_audit_events_event_type_allowed"),
        migrated.begin() as conn,
    ):
        conn.execute(
            text(
                "INSERT INTO audit_events (claim_id, event_type, actor, payload) "
                "VALUES ('CLM-TEST-CALC', 'NOT_AN_EVENT', 'system', '{}')"
            )
        )


def test_downgrading_0002_keeps_audited_calculation_failures(db_url: str) -> None:
    """The audit trail is append-only, so going back to 0001 keeps CALCULATION_FAILED rows; the
    old event-type check applies to new rows only."""
    config = alembic_config(db_url)
    command.upgrade(config, "head")
    engine = create_engine(db_url)
    with engine.begin() as conn:
        insert_claim(conn, "CLM-TEST-DOWN")
        conn.execute(
            text(
                "INSERT INTO audit_events (claim_id, event_type, actor, payload) "
                "VALUES ('CLM-TEST-DOWN', 'CALCULATION_FAILED', 'system', '{}')"
            )
        )

    command.downgrade(config, "0001")

    with engine.connect() as conn:
        kept = conn.execute(text("SELECT event_type FROM audit_events")).scalars().all()
    with (
        pytest.raises(DBAPIError, match="ck_audit_events_event_type_allowed"),
        engine.begin() as conn,
    ):
        conn.execute(
            text(
                "INSERT INTO audit_events (claim_id, event_type, actor, payload) "
                "VALUES ('CLM-TEST-DOWN', 'CALCULATION_FAILED', 'system', '{}')"
            )
        )
    engine.dispose()
    command.downgrade(config, "base")

    assert kept == ["CALCULATION_FAILED"]


def test_a_review_opening_can_be_audited(migrated: Engine) -> None:
    """Migration 0004 (P5.3): REVIEW_OPENED joins the audit event types."""
    with migrated.begin() as conn:
        insert_claim(conn, "CLM-TEST-OPEN")
        conn.execute(
            text(
                "INSERT INTO audit_events (claim_id, event_type, actor, payload) "
                "VALUES ('CLM-TEST-OPEN', 'REVIEW_OPENED', 'reviewer-1', '{}')"
            )
        )


def test_downgrading_0004_keeps_audited_review_openings(db_url: str) -> None:
    """Going back to 0003 keeps REVIEW_OPENED rows (append-only); new ones are refused."""
    config = alembic_config(db_url)
    command.upgrade(config, "head")
    engine = create_engine(db_url)
    insert = text(
        "INSERT INTO audit_events (claim_id, event_type, actor, payload) "
        "VALUES ('CLM-TEST-DOWN', 'REVIEW_OPENED', 'reviewer-1', '{}')"
    )
    with engine.begin() as conn:
        insert_claim(conn, "CLM-TEST-DOWN")
        conn.execute(insert)

    command.downgrade(config, "0003")

    with engine.connect() as conn:
        kept = conn.execute(text("SELECT event_type FROM audit_events")).scalars().all()
    with (
        pytest.raises(DBAPIError, match="ck_audit_events_event_type_allowed"),
        engine.begin() as conn,
    ):
        conn.execute(insert)
    engine.dispose()
    command.downgrade(config, "base")

    assert kept == ["REVIEW_OPENED"]


def test_a_field_correction_is_audited_with_its_request_id(migrated: Engine) -> None:
    """Migration 0010 (D-FIX-1, D-OBS-1): FIELD_CORRECTED joins the event types, and an event
    keeps the ID of the request that wrote it."""
    with migrated.begin() as conn:
        insert_claim(conn, "CLM-TEST-FIX")
        conn.execute(
            text(
                "INSERT INTO audit_events (claim_id, event_type, actor, payload, request_id) "
                "VALUES ('CLM-TEST-FIX', 'FIELD_CORRECTED', 'provider-1', '{}', 'abc123')"
            )
        )
        found = conn.execute(text("SELECT request_id FROM audit_events")).scalar_one()
    assert found == "abc123"


def test_downgrading_0010_keeps_audited_corrections(db_url: str) -> None:
    """Going back to 0009 keeps FIELD_CORRECTED rows (append-only) without their request ID; new
    ones are refused."""
    config = alembic_config(db_url)
    command.upgrade(config, "head")
    engine = create_engine(db_url)
    insert = text(
        "INSERT INTO audit_events (claim_id, event_type, actor, payload) "
        "VALUES ('CLM-TEST-DOWN', 'FIELD_CORRECTED', 'provider-1', '{}')"
    )
    with engine.begin() as conn:
        insert_claim(conn, "CLM-TEST-DOWN")
        conn.execute(insert)

    command.downgrade(config, "0009")

    with engine.connect() as conn:
        kept = conn.execute(text("SELECT event_type FROM audit_events")).scalars().all()
        columns = {c["name"] for c in inspect(conn).get_columns("audit_events")}
    with (
        pytest.raises(DBAPIError, match="ck_audit_events_event_type_allowed"),
        engine.begin() as conn,
    ):
        conn.execute(insert)
    engine.dispose()
    command.downgrade(config, "base")

    assert kept == ["FIELD_CORRECTED"]
    assert "request_id" not in columns


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
