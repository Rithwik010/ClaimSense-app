"""Helpers for the end-to-end tests: golden cases, fee rows, a stub model and a stub retriever, the
test users and their session tokens (D-AUTH-1), and the review helpers (the audit trail, the
stored accumulators)."""

import json
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.auth.passwords import hash_password
from app.auth.tokens import create_token
from app.db.models import Accumulator, Claim, User
from app.domain.contracts import DecisionRecord, RetrievedCriterion

GOLDEN = Path(__file__).resolve().parents[1] / "golden"
E2E_CASES = {
    c["case_id"]: c for c in json.loads((GOLDEN / "e2e" / "cases.json").read_text())["cases"]
}
E2E_V2_CASES = {  # policy set v2 versions, engine-derived (D-GOLD-9)
    c["case_id"]: c for c in json.loads((GOLDEN / "e2e_v2" / "cases.json").read_text())["cases"]
}


def golden_fee_rows() -> list[dict[str, Any]]:
    """Fee schedule rows (D6) as the golden calculator cases give them, so the test does not need
    `data/raw/` (absent in CI)."""
    fees: dict[str, dict[str, int]] = {}
    for path in sorted((GOLDEN / "calculator").glob("*.json")):
        for case in json.loads(path.read_text()).get("cases", []):
            fees |= case["given"]["fee_schedule"]
    return [
        {
            "procedure_code": code,
            "modifier": "",
            "effective_date": "2026-01-01",
            "source": "tests/golden/calculator",
            **fee,
        }
        for code, fee in sorted(fees.items())
    ]


def e2e_fee_rows() -> list[dict[str, Any]]:
    """The end-to-end database's fee schedule (D6) for every code in the calculator fixture (the
    golden calculator codes and the end-to-end claims' in-scope codes), computed as the seed does
    from data/raw/ (app.db.seed.fee_rows), so the tests need no data/raw/ (D-CI-2)."""
    from app.calculator.fee_schedule import allowed_amounts
    from app.db.curated import load_curated
    from scripts.verify.calculator_fixture import read_fixture, rvus

    rule = load_curated().fee_rule
    rows = []
    for code, rvu in sorted(rvus(read_fixture()).items()):
        inn, oon = allowed_amounts(
            rvu, rule.conversion_factor, rule.in_network_bps, rule.out_of_network_bps
        )
        rows.append(
            {
                "procedure_code": code,
                "modifier": "",
                "effective_date": rule.effective_date.isoformat(),
                "inn_allowed_cents": inn,
                "oon_allowed_cents": oon,
                "source": "tests/golden/calculator/raw_subset.json (D6)",
            }
        )
    return rows


class StubModel:
    """Returns a fixed answer and records the prompts it was given."""

    def __init__(self, answer: str, name: str = "stub-model") -> None:
        self.name = name
        self.answer = answer
        self.prompts: list[tuple[str, str]] = []

    def complete(self, system: str, user: str, attempt: int = 1) -> str:
        self.prompts.append((system, user))
        return self.answer


class StubRetriever:
    """Returns fixed criteria for every line (none by default)."""

    def __init__(self, criteria: list[RetrievedCriterion] | None = None) -> None:
        self.criteria = criteria or []
        self.queries: list[str] = []

    def retrieve(
        self, query: str, plan_id: str, day: date, procedure_code=None, exclude_policies=()
    ):  # noqa: ANN001, ANN201
        self.queries.append(query)
        return list(self.criteria)


def claim_on_file(row: dict[str, Any]) -> Claim:
    """A claim already on file, from a golden `existing_claims` row (one line), for the duplicate
    check (A-R6)."""
    return Claim(
        claim_id=row["claim_id"],
        member_id=row["member_id"],
        received_date=date.fromisoformat(row["date_of_service"]),
        source_format="JSON",
        status=row["status"],
        intake={
            "member_id": row["member_id"],
            "billing_npi": row["billing_npi"],
            "service_lines": [
                {
                    "line_no": 1,
                    "date_of_service": row["date_of_service"],
                    "procedure_code": row["procedure_code"],
                }
            ],
        },
        field_confidences={},
    )


class CaseRetriever(StubRetriever):
    """For a line's procedure code, the curated criteria the case's answer cites for that line."""

    def __init__(self, case: dict[str, Any], policy_set: str = "v1") -> None:
        super().__init__()
        from app.db.curated import load_curated

        curated = load_curated(policy_set)
        criteria = curated.criteria()
        codes = {
            line["line_no"]: line.get("procedure_code")
            for line in case["given"]["claim"]["service_lines"]
        }
        self.by_code: dict[str, list[RetrievedCriterion]] = {}
        for line in (case["given"].get("model_answer") or {}).get("lines", []):
            found = self.by_code.setdefault(codes.get(line["line_no"]), [])
            for cited in line.get("criteria", []):
                criterion_id = cited["criterion_id"]
                policy = curated.policies.get(criterion_id.split(".")[0])
                if criterion_id in criteria and policy is not None:
                    found.append(
                        RetrievedCriterion(
                            criterion_id=criterion_id,
                            policy_id=policy.policy_id,
                            policy_title=policy.title,
                            text=criteria[criterion_id].text,
                            source=criteria[criterion_id].source,
                            effective_date=policy.effective_date,
                        )
                    )

    def retrieve(self, query, plan_id, day, procedure_code=None, exclude_policies=()):  # noqa: ANN001, ANN201
        self.queries.append(query)
        return list(self.by_code.get(procedure_code, []))


