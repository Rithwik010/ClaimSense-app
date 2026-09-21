"""Helpers shared by the generators: output paths, JSONL writing, seeded NPIs and TINs."""

import json
import random
from collections.abc import Iterable
from datetime import date
from pathlib import Path
from typing import Any

from app.domain.contracts import npi_is_valid

GENERATED_DIR = Path(__file__).resolve().parents[2] / "data" / "generated"
DEFAULT_SEED = 20260921

# Dates of service window (DECISIONS.md R1) and the benefit period (D7).
DOS_START = date(2026, 10, 1)
DOS_END = date(2026, 12, 31)
PERIOD_START = date(2026, 1, 1)
PERIOD_END = date(2026, 12, 31)


def npi_check_digit(first_nine: str) -> str:
    """Luhn check digit over "80840" + the first nine NPI digits."""
    for digit in "0123456789":
        if npi_is_valid(first_nine + digit):
            return digit
    raise AssertionError("unreachable: one digit always satisfies Luhn")


def make_npi(rng: random.Random, taken: set[str]) -> str:
    while True:
        first_nine = str(rng.choice("12")) + "".join(rng.choice("0123456789") for _ in range(8))
        npi = first_nine + npi_check_digit(first_nine)
        if npi not in taken:
            taken.add(npi)
            return npi


def make_tin(rng: random.Random, taken: set[str]) -> str:
    while True:
        tin = str(rng.randint(10, 99)) + "".join(rng.choice("0123456789") for _ in range(7))
        if tin not in taken:
            taken.add(tin)
            return tin


def _default(value: Any) -> Any:
    if isinstance(value, date):
        return value.isoformat()
    raise TypeError(f"not JSON serializable: {type(value).__name__}")


def to_json(value: Any, *, indent: int | None = None) -> str:
    return json.dumps(value, default=_default, ensure_ascii=False, indent=indent)


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(to_json(row) + "\n")
            count += 1
    return count


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(to_json(value, indent=2) + "\n", encoding="utf-8")
