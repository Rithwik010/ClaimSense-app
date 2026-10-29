"""Row counts of every table and point counts of every Qdrant collection, on the docs measurement
stack (docs/PROJECT_INFO.md section 5.1), right after it was seeded from the repository's own
scripts (alembic, `app.db.seed` through `scripts.demo.reset`, `app.rag.knowledge`).

Refuses any database other than the docs stack's (port 5445), so it never reads the demo's.
Output (git-ignored): `data/generated/project_info/table_counts.json`.

    uv run python -m scripts.project_info.table_counts
"""

import json
from datetime import UTC, datetime
from pathlib import Path

from qdrant_client import QdrantClient
from sqlalchemy import inspect, text

from app.core.settings import get_settings
from app.db.session import get_engine

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "generated" / "project_info" / "table_counts.json"


def main() -> None:
    settings = get_settings()
    if ":5445/" not in settings.database_url:
        raise SystemExit(f"not the docs database: {settings.database_url}")
    engine = get_engine()
    tables = sorted(inspect(engine).get_table_names())
    with engine.connect() as conn:
        rows = {t: conn.execute(text(f'SELECT count(*) FROM "{t}"')).scalar_one() for t in tables}
    client = QdrantClient(url=settings.qdrant_url)
    points = {
        c.name: client.count(c.name, exact=True).count for c in client.get_collections().collections
    }
    report = {
        "measured_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "tables": rows,
        "total_rows": sum(rows.values()),
        "qdrant_points": points,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
