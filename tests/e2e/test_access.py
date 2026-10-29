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
        (
            "POST",
            "/v1/claims/intake/files",
            {"json": {"files": [{"name": "a.pdf", "content_base64": "bm90IGEgY2xhaW0="}]}},
            {"provider"},
        ),
        ("POST", f"/v1/claims/{CLAIM}/process", {}, {"provider"}),
        ("GET", "/v1/claims", {}, everyone),
        ("GET", f"/v1/claims/{CLAIM}", {}, everyone),
        ("GET", f"/v1/claims/{CLAIM}/explanation", {}, everyone),
        ("GET", f"/v1/claims/{CLAIM}/document", {}, everyone),
        ("GET", f"/v1/claims/{CLAIM}/document/1", {}, everyone),
        ("GET", f"/v1/claims/{CLAIM}/audit", {}, staff),
        ("GET", f"/v1/claims/{CLAIM}/form", {}, everyone),
        ("GET", f"/v1/claims/{CLAIM}/check", {}, {"provider"}),
        (
            "POST",
            f"/v1/claims/{CLAIM}/corrections",
            {"json": {"corrections": [{"field": "billing_npi", "value": "1234567893"}]}},
            {"provider"},
        ),
        ("GET", f"/v1/claims/{CLAIM}/eob", {}, everyone),
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
        ("GET", f"/v1/claims/{CLAIM}/document"),
        ("GET", f"/v1/claims/{CLAIM}/document/1"),
        ("GET", f"/v1/claims/{CLAIM}/form"),
        ("GET", f"/v1/claims/{CLAIM}/check"),
        ("POST", f"/v1/claims/{CLAIM}/corrections"),
        ("GET", f"/v1/claims/{CLAIM}/eob"),
        ("POST", f"/v1/claims/{CLAIM}/process"),
    ):
        body = {"corrections": [{"field": "billing_npi", "value": "1234567893"}]}
        extra = {"json": body} if path.endswith("/corrections") else {}
        response = client.request(method, path, headers=other, **extra)
        assert response.status_code == 404, (method, path)  # as if it did not exist
        assert response.json()["detail"] == f"claim {CLAIM} not found"
    assert client.get("/v1/claims", headers=other).json() == []
    assert [c["claim_id"] for c in client.get("/v1/claims", headers=PROVIDER).json()] == [CLAIM]


def test_a_provider_sees_in_review_until_the_decision_is_final(api, load_case_reference) -> None:  # noqa: ANN001
    client = process_case(api, load_case_reference, "E2E-14")

    view = client.get(f"/v1/claims/{CLAIM}", headers=PROVIDER).json()
    assert (view["status"], view["final"], view["explanation"]) == ("IN_REVIEW", False, None)
    assert view["outcome"] == "IN_REVIEW" and "record" not in view
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
    assert (view["status"], view["final"], view["outcome"]) == ("FINAL_APPROVED", True, "APPROVED")
    assert view["explanation"]["heading"] == "Claim approved" and view["explanation"]["billing"]
    listed = client.get("/v1/claims", headers=PROVIDER).json()[0]
    assert listed["claim_decision"] == "APPROVE" and listed["total_allowed_cents"] is not None
    assert client.get(f"/v1/claims/{CLAIM}/explanation", headers=PROVIDER).status_code == 200


def test_a_rule_outcome_is_final_for_the_provider_at_once(api, load_case_reference) -> None:  # noqa: ANN001
    client = process_case(api, load_case_reference, "E2E-05")  # DENIED_BY_RULE
    claim_id = E2E_CASES["E2E-05"]["given"]["claim"]["claim_id"]
    view = client.get(f"/v1/claims/{claim_id}", headers=PROVIDER).json()
    assert (view["status"], view["final"], view["outcome"]) == ("DENIED_BY_RULE", True, "DENIED")
    assert view["explanation"]["heading"] == "Claim denied" and view["explanation"]["codes"]


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


# --- The member role (D-MEM-1) -------------------------------------------------------------------
# Kept as separate tests so the matrix above stays as it is: a member is 403 on every endpoint in
# it but /v1/auth/me, and the member's own routes are for members only (what a member sees there is
# in test_member.py).


def member_endpoints() -> list[tuple[str, str]]:
    return [
        ("GET", "/v1/member/claims"),
        ("GET", f"/v1/member/claims/{CLAIM}"),
        ("GET", f"/v1/member/claims/{CLAIM}/eob"),
        ("GET", "/v1/member/benefits"),
        ("GET", "/v1/member/profile"),
    ]


def test_a_member_is_refused_every_endpoint_but_their_own(api, load_case_reference, engine) -> None:  # noqa: ANN001
    from tests.e2e.support import add_member_user

    client = process_case(api, load_case_reference, "E2E-14")
    member = add_member_user(engine, E2E_CASES["E2E-14"]["given"]["claim"]["member_id"])
    for method, path, kwargs, _allowed in endpoints():
        response = client.request(method, path, headers=member, **kwargs)
        expected = 200 if path == "/v1/auth/me" else 403  # a member files, reads or acts on none
        assert response.status_code == expected, (method, path, response.text)

    for method, path in member_endpoints():
        response = client.request(method, path, headers=member)
        assert response.status_code not in (401, 403), (method, path, response.text)
        for role, headers in WHO.items():
            response = client.request(method, path, headers=headers)
            assert response.status_code == 403, (method, path, role, response.text)
        response = client.request(method, path, headers=NO_SESSION)
        assert response.status_code == 401, (method, path, "not logged in")
        assert response.headers["www-authenticate"] == "Bearer"


