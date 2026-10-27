"""The 100 rendered v3 claims through the intake API (D-DOC-3). Report only.

The claims (claimsense-v3: scripts/demo/render_v3_claims.py; each a digital PDF, an image-only
scanned PDF, or its scanned pages as PNG files, 2 or 3 pages) go through the API's intake routes:
`POST /v1/claims/intake/file` for a PDF, `POST /v1/claims/intake/files` for the PNG pages, as a
provider, on a fresh database on the given Postgres server (migrated, the curated data seeded, one
provider login) with the given Qdrant, never the demo's (the configured servers are refused). Each
read is compared with its record's own claim (the claim the render was made from):

- fields: every claim box but the notes (the form's values, `to_form_values`), exactly;
- notes: the same words in the same order (exact), and the share of the record's words read in
  order (difflib on the word lists);
- intake time per claim, and per page for the scanned ones (OCR).

Split by format, and by pages (2 or 3). Writes data/generated/eval/multipage_intake.json.

    uv run python -m scripts.verify.multipage_intake --rendered <dir> --records <dir>
        [--database-url URL] [--qdrant-url URL]
"""

import argparse
import base64
import json
import statistics
import time
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.api.main import app
from app.auth.passwords import hash_password
from app.auth.tokens import create_token
from app.core.settings import Settings, get_settings
from app.db.models import User
from app.db.seed import seed_curated
from app.db.session import get_engine
from app.domain.contracts import IntakeClaim
from app.intake.form_codec import to_form_values

ROOT = Path(__file__).resolve().parents[2]
DATABASE = "claimsense_multipage_intake"
PROVIDER = (
    "provider-intake-check",
    "1234567893",
)  # a test provider login on the throwaway database


def fresh_database(server: str) -> str:
    url = make_url(server).set(database=DATABASE)
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{DATABASE}" WITH (FORCE)'))
        conn.execute(text(f'CREATE DATABASE "{DATABASE}"'))
    admin.dispose()
    rendered = url.render_as_string(hide_password=False)
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", rendered)
    config.attributes["configure_logger"] = False
    command.upgrade(config, "head")
    return rendered


def leaves(value: Any, prefix: str = "") -> dict[str, str]:  # noqa: ANN401
    if isinstance(value, dict):
        return {
            k: v for key, item in value.items() for k, v in leaves(item, f"{prefix}{key}.").items()
        }
    if isinstance(value, list):
        return {
            k: v for i, item in enumerate(value) for k, v in leaves(item, f"{prefix}{i}.").items()
        }
    return {prefix[:-1]: "" if value is None else str(value)}


def form_values(claim: dict[str, Any]) -> dict[str, str]:
    """The form's values of a claim read back; the claim's own fields when it is not a valid
    claim (a misread box)."""
    try:
        return to_form_values(IntakeClaim.model_validate(claim))
    except ValueError:
        return leaves(claim)


