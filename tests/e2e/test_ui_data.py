"""P8 UI pass: the read-only data the pages show, from the API (no contract change). The review
queue's columns and flags, the steps a provider sees while their claim is in review, the codes on
the claim list, the admin overview counts and the versions the decision records name."""

import json

from app.calculator import CALCULATOR_VERSION
from app.rules import RULES_VERSION
from tests.e2e.support import (
    ADMIN,
    E2E_CASES,
    PROVIDER,
    REVIEWER,
    CaseRetriever,
    StubModel,
    process_case,
)

QUICK = "CLM-E2E-14"  # awaiting quick review
RULE_DENIED = E2E_CASES["E2E-05"]["given"]["claim"]["claim_id"]  # DENIED_BY_RULE (R05)


def accept(claim_id: str) -> dict:
    return {
        "claim_id": claim_id,
        "reviewer_id": "reviewer-golden",
        "action": "ACCEPT",
        "timestamp": "2026-10-11T10:00:00Z",
    }


def test_the_queue_shows_provider_service_date_billed_lines_and_flags(
    api, load_case_reference
) -> None:  # noqa: ANN001, E501
    client = process_case(api, load_case_reference, "E2E-14")
    claim = E2E_CASES["E2E-14"]["given"]["claim"]
    record = client.get(f"/v1/claims/{QUICK}", headers=REVIEWER).json()["record"]

    (item,) = client.get("/v1/review/queue", headers=REVIEWER).json()

    assert item["provider_npi"] == claim["billing_npi"]
    assert item["service_date"] == min(line["date_of_service"] for line in claim["service_lines"])
    assert item["lines"] == len(claim["service_lines"])
    assert item["total_billed_cents"] == record["amounts"]["totals"]["billed_cents"]
    assert item["flags"] == []  # a clean quick claim
    assert set(item) >= {"provider_name", "review_tier", "processed"}


def test_an_unusable_model_answer_is_flagged(api, load_case_reference) -> None:  # noqa: ANN001
    case = E2E_CASES["E2E-14"]
    load_case_reference(case)
    client = api(StubModel("The visit looks fine to me."), CaseRetriever(case))
    assert client.post("/v1/claims/intake", json=case["given"]["claim"]).status_code == 201
    assert client.post(f"/v1/claims/{QUICK}/process").status_code == 200

    (item,) = client.get("/v1/review/queue", headers=REVIEWER).json()

    assert item["review_tier"] == "FULL" and "MODEL_ANSWER_UNUSABLE" in item["flags"]


def test_a_provider_sees_the_steps_of_a_claim_in_review_and_nothing_more(
    api, load_case_reference
) -> None:  # noqa: ANN001, E501
    client = process_case(api, load_case_reference, "E2E-14")

    view = client.get(f"/v1/claims/{QUICK}", headers=PROVIDER).json()

    assert view["stages"] == [
        "INTAKE_COMPLETED",
        "RULES_EVALUATED",
        "CONTEXT_ASSEMBLED",
        "SLM_RECOMMENDED",
        "CALCULATED",
        "EXPLANATION_BUILT",
    ]
    assert view["explanation"] is None and "record" not in view
    assert "APPROVE" not in json.dumps(view["stages"])


def test_the_claim_list_carries_the_codes_of_rule_outcomes(api, load_case_reference) -> None:  # noqa: ANN001
    client = process_case(api, load_case_reference, "E2E-05")

    (listed,) = client.get("/v1/claims", headers=REVIEWER).json()

    assert listed["claim_id"] == RULE_DENIED and listed["status"] == "DENIED_BY_RULE"
    codes = [c for a in listed["adjustments"] for c in a["codes"]]
    assert codes and codes[0]["kind"] == "CARC"
    assert listed["adjustments"][0]["reason_code"] == "DN_NOT_ELIGIBLE"


def test_the_admin_overview_counts_the_claims_on_file(api, load_case_reference) -> None:  # noqa: ANN001
    client = process_case(api, load_case_reference, "E2E-14")
    process_case(api, load_case_reference, "E2E-05")
    assert client.get("/v1/metrics/overview", headers=REVIEWER).status_code == 403

    before = client.get("/v1/metrics/overview", headers=ADMIN).json()
    assert client.post(f"/v1/claims/{QUICK}/review", json=accept(QUICK)).status_code == 200
    after = client.get("/v1/metrics/overview", headers=ADMIN).json()

    assert before["claims"] == 2 and before["decided_by_rules"] == 1
    assert before["queue_by_tier"] == {"QUICK": 1, "STANDARD": 0, "FULL": 0}
    assert before["final_outcomes"] == {"DENIED_BY_RULE": 1}
    assert (before["reviewed_accepted"], before["reviewed_overridden"]) == (0, 0)
    assert after["queue_by_tier"]["QUICK"] == 0 and after["reviewed_accepted"] == 1
    assert after["final_outcomes"] == {"DENIED_BY_RULE": 1, "FINAL_APPROVED": 1}


def test_system_status_names_the_versions_in_the_decision_records(api, load_case_reference) -> None:  # noqa: ANN001, E501
    client = process_case(api, load_case_reference, "E2E-14")
    assert client.get("/v1/metrics/system", headers=REVIEWER).status_code == 403

    shown = client.get("/v1/metrics/system", headers=ADMIN).json()

    assert shown["configured"]["rules"] == RULES_VERSION
    assert shown["configured"]["calculator"] == CALCULATOR_VERSION
    (used,) = shown["in_records"]
    assert used["rules_version"] == RULES_VERSION and used["model_name"] == "stub-model"
    assert used["records"] == 1 and isinstance(used["policy_versions"], list)  # none: no criteria
