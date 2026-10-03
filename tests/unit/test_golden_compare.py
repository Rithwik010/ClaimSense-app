"""Task G2: the spot-check answers go into empty answer cells only, blank cells are found, and the
answers are compared with the expected values exactly. In-memory sheets; no data/generated/."""

import pytest

from scripts.verify.golden_compare import (
    AMOUNT_COLUMNS,
    ASSUMPTIONS,
    CALCULATOR_ANSWERS,
    H5_VERDICTS,
    NOT_INDEPENDENT,
    RULES_ANSWERS,
    VERDICT,
    Outcome,
    check_cells,
    compare_amounts,
    expected_outcome,
    fill_sheet,
    parse_outcome,
    recorded_plan,
    slots,
)

SHEET = [
    "# Golden test spot-check (Task G1)",
    "",
    "## Golden assumptions (tests/golden/README.md, word for word)",
    "",
    "| ID | Assumption | ACCEPT / CHANGE | Notes |",
    "|---|---|---|---|",
    "| A1 | Fee per unit. |  |  |",
    "| A2 | Copay per line \\| even two lines. |  |  |",
    "",
    "## H5 field mapping used by the automatic checks",
    "",
    "| Rule | Fields used | Section 8.3 text it was read from | ACCEPT / CHANGE | Notes |",
    "|---|---|---|---|---|",
    "| R07 | received_date | Timely filing |  |  |",
    "",
    "## Rules cases (1, seed 42)",
    "",
    "### Rules case 1 (H5-02)",
    "",
    "| ID | Rule | Failure outcome | Internal reason code |",
    "|---|---|---|---|",
    "| R10 | Prior authorization | DENY | `DN_NO_AUTH` |",
    "",
    "| My outcome (REJECT / DENY / PEND / PASS and reason code; line outcomes if any) | Notes |",
    "|---|---|",
    "|  |  |",
    "",
    "## Calculator cases (1, seed 42: one per situation)",
    "",
    "### Calculator case 1 (C26)",
    "",
    "| Line | Code | Units | Billed (cents) | Decision | Benefit category |",
    "|---|---|---|---|---|---|",
    "| 1 | 99213 | 1 | 19000 | APPROVE | OFFICE_VISIT_PCP |",
    "| 2 | 99214 | 1 | 27000 | DENY | - |",
    "",
    "| Line | Allowed | Deductible applied | Copay | Coinsurance | Plan pays | Member pays |",
    "|---|---|---|---|---|---|---|",
    "| 1 |  |  |  |  |  |  |",
    "| 2 |  |  |  |  |  |  |",
    "",
    "Notes:",
]
AMOUNTS = dict(zip(AMOUNT_COLUMNS, ("11899", "0", "2500", "0", "9399", "2500"), strict=True))
PLAN = {
    ("assumption", "A2"): {VERDICT: "ACCEPT", "Notes": "matches 8.6"},
    ("h5", "R07"): {VERDICT: "CHANGE", "Notes": "add member_id"},
    ("rules", 1): {"My outcome": "REJECT RJ_LOW_CONFIDENCE_FIELD", "Notes": "H5"},
    ("calculator", 1, 1): AMOUNTS,
    ("notes", 1): {"Notes": "line 1: copay"},
}
CASES = {("rules", 1): "H5-02", ("calculator", 1, 1): "C26", ("notes", 1): "C26"}


def test_slots_are_the_answer_rows_only() -> None:
    found = slots(SHEET)

    assert [s.key for s in found] == [
        ("assumption", "A1"),
        ("assumption", "A2"),
        ("h5", "R07"),
        ("rules", 1),
        ("calculator", 1, 1),
        ("calculator", 1, 2),
        ("notes", 1),
    ]
    assert {s.key: s.case_id for s in found}[("rules", 1)] == "H5-02"
    assert {s.key: s.case_id for s in found}[("calculator", 1, 2)] == "C26"


def test_only_the_named_empty_cells_are_written() -> None:
    lines, conflicts, written = fill_sheet(SHEET, PLAN, CASES)

    assert conflicts == [] and written == 2 + 2 + 2 + 6 + 1
    assert lines[7] == "| A2 | Copay per line \\| even two lines. | ACCEPT | matches 8.6 |"
    assert lines[13] == "| R07 | received_date | Timely filing | CHANGE | add member_id |"
    assert lines[25] == "| REJECT RJ_LOW_CONFIDENCE_FIELD | H5 |"
    assert lines[38] == "| 1 | 11899 | 0 | 2500 | 0 | 9399 | 2500 |"
    assert lines[41] == "Notes: line 1: copay"
    changed = {i for i, (a, b) in enumerate(zip(SHEET, lines, strict=True)) if a != b}
    assert changed == {7, 13, 25, 38, 41}  # nothing outside the answer cells


def test_a_different_value_keeps_the_files_version_and_filling_twice_changes_nothing() -> None:
    sheet = list(SHEET)
    sheet[13] = "| R07 | received_date | Timely filing | ACCEPT |  |"

    lines, conflicts, written = fill_sheet(sheet, PLAN, CASES)

    assert lines[13] == "| R07 | received_date | Timely filing | ACCEPT | add member_id |"
    assert conflicts == [("H5 R07", VERDICT, "ACCEPT", "CHANGE")]
    again, conflicts_again, written_again = fill_sheet(lines, PLAN, CASES)
    assert again == lines and written_again == 0 and conflicts_again == conflicts


