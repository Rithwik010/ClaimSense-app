"""Shared test helpers: throwaway Postgres databases next to the dev database.

`TEST_DATABASE_URL` (optional) gives the server and credentials; each test module picks its own
database name. When Postgres is not reachable the tests are skipped, unless CLAIMSENSE_REQUIRE_DB=1
(set in CI), in which case they fail.
"""

import os
from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError

from app.core.settings import get_settings


def database_url(name: str) -> str:
    base = os.environ.get("TEST_DATABASE_URL") or get_settings().database_url
    return make_url(base).set(database=name).render_as_string(hide_password=False)


def alembic_config(url: str) -> Config:
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", url)
    config.attributes["configure_logger"] = False
    return config


@contextmanager
def fresh_database(name: str) -> Iterator[str]:
    """Create an empty database, yield its URL, and drop it afterwards."""
    url = make_url(database_url(name))
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
            conn.execute(text(f'CREATE DATABASE "{name}"'))
    except OperationalError as exc:
        admin.dispose()
        if os.environ.get("CLAIMSENSE_REQUIRE_DB") == "1":
            raise
        pytest.skip(f"Postgres not reachable ({type(exc).__name__}); run `docker compose up -d`")
    try:
        yield url.render_as_string(hide_password=False)
    finally:
        with admin.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        admin.dispose()
