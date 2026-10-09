"""Task P2.3c checkpoint 2: new golden R11 cases for the NCCI PTP-associated modifiers (D-RULE-8,
D-GOLD-7), drafted for an independent check on sheet G5.

Each accepted modifier group gets a bypass and a near miss: 59; an X modifier on an E&M line (a
change from A-R3 v1, where X modifiers counted on either line); 25 (with a 000-day procedure, on
the procedure line, with a 090-day procedure, between two E&Ms); 57 (with a 090-day procedure and
with a 000-day one); 58 (on a procedure, on an E&M); anatomic modifiers (different and same
sites). 24, 78, 79, 27 and 91 get unit tests only (P2.3c plan review).

Expected values are computed independently of app/rules (the code they will test, H12): R11 from
scripts/verify/ncci_modifiers_impact.py (the approved option B) on the full NCCI tables, and the
rules v2 checks of scripts/verify/rules_v2_impact.py, which must find nothing; every draft states
its expected line results by hand, and the two must agree. Every claim passes Groups A and B on the
current engine, which also shows where v1's R11 differs.

Outputs, in data/generated/verification/ (not committed):
- new_golden/r11_modifier_cases.json: the drafted cases for tests/golden/rules/R11_ncci.json;
- G5_r11_modifiers_sheet.md: the blind sheet (inputs, the facts R11 reads, the rule text, the
  status table) with blank result cells.

    uv run python -m scripts.verify.new_modifier_cases
"""

import json
from collections.abc import Mapping, Sequence
from datetime import date
from typing import Any

from app.db import raw
from app.db.curated import billing_articles, em_codes, load_curated
from scripts.verify.ncci_modifiers_impact import Line, Tables, lines_of, option_b, r11, tables_for
from scripts.verify.new_rules_cases import (
    GI,
    OUT_DIR,
    PRIMARY,
    RADIOLOGY,
    STAGING,
    Draft,
    L,
    authorizations,
    claim_for,
    reference,
    status_table,
)
from scripts.verify.rules_v2_impact import Lookups
from scripts.verify.rules_v2_impact import proposed as v2_checks

CASES_FILE = STAGING / "r11_modifier_cases.json"
SHEET_FILE = OUT_DIR / "G5_r11_modifiers_sheet.md"
TARGET = "R11_ncci.json"
MANUAL_PAGES = ("I-14", "I-16", "I-13", "I-17", "I-20")
I14, I16, I13, I17, I20 = (f"NCCI Policy Manual 2026, page {p}" for p in MANUAL_PAGES)
BYPASS = "PASS NCCI_BYPASS"
BUNDLED = "DENY DN_NCCI_BUNDLED"
EDIT = "NCCI {a}/{b} (column 1/column 2), modifier indicator 1: line 2 is the column-2 line."


def draft(  # noqa: PLR0913 - one argument per case field
    case_id: str,
    title: str,
    npi: str,
    dx: tuple[str, ...],
    lines: tuple[L, ...],
    expect: tuple[str, ...],
    steps: tuple[str, ...],
    sources: tuple[str, ...],
) -> Draft:
    return Draft(case_id, TARGET, title, ("R11",), npi, dx, lines, expect, steps, sources)


