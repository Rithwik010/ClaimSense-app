"""Policies v2, checkpoint 1: merging the pass 1 verdicts into the review sheet
(scripts/verify/policies_v2_review.py). Runs in CI on small made-up sheets."""

from scripts.verify.policies_v2_review import PROVENANCE, Verdict, merge, read_verdicts
from scripts.verify.policies_v2_sources import VERDICT_HEADER, has_verdicts

SHEET = f"""## Part B: kept criteria (1 rows)

| Row | Criterion | Text | Type | Applies to | Group |
|---|---|---|---|---|---|
| B1 | POL-TST-001.c1 | Kept text. | requirement | all | - |

## Verdicts

### Part A (MATCHES, DIFFERENT MEANING, NOT IN SOURCE or UNSURE)

{VERDICT_HEADER}
|---|---|---|---|---|---|
| A1 | POL-TST-001.c3 |  |  |  |  |

### Part B (AGREE, DISAGREE or UNSURE)

{VERDICT_HEADER}
|---|---|---|---|---|---|
| B1 | POL-TST-001.c1 |  |  |  |  |
"""
ANSWERS = {
    "A1": Verdict("A1", "POL-TST-001.c3", "DIFFERENT MEANING", "Drops a word."),
    "B1": Verdict("B1", "POL-TST-001.c1", "AGREE", "Fits."),
}


def test_merge_fills_only_the_pass_1_columns_of_the_verdict_tables() -> None:
    merged, problems = merge(SHEET, ANSWERS)

    assert problems == []
    assert "| B1 | POL-TST-001.c1 | Kept text. | requirement | all | - |" in merged  # Part B
    assert "| A1 | POL-TST-001.c3 | DIFFERENT MEANING | Drops a word. |  |  |" in merged
    assert "| B1 | POL-TST-001.c1 | AGREE | Fits. |  |  |" in merged
    assert PROVENANCE in merged
    assert merge(merged, ANSWERS) == (merged, [])  # merging again changes nothing
    assert not has_verdicts(SHEET) and has_verdicts(merged)


def test_a_mismatched_criterion_or_an_unknown_verdict_is_not_merged() -> None:
    wrong = {
        **ANSWERS,
        "A1": Verdict("A1", "POL-TST-001.c4", "MATCHES", ""),
        "B1": Verdict("B1", "POL-TST-001.c1", "MATCHES", ""),
    }

    assert merge(SHEET, wrong)[1] == [
        "A1: answer names POL-TST-001.c4, the sheet POL-TST-001.c3",
        "B1: verdict 'MATCHES' is not one of ('AGREE', 'DISAGREE', 'UNSURE')",
    ]


def test_a_different_pass_1_verdict_already_on_the_sheet_is_never_overwritten() -> None:
    merged, _ = merge(SHEET, ANSWERS)
    changed = {**ANSWERS, "B1": Verdict("B1", "POL-TST-001.c1", "DISAGREE", "Wrong type.")}

    assert merge(merged, changed)[1] == ["B1: the sheet already holds a different pass 1 verdict"]


def test_answers_are_read_by_row_and_a_repeated_row_stops_the_merge() -> None:
    table = "| A1 | POL-TST-001.c3 | MATCHES | Same. |  |  |\n"

    assert read_verdicts(table) == {"A1": Verdict("A1", "POL-TST-001.c3", "MATCHES", "Same.")}
    try:
        read_verdicts(table * 2)
    except SystemExit as stop:
        assert "row A1 answered twice" in str(stop)
    else:
        raise AssertionError("a repeated row must stop the merge")
