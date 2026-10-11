"""FastAPI application (INSTRUCTIONS.md §8.10). Run: uv run uvicorn app.api.main:app"""

import time
from collections.abc import Awaitable, Callable
from typing import Annotated

import httpx
from fastapi import Depends, FastAPI, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy import Engine

from app.api import claims, metrics, plans, review
from app.api.health import HealthReport, build_health_report, get_http_client
from app.core.logging import configure_logging, get_logger
from app.core.settings import Settings, get_settings
from app.db.session import get_engine

configure_logging()
log = get_logger(__name__)

app = FastAPI(title="ClaimSense API", version="0.1.0")
app.include_router(claims.router)
app.include_router(review.router)
app.include_router(metrics.router)
app.include_router(plans.router)


@app.middleware("http")
async def log_requests(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    started = time.perf_counter()
    response = await call_next(request)
    route = request.scope.get("route")
    log.info(
        "request",
        method=request.method,
        route=getattr(route, "path", request.url.path),
        status=response.status_code,
        duration_ms=round((time.perf_counter() - started) * 1000, 1),
    )
    return response


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse(url="/docs")


@app.get("/health")
def health(
    settings: Annotated[Settings, Depends(get_settings)],
    engine: Annotated[Engine, Depends(get_engine)],
    http: Annotated[httpx.Client, Depends(get_http_client)],
) -> HealthReport:
    return build_health_report(settings, engine, http)
