"""Task G3-compare: write the independent answers for C53-C56 into the G3 sheet, compare them with
the drafted expected values exact to the cent and, only if every amount agrees, add the cases to
the golden set (D-GOLD-2, H12).

The answers below were computed by a separate Claude chat from G3_new_cases_sheet.md only, without
access to the repository, the staged cases or any expected amount (2026-10-04). They are entered
word for word, into empty cells only (golden_compare.fill_sheet).

    uv run python -m scripts.verify.g3_compare fill      # write the answers into the empty cells
    uv run python -m scripts.verify.g3_compare compare   # blank cells, then every amount (report)
    uv run python -m scripts.verify.g3_compare promote   # only if all agree: golden set, summary
"""

import argparse
import json
import shutil
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from scripts.verify.golden_checks import situations
from scripts.verify.golden_compare import (
    AMOUNT_COLUMNS,
    AMOUNT_FIELDS,
    PIPE,
    Key,
    fill_sheet,
    slots,
)
from scripts.verify.new_calculator_cases import (
    CASES_FILE,
    DRAFTS,
    OUT_DIR,
    SHEET_FILE,
    build_sheet,
)
from scripts.verify.review_verdicts import COPIES_DIR, check_descriptors

ROOT = Path(__file__).resolve().parents[2]
GOLDEN_CALCULATOR = ROOT / "tests" / "golden" / "calculator"
SUMMARY_FILE = OUT_DIR / "G3_summary.md"
PROVENANCE = (
    "The answers were computed by a separate Claude chat from G3_new_cases_sheet.md only, without "
    "access to the repository, the staged cases or any expected amount. This is a Claude "
    "recomputation, not a blind human check, and not independent of the cases' author (also "
    "Claude). The sheet showed the inputs and the quoted section 8.6 steps only: no titles, "
    "expected values, worked steps, situations or per-case assumption names; A1-A9 were listed "
    "once for every case."
)
# Per line: Allowed | Deductible applied | Copay | Coinsurance | Plan pays | Member pays.
ANSWERS: dict[str, dict[int, tuple[str, ...]]] = {
    "C53": {
        1: ("24591", "24591", "0", "0", "0", "24591"),
        2: ("39621", "5409", "0", "10264", "23948", "15673"),
    },
    "C54": {1: ("2800", "0", "2800", "0", "0", "2800")},
    "C55": {
        1: ("24591", "20000", "0", "459", "0", "0"),
        2: ("16951", "0", "0", "1695", "15256", "1695"),
    },
    "C56": {
        1: ("16951", "0", "4000", "0", "12951", "4000"),
        2: ("39621", "10000", "0", "1000", "28621", "11000"),
        3: ("7266", "0", "0", "0", "7266", "0"),
    },
}
# Where each accepted case goes in tests/golden/calculator/.
GOLDEN_FILES = {
    "C53": "multi_line.json",
    "C54": "copay.json",
    "C55": "coordination_of_benefits.json",
    "C56": "out_of_pocket_max.json",
}
A6_NOTE = (
    "C55 line 2 depends on assumption A6: line 1's deductible counts toward the accumulators "
    "although the primary paid more than line 1's allowed amount, so line 2 takes no deductible."
)
# Proposed causes of mismatches, keyed (case, line, column); filled after the comparison is read.
CAUSES: dict[tuple[str, int, str], str] = {}


def plan_and_cases() -> tuple[dict[Key, dict[str, str]], dict[Key, str]]:
    """The answers keyed like golden_compare's sheet slots: ("calculator", case number, line)."""
    order = [draft.case_id for draft in DRAFTS]
    plan: dict[Key, dict[str, str]] = {}
    cases: dict[Key, str] = {}
    for case_id, lines in ANSWERS.items():
        number = order.index(case_id) + 1
        for line_no, values in lines.items():
            key = ("calculator", number, line_no)
            plan[key] = dict(zip(AMOUNT_COLUMNS, values, strict=True))
            cases[key] = case_id
    return plan, cases


def blanked(lines: Sequence[str]) -> list[str]:
    """The sheet with every amount cell emptied, as it was given to the checker."""
    out = list(lines)
    for slot in slots(lines):
        if slot.key[0] != "calculator":
            continue
        parts = PIPE.split(lines[slot.index])
        for column in slot.answers:
            parts[slot.header.index(column) + 1] = "  "
        out[slot.index] = "|".join(parts)
    return out