# --- The access matrix from the application's own route table (B4) ------------------------------
#
# Every route FastAPI serves is checked for every role and without a session, so a route added
# later cannot slip through: a route missing from ROUTE_ACCESS fails the test with its name, and
# an entry for a route that no longer exists fails too. Adding a role: add its session to SESSIONS
# and its name to the role sets of the routes it may use. A member (D-MEM-1) logs in as a member on
# file, so the member's session is added by the test that needs it (`with_member`).

SESSIONS = {"provider": PROVIDER, "reviewer": REVIEWER, "admin": ADMIN}
EVERYONE = frozenset(SESSIONS)
MEMBERS = frozenset({"member"})  # a member's own routes only, and /v1/auth/me
STAFF = frozenset({"reviewer", "admin"})
PROVIDERS = frozenset({"provider"})
REVIEWERS = frozenset({"reviewer"})
ADMINS = frozenset({"admin"})
# Values for the path parameters of the route templates.
PATH_VALUES = {"claim_id": CLAIM, "file_no": "1", "plan_id": "PLN-PPO-GOLD"}
CORRECTION = {"json": {"corrections": [{"field": "billing_npi", "value": "1234567893"}]}}
OTHER_REVIEW = {  # a review of another claim: refused (422) after the role check
    "json": {
        "claim_id": "CLM-OTHER",
        "reviewer_id": "reviewer-golden",
        "action": "ACCEPT",
        "timestamp": "2026-10-11T10:00:00Z",
    }
}

# (method, path template) -> (the roles allowed, request arguments). The bodies are valid enough
# to pass authorization; what comes after (409, 422) does not matter here.
ROUTE_ACCESS: dict[tuple[str, str], tuple[frozenset[str], dict[str, Any]]] = {
    ("GET", "/v1/auth/me"): (EVERYONE | MEMBERS, {}),
    ("POST", "/v1/claims/intake"): (PROVIDERS, {"json": E2E_CASES["E2E-14"]["given"]["claim"]}),
    ("POST", "/v1/claims/intake/file"): (PROVIDERS, {"content": b"not a claim"}),
    (
        "POST",
        "/v1/claims/intake/files",
    ): (PROVIDERS, {"json": {"files": [{"name": "a.pdf", "content_base64": "bm90IGEgY2xhaW0="}]}}),
    ("POST", "/v1/claims/{claim_id}/process"): (PROVIDERS, {}),
    ("GET", "/v1/claims"): (EVERYONE, {}),
    ("GET", "/v1/claims/{claim_id}"): (EVERYONE, {}),
    ("GET", "/v1/claims/{claim_id}/explanation"): (EVERYONE, {}),
    ("GET", "/v1/claims/{claim_id}/document"): (EVERYONE, {}),
    ("GET", "/v1/claims/{claim_id}/document/{file_no}"): (EVERYONE, {}),
    ("GET", "/v1/claims/{claim_id}/audit"): (STAFF, {}),
    ("GET", "/v1/claims/{claim_id}/form"): (EVERYONE, {}),
    ("POST", "/v1/claims/{claim_id}/corrections"): (PROVIDERS, CORRECTION),
    ("GET", "/v1/claims/{claim_id}/check"): (PROVIDERS, {}),
    ("GET", "/v1/claims/{claim_id}/eob"): (EVERYONE, {}),
    ("POST", "/v1/claims/{claim_id}/review/open"): (
        REVIEWERS,
        {"json": {"reviewer_id": "reviewer-golden"}},
    ),
    ("POST", "/v1/claims/{claim_id}/review"): (REVIEWERS, OTHER_REVIEW),
    ("GET", "/v1/review/queue"): (STAFF, {}),
    ("GET", "/v1/plans/{plan_id}"): (STAFF, {}),
    ("GET", "/v1/metrics/evaluation"): (ADMINS, {}),
    ("GET", "/v1/metrics/results"): (ADMINS, {}),
    ("GET", "/v1/metrics/overview"): (ADMINS, {}),
    ("GET", "/v1/metrics/system"): (ADMINS, {}),
    ("GET", "/v1/member/claims"): (MEMBERS, {}),
    ("GET", "/v1/member/claims/{claim_id}"): (MEMBERS, {}),
    ("GET", "/v1/member/claims/{claim_id}/eob"): (MEMBERS, {}),
    ("GET", "/v1/member/benefits"): (MEMBERS, {}),
    ("GET", "/v1/member/profile"): (MEMBERS, {}),
}
# Public routes (D-AUTH-1: login, logout and /health), always served.
PUBLIC_ROUTES = {("POST", "/v1/auth/login"), ("POST", "/v1/auth/logout"), ("GET", "/health")}
# Not API routes, served only in some setups: the web app's build (its files and index.html for
# the app's own paths, `make demo-up`) and the API docs (API_DOCS=1). They hold no claim data.
NOT_API_ROUTES = {
    ("MOUNT", "/assets"),
    ("GET", "/{path:path}"),
    ("GET", "/docs"),
    ("GET", "/docs/oauth2-redirect"),
    ("GET", "/openapi.json"),
}


