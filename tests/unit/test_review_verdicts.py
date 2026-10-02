"""Task V1d: verdicts go into empty verdict cells only, conflicts keep the file's value, and the
tally reads the filled sheets. In-memory sheets only; no data/generated/ needed."""

import pytest

from scripts.verify.review_verdicts import (
    REVIEWS,
    BlockVerdicts,
    TableVerdicts,
    fill_blocks,
    fill_table,
    read_blocks,
    read_tables,
)

SHEET = [
    "# Title",
    "",
    "| Kind | Count |",
    "|---|---|",
    "| 1 | 2 |",
    "",
    "## Sample",
    "",
    "| # | Record ID | Text a \\| b | My status | Who is right? | Notes | Gold status |",
    "|---|---|---|---|---|---|---|",
    "| 1 | DEC-1, line 1 | x \\| y |  |  |  | MET |",
    "| 2 | DEC-2, line 1 | z | NOT_MET |  |  | NOT_MET |",
]
COLUMNS = ("My status", "Who is right?", "Notes")


def test_only_the_named_empty_cells_are_written() -> None:
    verdicts = TableVerdicts(COLUMNS, {1: ("MET", "LABEL RIGHT", "fits"), 2: ("NOT_MET", "", "")})

    lines, conflicts, written = fill_table(SHEET, verdicts)

    assert lines[10] == "| 1 | DEC-1, line 1 | x \\| y | MET | LABEL RIGHT | fits | MET |"
    assert lines[11] == SHEET[11]  # already holds the same status; empty values are skipped
    assert lines[:10] == SHEET[:10]  # other tables (no "#" column) are untouched
    assert conflicts == [] and written == 3


def test_a_different_value_keeps_the_files_version_and_is_reported() -> None:
    verdicts = TableVerdicts(COLUMNS, {2: ("MET", "MODEL RIGHT", "")})

    lines, conflicts, written = fill_table(SHEET, verdicts)

    assert lines[11] == "| 2 | DEC-2, line 1 | z | NOT_MET | MODEL RIGHT |  | NOT_MET |"
    assert conflicts == [("row 2", "My status", "NOT_MET", "MET")] and written == 1


def test_filling_twice_changes_nothing_and_a_missing_row_stops() -> None:
    verdicts = TableVerdicts(COLUMNS, {1: ("MET", "LABEL RIGHT", "fits")})
    once, _, _ = fill_table(SHEET, verdicts)

    twice, conflicts, written = fill_table(once, verdicts)

    assert twice == once and conflicts == [] and written == 0
    with pytest.raises(ValueError, match="row 9"):
        fill_table(SHEET, TableVerdicts(COLUMNS, {9: ("MET", "", "")}))


BLOCKS = [
    "### 1. POL-X.F1: WRONG CRITERION (impact 5 lines)",
    "",
    "Your verdict (ADD IN V2, NOT NEEDED or UNSURE):",
    "",
    "Notes:",
    "",
    "### 2. Control: L1-cov-001 (POL-X)",
    "",
    "Your verdict (ADD IN V2, NOT NEEDED or UNSURE): NOT NEEDED",
    "",
    "Notes:",
]


def test_block_entries_get_their_verdict_and_notes_lines() -> None:
    verdicts = BlockVerdicts({1: ("ADD IN V2", "0 lines"), 2: ("ADD IN V2", "control OK")})

    lines, conflicts, written = fill_blocks(BLOCKS, verdicts)

    assert lines[2] == "Your verdict (ADD IN V2, NOT NEEDED or UNSURE): ADD IN V2"
    assert lines[4] == "Notes: 0 lines"
    assert lines[8] == BLOCKS[8]  # the file already says NOT NEEDED: kept
    assert lines[10] == "Notes: control OK"
    assert conflicts == [("entry 2", "Your verdict", "NOT NEEDED", "ADD IN V2")]
    assert written == 3
    with pytest.raises(ValueError, match="entry 3"):
        fill_blocks(BLOCKS, BlockVerdicts({3: ("NOT NEEDED", "")}))


def test_the_filled_sheets_read_back_with_their_headings() -> None:
    filled, _, _ = fill_table(SHEET, TableVerdicts(COLUMNS, {1: ("MET", "LABEL RIGHT", "a")}))
    blocks, _, _ = fill_blocks(BLOCKS, BlockVerdicts({1: ("ADD IN V2", "b")}))

    tables = read_tables(filled)
    entries = read_blocks(blocks)

    assert [(heading, len(rows)) for heading, rows in tables] == [("Sample", 2)]
    assert tables[0][1][0]["Who is right?"] == "LABEL RIGHT"
    assert tables[0][1][0]["Text a \\| b"] == "x \\| y"
    assert [(e.number, e.title, e.verdict, e.notes) for e in entries] == [
        (1, "POL-X.F1: WRONG CRITERION (impact 5 lines)", "ADD IN V2", "b"),
        (2, "Control: L1-cov-001 (POL-X)", "NOT NEEDED", ""),
    ]


def test_the_recorded_verdicts_use_each_sheets_words_and_cover_every_row() -> None:
    sizes = {}
    for review in REVIEWS:
        for verdicts in (review.table, review.blocks):
            if verdicts is None:
                continue
            values = list(verdicts.rows.values())
            sizes[(review.file, type(verdicts).__name__)] = len(values)
            for row in values:
                for allowed, value in zip(verdicts.allowed, row, strict=True):
                    assert value and (not allowed or value in allowed), (review.file, value)
                assert "|" not in "".join(row) and "\n" not in "".join(row)
    assert sizes == {
        ("A_labels_review.md", "TableVerdicts"): 5,
        ("B_policy_sources_review.md", "TableVerdicts"): 14,
        ("B_policy_sources_review.md", "BlockVerdicts"): 12,
        ("C_disagreements_review.md", "TableVerdicts"): 12,
    }
