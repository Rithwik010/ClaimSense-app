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
    monkeypatch.setattr(metrics, "ERRORS_REPORT", tmp_path / "errors.json")
    (tmp_path / "errors.json").write_text(
        json.dumps(
            {
                "lines": 416,
                "wrong_lines": 53,
                "direction": {"PEND->APPROVE": 19, "DENY->PEND": 14},
                "by_policy": {"POL-IMG-001": {"lines": 43, "wrong": 10, "directions": {}}},
                "tiers": {"QUICK": {"claims": 84, "with_wrong_line": 14, "wrong_lines": 15}},
            }
        )
    )
    client = api(None, None)

    shown = client.get("/v1/metrics/evaluation").json()

    assert shown["macro_f1_target"] == 0.9 and shown["ocr"] is None
    assert shown["v2_errors"] == {
        "lines": 416,
        "wrong_lines": 53,
        "directions": [
            {"gold": "PEND", "predicted": "APPROVE", "lines": 19},
            {"gold": "DENY", "predicted": "PEND", "lines": 14},
        ],
        "policies": [{"policy_id": "POL-IMG-001", "lines": 43, "wrong": 10}],
        "quick_claims": 84,
        "quick_claims_with_wrong_line": 14,
    }
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


def test_a_record_stored_under_an_older_contract_is_left_out(api, engine) -> None:  # noqa: ANN001
    from datetime import date

    from sqlalchemy.orm import Session

    from app.db.models import Claim, DecisionRecordRow

    with Session(engine) as session:
        session.add(
            Claim(
                claim_id="CLM-OLD-00001",
                member_id="MBR-000001",
                received_date=date(2026, 9, 22),
                source_format="JSON",
                status="AWAITING_REVIEW",
                intake={},
                field_confidences={},
            )
        )
        session.flush()
        session.add(
            DecisionRecordRow(claim_id="CLM-OLD-00001", version=1, record={"claim_id": "x"})
        )
        session.commit()
    client = api(None, None)

    listed = client.get("/v1/claims").json()
    queue = client.get("/v1/review/queue", headers={"X-Role": "reviewer"})

    assert [(c["claim_id"], c["total_allowed_cents"]) for c in listed] == [("CLM-OLD-00001", None)]
    assert queue.status_code == 200 and queue.json() == []


def test_a_plan_is_returned_with_its_benefits_and_exclusions(api) -> None:  # noqa: ANN001
    client = api(None, None)

    plan = client.get("/v1/plans/PLN-PPO-GOLD")
    missing = client.get("/v1/plans/PLN-NOPE")

    assert plan.status_code == 200 and missing.status_code == 404
    body = plan.json()
    assert body["plan_id"] == "PLN-PPO-GOLD" and body["benefits"]
    assert all(isinstance(b["covered"], bool) for b in body["benefits"])


def test_the_results_file_is_served_once_written(api, tmp_path, monkeypatch) -> None:  # noqa: ANN001
    client = api(None, None)
    monkeypatch.setattr(metrics, "RESULTS", tmp_path / "results.json")

    assert client.get("/v1/metrics/results").status_code == 404
    (tmp_path / "results.json").write_text('{"reviewer_agreement": "not measured"}')
    assert client.get("/v1/metrics/results").json() == {"reviewer_agreement": "not measured"}
