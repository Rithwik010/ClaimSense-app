"""Application wiring: root redirect and request logging."""

import logging

from fastapi.testclient import TestClient

from app.api.main import app
from app.core.logging import configure_logging


def test_root_redirects_to_docs() -> None:
    with TestClient(app) as client:
        response = client.get("/", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == "/docs"


def test_configure_logging_disables_uvicorn_access_log() -> None:
    access_log = logging.getLogger("uvicorn.access")
    access_log.disabled = False

    configure_logging()

    assert access_log.disabled
