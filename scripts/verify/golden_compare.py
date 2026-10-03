"""Task G2: write the spot-check answers into the G1 sheet, check that no answer cell is blank,
compare the answers with the golden expected values and record the result. Report only: no
golden case is changed.

The answers below were computed by a separate Claude chat from the sheet's text only, without
access to the repository or the answers file, and accepted by the reviewer (Manideep3183,
2026-10-03). They are entered word for word. Only answer, verdict and notes cells are written; a
cell that already holds a different value keeps the file's value and is reported as a conflict.

    uv run python -m scripts.verify.golden_compare fill     # write the answers into empty cells
    uv run python -m scripts.verify.golden_compare check    # G2 step 1: blank or unreadable cells
    uv run python -m scripts.verify.golden_compare compare  # G2 steps 2-4: summary and copies
"""

import argparse
import csv
import re
import shutil
from collections import Counter, defaultdict
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from scripts.verify.golden_checks import ANSWERS_FILE, OUT_DIR, SHEET_FILE, load_cases
from scripts.verify.review_verdicts import COPIES_DIR, check_descriptors

SUMMARY_FILE = "G_summary.md"
PROVENANCE = (
    "The spot-check answers were computed by a separate Claude chat from the sheet's text only, "
    "without access to the repository or the answers file, and accepted by the reviewer. This is "
    "a Claude recomputation, not a blind human check, and not independent of the golden cases' "
    "author (also Claude). P-01 is not independent (the sheet leaked its outcome; fixed in G2). "
    "The rules sample is only partly blind, because the sheet names the rule each case "
    "exercises; the calculator cases show no expected values but list the assumptions each case "
    "relies on (C19 and C21 name A4, the out-of-pocket cap)."
)
VERDICT = "ACCEPT / CHANGE"
VERDICTS = ("ACCEPT", "CHANGE")
MY_OUTCOME = "My outcome"
AMOUNT_COLUMNS = (
    "Allowed",
    "Deductible applied",
    "Copay",
    "Coinsurance",
    "Plan pays",
    "Member pays",
)
AMOUNT_FIELDS = dict(
    zip(
        AMOUNT_COLUMNS,
        (
            "allowed_cents",
            "deductible_cents",
            "copay_cents",
            "coinsurance_cents",
            "plan_pays_cents",
            "member_pays_cents",
        ),
        strict=True,
    )
)
OUTCOMES = ("REJECT", "DENY", "PEND", "PASS")
FLAGS = frozenset({"OON", "NCCI_BYPASS"})

# --- the answers, word for word ---------------------------------------------------------------

