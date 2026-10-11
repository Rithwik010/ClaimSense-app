"""D-AUTH-1: logins and who may do what. Every endpoint for every role (allowed, or 403), not
logged in (401), a provider opening another provider's claim (404), what a provider sees before
and after a claim is final, the session cookie, and expired, tampered or stale tokens (401)."""

from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
import pytest
from sqlalchemy import Engine, update
from sqlalchemy.orm import Session

from app.auth.tokens import COOKIE, SESSION_HOURS, create_token
from app.db.models import User
from tests.e2e.support import (
    ADMIN,
    E2E_CASES,
    NO_SESSION,
    PROVIDER,
    REVIEWER,
    TEST_PASSWORD,
    TEST_SECRET,
    StubModel,
    bearer,
    process_case,
)

CLAIM = "CLM-E2E-14"  # filed and processed by the test provider; awaiting QUICK review
WHO = {"provider": PROVIDER, "reviewer": REVIEWER, "admin": ADMIN}


def endpoints() -> list[tuple[str, str, dict[str, Any], set[str]]]:
    """(method, path, request arguments, the roles allowed). The bodies are valid enough to pass
    authorization; what comes after (409, 422) does not matter here."""
    claim = E2E_CASES["E2E-14"]["given"]["claim"]
    wrong_claim = {  # a review of another claim: refused (422) after the role check
        "claim_id": "CLM-OTHER",
        "reviewer_id": "reviewer-golden",
        "action": "ACCEPT",
        "timestamp": "2026-10-11T10:00:00Z",
    }
    everyone = {"provider", "reviewer", "admin"}
    staff = {"reviewer", "admin"}
    return [
        ("POST", "/v1/claims/intake", {"json": claim}, {"provider"}),
        ("POST", "/v1/claims/intake/file", {"content": b"not a claim"}, {"provider"}),
        ("POST", f"/v1/claims/{CLAIM}/process", {}, {"provider"}),
        ("GET", "/v1/claims", {}, everyone),
        ("GET", f"/v1/claims/{CLAIM}", {}, everyone),
        ("GET", f"/v1/claims/{CLAIM}/explanation", {}, everyone),
        ("GET", f"/v1/claims/{CLAIM}/audit", {}, staff),
        ("GET", "/v1/review/queue", {}, staff),
        ("GET", "/v1/plans/PLN-PPO-GOLD", {}, staff),
        ("GET", "/v1/metrics/evaluation", {}, {"admin"}),
        ("GET", "/v1/metrics/results", {}, {"admin"}),
        (
            "POST",
            f"/v1/claims/{CLAIM}/review/open",
            {"json": {"reviewer_id": "reviewer-golden"}},
            {"reviewer"},
        ),
        ("POST", f"/v1/claims/{CLAIM}/review", {"json": wrong_claim}, {"reviewer"}),
        ("GET", "/v1/auth/me", {}, everyone),
    ]


def test_every_endpoint_for_every_role(api, load_case_reference) -> None:  # noqa: ANN001
    client = process_case(api, load_case_reference, "E2E-14")
    for method, path, kwargs, allowed in endpoints():
        for role, headers in WHO.items():
            response = client.request(method, path, headers=headers, **kwargs)
            if role in allowed:
                assert response.status_code not in (401, 403), (method, path, role, response.text)
            else:
                assert response.status_code == 403, (method, path, role, response.text)
        response = client.request(method, path, headers=NO_SESSION, **kwargs)
        assert response.status_code == 401, (method, path, "not logged in")
        assert response.headers["www-authenticate"] == "Bearer"


def test_only_login_logout_and_health_are_public(api) -> None:  # noqa: ANN001
    client = api(StubModel("unused"))
    assert client.get("/health", headers=NO_SESSION).status_code == 200
    assert client.post("/v1/auth/logout", headers=NO_SESSION).status_code == 204
    login = {"username": "nobody", "password": "x"}
    assert client.post("/v1/auth/login", json=login, headers=NO_SESSION).status_code == 401
    assert client.get("/docs", headers=NO_SESSION).status_code == 404
    assert client.get("/openapi.json", headers=NO_SESSION).status_code == 404


def test_a_provider_cannot_open_another_providers_claim(api, load_case_reference) -> None:  # noqa: ANN001
    client = process_case(api, load_case_reference, "E2E-14")  # filed by provider-test
    other = bearer("provider-other")

    for method, path in (
        ("GET", f"/v1/claims/{CLAIM}"),
        ("GET", f"/v1/claims/{CLAIM}/explanation"),
        ("POST", f"/v1/claims/{CLAIM}/process"),
    ):
        response = client.request(method, path, headers=other)
        assert response.status_code == 404, (method, path)  # as if it did not exist
        assert response.json()["detail"] == f"claim {CLAIM} not found"
    assert client.get("/v1/claims", headers=other).json() == []
    assert [c["claim_id"] for c in client.get("/v1/claims", headers=PROVIDER).json()] == [CLAIM]


def test_a_provider_sees_in_review_until_the_decision_is_final(api, load_case_reference) -> None:  # noqa: ANN001
    client = process_case(api, load_case_reference, "E2E-14")

    view = client.get(f"/v1/claims/{CLAIM}", headers=PROVIDER).json()
    assert (view["status"], view["final"], view["record"]) == ("IN_REVIEW", False, None)
    assert view["filed_by"] == "provider-test" and "review_tier" not in str(view)
    listed = client.get("/v1/claims", headers=PROVIDER).json()[0]
    assert (listed["status"], listed["claim_decision"], listed["total_allowed_cents"]) == (
        "IN_REVIEW",
        None,
        None,
    )
    explanation = client.get(f"/v1/claims/{CLAIM}/explanation", headers=PROVIDER)
    assert explanation.status_code == 409

    accept = {
        "claim_id": CLAIM,
        "reviewer_id": "reviewer-golden",
        "action": "ACCEPT",
        "timestamp": "2026-10-11T10:00:00Z",
    }
    assert client.post(f"/v1/claims/{CLAIM}/review", json=accept).status_code == 200

    view = client.get(f"/v1/claims/{CLAIM}", headers=PROVIDER).json()
    assert (view["status"], view["final"]) == ("FINAL_APPROVED", True)
    assert view["record"]["review"]["reviewer_id"] == "reviewer-golden"
    listed = client.get("/v1/claims", headers=PROVIDER).json()[0]
    assert listed["claim_decision"] == "APPROVE" and listed["total_allowed_cents"] is not None
    assert client.get(f"/v1/claims/{CLAIM}/explanation", headers=PROVIDER).status_code == 200


