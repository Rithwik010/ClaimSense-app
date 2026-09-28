"""Task V1b policy source and completeness checks: made-up and changed sources are flagged, LCD
text is extracted and mapped deterministically. In-memory LCDs only; no data/raw/ needed."""

import csv
from pathlib import Path

import pytest

from scripts.verify.policy_sources import (
    ASSOCIATED_FIELD,
    COVERAGE_FIELD,
    JOIN,
    NOT_FOUND,
    SOURCES_CSV,
    Criterion,
    Item,
    Judgment,
    JudgmentsExist,
    Lcd,
    SourceRow,
    best_similarity,
    blocks,
    check_source,
    conditions,
    differing_values,
    items_of,
    load_criteria,
    mapped_criteria,
    planted_cases,
    planted_lcd,
    redact,
    resolve,
    round_robin,
    rule_classification,
    run_planted,
    save_judgments,
    self_test,
    values,
)


@pytest.mark.parametrize("case", planted_cases(), ids=lambda case: case.name)
def test_every_planted_case_behaves_as_expected(case) -> None:  # noqa: ANN001
    flags = run_planted(case)
    if case.expect_flag:
        assert any(case.expect_flag in f for f in flags), flags
    else:
        assert flags == []


def test_a_made_up_source_sentence_is_flagged() -> None:
    """The task's required test: a sentence that is not in the LCD scores below 0.9."""
    lcd = planted_lcd()
    texts = {f: lcd.text(f) for f in lcd.fields}
    made_up = "Injections are covered only after twelve months of daily acupuncture."
    criterion = Criterion("P.c1", "POL-P", "Injections need acupuncture first.", "", "L00001")

    result = check_source(
        criterion, SourceRow("P.c1", lcd.source_file(COVERAGE_FIELD), made_up), texts
    )

    assert result.similarity is not None and result.similarity < 0.9
    assert any(f.startswith("similarity") for f in result.flags)


def test_the_runtime_self_test_passes() -> None:
    text, ok = self_test()
    assert ok, text


def test_values_normalize_numbers_units_and_qualifiers() -> None:
    assert (
        values("at least four (4) weeks") == values("a minimum of 4 weeks") == {"at least 4 week"}
    )
    assert values("over 15 years") == values("more than 15 years")
    assert values("at 24-month intervals") == values("every 24 months")
    assert values("limited to one level") == values("a maximum of one level")
    assert values("50% improvement") == values("fifty percent improvement")


def test_differing_values_and_conditions() -> None:
    assert differing_values("at least 3 months", "a minimum of 3 months") == []
    assert differing_values("at least 3 months", "at least 6 months") == [
        "criterion: at least 3 month",
        "source: at least 6 month",
    ]
    assert conditions("with contrastunless the patient") == {"unless"}  # glued in the LCD text
    assert conditions("covered only when") == set()  # "only" is not checked (all false alarms)
    assert "condition word in source only: except" in differing_values(
        "at least 2 weeks apart", "a minimum of 2 weeks, except in some cases"
    )


def test_exact_text_scores_one_and_whitespace_changes_do_not() -> None:
    text = "The pain must be severe. Imaging must confirm it."
    assert best_similarity("The pain must be severe.", text) == 1.0
    assert best_similarity("The pain must be  very severe.", text) < 1.0


def test_blocks_skip_background_connectors_and_footnotes() -> None:
    raw = (
        "<p><strong>History/Background and/or General Information</strong></p><p>Old text.</p>"
        "<p><strong>Covered Indications</strong></p><ul><li>First<sup>12</sup> item.</li>"
        "<li>OR</li><li>Second item.</li></ul><p>4,5</p>"
    )
    found = blocks(COVERAGE_FIELD, raw)

    texts = [b.text for b in found if not b.heading and not b.background]
    assert texts == ["First item.", "Second item."]
    assert [b.text for b in found if b.background and not b.heading] == ["Old text."]
    assert all(b.section == "Covered Indications" for b in found if b.text.endswith("item."))


def _lcd(raw: str, associated: str = "") -> Lcd:
    return Lcd("L00002", "3", {COVERAGE_FIELD: raw, ASSOCIATED_FIELD: associated})


RAW = (
    "<p><strong>Covered Indications</strong></p><ul><li>Palpitations</li><li>Chest pain</li>"
    "</ul><p><strong>Limitations</strong></p><p>One. Two. Three.</p><ul><li>Palpitations</li></ul>"
)


def test_resolve_joins_adjacent_spans_and_marks_gaps() -> None:
    lcd = _lcd(RAW, "<p>Doc sentence.</p>")

    source_file, text = resolve(lcd, [f"{COVERAGE_FIELD}:1:0", f"{COVERAGE_FIELD}:2:0"])
    assert text == "Palpitations Chest pain" and JOIN not in text  # adjacent list items
    assert source_file.endswith(":L00002v3:indication")

    _, text = resolve(lcd, [f"{COVERAGE_FIELD}:4:0", f"{COVERAGE_FIELD}:4:2"])
    assert text == f"One.{JOIN}Three."  # a gap inside the block

    source_file, _ = resolve(lcd, [f"{COVERAGE_FIELD}:4:0", f"{ASSOCIATED_FIELD}:0:0"])
    assert source_file.endswith(
        f"indication{JOIN}" + source_file.split(JOIN)[1]
    ) and source_file.endswith(":associated_info")