RULES_ANSWERS: dict[int, tuple[str, str, str]] = {  # sheet number -> (case, my outcome, notes)
    1: (
        "H5-02",
        "REJECT RJ_LOW_CONFIDENCE_FIELD",
        "R10 fails (auth required, none on file), which would be DENY DN_NO_AUTH; procedure code "
        "read at 0.80, a field R10 uses, so H5 gives REJECT",
    ),
    2: (
        "DUP-01",
        "REJECT RJ_DUPLICATE",
        "same member, billing NPI, date and 99213 as CLM-EXIST-01, status not REJECTED",
    ),
    3: (
        "R11-09",
        "PASS; line 2 flag NCCI_BYPASS",
        "pair 45385/45380 allows bypass (indicator 1); XS on line 2; other rules pass",
    ),
    4: (
        "R03-04",
        "REJECT RJ_INVALID_NPI",
        "billing NPI has 9 digits (A-R8 to R03); Group A stops before R06",
    ),
    5: ("R02-01", "REJECT RJ_INVALID_CODE", '"M54.1" is not a valid FY2027 code as written'),
    6: (
        "R09-01",
        "DENY DN_MISSING_REFERRAL",
        "HMO requires referral for cardiology; rendering provider is cardiology; no referring NPI",
    ),
    7: (
        "P-01",
        "PASS",
        "every rule passes; status stays RECEIVED (A-R10). Not independent: computed after the "
        "sheet leak",
    ),
    8: ("R01-02", "REJECT RJ_MISSING_FIELD", "line 1 procedure code missing"),
    9: ("R04-01", "REJECT RJ_MEMBER_NOT_FOUND", "MBR-999999 not in member records"),
    10: (
        "R06-04",
        "DENY DN_NOT_ELIGIBLE (R06 PEND PD_PROVIDER_ENROLLMENT also recorded)",
        "service 2026-11-05 after coverage end 2026-10-31 gives R05 DENY; provider pending gives "
        "R06 PEND; DENY beats PEND in Group B",
    ),
}
# (sheet number, line) -> (case, (allowed, deductible applied, copay, coinsurance, plan pays,
# member pays), notes)
CALCULATOR_ANSWERS: dict[tuple[int, int], tuple[str, tuple[int, ...], str]] = {
    (1, 1): ("C04", (9000, 0, 2500, 0, 6500, 2500), "billed below fee, so allowed = billed"),
    (2, 1): (
        "C10",
        (24425, 24425, 0, 0, 0, 24425),
        "deductible not met; all of allowed to deductible",
    ),
    (3, 1): ("C49", (24425, 24425, 0, 0, 0, 24425), "remaining deductible 24425 equals allowed"),
    (4, 1): (
        "C30",
        (13561, 0, 0, 5424, 8137, 5424),
        "out of network (A3): 40% of 13561 = 5424.4, rounded to 5424; balance-bill 13439 not in "
        "member pays (A9)",
    ),
    (5, 1): (
        "C19",
        (39621, 0, 0, 5000, 34621, 5000),
        "20% = 7924.2 rounded to 7924, capped at remaining out-of-pocket 5000 (A4)",
    ),
    (6, 1): (
        "C21",
        (16951, 0, 1000, 0, 15951, 1000),
        "copay 5000 capped at remaining out-of-pocket 1000 (A4)",
    ),
    (7, 1): (
        "C31",
        (19540, 0, 0, 9770, 9770, 9770),
        "out-of-network Silver plan, deductible met, 50%",
    ),
    (8, 1): (
        "C41",
        (13561, 0, 0, 5424, 7561, 0),
        "normal plan payment 8137; secondary pays min(8137, 13561 - 6000 = 7561); member pays 0 "
        "(A6)",
    ),
    (9, 1): ("C26", (11899, 0, 2500, 0, 9399, 2500), "copay; does not touch the deductible"),
    (9, 2): ("C26", (0, 0, 0, 0, 0, 0), "denied line (A7)"),
    (9, 3): ("C26", (24591, 24591, 0, 0, 0, 24591), "full deductible still remaining"),
}
ASSUMPTION_IDS = (*(f"A-R{n}" for n in range(1, 12)), *(f"A{n}" for n in range(1, 10)))
ASSUMPTIONS: dict[str, tuple[str, str]] = {
    **dict.fromkeys(ASSUMPTION_IDS, ("ACCEPT", "")),
    "A-R3": (
        "CHANGE",
        "add modifier 59, the standard NCCI-associated modifier; check the full list in the NCCI "
        "Policy Manual; frozen for v1, so a v2 change",
    ),
    "A2": (
        "ACCEPT",
        "matches §8.6 as written; real plans usually charge one copay per visit, consider in v2",
    ),
    "A6": ("ACCEPT", "design choice: some plans credit only what the member actually paid"),
}
H5_RULES = ("R01", "R02", "R03", "R04", "DUP", *(f"R{n:02d}" for n in range(5, 14)))
H5_VERDICTS: dict[str, tuple[str, str]] = {
    **dict.fromkeys(H5_RULES, ("ACCEPT", "")),
    "R07": ("CHANGE", "add member_id: the filing window comes from the member's plan"),
    "R09": ("CHANGE", "add member_id: referral rules come from the member's plan"),
}
NOT_INDEPENDENT = {"P-01": "computed after the sheet leaked its outcome (fixed in G2)"}
# What the CHANGE rows would change, measured on the golden rules cases (report only): the H5
# mapping rows marked CHANGE, as their notes say, and the bypass modifier A-R3's note adds.
REVIEWED_H5_FIELDS: dict[str, tuple[str, ...]] = {"R07": ("member_id",), "R09": ("member_id",)}
REVIEWED_BYPASS_MODIFIER = "59"
# Proposed causes of mismatches, keyed (case, line or None, column or None); filled after the
# comparison is read, never before.
CAUSES: dict[tuple[str, int | None, str | None], str] = {}

