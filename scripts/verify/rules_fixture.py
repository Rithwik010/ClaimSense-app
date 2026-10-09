"""Task P2.3a-ci: the raw rows the golden rules cases need, as a committed fixture, so CI (which has
no data/raw/, H9) runs every golden rules case. Since P2.1 it also covers the golden
end-to-end claims, whose database the fixture loads in CI.

tests/golden/rules/raw_subset.json holds only what the rules engine reads from data/raw/ for the
codes the cases and claims use:
- ICD-10-CM FY2027 billable codes, procedure codes (the R02 code table) and place-of-service
  codes: the cases' codes that are in the real table. A code the real table lacks (99999, M541,
  POS 00) stays absent, so R02 decides exactly as with the full tables;
- NCCI edits for every ordered pair of codes billed on the same claim: every edit row of the pair,
  with its effective and deletion dates and modifier indicator, in the source order (the first
  edit active on the date of service applies);
- MUE unit limits for the cases' procedure codes;
- the billing articles' covered ICD-10-CM rows (article, group, code) for the cases' procedure
  codes and diagnoses, which R15 reads (D-CI-4). A diagnosis no group covers stays absent;
- the PFS global days of the cases' procedure codes, which R11 reads for modifiers 25 and 57.
NCCI edits, MUE limits and global days are read for every code the cases bill (with the rules' own
codes), as the database reference reads them per claim, in or out of scope (D-CI-5).
Codes, dates, indicators and limits only: no descriptions are read or written (H10). NCCI edits
and MUE limits cover the in-scope codes, as the engine's reference does (app/db/rules_reference).

tests/unit/test_rules_fixture.py checks the fixture holds nothing but codes, dates, indicators and
limits and, wherever data/raw/ is present, that it equals a fresh extraction. The golden rules
tests use it when data/raw/ is absent, or when CLAIMSENSE_IGNORE_RAW=1 (to run them as CI does).

    uv run python -m scripts.verify.rules_fixture           # compare with data/raw/
    uv run python -m scripts.verify.rules_fixture --write   # rewrite the fixture (deliberately)
"""

import argparse
import json
import os
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from app.db import raw
from app.db.curated import load_curated, rule_codes
from app.db.rules_reference import CodeTables, load_code_tables
from app.rules.reference import NcciEdit

ROOT = Path(__file__).resolve().parents[2]
GOLDEN_RULES = ROOT / "tests" / "golden" / "rules"
E2E_CASES = ROOT / "tests" / "golden" / "e2e" / "cases.json"
FIXTURE = GOLDEN_RULES / "raw_subset.json"
IGNORE_RAW_ENV = "CLAIMSENSE_IGNORE_RAW"
NOTE = (
    "Derived from data/raw/ by scripts/verify/rules_fixture.py for the golden rules cases and the "
    "golden end-to-end claims: codes, dates, modifier indicators and unit limits only (D-CI-1). "
    "Do not edit by hand."
)
KEYS = (
    "note",
    "sources",
    "icd10_codes",
    "procedure_codes",
    "place_of_service_codes",
    "ncci",
    "mue",
    "article_icd10_covered",
    "global_days",
)


def raw_in_use() -> bool:
    """Whether tests read data/raw/: it is present and not hidden with CLAIMSENSE_IGNORE_RAW=1."""
    return raw.raw_available() and os.environ.get(IGNORE_RAW_ENV) != "1"


def load_cases(folder: Path = GOLDEN_RULES) -> list[dict[str, Any]]:
    """Every golden rules case (files without `cases`, such as reference.json, hold none)."""
    return [
        case
        for path in sorted(folder.glob("*.json"))
        for case in json.loads(path.read_text(encoding="utf-8")).get("cases", [])
    ]


def fixture_cases() -> list[dict[str, Any]]:
    """The cases whose codes the fixture covers: every golden rules case and every golden
    end-to-end claim (P2.1)."""
    e2e = json.loads(E2E_CASES.read_text(encoding="utf-8"))["cases"]
    return [*load_cases(), *e2e]


@dataclass(frozen=True)
class CaseCodes:
    diagnoses: frozenset[str]  # as the contract normalizes them: no dots, upper case
    procedure_codes: frozenset[str]
    places_of_service: frozenset[str]
    pairs: frozenset[tuple[str, str]]  # ordered pairs of codes billed on the same claim


def case_codes(cases: Iterable[Mapping[str, Any]]) -> CaseCodes:
    diagnoses, codes, places, pairs = set(), set(), set(), set()
    for case in cases:
        claim = case["given"]["claim"]
        diagnoses |= {
            d.replace(".", "").strip().upper()
            for d in claim.get("diagnoses") or []
            if isinstance(d, str)
        }
        lines = [line for line in claim.get("service_lines") or [] if isinstance(line, dict)]
        line_codes = [line.get("procedure_code") for line in lines]
        codes |= {code for code in line_codes if isinstance(code, str)}
        places |= {line["place_of_service"] for line in lines if line.get("place_of_service")}
        pairs |= {
            (a, b)
            for i, a in enumerate(line_codes)
            for j, b in enumerate(line_codes)
            if i != j and isinstance(a, str) and isinstance(b, str)
        }
    return CaseCodes(frozenset(diagnoses), frozenset(codes), frozenset(places), frozenset(pairs))


def _day(value: date | None) -> str | None:
    return value.isoformat() if value else None


