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
   field, a duplicate claim ID, and Ollama stopped: each gives a clear 4xx or a clear claim
   status, never a 5xx, and no claim is lost;
4b. logins (D-AUTH-1): it logs in as every demo user (passwords from .env, `make demo-users`);
   each claim is filed and processed by its provider (scripts/demo/users.py FILED_BY) and reviewed
   by reviewer1; not logged in is 401, another role's endpoint 403, another provider's claim 404;
   a provider sees IN_REVIEW until the claim is final;
5. recovery after Ollama comes back: a second API on :8001 reaches Ollama through a local port
   that refuses connections (Ollama stopped: 503, the claim stays RECEIVED with nothing
   half-written), then passes them through to the running Ollama (Ollama started; the demo
   model stays loaded). The same API process then processes the same claim ID normally, with no
   duplicate rejection, and after review its audit trail holds every stage once, in order;
6. that the CARC/RARC codes come back, with official descriptions, on the DENY and REJECT lines
   and not on pended ones (D-CARC-2);
7. with --log (repeatable), that each log holds no patient name, street address, date of birth
   or clinical note text of any demo claim as stored at intake (INSTRUCTIONS.md §8.9), and no
   part of any stored original file (D-DOC-1); --privacy-only runs just that check (the e2e
   run's own output is checked after the run);
8. D-DOC-1 and D-UI-6 for the nine demo claims: each original file is served (to its provider,
   reviewers and admins; 404 to another provider) with its type and the SHA-256 of the upload; the
   provider's explanation appears only once the claim is final and holds no rule IDs or internal
   codes; claims not paid as billed carry their reason texts; the reviewer's summary names the
   outcome the record gives; and each paid claim's billing adds up to the cent;
9. D-DOC-2: a claim filed from its form's two pages as two scanned images (CLM-E2E-PAGES, demo
   claim 01 three weeks later): one claim, its note read from page 2, both files kept in page
   order and served with their hashes; the same pages in the wrong order are refused, keeping
   nothing;
10. D-CHK-1, D-FIX-1, D-EOB-1, D-OBS-1: a digital PDF with a misread billing NPI (CLM-E2E-FIX,
   demo claim 01 four weeks later): the check says it would be rejected and names that box only;
   a bad correction is refused, a good one is audited as FIELD_CORRECTED with the request ID of
   its response; the check is then ready, with the line's coverage criteria; processed, accepted
   and finalized, its patient EOB matches the calculator to the cent, with the year to date; a
   rejected claim has no EOB, a claim the rules denied has one without amounts; every audit event
   of a request carries its X-Request-ID, and the rules event names the reference data versions.

    uv run python -m scripts.demo.e2e_api [--log data/generated/logs/api.log] [--privacy-only]