# --- the sheet --------------------------------------------------------------------------------

PIPE = re.compile(r"(?<!\\)\|")  # a cell border; "\|" inside a cell is text
SEPARATOR = re.compile(r":?-+:?")
SECTION = re.compile(r"^### (Rules|Calculator) case (\d+) \(([^)]+)\)$")
Key = tuple[Any, ...]
Conflict = tuple[str, str, str, str]  # (where, column, file's value, recorded value)


@dataclass(frozen=True)
class Slot:
    """An answer row of the sheet: a table row with answer cells, or a calculator Notes line."""

    index: int  # 0-based line number
    key: Key  # ("assumption", ID) | ("h5", rule) | ("rules", n) | ("calculator", n, line)
    # | ("notes", n)
    case_id: str
    header: tuple[str, ...]  # the row's columns; ("Notes",) for a Notes line
    cells: tuple[str, ...]
    answers: tuple[str, ...]  # the columns the reviewer fills


def _cells(line: str) -> list[str]:
    return [c.strip() for c in PIPE.split(line)[1:-1]]


def _answer_columns(kind: str, header: tuple[str, ...]) -> tuple[str, ...]:
    if kind in ("assumption", "h5") and VERDICT in header:
        return VERDICT, "Notes"
    if kind == "rules" and header and header[0] == MY_OUTCOME:
        return MY_OUTCOME, "Notes"
    if kind == "calculator" and header == ("Line", *AMOUNT_COLUMNS):
        return AMOUNT_COLUMNS
    return ()


def slots(lines: Sequence[str]) -> list[Slot]:
    found: list[Slot] = []
    kind, number, case_id = "", 0, ""
    header: tuple[str, ...] | None = None
    notes_seen: set[int] = set()
    for i, line in enumerate(lines):
        if line.startswith("## "):
            kind = (
                "assumption"
                if line.startswith("## Golden assumptions")
                else "h5"
                if line.startswith("## H5 field mapping")
                else ""
            )
            number, case_id, header = 0, "", None
            continue
        section = SECTION.match(line)
        if section:
            kind, number, case_id = (
                section.group(1).lower(),
                int(section.group(2)),
                section.group(3),
            )
            header = None
            continue
        if not line.startswith("|"):
            header = None
            if kind == "calculator" and line.startswith("Notes:") and number not in notes_seen:
                notes_seen.add(number)
                text = line[len("Notes:") :].strip()
                found.append(Slot(i, ("notes", number), case_id, ("Notes",), (text,), ("Notes",)))
            continue
        cells = _cells(line)
        if all(SEPARATOR.fullmatch(c) for c in cells):
            continue
        if header is None:
            header = tuple(MY_OUTCOME if c.startswith(MY_OUTCOME) else c for c in cells)
            continue
        answers = _answer_columns(kind, header)
        if not answers:
            continue
        if len(cells) != len(header):
            raise ValueError(f"line {i + 1}: {len(cells)} cells under {len(header)} columns")
        key: Key = (
            (kind, cells[0])
            if kind in ("assumption", "h5")
            else ("rules", number)
            if kind == "rules"
            else ("calculator", number, int(cells[0]))
        )
        found.append(Slot(i, key, case_id, header, tuple(cells), answers))
    return found


def where(key: Key, case_id: str = "") -> str:
    kind = key[0]
    if kind == "assumption":
        return f"Assumption {key[1]}"
    if kind == "h5":
        return f"H5 {key[1]}"
    if kind == "rules":
        return f"Rules {key[1]} ({case_id})"
    if kind == "calculator":
        return f"Calculator {key[1]} ({case_id}) line {key[2]}"
    return f"Calculator {key[1]} ({case_id}) notes"


