"""Helpers for the end-to-end tests: golden cases, fee rows and a stub model."""

import json
from pathlib import Path
from typing import Any

GOLDEN = Path(__file__).resolve().parents[1] / "golden"
E2E_CASES = {
    c["case_id"]: c for c in json.loads((GOLDEN / "e2e" / "cases.json").read_text())["cases"]
}


def golden_fee_rows() -> list[dict[str, Any]]:
    """Fee schedule rows (D6) as the golden calculator cases give them, so the test does not need
    `data/raw/` (absent in CI)."""
    fees: dict[str, dict[str, int]] = {}
    for path in sorted((GOLDEN / "calculator").glob("*.json")):
        for case in json.loads(path.read_text())["cases"]:
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
