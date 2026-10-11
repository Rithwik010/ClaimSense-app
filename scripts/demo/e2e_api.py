"""`make e2e-api`: an end-to-end check of the running stack through the API alone (no UI).

Run it right after `make demo-reset` with the API up on :8000 (`make demo` or `make demo-up`):
each demo claim can be filed only once. It checks:

1. every endpoint of INSTRUCTIONS.md §8.10 (and the claim list, file intake, explanation and
   metrics endpoints the web app uses);
2. all nine demo claims (demo/claims/) from intake to final status: JSON body, JSON file, digital
   PDF (claim 02, rendered from its JSON), scanned PDF; ACCEPT, OVERRIDE with a reason,
   finalization, accumulator and visit-usage updates, the audit trail in order;
3. for each claim, that the text explanation matches the decision record
   (tests/explain_support.py), that the explanation shown (text and HTML) is the one audited as
   EXPLANATION_BUILT for the latest record (its SHA-256), and that the record names the rules,
   model, prompt and policy versions where the claim reached them;
4. bad inputs and failures: wrong file type, empty file, corrupted PDF, JSON with a missing
   field, a duplicate claim ID, a provider calling review, and Ollama stopped: each gives a clear
   4xx or a clear claim status, never a 5xx, and no claim is lost;
5. recovery after Ollama comes back: a second API on :8001 reaches Ollama through a local port
   that refuses connections (Ollama stopped: 503, the claim stays RECEIVED with nothing
   half-written), then passes them through to the running Ollama (Ollama started; the demo
   model stays loaded). The same API process then processes the same claim ID normally, with no
   duplicate rejection, and after review its audit trail holds every stage once, in order;
6. that the CARC/RARC codes come back, with official descriptions, on the DENY and REJECT lines
   and not on pended ones (D-CARC-2);
7. with --log (repeatable), that each log holds no patient name, street address, date of birth
   or clinical note text of any demo claim as stored at intake (INSTRUCTIONS.md §8.9);
   --privacy-only runs just that check (the e2e run's own output is checked after the run).

    uv run python -m scripts.demo.e2e_api [--log data/generated/logs/api.log] [--privacy-only]
"""

import argparse
import hashlib
import json
import os
import socket
import socketserver
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx

from app.core.settings import get_settings
from app.domain.contracts import DecisionRecord, IntakeClaim
from app.intake.form_codec import to_form_values
from tests.explain_support import mismatches
from training.generate.forms import render_pdf

ROOT = Path(__file__).resolve().parents[2]
CLAIMS = ROOT / "demo" / "claims"
API = "http://localhost:8000"
DEAD_API_PORT = 8001
REVIEWER = {"X-Role": "reviewer"}
PROVIDER = {"X-Role": "provider"}
MODEL_EVENTS = [
    "INTAKE_COMPLETED",
    "RULES_EVALUATED",
    "CONTEXT_ASSEMBLED",
    "SLM_RECOMMENDED",
    "CALCULATED",
]
REVIEWED_EVENTS = [
    *MODEL_EVENTS,
    "EXPLANATION_BUILT",
    "REVIEW_OPENED",
    "REVIEW_ACCEPTED",
    "FINALIZED",
    "EXPLANATION_BUILT",
]


class Check:
    def __init__(self) -> None:
        self.failed: list[str] = []
        self.passed = 0

    def __call__(self, ok: bool, what: str) -> bool:
        if ok:
            self.passed += 1
        else:
            self.failed.append(what)
        print(f"  {'ok  ' if ok else 'FAIL'} {what}", flush=True)
        return ok


def no_5xx(check: Check, response: httpx.Response, what: str) -> httpx.Response:
    """Never a 500 or a bare 5xx; a 503 that says which service is down is a clear answer."""
    detail = ""
    if response.status_code >= 500:
        try:
            detail = str(response.json().get("detail", ""))
        except ValueError:
            detail = ""
    clear = response.status_code < 500 or (response.status_code == 503 and bool(detail))
    check(clear, f"{what}: answered {response.status_code}, no server error")
    return response


def subsequence(events: list[str], wanted: list[str]) -> bool:
    it = iter(events)
    return all(any(e == w for e in it) for w in wanted)


