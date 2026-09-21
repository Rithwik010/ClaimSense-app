"""GET /health reports database, Qdrant and Ollama reachability (INSTRUCTIONS.md §8.10).

Services are simulated: SQLite stands in for a reachable database, a closed local port for an
unreachable one, and an httpx mock transport for Qdrant and Ollama.
"""

from collections.abc import Callable, Iterator

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine

from app.api.health import build_health_report, get_http_client
from app.api.main import app
from app.core.settings import Settings, get_settings
from app.db.session import get_engine

SETTINGS = Settings(
    _env_file=None,
    qdrant_url="http://qdrant.test",
    ollama_url="http://ollama.test",
    model_name="gemma4:e2b",
)

Handler = Callable[[httpx.Request], httpx.Response]


def reachable_db() -> Engine:
    return create_engine("sqlite://")


def unreachable_db() -> Engine:
    return create_engine(
        "postgresql+psycopg://user:secret@127.0.0.1:1/none",
        connect_args={"connect_timeout": 2},
    )


def services(
    *, qdrant_up: bool = True, ollama_up: bool = True, models: list[str] | None = None
) -> Handler:
    pulled = ["gemma4:e2b"] if models is None else models

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "qdrant.test" and request.url.path == "/readyz":
            if not qdrant_up:
                raise httpx.ConnectError("connection refused", request=request)
            return httpx.Response(200, text="all shards are ready")
        if request.url.host == "ollama.test" and request.url.path == "/api/tags":
            if not ollama_up:
                raise httpx.ConnectError("connection refused", request=request)
            return httpx.Response(200, json={"models": [{"name": name} for name in pulled]})
        return httpx.Response(404)

    return handler


def report(engine: Engine, handler: Handler):
    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        return build_health_report(SETTINGS, engine, http)


def test_all_services_up() -> None:
    result = report(reachable_db(), services())

    assert result.status == "ok"
    assert result.database.ok and result.qdrant.ok and result.ollama.ok
    assert result.ollama.detail == "reachable, model gemma4:e2b available"


def test_database_down_is_degraded() -> None:
    result = report(unreachable_db(), services())

    assert result.status == "degraded"
    assert not result.database.ok
    assert result.qdrant.ok and result.ollama.ok


def test_database_failure_detail_hides_credentials() -> None:
    result = report(unreachable_db(), services())

    assert "secret" not in result.database.detail
    assert "127.0.0.1" not in result.database.detail


def test_qdrant_down_is_degraded() -> None:
    result = report(reachable_db(), services(qdrant_up=False))

    assert result.status == "degraded"
    assert not result.qdrant.ok
    assert result.qdrant.detail == "unreachable (ConnectError)"


def test_ollama_down_is_degraded() -> None:
    result = report(reachable_db(), services(ollama_up=False))

    assert result.status == "degraded"
    assert not result.ollama.ok


def test_model_not_pulled_is_degraded() -> None:
    result = report(reachable_db(), services(models=["llama3.2:3b"]))

    assert result.status == "degraded"
    assert not result.ollama.ok
    assert result.ollama.detail == "reachable, but model gemma4:e2b is not pulled"


@pytest.fixture
def client() -> Iterator[TestClient]:
    def http_client() -> Iterator[httpx.Client]:
        with httpx.Client(transport=httpx.MockTransport(services(qdrant_up=False))) as http:
            yield http

    app.dependency_overrides[get_settings] = lambda: SETTINGS
    app.dependency_overrides[get_engine] = reachable_db
    app.dependency_overrides[get_http_client] = http_client
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_health_endpoint_returns_200_with_per_service_status(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "degraded",
        "database": {"ok": True, "detail": "reachable"},
        "qdrant": {"ok": False, "detail": "unreachable (ConnectError)"},
        "ollama": {"ok": True, "detail": "reachable, model gemma4:e2b available"},
    }