def extract(
    cases: Iterable[Mapping[str, Any]], tables: CodeTables, sources: list[str]
) -> dict[str, Any]:
    used = case_codes(cases)
    support = load_curated().diagnosis_support
    return {
        "note": NOTE,
        "sources": sources,
        "icd10_codes": {
            str(year): sorted(used.diagnoses & codes) for year, codes in tables.icd10_codes.items()
        },
        "procedure_codes": sorted(used.procedure_codes & tables.procedure_codes),
        "place_of_service_codes": sorted(used.places_of_service & tables.place_of_service_codes),
        "ncci": [
            [edit.column1, edit.column2, _day(edit.effective_date), _day(edit.deletion_date)]
            + [edit.modifier_indicator]
            for pair in sorted(used.pairs)
            for edit in tables.ncci.get(pair, ())
        ],
        "mue": {
            code: tables.mue[code] for code in sorted(used.procedure_codes) if code in tables.mue
        },
        "article_icd10_covered": [
            [article, group, code]
            for article in sorted(
                {s.billing_article for c, s in support.items() if c in used.procedure_codes}
            )
            for group, codes in sorted(tables.article_covered.get(article, {}).items())
            for code in sorted(used.diagnoses & codes)
        ],
        "global_days": {
            code: tables.global_days[code]
            for code in sorted(used.procedure_codes)
            if code in tables.global_days
        },
    }


def raw_sources() -> list[str]:
    """The data/raw/ files the fixture's rows come from, relative to data/raw/."""
    files = [raw.ICD10_ZIP, raw.PFS_CSV, raw.HCPCS_TXT, raw.POS_PDF, *raw._ncci_files()]
    files += [raw.MUE_CSV, raw.MCD_ARTICLES_ZIP]
    return [path.relative_to(raw.RAW_DIR).as_posix() for path in files]


def fresh_fixture() -> dict[str, Any]:
    """The fixture extracted from data/raw/ now (slow: reads the NCCI table)."""
    cases = fixture_cases()
    tables = load_code_tables(rule_codes(load_curated()) | case_codes(cases).procedure_codes)
    return extract(cases, tables, raw_sources())


def code_tables(fixture: Mapping[str, Any]) -> CodeTables:
    """The engine's code tables from the fixture."""
    ncci: dict[tuple[str, str], list[NcciEdit]] = {}
    for column1, column2, effective, deletion, indicator in fixture["ncci"]:
        ncci.setdefault((column1, column2), []).append(
            NcciEdit(
                column1=column1,
                column2=column2,
                effective_date=date.fromisoformat(effective),
                deletion_date=date.fromisoformat(deletion) if deletion else None,
                modifier_indicator=indicator,
            )
        )
    return CodeTables(
        icd10_codes={int(year): frozenset(codes) for year, codes in fixture["icd10_codes"].items()},
        procedure_codes=frozenset(fixture["procedure_codes"]),
        place_of_service_codes=frozenset(fixture["place_of_service_codes"]),
        ncci={key: tuple(edits) for key, edits in ncci.items()},
        mue=dict(fixture["mue"]),
        article_covered=article_covered(fixture),
        global_days=dict(fixture["global_days"]),
    )


def article_covered(fixture: Mapping[str, Any]) -> dict[str, dict[int, frozenset[str]]]:
    covered: dict[str, dict[int, set[str]]] = {}
    for article, group, code in fixture["article_icd10_covered"]:
        covered.setdefault(article, {}).setdefault(group, set()).add(code)
    return {a: {g: frozenset(c) for g, c in groups.items()} for a, groups in covered.items()}


def render(fixture: Mapping[str, Any]) -> str:
    """Stable JSON, one NCCI edit per line."""

    def entry(key: str) -> str:
        if key in ("ncci", "article_icd10_covered"):
            rows = ",\n".join(f"    {json.dumps(row)}" for row in fixture[key])
            return f'  "{key}": [\n{rows}\n  ]'
        value = json.dumps(fixture[key], indent=2).replace("\n", "\n  ")
        return f"  {json.dumps(key)}: {value}"

    return "{\n" + ",\n".join(entry(key) for key in KEYS) + "\n}\n"


def read_fixture(path: Path = FIXTURE) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--write", action="store_true", help="rewrite the committed fixture")
    args = parser.parse_args()
    if not raw.raw_available():
        raise SystemExit("data/raw/ is required to extract the fixture (see SOURCES.md)")
    fixture = fresh_fixture()
    if args.write:
        FIXTURE.write_text(render(fixture), encoding="utf-8")
        print(f"wrote {FIXTURE.relative_to(ROOT)}: {summary(fixture)}")
        return
    same = FIXTURE.exists() and read_fixture() == fixture
    print(f"{FIXTURE.relative_to(ROOT)} {'equals' if same else 'DIFFERS FROM'} a fresh extraction")
    if not same:
        raise SystemExit(1)


def summary(fixture: Mapping[str, Any]) -> str:
    return (
        f"{sum(len(c) for c in fixture['icd10_codes'].values())} ICD-10-CM codes, "
        f"{len(fixture['procedure_codes'])} procedure codes, "
        f"{len(fixture['place_of_service_codes'])} place-of-service codes, "
        f"{len(fixture['ncci'])} NCCI edits, {len(fixture['mue'])} MUE limits, "
        f"{len(fixture['article_icd10_covered'])} covered article rows, "
        f"{len(fixture['global_days'])} global days"
    )


if __name__ == "__main__":
    main()
