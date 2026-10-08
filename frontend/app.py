"""ClaimSense walking-skeleton page (P1.5): submit a JSON claim, process it, show the decision
record and the audit trail, and review a claim awaiting review (P5.3: Accept, or one Submit with
every changed line). The P5.5 pages replace it.

Calls the API over HTTP only; never imports `app` or touches the database (§8.11).

    uv run uvicorn app.api.main:app          # terminal 1
    uv run streamlit run frontend/app.py     # terminal 2
"""

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import streamlit as st

API_URL = os.environ.get("CLAIMSENSE_API_URL", "http://localhost:8000")
SAMPLE = Path(__file__).parent / "sample_claim.json"
TIMEOUT_SECONDS = 330.0  # the model call may take minutes on a laptop
CALCULATION_FAILED = "CALCULATION_FAILED:"  # an output_errors entry from the calculator (P2.4)
REVIEWER_HEADERS = {"X-Role": "reviewer"}  # the prototype's role header (§8.10)
DECISIONS = ["APPROVE", "PEND", "DENY"]


def dollars(cents: int) -> str:
    """Display only; amounts stay integer cents (H2)."""
    sign = "-" if cents < 0 else ""
    return f"{sign}${abs(cents) // 100:,}.{abs(cents) % 100:02d}"


def show_error(response: httpx.Response, what: str) -> None:
    try:
        detail = response.json().get("detail", response.text)
    except ValueError:
        detail = response.text
    st.error(f"{what} failed ({response.status_code}): {detail}")


def submit(http: httpx.Client, claim: dict[str, Any]) -> str | None:
    claim_id = claim.get("claim_id", "")
    response = http.post("/v1/claims/intake", json=claim)
    if response.status_code != 201:
        show_error(response, "Intake")
        return None
    contract_errors = response.json().get("contract_errors")
    if contract_errors:  # filed although it fails the contract; the rules will reject it (P2.5)
        st.warning(
            "Filed with contract errors; the rules will reject it:\n\n"
            + "\n".join(f"- {e}" for e in contract_errors)
        )
    with st.spinner("Running the rules, the model and the calculator..."):
        response = http.post(f"/v1/claims/{claim_id}/process")
    if response.status_code != 200:
        show_error(response, f"Processing (claim {claim_id} stays RECEIVED)")
    return claim_id


def show_health(http: httpx.Client) -> None:
    try:
        report = http.get("/health", timeout=5).json()
    except (httpx.HTTPError, ValueError) as exc:
        st.sidebar.error(f"API unreachable ({type(exc).__name__})")
        return
    for service in ("database", "qdrant", "ollama"):
        status = report[service]
        (st.sidebar.success if status["ok"] else st.sidebar.warning)(
            f"{service}: {status['detail']}"
        )


def candidate_categories(record: dict[str, Any]) -> dict[int, list[str]]:
    context = record["context_refs"]
    if not context:
        return {}
    return {
        line["line_no"]: [fact["benefit_category"] for fact in line["candidate_benefits"]]
        for line in context["lines"]
    }


def open_for_review(http: httpx.Client, claim_id: str, reviewer_id: str) -> None:
    """REVIEW_OPENED once per claim and reviewer in this session: the start of the review time."""
    opened = st.session_state.setdefault("opened", set())
    if (claim_id, reviewer_id) in opened:
        return
    response = http.post(
        f"/v1/claims/{claim_id}/review/open",
        json={"reviewer_id": reviewer_id},
        headers=REVIEWER_HEADERS,
    )
    if response.status_code != 200:
        show_error(response, "Opening the claim for review")
        return
    opened.add((claim_id, reviewer_id))


def send_review(
    http: httpx.Client,
    claim_id: str,
    reviewer_id: str,
    action: str,
    overrides: list[dict[str, Any]],
) -> None:
    body = {
        "claim_id": claim_id,
        "reviewer_id": reviewer_id,
        "action": action,
        "line_overrides": overrides,
        "timestamp": datetime.now(UTC).isoformat(),
    }
    response = http.post(f"/v1/claims/{claim_id}/review", json=body, headers=REVIEWER_HEADERS)
    if response.status_code != 200:
        show_error(response, "Review")
        return
    status = response.json()["status"]
    st.session_state["reviewed"] = f"Claim {claim_id} finalized as {status} by {reviewer_id}."
    st.rerun()


