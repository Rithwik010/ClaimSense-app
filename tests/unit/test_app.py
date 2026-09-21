"""Application wiring: root redirect and request logging."""

import logging

from fastapi.testclient import TestClient

from app.api.main import app


def test_root_redirects_to_docs() -> None:
    with TestClient(app) as client:
        response = client.get("/", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == "/docs"


def test_uvicorn_access_log_is_disabled() -> None:
    assert logging.getLogger("uvicorn.access").disabled