def claim_json(name: str) -> dict[str, Any]:
    return json.loads((CLAIMS / name).read_text(encoding="utf-8"))


def file_and_process(
    check: Check, api: httpx.Client, name: str, claim_id: str, via: str
) -> dict[str, Any]:
    """File a demo claim the given way and process it; returns the decision record."""
    if via == "json-body":
        filed = api.post("/v1/claims/intake", json=claim_json(name))
    elif via == "digital-pdf":
        pdf = render_pdf(to_form_values(IntakeClaim.model_validate(claim_json(name))))
        filed = api.post(
            "/v1/claims/intake/file", content=pdf, headers={"Content-Type": "application/pdf"}
        )
        check(
            filed.json().get("source_format") == "DIGITAL_PDF", f"{claim_id}: read as a digital PDF"
        )
    else:
        filed = api.post("/v1/claims/intake/file", content=(CLAIMS / name).read_bytes())
    no_5xx(check, filed, f"{claim_id}: intake ({via})")
    check(filed.status_code == 201, f"{claim_id}: filed (201)")
    processed = no_5xx(check, api.post(f"/v1/claims/{claim_id}/process"), f"{claim_id}: process")
    check(processed.status_code == 200, f"{claim_id}: processed (200)")
    return processed.json()


def review(api: httpx.Client, claim_id: str, overrides: list[dict] | None = None) -> httpx.Response:
    api.post(
        f"/v1/claims/{claim_id}/review/open", json={"reviewer_id": "reviewer-e2e"}, headers=REVIEWER
    )
    return api.post(
        f"/v1/claims/{claim_id}/review",
        json={
            "claim_id": claim_id,
            "reviewer_id": "reviewer-e2e",
            "action": "OVERRIDE" if overrides else "ACCEPT",
            "line_overrides": overrides or [],
            "timestamp": "2026-10-11T10:00:00Z",
        },
        headers=REVIEWER,
    )


def finalized_payload(api: httpx.Client, claim_id: str) -> dict[str, Any]:
    events = api.get(f"/v1/claims/{claim_id}/audit").json()
    return next(e["payload"] for e in events if e["event_type"] == "FINALIZED")


def explained(check: Check, api: httpx.Client, claim_id: str) -> None:
    record = DecisionRecord.model_validate(api.get(f"/v1/claims/{claim_id}").json()["record"])
    text = no_5xx(
        check,
        api.get(f"/v1/claims/{claim_id}/explanation", params={"format": "text"}),
        f"{claim_id}: explanation",
    )
    check(
        mismatches(record, text.text) == [],
        f"{claim_id}: every amount and reason of the explanation matches the record",
    )
    versions = record.versions
    check(
        bool(versions.rules_version),
        f"{claim_id}: rules version recorded ({versions.rules_version})",
    )
    if record.slm_output is not None or record.output_errors:
        check(
            bool(versions.model_name and versions.prompt_version and versions.policy_versions),
            f"{claim_id}: model, prompt and policy versions recorded"
            f" ({versions.model_name}, {versions.prompt_version})",
        )
    events = api.get(f"/v1/claims/{claim_id}/audit").json()
    built = [e["payload"] for e in events if e["event_type"] == "EXPLANATION_BUILT"]
    shown = {
        fmt: api.get(f"/v1/claims/{claim_id}/explanation", params={"format": fmt}).text
        for fmt in ("text", "html")
    }
    check(
        bool(built)
        and all(
            hashlib.sha256(shown[fmt].encode()).hexdigest() == built[-1][f"{fmt}_sha256"]
            for fmt in shown
        ),
        f"{claim_id}: EXPLANATION_BUILT audited ({len(built)}x); the explanation shown (text and"
        " HTML) is the one built for the latest record",
    )
    ids = [e["id"] for e in events]
    check(
        ids == sorted(ids) and events[0]["event_type"] == "INTAKE_COMPLETED",
        f"{claim_id}: audit trail in order",
    )


