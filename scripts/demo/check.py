"""`make demo-check`: OK or FAIL for each service the demo needs.

Postgres (a query), Ollama with the demo model loaded in memory, the API's /health, and the web
app (its page and the API through its proxy).

    uv run python -m scripts.demo.check
"""

import os
import sys

import httpx
from sqlalchemy import text

from app.core.settings import get_settings
from app.db.session import get_engine

WEB = "http://localhost:5173"
API = "http://localhost:8000"


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
        proxied = httpx.get(f"{WEB}/v1/claims", timeout=10)
        ok = '<div id="root">' in page.text and proxied.headers.get("content-type", "").startswith(
            "application/json"
        )
        return (
            ok,
            "page served, API reachable through it" if ok else "page or API proxy not answering",
        )

    probe("Postgres", postgres)
    probe("Ollama", ollama)
    probe("API", api)
    probe("Web app", web)
    for name, ok, detail in results:
        print(f"{'OK  ' if ok else 'FAIL'} {name:8} {detail}")
    if not all(ok for _, ok, _ in results):
        sys.exit(1)


if __name__ == "__main__":
    main()
