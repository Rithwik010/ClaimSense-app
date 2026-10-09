"""Task P2.3b checkpoint 3: compare the independent G4 answers with the drafted rules v2 cases and,
only if every compared cell agrees, add the cases to the golden set (D-GOLD-2, D-GOLD-6, H12).

The answers (G4_rules_v2_answers.md, the sheet with its cells filled) were worked out by a separate
Claude Code session with repository access, told to use only the sheet; it reports it did not open
new_golden/ or DECISIONS.md (2026-10-09). Like G3 this is a Claude recomputation, not a blind human
check, and not independent of the cases' author (also Claude).

The sheet named no claim statuses, so the checker described five status cells instead of naming
them (UNDECIDABLE). Those descriptions are mapped through the status table of INSTRUCTIONS.md
section 5 (a sheet gap, not a disagreement; the team's decision of 2026-10-09). A cell with no
drafted value (the claim decision of a rule-denied claim, which the decision record leaves empty)
is listed, not compared.

    uv run python -m scripts.verify.g4_compare compare   # report; writes G4_summary.md
    uv run python -m scripts.verify.g4_compare promote   # only if all agree: the golden set
"""

import argparse
import json
import re
import shutil
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scripts.verify.new_rules_cases import E2E_FILE, OUT_DIR, RULES_FILE
from scripts.verify.review_verdicts import COPIES_DIR, check_descriptors

ROOT = Path(__file__).resolve().parents[2]
ANSWERS_FILE = OUT_DIR / "G4_rules_v2_answers.md"
SUMMARY_FILE = OUT_DIR / "G4_summary.md"
GOLDEN_RULES = ROOT / "tests" / "golden" / "rules"
GOLDEN_E2E = ROOT / "tests" / "golden" / "e2e" / "cases.json"
CODE = re.compile(r"\b[A-Z]{2,}(?:_[A-Z0-9]+)+\b")  # reason codes and flags
CHECKER = (
    "a separate Claude Code session with repository access, told to use only the sheet, which "
    "reports it did not open new_golden/ or DECISIONS.md. Like G3, this is a Claude "
    "recomputation, not a blind human check, and not independent of the cases' author (also "
    "Claude)."
)
FINAL_STATUS = {
    "APPROVE": "FINAL_APPROVED",
    "DENY": "FINAL_DENIED",
    "PEND": "FINAL_PENDED",
    "PARTIAL": "FINAL_PARTIAL",
}


@dataclass(frozen=True)
class Cell:
    case: str
    field: str
    answer: str
    expected: str
    mapped_from: str = ""  # an UNDECIDABLE description mapped to a status

    @property
    def agrees(self) -> bool:
        return self.answer == self.expected


def sections(text: str) -> dict[str, list[str]]:
    """Each answered case's lines, keyed by case ID (rules cases and end-to-end cases)."""
    out: dict[str, list[str]] = {}
    current = None
    for line in text.splitlines():
        heading = re.match(r"^### (?:Case \d+ \((?P<id>[^)]+)\)|(?P<e2e>E2E-\d+))\s*$", line)
        if heading:
            current = heading.group("id") or heading.group("e2e")
            out[current] = []
        elif line.startswith("## "):
            current = None
        elif current:
            out[current].append(line)
    return out


def table_rows(lines: Sequence[str], header: str) -> list[list[str]]:
    """The rows of the table whose header starts with `header` (the answer table, not the
    inputs table above it)."""
    rows: list[list[str]] = []
    inside = False
    for line in lines:
        if line.startswith(header):
            inside = True
            continue
        if not inside:
            continue
        if not line.startswith("|"):
            if rows:
                break
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if cells and cells[0].isdigit():
            rows.append(cells)
    return rows


def codes(cell: str) -> str:
    return " ".join(CODE.findall(cell))


def first_word(cell: str, words: Sequence[str]) -> str:
    found = re.match(r"\s*([A-Z_]+)", cell)
    return found.group(1) if found and found.group(1) in words else ""