def fill_sheet(
    lines: Sequence[str],
    plan: Mapping[Key, Mapping[str, str]],
    case_ids: Mapping[Key, str],
) -> tuple[list[str], list[Conflict], int]:
    """(lines, conflicts, cells written). Writes the planned values into empty answer cells;
    a planned row that is not in the sheet, or sits under another case, stops the run."""
    for key, values in plan.items():
        if any("|" in v or "\n" in v for v in values.values()):
            raise ValueError(f"{key}: a value holds a pipe or line break")
    out = list(lines)
    conflicts: list[Conflict] = []
    written = 0
    found: Counter[Key] = Counter()
    for slot in slots(lines):
        if slot.key not in plan:
            continue
        found[slot.key] += 1
        expected_case = case_ids.get(slot.key)
        if expected_case is not None and slot.case_id != expected_case:
            raise ValueError(
                f"{where(slot.key, slot.case_id)}: the answers are for {expected_case}"
            )
        parts = PIPE.split(lines[slot.index])
        for column, value in plan[slot.key].items():
            current = slot.cells[slot.header.index(column)]
            if not value or current == value:
                continue
            if current:
                conflicts.append((where(slot.key, slot.case_id), column, current, value))
                continue
            if slot.key[0] == "notes":
                out[slot.index] = f"Notes: {value}"
            else:
                parts[slot.header.index(column) + 1] = f" {value} "
                out[slot.index] = "|".join(parts)
            written += 1
    missing = [key for key in plan if not found[key]]
    if missing:
        raise ValueError(f"not in the sheet: {missing}")
    repeated = [key for key, n in found.items() if n > 1]
    if repeated:
        raise ValueError(f"in the sheet more than once: {repeated}")
    return out, conflicts, written


def recorded_plan() -> tuple[dict[Key, dict[str, str]], dict[Key, str]]:
    """The recorded answers as (values per answer row, case ID per case row)."""
    plan: dict[Key, dict[str, str]] = {}
    cases: dict[Key, str] = {}
    for n, (case_id, outcome, notes) in RULES_ANSWERS.items():
        plan[("rules", n)] = {MY_OUTCOME: outcome, "Notes": notes}
        cases[("rules", n)] = case_id
    by_case: dict[int, list[tuple[int, str, str]]] = defaultdict(list)
    for (n, line), (case_id, amounts, notes) in CALCULATOR_ANSWERS.items():
        plan[("calculator", n, line)] = {
            c: str(a) for c, a in zip(AMOUNT_COLUMNS, amounts, strict=True)
        }
        cases[("calculator", n, line)] = case_id
        by_case[n].append((line, case_id, notes))
    for n, items in by_case.items():  # the sheet has one Notes line per calculator case
        text = (
            items[0][2]
            if len(items) == 1
            else " / ".join(f"line {line}: {note}" for line, _, note in items)
        )
        plan[("notes", n)] = {"Notes": text}
        cases[("notes", n)] = items[0][1]
    for kind, verdicts in (("assumption", ASSUMPTIONS), ("h5", H5_VERDICTS)):
        for row, (verdict, notes) in verdicts.items():
            plan[(kind, row)] = {VERDICT: verdict, "Notes": notes}
    return plan, cases


def check_cells(found: Sequence[Slot]) -> list[str]:
    """Blank or unreadable answer cells. Notes are optional."""
    problems = []
    for slot in found:
        for column in slot.answers:
            if column == "Notes":
                continue
            value = slot.cells[slot.header.index(column)]
            label = f"{where(slot.key, slot.case_id)}: {column}"
            if not value:
                problems.append(f"{label} is blank")
            elif column == VERDICT and value not in VERDICTS:
                problems.append(f"{label} is {value}, not ACCEPT or CHANGE")
            elif column in AMOUNT_COLUMNS and not re.fullmatch(r"\d+", value):
                problems.append(f"{label} is {value}, not whole cents")
            elif column == MY_OUTCOME and not re.search(rf"\b({'|'.join(OUTCOMES)})\b", value):
                problems.append(f"{label} names no REJECT, DENY, PEND or PASS")
    return problems


# --- comparison -------------------------------------------------------------------------------


