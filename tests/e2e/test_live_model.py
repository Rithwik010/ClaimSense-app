"""P1.5 acceptance with the real model: the sample claim runs end to end through the base model.

Opt-in, because it needs Ollama with MODEL_NAME pulled and takes seconds to minutes:

    CLAIMSENSE_LIVE_MODEL=1 uv run pytest tests/e2e/test_live_model.py

Whether the base model's answer is right is measured in P4.2. This test checks that the pipeline
completes with whatever the model returns and that the record is consistent.
"""

import json
import os
from pathlib import Path

import pytest

from app.core.settings import get_settings
from app.domain.contracts import DecisionRecord
from app.ml.client import OllamaDecisionModel
from tests.e2e.support import E2E_CASES

pytestmark = pytest.mark.skipif(
    os.environ.get("CLAIMSENSE_LIVE_MODEL") != "1", reason="set CLAIMSENSE_LIVE_MODEL=1"
)

SAMPLE = Path(__file__).resolve().parent / "sample_claim.json"


def test_sample_claim_runs_through_the_base_model(api, load_case_reference) -> None:
    load_case_reference(E2E_CASES["E2E-14"])  # the sample is the E2E-14 claim under a new ID
    settings = get_settings()
    client = api(OllamaDecisionModel(settings.ollama_url, settings.model_name))
    claim = json.loads(SAMPLE.read_text())

    assert client.post("/v1/claims/intake", json=claim).status_code == 201
    response = client.post(f"/v1/claims/{claim['claim_id']}/process")

    assert response.status_code == 200, response.text
    record = DecisionRecord.model_validate(response.json())
    assert record.status.value == "AWAITING_REVIEW"
    assert record.versions.model_name == settings.model_name
    assert [d.line_no for d in record.line_decisions] == [1]
    assert record.line_decisions[0].source in {"MODEL", "VALIDATION"}
    assert (record.slm_output is not None) or record.output_errors
    assert record.amounts is not None and record.review_tier is not None
    events = [e["event_type"] for e in client.get(f"/v1/claims/{claim['claim_id']}/audit").json()]
    assert events[:3] == ["INTAKE_COMPLETED", "RULES_EVALUATED", "CONTEXT_ASSEMBLED"]
    assert events[3] in {"SLM_RECOMMENDED", "OUTPUT_INVALID"}
    assert events[4:] == ["CALCULATED"]
