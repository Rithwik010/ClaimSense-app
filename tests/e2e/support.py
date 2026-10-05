"""Helpers for the end-to-end tests: golden cases, fee rows, a stub model and a stub retriever."""

import json
from datetime import date
from pathlib import Path
from typing import Any

from app.db.models import Claim
from app.domain.contracts import RetrievedCriterion

GOLDEN = Path(__file__).resolve().parents[1] / "golden"
E2E_CASES = {
    c["case_id"]: c for c in json.loads((GOLDEN / "e2e" / "cases.json").read_text())["cases"]
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


class StubModel:
    """Returns a fixed answer and records the prompts it was given."""

    def __init__(self, answer: str, name: str = "stub-model") -> None:
        self.name = name
        self.answer = answer
        self.prompts: list[tuple[str, str]] = []

    def complete(self, system: str, user: str) -> str:
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
