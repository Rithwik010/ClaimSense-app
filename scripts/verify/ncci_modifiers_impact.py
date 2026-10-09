"""Task P2.3c planning: the impact of widening R11's bypass modifiers (D-GOLD-3) before any rule
change, and the gap between the file-backed and the database-backed NCCI and MUE tables.

Report only. R11 (A-R3) is recomputed here, independently of app/rules, for every claim of the 121
golden rules cases, the 31 golden end-to-end claims and the 2,600 records of the model v1 dataset,
under each option, and compared with v1 (XE, XP, XS, XU on either line):

- A: v1 plus modifier 59;
- B: the manual's full list of NCCI PTP-associated modifiers (2026 NCCI Policy Manual, Chapter I
  section E, page I-14), with the placement the manual gives (proposed): 59, XE, XP, XS and XU not
  on an E&M line (the CPT definition of 59, which the manual reproduces on page I-17, excludes E&M
  services; the definition itself is AMA text and is not copied here); 24, 25 and 57 only on an
  E&M line paired with a non-E&M code, 25 only when that code's PFS global period is 000, 010 or
  XXX (page I-16) and 57 only when it is 090 (page I-13); 58, 78 and 79 on a non-E&M line; 27 and
  91 on either line; anatomic modifiers
  only when both lines carry one and they share none ("2 different anatomic sites");
- B on either line: the full list with no placement rule (for comparison).

A changed line is one whose R11 result (denied DN_NCCI_BUNDLED, or passed with NCCI_BYPASS) differs
from v1. The gap section recomputes R11 and R12 with the tables the file-backed reference reads
(NCCI pairs and MUE limits of the 60 in-scope codes only) and with the full tables for the claim's
own codes (as the database reference reads them), and lists every line whose result differs.
Codes and modifiers only; no descriptor text is read out (H10).

    uv run python -m scripts.verify.ncci_modifiers_impact
    # prints the report and writes data/generated/verification/ncci_modifiers_impact.md
"""

import json
from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from app.db import raw
from app.db.curated import load_curated
from scripts.verify.rules_fixture import load_cases
from scripts.verify.rules_v2_impact import load_records

ROOT = Path(__file__).resolve().parents[2]
E2E_CASES = ROOT / "tests" / "golden" / "e2e" / "cases.json"
OUT = ROOT / "data" / "generated" / "verification" / "ncci_modifiers_impact.md"

V1 = frozenset({"XE", "XP", "XS", "XU"})
X_AND_59 = V1 | {"59"}
ANATOMIC = frozenset(
    {"E1", "E2", "E3", "E4", "FA", *(f"F{n}" for n in range(1, 10)), "TA"}
    | {*(f"T{n}" for n in range(1, 10)), "LT", "RT", "LC", "LD", "RC", "LM", "RI"}
)  # manual, Chapter I E: anatomic modifiers
EM_ONLY = frozenset({"24", "25", "57"})  # global surgery modifiers for an E&M line
PROCEDURE_ONLY = frozenset({"58", "78", "79"})  # global surgery modifiers for a procedure
EITHER = frozenset({"27", "91"})
FULL_LIST = X_AND_59 | ANATOMIC | EM_ONLY | PROCEDURE_ONLY | EITHER


@dataclass(frozen=True)
class Line:
    line_no: int
    code: str
    day: str
    units: int
    modifiers: frozenset[str]


def lines_of(claim: Mapping[str, Any]) -> list[Line]:
    out = []
    for i, s in enumerate(claim.get("service_lines") or []):
        if not isinstance(s, Mapping) or not isinstance(s.get("procedure_code"), str):
            continue
        out.append(
            Line(
                s.get("line_no", i + 1),
                s["procedure_code"],
                str(s.get("date_of_service")),
                int(s.get("units") or 0),
                frozenset(m for m in s.get("modifiers") or [] if isinstance(m, str)),
            )
        )
    return out


