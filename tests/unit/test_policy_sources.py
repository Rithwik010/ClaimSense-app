"""Task V1b policy source and completeness checks: made-up and changed sources are flagged, LCD
text is extracted and mapped deterministically. In-memory LCDs only; no data/raw/ needed."""

import csv
from collections import Counter
from pathlib import Path

import pytest

from scripts.verify.policy_sources import (
    ASSOCIATED_FIELD,
    COVERAGE_FIELD,
    FINDING_KINDS,
    FINDINGS,
    JOIN,
    MISSING,
    NOT_FOUND,
    RULE,
    SOURCES_CSV,
    WRONG,
    Criterion,
    DatasetLine,
    Finding,
    Item,
    Judgment,
    JudgmentsExist,
    Lcd,
    SourceRow,
    best_similarity,
    blocks,
    check_source,
    classify,
    conditions,
    criterion_usage,
    differing_values,
    fill_sitting,
    group_findings,
    items_of,
    load_criteria,
    mapped_criteria,
    merge_judgments,
    planted_cases,
    planted_lcd,
    redact,
    resolve,
    rule_classification,
    run_planted,
    save_judgments,
    scope_codes,
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


def test_a_saved_judgment_overrides_a_keyword_rule() -> None:
    """V1b: the billing keyword rule called "Bill type codes only apply to ... Part A" a rule
    candidate; the saved judgment (out of scope) must win."""
    rule = ("rule candidate", "coding or billing instruction checkable from claim codes")
    judgment = Judgment("L1-cov-052", "out of scope", "Part A bill types", "", "judgment")

    assert classify([], judgment, rule, needs_judgment=False) == (
        "out of scope",
        "Part A bill types",
        "judgment",
        "",
    )
    assert classify([], None, rule, needs_judgment=False) == (*rule, "rule", "")
    assert classify([], None, None, needs_judgment=True) is None  # waits for a judgment
    assert classify(["POL-P.c1"], judgment, rule, needs_judgment=False)[0] == "mapped"


def test_added_judgments_replace_by_item_and_keep_order() -> None:
    old = {
        "a": Judgment("a", "out of scope", "r1"),
        "b": Judgment("b", "rule candidate", "r2"),
    }
    merged = merge_judgments(
        old, [Judgment("b", "out of scope", "fixed"), Judgment("c", "out of scope", "new")]
    )
    assert [(j.item_id, j.reason) for j in merged] == [("a", "r1"), ("b", "fixed"), ("c", "new")]


def _gap(item_id: str, classification: str = "affects decisions", codes: str = "") -> dict:
    return {
        "item_id": item_id,
        "policy_id": "POL-P",
        "classification": classification,
        "codes": codes,
    }


def test_findings_hold_every_gap_item_exactly_once() -> None:
    rows = [
        _gap("L1-cov-001", codes="111"),
        _gap("L1-cov-002", "rule candidate"),
        _gap("L1-cov-003", "out of scope"),
    ]
    findings = [
        Finding("POL-P.F1", MISSING, "add it", ("cov-001",)),
        Finding("POL-P.F2", RULE, "check it", ("cov-002",)),
    ]
    args = ({"POL-P": "L1"}, Counter({"111": 5, "222": 7}), {"POL-P": ["111", "222"]})

    grouped = group_findings(rows, findings, *args)

    assert [(g["finding_id"], g["codes"], g["impact"]) for g in grouped] == [
        ("POL-P.F1", "111", 5),
        ("POL-P.F2", "111 222", 12),  # no codes of its own: the policy's codes
    ]
    with pytest.raises(ValueError, match="L1-cov-002: not in any finding"):
        group_findings(rows, findings[:1], *args)
    with pytest.raises(ValueError, match="L1-cov-001: in 2 findings"):
        group_findings(rows, [*findings, Finding("POL-P.F3", MISSING, "x", ("cov-001",))], *args)
    with pytest.raises(ValueError, match="L1-cov-003 is not a gap item"):
        group_findings(rows, [*findings, Finding("POL-P.F3", MISSING, "x", ("cov-003",))], *args)
    with pytest.raises(ValueError, match="'rule candidate', not 'affects decisions'"):
        group_findings(rows, [Finding("POL-P.F1", MISSING, "x", ("cov-001", "cov-002"))], *args)


def test_the_findings_table_is_well_formed() -> None:
    criteria = load_criteria()
    codes = scope_codes()
    ids = [f.finding_id for f in FINDINGS]

    assert len(ids) == len(set(ids))
    for f in FINDINGS:
        assert f.kind in FINDING_KINDS and f.change and f.items, f.finding_id
        assert f.policy_id in codes, f.finding_id
        if f.kind == WRONG:
            assert f.criteria and f.codes, f.finding_id
            assert all(criteria[c].policy_id == f.policy_id for c in f.criteria)
            assert set(f.codes) <= set(codes[f.policy_id])
        else:
            assert not f.criteria and not f.codes, f.finding_id


def test_wrong_criterion_lines_are_counted_by_split_and_gold_decision() -> None:
    finding = Finding("POL-P.F1", WRONG, "x", ("cov-001",), ("POL-P.c1",), ("95024",))
    lines = [
        DatasetLine("train", "95024", "DENY", {"POL-P.c1": "NOT_MET"}),
        DatasetLine("train", "95024", "APPROVE", {"POL-P.c1": "MET", "POL-P.c2": "MET"}),
        DatasetLine("train", "95004", "APPROVE", {"POL-P.c1": "MET"}),  # another code
        DatasetLine("test", "95024", "PEND", {"POL-P.c1": "NOT_APPLICABLE"}),  # not used
        DatasetLine("test", "95024", "PEND", {"POL-P.c2": "MET"}),  # another criterion
    ]

    usage = criterion_usage(finding, lines)

    assert usage["train"].lines == 3 and usage["train"].on_codes == 2
    assert usage["train"].decisions == Counter({"APPROVE": 1, "DENY": 1})
    assert usage["train"].statuses == Counter({"c1 MET": 1, "c1 NOT_MET": 1})
    assert usage["test"].lines == 0 and usage["validation"].lines == 0


def test_a_sitting_keeps_required_rows_then_fills_in_order_within_the_budget() -> None:
    def minutes(row: int) -> int:
        return row

    shown, left, total = fill_sitting([10, 10], [5, 20, 1], minutes, budget=30)
    assert shown == [10, 10, 5] and left == [20, 1] and total == 25  # order kept: 1 is not pulled
    shown, _, total = fill_sitting([40], [1], minutes, budget=30)
    assert shown == [40] and total == 40  # required rows are always shown


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