def expected_cases() -> list[dict[str, Any]]:
    """The drafted cases: staged, or (after promotion) from the golden set."""
    if CASES_FILE.exists():
        return json.loads(CASES_FILE.read_text(encoding="utf-8"))["cases"]
    golden = {
        case["case_id"]: case
        for path in sorted(GOLDEN_CALCULATOR.glob("*.json"))
        for case in json.loads(path.read_text(encoding="utf-8"))["cases"]
    }
    return [golden[draft.case_id] for draft in DRAFTS]


def answer_rows(lines: Sequence[str]) -> dict[tuple[str, int], dict[str, str]]:
    rows = {}
    for slot in slots(lines):
        if slot.key[0] == "calculator":
            rows[(slot.case_id, slot.key[2])] = dict(zip(slot.header, slot.cells, strict=True))
    return rows


def blank_cells(rows: Mapping[tuple[str, int], Mapping[str, str]]) -> list[str]:
    return [
        f"{case_id} line {line_no} {column}: {row[column]!r}"
        for (case_id, line_no), row in rows.items()
        for column in AMOUNT_COLUMNS
        if not row[column].isdigit()
    ]


def compare(
    cases: Sequence[Mapping[str, Any]], rows: Mapping[tuple[str, int], Mapping[str, str]]
) -> tuple[int, list[tuple[str, int, str, str, int]]]:
    """(amounts compared, mismatches as (case, line, column, answer, expected))."""
    compared, mismatches = 0, []
    for case in cases:
        for line in case["expected"]["amounts"]["lines"]:
            row = rows[(case["case_id"], line["line_no"])]
            for column, field in AMOUNT_FIELDS.items():
                compared += 1
                if row[column] != str(line[field]):
                    mismatches.append(
                        (case["case_id"], line["line_no"], column, row[column], line[field])
                    )
    if len(rows) != sum(len(c["expected"]["amounts"]["lines"]) for c in cases):
        raise SystemExit("the sheet and the cases have different lines")
    return compared, mismatches


def mismatch_report(
    cases: Sequence[Mapping[str, Any]], mismatches: Sequence[tuple[str, int, str, str, int]]
) -> str:
    by_id = {case["case_id"]: case for case in cases}
    out = []
    for case_id, line_no, column, answer, expected in mismatches:
        cause = CAUSES.get((case_id, line_no, column), "not yet proposed")
        out.append(f"- {case_id} line {line_no} {column}: answer {answer}, expected {expected}")
        out.append(f"  proposed cause: {cause}")
    for case_id in dict.fromkeys(m[0] for m in mismatches):
        out.append(f"\nWorked steps, {case_id}:")
        out += [f"    {step}" for step in by_id[case_id]["worked_steps"]]
    return "\n".join(out)


def _golden_cases() -> list[dict[str, Any]]:
    return [
        case
        for path in sorted(GOLDEN_CALCULATOR.glob("*.json"))
        for case in json.loads(path.read_text(encoding="utf-8"))["cases"]
    ]