def review_controls(http: httpx.Client, record: dict[str, Any], reviewer_id: str) -> None:
    """Accept, or Submit every changed line in one OVERRIDE (§8.8). Reviewers never enter amounts.
    Rule lines are read-only (D-REV-2); a category choice appears only on an APPROVE line with
    several candidate categories (D-REV-4)."""
    claim_id = record["claim_id"]
    candidates = candidate_categories(record)
    st.markdown("**Review**")
    overrides: list[dict[str, Any]] = []
    without_reason: list[int] = []
    for line in record["line_decisions"]:
        n = line["line_no"]
        if line["source"] == "RULE":
            st.caption(
                f"Line {n}: {line['decision']} by rule ({', '.join(line['reason_codes'])}); "
                "rule outcomes are automatic and cannot be overridden."
            )
            continue
        columns = st.columns([1, 1, 2])
        decision = columns[0].selectbox(
            f"Line {n} decision",
            DECISIONS,
            index=DECISIONS.index(line["decision"]),
            key=f"decision-{claim_id}-{n}",
        )
        category = line["benefit_category"]
        options = candidates.get(n, [])
        if decision == "APPROVE" and len(options) > 1:
            category = columns[1].selectbox(
                f"Line {n} benefit category",
                options,
                index=options.index(category) if category in options else None,
                placeholder="Choose one",
                key=f"category-{claim_id}-{n}",
            )
        reason = columns[2].text_input(f"Line {n} reason", key=f"reason-{claim_id}-{n}")
        if decision == line["decision"] and category == line["benefit_category"]:
            continue
        override = {"line_no": n, "decision": decision, "reason": reason}
        if decision == "APPROVE" and len(options) > 1 and category is not None:
            override["benefit_category"] = category
        overrides.append(override)
        if not reason.strip():
            without_reason.append(n)

    accept, submit = st.columns(2)
    if accept.button(
        "Accept",
        type="primary",
        disabled=bool(overrides),
        help="Accept keeps every line as recommended; undo the changed lines to use it.",
        key=f"accept-{claim_id}",
    ):
        send_review(http, claim_id, reviewer_id, "ACCEPT", [])
    if submit.button("Submit", key=f"submit-{claim_id}"):
        if not overrides:
            st.error("Change at least one line's decision or category, or use Accept.")
        elif without_reason:
            lines = ", ".join(str(n) for n in without_reason)
            st.error(f"Each changed line needs a reason (line {lines}).")
        else:
            send_review(http, claim_id, reviewer_id, "OVERRIDE", overrides)


