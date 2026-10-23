"""The v3 gate's matching (training/generate/v3/verify.py; the gate fix of 20 Oct, D-V3-12).

- quote to fact: a verifier quote that states another fact is replaced by the note's own sentence
  for this one, or fails the note; a terse quote of the right fact counts; a fact split over
  adjacent sentences, written with short forms or with a spelled-out number is found; a
  contradiction only word for word; a value counts only as a number of its own;
- the claim's own wording: naming the requested procedure is no leak, while a sentence that states
  the missing fact beyond it still fails the note, and a diagnosis line is not waved through;
- the second look: a leak finding counts only when the verifier, asked about that fact alone,
  finds it again; the fact's own negative mention is no leak, but its flip is.

Synthetic sentences only.
"""

import pytest

from training.generate.v3 import verify
from training.generate.v3.verify import (
    ago_dates,
    check_note,
    claim_words,
    expand,
    has_value,
    missing_matches,
    stated_locally,
    words,
)

EYELIDS = "The patient says the eyelids block the upper vision, making reading and driving hard."
TAPED = "With the lids taped up, the upper visual field improves by 12 degrees on testing."
CARE_PLAN = (
    "The care plan covers off-loading, infection control and blood-sugar management to help the "
    "wound close."
)
PROCEDURE = "Removal of dead tissue from a wound down to the fat layer, first 20 square cm or less"


@pytest.fixture(autouse=True)
def _no_label_check(monkeypatch: pytest.MonkeyPatch) -> None:
    # The label recomputation (check 4) needs a whole fact sheet; these tests are about matching.
    monkeypatch.setattr(verify, "label_problems", lambda *args: [])


def documented(fid: str, text: str, values: list[str] | None = None, **extra: object) -> dict:
    return {
        "fact_id": fid,
        "kind": "criterion",
        "status": "documented",
        "label_status": "MET",
        "text": {"A": text},
        "values": values or [],
        **extra,
    }


def sheet(*facts: dict, procedures: list[str] | None = None, diagnoses: list[str] | None = None):
    return {
        "sheet_id": "S-TEST",
        "writer": "B",
        "facts": list(facts),
        "procedures": procedures or [],
        "diagnoses": [{"code": "X", "description": d} for d in diagnoses or []],
    }


def wound_missing() -> dict:
    return {
        "fact_id": "F2",
        "kind": "criterion",
        "status": "missing",
        "label_status": "NOT_DOCUMENTED",
        "missing_text": "What was removed from the wound, how deep, and the wound size",
        "forbidden": [
            "Dead tissue was removed from the {size} cm ulcer on the {site} down to the fat "
            "layer, with the patient seen one on one.",
            "Only the dressing was changed; no dead tissue was removed.",
        ],
    }


# --- quote to fact -------------------------------------------------------------------------------


def test_a_quote_that_states_another_fact_gives_way_to_the_notes_own_sentence() -> None:
    note = f"HPI: {EYELIDS}\nRESULTS: {TAPED}"
    facts = sheet(documented("F1", EYELIDS), documented("F2", TAPED, ["12"]))
    result = check_note(facts, note, None, {"F1": TAPED, "F2": TAPED})
    assert result.failures == []
    assert note[slice(*result.spans["F1"])] == EYELIDS
    assert result.local_spans == ["F1"]


def test_a_mixed_up_quote_fails_the_note_when_the_fact_is_not_there() -> None:
    note = f"HPI: Reading is fine.\nRESULTS: {TAPED}"
    facts = sheet(documented("F1", EYELIDS), documented("F2", TAPED, ["12"]))
    result = check_note(facts, note, None, {"F1": TAPED, "F2": TAPED})
    assert "F1: the quote does not state the fact" in result.failures


def test_a_terse_quote_of_the_right_fact_counts() -> None:
    note = "Plan: Off-loading, infection control, blood sugar mgmt. Return in 1 week."
    result = check_note(
        sheet(documented("F1", CARE_PLAN)),
        note,
        None,
        {"F1": "Off-loading, infection control, blood sugar mgmt."},
    )
    assert result.failures == []
    assert result.local_spans == []


def test_a_fact_split_over_adjacent_sentences_or_written_short_is_found() -> None:
    fact = documented(
        "F1",
        "Memory problems have grown over 19 months, and the results will guide treatment.",
        ["19"],
    )
    note = "Memory problems for 19 mos, grew; results will guide tx. Exam unremarkable."
    span = stated_locally(note, fact)
    assert span is not None
    assert note[slice(*span)] == "Memory problems for 19 mos, grew; results will guide tx."
    assert {"month", "treatment"} <= words("Memory problems for 19 mos; guide tx")
    assert expand("Pt c/o LBP, failed PT") == (
        "patient complains of low back pain, failed physical therapy"
    )