def value_after(lines: Sequence[str], label: str) -> str:
    for line in lines:
        for part in line.split(" | "):
            if part.startswith(f"{label}:"):
                return part.split(":", 1)[1].strip()
    raise ValueError(f"no '{label}' cell")


def status_from_description(text: str) -> str:
    """An UNDECIDABLE status cell, mapped through the status table of INSTRUCTIONS.md section 5:
    rule-denied and closed -> DENIED_BY_RULE (rule failure, final); waits for review ->
    AWAITING_REVIEW (ready for a human); an accepted claim decision -> its FINAL_* status
    (reviewer confirmed)."""
    accepted = re.search(r"accepted decision is (APPROVE|DENY|PEND|PARTIAL)", text)
    if accepted:
        return FINAL_STATUS[accepted.group(1)]
    if "rule-denied" in text and ("closes" in text or "never reaches" in text):
        return "DENIED_BY_RULE"
    if "waits for" in text and "review" in text:
        return "AWAITING_REVIEW"
    return ""


def status_cell(case: str, field: str, answer: str, expected: str) -> Cell:
    if answer.startswith("UNDECIDABLE"):
        return Cell(case, field, status_from_description(answer), expected, answer)
    return Cell(case, field, answer.split()[0] if answer else "", expected)


def rules_cells(case: Mapping[str, Any], lines: Sequence[str]) -> list[Cell]:
    case_id, expected = case["case_id"], case["expected"]
    outcome = value_after(lines, "Claim outcome (PASS / DENY / REJECT)")
    cells = [
        Cell(
            case_id,
            "claim outcome",
            first_word(outcome, ("PASS", "DENY", "REJECT")),
            expected["claim_outcome"],
        )
    ]
    if expected["claim_outcome"] == "REJECT":
        reasons = " ".join(f["reason_code"] for f in expected["failures"])
        cells.append(Cell(case_id, "REJECT reason", codes(outcome), reasons))
    rows = table_rows(lines, "| Line | Outcome")
    if expected["line_outcomes"] is None:
        answered = [r for r in rows if first_word(r[1], ("PASS", "DENY"))]
        cells.append(Cell(case_id, "line outcomes", "none" if not answered else "some", "none"))
        return cells
    for row, line in zip(rows, expected["line_outcomes"], strict=True):
        n = line["line_no"]
        cells += [
            Cell(
                case_id, f"line {n} outcome", first_word(row[1], ("PASS", "DENY")), line["outcome"]
            ),
            Cell(case_id, f"line {n} reasons", codes(row[2]), " ".join(line["reason_codes"])),
            Cell(case_id, f"line {n} flags", codes(row[3]), " ".join(line["flags"])),
        ]
    return cells


def drafted_lines(case: Mapping[str, Any]) -> list[tuple[str, str, str]]:
    """(decision, source, reason codes) per line: the recommendation's, or the rule denials."""
    recommendation = case["expected"]["recommendation"]
    if recommendation:
        return [
            (d["decision"], d["source"], " ".join(d["reason_codes"]))
            for d in recommendation["line_decisions"]
        ]
    reasons: dict[int, list[str]] = {}
    for failure in case["expected"]["rules"]["failures"]:
        reasons.setdefault(failure["line_no"], []).append(failure["reason_code"])
    return [("DENY", "RULE", " ".join(r)) for _, r in sorted(reasons.items())]


