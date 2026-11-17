"""FastAPI application (INSTRUCTIONS.md §8.10). Run: uv run uvicorn app.api.main:app"""

import time
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Annotated

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import Engine

from app.api import (
    audit,
    auth,
    claims,
    member,
    metrics,
    notifications,
    plans,
    policies,
    review,
    users,
)
from app.api.health import HealthReport, build_health_report, get_http_client
from app.core.logging import (
    REQUEST_ID_HEADER,
    bind_request_id,
    clear_request_id,
    configure_logging,
    get_logger,
)
from app.core.settings import Settings, get_settings
from app.db.session import get_engine

configure_logging()
log = get_logger(__name__)

SETTINGS = get_settings()
# Only login and /health are public (D-AUTH-1): the API docs are off unless API_DOCS=1.
app = FastAPI(
    title="ClaimSense API",
    version="0.1.0",
    docs_url="/docs" if SETTINGS.api_docs else None,
    redoc_url=None,
    openapi_url="/openapi.json" if SETTINGS.api_docs else None,
)
app.include_router(auth.router)
app.include_router(claims.router)
app.include_router(review.router)
app.include_router(metrics.router)
app.include_router(plans.router)
app.include_router(member.router)
app.include_router(users.router)
app.include_router(audit.router)
app.include_router(policies.router)
app.include_router(notifications.router)


@app.middleware("http")
async def log_requests(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Log every request as one JSON line with its request ID (D-OBS-1), which every other log
    line and audit event of the request carries too, and which the response returns."""
    started = time.perf_counter()
    request_id = bind_request_id()
    try:
        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = request_id
        route = request.scope.get("route")
        log.info(
            "request",
            method=request.method,
            route=getattr(route, "path", request.url.path),
            status=response.status_code,
            duration_ms=round((time.perf_counter() - started) * 1000, 1),
        )
        return response
    finally:
        clear_request_id()


@app.get("/health")
def health(
    settings: Annotated[Settings, Depends(get_settings)],
    engine: Annotated[Engine, Depends(get_engine)],
    http: Annotated[httpx.Client, Depends(get_http_client)],
) -> HealthReport:
    return build_health_report(settings, engine, http)


def serve_web_app(api: FastAPI, web: Path) -> None:
    """The production build of the web app on the API's own origin (D-AUTH-1), so the session
    cookie needs no CORS: its files, and index.html for any other path the app routes itself. API
    paths never fall through to it. Nothing is served without a build."""
    if not (web / "index.html").is_file():
        return
    root = web.resolve()
    if (web / "assets").is_dir():
        api.mount("/assets", StaticFiles(directory=web / "assets"), name="assets")

    @api.get("/{path:path}", include_in_schema=False)
    def web_app(path: str) -> FileResponse:
        if path.startswith(("v1/", "health", "docs", "openapi.json")):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Not Found")
        file = (root / path).resolve()
        if path and file.is_file() and file.is_relative_to(root):
            return FileResponse(file)
        return FileResponse(root / "index.html")


serve_web_app(app, SETTINGS.web_dist)
