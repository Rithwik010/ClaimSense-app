"""`make demo-check`: OK or FAIL for each service the demo needs.

Postgres (a query), Ollama with the demo model loaded in memory, the API's /health, the web app
(its page, with the API on the same origin: `make demo-up` serves both on :8000, D-AUTH-1; set
WEB_URL=http://localhost:5173 for the dev server of `make demo`), and every demo login (the
passwords in .env).

    uv run python -m scripts.demo.check
"""

import os
import sys

import httpx
from sqlalchemy import text

from app.core.settings import get_settings
from app.db.session import get_engine
from scripts.demo.users import USERS, password

API = "http://localhost:8000"
WEB = os.environ.get("WEB_URL", API)


def main() -> None:
    settings = get_settings()
    model = os.environ.get("MODEL_NAME", "claimsense-decision:v2")
    results: list[tuple[str, bool, str]] = []

    def probe(name: str, test) -> None:  # noqa: ANN001
        try:
            ok, detail = test()
        except Exception as exc:  # noqa: BLE001 - a check reports any failure as FAIL
            ok, detail = False, f"{type(exc).__name__}: {exc}"[:120]
        results.append((name, ok, detail))

    def postgres() -> tuple[bool, str]:
        with get_engine().connect() as connection:
            claims = connection.execute(text("select count(*) from claims")).scalar()
        return True, f"{claims} claims on file"

    def ollama() -> tuple[bool, str]:
        loaded = [
            m["name"]
            for m in httpx.get(f"{settings.ollama_url}/api/ps", timeout=5).json()["models"]
        ]
        return (
            model in loaded,
            f"{model} loaded" if model in loaded else f"loaded: {loaded or 'none'}",
        )

    def api() -> tuple[bool, str]:
        health = httpx.get(f"{API}/health", timeout=10).json()
        bad = [s for s in ("database", "qdrant", "ollama") if not health[s]["ok"]]
        return not bad, "database, Qdrant and Ollama reachable" if not bad else f"not ok: {bad}"

    def web() -> tuple[bool, str]:
        page = httpx.get(WEB, timeout=5)
        api_there = httpx.get(f"{WEB}/v1/auth/me", timeout=10)  # 401 JSON: the API answers
        ok = '<div id="root">' in page.text and api_there.headers.get(
            "content-type", ""
        ).startswith("application/json")
        return (
            ok,
            f"page and API at {WEB}" if ok else f"{WEB}: page or API missing",
        )

    def logins() -> tuple[bool, str]:
        failed = []
        for username, (role, _, _) in USERS.items():
            with httpx.Client(base_url=WEB, timeout=10) as client:
                login = client.post(
                    "/v1/auth/login", json={"username": username, "password": password(username)}
                )
                me = client.get("/v1/auth/me")
            if login.status_code != 200 or me.json().get("role") != role.value:
                failed.append(username)
        return (
            not failed,
            f"{len(USERS)} demo users log in" if not failed else f"cannot log in: {failed}",
        )

    probe("Postgres", postgres)
    probe("Ollama", ollama)
    probe("API", api)
    probe("Web app", web)
    probe("Logins", logins)
    for name, ok, detail in results:
        print(f"{'OK  ' if ok else 'FAIL'} {name:8} {detail}")
    if not all(ok for _, ok, _ in results):
        sys.exit(1)


if __name__ == "__main__":
    main()