def coverage(cases: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    """How many golden calculator cases exercise each cost-share situation (golden_checks)."""
    from app.db.curated import load_curated
    from scripts.verify.golden_checks import EXTRA_SITUATIONS, SITUATIONS

    curated = load_curated()
    counts = dict.fromkeys((*SITUATIONS, *EXTRA_SITUATIONS), 0)
    for case in cases:
        plan = curated.plans[case["given"]["plan_id"]]

        def benefit(category: str, plan_id: str = plan.plan_id) -> tuple[str, int | None]:
            b = curated.benefit(plan_id, category)
            return b.cost_share_rule, b.copay_cents

        for name in situations(case, plan, benefit):
            counts[name] = counts.get(name, 0) + 1
    return counts


def summarize(
    cases: Sequence[Mapping[str, Any]],
    rows: Mapping[tuple[str, int], Mapping[str, str]],
    compared: int,
    before: Mapping[str, int],
    after: Mapping[str, int],
    total_before: int,
    total_after: int,
) -> str:
    def amounts(values: Sequence[Any]) -> str:
        return " / ".join(str(v) for v in values)

    lines = [
        "# New calculator golden cases: independent check (Task G3)",
        "",
        PROVENANCE,
        "",
        f"- Cases: {', '.join(c['case_id'] for c in cases)} "
        f"({sum(len(c['expected']['amounts']['lines']) for c in cases)} lines); amounts "
        f"compared: {compared}; agree: {compared}; mismatches: 0.",
        "- Added to tests/golden/calculator/: "
        + ", ".join(f"{case_id} ({name})" for case_id, name in GOLDEN_FILES.items())
        + f"; golden calculator cases {total_before} -> {total_after}.",
        f"- {A6_NOTE}",
        "",
        "## Comparison (allowed / deductible / copay / coinsurance / plan pays / member pays)",
        "",
        "| Case | Line | Answer | Expected | Agree |",
        "|---|---|---|---|---|",
    ]
    for case in cases:
        for line in case["expected"]["amounts"]["lines"]:
            row = rows[(case["case_id"], line["line_no"])]
            answer = [row[column] for column in AMOUNT_COLUMNS]
            expected = [line[field] for field in AMOUNT_FIELDS.values()]
            same = answer == [str(v) for v in expected]
            lines.append(
                f"| {case['case_id']} | {line['line_no']} | {amounts(answer)} | "
                f"{amounts(expected)} | {'yes' if same else 'NO'} |"
            )
    lines += [
        "",
        "## Mismatches",
        "",
        "None: every answer agrees with the expected value.",
        "",
        "## Coverage: cost-share situations (calculator)",
        "",
        f"| Situation | Golden cases before ({total_before}) | After ({total_after}) |",
        "|---|---|---|",
        *[
            f"| {name} | {before[name] or '**none**'} | {after[name] or '**none**'} |"
            for name in after
        ],
        "",
    ]
    return "\n".join(lines)


def promote(cases: Sequence[Mapping[str, Any]]) -> None:
    """Append the accepted cases to their golden files (same formatting) and remove the staged
    file."""
    present = {case["case_id"] for case in _golden_cases()}
    if present & set(GOLDEN_FILES):
        raise SystemExit(f"already in the golden set: {sorted(present & set(GOLDEN_FILES))}")
    for case in cases:
        path = GOLDEN_CALCULATOR / GOLDEN_FILES[case["case_id"]]
        data = json.loads(path.read_text(encoding="utf-8"))
        data["cases"].append(case)
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    CASES_FILE.unlink()


def main() -> None:
    from app.db.curated import load_curated

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("step", choices=("fill", "compare", "promote"))
    step = parser.parse_args().step
    lines = SHEET_FILE.read_text(encoding="utf-8").splitlines()
    cases = expected_cases()
    given_sheet = build_sheet(cases, load_curated()).splitlines()
    if blanked(lines) != given_sheet:
        raise SystemExit(f"{SHEET_FILE.name} differs from the sheet built from the drafted cases")
    if step == "fill":
        plan, case_ids = plan_and_cases()
        filled, conflicts, written = fill_sheet(lines, plan, case_ids)
        if filled != lines:
            SHEET_FILE.write_text("\n".join(filled) + "\n", encoding="utf-8")
        print(f"{written} cells written; conflicts (file's value kept): {conflicts or 'none'}")
        return
    rows = answer_rows(lines)
    blanks = blank_cells(rows)
    if blanks:
        raise SystemExit("blank or unreadable cells:\n" + "\n".join(blanks))
    compared, mismatches = compare(cases, rows)
    print(f"amounts compared: {compared}; agree: {compared - len(mismatches)}")
    if mismatches:
        print(mismatch_report(cases, mismatches))
        raise SystemExit(1)
    if step == "compare":
        return
    before_cases = _golden_cases()
    promote(cases)
    after_cases = _golden_cases()
    SUMMARY_FILE.write_text(
        summarize(
            cases,
            rows,
            compared,
            coverage(before_cases),
            coverage(after_cases),
            len(before_cases),
            len(after_cases),
        ),
        encoding="utf-8",
    )
    paths = [SHEET_FILE, SUMMARY_FILE]
    checked = check_descriptors(paths)
    COPIES_DIR.mkdir(parents=True, exist_ok=True)
    for path in paths:
        shutil.copyfile(path, COPIES_DIR / path.name)
    print(
        f"added {len(cases)} cases to tests/golden/calculator/ ({len(before_cases)} -> "
        f"{len(after_cases)}); no AMA CPT descriptor text ({checked} checked); copied "
        f"{len(paths)} files to {COPIES_DIR.relative_to(ROOT)}"
    )


if __name__ == "__main__":
    main()
