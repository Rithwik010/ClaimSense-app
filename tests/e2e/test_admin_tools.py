"""Logins, users, audit search, notifications, the quality numbers, the policy library, the
member's plan summary and the notice of another reviewer (D-AUTH-2, D-AUD-1, D-NTF-1, D-QLT-1,
D-POL-9, D-MEM-3, D-REV-10), through the API."""

from datetime import UTC, datetime
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import Engine

from tests.e2e.support import (
    E2E_CASES,
    NO_SESSION,
    PROVIDER,
    REVIEWER,
    TEST_PASSWORD,
    add_member_user,
    bearer,
    process_case,
)

ADMIN = bearer("admin-test")


def login(client: TestClient, username: str, password: str) -> Any:  # noqa: ANN401
    return client.post(
        "/v1/auth/login", json={"username": username, "password": password}, headers=NO_SESSION
    )


def user(client: TestClient, username: str) -> dict[str, Any]:
    users = client.get("/v1/users", headers=ADMIN).json()
    return next(u for u in users if u["username"] == username)


# --- Logins and users (D-AUTH-2) -----------------------------------------------------------------


def test_five_failed_logins_lock_the_login_until_an_admin_unlocks_it(
    api, load_case_reference
) -> None:  # noqa: ANN001, E501
    client = process_case(api, load_case_reference, "E2E-14")
    for _ in range(5):
        assert login(client, "reviewer-1", "wrong password").status_code == 401

    locked = login(client, "reviewer-1", TEST_PASSWORD)  # right, but locked

    assert locked.status_code == 429
    assert "ask your administrator to unlock" in locked.json()["detail"]
    assert 0 < int(locked.headers["retry-after"]) <= 15 * 60
    assert user(client, "reviewer-1")["locked_until"] is not None
    assert client.post("/v1/users/reviewer-1/unlock", headers=ADMIN).status_code == 204
    assert user(client, "reviewer-1")["locked_until"] is None
    assert login(client, "reviewer-1", TEST_PASSWORD).status_code == 200


def test_a_successful_login_clears_the_failed_count(api, load_case_reference) -> None:  # noqa: ANN001
    client = process_case(api, load_case_reference, "E2E-14")
    for _ in range(4):
        login(client, "reviewer-a", "wrong password")
    assert login(client, "reviewer-a", TEST_PASSWORD).status_code == 200
    for _ in range(4):
        login(client, "reviewer-a", "wrong password")
    assert login(client, "reviewer-a", TEST_PASSWORD).status_code == 200  # never five in a row


def test_an_admin_creates_users_by_the_rules(api, load_case_reference) -> None:  # noqa: ANN001
    client = process_case(api, load_case_reference, "E2E-14")
    new = {"username": "reviewer-new", "role": "reviewer", "password": "a long enough one"}

    created = client.post("/v1/users", json=new, headers=ADMIN)

    assert created.status_code == 201, created.text
    assert {k: created.json()[k] for k in ("username", "role", "active")} == {
        "username": "reviewer-new",
        "role": "reviewer",
        "active": True,
    }
    assert "password_hash" not in created.text
    assert login(client, "reviewer-new", "a long enough one").status_code == 200
    refused = [
        new,  # the username is taken
        {**new, "username": "short-one", "password": "too short"},
        {**new, "username": "same-name", "password": "same-name"},  # 9 letters, and the name
        {**new, "username": "provider-x", "role": "provider"},  # no NPI on file
        {**new, "username": "member-x", "role": "member", "member_id": "MBR-NOBODY"},
        {**new, "username": "bad name!"},
    ]
    for body in refused:
        response = client.post("/v1/users", json=body, headers=ADMIN)
        assert response.status_code == 422, (body, response.text)


def test_users_change_their_own_password(api, load_case_reference) -> None:  # noqa: ANN001
    client = process_case(api, load_case_reference, "E2E-14")
    change = {"current_password": "not the password", "new_password": "a brand new password"}
    assert client.post("/v1/auth/password", json=change, headers=REVIEWER).status_code == 422

    changed = client.post(
        "/v1/auth/password", json={**change, "current_password": TEST_PASSWORD}, headers=REVIEWER
    )

    assert changed.status_code == 204, changed.text
    assert login(client, "reviewer-golden", TEST_PASSWORD).status_code == 401
    assert login(client, "reviewer-golden", "a brand new password").status_code == 200
    assert user(client, "reviewer-golden")["password_changed_at"] is not None