def e2e_cells(case: Mapping[str, Any], lines: Sequence[str]) -> tuple[list[Cell], list[str]]:
    case_id, expected = case["case_id"], case["expected"]
    recommendation = expected["recommendation"]
    reviewed = case["given"].get("review_action") is not None
    cells = [
        Cell(
            case_id,
            "rules claim outcome",
            value_after(lines, "Rules claim outcome").split()[0],
            expected["rules"]["claim_outcome"],
        ),
        status_cell(
            case_id,
            "status after processing",
            value_after(lines, "Status after processing"),
            expected["status_after_processing"],
        ),
    ]
    for row, (decision, source, reasons) in zip(
        table_rows(lines, "| Line | Decision"), drafted_lines(case), strict=True
    ):
        n = row[0]
        cells += [
            Cell(
                case_id,
                f"line {n} decision",
                first_word(row[1], ("APPROVE", "DENY", "PEND")),
                decision,
            ),
            Cell(
                case_id,
                f"line {n} source",
                first_word(row[2], ("RULE", "MODEL", "VALIDATION")),
                source,
            ),
            Cell(case_id, f"line {n} reasons", codes(row[3]), reasons),
        ]
    not_compared = []
    claim_decision = value_after(lines, "Claim decision")
    if recommendation:
        cells.append(
            Cell(case_id, "claim decision", claim_decision, recommendation["claim_decision"])
        )
    else:
        not_compared.append(
            f"{case_id} claim decision: answer {claim_decision}; the draft has none (a rule-denied "
            "claim's decision record leaves claim_decision empty; the rules claim outcome above "
            "is compared instead)"
        )
    tier = value_after(lines, "Review tier")
    cells.append(
        Cell(
            case_id,
            "review tier",
            tier.split()[0],
            recommendation["review_tier"] if recommendation else "N/A",
        )
    )
    final = value_after(lines, "Final status after ACCEPT (or N/A)")
    cells.append(
        status_cell(
            case_id,
            "final status after ACCEPT",
            final,
            expected["final"]["status"] if reviewed else "N/A",
        )
    )
    return cells, not_compared


def compare() -> tuple[list[Cell], list[str]]:
    answers = sections(ANSWERS_FILE.read_text(encoding="utf-8"))
    rules = [c for cases in json.loads(RULES_FILE.read_text()).values() for c in cases]
    e2e = json.loads(E2E_FILE.read_text())
    missing = [c["case_id"] for c in rules if c["case_id"] not in answers]
    missing += [case_id for case_id in e2e if case_id not in answers]
    if missing:
        raise SystemExit(f"no answers for {missing}")
    cells: list[Cell] = []
    not_compared: list[str] = []
    for case in rules:
        cells += rules_cells(case, answers[case["case_id"]])
    for case_id, case in e2e.items():
        found, extra = e2e_cells(case, answers[case_id])
        cells += found
        not_compared += extra
    return cells, not_compared


def summarize(cells: Sequence[Cell], not_compared: Sequence[str]) -> str:
    rules_cases = sorted({c.case for c in cells if not c.case.startswith("E2E")})
    e2e_cases = sorted({c.case for c in cells if c.case.startswith("E2E")})
    mapped = [c for c in cells if c.mapped_from]
    disagree = [c for c in cells if not c.agrees]
    out = [
        "# Rules v2 golden cases: independent check (Task G4)",
        "",
        f"The answers were worked out by {CHECKER} The sheet (G4_rules_v2_sheet.md) showed the "
        "inputs, the facts the rules read and the rule text with every team decision "
        "(D-RULE-2 to D-RULE-4, D-RULE-7); no titles, worked steps or expected values.",
        "",
        f"- Cases: {len(rules_cases)} rules cases and {len(e2e_cases)} end-to-end cases "
        f"({', '.join(e2e_cases)}); cells compared: {len(cells)}; agree: "
        f"{len(cells) - len(disagree)}; disagree: {len(disagree)}.",
        f"- {len(mapped)} status cells were UNDECIDABLE because the sheet named no statuses (a "
        "sheet gap): the checker's descriptions, mapped through the status table of "
        "INSTRUCTIONS.md section 5, agree with the drafts and are counted as agreeing. Future "
        "G sheets include the status table.",
        "- Case R14-05: the checker denies both lines by R12 (2 units of 64483 on one date, MUE "
        "1) with no DN_MULTIPLE_BLOCKS, as the draft does (A-R4); the case stays, showing R14 adds "
        "nothing for the same code on two lines.",
        "- Case R18-03: the checker read each 64484 unit as one level and noted the rule text "
        'said only "levels"; D-RULE-3 and INSTRUCTIONS.md section 8.3 now say each unit of an '
        "add-on level code is one level.",
        "",
        "## Status cells mapped through section 5",
        "",
        "| Case | Cell | Checker's description | Mapped | Draft |",
        "|---|---|---|---|---|",
        *(
            f"| {c.case} | {c.field} | {c.mapped_from.removeprefix('UNDECIDABLE: ')} | "
            f"{c.answer} | {c.expected} |"
            for c in mapped
        ),
        "",
        "## Not compared",
        "",
        *(f"- {line}" for line in not_compared),
        "",
        "## Disagreements",
        "",
    ]
    if disagree:
        out += ["| Case | Cell | Answer | Draft |", "|---|---|---|---|"]
        out += [f"| {c.case} | {c.field} | {c.answer} | {c.expected} |" for c in disagree]
    else:
        out.append("None: every compared cell agrees.")
    out += ["", "## Every compared cell", "", "| Case | Cell | Answer | Draft | Agree |"]
    out += ["|---|---|---|---|---|"]
    out += [
        f"| {c.case} | {c.field} | {c.answer or '-'} | {c.expected or '-'} | "
        f"{'yes' if c.agrees else 'NO'} |"
        for c in cells
    ]
    return "\n".join(out) + "\n"