DRAFTS: tuple[Draft, ...] = (
    draft(
        "R11-10",
        "Modifier 59 on the column-2 procedure bypasses",
        GI,
        ("K635",),
        (L("45385"), L("45380", modifiers=("59",))),
        ("PASS", BYPASS),
        (
            EDIT.format(a="45385", b="45380"),
            "59 is on a procedure line (not an E&M) -> bypass: line 2 passes with NCCI_BYPASS.",
        ),
        (I14, I17),
    ),
    draft(
        "R11-11",
        "Modifier 59 on an E&M line does not bypass",
        PRIMARY,
        ("E1142",),
        (L("11720"), L("99213", modifiers=("59",))),
        ("PASS", BUNDLED),
        (
            EDIT.format(a="11720", b="99213"),
            "59 counts only on a non-E&M line; 99213 is an E&M -> no bypass -> line 2 denied.",
        ),
        (I14, I17),
    ),
    draft(
        "R11-12",
        "An X modifier on an E&M line does not bypass",
        PRIMARY,
        ("E1142",),
        (L("11720"), L("99213", modifiers=("XU",))),
        ("PASS", BUNDLED),
        (
            EDIT.format(a="11720", b="99213"),
            "XU, like 59, counts only on a non-E&M line -> no bypass -> line 2 denied (rules v1 "
            "let an X modifier count on either line, A-R3).",
        ),
        (I14, I20),
    ),
    draft(
        "R11-13",
        "Modifier 25 on the E&M with a 000-day procedure bypasses",
        PRIMARY,
        ("E1142",),
        (L("11720"), L("99213", modifiers=("25",))),
        ("PASS", BYPASS),
        (
            EDIT.format(a="11720", b="99213"),
            "25 is on the E&M line, paired with 11720 (PFS global 000) -> bypass.",
        ),
        (I14, I16),
    ),
    draft(
        "R11-14",
        "Modifier 25 on the procedure line does not bypass",
        PRIMARY,
        ("E1142",),
        (L("11720", modifiers=("25",)), L("99213")),
        ("PASS", BUNDLED),
        (
            EDIT.format(a="11720", b="99213"),
            "25 counts only on an E&M line; here it is on the procedure -> no bypass -> line 2 "
            "denied.",
        ),
        (I14, I16),
    ),
    draft(
        "R11-15",
        "Modifier 25 with a 090-day procedure does not bypass",
        PRIMARY,
        ("H2513",),
        (L("66982"), L("99213", modifiers=("25",))),
        ("PASS", BUNDLED),
        (
            EDIT.format(a="66982", b="99213"),
            "25 is on the E&M, but 66982 has PFS global 090; 25 needs 000, 010 or XXX -> no "
            "bypass -> line 2 denied.",
        ),
        (I14, I16, I13),
    ),
    draft(
        "R11-16",
        "Modifier 57 on the E&M with a 090-day procedure bypasses",
        PRIMARY,
        ("H2513",),
        (L("66982"), L("99213", modifiers=("57",))),
        ("PASS", BYPASS),
        (
            EDIT.format(a="66982", b="99213"),
            "57 is on the E&M, paired with 66982 (PFS global 090, a major surgical procedure) -> "
            "bypass.",
        ),
        (I14, I13),
    ),
    draft(
        "R11-17",
        "Modifier 57 with a 000-day procedure does not bypass",
        PRIMARY,
        ("E1142",),
        (L("11720"), L("99213", modifiers=("57",))),
        ("PASS", BUNDLED),
        (
            EDIT.format(a="11720", b="99213"),
            "57 needs a paired code with PFS global 090; 11720 is 000 -> no bypass -> line 2 "
            "denied.",
        ),
        (I14, I13),
    ),
    draft(
        "R11-18",
        "Modifier 25 between two E&M services does not bypass",
        PRIMARY,
        ("E1142",),
        (L("99213"), L("99212", modifiers=("25",))),
        ("PASS", BUNDLED),
        (
            EDIT.format(a="99213", b="99212"),
            "25 counts on an E&M paired with a non-E&M code; both lines are E&M -> no bypass -> "
            "line 2 denied.",
        ),
        (I14, I16),
    ),
    draft(
        "R11-19",
        "Modifier 58 on the column-2 procedure bypasses",
        GI,
        ("K635",),
        (L("45385"), L("45380", modifiers=("58",))),
        ("PASS", BYPASS),
        (
            EDIT.format(a="45385", b="45380"),
            "58 is on a procedure line (not an E&M) -> bypass.",
        ),
        (I14, I16),
    ),
    draft(
        "R11-20",
        "Modifier 58 on an E&M line does not bypass",
        PRIMARY,
        ("E1142",),
        (L("11720"), L("99213", modifiers=("58",))),
        ("PASS", BUNDLED),
        (
            EDIT.format(a="11720", b="99213"),
            "58 counts only on a non-E&M line -> no bypass -> line 2 denied.",
        ),
        (I14, I16),
    ),
    draft(
        "R11-21",
        "Anatomic modifiers for different sites bypass",
        RADIOLOGY,
        ("M25561", "M25562"),
        (L("76881", "A", ("RT",)), L("76882", "B", ("LT",))),
        ("PASS", BYPASS),
        (
            EDIT.format(a="76881", b="76882"),
            "Both lines carry an anatomic modifier and they share none (RT, LT) -> different "
            "sites -> bypass.",
        ),
        (I14, I17),
    ),
    draft(
        "R11-22",
        "Anatomic modifiers for the same site do not bypass",
        RADIOLOGY,
        ("M25561",),
        (L("76881", modifiers=("RT",)), L("76882", modifiers=("RT",))),
        ("PASS", BUNDLED),
        (
            EDIT.format(a="76881", b="76882"),
            "Both lines carry RT: the same site -> no bypass -> line 2 denied.",
        ),
        (I14, I17),
    ),
)