def process_case(api, load_case_reference, case_id: str, claim: dict[str, Any] | None = None):  # noqa: ANN001, ANN201
    """A golden end-to-end case (or a copy of its claim) through intake and processing with the
    case's stub model and retriever; returns the API client."""
    case = E2E_CASES[case_id]
    load_case_reference(case)
    answer = case["given"].get("model_answer")
    client = api(StubModel(json.dumps(answer) if answer else "unused"), CaseRetriever(case))
    claim = claim or case["given"]["claim"]
    assert client.post("/v1/claims/intake", json=claim).status_code == 201
    response = client.post(f"/v1/claims/{claim['claim_id']}/process")
    assert response.status_code == 200, response.text
    return client


# --- Logins (D-AUTH-1) ---------------------------------------------------------------------------

TEST_SECRET = "claimsense-test-secret-for-the-test-suite-only"
TEST_PASSWORD = "test password"
TEST_USERS = {  # username: (role, provider ID)
    "provider-test": ("provider", "1234567893"),
    "provider-other": ("provider", "1987654320"),
    "reviewer-golden": ("reviewer", None),  # the golden cases' reviewer ID
    "reviewer-1": ("reviewer", None),
    "reviewer-a": ("reviewer", None),
    "reviewer-b": ("reviewer", None),
    "admin-test": ("admin", None),
}


def bearer(username: str) -> dict[str, str]:
    """An Authorization header with a valid session token of a test user."""
    role = TEST_USERS[username][0]
    return {"Authorization": f"Bearer {create_token(username, role, TEST_SECRET)}"}


# How a test that files a claim directly (not through the API) files it as the test provider.
FILED_BY_TEST_PROVIDER = {
    "provider_id": TEST_USERS["provider-test"][1],
    "filed_by": "provider-test",
}
NO_SESSION = {"Authorization": ""}  # neither a token nor a cookie: not logged in
PROVIDER = bearer("provider-test")
REVIEWER = bearer("reviewer-golden")
ADMIN = bearer("admin-test")


@lru_cache(maxsize=1)
def _test_hash() -> str:
    return hash_password(TEST_PASSWORD)  # once: Argon2 is slow on purpose


def add_test_users(session: Session) -> None:
    session.add_all(
        User(
            username=name,
            display_name=name.replace("-", " ").title(),
            password_hash=_test_hash(),
            role=role,
            provider_id=provider_id,
        )
        for name, (role, provider_id) in TEST_USERS.items()
    )


class SessionClient(TestClient):
    """The end-to-end tests' API client. A request without an Authorization header acts as the
    role its endpoint needs: the test provider files and processes claims, a review action runs as
    the reviewer it names, and the golden reviewer reads everything else. The access tests pass
    their own header (PROVIDER, REVIEWER, ADMIN, bearer(...))."""

    def request(self, method: str, url: Any, **kwargs: Any) -> Any:  # noqa: ANN401
        headers = dict(kwargs.pop("headers", None) or {})
        if not any(name.lower() == "authorization" for name in headers):
            path = str(url)
            body = kwargs.get("json")
            reviewer = body.get("reviewer_id") if isinstance(body, dict) else None
            if method.upper() == "POST" and (
                path.startswith("/v1/claims/intake") or path.endswith("/process")
            ):
                headers |= PROVIDER
            elif reviewer in TEST_USERS and TEST_USERS[reviewer][0] == "reviewer":
                headers |= bearer(reviewer)
            else:
                headers |= REVIEWER
        return super().request(method, url, headers=headers, **kwargs)


def record_of(client: TestClient, claim_id: str) -> DecisionRecord:
    """The claim's latest decision record, as a reviewer reads it (a provider's process answer
    holds no recommendation, D-AUTH-1)."""
    response = client.get(f"/v1/claims/{claim_id}")
    assert response.status_code == 200, response.text
    return DecisionRecord.model_validate(response.json()["record"])


def process_record(client: TestClient, claim_id: str) -> DecisionRecord:
    """Process a filed claim as its provider and return the decision record a reviewer reads."""
    response = client.post(f"/v1/claims/{claim_id}/process")
    assert response.status_code == 200, response.text
    return record_of(client, claim_id)


# --- Review --------------------------------------------------------------------------------------


def audit(client, claim_id: str) -> list[dict[str, Any]]:  # noqa: ANN001
    return client.get(f"/v1/claims/{claim_id}/audit").json()


def stored_accumulators(engine: Engine, member_id: str) -> dict[str, int] | None:
    """The member's stored in-network accumulators for benefit year 2026 (None without a row)."""
    with Session(engine) as session:
        row = session.get(Accumulator, (member_id, date(2026, 1, 1), "IN_NETWORK"))
        if row is None:
            return None
        return {
            "deductible_met_cents": row.deductible_met_cents,
            "oop_met_cents": row.oop_met_cents,
        }