def test_a_spelled_out_number_is_the_value() -> None:
    fact = documented(
        "F1", "Forgetfulness has worsened over 9 months, and testing will help.", ["9"]
    )
    note = "Forgetfulness has worsened over the past nine months, and testing will help."
    assert stated_locally(note, fact) is not None


def test_a_value_counts_only_as_a_number_of_its_own() -> None:
    weeks = ["The pain has lasted 5 weeks."]
    assert has_value("pain x5wks", "5", weeks)
    assert has_value("pain for 5 weeks", "5", weeks)
    assert not has_value("MRI C5-C6 disc", "5", weeks)  # a spinal level, not the 5 weeks
    assert not has_value("Oswestry 44%", "4", ["The first injection 4 months ago."])
    assert not has_value("pain 5/10", "5", weeks)
    assert has_value("MRI C5-C6 disc", "5", ["MRI C5-C6: disc herniation."])  # the fact's own form
    assert has_value("SWM: 2/5 sites insensate", "2", ["SWM: 2/5 sites insensate left foot."])
    assert has_value("pain 7/10", "7/10")


def test_a_contradiction_is_found_only_word_for_word() -> None:
    fact = {
        **documented("F1", "Symptoms have lasted 8 weeks despite physical therapy.", ["8"]),
        "status": "contradicted",
        "original": {"A": "The pain began 6 days ago, and no treatment has been tried."},
    }
    exact = "Update: Symptoms have lasted 8 weeks despite physical therapy."
    assert stated_locally(exact, fact) is not None
    assert stated_locally("Symptoms lasted 8 weeks despite PT.", fact) is None
    copied = "Copied: The pain began 6 days ago, and no treatment has been tried."
    assert stated_locally(copied, fact, original=True) is not None


# --- the claim's own wording ---------------------------------------------------------------------


def test_naming_the_requested_procedure_is_no_leak() -> None:
    facts = sheet(wound_missing(), procedures=[PROCEDURE])
    note = (
        "The plan involves removal of dead tissue from the wound down to the fat layer, with the "
        "first 20 square cm or less to be treated."
    )
    assert missing_matches(note, wound_missing()["forbidden"], claim_words(facts)) == []
    result = check_note(facts, note, None, {"F2": note})
    assert result.failures == []
    assert result.looks == []  # mostly the procedure's own words: not even a second look


def test_stating_the_missing_fact_beyond_the_procedure_wording_still_fails() -> None:
    facts = sheet(wound_missing(), procedures=[PROCEDURE])
    note = (
        "Dead tissue was removed from the 4 cm ulcer on the left foot down to the fat layer, "
        "with the patient seen one on one."
    )
    result = check_note(facts, note, None, {"F2": None})
    assert any("missing fact appears" in f for f in result.failures)


@pytest.mark.usefixtures("looks_on")
def test_a_diagnosis_line_is_not_waved_through() -> None:
    heart = {
        "fact_id": "F1",
        "kind": "criterion",
        "status": "missing",
        "label_status": "NOT_DOCUMENTED",
        "missing_text": "Heart symptoms or a known heart condition that call for an echocardiogram",
        "forbidden": ["Shortness of breath on stairs and leg swelling suggest heart failure."],
    }
    facts = sheet(heart, diagnoses=["Chronic systolic (congestive) heart failure"])
    note = "A/P: Chronic systolic (congestive) heart failure (I50.22)."
    result = check_note(facts, note, None, {"F1": note})
    assert result.looks == ["F1"]  # the verifier is asked again: a diagnosis can document it


# --- the second look -----------------------------------------------------------------------------


def score_missing() -> dict:
    return {
        "fact_id": "F1",
        "kind": "criterion",
        "status": "missing",
        "label_status": "NOT_DOCUMENTED",
        "missing_text": "A pain score recorded before treatment",
        "forbidden": ["The patient rates pain {pain}/10 on a numeric scale today."],
    }


@pytest.fixture
def looks_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(verify, "second_look_on", lambda: True)


def test_a_leak_finding_counts_at_once_with_the_second_look_off(monkeypatch) -> None:
    monkeypatch.setattr(verify, "second_look_on", lambda: False)
    note = "Exam: tender lumbar paraspinals. Pain is 7 of 10 today."
    result = check_note(sheet(score_missing()), note, None, {"F1": "Pain is 7 of 10 today."})
    assert result.looks == [] and any("found the missing fact" in f for f in result.failures)


@pytest.mark.usefixtures("looks_on")
def test_a_leak_finding_counts_only_when_the_second_look_finds_it_again() -> None:
    note = "Exam: tender lumbar paraspinals. Pain is 7 of 10 today."
    cited = "Pain is 7 of 10 today."  # too few of the wording's words for the local check
    first = check_note(sheet(score_missing()), note, None, {"F1": cited})
    assert first.looks == ["F1"] and first.pending and not first.passed
    again = check_note(sheet(score_missing()), note, None, {"F1": cited}, {"F1": cited})
    assert any("found the missing fact twice" in f for f in again.failures)
    cleared = check_note(sheet(score_missing()), note, None, {"F1": cited}, {"F1": None})
    assert cleared.passed


