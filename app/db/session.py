"""Database engine: SQLAlchemy 2.0 over psycopg 3."""

from functools import lru_cache

from sqlalchemy import Engine, create_engine

from app.core.settings import get_settings

CONNECT_TIMEOUT_SECONDS = 2


@lru_cache
def get_engine() -> Engine:
    return create_engine(
        get_settings().database_url,
        pool_pre_ping=True,
        connect_args={"connect_timeout": CONNECT_TIMEOUT_SECONDS},
    )