"""

import argparse
import base64
import hashlib
import json
import os
import re
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
from app.domain.contracts import ClaimStatus, DecisionRecord, IntakeClaim
from app.explain.reasons import REASONED_OUTCOMES, claim_outcome
from app.intake.form_codec import to_form_values
from scripts.demo.claim_image import digital_pdf, images
from scripts.demo.users import FILED_BY, USERS, password
from tests.explain_support import mismatches
from training.generate.forms import render_pdf

ROOT = Path(__file__).resolve().parents[2]
CLAIMS = ROOT / "demo" / "claims"
API = "http://localhost:8000"
DEAD_API_PORT = 8001
REVIEWER_ID = "reviewer1"  # the logged-in reviewer: review actions must name them
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


def login(base_url: str, username: str) -> httpx.Client:
    """A client logged in as a demo user (the session cookie stays in its cookie jar)."""
    client = httpx.Client(base_url=base_url, timeout=300)
    response = client.post(
        "/v1/auth/login", json={"username": username, "password": password(username)}
    )
    if response.status_code != 200:
        raise SystemExit(f"cannot log in as {username} ({response.status_code}): make demo-users")
    return client


UPLOADED: dict[str, tuple[bytes, str]] = {}  # claim ID -> (the bytes filed, their content type)
HIDDEN = re.compile(
    r"\bR(?:0[1-9]|1[0-9]|20)\b|\bDUP\b|\b(?:RJ|DN|PD|RV)_[A-Z0-9_]+\b"
    r"|\bMODEL_OUTPUT_INVALID\b|\bPOL-[A-Z]+-[0-9]{3}\.c[0-9]+\b"
)
TYPES = {".json": "application/json", ".pdf": "application/pdf"}


def file_and_process(
    check: Check, sessions: dict[str, httpx.Client], name: str, claim_id: str, via: str
) -> dict[str, Any]:
    """File a demo claim the given way and process it as its provider; returns the decision
    record as the reviewer reads it (the provider's answer holds no recommendation)."""
    filer = FILED_BY[name]
    api = sessions[filer]
    named = {"X-File-Name": name}
    if via == "json-body":
        body = (CLAIMS / name).read_bytes()
        UPLOADED[claim_id] = (body, "application/json")
        filed = api.post(
            "/v1/claims/intake",
            content=body,
            headers={"Content-Type": "application/json", **named},
        )
    elif via == "digital-pdf":
        pdf = render_pdf(to_form_values(IntakeClaim.model_validate(claim_json(name))))
        UPLOADED[claim_id] = (pdf, "application/pdf")
        filed = api.post(
            "/v1/claims/intake/file",
            content=pdf,
            headers={"Content-Type": "application/pdf", **named},
        )
        check(
            filed.json().get("source_format") == "DIGITAL_PDF", f"{claim_id}: read as a digital PDF"
        )
    else:
        body = (CLAIMS / name).read_bytes()
        UPLOADED[claim_id] = (body, TYPES[Path(name).suffix])
        filed = api.post("/v1/claims/intake/file", content=body, headers=named)
    no_5xx(check, filed, f"{claim_id}: intake ({via}) by {filer}")
    check(filed.status_code == 201, f"{claim_id}: filed (201) by {filer}")
    processed = no_5xx(check, api.post(f"/v1/claims/{claim_id}/process"), f"{claim_id}: process")
    check(processed.status_code == 200, f"{claim_id}: processed (200)")
    view = processed.json()
    record = sessions[REVIEWER_ID].get(f"/v1/claims/{claim_id}").json()["record"]
    shown = view.get("explanation") is not None
    check(
        shown == view.get("final")
        and (view["status"] == "IN_REVIEW") != shown
        and "record" not in view,
        f"{claim_id}: {filer} sees {view['status']}"
        + (" with the decision (final)" if shown else ", no recommendation"),
    )
    return record


def review(api: httpx.Client, claim_id: str, overrides: list[dict] | None = None) -> httpx.Response:
    api.post(f"/v1/claims/{claim_id}/review/open", json={"reviewer_id": REVIEWER_ID})
    return api.post(
        f"/v1/claims/{claim_id}/review",
        json={
            "claim_id": claim_id,
            "reviewer_id": REVIEWER_ID,
            "action": "OVERRIDE" if overrides else "ACCEPT",
            "line_overrides": overrides or [],
            "timestamp": "2026-10-11T10:00:00Z",
        },
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


def billing_errors(billing: dict[str, Any]) -> list[str]:
    """Billed minus the reductions to the allowed amount is the allowed amount; the allowed amount
    is what the plan, the patient and another plan pay; per line and in total, to the cent."""
    to_allowed = ("allowed_amount", "out_of_network", "not_paid")
    found = []
    cut_total = 0
    for line in billing["lines"]:
        cut = sum(r["amount_cents"] for r in line["reductions"] if r["kind"] in to_allowed)
        cut_total += cut
        if line["billed_cents"] - cut != line["allowed_cents"]:
            found.append(f"line {line['line_no']}: billed - reductions != allowed")
        paid = line["plan_pays_cents"] + line["patient_pays_cents"] + line["other_plan_paid_cents"]
        if paid != line["allowed_cents"]:
            found.append(f"line {line['line_no']}: plan + patient + other plan != allowed")
    t = billing["totals"]
    if t["billed_cents"] - cut_total != t["allowed_cents"]:
        found.append("totals: billed - reductions != allowed")
    if (
        t["plan_pays_cents"] + t["patient_pays_cents"] + t["other_plan_paid_cents"]
        != t["allowed_cents"]
    ):
        found.append("totals: plan + patient + other plan != allowed")
    return found


def documents_and_views(check: Check, sessions: dict[str, httpx.Client]) -> None:
    rv, ad = sessions[REVIEWER_ID], sessions["admin"]
    for n in range(1, 10):
        claim_id = f"CLM-DEMO-{n:02d}"
        filer = next(FILED_BY[f] for f in FILED_BY if f.startswith(f"{n:02d}-"))
        other = sessions["provider2" if filer == "provider1" else "provider1"]
        body, kind = UPLOADED[claim_id]
        url = f"/v1/claims/{claim_id}/document"
        served = {who: sessions[who].get(url) for who in (filer, REVIEWER_ID, "admin")}
        check(
            all(
                r.status_code == 200
                and r.headers["content-type"] == kind
                and r.headers["x-content-type-options"] == "nosniff"
                and r.headers["content-disposition"].startswith("inline;")
                and hashlib.sha256(r.content).hexdigest() == hashlib.sha256(body).hexdigest()
                for r in served.values()
            ),
            f"{claim_id}: original file served to {filer}, reviewer1 and admin as {kind}, its"
            " SHA-256 the upload's",
        )
        check(other.get(url).status_code == 404, f"{claim_id}: another provider gets 404")

        staff = rv.get(f"/v1/claims/{claim_id}").json()
        record = DecisionRecord.model_validate(staff["record"])
        outcome = claim_outcome(ClaimStatus(staff["status"]), record)
        check(
            staff["outcome"] == staff["summary"]["outcome"] == outcome,
            f"{claim_id}: the summary's outcome is the record's ({outcome})",
        )
        listed = next(c for c in ad.get("/v1/claims").json() if c["claim_id"] == claim_id)
        reasons = listed["reasons"]
        check(
            (bool(reasons) and all(r["short"] for r in reasons))
            if outcome in REASONED_OUTCOMES
            else reasons == [],
            f"{claim_id}: Reason column "
            + (f"'{reasons[0]['short']}'" if reasons else "'—'")
            + (f" +{len(reasons) - 1} more" if len(reasons) > 1 else ""),
        )
        mine = sessions[filer].get(f"/v1/claims/{claim_id}").json()
        listed_mine = sessions[filer].get("/v1/claims").json()
        hidden = HIDDEN.findall(json.dumps(mine)) + HIDDEN.findall(json.dumps(listed_mine))
        check(hidden == [], f"{claim_id}: {filer}'s view holds no rule IDs or internal codes")
        explanation = mine["explanation"]
        if not mine["final"]:
            check(explanation is None, f"{claim_id}: {filer} sees no explanation while in review")
            continue
        check(
            explanation is not None
            and explanation["outcome"] == outcome
            and (bool(explanation["why"]) == (outcome in REASONED_OUTCOMES)),
            f"{claim_id}: {filer} sees '{explanation['heading'] if explanation else None}'"
            + (f" with {len(explanation['why'])} reason(s)" if explanation else ""),
        )
        if explanation and explanation["billing"]:
            errors = billing_errors(explanation["billing"])
            check(errors == [], f"{claim_id}: the billing adds up to the cent {errors or ''}")


PAGES_CLAIM = "CLM-E2E-PAGES"


def pages_in_files(check: Check, sessions: dict[str, httpx.Client]) -> None:
    p1, p2, rv = sessions["provider1"], sessions["provider2"], sessions[REVIEWER_ID]
    pages = images(PAGES_CLAIM, "PNG", days=21)
    body = {
        "files": [
            {"name": f"scan page {n}.png", "content_base64": base64.b64encode(page).decode()}
            for n, page in enumerate(pages, start=1)
        ]
    }
    before = len(rv.get("/v1/claims").json())
    swapped = {"files": list(reversed(body["files"]))}
    refused = no_5xx(check, p1.post("/v1/claims/intake/files", json=swapped), "pages swapped")
    check(
        refused.status_code == 422
        and "page 2" in refused.json().get("detail", "")
        and len(rv.get("/v1/claims").json()) == before,
        f"pages in the wrong order: 422, nothing filed ({refused.json().get('detail', '')[:60]})",
    )
    filed = no_5xx(check, p1.post("/v1/claims/intake/files", json=body), "two page files")
    read = filed.json()
    claim = read.get("claim") or read.get("received") or {}
    check(
        filed.status_code == 201
        and read.get("source_format") == "SCANNED"
        and claim.get("claim_id") == PAGES_CLAIM,
        f"{PAGES_CLAIM}: filed from two image files as one scanned claim ({filed.status_code})",
    )
    check(
        len(claim.get("clinical_notes") or "") > 20,
        f"{PAGES_CLAIM}: its clinical note read from page 2"
        f" ({len(claim.get('clinical_notes') or '')} characters)",
    )
    kept = rv.get(f"/v1/claims/{PAGES_CLAIM}").json()["documents"]
    check(
        [(d["file_no"], d["file_name"], d["content_type"]) for d in kept]
        == [(1, "scan page 1.png", "image/png"), (2, "scan page 2.png", "image/png")],
        f"{PAGES_CLAIM}: both files kept, in page order",
    )
    for number, page in enumerate(pages, start=1):
        url = f"/v1/claims/{PAGES_CLAIM}/document/{number}"
        check(
            all(
                hashlib.sha256(client.get(url).content).hexdigest()
                == hashlib.sha256(page).hexdigest()
                for client in (p1, rv, sessions["admin"])
            )
            and p2.get(url).status_code == 404,
            f"{PAGES_CLAIM}: file {number} served with the upload's SHA-256; another provider 404",
        )


FIX_CLAIM = "CLM-E2E-FIX"
MISREAD_NPI = "1234567890"  # fails the NPI check digit


def provider_tools(check: Check, sessions: dict[str, httpx.Client]) -> None:
    """Check, correct, process, review and the patient EOB (D-CHK-1, D-FIX-1, D-EOB-1, D-OBS-1)."""
    p1, rv = sessions["provider1"], sessions[REVIEWER_ID]
    npi = claim_json("01-approve-quick.json")["billing_npi"]
    pdf = digital_pdf(FIX_CLAIM, 28, {"billing_npi": MISREAD_NPI})
    filed = no_5xx(
        check,
        p1.post("/v1/claims/intake/file", content=pdf, headers={"X-File-Name": "fix.pdf"}),
        "PDF with a misread NPI",
    )
    check(filed.status_code == 201, f"{FIX_CLAIM}: filed from a PDF with a misread NPI")
    found = no_5xx(check, p1.get(f"/v1/claims/{FIX_CLAIM}/check"), "check").json()
    check(
        found.get("outcome") == "REJECTED"
        and [p["fields"] for p in found.get("problems", [])] == [["billing_npi"]],
        f"{FIX_CLAIM}: the check says rejected, for the billing NPI box only",
    )
    bad = p1.post(
        f"/v1/claims/{FIX_CLAIM}/corrections",
        json={"corrections": [{"field": "billing_npi", "value": "1234567891"}]},
    )
    check(bad.status_code == 422, f"a correction that fails the NPI check: 422 ({bad.text[:60]})")
    good = no_5xx(
        check,
        p1.post(
            f"/v1/claims/{FIX_CLAIM}/corrections",
            json={"corrections": [{"field": "billing_npi", "value": npi}]},
        ),
        "correction",
    )
    boxes = {b["field"]: b for b in good.json().get("boxes", [])}
    check(
        good.status_code == 200
        and (boxes["billing_npi"]["text"], boxes["billing_npi"]["corrected"]) == (npi, True),
        f"{FIX_CLAIM}: the billing NPI corrected",
    )
    events = rv.get(f"/v1/claims/{FIX_CLAIM}/audit").json()
    corrected = [e for e in events if e["event_type"] == "FIELD_CORRECTED"]
    check(
        len(corrected) == 1
        and corrected[0]["actor"] == "provider1"
        and corrected[0]["request_id"] == good.headers.get("x-request-id")
        and corrected[0]["payload"]["fields"][0]["before"] == MISREAD_NPI,
        "FIELD_CORRECTED: by provider1, the box before and after, its response's request ID",
    )
    ready = p1.get(f"/v1/claims/{FIX_CLAIM}/check").json()
    check(
        ready.get("outcome") == "READY" and bool(ready.get("coverage")),
        f"{FIX_CLAIM}: the check is then ready, with the line's coverage criteria",
    )
    processed = p1.post(f"/v1/claims/{FIX_CLAIM}/process")
    check(processed.status_code == 200, f"{FIX_CLAIM}: processed")
    in_review = p1.get(f"/v1/claims/{FIX_CLAIM}/eob")
    check(in_review.status_code == 409, "no EOB while the claim is in review")
    reviewed = review(rv, FIX_CLAIM)
    check(reviewed.status_code == 200, f"{FIX_CLAIM}: accepted and finalized")
    record = DecisionRecord.model_validate(rv.get(f"/v1/claims/{FIX_CLAIM}").json()["record"])
    eob = p1.get(f"/v1/claims/{FIX_CLAIM}/eob").json()
    totals = record.amounts.totals if record.amounts else None
    check(
        totals is not None
        and eob["totals"]["plan_pays_cents"] == totals.plan_pays_cents
        and eob["totals"]["patient_pays_cents"] == totals.member_pays_cents
        and eob["notes"][0] == "This is not a bill."
        and eob["year_to_date"] is not None,
        f"{FIX_CLAIM}: the patient EOB matches the calculator, with the year to date",
    )
    check(
        sessions["provider2"].get("/v1/claims/CLM-DEMO-06/eob").status_code == 409,
        "CLM-DEMO-06 (rejected): no EOB",
    )
    denied = sessions["provider2"].get("/v1/claims/CLM-DEMO-05/eob").json()
    check(
        denied.get("totals") is None and denied.get("lines", [{}])[0].get("billed_cents"),
        "CLM-DEMO-05 (denied by the rules): an EOB with its charges and no other amount",
    )
    events = rv.get(f"/v1/claims/{FIX_CLAIM}/audit").json()
    rules = next(e for e in events if e["event_type"] == "RULES_EVALUATED")
    check(
        all(e.get("request_id") for e in events)
        and rules["request_id"] == processed.headers.get("x-request-id")
        and "ncci_ptp_edits" in rules["payload"]["reference_data"]["tables"],
        "every audit event names its request; the rules event, the reference data versions",
    )


def file_fragments(data: bytes) -> dict[str, str]:
    """Pieces of a stored file as they could appear in a log: a stretch of its text, and a chunk
    of its bytes as base64 and as hex."""
    middle = data[len(data) // 2 : len(data) // 2 + 48]
    found = {
        "file bytes (base64)": base64.b64encode(middle).decode(),
        "file bytes (hex)": middle.hex(),
    }
    if data.lstrip()[:1] == b"{":
        text = " ".join(data.decode("utf-8", "replace").split())
        found["file text"] = text[len(text) // 3 : len(text) // 3 + 60]
    return found


def privacy(check: Check, api: httpx.Client, log: Path) -> None:
    """No patient name, street address, date of birth, clinical note text or stored original file
    of any demo claim (as stored at intake) in the log."""
    text = log.read_text(encoding="utf-8", errors="replace")
    for claim_id in [*(f"CLM-DEMO-{n:02d}" for n in range(1, 10)), PAGES_CLAIM]:
        response = api.get(f"/v1/claims/{claim_id}")
        if response.status_code != 200:
            continue
        claim = response.json()["received"]
        patient = claim.get("patient") or {}
        address = patient.get("address") or {}
        notes = " ".join((claim.get("clinical_notes") or "").split())
        secrets = {
            "patient name": " ".join(
                part for part in (patient.get("first_name"), patient.get("last_name")) if part
            ),
            "last name": patient.get("last_name", ""),
            "street address": address.get("line1", ""),
            "date of birth": patient.get("date_of_birth", ""),
        }
        # every 40-character stretch of the note, 20 characters apart
        for start in range(0, max(len(notes) - 40, 0) + 1, 20):
            secrets[f"clinical note text ({start})"] = notes[start : start + 40]
        for kept in response.json().get("documents", []):
            document = api.get(f"/v1/claims/{claim_id}/document/{kept['file_no']}")
            if document.status_code == 200:
                secrets |= {
                    f"{what} of file {kept['file_no']}": value
                    for what, value in file_fragments(document.content).items()
                }
        flat = " ".join(text.split())
        found = sorted(
            {
                what.split(" (")[0] if what.startswith("clinical") else what
                for what, value in secrets.items()
                if len(value) >= 4 and (value in text or value in flat)
            }
        )
        check(
            not found,
            f"{log.name} holds no patient name, address, birth date, note text or stored file"
            f" of {claim_id}" + (f" (found: {found})" if found else ""),
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
    anonymous = httpx.Client(base_url=API, timeout=300)
    if args.privacy_only:
        reviewer = login(API, REVIEWER_ID)
        for log in args.log:
            print(f"Privacy of {log}")
            privacy(check, reviewer, log)
        report(check)
        return

    print("Logins (D-AUTH-1)")
    sessions = {username: login(API, username) for username in USERS}
    for username, (role, provider_id, _) in USERS.items():
        me = sessions[username].get("/v1/auth/me").json()
        check(
            (me["role"], me["provider_id"]) == (role.value, provider_id),
            f"{username} logs in as {role.value}" + (f" ({provider_id})" if provider_id else ""),
        )
    rv, ad, p1, p2 = (sessions[u] for u in (REVIEWER_ID, "admin", "provider1", "provider2"))
    check(anonymous.get("/v1/claims").status_code == 401, "not logged in: GET /v1/claims is 401")
    check(anonymous.get("/health").status_code == 200, "not logged in: GET /health is public")
    check(p1.get("/v1/review/queue").status_code == 403, "a provider cannot see the queue (403)")
    check(
        rv.get("/v1/metrics/evaluation").status_code == 403, "a reviewer cannot see metrics (403)"
    )
    check(
        ad.post("/v1/claims/intake", json=claim_json("01-approve-quick.json")).status_code == 403,
        "an admin cannot file a claim (403)",
    )

    print("Endpoints")
    health = anonymous.get("/health").json()
    check(
        all(health[s]["ok"] for s in ("database", "qdrant", "ollama")),
        "GET /health: database, Qdrant and Ollama reachable",
    )
    check(rv.get("/v1/plans/PLN-PPO-GOLD").status_code == 200, "GET /v1/plans/{plan_id}")
    check(
        rv.get("/v1/plans/PLN-NOPE").status_code == 404,
        "GET /v1/plans/{plan_id}: unknown plan is 404",
    )
    check(
        rv.get("/v1/claims/CLM-NOPE-1").status_code == 404,
        "GET /v1/claims/{id}: unknown claim is 404",
    )
    check(ad.get("/v1/metrics/evaluation").status_code == 200, "GET /v1/metrics/evaluation (admin)")

    print("Ollama stopped, then started again (a second API on :8001)")
    switch = OllamaSwitch()
    server = second_api(switch.url)
    try:
        second_api_url = f"http://localhost:{DEAD_API_PORT}"
        second, second_rv = login(second_api_url, "provider1"), login(second_api_url, REVIEWER_ID)
        pdf = render_pdf(
            to_form_values(IntakeClaim.model_validate(claim_json("02-pend-standard.json")))
        )
        UPLOADED["CLM-DEMO-02"] = (pdf, "application/pdf")
        second.post(
            "/v1/claims/intake/file",
            content=pdf,
            headers={"Content-Type": "application/pdf", "X-File-Name": "02-pend-standard.pdf"},
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
        events = [e["event_type"] for e in second_rv.get("/v1/claims/CLM-DEMO-02/audit").json()]
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
        check(
            again.status_code == 200 and again.json().get("claim_id") == "CLM-DEMO-02",
            f"CLM-DEMO-02: processed on the same claim ID ({again.status_code})",
        )
        record = second_rv.get("/v1/claims/CLM-DEMO-02").json()["record"]
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
    r = file_and_process(check, sessions, "01-approve-quick.json", "CLM-DEMO-01", "json-body")
    check(
        r["status"] == "AWAITING_REVIEW" and r["review_tier"] == "QUICK",
        "CLM-DEMO-01: awaiting quick review",
    )
    check(
        p2.get("/v1/claims/CLM-DEMO-01").status_code == 404,
        "provider2 cannot open provider1's claim (404)",
    )
    check(
        p1.get("/v1/claims/CLM-DEMO-01/explanation").status_code == 409,
        "provider1 gets no explanation while CLM-DEMO-01 is in review (409)",
    )
    check(
        review(rv, "CLM-DEMO-01").json().get("status") == "FINAL_APPROVED",
        "CLM-DEMO-01: ACCEPT by reviewer1 -> FINAL_APPROVED",
    )
    final_view = p1.get("/v1/claims/CLM-DEMO-01").json()
    check(
        (final_view["status"], final_view["final"]) == ("FINAL_APPROVED", True)
        and final_view["explanation"] is not None,
        "provider1 sees CLM-DEMO-01's decision once final",
    )
    payload = finalized_payload(rv, "CLM-DEMO-01")
    visits = payload["visit_usage"]["REHAB_THERAPY"]
    check(
        visits["after"] == visits["before"] + 1,
        f"CLM-DEMO-01: therapy visits {visits['before']} -> {visits['after']}",
    )
    check(
        payload["accumulators"]["after"] != payload["accumulators"]["before"],
        "CLM-DEMO-01: accumulators updated",
    )
    audit = rv.get("/v1/claims/CLM-DEMO-01/audit").json()
    events = [e["event_type"] for e in audit]
    check(
        subsequence(events, [*MODEL_EVENTS, "REVIEW_OPENED", "FINALIZED"]),
        f"CLM-DEMO-01: full audit trail in order ({len(events)} events)",
    )
    actors = {e["event_type"]: e["actor"] for e in audit}
    check(
        (actors["INTAKE_COMPLETED"], actors["REVIEW_ACCEPTED"], actors["FINALIZED"])
        == ("provider1", REVIEWER_ID, REVIEWER_ID),
        "CLM-DEMO-01: audit actors are the logged-in provider and reviewer",
    )

    check(
        review(rv, "CLM-DEMO-02").json().get("status") == "FINAL_PENDED",
        "CLM-DEMO-02: ACCEPT -> FINAL_PENDED",
    )
    events = [e["event_type"] for e in rv.get("/v1/claims/CLM-DEMO-02/audit").json()]
    check(
        events == REVIEWED_EVENTS,
        "CLM-DEMO-02: complete audit trail after the recovery, each stage once and the"
        f" explanation built for the recommendation and the final decision ({events})",
    )

    r = file_and_process(check, sessions, "03-deny-full-override.json", "CLM-DEMO-03", "json-file")
    check(
        r["review_tier"] == "FULL" and r["line_decisions"][0]["decision"] == "DENY",
        "CLM-DEMO-03: model DENY, full review",
    )
    no_reason = review(rv, "CLM-DEMO-03", [{"line_no": 1, "decision": "APPROVE", "reason": ""}])
    check(
        no_reason.status_code == 422,
        f"CLM-DEMO-03: an override without a reason is refused ({no_reason.status_code})",
    )
    final = review(
        rv,
        "CLM-DEMO-03",
        [{"line_no": 1, "decision": "APPROVE", "reason": "The note documents the criterion."}],
    ).json()
    check(
        final.get("status") == "FINAL_APPROVED" and final["amounts"]["totals"]["allowed_cents"] > 0,
        "CLM-DEMO-03: OVERRIDE -> FINAL_APPROVED, amounts recomputed",
    )

    r = file_and_process(check, sessions, "04-partial-ncci.json", "CLM-DEMO-04", "json-file")
    check(
        any(d["source"] == "RULE" and d["decision"] == "DENY" for d in r["line_decisions"]),
        "CLM-DEMO-04: a line denied by NCCI",
    )
    check(
        review(rv, "CLM-DEMO-04").json().get("status") == "FINAL_PARTIAL",
        "CLM-DEMO-04: ACCEPT -> FINAL_PARTIAL",
    )

    r = file_and_process(check, sessions, "05-rule-deny-r15.json", "CLM-DEMO-05", "json-file")
    check(r["status"] == "DENIED_BY_RULE", "CLM-DEMO-05: DENIED_BY_RULE (R15)")
    check(
        review(rv, "CLM-DEMO-05").status_code == 409,
        "CLM-DEMO-05: a rule outcome cannot be reviewed (409)",
    )
    codes = rv.get("/v1/claims/CLM-DEMO-05").json()["adjustments"]
    check(
        bool(codes) and codes[0]["codes"][0]["code"] == "11" and codes[0]["billing_article"],
        "CLM-DEMO-05: CARC 11 with its billing article",
    )

    r = file_and_process(check, sessions, "06-reject-invalid-npi.json", "CLM-DEMO-06", "json-file")
    check(r["status"] == "REJECTED", "CLM-DEMO-06: invalid NPI -> REJECTED")
    r = file_and_process(check, sessions, "07-duplicate-of-01.json", "CLM-DEMO-07", "json-file")
    reasons = [x["reason_code"] for x in r["rules_outcome"]["rule_results"] if not x["passed"]]
    check(
        r["status"] == "REJECTED" and "RJ_DUPLICATE" in reasons,
        "CLM-DEMO-07: duplicate -> REJECTED RJ_DUPLICATE",
    )
    r = file_and_process(check, sessions, "08-scanned-clean.pdf", "CLM-DEMO-08", "scanned")
    check(r["status"] == "AWAITING_REVIEW", "CLM-DEMO-08 (scanned): awaiting review")
    r = file_and_process(check, sessions, "09-scanned-low-confidence.pdf", "CLM-DEMO-09", "scanned")
    reasons = [x["reason_code"] for x in r["rules_outcome"]["rule_results"] if not x["passed"]]
    check(
        r["status"] == "REJECTED" and "RJ_LOW_CONFIDENCE_FIELD" in reasons,
        "CLM-DEMO-09 (scanned): REJECTED RJ_LOW_CONFIDENCE_FIELD",
    )

    print("Explanations, versions, audit trails")
    for n in range(1, 10):
        explained(check, rv, f"CLM-DEMO-{n:02d}")

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
            for a in rv.get(f"/v1/claims/{claim_id}").json()["adjustments"]
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
    pended = rv.get("/v1/claims/CLM-DEMO-02").json()["adjustments"]
    check(pended == [], "CLM-DEMO-02 (pended): no CARC/RARC codes")
    article = rv.get("/v1/claims/CLM-DEMO-05").json()["adjustments"][0]
    check(
        bool(article["billing_article"] and article["lcds"]),
        f"CLM-DEMO-05: billing article {article['billing_article']},"
        f" LCD {', '.join(article['lcds'])}",
    )
    own = p2.get("/v1/claims/CLM-DEMO-06").json()
    check(
        own["final"] and [g["codes"][0]["code"] for g in own["explanation"]["codes"]] == ["16"],
        "provider2 sees CLM-DEMO-06's rejection codes at once (a rule outcome is final)",
    )

    print("Queue, lists and roles")
    queue = rv.get("/v1/review/queue").json()
    check(
        [q["claim_id"] for q in queue] == ["CLM-DEMO-08"],
        "GET /v1/review/queue: only CLM-DEMO-08 still waits",
    )
    check(ad.get("/v1/review/queue").status_code == 200, "an admin can read the queue")
    check(review_as(p2, "provider2").status_code == 403, "a provider cannot review a claim (403)")
    check(review_as(ad, "admin").status_code == 403, "an admin cannot review a claim (403)")
    check(
        review_as(rv, "reviewer2").status_code == 403,
        "reviewer1 cannot review as reviewer2 (403)",
    )
    listed = {c["claim_id"] for c in rv.get("/v1/claims").json()}
    check({f"CLM-DEMO-{n:02d}" for n in range(1, 10)} <= listed, "GET /v1/claims: no claim lost")
    for username, client in (("provider1", p1), ("provider2", p2)):
        mine = {c["claim_id"] for c in client.get("/v1/claims").json()}
        theirs = {f"CLM-DEMO-{name[:2]}" for name, who in FILED_BY.items() if who == username}
        check(mine == theirs, f"{username} lists only their own claims ({len(mine)})")
    waiting = next(c for c in p2.get("/v1/claims").json() if c["claim_id"] == "CLM-DEMO-08")
    check(
        (waiting["status"], waiting["claim_decision"]) == ("IN_REVIEW", None),
        "provider2 sees CLM-DEMO-08 as IN_REVIEW, without its recommendation",
    )

    print("Original files and the pages' explanations (D-DOC-1, D-UI-6)")
    documents_and_views(check, sessions)

    print("One claim from its form's pages in two files (D-DOC-2)")
    pages_in_files(check, sessions)

    print("Check, correct, process and the patient EOB (D-CHK-1, D-FIX-1, D-EOB-1, D-OBS-1)")
    provider_tools(check, sessions)

    print("Bad inputs")
    for what, body, headers in (
        ("wrong file type", b"just some text, not a claim", {"Content-Type": "text/plain"}),
        ("empty file", b"", {}),
        ("corrupted PDF", b"%PDF-1.7\nbroken", {"Content-Type": "application/pdf"}),
    ):
        response = no_5xx(
            check, p1.post("/v1/claims/intake/file", content=body, headers=headers), what
        )
        check(response.status_code == 422, f"{what}: 422 {response.json().get('detail', '')[:70]}")
    missing = dict(claim_json("01-approve-quick.json"), claim_id="CLM-E2E-MISSING")
    missing["service_lines"] = [dict(missing["service_lines"][0])]
    missing["service_lines"][0].pop("procedure_code")
    filed = no_5xx(check, p1.post("/v1/claims/intake", json=missing), "JSON with a missing field")
    check(
        filed.status_code == 201 and filed.json()["contract_errors"],
        "JSON with a missing field: filed with its contract errors",
    )
    status = p1.post("/v1/claims/CLM-E2E-MISSING/process").json()["status"]
    check(status == "REJECTED", f"JSON with a missing field: {status} after processing")
    no_id = no_5xx(
        check,
        p1.post("/v1/claims/intake", json={"member_id": "MBR-000001"}),
        "JSON without a claim ID",
    )
    check(no_id.status_code == 422, "JSON without a claim ID: 422")
    again = no_5xx(
        check,
        p1.post("/v1/claims/intake", json=claim_json("01-approve-quick.json")),
        "duplicate claim ID",
    )
    check(again.status_code == 409, "the same claim ID twice: 409")

    for log in args.log:
        print(f"Privacy of {log}")
        privacy(check, rv, log)
    report(check)


def report(check: Check) -> None:
    print(f"\n{check.passed} checks passed, {len(check.failed)} failed")
    for what in check.failed:
        print(f"  FAIL {what}")
    if check.failed:
        raise SystemExit(1)


def review_as(api: httpx.Client, reviewer_id: str) -> httpx.Response:
    """An ACCEPT of CLM-DEMO-08 naming `reviewer_id`, sent by `api`'s user."""
    return api.post(
        "/v1/claims/CLM-DEMO-08/review",
        json={
            "claim_id": "CLM-DEMO-08",
            "reviewer_id": reviewer_id,
            "action": "ACCEPT",
            "timestamp": "2026-10-11T10:00:00Z",
        },
    )


if __name__ == "__main__":
    main()
