"""Fixtures for the end-to-end tests: a fresh, migrated and seeded database, and an API client
with the database and the model swapped in."""

from collections.abc import Callable, Iterator
from typing import Any

import pytest
from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

from app.api.deps import get_decision_model
from app.api.main import app
from app.db.models import FeeScheduleEntry
from app.db.seed import load_reference, seed_curated, upsert
from app.db.session import get_engine
from app.ml.client import DecisionModel
from tests.database import alembic_config, fresh_database
from tests.e2e.support import golden_fee_rows


@pytest.fixture(scope="module")
def engine() -> Iterator[Engine]:
    with fresh_database("claimsense_e2e") as url:
        command.upgrade(alembic_config(url), "head")
        engine = create_engine(url)
        with Session(engine) as session:
            seed_curated(session)
            upsert(session, FeeScheduleEntry, golden_fee_rows())
            session.commit()
        yield engine
        engine.dispose()


@pytest.fixture
def load_case_reference(engine: Engine) -> Callable[[dict[str, Any]], None]:
    def load(case: dict[str, Any]) -> None:
        with Session(engine) as session:
            load_reference(session, case["given"]["reference_additions"])
            session.commit()

    return load


@pytest.fixture
def api(engine: Engine) -> Iterator[Callable[[DecisionModel], TestClient]]:
    clients: list[TestClient] = []

    def make(model: DecisionModel) -> TestClient:
        app.dependency_overrides[get_engine] = lambda: engine
        app.dependency_overrides[get_decision_model] = lambda: model
        client = TestClient(app)
        clients.append(client)
        return client

    yield make
    for client in clients:
        client.close()
    app.dependency_overrides.clear()