def show_claim(http: httpx.Client, claim_id: str, reviewer_id: str = "") -> None:
    response = http.get(f"/v1/claims/{claim_id}")
    if response.status_code != 200:
        show_error(response, "Loading the claim")
        return
    view = response.json()
    record = view["record"]
    st.subheader(f"Claim {claim_id}")
    if record is None:
        st.info(f"Status {view['status']}: not processed yet.")
        return
    if message := st.session_state.pop("reviewed", None):
        st.success(message)
    awaiting_review = record["status"] == "AWAITING_REVIEW" and bool(reviewer_id)
    if awaiting_review:
        open_for_review(http, claim_id, reviewer_id)
    events = http.get(f"/v1/claims/{claim_id}/audit").json()

    amounts = record["amounts"]
    totals = amounts["totals"] if amounts else None
    columns = st.columns(5)
    columns[0].metric("Status", record["status"])
    columns[1].metric("Claim decision", record["claim_decision"] or "-")
    columns[2].metric("Review tier", record["review_tier"] or "-")
    columns[3].metric("Plan pays", dollars(totals["plan_pays_cents"]) if totals else "-")
    columns[4].metric("Member pays", dollars(totals["member_pays_cents"]) if totals else "-")
    calculation_errors = [e for e in record["output_errors"] if e.startswith(CALCULATION_FAILED)]
    model_errors = [e for e in record["output_errors"] if not e.startswith(CALCULATION_FAILED)]
    if model_errors:
        st.warning(
            "The model output failed validation, so every model line is PEND "
            "(MODEL_OUTPUT_INVALID):\n\n" + "\n".join(f"- {e}" for e in model_errors)
        )
    if calculation_errors:
        st.warning(
            "The amounts could not be calculated, so the claim needs FULL review:\n\n"
            + "\n".join(f"- {e}" for e in calculation_errors)
        )

    st.markdown("**Rule checks**")
    st.dataframe(
        [
            {
                "rule": r["rule_id"],
                "passed": r["passed"],
                "outcome": r["outcome"],
                "reason code": r["reason_code"] or "",
                "detail": r["detail"],
            }
            for r in record["rules_outcome"]["rule_results"]
        ],
        hide_index=True,
    )

    if record["line_decisions"]:
        st.markdown("**Line decisions**")
        st.dataframe(
            [
                {
                    "line": d["line_no"],
                    "decision": d["decision"],
                    "benefit category": d["benefit_category"] or "",
                    "decided by": d["source"],
                    "reason codes": ", ".join(d["reason_codes"]),
                }
                for d in record["line_decisions"]
            ],
            hide_index=True,
        )

    if record["slm_output"]:
        output = record["slm_output"]
        st.markdown(f"**Model recommendation** (complexity {output['complexity']})")
        criteria = [
            {
                "line": line["line_no"],
                "criterion": c["criterion_id"],
                "status": c["status"],
                "evidence": c["evidence"],
            }
            for line in output["lines"]
            for c in line["criteria"]
        ]
        if criteria:
            st.dataframe(criteria, hide_index=True)
        else:
            st.caption("No coverage criteria evaluated.")

    if amounts:
        st.markdown("**Amounts**")
        names = [
            ("billed", "billed_cents"),
            ("allowed", "allowed_cents"),
            ("contractual adj.", "contractual_adjustment_cents"),
            ("deductible", "deductible_cents"),
            ("copay", "copay_cents"),
            ("coinsurance", "coinsurance_cents"),
            ("plan pays", "plan_pays_cents"),
            ("member pays", "member_pays_cents"),
        ]
        rows = [
            {"line": str(line["line_no"])} | {label: dollars(line[key]) for label, key in names}
            for line in amounts["lines"]
        ]
        rows.append({"line": "total"} | {k: dollars(amounts["totals"][v]) for k, v in names})
        st.dataframe(rows, hide_index=True)
    finalized = next((e for e in reversed(events) if e["event_type"] == "FINALIZED"), None)
    if finalized and finalized["payload"]["amounts_changed_since_review"]:
        changed = ", ".join(finalized["payload"]["changed_totals"])
        st.info(
            f"The final amounts differ from those shown at review ({changed}): they were "
            "recomputed at finalization from the final line decisions and the member's "
            "accumulators at that time."
        )

    if awaiting_review:
        review_controls(http, record, reviewer_id)

    st.markdown("**Audit trail**")
    st.dataframe(
        [
            {
                "time": e["created_at"],
                "event": e["event_type"],
                "actor": e["actor"],
                "rules": e["rules_version"] or "",
                "model": e["model_name"] or "",
                "prompt": e["prompt_version"] or "",
                "payload": json.dumps(e["payload"]),
            }
            for e in events
        ],
        hide_index=True,
    )
    versions = record["versions"]
    st.caption(
        f"Rules {versions['rules_version']} | model {versions['model_name'] or '-'} | "
        f"prompt {versions['prompt_version'] or '-'}"
    )
    with st.expander("Decision record (JSON)"):
        st.json(record)


def main() -> None:
    st.set_page_config(page_title="ClaimSense", layout="wide")
    st.title("ClaimSense")
    st.caption(
        "JSON claim → rules R01–R13 → model → calculator → decision record → audit trail. "
        "A rule failure is final; every model recommendation goes to a human reviewer. "
        "Synthetic data only."
    )
    api_url = st.sidebar.text_input("API URL", API_URL)
    reviewer_id = st.sidebar.text_input("Reviewer ID", "reviewer-1").strip()
    with httpx.Client(base_url=api_url, timeout=TIMEOUT_SECONDS) as http:
        show_health(http)

        with st.expander("Submit a claim", expanded="claim_id" not in st.session_state):
            text = st.text_area("Claim JSON (IntakeClaim)", SAMPLE.read_text(), height=400)
            new_id = st.toggle(
                "Use a new claim ID",
                value=True,
                help=(
                    "Claim IDs are unique, so a resubmit needs a new one; the duplicate rule then "
                    "rejects it unless the earlier claim was rejected (A-R6)."
                ),
            )
            if st.button("Submit and process", type="primary"):
                try:
                    claim = json.loads(text)
                except json.JSONDecodeError as exc:
                    st.error(f"Not valid JSON: {exc}")
                    st.stop()
                if new_id:
                    claim["claim_id"] = f"CLM-DEMO-{datetime.now():%Y%m%d-%H%M%S}"
                claim_id = submit(http, claim)
                if claim_id:
                    st.session_state["claim_id"] = claim_id

        claim_id = st.text_input("Claim ID", st.session_state.get("claim_id", ""))
        if claim_id:
            show_claim(http, claim_id.strip(), reviewer_id)


if __name__ == "__main__":  # Streamlit runs the page as __main__
    main()