@dataclass(frozen=True)
class Outcome:
    outcome: str
    reasons: frozenset[str]
    flags: frozenset[str]


def _words(text: str) -> set[str]:
    return set(re.findall(r"\b[A-Z][A-Z0-9_]+\b", text))


def parse_outcome(text: str, reason_codes: Collection[str]) -> Outcome:
    """The first outcome word, the internal reason codes and the flags named in free text."""
    first = re.search(rf"\b({'|'.join(OUTCOMES)})\b", text)
    words = _words(text)
    return Outcome(
        first.group(1) if first else "",
        frozenset(words & set(reason_codes)),
        frozenset(words & FLAGS),
    )


def expected_outcome(row: Mapping[str, str], reason_codes: Collection[str]) -> Outcome:
    words = _words(" ".join((row["failures"], row["line_outcomes"], row["flags"])))
    return Outcome(
        row["claim_outcome"], frozenset(words & set(reason_codes)), frozenset(words & FLAGS)
    )


def compare_amounts(
    mine: Mapping[str, str], expected: Mapping[str, str]
) -> list[tuple[str, str, str]]:
    """(column, mine, expected) for every amount that differs, exact to the cent."""
    return [
        (column, mine[column], expected[field])
        for column, field in AMOUNT_FIELDS.items()
        if mine[column] != expected[field]
    ]


def reviewed_mapping(
    base: Mapping[str, tuple[str, ...]], changes: Mapping[str, tuple[str, ...]]
) -> dict[str, tuple[str, ...]]:
    """The H5 field mapping with the fields the CHANGE rows add."""
    return {rule: (*fields, *changes.get(rule, ())) for rule, fields in base.items()}


def change_effects() -> list[str]:
    """What the CHANGE rows would change in the golden rules cases (report only)."""
    from scripts.verify import golden_checks as g

    spec = g.parse_instructions(g.INSTRUCTIONS_MD.read_text(encoding="utf-8"))
    cases = load_cases("rules")

    def h5_findings(fields: Mapping[str, tuple[str, ...]]) -> set[tuple[str, str]]:
        return {
            (f.case_id, f.check)
            for case in cases
            for f in g.check_rules_case(case, spec, fields)
            if f.check.startswith("H5")
        }

    before = h5_findings(g.FIELDS_USED)
    after = h5_findings(reviewed_mapping(g.FIELDS_USED, REVIEWED_H5_FIELDS))
    new = sorted(after - before)
    with_modifier = sorted(
        case["case_id"]
        for case in cases
        if any(
            isinstance(line, Mapping)
            and isinstance(line.get("modifiers"), list)
            and REVIEWED_BYPASS_MODIFIER in line["modifiers"]
            for line in case["given"]["claim"].get("service_lines") or []
        )
    )
    return [
        f"H5 check with member_id added to R07 and R09 (H5 mapping rows marked CHANGE): "
        f"{len(after)} findings on the {len(cases)} rules cases ({len(before)} with the G1 "
        "mapping)"
        + (
            "; new: " + ", ".join(f"{c} ({check})" for c, check in new)
            if new
            else "; no golden rules case is affected."
        ),
        f"Golden rules cases with modifier {REVIEWED_BYPASS_MODIFIER} on a line (A-R3 marked "
        f"CHANGE): {len(with_modifier)}"
        + (
            f" ({', '.join(with_modifier)}); their expected R11 outcomes need review if "
            f"{REVIEWED_BYPASS_MODIFIER} becomes a bypass modifier."
            if with_modifier
            else f"; making {REVIEWED_BYPASS_MODIFIER} a bypass modifier changes no golden rules "
            "case."
        ),
    ]


def _outcome_text(o: Outcome) -> str:
    parts = [o.outcome, *sorted(o.reasons)]
    if o.flags:
        parts.append("flags " + ", ".join(sorted(o.flags)))
    return " ".join(parts)