def test_items_map_by_position_not_by_wording() -> None:
    lcd = _lcd(RAW)
    items, _ = items_of("POL-P", lcd)
    texts = {f: lcd.text(f) for f in lcd.fields}
    criteria = {"POL-P.c1": Criterion("POL-P.c1", "POL-P", "Symptoms.", "", "L00002")}
    source_file, text = resolve(lcd, [f"{COVERAGE_FIELD}:1:0", f"{COVERAGE_FIELD}:2:0"])
    sources = {"POL-P.c1": SourceRow("POL-P.c1", source_file, text)}

    mapped = {i.item_id: mapped_criteria(i, sources, criteria, texts) for i in items}

    palpitations = [i for i in items if i.text == "Palpitations"]
    assert mapped[palpitations[0].item_id] == ["POL-P.c1"]
    assert mapped[palpitations[1].item_id] == []  # the same words under Limitations


def test_keyword_rules() -> None:
    def item(text: str) -> Item:
        return Item("x", "POL-P", "L0", COVERAGE_FIELD, "", text)

    assert rule_classification(item("Moderate sedation is rarely needed."))[0] == "out of scope"
    assert (
        rule_classification(item("No more than 4 sessions per year are covered."))[0]
        == "rule candidate"
    )
    assert rule_classification(item("Pain must be documented.")) is None


def test_round_robin_orders_by_impact_then_policy_turns() -> None:
    rows = [
        {"item_id": "a1", "policy_id": "A", "impact": 50},
        {"item_id": "a2", "policy_id": "A", "impact": 40},
        {"item_id": "b1", "policy_id": "B", "impact": 45},
        {"item_id": "c1", "policy_id": "C", "impact": 5},
    ]
    assert [r["item_id"] for r in round_robin(rows)] == ["a1", "b1", "c1", "a2"]


def test_descriptor_text_is_redacted() -> None:
    text, n = redact(
        "Uses COMPUTED TOMOGRAPHY, HEAD OR BRAIN here.", ["computed tomography, head or brain"]
    )
    assert n == 1 and "COMPUTED" not in text


def test_the_committed_source_table_covers_every_criterion() -> None:
    with SOURCES_CSV.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    criteria = load_criteria()

    assert [r["criterion_id"] for r in rows] == sorted(criteria)
    for r in rows:
        assert r["source_text"].strip(), r["criterion_id"]
        if r["source_text"] != NOT_FOUND:
            fields = [p.rsplit(":", 1)[-1] for p in r["source_file"].split(JOIN)]
            assert set(fields) <= {
                COVERAGE_FIELD,
                ASSOCIATED_FIELD,
                "summary_of_evidence",
                "analysis_of_evidence",
            }
            assert Path(r["source_file"].split(":", 1)[0]).name == "current_lcd.zip"


# --- regression tests for bugs found in V1b ---------------------------------------------------


def test_regression_adjacent_list_items_are_one_excerpt_not_a_gap() -> None:
    """Bug: consecutive list items were joined with " [...] ", which marked 9 criteria composite."""
    lcd = _lcd(RAW)

    _, text = resolve(lcd, [f"{COVERAGE_FIELD}:1:0", f"{COVERAGE_FIELD}:2:0"])

    assert JOIN not in text
    assert text in lcd.text(COVERAGE_FIELD)  # one stretch of the field's text, word for word


def test_regression_percentages_are_extracted() -> None:
    """Bug: the pattern needed a word boundary after "%", so "50% improvement" gave nothing and
    every percentage in the criteria and sources was skipped."""
    assert values("at least 50% improvement in pain") == {"at least 50 %"}
    assert values("a 30% loss of upper field") == {"30 %"}
    assert differing_values("at least 50% relief", "at least 30% relief") == [
        "criterion: at least 50 %",
        "source: at least 30 %",
    ]


def test_regression_or_less_is_an_upper_bound() -> None:
    """Bug: "or more" was read as a qualifier but "or less" was ignored."""
    assert values("an ejection fraction of 40% or less") == {"at most 40 %"}
    assert values("an ejection fraction of 40% or less") == values("up to 40%")
    assert values("4 weeks or more") == {"at least 4 week"}


def test_judgments_are_not_overwritten_without_force(tmp_path) -> None:  # noqa: ANN001
    """Incident: a re-run replaced 910 judgments with an empty file. They cannot be regenerated."""
    path = tmp_path / "judgments.csv"
    first = [
        Judgment("L1-cov-001", "out of scope", "reason"),
        Judgment("L1-cov-002", "rule candidate", "r"),
    ]

    assert save_judgments(first, path) == 2
    with pytest.raises(JudgmentsExist):
        save_judgments([], path)  # an empty save must not wipe them
    with pytest.raises(JudgmentsExist):
        save_judgments(first[:1], path)
    assert save_judgments(first[:1], path, force=True) == 1

    with pytest.raises(ValueError, match="unknown classification"):
        save_judgments([Judgment("L1-cov-003", "maybe", "r")], tmp_path / "other.csv")
    with pytest.raises(ValueError, match="judged twice"):
        save_judgments([first[0], first[0]], tmp_path / "third.csv")
    assert (
        save_judgments(
            [Judgment("L1-cov-004", "covered by POL-X-001.c1 (paraphrase)", "r")],
            tmp_path / "fourth.csv",
        )
        == 1
    )