R11_06 = {  # D-GOLD-7: reworded; expected values unchanged
    "title": "Laterality on one line alone does not bypass",
    "worked_steps": [
        "PTP 45385/45380 indicator 1.",
        "LT is an anatomic modifier, but only line 2 carries one: no two different anatomic "
        "sites (D-RULE-8) -> no bypass -> line 2 DENY DN_NCCI_BUNDLED.",
    ],
}


def expected_for(d: Draft, claim: Mapping[str, Any], tables: Tables, lookups: Lookups) -> dict:
    em = em_codes(lookups.curated)
    lines: list[Line] = lines_of(claim)
    results = r11(lines, tables, option_b, em, tables.global_days)
    computed = [BUNDLED if r == "DENY" else BYPASS if r == "BYPASS" else "PASS" for r in results]
    if list(d.expect) != computed:
        raise SystemExit(f"{d.case_id}: stated {d.expect} != computed {computed}")
    if v2_checks(claim, lookups):
        raise SystemExit(f"{d.case_id}: a rules v2 check fires: {v2_checks(claim, lookups)}")
    outcomes = [
        {
            "line_no": x.line_no,
            "outcome": r.split()[0],
            "reason_codes": ["DN_NCCI_BUNDLED"] if r == BUNDLED else [],
            "flags": ["NCCI_BYPASS"] if r == BYPASS else [],
        }
        for x, r in zip(lines, computed, strict=True)
    ]
    denied = all(o["outcome"] == "DENY" for o in outcomes)
    return {
        "claim_outcome": "DENY" if denied else "PASS",
        "status": "DENIED_BY_RULE" if denied else "RECEIVED",
        "failures": [
            {"rule_id": "R11", "outcome": "DENY", "reason_code": "DN_NCCI_BUNDLED"}
            | {"line_no": o["line_no"]}
            for o in outcomes
            if o["reason_codes"]
        ],
        "line_outcomes": outcomes,
        "flags": [],
    }


def v1_r11(cases: Sequence[Mapping[str, Any]]) -> dict[str, list[str]]:
    """Every drafted claim on the current engine: Groups A and B pass (else stop); v1's R11
    result per line, to show where rules v2.1 differ."""
    from app.db.curated import rule_codes
    from app.db.rules_reference import build_reference, load_code_tables
    from app.rules.engine import evaluate

    shared = reference()
    curated = load_curated()
    codes = {x["procedure_code"] for c in cases for x in c["given"]["claim"]["service_lines"]}
    tables = load_code_tables(rule_codes(curated) | codes)
    out = {}
    for case in cases:
        given = case["given"]
        ref = build_reference(
            curated,
            tables,
            shared["members"],
            shared["providers"],
            shared["provider_networks"],
            [*shared["authorizations"], *given["reference_additions"].get("authorizations", [])],
            shared["existing_claims"],
        )
        outcome = evaluate(given["claim"], {}, ref, confidence_min=0.85)
        stops = [r for r in outcome.rule_results if not r.passed and r.line_no is None]
        if stops or not outcome.line_outcomes:
            raise SystemExit(f"{case['case_id']}: stops before Group C: {stops}")
        out[case["case_id"]] = [
            "DENY" if line.reason_codes else ("BYPASS" if line.flags else "PASS")
            for line in outcome.line_outcomes
        ]
    return out


RULE_TEXT = """\
R11 (A-R3 as amended by D-RULE-8; RULES_VERSION 2.1.0). For two lines on the same date of service,
the first NCCI edit active that day with line A's code in column 1 and line B's in column 2 applies
(indicator 9: none). Indicator 0: line B is denied, DN_NCCI_BUNDLED. Indicator 1: line B passes
with the flag NCCI_BYPASS when an NCCI PTP-associated modifier is reported where the manual places
it, and is denied DN_NCCI_BUNDLED otherwise. The modifiers and their places:

- 59, XE, XP, XS, XU: on either line, but not on an E&M line.
- 24, 25, 57: on an E&M line paired with a non-E&M code; 25 only when that code's PFS global period
  is 000, 010 or XXX; 57 only when it is 090.
- 58, 78, 79: on a non-E&M line (either column).
- 27, 91: on either line.
- Anatomic (E1-E4, FA, F1-F9, TA, T1-T9, LT, RT, LC, LD, RC, LM, RI): only when both lines carry an
  anatomic modifier and they share none (different sites).

E&M lines are the office visit codes 99202-99205 and 99211-99215. A line with no reason code
passes; when every line is denied the claim is DENY, otherwise PASS. Every claim below passes
Groups A and B and rules R12 to R20; only R11 decides."""


