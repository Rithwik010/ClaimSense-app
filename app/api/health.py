"""Reachability checks behind GET /health (INSTRUCTIONS.md §8.10).

Each check reports success or failure without raising. Failure details carry only the error
type, never connection strings or credentials.
"""

from collections.abc import Iterator
from typing import Literal

import httpx
from pydantic import BaseModel
from sqlalchemy import Engine, text
from sqlalchemy.exc import SQLAlchemyError

from app.core.settings import Settings

HEALTH_TIMEOUT_SECONDS = 2.0


class ServiceStatus(BaseModel):
    ok: bool
    detail: str


class HealthReport(BaseModel):
    status: Literal["ok", "degraded"]
    database: ServiceStatus
    qdrant: ServiceStatus
    ollama: ServiceStatus


def get_http_client() -> Iterator[httpx.Client]:
    with httpx.Client(timeout=HEALTH_TIMEOUT_SECONDS) as client:
        yield client


def check_database(engine: Engine) -> ServiceStatus:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        return ServiceStatus(ok=False, detail=f"unreachable ({type(exc).__name__})")
    return ServiceStatus(ok=True, detail="reachable")


def check_qdrant(settings: Settings, http: httpx.Client) -> ServiceStatus:
    try:
        http.get(f"{settings.qdrant_url}/readyz").raise_for_status()
    except httpx.HTTPError as exc:
        return ServiceStatus(ok=False, detail=f"unreachable ({type(exc).__name__})")
    return ServiceStatus(ok=True, detail="reachable")


def check_ollama(settings: Settings, http: httpx.Client) -> ServiceStatus:
    try:
        response = http.get(f"{settings.ollama_url}/api/tags")
        response.raise_for_status()
        models = {model.get("name") for model in response.json().get("models", [])}
    except (httpx.HTTPError, ValueError, AttributeError) as exc:
        return ServiceStatus(ok=False, detail=f"unreachable ({type(exc).__name__})")
    if settings.model_name not in models:
        return ServiceStatus(
            ok=False, detail=f"reachable, but model {settings.model_name} is not pulled"
        )
    return ServiceStatus(ok=True, detail=f"reachable, model {settings.model_name} available")


def build_health_report(settings: Settings, engine: Engine, http: httpx.Client) -> HealthReport:
    database = check_database(engine)
    qdrant = check_qdrant(settings, http)
    ollama = check_ollama(settings, http)
    all_ok = database.ok and qdrant.ok and ollama.ok
    return HealthReport(
        status="ok" if all_ok else "degraded",
        database=database,
        qdrant=qdrant,
        ollama=ollama,
    )
