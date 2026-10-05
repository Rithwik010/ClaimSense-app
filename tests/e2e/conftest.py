"""Fixtures for the end-to-end tests: a fresh, migrated and seeded database per test, and an API
client with the database and the model swapped in."""

from collections.abc import Callable, Iterator
from typing import Any

import pytest
from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

from app.api.deps import get_decision_model, get_retriever
from app.api.main import app
from app.db.models import FeeScheduleEntry
from app.db.seed import load_reference, load_rule_tables, seed_curated, upsert
from app.db.session import get_engine
from app.ml.client import DecisionModel
from tests.database import alembic_config, fresh_database
from tests.e2e.support import StubRetriever, claim_on_file, e2e_fee_rows
from tests.rule_tables import fixture_rule_tables


@pytest.fixture
def engine() -> Iterator[Engine]:
    """Each test gets its own database: claims on file count for the duplicate check (A-R6) and
    audit events cannot be deleted. The rule tables come from the committed fixture, which covers
    every golden end-to-end claim (D-CI-1), so the tests run the same in CI."""
    with fresh_database("claimsense_e2e") as url:
        command.upgrade(alembic_config(url), "head")
        engine = create_engine(url)
        with Session(engine) as session:
            seed_curated(session)
            load_rule_tables(session, fixture_rule_tables())
            upsert(session, FeeScheduleEntry, e2e_fee_rows())
            session.commit()
        yield engine
        engine.dispose()


@pytest.fixture
def load_case_reference(engine: Engine) -> Callable[[dict[str, Any]], None]:
    """The case's reference additions, with its claims on file as claims rows."""

    def load(case: dict[str, Any]) -> None:
        additions = case["given"]["reference_additions"]
        with Session(engine) as session:
            load_reference(session, additions)
            session.add_all(claim_on_file(row) for row in additions.get("existing_claims", []))
            session.commit()

    return load


@pytest.fixture
def api(engine: Engine) -> Iterator[Callable[[DecisionModel], TestClient]]:
    clients: list[TestClient] = []

    def make(model: DecisionModel, retriever: StubRetriever | None = None) -> TestClient:
        app.dependency_overrides[get_engine] = lambda: engine
        app.dependency_overrides[get_decision_model] = lambda: model
        app.dependency_overrides[get_retriever] = lambda: retriever or StubRetriever()
        client = TestClient(app)
        clients.append(client)
        return client

    yield make
    for client in clients:
        client.close()
    app.dependency_overrides.clear()
