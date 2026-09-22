"""ClaimSense walking-skeleton page (P1.5): submit a JSON claim, process it, and show the decision
record and the audit trail. The P5.5 pages replace it.

Calls the API over HTTP only; never imports `app` or touches the database (§8.11).

    uv run uvicorn app.api.main:app          # terminal 1
    uv run streamlit run frontend/app.py     # terminal 2
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
import streamlit as st

API_URL = os.environ.get("CLAIMSENSE_API_URL", "http://localhost:8000")
SAMPLE = Path(__file__).parent / "sample_claim.json"
TIMEOUT_SECONDS = 330.0  # the model call may take minutes on a laptop


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


def show_claim(http: httpx.Client, claim_id: str) -> None:
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

    amounts = record["amounts"]
    totals = amounts["totals"] if amounts else None
    columns = st.columns(5)
    columns[0].metric("Status", record["status"])
    columns[1].metric("Claim decision", record["claim_decision"] or "-")
    columns[2].metric("Review tier", record["review_tier"] or "-")
    columns[3].metric("Plan pays", dollars(totals["plan_pays_cents"]) if totals else "-")
    columns[4].metric("Member pays", dollars(totals["member_pays_cents"]) if totals else "-")
    if record["output_errors"]:
        st.warning(
            "The model output failed validation, so every model line is PEND "
            "(MODEL_OUTPUT_INVALID):\n\n" + "\n".join(f"- {e}" for e in record["output_errors"])
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
                "met": c["met"],
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

    st.markdown("**Audit trail**")
    events = http.get(f"/v1/claims/{claim_id}/audit").json()
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
        "Walking skeleton (P1.5): JSON claim → rule R05 → base model → copay calculator → "
        "decision record → audit trail. Synthetic data only; every recommendation goes to a "
        "human reviewer."
    )
    api_url = st.sidebar.text_input("API URL", API_URL)
    with httpx.Client(base_url=api_url, timeout=TIMEOUT_SECONDS) as http:
        show_health(http)

        with st.expander("Submit a claim", expanded="claim_id" not in st.session_state):
            text = st.text_area("Claim JSON (IntakeClaim)", SAMPLE.read_text(), height=400)
            new_id = st.toggle(
                "Use a new claim ID", value=True, help="Claim IDs are unique; resubmits need one"
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
            show_claim(http, claim_id.strip())


if __name__ == "__main__":  # Streamlit runs the page as __main__
    main()
