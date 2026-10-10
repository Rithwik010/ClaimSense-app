"""P2.1/P2.5 decision 2: how many claims have a date of service before 2026-10-01, the first day of
ICD-10-CM FY2027, the only fiscal year loaded. Such a claim cannot be checked (rule R02), so the
pipeline leaves it RECEIVED with a 503 until FY2026 is loaded.

Counts every claim set: the model v1 decision dataset, the claim corpus, the golden rules cases,
the golden end-to-end claims, the blind-review claims (only their dates of service are read) and
the live-model test's sample claim. Report only.

    uv run python -m scripts.verify.early_dates
"""

import json
from collections.abc import Iterable, Iterator, Mapping
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
FIRST_LOADED_DAY = "2026-10-01"  # ICD-10-CM FY2027 starts on 1 October 2026


def _jsonl(path: Path) -> Iterator[dict[str, Any]]:
    with path.open(encoding="utf-8") as f:
        yield from (json.loads(line) for line in f if line.strip())


def dates_of_service(claim: Mapping[str, Any]) -> list[str]:
    return [
        line["date_of_service"]
        for line in claim.get("service_lines") or []
        if isinstance(line, Mapping) and isinstance(line.get("date_of_service"), str)
    ]


def claim_sets(root: Path = ROOT) -> dict[str, list[list[str]]]:
    """Each set's claims as their dates of service only; a set whose files are absent is left out
    (data/generated/ is not in the repository)."""
    sets: dict[str, list[list[str]]] = {}
    decision = root / "data" / "generated" / "decision"
    for split in ("train", "validation", "test"):
        path = decision / f"{split}_inputs.jsonl"
        if path.exists():
            sets[f"decision dataset, {split}"] = [
                dates_of_service(row["claim"]) for row in _jsonl(path)
            ]
    corpus = root / "data" / "generated" / "claims" / "claims.jsonl"
    if corpus.exists():
        sets["claim corpus"] = [dates_of_service(row["claim"]) for row in _jsonl(corpus)]
    golden = root / "tests" / "golden"
    sets["golden rules cases"] = [
        dates_of_service(case["given"]["claim"])
        for path in sorted((golden / "rules").glob("*.json"))
        for case in json.loads(path.read_text(encoding="utf-8")).get("cases", [])
    ]
    sets["golden end-to-end claims"] = [
        dates_of_service(case["given"]["claim"])
        for case in json.loads((golden / "e2e" / "cases.json").read_text(encoding="utf-8"))["cases"]
    ]
    blind = json.loads((golden / "blind_review" / "claims.json").read_text(encoding="utf-8"))
    sets["blind-review claims"] = [dates_of_service(item["claim"]) for item in blind["claims"]]
    sample = root / "tests" / "e2e" / "sample_claim.json"
    sets["live-model test sample claim"] = [
        dates_of_service(json.loads(sample.read_text(encoding="utf-8")))
    ]
    return sets


def summary(sets: Mapping[str, Iterable[list[str]]]) -> list[tuple[str, int, int, str, str]]:
    """(set, claims, claims with a date before FIRST_LOADED_DAY, earliest, latest date)."""
    rows = []
    for name, claims in sets.items():
        claims = list(claims)
        days = [day for claim in claims for day in claim]
        early = sum(any(day < FIRST_LOADED_DAY for day in claim) for claim in claims)
        rows.append((name, len(claims), early, min(days, default="-"), max(days, default="-")))
    return rows


def main() -> None:
    print(f"| Claim set | Claims | With a date of service before {FIRST_LOADED_DAY} | Dates |")
    print("|---|---|---|---|")
    for name, total, early, first, last in summary(claim_sets()):
        print(f"| {name} | {total:,} | {early} | {first} to {last} |")


if __name__ == "__main__":
    main()
