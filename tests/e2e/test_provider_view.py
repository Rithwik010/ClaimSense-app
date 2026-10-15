"""D-UI-6 through the API, on every golden end-to-end case (v1 and v2), processed and reviewed:

- a provider's responses (the process answer, the claim and the list) hold no rule IDs, internal
  reason codes, criterion IDs, model output, confidence scores or versions, after processing and
  once final;
- the provider's explanation appears only once the claim is final, with the outcome every
  dashboard shows, a reason for each claim not paid as billed and, for paid claims, the billing:
  billed minus the reductions to the allowed amount is the allowed amount, and the allowed amount
  is what the plan pays plus what the patient pays plus what another plan paid first, to the cent;
- a reviewer's claim carries the summary of the same outcome, and the list the reasons with their
  codes and rules for the Reason column.

D-CHK-1: checking the claim before it is processed predicts what the rules then do (rejected,
denied, on hold, or going on to review) and writes nothing. D-EOB-1: a decided claim's patient EOB
shows the calculator's amounts line by line and in total, to the cent; a claim in review, rejected
or on hold by the rules has none (409).
"""

import json
import re
from typing import Any

import pytest
from sqlalchemy.orm import Session

from app.domain.contracts import ClaimStatus, DecisionRecord, LineDecision, SourceFormat
from app.explain.eob import EOB_STATUSES, NOT_A_BILL
from app.explain.reasons import REASONED_OUTCOMES, claim_outcome
from app.workflow.pipeline import intake_claim_data
from scripts.verify.e2e_v2_cases import v2_retriever
from tests.e2e.support import (
    E2E_CASES,
    E2E_V2_CASES,
    FILED_BY_TEST_PROVIDER,
    PROVIDER,
    REVIEWER,
    CaseRetriever,
    StubModel,
    record_of,
)

CASES = [E2E_CASES[k] for k in sorted(E2E_CASES)] + [E2E_V2_CASES[k] for k in sorted(E2E_V2_CASES)]
# What a provider never sees (D-UI-6): rule IDs, internal reason codes and criterion IDs.
HIDDEN = re.compile(
    r"\bR(?:0[1-9]|1[0-9]|20)\b|\bDUP\b|\b(?:RJ|DN|PD|RV)_[A-Z0-9_]+\b"
    r"|\bMODEL_OUTPUT_INVALID\b|\bPOL-[A-Z]+-[0-9]{3}\.c[0-9]+\b"
)
HIDDEN_KEYS = (
    "record",
    "rule_results",
    "rules_outcome",
    "slm_output",
    "field_confidences",
    "rules_version",
    "model_name",
    "prompt_version",
    "review_tier",
    "failed_rules",
    "reason_code",
    "criterion_id",
)
TO_ALLOWED = ("allowed_amount", "out_of_network", "not_paid")
# What a check before processing says for each status processing then gives (D-CHK-1).
PREDICTED = {
    "REJECTED": {"REJECTED"},
    "DENIED_BY_RULE": {"DENIED"},
    "PENDED_BY_RULE": {"PENDED"},
    "AWAITING_REVIEW": {"READY", "LINES_DENIED"},
}
EOB_LINE = {
    LineDecision.APPROVE: "PAID",
    LineDecision.DENY: "NOT_PAID",
    LineDecision.PEND: "PENDING",
}


def provider_safe(response: Any) -> list[str]:  # noqa: ANN401
    """Everything in a provider's response that must not be there."""
    text = json.dumps(response)
    found = HIDDEN.findall(text)
    found += [f'key "{key}"' for key in HIDDEN_KEYS if f'"{key}":' in text]
    return found


def billing_errors(billing: dict[str, Any]) -> list[str]:
    """The arithmetic each billing line and the totals must satisfy, to the cent."""
    found = []
    not_paid = 0
    for line in billing["lines"]:
        cut = sum(r["amount_cents"] for r in line["reductions"] if r["kind"] in TO_ALLOWED)
        if line["billed_cents"] - cut != line["allowed_cents"]:
            found.append(f"line {line['line_no']}: billed - reductions != allowed")
        paid = line["plan_pays_cents"] + line["patient_pays_cents"] + line["other_plan_paid_cents"]
        if paid != line["allowed_cents"]:
            found.append(f"line {line['line_no']}: plan + patient + other plan != allowed")
        if any(r["amount_cents"] == 0 for r in line["reductions"]):
            found.append(f"line {line['line_no']}: a zero reduction is shown")
        not_paid += sum(r["amount_cents"] for r in line["reductions"] if r["kind"] == "not_paid")
        if line["paid"] == any(r["kind"] == "not_paid" for r in line["reductions"]):
            found.append(f"line {line['line_no']}: paid and not-paid sentences disagree")
    t = billing["totals"]
    lines = billing["lines"]
    for name in ("billed_cents", "allowed_cents", "plan_pays_cents", "patient_pays_cents"):
        if sum(line[name] for line in lines) != t[name]:
            found.append(f"totals: {name} is not the sum of the lines")
    cut = sum(
        r["amount_cents"] for line in lines for r in line["reductions"] if r["kind"] in TO_ALLOWED
    )
    if t["billed_cents"] - cut != t["allowed_cents"]:
        found.append("totals: billed - reductions != allowed")
    if (
        t["plan_pays_cents"] + t["patient_pays_cents"] + t["other_plan_paid_cents"]
        != t["allowed_cents"]
    ):
        found.append("totals: plan + patient + other plan != allowed")
    return found


