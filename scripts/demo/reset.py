"""`make demo-reset` (demo plan item 8): a clean database ready for the demo claims.

1. Drops every table and migrates to the latest schema (alembic downgrade base, upgrade head),
   which deletes every claim with its stored original file (D-DOC-1).
2. Generates the synthetic reference data if `data/generated/reference/` is missing (seeded, so
   always the same members, providers and plans).
3. Seeds curated data, the public code tables from data/raw/ and the reference data, then the
   prior authorizations the demo claims need (`demo/authorizations.jsonl`).
4. Builds the coverage policy collections in Qdrant when one is missing.
5. The demo logins (`scripts/demo/users.py`; passwords and SECRET_KEY in .env, written when
   missing).
6. Checks that Ollama serves the demo model (`MODEL_NAME`, default claimsense-decision:v3), then
   loads it and keeps it loaded (a warm-up call with keep_alive -1).

    uv run python -m scripts.demo.reset
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import httpx
from alembic import command
from alembic.config import Config
from qdrant_client import QdrantClient
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session

from app.core.settings import get_settings
from app.db import raw
from app.db.models import Authorization
from app.db.seed import seed, upsert
from app.db.session import get_engine
from app.rag.knowledge import COVERAGE_COLLECTIONS
from scripts.demo.users import USERS, ensure_env, seed_users

ROOT = Path(__file__).resolve().parents[2]
REFERENCE = ROOT / "data" / "generated" / "reference"
DEMO = ROOT / "demo"
DEMO_MODEL = "claimsense-decision:v3"


def step(text: str) -> None:
    print(f"- {text}", flush=True)


def stored_files(url: str) -> int:
    """How many original claim files the database holds (0 before migration 0008)."""
    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            if "claim_documents" not in inspect(conn).get_table_names():
                return 0
            return conn.execute(text("SELECT count(*) FROM claim_documents")).scalar_one()
    finally:
        engine.dispose()


def reset_database(alembic: Config, url: str) -> int:
    """Drop every table (claims, their records, audit trails and stored files included) and
    migrate to the latest schema; returns how many stored files were deleted."""
    deleted = stored_files(url)
    command.downgrade(alembic, "base")
    command.upgrade(alembic, "head")
    return deleted


def main() -> None:
    settings = get_settings()
    alembic = Config(str(ROOT / "alembic.ini"))
    step("database: dropping every table and migrating to the latest schema")
    deleted = reset_database(alembic, settings.database_url)
    step(f"stored claim files deleted: {deleted}")

    if not REFERENCE.exists():
        step("reference data: generating (seeded)")
        subprocess.run([sys.executable, "-m", "training.generate.reference"], check=True, cwd=ROOT)
    if not raw.raw_available():
        sys.exit(
            "data/raw/ is missing: the rule tables and fee schedule cannot be loaded (SETUP.md)"
        )

    step("database: seeding curated data, code tables and reference data")
    with Session(get_engine()) as session:
        counts = seed(session, REFERENCE)
        rows = [
            json.loads(line)
            for line in (DEMO / "authorizations.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        upsert(session, Authorization, rows)
        session.commit()
    step(f"seeded {sum(counts.values()):,} rows; {len(rows)} demo authorizations")
    written = ensure_env()
    with Session(get_engine()) as session:
        seed_users(session)
    step(
        f"users: {', '.join(USERS)} (passwords in .env"
        + (f"; wrote {', '.join(written)}" if written else "")
        + ")"
    )

    client = QdrantClient(url=settings.qdrant_url)
    have = {c.name for c in client.get_collections().collections}
    if not set(COVERAGE_COLLECTIONS.values()) <= have:
        step("qdrant: building the coverage policy collections")
        subprocess.run([sys.executable, "-m", "app.rag.knowledge"], check=True, cwd=ROOT)
    step("qdrant: coverage policy collections ready")

    model = os.environ.get("MODEL_NAME", DEMO_MODEL)
    try:
        names = [
            m["name"]
            for m in httpx.get(f"{settings.ollama_url}/api/tags", timeout=5).json()["models"]
        ]
    except httpx.HTTPError:
        sys.exit(f"Ollama is not reachable at {settings.ollama_url}: start it with 'ollama serve'")
    if model not in names:
        sys.exit(
            f"Ollama does not serve {model}: create it from its Modelfile (docs/fine-tuning.md)"
        )
    step(f"ollama: {model} available")
    # Warm-up: load the model now and keep it loaded, so the first demo claim is not slow.
    httpx.post(
        f"{settings.ollama_url}/api/generate", json={"model": model, "keep_alive": -1}, timeout=300
    ).raise_for_status()
    step(f"ollama: {model} loaded and kept loaded")
    print("Ready. Start the app with: make demo-up (or make demo for the dev server)")


if __name__ == "__main__":
    main()
