"""P2.5: the review page (frontend/app.py) against the real API and pipeline on the end-to-end
database, for a valid claim and for a claim filed with contract errors (intake response with
`contract_errors`; GET /v1/claims/{id} with `intake: null` and `received`).

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
from tests.e2e.support import E2E_CASES, StubModel

PAGE = Path(__file__).resolve().parents[2] / "frontend" / "app.py"


def submit_on_the_page(
    api, monkeypatch: pytest.MonkeyPatch, model: StubModel, claim: dict[str, Any]
) -> AppTest:  # noqa: ANN001
    api(model)  # the API's database, model and retriever for this test
    real_client = httpx.Client

    def client(*args: Any, **kwargs: Any) -> httpx.Client:
        return TestClient(app) if "base_url" in kwargs else real_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "Client", client)
    page = AppTest.from_file(str(PAGE), default_timeout=60).run()
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