def test_a_quote_about_something_else_is_no_finding() -> None:
    note = "Exam: tender lumbar paraspinals. Gait is steady."
    result = check_note(sheet(score_missing()), note, None, {"F1": "Gait is steady."})
    assert result.passed and result.looks == []


@pytest.mark.usefixtures("looks_on")
def test_the_exclusions_own_negative_mention_is_no_leak_but_its_flip_is() -> None:
    cataract = {
        "fact_id": "F2",
        "kind": "criterion",
        "status": "absent",
        "label_status": "NOT_APPLICABLE",
        "role": "exclusion",
        "forbidden": [
            "The lens is slightly cloudy on exam, but the patient has no vision complaints."
        ],
        "negated": {"A": "The patient does have vision complaints from the cataract."},
    }
    own = "The patient does have vision complaints from the cataract."
    assert check_note(sheet(cataract), own, None, {"F2": own}).passed
    flipped = "The patient does not have vision complaints from the cataract."
    assert check_note(sheet(cataract), flipped, None, {"F2": flipped}).looks == ["F2"]


def test_a_time_before_the_visit_may_be_written_as_its_date() -> None:
    fact = documented("F4", "The previous injection 4 months ago brought 45% relief.", ["4", "45"])
    facts = {**sheet(fact), "visit_date": "2026-11-01", "timeline": []}
    dates = ago_dates(facts, fact)
    wording = fact["text"].values()
    assert has_value("injection on 07/01/2026 gave 45% relief", "4", wording, dates)
    assert has_value("injection July 1, 2026", "4", wording, dates)
    assert not has_value("injection on 06/01/2026 gave 45% relief", "4", wording, dates)
    assert not has_value("Oswestry 44%", "4", wording, dates)
    given = {**facts, "timeline": [{"date": "2026-07-04", "fact_id": "F4"}]}  # the writer's date
    assert has_value("injection 7/4/26", "4", wording, ago_dates(given, fact))
    assert has_value("palpitations 1x/5 days", "5", ["once every 5 days"])  # x/ is "per"


def test_a_quote_with_all_the_facts_values_is_about_it() -> None:
    fact = documented(
        "F2",
        "Pain is 8/10, and the Neck Disability Index score is 57%, limiting work.",
        ["8/10", "57"],
    )
    note = "MRI reviewed. Pain 8/10, NDI 57%. Plan injection."
    result = check_note(sheet(fact), note, None, {"F2": "Pain 8/10, NDI 57%."})
    assert result.failures == []


# --- the judge (the second look at a missing fact) -----------------------------------------------


def test_the_judge_answers_yes_or_no_and_nothing_else() -> None:
    from training.generate.v3.llm import parse_judge

    assert parse_judge('{"answer": "yes"}') is True
    assert parse_judge('Sure. {"answer": "No"}') is False
    with pytest.raises(ValueError):
        parse_judge("The passage partly supports it.")


def test_the_stage_judges_missing_facts_and_asks_again_about_exclusions() -> None:
    from training.generate.v3 import kaggle_stage
    from training.generate.v3.kaggle import run_config

    run = run_config()
    job = {
        "job_id": "S-1#1",
        "sheet_id": "S-1",
        "attempt": 1,
        "note": "HPI: pain. Plan: block.",
        "statements": [
            {"id": 1, "fact_id": "F1", "statement": "Pain for 6 weeks.", "expect": "present"},
            {
                "id": 2,
                "fact_id": "F2",
                "statement": "The note documents: a pain score.",
                "expect": "absent",
                "check": "judge",
            },
            {
                "id": 3,
                "fact_id": "F3",
                "statement": "Testing is a routine check.",
                "expect": "absent",
                "check": "look",
            },
        ],
    }
    answer = '{"answers": [{"id": 1, "quote": "HPI: pain."}, {"id": 2, "quote": "Plan: block."},'
    answer += ' {"id": 3, "quote": "HPI: pain."}]}'
    items = kaggle_stage.second_looks(
        run,
        {"temperature": 0.0, "max_tokens": 9},
        [{"job_id": "verify-S-1#1", "text": answer}],
        {"S-1#1": job},
    )
    ids = [item[0]["job_id"] for item in items]
    assert ids == ["judge-S-1#1:F2", "look-S-1#1:F3"]
    assert "Plan: block." in items[0][1][1]["content"]  # the judge reads the cited passage only
    assert "HPI: pain. Plan: block." in items[1][1][1]["content"]  # the look reads the note


