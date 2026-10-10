"""`make demo-reset` (demo plan item 8): a clean database ready for the demo claims.

1. Drops every table and migrates to the latest schema (alembic downgrade base, upgrade head).
2. Generates the synthetic reference data if `data/generated/reference/` is missing (seeded, so
   always the same members, providers and plans).
3. Seeds curated data, the public code tables from data/raw/ and the reference data, then the
   prior authorizations the demo claims need (`demo/authorizations.jsonl`).
4. Builds the coverage policy collections in Qdrant when one is missing.
5. Checks that Ollama serves the demo model (`MODEL_NAME`, default claimsense-decision:v2).

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
from sqlalchemy.orm import Session

from app.core.settings import get_settings
from app.db import raw
from app.db.models import Authorization
from app.db.seed import seed, upsert
from app.db.session import get_engine
from app.rag.knowledge import COVERAGE_COLLECTIONS

ROOT = Path(__file__).resolve().parents[2]
REFERENCE = ROOT / "data" / "generated" / "reference"
DEMO = ROOT / "demo"
DEMO_MODEL = "claimsense-decision:v2"


def step(text: str) -> None:
    print(f"- {text}", flush=True)


def main() -> None:
    settings = get_settings()
    alembic = Config(str(ROOT / "alembic.ini"))
    step("database: dropping every table and migrating to the latest schema")
    command.downgrade(alembic, "base")
    command.upgrade(alembic, "head")

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
    print("Ready. Start the app with: make demo")


if __name__ == "__main__":
    main()