def run(api, load_case_reference, engine, case: dict[str, Any]):  # noqa: ANN001, ANN201
    given = case["given"]
    load_case_reference(case)
    answer = given.get("model_answer")
    model = StubModel(json.dumps(answer) if answer is not None else "unused")
    v2 = case["case_id"] in E2E_V2_CASES
    client = api(model, v2_retriever(), policy_set="v2") if v2 else api(model, CaseRetriever(case))
    claim = given["claim"]
    if given["source_format"] == "JSON":
        assert client.post("/v1/claims/intake", json=claim).status_code == 201
    else:
        with Session(engine) as session:
            intake_claim_data(
                session,
                claim,
                given["field_confidences"],
                SourceFormat(given["source_format"]),
                0.85,
                **FILED_BY_TEST_PROVIDER,
            )
    return client


def check_provider(client, claim_id: str, record: DecisionRecord) -> dict[str, Any]:  # noqa: ANN001
    view = client.get(f"/v1/claims/{claim_id}", headers=PROVIDER).json()
    listed = client.get("/v1/claims", headers=PROVIDER).json()
    assert provider_safe(view) == [] and provider_safe(listed) == []
    final = record.status not in (ClaimStatus.RECEIVED, ClaimStatus.AWAITING_REVIEW)
    assert view["final"] is final
    if not final:
        assert view["explanation"] is None and view["outcome"] == "IN_REVIEW"
        return view
    outcome = claim_outcome(record.status, record)
    explanation = view["explanation"]
    assert view["outcome"] == outcome == explanation["outcome"]
    assert next(c for c in listed if c["claim_id"] == claim_id)["outcome"] == outcome
    if outcome in REASONED_OUTCOMES:
        assert explanation["why"] and explanation["review"], explanation
    else:
        assert explanation["why"] == [] and explanation["codes"] == []
    if outcome in ("APPROVED", "PARTLY_APPROVED") and record.amounts is not None:
        assert billing_errors(explanation["billing"]) == []
    else:
        assert explanation["billing"] is None
    assert view["eob"] is (record.status in EOB_STATUSES)
    check_eob(client, claim_id, record)
    return view


def check_eob(client, claim_id: str, record: DecisionRecord) -> None:  # noqa: ANN001
    """The patient EOB of a decided claim matches the calculator to the cent; others have none."""
    response = client.get(f"/v1/claims/{claim_id}/eob", headers=PROVIDER)
    if record.status not in EOB_STATUSES:
        assert response.status_code == 409, response.text
        return
    assert response.status_code == 200, response.text
    eob = response.json()
    assert provider_safe(eob) == []
    assert eob["notes"][0] == NOT_A_BILL
    assert eob["outcome"] == claim_outcome(record.status, record)
    if record.amounts is None:
        assert eob["totals"] is None
        assert all(line["allowed_cents"] is None for line in eob["lines"])
        assert all(line["status"] == "NOT_PAID" for line in eob["lines"])
        return
    t = record.amounts.totals
    assert eob["totals"] == {
        "billed_cents": t.billed_cents,
        "allowed_cents": t.allowed_cents,
        "plan_pays_cents": t.plan_pays_cents,
        "patient_pays_cents": t.member_pays_cents,
        "other_plan_paid_cents": t.cob_primary_paid_cents,
    }
    decisions = {d.line_no: d.decision for d in record.line_decisions}
    for line, amounts in zip(eob["lines"], record.amounts.lines, strict=True):
        assert line["line_no"] == amounts.line_no
        assert (line["billed_cents"], line["allowed_cents"]) == (
            amounts.billed_cents,
            amounts.allowed_cents,
        )
        assert (line["plan_pays_cents"], line["patient_pays_cents"]) == (
            amounts.plan_pays_cents,
            amounts.member_pays_cents,
        )
        assert line["status"] == EOB_LINE[decisions[amounts.line_no]]
    assert eob["year_to_date"] is not None