def facts(claim: Mapping[str, Any], tables: Tables, em: frozenset[str]) -> list[str]:
    codes = [x["procedure_code"] for x in claim["service_lines"]]
    day = date.fromisoformat(claim["service_lines"][0]["date_of_service"])
    out = []
    for a in codes:
        for b in codes:
            edits = [e for e in tables.ncci.get((a, b), ()) if e.active_on(day)]
            if a != b and edits:
                out.append(f"NCCI {a}/{b} (column 1/column 2): modifier indicator "
                           f"{edits[0].modifier_indicator}")  # fmt: skip
    for code in dict.fromkeys(codes):
        kind = "E&M" if code in em else "not E&M"
        out.append(f"{code}: {kind}, PFS global {tables.global_days.get(code, '-')}")
    return out


def build_sheet(cases: Sequence[Mapping[str, Any]], tables: Tables, em: frozenset[str]) -> str:
    out = [
        "# R11 modifier golden cases: independent check (Task G5)",
        "",
        "For one reviewer, or a separate Claude chat that sees only this sheet (D-GOLD-2). Work "
        "out each case from the inputs, the facts and the rule text, then fill in the blank cells. "
        "**Do not open data/generated/verification/new_golden/ until every cell is filled.**",
        "",
        "## Rule text",
        "",
        RULE_TEXT,
        "",
        "Claim statuses (INSTRUCTIONS.md section 5; a PASS claim stays RECEIVED, a DENY claim is "
        "DENIED_BY_RULE):",
        "",
        *status_table(),
        "",
        "## Cases",
    ]
    for n, case in enumerate(cases, start=1):
        claim = case["given"]["claim"]
        out += ["", f"### Case {n} ({case['case_id']})", ""]
        out += ["| Line | Date | Code | Units | Modifiers |", "|---|---|---|---|---|"]
        out += [
            f"| {s['line_no']} | {s['date_of_service']} | {s['procedure_code']} | {s['units']} | "
            f"{' '.join(s['modifiers']) or '-'} |"
            for s in claim["service_lines"]
        ]
        out += ["", "Facts: " + "; ".join(facts(claim, tables, em)) + ".", ""]
        out += [
            "Claim outcome (PASS / DENY): ____ | Status: ____",
            "",
            "| Line | Outcome (PASS / DENY) | Reason codes | Flags |",
            "|---|---|---|---|",
            *(f"| {s['line_no']} |  |  |  |" for s in claim["service_lines"]),
        ]
    return "\n".join(out) + "\n"


def main() -> None:
    if not raw.raw_available():
        raise SystemExit("data/raw/ is required (see SOURCES.md)")
    curated = load_curated()
    articles = raw.read_article_diagnoses(billing_articles(curated))
    lookups = Lookups(curated, {a: d.covered for a, d in articles.items()})
    codes = {x.code for d in DRAFTS for x in d.lines}
    tables = tables_for(codes)
    cases = []
    for d in DRAFTS:
        claim = claim_for(d)
        auths = authorizations(d, curated)
        cases.append(
            {
                "case_id": d.case_id,
                "title": d.title,
                "rules": list(d.rules),
                "given": {
                    "claim": claim,
                    "source_format": "JSON",
                    "field_confidences": {},
                    "reference_additions": {"authorizations": auths} if auths else {},
                },
                "expected": expected_for(d, claim, tables, lookups),
                "worked_steps": [
                    *(
                        f"R10: authorization {a['auth_number']} covers {a['procedure_code']}."
                        for a in auths
                    ),  # fmt: skip
                    *d.steps,
                ],
                "sources": list(d.sources),
            }
        )
    v1 = v1_r11(cases)
    changed = {
        c["case_id"]: v1[c["case_id"]]
        for c in cases
        if v1[c["case_id"]]
        != [
            "DENY" if o["reason_codes"] else ("BYPASS" if o["flags"] else "PASS")
            for o in c["expected"]["line_outcomes"]
        ]
    }
    STAGING.mkdir(parents=True, exist_ok=True)
    CASES_FILE.write_text(
        json.dumps({TARGET: cases, "R11-06": R11_06}, indent=2) + "\n", encoding="utf-8"
    )
    SHEET_FILE.write_text(build_sheet(cases, tables, em_codes(curated)), encoding="utf-8")
    print(f"{len(cases)} cases for {TARGET}; wrote {CASES_FILE.name} and {SHEET_FILE.name}")
    print("every drafted claim passes Groups A and B and rules R12 to R20")
    print(f"cases where rules v1's R11 differs (v1 per line): {changed}")


if __name__ == "__main__":
    main()