def test_a_missing_fact_takes_the_judges_answer_and_an_exclusion_the_look(tmp_path) -> None:
    import json

    from training.generate.v3.dataset import second_look_answers

    sheets = {
        "S-1": {
            "facts": [
                {"fact_id": "F2", "status": "missing"},
                {"fact_id": "F3", "status": "absent"},
            ]
        }
    }
    rows = [
        {"sheet_id": "S-1", "attempt": 1, "fact_id": "F2", "quote": "Plan: block.", "error": None},
        {"sheet_id": "S-1", "attempt": 1, "fact_id": "F3", "quote": "HPI: pain.", "error": None},
        {
            "sheet_id": "S-1",
            "attempt": 1,
            "fact_id": "F2",
            "source": "judge",
            "quote": None,
            "error": None,
        },
    ]
    (tmp_path / "second_look.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    assert second_look_answers(tmp_path, sheets) == {("S-1", 1): {"F2": None, "F3": "HPI: pain."}}


# --- D-V3-14: two-part facts and lead lines ------------------------------------------------------


def test_every_part_of_a_two_part_met_fact_needs_support() -> None:
    from training.generate.v3.verify import supports_parts

    fact = documented(
        "F3",
        "Forgetfulness and slowed thinking have worsened over 14 months, and the results will "
        "decide between treatment for dementia and for depression.",
        ["14"],
    )
    half = "Referred for testing due to worsening forgetfulness and slowed thinking over 14 months."
    assert not supports_parts(half, fact)
    whole = half + " Results will decide between dementia and depression treatment."
    assert supports_parts(whole, fact)
    one_part = documented("F1", "The pain has lasted 6 weeks despite physical therapy.", ["6"])
    assert supports_parts("Pain x6 wks.", one_part)  # a fact of one part is not split


def test_a_lead_never_states_a_criterion_the_sheet_marks_missing() -> None:
    from training.generate.v3.sheets import safe_lead

    lead = {"A": "The patient is seen for heart rhythm symptoms.", "B": "CC: palpitations."}
    missing = [{"fact_id": "F1", "criterion_id": "POL-CAR-002.c6", "status": "missing"}]
    documented_too = [{"fact_id": "F1", "criterion_id": "POL-CAR-002.c6", "status": "documented"}]
    new, replaced = safe_lead(lead, missing)
    assert replaced and "symptom" not in new["A"] and "palpitation" not in new["B"].lower()
    assert safe_lead(lead, documented_too) == (lead, False)


def test_the_training_trim_keeps_top_ups_writers_and_tricky_shares(monkeypatch) -> None:
    from collections import Counter

    from training.generate.v3 import build

    monkeypatch.setattr(
        build,
        "config",
        lambda: {
            "sizes": {"train": 10},
            "writer_mix": {"train": {"A": 0.5, "B": 0.5}},
            "top_up": {"floors": {"tricky": 3}},
        },
    )
    # one coverage cell, held by the rows of sheets S0 to S3 only: its floor is 3
    cell = ("tricky", "POL-X borderline")

    def cells_of(sheet: dict) -> Counter:
        return Counter({cell: 1} if sheet["sheet_id"] in ("S0", "S1", "S2", "S3") else {})

    monkeypatch.setattr(build, "sheet_cells", cells_of)
    monkeypatch.setattr(
        build, "cell_counts", lambda sheets: sum((cells_of(s) for s in sheets), Counter())
    )

    def sheet_of(i: int, borderline: bool, top_up: bool = False) -> dict:
        return {
            "sheet_id": f"S{i}",
            "split": "train",
            "tricky": ["borderline"] if borderline else [],
            "distractors": {},
            **({"top_up": ["cell"]} if top_up else {}),
        }

    # drawn: 1 in 4 natural sheets has a borderline fact; the passing rows hold more of them
    sheets = {f"S{i}": sheet_of(i, i % 4 == 0) for i in range(40)}
    rows = [
        ({"metadata": {"sheet_id": f"S{i}", "writer": "AB"[i % 2]}}, {})
        for i in range(40)
        if i % 4 == 0 or i < 12
    ]
    sheets["S99"] = sheet_of(99, False, top_up=True)
    rows.append(({"metadata": {"sheet_id": "S99", "writer": "B", "top_up": ["cell"]}}, {}))
    kept, report = build._balanced_train(rows, sheets)
    ids = [r[0]["metadata"]["sheet_id"] for r in kept]
    assert len(kept) == 10 and "S99" in ids and report["cut"] == 10
    assert sum(i in ids for i in ("S0", "S1", "S2", "S3")) >= 3  # the cell stays at its floor
    assert sum(r[0]["metadata"]["writer"] == "A" for r in kept) == 5
    share = sum(sheets[i]["tricky"] == ["borderline"] for i in ids) / 10
    assert share <= 0.3  # 10 of the 20 rows had one: the cuts take those first