def check_before_processing(client, claim_id: str, expected: str) -> None:  # noqa: ANN001
    """The check predicts what processing does, and writes nothing."""
    events = len(client.get(f"/v1/claims/{claim_id}/audit", headers=REVIEWER).json())
    response = client.get(f"/v1/claims/{claim_id}/check", headers=PROVIDER)
    assert response.status_code == 200, response.text
    check = response.json()
    assert provider_safe(check) == []
    assert check["outcome"] in PREDICTED[expected], check
    if check["outcome"] != "READY":
        assert check["problems"], check
    if expected == "AWAITING_REVIEW":
        assert check["coverage"] is not None
    assert len(client.get(f"/v1/claims/{claim_id}/audit", headers=REVIEWER).json()) == events
    view = client.get(f"/v1/claims/{claim_id}", headers=REVIEWER).json()
    assert view["status"] == "RECEIVED" and view["record"] is None


def check_reviewer(client, claim_id: str, record: DecisionRecord) -> None:  # noqa: ANN001
    view = client.get(f"/v1/claims/{claim_id}", headers=REVIEWER).json()
    outcome = claim_outcome(record.status, record)
    assert view["outcome"] == view["summary"]["outcome"] == outcome
    kinds = [item["kind"] for item in view["summary"]["items"]]
    assert kinds[:2] == ["glance", "checks"] and 2 <= len(kinds) <= 2 + 6
    listed = next(
        c for c in client.get("/v1/claims", headers=REVIEWER).json() if c["claim_id"] == claim_id
    )
    assert listed["outcome"] == outcome
    if outcome in REASONED_OUTCOMES:
        assert listed["reasons"] and all(r["short"] and r["code"] for r in listed["reasons"])
    else:
        assert listed["reasons"] == []


@pytest.mark.parametrize("case", CASES, ids=[case["case_id"] for case in CASES])
def test_the_provider_view_and_the_summary(
    api, load_case_reference, engine, case: dict[str, Any]
) -> None:  # noqa: ANN001, E501
    client = run(api, load_case_reference, engine, case)
    claim_id = case["given"]["claim"]["claim_id"]
    before = client.get(f"/v1/claims/{claim_id}", headers=PROVIDER).json()
    assert (before["outcome"], before["explanation"]) == ("IN_REVIEW", None)  # not processed
    expected = case["expected"]["status_after_processing"]
    check_before_processing(client, claim_id, expected)

    processed = client.post(f"/v1/claims/{claim_id}/process")
    assert processed.status_code == 200, processed.text
    assert provider_safe(processed.json()) == []
    record = record_of(client, claim_id)
    assert record.status.value == expected
    assert client.get(f"/v1/claims/{claim_id}/check", headers=PROVIDER).status_code == 409
    check_provider(client, claim_id, record)
    check_reviewer(client, claim_id, record)
    action = case["given"].get("review_action")
    if action is None:
        return

    reviewed = client.post(f"/v1/claims/{claim_id}/review", json=action)
    assert reviewed.status_code == 200, reviewed.text
    final = DecisionRecord.model_validate(reviewed.json())
    check_provider(client, claim_id, final)
    check_reviewer(client, claim_id, final)


def test_a_partly_paid_pended_claim_counts_as_partly_approved(
    api, load_case_reference, engine
) -> None:  # noqa: ANN001
    """E2E-21: a pended line and an approved (paid) line: mixed outcomes are partly approved."""
    case = E2E_CASES["E2E-21"]
    client = run(api, load_case_reference, engine, case)
    claim_id = case["given"]["claim"]["claim_id"]
    assert client.post(f"/v1/claims/{claim_id}/process").status_code == 200
    reviewed = client.post(f"/v1/claims/{claim_id}/review", json=case["given"]["review_action"])
    assert reviewed.json()["status"] == "FINAL_PENDED"

    view = client.get(f"/v1/claims/{claim_id}", headers=PROVIDER).json()

    explanation = view["explanation"]
    assert view["outcome"] == "PARTLY_APPROVED"
    assert explanation["heading"] == "Claim partly approved"
    assert [item["line_no"] for item in explanation["why"]] == [2]
    paid = [line["paid"] for line in explanation["billing"]["lines"]]
    assert paid == [True, False]
    assert explanation["billing"]["lines"][1]["reductions"][0]["text"].startswith("Not paid yet")