def summarize(found: Sequence[Slot], expected_rows: Sequence[Mapping[str, str]]) -> str:
    from app.db.curated import load_curated

    reason_codes = set(load_curated().reason_codes)
    worked = {
        c["case_id"]: c["worked_steps"] for f in ("rules", "calculator") for c in load_cases(f)
    }
    by_key = {s.key: s for s in found}
    rules_expected = {
        int(r["sheet_no"].split()[1]): r for r in expected_rows if r["kind"] == "rules"
    }
    calc_expected = {
        (int(r["sheet_no"].split()[1]), int(r["line_no"])): r
        for r in expected_rows
        if r["kind"] == "calculator" and r["line_no"] != "total"
    }

    rules_rows, mismatches = [], []
    agreed = agreed_independent = 0
    for n, row in sorted(rules_expected.items()):
        slot = by_key[("rules", n)]
        mine_text = slot.cells[slot.header.index(MY_OUTCOME)]
        mine = parse_outcome(mine_text, reason_codes)
        expected = expected_outcome(row, reason_codes)
        ok = mine == expected
        independent = slot.case_id not in NOT_INDEPENDENT
        agreed += ok
        agreed_independent += ok and independent
        rules_rows.append(
            f"| {n} | {slot.case_id} | {mine_text} | {_outcome_text(expected)} | "
            f"{'yes' if ok else '**no**'} | "
            f"{'yes' if independent else 'no: ' + NOT_INDEPENDENT[slot.case_id]} |"
        )
        if not ok:
            mismatches.append(
                (slot.case_id, None, None, mine_text, _outcome_text(expected), worked[slot.case_id])
            )
    calc_rows = []
    lines_agreed = cells_agreed = 0
    for (n, line), row in sorted(calc_expected.items()):
        slot = by_key[("calculator", n, line)]
        mine = {c: slot.cells[slot.header.index(c)] for c in AMOUNT_COLUMNS}
        differs = compare_amounts(mine, row)
        lines_agreed += not differs
        cells_agreed += len(AMOUNT_COLUMNS) - len(differs)
        calc_rows.append(
            f"| {n} | {slot.case_id} | {line} | "
            + " / ".join(mine[c] for c in AMOUNT_COLUMNS)
            + " | "
            + " / ".join(row[AMOUNT_FIELDS[c]] for c in AMOUNT_COLUMNS)
            + f" | {'yes' if not differs else '**no**: ' + ', '.join(c for c, _, _ in differs)} |"
        )
        for column, mine_value, expected_value in differs:
            mismatches.append(
                (slot.case_id, line, column, mine_value, expected_value, worked[slot.case_id])
            )
    independent_rules = sum(
        by_key[("rules", n)].case_id not in NOT_INDEPENDENT for n in rules_expected
    )
    verdicts = {
        kind: Counter(s.cells[s.header.index(VERDICT)] for s in found if s.key[0] == kind)
        for kind in ("assumption", "h5")
    }
    changed = [
        s
        for s in found
        if s.key[0] in ("assumption", "h5") and s.cells[s.header.index(VERDICT)] == "CHANGE"
    ]
    accepted_with_note = [
        s
        for s in found
        if s.key[0] in ("assumption", "h5")
        and s.cells[s.header.index(VERDICT)] == "ACCEPT"
        and s.cells[s.header.index("Notes")]
    ]
    lines = [
        "# Golden-test spot-check: comparison (Task G2)",
        "",
        PROVENANCE,
        "",
        "## Result",
        "",
        f"- Rules cases: {agreed} of {len(rules_expected)} agree on outcome, reason codes and "
        f"flags; {agreed_independent} of the {independent_rules} independent cases.",
        f"- Calculator: {lines_agreed} of {len(calc_expected)} lines agree on all six amounts, "
        f"exact to the cent ({cells_agreed} of {len(calc_expected) * len(AMOUNT_COLUMNS)} "
        "amounts).",
        f"- Mismatches: {len(mismatches)}. No golden case was changed.",
        "- Golden assumptions: "
        + ", ".join(f"{v} {n}" for v, n in sorted(verdicts["assumption"].items()))
        + "; H5 field mapping: "
        + ", ".join(f"{v} {n}" for v, n in sorted(verdicts["h5"].items()))
        + ".",
        "",
        "## Rules cases",
        "",
        "Agreement means the same claim outcome, the same internal reason codes and the same "
        "flags (OON, NCCI_BYPASS).",
        "",
        "| # | Case | My outcome | Expected (outcome, reason codes, flags) | Agrees "
        "| Independent |",
        "|---|---|---|---|---|---|",
        *rules_rows,
        "",
        "## Calculator cases",
        "",
        "Amounts in cents: allowed / deductible applied / copay / coinsurance / plan pays / "
        "member pays.",
        "",
        "| # | Case | Line | My amounts | Expected amounts | Agrees |",
        "|---|---|---|---|---|---|",
        *calc_rows,
        "",
        "## Mismatches",
        "",
    ]
    if not mismatches:
        lines += ["None: every answer agrees with the golden expected value.", ""]
    for case_id, line_no, column, mine_value, expected_value, steps in mismatches:
        label = (
            case_id + (f" line {line_no}" if line_no else "") + (f", {column}" if column else "")
        )
        cause = CAUSES.get((case_id, line_no, column), "not yet proposed")
        lines += [
            f"### {label}",
            "",
            f"- Mine: {mine_value}",
            f"- Expected: {expected_value}",
            f"- Proposed cause (Claude): {cause}",
            "- Golden worked steps:",
            *[f"  - {step}" for step in steps],
            "",
        ]
    lines += [
        "## Assumptions and H5 mapping rows marked CHANGE",
        "",
        "| Row | Verdict | Note |",
        "|---|---|---|",
        *[
            f"| {where(s.key)} | CHANGE | {s.cells[s.header.index('Notes')] or '-'} |"
            for s in changed
        ],
        "",
        "Accepted with a note:",
        "",
        *[f"- {where(s.key)}: {s.cells[s.header.index('Notes')]}" for s in accepted_with_note],
        "",
        "## Effect of the CHANGE rows on the golden cases (report only; nothing changed)",
        "",
        *[f"- {line}" for line in change_effects()],
    ]
    return "\n".join(lines) + "\n"


