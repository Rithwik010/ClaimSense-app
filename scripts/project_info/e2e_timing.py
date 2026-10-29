"""End-to-end time per claim, from upload to decision record (docs/PROJECT_INFO.md section 7.2).

Runs against a running API on its own disposable database (never the demo's: the database URL
must use port 5445, the docs measurement stack). For each round, the nine demo claims
(`demo/claims/`, in run-sheet order) are filed and processed by their provider, one after another,
as a client sees it: the intake request (JSON body; claim 02 as a digital PDF rendered from its
JSON, as `make e2e-api` does; claims 08 and 09 as the scanned PDFs) and then the process request,
which
answers once the decision record is saved. Upload to decision record = intake + process. Nothing
is reviewed or finalized. Between rounds the claim tables are emptied (claims, decision records,
audit events), so the same claims can be filed again.

The API's own log gives the stage times: the `claim_processed` lines (rules, context, model,
calculator and the whole processing) and the `request` lines (server time per route).

Output (git-ignored): `data/generated/project_info/e2e_timing.json`.

    uv run python -m scripts.project_info.e2e_timing --api http://127.0.0.1:8105 \
        --log data/generated/project_info/api-docs.log --rounds 3
"""

import argparse
import json
import statistics
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import text

from app.core.settings import get_settings
from app.db.session import get_engine
from app.domain.contracts import IntakeClaim
from app.intake.form_codec import to_form_values
from scripts.demo.e2e_api import CLAIMS, claim_json, login
from scripts.demo.users import FILED_BY
from training.generate.forms import render_pdf

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "generated" / "project_info" / "e2e_timing.json"
DOCS_DB_PORT = ":5445/"
RUN_SHEET = [
    ("01-approve-quick.json", "json"),
    ("02-pend-standard.json", "digital-pdf"),
    ("03-deny-full-override.json", "json"),
    ("04-partial-ncci.json", "json"),
    ("05-rule-deny-r15.json", "json"),
    ("06-reject-invalid-npi.json", "json"),
    ("07-duplicate-of-01.json", "json"),
    ("08-scanned-clean.pdf", "scan"),
    ("09-scanned-low-confidence.pdf", "scan"),
]


def empty_claim_tables() -> None:
    url = get_settings().database_url
    if DOCS_DB_PORT not in url:
        raise SystemExit(f"refusing to empty claim tables on {url}: not the docs database")
    with get_engine().begin() as conn:
        conn.execute(text("TRUNCATE audit_events, decision_records, claims CASCADE"))


def file_and_process(sessions: dict[str, Any], name: str, via: str) -> dict[str, Any]:
    api = sessions[FILED_BY[name]]
    t0 = time.perf_counter()
    if via == "json":
        filed = api.post("/v1/claims/intake", json=claim_json(name))
    elif via == "digital-pdf":
        pdf = render_pdf(to_form_values(IntakeClaim.model_validate(claim_json(name))))
        filed = api.post(
            "/v1/claims/intake/file", content=pdf, headers={"Content-Type": "application/pdf"}
        )
    else:
        filed = api.post("/v1/claims/intake/file", content=(CLAIMS / name).read_bytes())
    t1 = time.perf_counter()
    if filed.status_code != 201:
        raise SystemExit(f"{name}: intake answered {filed.status_code}: {filed.text[:200]}")
    body = filed.json()  # IntakeResult, or FiledWithErrors for a claim the rules will reject
    claim_id = body["claim"]["claim_id"] if "claim" in body else body["claim_id"]
    processed = api.post(f"/v1/claims/{claim_id}/process")
    t2 = time.perf_counter()
    if processed.status_code != 200:
        raise SystemExit(f"{name}: process answered {processed.status_code}")
    return {
        "claim": name,
        "claim_id": claim_id,
        "via": via,
        "source_format": body.get("source_format"),
        "status_for_provider": processed.json().get("status"),
        "intake_ms": round((t1 - t0) * 1000, 1),
        "process_ms": round((t2 - t1) * 1000, 1),
        "upload_to_record_ms": round((t2 - t0) * 1000, 1),
    }


def stats(values: list[float]) -> dict[str, float]:
    ordered = sorted(values)
    return {
        "n": len(ordered),
        "median": round(statistics.median(ordered), 1),
        "p95": round(ordered[int(0.95 * (len(ordered) - 1))], 1),
        "max": round(ordered[-1], 1),
    }


def from_log(log: Path) -> dict[str, Any]:
    processed, requests = [], {}
    for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.startswith("{"):
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("event") == "claim_processed":
            processed.append(row)
        elif row.get("event") == "request" and row.get("method") == "POST":
            requests.setdefault(row["route"], []).append(row["duration_ms"])
    stages = {}
    for stage in ("rules_ms", "context_ms", "model_ms", "calculator_ms", "duration_ms"):
        values = [r[stage] for r in processed if stage in r]
        if values:
            stages[stage] = stats(values)
    return {
        "claim_processed_lines": len(processed),
        "stages": stages,
        "server_ms_by_route": {k: stats(v) for k, v in requests.items() if "claims" in k},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--api", default="http://127.0.0.1:8105")
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--rounds", type=int, default=3)
    args = parser.parse_args()

    rows = []
    for n in range(1, args.rounds + 1):
        empty_claim_tables()
        sessions = {who: login(args.api, who) for who in sorted(set(FILED_BY.values()))}
        for name, via in RUN_SHEET:
            row = {"round": n, **file_and_process(sessions, name, via)}
            rows.append(row)
            print(json.dumps(row), flush=True)

    model_claims = [r for r in rows if r["status_for_provider"] == "IN_REVIEW"]
    rule_claims = [r for r in rows if r["status_for_provider"] != "IN_REVIEW"]
    by_path: dict[str, list[float]] = {}
    for r in rows:
        by_path.setdefault(r["via"], []).append(r["upload_to_record_ms"])
    summary = {
        "measured_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "api": args.api,
        "rounds": args.rounds,
        "claims": len(rows),
        "upload_to_record_ms": {
            "all": stats([r["upload_to_record_ms"] for r in rows]),
            "model_decided (in review)": stats([r["upload_to_record_ms"] for r in model_claims]),
            "rule_decided": stats([r["upload_to_record_ms"] for r in rule_claims]),
            **{f"path {k}": stats(v) for k, v in by_path.items()},
        },
        "intake_ms_by_path": {
            k: stats([r["intake_ms"] for r in rows if r["via"] == k]) for k in by_path
        },
        "per_claim_median_ms": {
            name: stats([r["upload_to_record_ms"] for r in rows if r["claim"] == name])
            for name, _ in RUN_SHEET
        },
        "api_log": from_log(args.log),
        "rows": rows,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "rows"}, indent=2))
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