def test_a_wrong_case_or_a_missing_row_stops() -> None:
    with pytest.raises(ValueError, match="DUP-01"):
        fill_sheet(SHEET, PLAN, {**CASES, ("rules", 1): "DUP-01"})
    with pytest.raises(ValueError, match="not in the sheet"):
        fill_sheet(SHEET, {**PLAN, ("calculator", 1, 3): AMOUNTS}, CASES)
    with pytest.raises(ValueError, match="pipe or line break"):
        fill_sheet(SHEET, {("h5", "R07"): {VERDICT: "CHANGE", "Notes": "a | b"}}, {})


def test_check_cells_lists_blank_and_unreadable_cells_but_not_notes() -> None:
    lines, _, _ = fill_sheet(SHEET, PLAN, CASES)
    lines[38] = "| 1 | 11899 | 0 | 2500 | 0 | 9399.5 | 2500 |"
    lines[13] = "| R07 | received_date | Timely filing | MAYBE | add member_id |"

    problems = check_cells(slots(lines))

    assert problems == [
        "Assumption A1: ACCEPT / CHANGE is blank",
        "H5 R07: ACCEPT / CHANGE is MAYBE, not ACCEPT or CHANGE",
        "Calculator 1 (C26) line 1: Plan pays is 9399.5, not whole cents",
        "Calculator 1 (C26) line 2: Allowed is blank",
        "Calculator 1 (C26) line 2: Deductible applied is blank",
        "Calculator 1 (C26) line 2: Copay is blank",
        "Calculator 1 (C26) line 2: Coinsurance is blank",
        "Calculator 1 (C26) line 2: Plan pays is blank",
        "Calculator 1 (C26) line 2: Member pays is blank",
    ]


CODES = {"RJ_LOW_CONFIDENCE_FIELD", "DN_NOT_ELIGIBLE", "PD_PROVIDER_ENROLLMENT", "DN_NO_AUTH"}


def test_outcomes_are_read_from_free_text() -> None:
    text = "DENY DN_NOT_ELIGIBLE (R06 PEND PD_PROVIDER_ENROLLMENT also recorded)"
    assert parse_outcome(text, CODES) == Outcome(
        "DENY", frozenset({"DN_NOT_ELIGIBLE", "PD_PROVIDER_ENROLLMENT"}), frozenset()
    )
    assert parse_outcome("PASS; line 2 flag NCCI_BYPASS", CODES) == Outcome(
        "PASS", frozenset(), frozenset({"NCCI_BYPASS"})
    )
    expected = expected_outcome(
        {
            "claim_outcome": "PASS",
            "failures": "",
            "line_outcomes": "line 1 PASS ; line 2 PASS  flags NCCI_BYPASS",
            "flags": "",
        },
        CODES,
    )
    assert expected == Outcome("PASS", frozenset(), frozenset({"NCCI_BYPASS"}))


def test_amounts_must_agree_to_the_cent() -> None:
    expected = {"allowed_cents": "11899", "deductible_cents": "0", "copay_cents": "2500"}
    expected |= {"coinsurance_cents": "0", "plan_pays_cents": "9399", "member_pays_cents": "2500"}

    assert compare_amounts(AMOUNTS, expected) == []
    assert compare_amounts({**AMOUNTS, "Plan pays": "9400"}, expected) == [
        ("Plan pays", "9400", "9399")
    ]


def test_the_recorded_answers_cover_the_sample_and_use_the_sheets_words() -> None:
    plan, cases = recorded_plan()

    assert [c for c, _, _ in RULES_ANSWERS.values()] == [
        "H5-02",
        "DUP-01",
        "R11-09",
        "R03-04",
        "R02-01",
        "R09-01",
        "P-01",
        "R01-02",
        "R04-01",
        "R06-04",
    ]
    assert [(n, line, c) for (n, line), (c, _, _) in CALCULATOR_ANSWERS.items()] == [
        (1, 1, "C04"),
        (2, 1, "C10"),
        (3, 1, "C49"),
        (4, 1, "C30"),
        (5, 1, "C19"),
        (6, 1, "C21"),
        (7, 1, "C31"),
        (8, 1, "C41"),
        (9, 1, "C26"),
        (9, 2, "C26"),
        (9, 3, "C26"),
    ]
    assert len(ASSUMPTIONS) == 20 and len(H5_VERDICTS) == 14
    assert {v for v, _ in [*ASSUMPTIONS.values(), *H5_VERDICTS.values()]} == {"ACCEPT", "CHANGE"}
    assert set(NOT_INDEPENDENT) == {"P-01"}
    assert "Not independent" in RULES_ANSWERS[7][2]
    for values in plan.values():
        assert not any("|" in v or "\n" in v for v in values.values())
    assert plan[("notes", 9)]["Notes"].startswith("line 1: copay; does not touch the deductible")
    assert cases[("notes", 9)] == "C26"


def test_the_reviewed_h5_mapping_adds_fields_and_keeps_the_rest() -> None:
    from scripts.verify.golden_compare import REVIEWED_H5_FIELDS, reviewed_mapping

    base = {"R07": ("received_date",), "R09": ("referring_npi",), "R12": ("units",)}

    assert reviewed_mapping(base, REVIEWED_H5_FIELDS) == {
        "R07": ("received_date", "member_id"),
        "R09": ("referring_npi", "member_id"),
        "R12": ("units",),
    }