def test_an_admin_deactivates_and_resets_but_not_their_own_login(api, load_case_reference) -> None:  # noqa: ANN001, E501
    client = process_case(api, load_case_reference, "E2E-14")
    own = client.post("/v1/users/admin-test/active", json={"active": False}, headers=ADMIN)
    assert own.status_code == 422
    off = client.post("/v1/users/reviewer-b/active", json={"active": False}, headers=ADMIN)
    assert off.status_code == 204
    assert login(client, "reviewer-b", TEST_PASSWORD).status_code == 401
    assert client.get("/v1/auth/me", headers=bearer("reviewer-b")).status_code == 401
    client.post("/v1/users/reviewer-b/active", json={"active": True}, headers=ADMIN)
    reset = client.post(
        "/v1/users/reviewer-b/password", json={"password": "set by the admin"}, headers=ADMIN
    )
    assert reset.status_code == 204
    assert login(client, "reviewer-b", "set by the admin").status_code == 200
    missing = client.post("/v1/users/nobody/unlock", headers=ADMIN)
    assert missing.status_code == 404


# --- Audit search (D-AUD-1) ----------------------------------------------------------------------


def test_audit_search_by_claim_actor_event_and_day(api, load_case_reference) -> None:  # noqa: ANN001
    load_case_reference(E2E_CASES["E2E-03"])
    client = process_case(api, load_case_reference, "E2E-14")
    client.post("/v1/claims/intake", json=E2E_CASES["E2E-03"]["given"]["claim"])
    client.post("/v1/claims/CLM-E2E-03/process")

    def search(**params: Any) -> list[dict[str, Any]]:  # noqa: ANN401
        response = client.get("/v1/audit/events", params=params, headers=ADMIN)
        assert response.status_code == 200, response.text
        return response.json()["events"]

    one = search(claim_id="CLM-E2E-03")
    assert one and {e["claim_id"] for e in one} == {"CLM-E2E-03"}
    assert [e["id"] for e in one] == sorted((e["id"] for e in one), reverse=True)  # newest first
    rules = search(event_type="RULES_EVALUATED")
    assert {e["claim_id"] for e in rules} == {"CLM-E2E-03", "CLM-E2E-14"}
    assert {e["actor"] for e in search(actor="provider-test")} == {"provider-test"}
    today = datetime.now(UTC).date().isoformat()
    assert len(search(since=today, until=today)) == len(search())
    assert search(until="2000-01-01") == []
    assert len(search(limit=2)) == 2
    bad = client.get("/v1/audit/events", params={"event_type": "NOPE"}, headers=ADMIN)
    assert bad.status_code == 422


# --- Notifications (D-NTF-1) ---------------------------------------------------------------------


def test_each_role_is_notified_of_its_own_claims(api, load_case_reference, engine: Engine) -> None:  # noqa: ANN001, E501
    load_case_reference(E2E_CASES["E2E-03"])
    client = process_case(api, load_case_reference, "E2E-14")  # to review: the model's answer
    client.post("/v1/claims/intake", json=E2E_CASES["E2E-03"]["given"]["claim"])
    client.post("/v1/claims/CLM-E2E-03/process")  # returned by a rule: final at once

    def items(headers: dict[str, str], **params: Any) -> list[dict[str, Any]]:  # noqa: ANN401
        response = client.get("/v1/notifications", params=params, headers=headers)
        assert response.status_code == 200, response.text
        return response.json()["items"]

    provider = items(PROVIDER)
    assert [(n["claim_id"], n["event_type"], n["outcome"]) for n in provider] == [
        ("CLM-E2E-03", "AUTO_OUTCOME", "REJECTED")
    ]
    assert items(bearer("provider-other")) == []
    reviewer = items(REVIEWER)
    assert [(n["claim_id"], n["event_type"]) for n in reviewer] == [
        ("CLM-E2E-14", "SLM_RECOMMENDED")
    ]
    assert items(REVIEWER, after=reviewer[0]["id"]) == []
    member = add_member_user(engine, E2E_CASES["E2E-03"]["given"]["claim"]["member_id"])
    assert [n["claim_id"] for n in items(member)] == ["CLM-E2E-03"]
    other_member = add_member_user(
        engine, E2E_CASES["E2E-14"]["given"]["claim"]["member_id"], username="member-14"
    )
    assert items(other_member) == []  # their claim is in review: nothing until it is final


# --- Quality numbers (D-QLT-1) -------------------------------------------------------------------


