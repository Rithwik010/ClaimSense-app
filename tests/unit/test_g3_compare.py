"""G3-compare: the independent answers for C53-C56 (scripts/verify/g3_compare.py). They agree with
the golden cases on all 48 amounts, the tracked filled sheet holds exactly those answers, and a
different amount is reported as a mismatch."""

import copy

from scripts.verify.g3_compare import (
    ANSWERS,
    GOLDEN_FILES,
    answer_rows,
    blank_cells,
    blanked,
    compare,
    expected_cases,
    plan_and_cases,
)
from scripts.verify.golden_compare import AMOUNT_COLUMNS
from scripts.verify.review_verdicts import COPIES_DIR

SHEET = COPIES_DIR / "G3_new_cases_sheet.md"


def _rows() -> dict:
    return {
        (case_id, line_no): dict(zip(AMOUNT_COLUMNS, values, strict=True))
        for case_id, lines in ANSWERS.items()
        for line_no, values in lines.items()
    }


def test_the_answers_cover_the_four_cases_line_by_line() -> None:
    plan, cases = plan_and_cases()

    assert set(ANSWERS) == set(GOLDEN_FILES) == {"C53", "C54", "C55", "C56"}
    assert len(plan) == 8 and sorted(set(cases.values())) == sorted(ANSWERS)
    assert sum(len(values) for values in plan.values()) == 48


def test_the_recorded_answers_equal_the_golden_cases() -> None:
    compared, mismatches = compare(expected_cases(), _rows())

    assert (compared, mismatches) == (48, [])


def test_the_tracked_sheet_holds_exactly_the_recorded_answers() -> None:
    lines = SHEET.read_text(encoding="utf-8").splitlines()

    rows = answer_rows(lines)

    assert blank_cells(rows) == []
    assert {key: tuple(row[c] for c in AMOUNT_COLUMNS) for key, row in rows.items()} == {
        key: tuple(row.values()) for key, row in _rows().items()
    }
    assert blank_cells(answer_rows(blanked(lines))) == [
        f"{case_id} line {line_no} {column}: ''"
        for (case_id, line_no) in rows
        for column in AMOUNT_COLUMNS
    ]


def test_a_different_amount_is_a_mismatch() -> None:
    rows = copy.deepcopy(_rows())
    rows[("C55", 2)]["Member pays"] = "16951"

    compared, mismatches = compare(expected_cases(), rows)

    assert compared == 48
    assert mismatches == [("C55", 2, "Member pays", "16951", 1695)]