# --- Promote (only when every compared cell agrees) ---------------------------------------------


def promote() -> list[str]:
    """The drafted rules cases into their golden files (appended), the end-to-end changes into
    cases.json (E2E-17 and E2E-23 replaced, E2E-32 added after E2E-31), and the answered sheet
    and the summary into data/verification/reviews/."""
    done = []
    for name, cases in json.loads(RULES_FILE.read_text()).items():
        path = GOLDEN_RULES / name
        data = json.loads(path.read_text()) if path.exists() else {"cases": []}
        known = {c["case_id"] for c in data["cases"]}
        if known & {c["case_id"] for c in cases}:
            raise SystemExit(f"{name} already holds some of {[c['case_id'] for c in cases]}")
        data["cases"] += cases
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        done.append(f"{name}: +{len(cases)}")
    e2e = json.loads(E2E_FILE.read_text())
    data = json.loads(GOLDEN_E2E.read_text())
    data["cases"] = [e2e.get(c["case_id"], c) for c in data["cases"]]
    if "E2E-32" in {c["case_id"] for c in data["cases"]}:
        raise SystemExit("cases.json already holds E2E-32")
    data["cases"].append(e2e["E2E-32"])
    GOLDEN_E2E.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    done.append("e2e/cases.json: E2E-17 and E2E-23 replaced, E2E-32 added")
    check_descriptors([ANSWERS_FILE, SUMMARY_FILE])
    for source in (ANSWERS_FILE, SUMMARY_FILE):
        shutil.copyfile(source, COPIES_DIR / source.name)
        done.append(f"copied {source.name} to {COPIES_DIR.relative_to(ROOT)}")
    return done


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("step", choices=("compare", "promote"))
    step = parser.parse_args().step
    cells, not_compared = compare()
    SUMMARY_FILE.write_text(summarize(cells, not_compared), encoding="utf-8")
    disagree = [c for c in cells if not c.agrees]
    print(
        f"{len(cells)} cells compared, {len(cells) - len(disagree)} agree, "
        f"{len(disagree)} disagree; {sum(bool(c.mapped_from) for c in cells)} status cells mapped "
        f"through section 5; {len(not_compared)} not compared; wrote {SUMMARY_FILE.name}"
    )
    for c in disagree:
        print(f"  DISAGREE {c.case} {c.field}: answer {c.answer!r}, draft {c.expected!r}")
    if step == "promote":
        if disagree:
            raise SystemExit("not promoted: some cells disagree")
        for line in promote():
            print(f"  {line}")


if __name__ == "__main__":
    main()