# (column 1 line, column 2 line, E&M codes, PFS global days)
Bypass = Callable[[Line, Line, frozenset[str], Mapping[str, str]], bool]
PAIRED_DAYS = {"25": {"000", "010", "XXX"}, "57": {"090"}}  # pages I-16 and I-13 (D-RULE-8)


def v1(a: Line, b: Line, em: frozenset[str], days: Mapping[str, str]) -> bool:
    return bool(V1 & (a.modifiers | b.modifiers))


def option_a(a: Line, b: Line, em: frozenset[str], days: Mapping[str, str]) -> bool:
    return bool(X_AND_59 & (a.modifiers | b.modifiers))


def option_b_either_line(a: Line, b: Line, em: frozenset[str], days: Mapping[str, str]) -> bool:
    return bool(FULL_LIST & (a.modifiers | b.modifiers))


def option_b(a: Line, b: Line, em: frozenset[str], days: Mapping[str, str]) -> bool:
    """The approved R11 bypass (D-RULE-8)."""
    for line, other in ((a, b), (b, a)):
        is_em = line.code in em
        if X_AND_59 & line.modifiers and not is_em:
            return True
        for modifier in EM_ONLY & line.modifiers:
            paired = days.get(other.code)
            needed = PAIRED_DAYS.get(modifier)
            if is_em and other.code not in em and (needed is None or paired in needed):
                return True
        if PROCEDURE_ONLY & line.modifiers and not is_em:
            return True
        if EITHER & line.modifiers:
            return True
    sites_a, sites_b = ANATOMIC & a.modifiers, ANATOMIC & b.modifiers
    return bool(sites_a and sites_b and not sites_a & sites_b)


OPTIONS: dict[str, Bypass] = {
    "A (v1 + 59)": option_a,
    "B (full list, manual placement; approved, D-RULE-8)": option_b,
    "B on either line (no placement)": option_b_either_line,
}


@dataclass(frozen=True)
class Tables:
    ncci: Mapping[tuple[str, str], Sequence[raw.NcciPair]]
    mue: Mapping[str, int]
    global_days: Mapping[str, str]


def tables_for(codes: set[str]) -> Tables:
    ncci: dict[tuple[str, str], list[raw.NcciPair]] = {}
    for pair in raw.read_ncci_pairs(codes):
        ncci.setdefault((pair.column1, pair.column2), []).append(pair)
    mue = {c: e.max_units for c, e in raw.read_mue(codes).items()}
    return Tables(ncci, mue, raw.read_pfs_global_days(codes))


def r11(
    lines: list[Line],
    tables: Tables,
    bypass: Bypass,
    em: frozenset[str],
    days: Mapping[str, str] = {},  # noqa: B006 - read only
) -> list[str]:
    """Per line: "DENY" (DN_NCCI_BUNDLED), "BYPASS" (NCCI_BYPASS) or "" (A-R3)."""
    out = [""] * len(lines)
    for i, a in enumerate(lines):
        for j, b in enumerate(lines):
            if i == j or a.day != b.day:
                continue
            edits = tables.ncci.get((a.code, b.code), ())
            day = date.fromisoformat(a.day)
            indicator = next((e.modifier_indicator for e in edits if e.active_on(day)), None)
            if indicator in (None, "9"):
                continue
            if indicator == "1" and bypass(a, b, em, days):
                if out[j] != "DENY":
                    out[j] = "BYPASS"
            else:
                out[j] = "DENY"
    return out


def r12(lines: list[Line], tables: Tables) -> list[bool]:
    return [
        x.code in tables.mue
        and sum(y.units for y in lines if (y.code, y.day) == (x.code, x.day)) > tables.mue[x.code]
        for x in lines
    ]


@dataclass(frozen=True)
class Claim:
    source: str  # golden rules | golden e2e | dataset <split>
    case_id: str
    claim: Mapping[str, Any]
    labels: Mapping[int, str]
    scenario: str


