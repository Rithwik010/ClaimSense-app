"""P5.5: the claim list (GET /v1/claims) and the evaluation results (GET /v1/metrics/evaluation)
the UI shows."""

import json

from app.api import metrics
from tests.e2e.support import E2E_CASES, process_case


def test_claims_are_listed_with_their_status_totals_and_failed_rules(
    api, load_case_reference
) -> None:  # noqa: ANN001, E501
    client = process_case(api, load_case_reference, "E2E-01")
    rejected = E2E_CASES["E2E-01"]["given"]["claim"]["claim_id"]

    every = client.get("/v1/claims").json()
    rule_outcomes = client.get(
        "/v1/claims", params=[("status", "REJECTED"), ("status", "DENIED_BY_RULE")]
    ).json()
    none = client.get("/v1/claims", params={"status": "FINAL_APPROVED"}).json()

    assert [c["claim_id"] for c in every] == [rejected]
    assert rule_outcomes[0]["status"] == "REJECTED"
    failed = rule_outcomes[0]["failed_rules"]
    assert failed and all(r["outcome"] == "REJECT" and r["reason_code"] for r in failed)
    assert none == []


def test_the_evaluation_lists_each_model_report_with_its_targets(
    api, tmp_path, monkeypatch
) -> None:  # noqa: ANN001, E501
    report = {
        "model": "claimsense-decision:v1",
        "prompt": "decision_v2",
        "metrics": {
            "records": 300,
            "valid_output_rate": 0.9167,
            "decisions": {
                "accuracy": 0.7188,
                "macro_f1": 0.694,
                "per_class": {"DENY": {"precision": 0.7966}},
            },
            "criterion_status_accuracy": 0.7608,
            "latency_ms": {"p50": 6444, "p95": 46738},
        },
    }
    (tmp_path / "v1.json").write_text(json.dumps(report))
    monkeypatch.setattr(metrics, "MODEL_REPORTS", (tmp_path / "v1.json", tmp_path / "v2.json"))
    monkeypatch.setattr(metrics, "OCR_REPORT", tmp_path / "missing.json")
    client = api(None, None)

    shown = client.get("/v1/metrics/evaluation").json()

    assert shown["macro_f1_target"] == 0.9 and shown["ocr"] is None
    assert shown["models"] == [
        {
            "model": "claimsense-decision:v1",
            "prompt": "decision_v2",
            "records": 300,
            "valid_output": 0.9167,
            "line_accuracy": 0.7188,
            "macro_f1": 0.694,
            "criterion_accuracy": 0.7608,
            "deny_precision": 0.7966,
            "median_ms_per_claim": 6444,
        }
    ]