class OllamaSwitch:
    """Ollama as the second API sees it: a local port that refuses connections until `start()`
    (Ollama stopped), then passes each connection through to the running Ollama (Ollama started).
    The real Ollama keeps the demo model loaded throughout."""

    def __init__(self) -> None:
        url = urlsplit(get_settings().ollama_url)
        self.target = (url.hostname or "localhost", url.port or 11434)
        with socket.socket() as probe:  # a free port; nothing listens on it until start()
            probe.bind(("127.0.0.1", 0))
            self.port = probe.getsockname()[1]
        self.url = f"http://127.0.0.1:{self.port}"
        self._server: socketserver.ThreadingTCPServer | None = None

    def start(self) -> None:
        target = self.target

        def pump(source: socket.socket, sink: socket.socket) -> None:
            try:
                while data := source.recv(65536):
                    sink.sendall(data)
            except OSError:
                pass
            finally:
                try:
                    sink.shutdown(socket.SHUT_WR)
                except OSError:
                    pass

        class Pipe(socketserver.BaseRequestHandler):
            def handle(self) -> None:
                with socket.create_connection(target) as upstream:
                    back = threading.Thread(target=pump, args=(upstream, self.request), daemon=True)
                    back.start()
                    pump(self.request, upstream)
                    back.join()

        socketserver.ThreadingTCPServer.allow_reuse_address = True
        self._server = socketserver.ThreadingTCPServer(("127.0.0.1", self.port), Pipe)
        self._server.daemon_threads = True
        threading.Thread(target=self._server.serve_forever, daemon=True).start()

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()


def second_api(ollama_url: str) -> subprocess.Popen:
    env = dict(os.environ, OLLAMA_URL=ollama_url)
    env.setdefault("MODEL_NAME", "claimsense-decision:v2")
    server = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.api.main:app", "--port", str(DEAD_API_PORT)],
        cwd=ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(60):
        try:
            httpx.get(f"http://localhost:{DEAD_API_PORT}/health", timeout=2)
            return server
        except httpx.HTTPError:
            time.sleep(0.5)
    server.terminate()
    raise SystemExit("the second API (Ollama stopped) did not start")


