"""Application wiring: root redirect and request logging."""

import logging

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.main import app, serve_web_app
from app.core.logging import configure_logging


def test_the_api_serves_the_web_app_build_on_its_own_origin(tmp_path) -> None:  # noqa: ANN001
    """D-AUTH-1: the build's files, index.html for the app's own routes, never for API paths, and
    nothing outside the build."""
    (tmp_path / "web" / "assets").mkdir(parents=True)
    (tmp_path / "web" / "index.html").write_text("<!doctype html><title>ClaimSense</title>")
    (tmp_path / "web" / "assets" / "app.js").write_text("console.log(1)")
    (tmp_path / "secret.txt").write_text("outside the build")
    api = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)  # as the app

    @api.get("/v1/known")
    def known() -> dict[str, bool]:
        return {"ok": True}

    serve_web_app(api, tmp_path / "web")
    client = TestClient(api)

    for path in ("/", "/login", "/queue", "/claims/CLM-1"):
        assert "<title>ClaimSense</title>" in client.get(path).text, path
    assert client.get("/assets/app.js").text == "console.log(1)"
    assert client.get("/v1/known").json() == {"ok": True}
    for path in ("/v1/unknown", "/health/x", "/docs", "/openapi.json"):
        assert client.get(path).status_code == 404, path
    assert "outside the build" not in client.get("/..%2Fsecret.txt").text


def test_without_a_build_nothing_is_served(tmp_path) -> None:  # noqa: ANN001
    api = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)  # as the app
    serve_web_app(api, tmp_path)
    assert TestClient(api).get("/").status_code == 404


def test_the_api_docs_are_off(tmp_path) -> None:  # noqa: ANN001
    with TestClient(app) as client:
        assert client.get("/docs").status_code == 404
        assert client.get("/openapi.json").status_code == 404


def test_configure_logging_disables_uvicorn_access_log() -> None:
    access_log = logging.getLogger("uvicorn.access")
    access_log.disabled = False

    configure_logging()

    assert access_log.disabled
