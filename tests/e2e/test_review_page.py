"""P2.5: the review page (frontend/app.py) against the real API and pipeline on the end-to-end
database, for a valid claim and for a claim filed with contract errors (intake response with
`contract_errors`; GET /v1/claims/{id} with `intake: null` and `received`). P5.3: the review
controls (Accept; Submit with every changed line; rule lines read-only; a category choice only
where it is needed; the final amounts and the notice when they changed since review).

Streamlit's in-process test runner drives the page. The page's HTTP client (the one created with a
`base_url`) is the API's TestClient; every other client, such as the health check's, stays real."""

import copy
import json
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from streamlit.testing.v1 import AppTest

from app.api.main import app
from frontend.app import dollars
from tests.e2e.support import E2E_CASES, StubModel, audit, process_case

PAGE = Path(__file__).resolve().parents[2] / "frontend" / "app.py"


def page_on_the_api(monkeypatch: pytest.MonkeyPatch) -> AppTest:
    real_client = httpx.Client

    def client(*args: Any, **kwargs: Any) -> httpx.Client:
        return TestClient(app) if "base_url" in kwargs else real_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "Client", client)
    return AppTest.from_file(str(PAGE), default_timeout=60).run()


def submit_on_the_page(
    api, monkeypatch: pytest.MonkeyPatch, model: StubModel, claim: dict[str, Any]
) -> AppTest:  # noqa: ANN001
    api(model)  # the API's database, model and retriever for this test
    page = page_on_the_api(monkeypatch)
    page.text_area[0].set_value(json.dumps(claim))
    page.toggle[0].set_value(False)  # keep the claim's own ID
    page.button[0].click().run()
    return page


def metric(page: AppTest, label: str) -> str:
    return next(m.value for m in page.metric if m.label == label)


def test_the_page_shows_a_claim_awaiting_review(api, load_case_reference, monkeypatch) -> None:  # noqa: ANN001
    case = E2E_CASES["E2E-14"]
    load_case_reference(case)
    claim = {**copy.deepcopy(case["given"]["claim"]), "claim_id": "CLM-PAGE-VALID"}

    page = submit_on_the_page(
        api, monkeypatch, StubModel(json.dumps(case["given"]["model_answer"])), claim
    )

    assert not page.exception
    assert metric(page, "Status") == "AWAITING_REVIEW"
    assert metric(page, "Review tier") == case["expected"]["recommendation"]["review_tier"]
    assert not page.main.warning and not page.main.error  # the sidebar shows service health
    assert page.subheader[0].value == "Claim CLM-PAGE-VALID"


def test_the_page_shows_a_claim_filed_with_contract_errors(
    api,
    load_case_reference,
    monkeypatch,  # noqa: ANN001
) -> None:
    case = E2E_CASES["E2E-14"]
    load_case_reference(case)
    claim = {**copy.deepcopy(case["given"]["claim"]), "claim_id": "CLM-PAGE-CONTRACT"}
    del claim["service_lines"][0]["procedure_code"]
    model = StubModel("unused")

    page = submit_on_the_page(api, monkeypatch, model, claim)

    assert not page.exception and not page.main.error
    [warning] = page.main.warning  # the sidebar shows service health
    assert "Filed with contract errors" in warning.value
    assert "R01: Required field missing: service_lines.0.procedure_code." in warning.value
    assert metric(page, "Status") == "REJECTED"
    assert metric(page, "Claim decision") == "-" and metric(page, "Plan pays") == "-"
    rules = page.dataframe[0].value
    failed = rules[~rules["passed"]]
    assert list(zip(failed["rule"], failed["reason code"], strict=True)) == [
        ("R01", "RJ_MISSING_FIELD")
    ]
    assert model.prompts == []


# --- Review controls (P5.3) ----------------------------------------------------------------------


def labelled(widgets, label: str):  # noqa: ANN001, ANN201
    return next(w for w in widgets if w.label == label)


def review_page(monkeypatch: pytest.MonkeyPatch, claim_id: str) -> AppTest:
    """The page showing a claim the API already processed."""
    page = page_on_the_api(monkeypatch)
    labelled(page.text_input, "Claim ID").set_value(claim_id)
    return page.run()


def events(client, claim_id: str) -> list[str]:  # noqa: ANN001
    return [e["event_type"] for e in audit(client, claim_id)]