def test_a_rule_outcome_is_final_for_the_provider_at_once(api, load_case_reference) -> None:  # noqa: ANN001
    client = process_case(api, load_case_reference, "E2E-05")  # DENIED_BY_RULE
    claim_id = E2E_CASES["E2E-05"]["given"]["claim"]["claim_id"]
    view = client.get(f"/v1/claims/{claim_id}", headers=PROVIDER).json()
    assert (view["status"], view["final"]) == ("DENIED_BY_RULE", True)
    assert view["record"]["status"] == "DENIED_BY_RULE" and view["adjustments"]


def test_review_actions_name_the_logged_in_reviewer(api, load_case_reference) -> None:  # noqa: ANN001
    client = process_case(api, load_case_reference, "E2E-14")
    url = f"/v1/claims/{CLAIM}/review/open"
    as_other = client.post(url, json={"reviewer_id": "reviewer-1"}, headers=REVIEWER)
    assert as_other.status_code == 403
    assert client.post(url, json={"reviewer_id": "reviewer-golden"}, headers=REVIEWER).json()
    events = client.get(f"/v1/claims/{CLAIM}/audit").json()
    assert (events[-1]["event_type"], events[-1]["actor"]) == ("REVIEW_OPENED", "reviewer-golden")
    assert events[0]["actor"] == "provider-test"  # INTAKE_COMPLETED: the provider who filed it


def test_login_sets_an_http_only_strict_cookie_for_eight_hours(api) -> None:  # noqa: ANN001
    client = api(StubModel("unused"))
    wrong = client.post(
        "/v1/auth/login",
        json={"username": "reviewer-1", "password": "wrong"},
        headers=NO_SESSION,
    )
    assert wrong.status_code == 401 and COOKIE not in wrong.cookies

    login = client.post(
        "/v1/auth/login",
        json={"username": "reviewer-1", "password": TEST_PASSWORD},
        headers=NO_SESSION,
    )

    assert login.status_code == 200, login.text
    assert login.json() == {
        "username": "reviewer-1",
        "display_name": "Reviewer 1",
        "role": "reviewer",
        "provider_id": None,
    }
    cookie = login.headers["set-cookie"]
    for attribute in ("HttpOnly", "SameSite=strict", f"Max-Age={SESSION_HOURS * 3600}", "Path=/"):
        assert attribute.lower() in cookie.lower(), cookie
    assert client.get("/v1/auth/me", headers=NO_SESSION).json()["username"] == "reviewer-1"
    assert client.get("/v1/review/queue", headers=NO_SESSION).status_code == 200  # by cookie

    assert client.post("/v1/auth/logout", headers=NO_SESSION).status_code == 204
    assert client.get("/v1/auth/me", headers=NO_SESSION).status_code == 401


@pytest.mark.parametrize(
    "token",
    [
        "not-a-token",
        create_token("reviewer-1", "reviewer", "another secret entirely, not the test one"),
        create_token(
            "reviewer-1", "reviewer", TEST_SECRET, now=datetime.now(UTC) - timedelta(hours=9)
        ),
        jwt.encode({"sub": "reviewer-1", "role": "reviewer"}, TEST_SECRET, algorithm="HS256"),
        create_token("reviewer-1", "admin", TEST_SECRET),  # the role is not the user's
        create_token("someone-else", "reviewer", TEST_SECRET),  # no such user
    ],
    ids=["garbage", "other-key", "expired", "no-expiry", "wrong-role", "unknown-user"],
)
def test_an_invalid_token_is_401(api, token: str) -> None:  # noqa: ANN001
    client = api(StubModel("unused"))
    response = client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


def test_a_tampered_token_is_401(api) -> None:  # noqa: ANN001
    client = api(StubModel("unused"))
    header, payload, signature = create_token("reviewer-1", "reviewer", TEST_SECRET).split(".")
    admin = jwt.encode({"sub": "reviewer-1", "role": "admin"}, "x", algorithm="HS256")
    forged = f"{header}.{admin.split('.')[1]}.{signature}"  # admin claims, reviewer signature
    assert (
        client.get("/v1/auth/me", headers={"Authorization": f"Bearer {forged}"}).status_code == 401
    )
    assert (
        client.get(
            "/v1/auth/me", headers={"Authorization": f"Bearer {header}.{payload}."}
        ).status_code
        == 401
    )


def test_a_deactivated_user_is_logged_out(api, engine: Engine) -> None:  # noqa: ANN001
    client = api(StubModel("unused"))
    assert client.get("/v1/auth/me", headers=bearer("reviewer-1")).status_code == 200
    with Session(engine) as session:
        session.execute(update(User).where(User.username == "reviewer-1").values(active=False))
        session.commit()
    assert client.get("/v1/auth/me", headers=bearer("reviewer-1")).status_code == 401
    login = {"username": "reviewer-1", "password": TEST_PASSWORD}
    assert client.post("/v1/auth/login", json=login, headers=NO_SESSION).status_code == 401