def compare(expected: IntakeClaim, read: dict[str, Any]) -> dict[str, Any]:
    want = {k: v for k, v in to_form_values(expected).items() if k != "clinical_notes"}
    got = form_values(read)
    wrong = sorted(k for k, v in want.items() if got.get(k) != v)
    words, read_words = (
        expected.clinical_notes.split(),
        str(read.get("clinical_notes") or "").split(),
    )
    matcher = SequenceMatcher(a=words, b=read_words, autojunk=False)
    in_order = sum(block.size for block in matcher.get_matching_blocks()) / max(1, len(words))
    return {
        "fields": len(want),
        "fields_wrong": wrong,
        "notes_exact": words == read_words,
        "notes_words_in_order": round(in_order, 4),
        "notes_words": len(words),
        "notes_words_read": len(read_words),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--rendered", type=Path, required=True)
    parser.add_argument("--records", type=Path, required=True)
    parser.add_argument(
        "--database-url", default="postgresql+psycopg://claimsense:claimsense@127.0.0.1:5443/x"
    )
    parser.add_argument("--qdrant-url", default="http://127.0.0.1:6343")
    args = parser.parse_args()
    configured = get_settings()
    if make_url(args.database_url).port == make_url(configured.database_url).port:
        raise SystemExit("refusing the configured (demo) Postgres server: pass another")
    if args.qdrant_url.rstrip("/") == configured.qdrant_url.rstrip("/"):
        raise SystemExit("refusing the configured (demo) Qdrant: pass another")
    url = fresh_database(args.database_url)
    engine = create_engine(url)
    with Session(engine) as session:
        seed_curated(session)
        session.add(
            User(
                username=PROVIDER[0],
                display_name="Intake check",
                password_hash=hash_password("not used: a token is issued directly"),
                role="provider",
                provider_id=PROVIDER[1],
            )
        )
        session.commit()
    secret = "intake-check-" + base64.b16encode(PROVIDER[1].encode()).decode()
    settings = Settings(database_url=url, qdrant_url=args.qdrant_url, secret_key=secret)
    app.dependency_overrides[get_engine] = lambda: engine
    app.dependency_overrides[get_settings] = lambda: settings
    headers = {"Authorization": f"Bearer {create_token(PROVIDER[0], 'provider', secret)}"}
    expected: dict[str, IntakeClaim] = {}
    for path in args.records.glob("*_inputs.jsonl"):
        for line in path.open(encoding="utf-8"):
            row = json.loads(line)
            expected[row["record_id"]] = IntakeClaim.model_validate(row["claim"])
    index = json.loads((args.rendered / "index.json").read_text())["claims"]
    rows = []
    with TestClient(app) as client:
        for claim in index:
            files = [args.rendered / f for f in claim["files"]]
            started = time.perf_counter()
            if claim["format"] == "png":
                body = {
                    "files": [
                        {
                            "name": f.name,
                            "content_base64": base64.b64encode(f.read_bytes()).decode(),
                        }
                        for f in files
                    ]
                }
                reply = client.post("/v1/claims/intake/files", json=body, headers=headers)
            else:
                reply = client.post(
                    "/v1/claims/intake/file",
                    content=files[0].read_bytes(),
                    headers=headers | {"X-File-Name": files[0].name},
                )
            seconds = time.perf_counter() - started
            row = {
                "record_id": claim["record_id"],
                "format": claim["format"],
                "pages": claim["pages"],
                "status": reply.status_code,
                "seconds": round(seconds, 2),
            }
            if reply.status_code == 201:
                answer = reply.json()
                read = answer.get("claim") or answer.get("received") or {}
                row |= compare(expected[claim["record_id"]], read)
                row["source_format"] = answer.get("source_format")
            else:
                row["error"] = reply.text[:300]
            rows.append(row)
            print(json.dumps({k: v for k, v in row.items() if k != "fields_wrong"}), flush=True)
    app.dependency_overrides.clear()
    groups: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        groups[row["format"]].append(row)
        groups[f"{row['format']}, {row['pages']} pages"].append(row)
        groups["all"].append(row)
    summary = {}
    for name, items in sorted(groups.items()):
        read = [r for r in items if r["status"] == 201]
        fields = sum(r["fields"] for r in read)
        scanned_pages = [r["seconds"] / r["pages"] for r in items if r["format"] != "digital-pdf"]
        summary[name] = {
            "claims": len(items),
            "filed": len(read),
            "refused": [
                (r["record_id"], r.get("error", "")[:120]) for r in items if r["status"] != 201
            ],
            "fields_exact": round(
                1 - sum(len(r["fields_wrong"]) for r in read) / max(1, fields), 4
            ),
            "claims_every_field_exact": sum(not r["fields_wrong"] for r in read),
            "notes_exact": sum(r["notes_exact"] for r in read),
            "notes_words_in_order_mean": round(
                statistics.mean(r["notes_words_in_order"] for r in read), 4
            )
            if read
            else None,
            "notes_words_in_order_min": min(
                (r["notes_words_in_order"] for r in read), default=None
            ),
            "seconds_per_claim_median": round(statistics.median(r["seconds"] for r in items), 2),
            "seconds_per_scanned_page_median": round(statistics.median(scanned_pages), 2)
            if scanned_pages
            else None,
            "seconds_per_scanned_page_max": round(max(scanned_pages), 2) if scanned_pages else None,
            "fields_most_often_wrong": sorted(
                {f for r in read for f in r["fields_wrong"]},
                key=lambda f: -sum(f in r["fields_wrong"] for r in read),
            )[:8],
        }
    out = ROOT / "data/generated/eval/multipage_intake.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"summary": summary, "claims": rows}, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