def privacy(check: Check, api: httpx.Client, log: Path) -> None:
    """No patient name, street address, date of birth or clinical note text of any demo claim (as
    stored at intake) in the log."""
    text = log.read_text(encoding="utf-8", errors="replace")
    for n in range(1, 10):
        claim_id = f"CLM-DEMO-{n:02d}"
        response = api.get(f"/v1/claims/{claim_id}")
        if response.status_code != 200:
            continue
        claim = response.json()["received"]
        patient = claim.get("patient") or {}
        address = patient.get("address") or {}
        secrets = {
            "patient name": " ".join(
                part for part in (patient.get("first_name"), patient.get("last_name")) if part
            ),
            "last name": patient.get("last_name", ""),
            "street address": address.get("line1", ""),
            "date of birth": patient.get("date_of_birth", ""),
            "clinical note text": (claim.get("clinical_notes") or "")[:40],
        }
        found = [what for what, value in secrets.items() if len(value) >= 4 and value in text]
        check(
            not found,
            f"{log.name} holds no patient name, address, birth date or note text of {claim_id}"
            + (f" (found: {found})" if found else ""),
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--log",
        type=Path,
        action="append",
        default=[],
        help="a log to check for patient data (repeat)",
    )
    parser.add_argument("--privacy-only", action="store_true", help="only check the logs")
    args = parser.parse_args()
    check = Check()
    api = httpx.Client(base_url=API, timeout=300)
    if args.privacy_only:
        for log in args.log:
            print(f"Privacy of {log}")
            privacy(check, api, log)
        report(check)
        return

    print("Endpoints")
    health = api.get("/health").json()
    check(
        all(health[s]["ok"] for s in ("database", "qdrant", "ollama")),
        "GET /health: database, Qdrant and Ollama reachable",
    )
    check(api.get("/v1/plans/PLN-PPO-GOLD").status_code == 200, "GET /v1/plans/{plan_id}")
    check(
        api.get("/v1/plans/PLN-NOPE").status_code == 404,
        "GET /v1/plans/{plan_id}: unknown plan is 404",
    )
    check(
        api.get("/v1/claims/CLM-NOPE-1").status_code == 404,
        "GET /v1/claims/{id}: unknown claim is 404",
    )
    check(api.get("/v1/metrics/evaluation").status_code == 200, "GET /v1/metrics/evaluation")

    print("Ollama stopped, then started again (a second API on :8001)")
    switch = OllamaSwitch()
    server = second_api(switch.url)
    try:
        second = httpx.Client(base_url=f"http://localhost:{DEAD_API_PORT}", timeout=300)
        pdf = render_pdf(
            to_form_values(IntakeClaim.model_validate(claim_json("02-pend-standard.json")))
        )
        second.post(
            "/v1/claims/intake/file", content=pdf, headers={"Content-Type": "application/pdf"}
        )
        down = no_5xx(
            check, second.post("/v1/claims/CLM-DEMO-02/process"), "process with Ollama stopped"
        )
        check(
            down.status_code == 503,
            f"process with Ollama stopped: {down.status_code} {down.json().get('detail', '')[:80]}",
        )
        kept = second.get("/v1/claims/CLM-DEMO-02").json()
        check(
            kept["status"] == "RECEIVED",
            "the claim is not lost: still RECEIVED, ready to process again",
        )
        events = [e["event_type"] for e in second.get("/v1/claims/CLM-DEMO-02/audit").json()]
        check(
            events == ["INTAKE_COMPLETED"],
            f"nothing half-written by the failed run: audit {events}",
        )

        switch.start()
        again = no_5xx(
            check,
            second.post("/v1/claims/CLM-DEMO-02/process"),
            "CLM-DEMO-02: process again after Ollama started (same API process)",
        )
        record = again.json()
        check(
            again.status_code == 200 and record.get("claim_id") == "CLM-DEMO-02",
            f"CLM-DEMO-02: processed on the same claim ID ({again.status_code})",
        )
        check(
            record.get("status") == "AWAITING_REVIEW" and record.get("review_tier") == "STANDARD",
            "CLM-DEMO-02 (digital PDF): finished normally, awaiting standard review",
        )
        failed = [
            r["reason_code"] for r in record["rules_outcome"]["rule_results"] if not r["passed"]
        ]
        check(
            "RJ_DUPLICATE" not in failed and record.get("status") != "REJECTED",
            "CLM-DEMO-02: no duplicate rejection of its own earlier attempt",
        )
        twice = second.post("/v1/claims/CLM-DEMO-02/process")
        check(twice.status_code == 409, f"CLM-DEMO-02: not processed twice ({twice.status_code})")
    finally:
        server.terminate()
        server.wait(timeout=30)
        switch.stop()

    print("Demo claims")
    r = file_and_process(check, api, "01-approve-quick.json", "CLM-DEMO-01", "json-body")
    check(
        r["status"] == "AWAITING_REVIEW" and r["review_tier"] == "QUICK",
        "CLM-DEMO-01: awaiting quick review",
    )
    check(
        review(api, "CLM-DEMO-01").json().get("status") == "FINAL_APPROVED",
        "CLM-DEMO-01: ACCEPT -> FINAL_APPROVED",
    )
    payload = finalized_payload(api, "CLM-DEMO-01")
    visits = payload["visit_usage"]["REHAB_THERAPY"]
    check(
        visits["after"] == visits["before"] + 1,
        f"CLM-DEMO-01: therapy visits {visits['before']} -> {visits['after']}",
    )
    check(
        payload["accumulators"]["after"] != payload["accumulators"]["before"],
        "CLM-DEMO-01: accumulators updated",
    )
    events = [e["event_type"] for e in api.get("/v1/claims/CLM-DEMO-01/audit").json()]
    check(
        subsequence(events, [*MODEL_EVENTS, "REVIEW_OPENED", "FINALIZED"]),
        f"CLM-DEMO-01: full audit trail in order ({len(events)} events)",
    )

    check(
        review(api, "CLM-DEMO-02").json().get("status") == "FINAL_PENDED",
        "CLM-DEMO-02: ACCEPT -> FINAL_PENDED",
    )
    events = [e["event_type"] for e in api.get("/v1/claims/CLM-DEMO-02/audit").json()]
    check(
        events == REVIEWED_EVENTS,
        "CLM-DEMO-02: complete audit trail after the recovery, each stage once and the"
        f" explanation built for the recommendation and the final decision ({events})",
    )

    r = file_and_process(check, api, "03-deny-full-override.json", "CLM-DEMO-03", "json-file")
    check(
        r["review_tier"] == "FULL" and r["line_decisions"][0]["decision"] == "DENY",
        "CLM-DEMO-03: model DENY, full review",
    )
    no_reason = review(api, "CLM-DEMO-03", [{"line_no": 1, "decision": "APPROVE", "reason": ""}])
    check(
        no_reason.status_code == 422,
        f"CLM-DEMO-03: an override without a reason is refused ({no_reason.status_code})",
    )
    final = review(
        api,
        "CLM-DEMO-03",
        [{"line_no": 1, "decision": "APPROVE", "reason": "The note documents the criterion."}],
    ).json()
    check(
        final.get("status") == "FINAL_APPROVED" and final["amounts"]["totals"]["allowed_cents"] > 0,
        "CLM-DEMO-03: OVERRIDE -> FINAL_APPROVED, amounts recomputed",
    )

    r = file_and_process(check, api, "04-partial-ncci.json", "CLM-DEMO-04", "json-file")
    check(
        any(d["source"] == "RULE" and d["decision"] == "DENY" for d in r["line_decisions"]),
        "CLM-DEMO-04: a line denied by NCCI",
    )
    check(
        review(api, "CLM-DEMO-04").json().get("status") == "FINAL_PARTIAL",
        "CLM-DEMO-04: ACCEPT -> FINAL_PARTIAL",
    )

    r = file_and_process(check, api, "05-rule-deny-r15.json", "CLM-DEMO-05", "json-file")
    check(r["status"] == "DENIED_BY_RULE", "CLM-DEMO-05: DENIED_BY_RULE (R15)")
    check(
        review(api, "CLM-DEMO-05").status_code == 409,
        "CLM-DEMO-05: a rule outcome cannot be reviewed (409)",
    )
    codes = api.get("/v1/claims/CLM-DEMO-05").json()["adjustments"]
    check(
        bool(codes) and codes[0]["codes"][0]["code"] == "11" and codes[0]["billing_article"],
        "CLM-DEMO-05: CARC 11 with its billing article",
    )

    r = file_and_process(check, api, "06-reject-invalid-npi.json", "CLM-DEMO-06", "json-file")
    check(r["status"] == "REJECTED", "CLM-DEMO-06: invalid NPI -> REJECTED")
    r = file_and_process(check, api, "07-duplicate-of-01.json", "CLM-DEMO-07", "json-file")
    reasons = [x["reason_code"] for x in r["rules_outcome"]["rule_results"] if not x["passed"]]
    check(
        r["status"] == "REJECTED" and "RJ_DUPLICATE" in reasons,
        "CLM-DEMO-07: duplicate -> REJECTED RJ_DUPLICATE",
    )
    r = file_and_process(check, api, "08-scanned-clean.pdf", "CLM-DEMO-08", "scanned")
    check(r["status"] == "AWAITING_REVIEW", "CLM-DEMO-08 (scanned): awaiting review")
    r = file_and_process(check, api, "09-scanned-low-confidence.pdf", "CLM-DEMO-09", "scanned")
    reasons = [x["reason_code"] for x in r["rules_outcome"]["rule_results"] if not x["passed"]]
    check(
        r["status"] == "REJECTED" and "RJ_LOW_CONFIDENCE_FIELD" in reasons,
        "CLM-DEMO-09 (scanned): REJECTED RJ_LOW_CONFIDENCE_FIELD",
    )

    print("Explanations, versions, audit trails")
    for n in range(1, 10):
        explained(check, api, f"CLM-DEMO-{n:02d}")

    print("CARC/RARC codes on DENY and REJECT lines (D-CARC-2)")
    expected = {
        "CLM-DEMO-04": (2, "DN_NCCI_BUNDLED", ["236"]),
        "CLM-DEMO-05": (1, "DN_DX_NOT_SUPPORTED", ["11", "N115"]),
        "CLM-DEMO-06": (None, "RJ_INVALID_NPI", ["16", "N257"]),
        "CLM-DEMO-07": (None, "RJ_DUPLICATE", ["18"]),
        "CLM-DEMO-09": (None, "RJ_LOW_CONFIDENCE_FIELD", ["16", "MA130"]),
    }
    for claim_id, (line_no, reason, codes) in expected.items():
        found = [
            a
            for a in api.get(f"/v1/claims/{claim_id}").json()["adjustments"]
            if a["reason_code"] == reason and (line_no is None or a["line_no"] == line_no)
        ]
        got = [c["code"] for c in found[0]["codes"]] if found else []
        described = bool(found) and all(
            c["description"] and "Usage:" not in c["description"] for c in found[0]["codes"]
        )
        check(
            got == codes and described,
            f"{claim_id}: {reason} -> {' + '.join(got) or 'none'} with official descriptions",
        )
    pended = api.get("/v1/claims/CLM-DEMO-02").json()["adjustments"]
    check(pended == [], "CLM-DEMO-02 (pended): no CARC/RARC codes")
    article = api.get("/v1/claims/CLM-DEMO-05").json()["adjustments"][0]
    check(
        bool(article["billing_article"] and article["lcds"]),
        f"CLM-DEMO-05: billing article {article['billing_article']},"
        f" LCD {', '.join(article['lcds'])}",
    )

    print("Queue, list and roles")
    queue = api.get("/v1/review/queue", headers=REVIEWER).json()
    check(
        [q["claim_id"] for q in queue] == ["CLM-DEMO-08"],
        "GET /v1/review/queue: only CLM-DEMO-08 still waits",
    )
    check(
        api.get("/v1/review/queue", headers=PROVIDER).status_code == 403,
        "a provider cannot see the review queue (403)",
    )
    check(review_as_provider(api).status_code == 403, "a provider cannot review a claim (403)")
    listed = {c["claim_id"] for c in api.get("/v1/claims").json()}
    check({f"CLM-DEMO-{n:02d}" for n in range(1, 10)} <= listed, "GET /v1/claims: no claim lost")

    print("Bad inputs")
    for what, body, headers in (
        ("wrong file type", b"just some text, not a claim", {"Content-Type": "text/plain"}),
        ("empty file", b"", {}),
        ("corrupted PDF", b"%PDF-1.7\nbroken", {"Content-Type": "application/pdf"}),
    ):
        response = no_5xx(
            check, api.post("/v1/claims/intake/file", content=body, headers=headers), what
        )
        check(response.status_code == 422, f"{what}: 422 {response.json().get('detail', '')[:70]}")
    missing = dict(claim_json("01-approve-quick.json"), claim_id="CLM-E2E-MISSING")
    missing["service_lines"] = [dict(missing["service_lines"][0])]
    missing["service_lines"][0].pop("procedure_code")
    filed = no_5xx(check, api.post("/v1/claims/intake", json=missing), "JSON with a missing field")
    check(
        filed.status_code == 201 and filed.json()["contract_errors"],
        "JSON with a missing field: filed with its contract errors",
    )
    status = api.post("/v1/claims/CLM-E2E-MISSING/process").json()["status"]
    check(status == "REJECTED", f"JSON with a missing field: {status} after processing")
    no_id = no_5xx(
        check,
        api.post("/v1/claims/intake", json={"member_id": "MBR-000001"}),
        "JSON without a claim ID",
    )
    check(no_id.status_code == 422, "JSON without a claim ID: 422")
    again = no_5xx(
        check,
        api.post("/v1/claims/intake", json=claim_json("01-approve-quick.json")),
        "duplicate claim ID",
    )
    check(again.status_code == 409, "the same claim ID twice: 409")

    for log in args.log:
        print(f"Privacy of {log}")
        privacy(check, api, log)
    report(check)


def report(check: Check) -> None:
    print(f"\n{check.passed} checks passed, {len(check.failed)} failed")
    for what in check.failed:
        print(f"  FAIL {what}")
    if check.failed:
        raise SystemExit(1)


def review_as_provider(api: httpx.Client) -> httpx.Response:
    return api.post(
        "/v1/claims/CLM-DEMO-08/review",
        json={
            "claim_id": "CLM-DEMO-08",
            "reviewer_id": "x",
            "action": "ACCEPT",
            "timestamp": "2026-10-11T10:00:00Z",
        },
        headers=PROVIDER,
    )


if __name__ == "__main__":
    main()