def test_review_quality_and_the_overview_from_the_reviews_on_file(api, load_case_reference) -> None:  # noqa: ANN001, E501
    process_case(api, load_case_reference, "E2E-15")  # each with its own model answer
    client = process_case(api, load_case_reference, "E2E-24")
    client.post("/v1/claims/CLM-E2E-24/review", json=E2E_CASES["E2E-24"]["given"]["review_action"])
    client.post("/v1/claims/CLM-E2E-15/review", json=E2E_CASES["E2E-15"]["given"]["review_action"])

    quality = client.get("/v1/metrics/quality", headers=ADMIN).json()

    # Two model lines, both recommended APPROVE: one accepted, one denied on review (worked: 1 of
    # 2 accepted = 5000 basis points).
    assert (quality["overall"]["lines"], quality["overall"]["overridden"]) == (2, 1)
    assert quality["acceptance_rate_bp"] == 5000
    assert quality["matrix"] == {"APPROVE": {"APPROVE": 1, "DENY": 1}}
    assert [r["reviewer"] for r in quality["by_reviewer"]] == ["reviewer-golden"]
    assert quality["appeals"] == {"open": 0, "upheld": 0, "changed": 0}

    overview = client.get("/v1/metrics/overview", headers=ADMIN).json()
    extras = overview["extras"]
    assert overview["not_processed"] == 0
    assert extras["decided_claims"] == 2
    assert extras["override_rate_bp"] == 5000
    assert len(extras["daily"]) == 14
    assert sum(day["received"] for day in extras["daily"]) == 2
    assert extras["billed_cents"] >= extras["plan_paid_cents"] >= 0


# --- The policy library (D-POL-9) ----------------------------------------------------------------


def test_the_policy_library_lists_each_policy_with_its_criteria(api, load_case_reference) -> None:  # noqa: ANN001, E501
    client = process_case(api, load_case_reference, "E2E-14")
    listed = client.get("/v1/policies", headers=PROVIDER).json()
    assert listed and all(p["codes"] and p["criteria"] > 0 for p in listed)
    first = listed[0]

    detail = client.get(f"/v1/policies/{first['policy_id']}", headers=PROVIDER).json()

    assert detail["policy_id"] == first["policy_id"]
    assert len(detail["items"]) == first["criteria"]
    assert all(item["text"] and item["source"] for item in detail["items"])
    assert client.get("/v1/policies/POL-NOPE", headers=PROVIDER).status_code == 404


# --- The member's plan summary and benefits (P3.2, D-MEM-3) ---------------------------------------


def test_the_member_reads_their_plans_summary(api, load_case_reference, engine: Engine) -> None:  # noqa: ANN001
    client = process_case(api, load_case_reference, "E2E-14")
    member = add_member_user(engine, E2E_CASES["E2E-14"]["given"]["claim"]["member_id"])

    summary = client.get("/v1/member/plan-summary", headers=member).json()

    assert "Summary of Benefits and Coverage" in summary["title"]
    headings = [s["heading"] for s in summary["sections"]]
    assert "What you pay for covered services" in headings
    table = next(b for s in summary["sections"] for b in s["blocks"] if b["kind"] == "table")
    assert table["header"][0] == "Service" and table["rows"]
    benefits = client.get("/v1/member/benefits", headers=member).json()
    network = benefits["networks"][0]
    assert network["deductible_left_cents"] + network["deductible_met_cents"] in (
        network["deductible_cents"],
        network["deductible_met_cents"],  # met past the limit: nothing left
    )


# --- Another reviewer has the claim open (D-REV-10) ----------------------------------------------


def test_a_reviewer_is_told_who_else_has_the_claim_open(api, load_case_reference) -> None:  # noqa: ANN001
    client = process_case(api, load_case_reference, "E2E-14")
    first = client.post(
        "/v1/claims/CLM-E2E-14/review/open", json={"reviewer_id": "reviewer-golden"}
    ).json()
    assert first["others"] == []

    second = client.post(
        "/v1/claims/CLM-E2E-14/review/open", json={"reviewer_id": "reviewer-a"}
    ).json()

    assert [o["reviewer_id"] for o in second["others"]] == ["reviewer-golden"]
    seen = client.get("/v1/claims/CLM-E2E-14/review/others", headers=REVIEWER).json()
    assert [o["reviewer_id"] for o in seen] == ["reviewer-a"]
    action = E2E_CASES["E2E-14"]["given"].get("review_action") or {
        "claim_id": "CLM-E2E-14",
        "reviewer_id": "reviewer-a",
        "action": "ACCEPT",
        "line_overrides": [],
        "reason": None,
        "timestamp": datetime.now(UTC).isoformat(),
    }
    client.post("/v1/claims/CLM-E2E-14/review", json={**action, "reviewer_id": "reviewer-a"})
    assert client.get("/v1/claims/CLM-E2E-14/review/others", headers=REVIEWER).json() == []
