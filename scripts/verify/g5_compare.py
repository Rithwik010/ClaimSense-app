"""Task P2.3c checkpoint 3: compare the independent G5 answers with the drafted R11 modifier cases
and, only if every compared cell agrees, add them to the golden set (D-GOLD-2, D-GOLD-7, H12).

The answers (G5_r11_modifiers_answers.md, the sheet with its cells filled) were worked out by a
normal Claude chat with no repository access, which saw only the pasted sheet (2026-10-09). This is
a Claude recomputation, not a blind human check, and not independent of the cases' author (also
Claude); unlike G4 it is independent of the repository by construction. An UNDECIDABLE status cell
is mapped through the status table of INSTRUCTIONS.md section 5, as in G4.

    uv run python -m scripts.verify.g5_compare compare   # report; writes G5_summary.md
    uv run python -m scripts.verify.g5_compare promote   # only if all agree: the golden set
"""

import argparse
import json
import shutil
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from scripts.verify.g4_compare import (
    Cell,
    codes,
    first_word,
    sections,
    status_cell,
    table_rows,
    value_after,
)
from scripts.verify.new_modifier_cases import CASES_FILE, OUT_DIR, TARGET
from scripts.verify.review_verdicts import COPIES_DIR, check_descriptors

ROOT = Path(__file__).resolve().parents[2]
ANSWERS_FILE = OUT_DIR / "G5_r11_modifiers_answers.md"
SUMMARY_FILE = OUT_DIR / "G5_summary.md"
GOLDEN_R11 = ROOT / "tests" / "golden" / "rules" / TARGET
CHECKER = (
    "a normal Claude chat with no repository access, which saw only the pasted sheet. This is a "
    "Claude recomputation, not a blind human check, and not independent of the cases' author "
    "(also Claude); unlike G4 it is independent of the repository by construction."
)


def case_cells(case: Mapping[str, Any], lines: Sequence[str]) -> list[Cell]:
    case_id, expected = case["case_id"], case["expected"]
    cells = [
        Cell(
            case_id,
            "claim outcome",
            first_word(value_after(lines, "Claim outcome (PASS / DENY)"), ("PASS", "DENY")),
            expected["claim_outcome"],
        ),
        status_cell(case_id, "status", value_after(lines, "Status"), expected["status"]),
    ]
    rows = table_rows(lines, "| Line | Outcome")
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


def drafts() -> list[dict[str, Any]]:
    return json.loads(CASES_FILE.read_text(encoding="utf-8"))[TARGET]


def compare() -> list[Cell]:
    answers = sections(ANSWERS_FILE.read_text(encoding="utf-8"))
    cases = drafts()
    missing = [c["case_id"] for c in cases if c["case_id"] not in answers]
    if missing:
        raise SystemExit(f"no answers for {missing}")
    return [cell for c in cases for cell in case_cells(c, answers[c["case_id"]])]


def summarize(cells: Sequence[Cell]) -> str:
    cases = sorted({c.case for c in cells}, key=lambda k: int(k.split("-")[1]))
    mapped = [c for c in cells if c.mapped_from]
    disagree = [c for c in cells if not c.agrees]
    out = [
        "# R11 modifier golden cases: independent check (Task G5)",
        "",
        f"The answers were worked out by {CHECKER} The sheet (G5_r11_modifiers_sheet.md) showed "
        "the R11 rule text with the team's decisions (D-RULE-8), the status table, and for each "
        "case the lines, the NCCI edit and its indicator, which codes are E&M and each code's PFS "
        "global period; no titles, worked steps or expected values.",
        "",
        f"- Cases: {len(cases)} ({', '.join(cases)}); cells compared: {len(cells)}; agree: "
        f"{len(cells) - len(disagree)}; disagree: {len(disagree)}; status cells mapped through "
        f"section 5: {len(mapped)}.",
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


def promote() -> list[str]:
    """The drafted cases appended to R11_ncci.json, R11-06 reworded (title and worked steps; its
    expected values unchanged, D-GOLD-7), and the answered sheet and the summary copied to
    data/verification/reviews/."""
    staged = json.loads(CASES_FILE.read_text(encoding="utf-8"))
    data = json.loads(GOLDEN_R11.read_text(encoding="utf-8"))
    known = {c["case_id"] for c in data["cases"]}
    new = staged[TARGET]
    if known & {c["case_id"] for c in new}:
        raise SystemExit(f"{TARGET} already holds some of {[c['case_id'] for c in new]}")
    r11_06 = next(c for c in data["cases"] if c["case_id"] == "R11-06")
    before = r11_06["expected"]
    r11_06.update(staged["R11-06"])
    if r11_06["expected"] != before:
        raise SystemExit("R11-06's expected values would change")
    data["cases"] += new
    GOLDEN_R11.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    check_descriptors([ANSWERS_FILE, SUMMARY_FILE])
    done = [f"{TARGET}: +{len(new)}; R11-06 title and worked steps reworded"]
    for source in (ANSWERS_FILE, SUMMARY_FILE):
        shutil.copyfile(source, COPIES_DIR / source.name)
        done.append(f"copied {source.name} to {COPIES_DIR.relative_to(ROOT)}")
    return done


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("step", choices=("compare", "promote"))
    step = parser.parse_args().step
    cells = compare()
    SUMMARY_FILE.write_text(summarize(cells), encoding="utf-8")
    disagree = [c for c in cells if not c.agrees]
    undecided = [c for c in cells if c.mapped_from and not c.answer]
    print(
        f"{len(cells)} cells compared, {len(cells) - len(disagree)} agree, "
        f"{len(disagree)} disagree; {sum(bool(c.mapped_from) for c in cells)} status cells mapped "
        f"through section 5 ({len(undecided)} unmapped); wrote {SUMMARY_FILE.name}"
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