def test_a_reviewer_accepts_on_the_page(api, load_case_reference, monkeypatch) -> None:  # noqa: ANN001
    final = E2E_CASES["E2E-14"]["expected"]["final"]
    client = process_case(api, load_case_reference, "E2E-14")

    page = review_page(monkeypatch, "CLM-E2E-14").run()  # shown twice: opened once

    assert not page.exception and not page.main.error
    assert events(client, "CLM-E2E-14").count("REVIEW_OPENED") == 1
    [decision] = page.selectbox
    assert (decision.label, decision.value) == ("Line 1 decision", "APPROVE")
    labelled(page.button, "Accept").click().run()

    assert not page.exception and not page.main.error
    assert "finalized as FINAL_APPROVED by reviewer-1" in page.success[0].value
    assert metric(page, "Status") == "FINAL_APPROVED"
    assert metric(page, "Plan pays") == dollars(final["amounts"]["totals"]["plan_pays_cents"])
    assert not page.main.info  # the amounts are those shown at review
    assert not page.selectbox and "Accept" not in [b.label for b in page.button]
    assert events(client, "CLM-E2E-14")[-3:] == ["REVIEW_OPENED", "REVIEW_ACCEPTED", "FINALIZED"]
    accepted = audit(client, "CLM-E2E-14")[-2]
    assert accepted["actor"] == "reviewer-1" and accepted["payload"]["review_seconds"] >= 0


def test_a_reviewer_overrides_on_the_page_and_rule_lines_are_read_only(
    api, load_case_reference, monkeypatch
) -> None:  # noqa: ANN001
    """E2E-22: line 1 decided by the model, line 2 denied by a rule (MUE)."""
    client = process_case(api, load_case_reference, "E2E-22")
    page = review_page(monkeypatch, "CLM-E2E-22")
    assert [s.label for s in page.selectbox] == ["Line 1 decision"]  # line 2 is read-only
    assert any("Line 2: DENY by rule (DN_MUE_EXCEEDED)" in c.value for c in page.caption)

    labelled(page.button, "Submit").click().run()
    assert "Change at least one line" in page.main.error[0].value
    labelled(page.selectbox, "Line 1 decision").set_value("DENY").run()
    assert labelled(page.button, "Accept").disabled  # Accept keeps the recommendation
    labelled(page.button, "Submit").click().run()
    assert "needs a reason (line 1)" in page.main.error[0].value
    assert events(client, "CLM-E2E-22")[-1] == "REVIEW_OPENED"  # nothing sent
    labelled(page.text_input, "Line 1 reason").set_value("Reviewed the therapy notes").run()
    labelled(page.button, "Submit").click().run()

    assert not page.exception and not page.main.error
    assert metric(page, "Status") == "FINAL_DENIED"
    [overridden] = [
        e for e in audit(client, "CLM-E2E-22") if e["event_type"] == "REVIEW_OVERRIDDEN"
    ]
    assert [(c["line_no"], c["after"]["decision"]) for c in overridden["payload"]["changes"]] == [
        (1, "DENY")
    ]


def test_the_category_choice_appears_only_where_it_is_needed(
    api, load_case_reference, monkeypatch
) -> None:  # noqa: ANN001
    """E2E-26: a pended colonoscopy (two candidate categories). Approving it shows the choice,
    preset to the model's category."""
    client = process_case(api, load_case_reference, "E2E-26")
    page = review_page(monkeypatch, "CLM-E2E-26")
    assert [s.label for s in page.selectbox] == ["Line 1 decision"]  # PEND: no category choice

    labelled(page.selectbox, "Line 1 decision").set_value("APPROVE").run()
    category = labelled(page.selectbox, "Line 1 benefit category")
    assert (category.value, category.options) == ("ENDOSCOPY", ["ENDOSCOPY", "PREVENTIVE_CARE"])
    category.set_value("PREVENTIVE_CARE")
    labelled(page.text_input, "Line 1 reason").set_value("Screening, not surveillance")
    page.run()
    labelled(page.button, "Submit").click().run()

    assert not page.exception and not page.main.error
    assert metric(page, "Status") == "FINAL_APPROVED"
    assert metric(page, "Member pays") == "$0.00"  # preventive care: no cost share
    assert "The final amounts differ from those shown at review" in page.main.info[0].value
    [overridden] = [
        e for e in audit(client, "CLM-E2E-26") if e["event_type"] == "REVIEW_OVERRIDDEN"
    ]
    assert overridden["payload"]["changes"][0]["after"]["benefit_category"] == "PREVENTIVE_CARE"