def served_routes() -> set[tuple[str, str]]:
    """(method, path template) of every route the application serves, from FastAPI's route table
    (included routers flattened); a mounted application is ("MOUNT", path)."""
    from fastapi.routing import iter_route_contexts

    from app.api.main import app

    found: set[tuple[str, str]] = set()
    for route in iter_route_contexts(app.routes):
        path = route.path
        assert path, f"a route without a path: {route!r}"
        methods = route.methods
        if not methods:
            found.add(("MOUNT", path))
            continue
        found |= {(method, path) for method in methods if method != "HEAD"}
    return found


def test_every_served_route_has_an_access_rule() -> None:
    served = served_routes()

    unlisted = sorted(served - ROUTE_ACCESS.keys() - PUBLIC_ROUTES - NOT_API_ROUTES)
    gone = sorted((ROUTE_ACCESS.keys() | PUBLIC_ROUTES) - served)

    assert not unlisted, f"routes without an entry in ROUTE_ACCESS (who may use them?): {unlisted}"
    assert not gone, f"ROUTE_ACCESS or PUBLIC_ROUTES lists routes that no longer exist: {gone}"
    assert not ROUTE_ACCESS.keys() & (PUBLIC_ROUTES | NOT_API_ROUTES)
    assert all(roles <= EVERYONE | MEMBERS and roles for roles, _ in ROUTE_ACCESS.values())


def _url(template: str) -> str:
    return template.format(**PATH_VALUES)


def with_member(engine: Engine) -> dict[str, dict[str, str]]:
    """SESSIONS and the session of the member whose claim CLAIM is (D-MEM-1)."""
    from tests.e2e.support import add_member_user

    member_id = E2E_CASES["E2E-14"]["given"]["claim"]["member_id"]
    return SESSIONS | {"member": add_member_user(engine, member_id)}


def test_every_route_from_the_route_table_for_every_role(api, load_case_reference, engine) -> None:  # noqa: ANN001
    client = process_case(api, load_case_reference, "E2E-14")
    sessions = with_member(engine)
    checked = 0
    for method, template in sorted(served_routes()):
        if (method, template) in PUBLIC_ROUTES | NOT_API_ROUTES:
            continue
        allowed, kwargs = ROUTE_ACCESS[(method, template)]
        url = _url(template)
        for role, session in sessions.items():
            response = client.request(method, url, headers=session, **kwargs)
            if role in allowed:
                assert response.status_code not in (401, 403), (method, url, role, response.text)
            else:
                assert response.status_code == 403, (method, url, role, response.text)
        response = client.request(method, url, headers=NO_SESSION, **kwargs)
        assert response.status_code == 401, (method, url, "not logged in")
        assert response.headers["www-authenticate"] == "Bearer"
        checked += 1
    assert checked == len(ROUTE_ACCESS)


def test_the_public_routes_answer_without_a_session(api) -> None:  # noqa: ANN001
    client = api(StubModel("unused"))
    login = {"username": "nobody", "password": "x"}
    answers = {
        ("GET", "/health"): client.get("/health", headers=NO_SESSION).status_code,
        ("POST", "/v1/auth/logout"): client.post("/v1/auth/logout", headers=NO_SESSION).status_code,
        ("POST", "/v1/auth/login"): client.post(
            "/v1/auth/login", json=login, headers=NO_SESSION
        ).status_code,
    }
    assert answers.keys() == PUBLIC_ROUTES
    assert answers == {
        ("GET", "/health"): 200,
        ("POST", "/v1/auth/logout"): 204,
        ("POST", "/v1/auth/login"): 401,  # wrong password, not "log in first"
    }


def test_every_claim_route_hides_another_providers_claim(api, load_case_reference) -> None:  # noqa: ANN001
    """Every route of one claim a provider may use answers another provider as if the claim did
    not exist (404), so its existence is not revealed (D-AUTH-1)."""
    client = process_case(api, load_case_reference, "E2E-14")  # filed by provider-test
    other = bearer("provider-other")
    claim_routes = [
        (method, template)
        for (method, template), (allowed, _) in sorted(ROUTE_ACCESS.items())
        if "{claim_id}" in template and "provider" in allowed
    ]

    assert len(claim_routes) >= 9
    for method, template in claim_routes:
        kwargs = ROUTE_ACCESS[(method, template)][1]
        response = client.request(method, _url(template), headers=other, **kwargs)
        assert response.status_code == 404, (method, template, response.text)
        assert response.json()["detail"] == f"claim {CLAIM} not found"