# --- run --------------------------------------------------------------------------------------


def _read_sheet() -> list[str]:
    return (OUT_DIR / SHEET_FILE).read_text(encoding="utf-8").splitlines()


def _check(lines: Sequence[str]) -> list[Slot]:
    found = slots(lines)
    problems = check_cells(found)
    if problems:
        raise SystemExit(
            f"{len(problems)} blank or unreadable cells:\n" + "\n".join(f"- {p}" for p in problems)
        )
    counts = Counter(s.key[0] for s in found)
    print(
        "no blank answer, verdict or amount cells: rules "
        f"{counts['rules']}, calculator lines {counts['calculator']}, assumptions "
        f"{counts['assumption']}, H5 rows {counts['h5']}"
    )
    return found


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("step", choices=("fill", "check", "compare"))
    step = parser.parse_args().step
    path = OUT_DIR / SHEET_FILE
    lines = _read_sheet()
    if step == "fill":
        plan, cases = recorded_plan()
        filled, conflicts, written = fill_sheet(lines, plan, cases)
        if filled != lines:
            path.write_text("\n".join(filled) + "\n", encoding="utf-8")
        print(f"{written} cells written; conflicts (file's value kept): {conflicts or 'none'}")
        return
    found = _check(lines)
    if step == "check":
        return
    with (OUT_DIR / ANSWERS_FILE).open(encoding="utf-8", newline="") as f:
        expected_rows = list(csv.DictReader(f))
    summary = OUT_DIR / SUMMARY_FILE
    summary.write_text(summarize(found, expected_rows), encoding="utf-8")
    paths = [path, summary]
    checked = check_descriptors(paths)
    COPIES_DIR.mkdir(parents=True, exist_ok=True)
    for p in paths:
        shutil.copyfile(p, COPIES_DIR / p.name)
    for line in summary.read_text(encoding="utf-8").splitlines():
        if line.startswith("- "):
            print(line)
        elif line.startswith("## Rules cases"):
            break
    print(f"no AMA CPT descriptor text ({checked} checked); copied {len(paths)} files")


if __name__ == "__main__":
    main()