def claims() -> list[Claim]:
    out = [
        Claim("golden rules", c["case_id"], c["given"]["claim"], {}, "")
        for c in load_cases()
        if isinstance(c["given"]["claim"], Mapping)
    ]
    out += [
        Claim("golden e2e", c["case_id"], c["given"]["claim"], {}, "")
        for c in json.loads(E2E_CASES.read_text(encoding="utf-8"))["cases"]
    ]
    out += [
        Claim(f"dataset {r.split}", r.record_id, r.claim, r.labels, r.scenario)
        for r in load_records()
    ]
    return out


def all_codes(found: Iterable[Claim]) -> set[str]:
    return {x.code for c in found for x in lines_of(c.claim)}


def main() -> None:
    curated = load_curated()
    em = frozenset(
        c
        for c, entry in curated.scope.items()
        if any(cat.startswith("OFFICE_VISIT") for cat in entry.candidate_categories)
    )
    found = claims()
    full = tables_for(all_codes(found))
    scoped = tables_for(set(curated.scope))
    out = ["# P2.3c planning: NCCI modifiers and the reference tables", ""]

    usage: Counter[tuple[str, str]] = Counter()
    for c in found:
        for x in lines_of(c.claim):
            for m in x.modifiers:
                usage[(c.source.split()[0] + " " + c.source.split()[1], m)] += 1
    out += ["## Modifiers billed", ""]
    out += [f"- {source}: {m} x {n}" for (source, m), n in sorted(usage.items())]

    out += ["", "## R11 changes against v1 (every changed line)", ""]
    for name, bypass in OPTIONS.items():
        rows: list[str] = []
        by_group: Counter[str] = Counter()
        office_25 = 0
        for c in found:
            lines = lines_of(c.claim)
            before = r11(lines, full, v1, em, full.global_days)
            after = r11(lines, full, bypass, em, full.global_days)
            for x, old, new in zip(lines, before, after, strict=True):
                if old != new:
                    label = c.labels.get(x.line_no, "")
                    rows.append(
                        f"| {c.source} | {c.case_id} | {x.line_no} | {x.code} | "
                        f"{' '.join(sorted(x.modifiers)) or '-'} | {old or 'PASS'} -> "
                        f"{new or 'PASS'} | {c.scenario or '-'} | {label or '-'} |"
                    )
                    by_group[f"{c.source} {label}".strip()] += 1
                    if x.code in em and "25" in x.modifiers:
                        office_25 += 1
        out += [
            f"### Option {name}: {len(rows)} changed lines; office visits with 25 among them: "
            f"{office_25}",
            "",
        ]
        if rows:
            out += ["| Source | Case | Line | Code | Modifiers | R11 | Scenario | Label |"]
            out += ["|---|---|---|---|---|---|---|---|", *rows, ""]
            out += [f"- {k}: {n}" for k, n in sorted(by_group.items())]
        out.append("")

    out += ["## File-backed against database-backed tables (R11, R12)", ""]
    diffs: list[str] = []
    outside: Counter[str] = Counter()
    for c in found:
        lines = lines_of(c.claim)
        for x in lines:
            if x.code not in curated.scope:
                outside[c.source] += 1
        a, b = r11(lines, scoped, v1, em), r11(lines, full, v1, em)  # v1: no global days
        m, n = r12(lines, scoped), r12(lines, full)
        for x, r11_file, r11_db, r12_file, r12_db in zip(lines, a, b, m, n, strict=True):
            if (r11_file, r12_file) != (r11_db, r12_db):
                diffs.append(
                    f"| {c.source} | {c.case_id} | {x.line_no} | {x.code} | "
                    f"R11 {r11_file or 'PASS'} / {r11_db or 'PASS'}; R12 {r12_file} / {r12_db} |"
                )
    out += [
        "Lines billing a code outside the 60-code scope: "
        + (", ".join(f"{k} {v}" for k, v in sorted(outside.items())) or "none"),
        "",
        f"Lines whose R11 or R12 result differs (file / database): {len(diffs)}",
    ]
    if diffs:
        out += ["", "| Source | Case | Line | Code | Result |", "|---|---|---|---|---|", *diffs]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(out) + "\n", encoding="utf-8")
    print("\n".join(out))


if __name__ == "__main__":
    main()
