"""Task V1a label checks: each check flags a planted wrong record and leaves a correct one alone.

The checks run on small in-memory records with fixed lookups, so no `data/raw/`, curated files or
embedding model are needed. The same planted cases are the script's runtime self-test.
"""

import copy
import csv
import io

import pytest

from scripts.verify.label_checks import (
    CHECK_NAMES,
    Flag,
    Support,
    WordOverlap,
    calibrate,
    check_criterion_ids,
    check_decision_rule,
    check_evidence,
    check_mcd,
    check_not_applicable,
    content_words,
    implied_decision,
    note_sentences,
    planted_cases,
    planted_lookups,
    redact_hcpc_row,
    review_markdown,
    review_sample,
    run_planted,
    structural_cue,
    subject,
    supported,
)


@pytest.mark.parametrize("case", planted_cases(), ids=lambda case: case.name)
def test_every_planted_case_behaves_as_expected(case) -> None:  # noqa: ANN001
    """One planted wrong record per check is flagged; the planted correct records are not."""
    assert run_planted(case) == case.expect_flag


def test_every_check_has_a_planted_error_that_is_caught() -> None:
    caught = {case.check for case in planted_cases() if case.expect_flag}
    assert caught == set(CHECK_NAMES)


def test_the_ncci_exemption_is_narrow() -> None:
    """B: exempt only NCCI_BYPASS + PEND + no NOT_MET or NOT_DOCUMENTED criterion."""
    names = {case.name: case for case in planted_cases()}

    assert not run_planted(names["2: NCCI_BYPASS PEND line, all criteria MET"])
    assert run_planted(names["2: PEND line, all criteria MET, no flag"])


def test_checks_never_change_the_record() -> None:
    lookups = planted_lookups()
    for case in planted_cases():
        before = copy.deepcopy(case.record)
        run_planted(case)
        assert case.record == before
    assert lookups == planted_lookups()


def test_group_rules_combine_as_documented() -> None:
    """`1|2+3`: group 1 alone, or one diagnosis in group 2 and one in group 3."""
    rule = Support(article="A1", alternatives=((1,), (2, 3)))
    covered = {"A1": {1: frozenset({"K921"}), 2: frozenset({"Z1211"}), 3: frozenset({"Z8601"})}}

    assert supported(["K921"], rule, covered)
    assert supported(["Z1211", "Z8601"], rule, covered)
    assert not supported(["Z1211"], rule, covered)  # group 2 without group 3
    assert not supported(["J069"], rule, covered)
    assert not supported(["K921"], Support("A-missing", ((1,),)), covered)


def test_a_procedure_without_an_article_is_not_checkable() -> None:
    names = {case.name: case for case in planted_cases()}
    record = names["1: APPROVE line, diagnosis covered"].record
    office = copy.deepcopy(record)
    office.claim["service_lines"][0]["procedure_code"] = "99213"

    flags, not_checkable = check_mcd(office, planted_lookups())

    assert flags == [] and not_checkable == 1


def test_the_implied_decision_follows_the_precedence() -> None:
    assert implied_decision(["MET", "NOT_DOCUMENTED", "NOT_MET"]) == "DENY"
    assert implied_decision(["MET", "NOT_DOCUMENTED"]) == "PEND"
    assert implied_decision(["MET", "NOT_APPLICABLE"]) == "APPROVE"
    assert implied_decision([]) == "APPROVE"


def test_the_subject_is_what_the_criterion_is_about() -> None:
    assert subject("Stress echocardiography is covered to evaluate chest pain.") == (
        "Stress echocardiography"
    )
    assert subject("The patient must have back pain.") == "The patient"
    assert content_words("The tests and the patch") == {"tests", "patch"}  # no function words


def test_a_structural_cue_needs_another_codes_procedure_in_the_subject() -> None:
    codes = ("93306", "93350")
    descriptions = {
        "93306": "Complete heart ultrasound through the chest wall",
        "93350": "Heart ultrasound during an exercise or drug stress test",
    }

    cue = structural_cue(
        "Stress echocardiography is covered for chest pain.", "93306", codes, descriptions
    )
    assert cue is not None and "93350" in cue and "stress" in cue
    # names the line's own procedure too: not a cue
    assert (
        structural_cue("Stress and complete studies are covered.", "93306", codes, descriptions)
        is None
    )
    # the other procedure is only mentioned in the body, not the subject: not a cue
    assert (
        structural_cue(
            "Repeat studies are covered after a stress test.", "93306", codes, descriptions
        )
        is None
    )
    # a procedure code in the text that is not the line's is always a cue
    assert "93350" in structural_cue(
        "Code 93350 needs a stress protocol.", "93306", codes, descriptions
    )
    assert structural_cue("Code 93306 is covered.", "93306", codes, descriptions) is None


def test_a_subject_about_the_patient_names_no_procedure() -> None:
    """Audit finding: "colon" in "colon cancer" matched a colonoscopy description's "the colon"."""
    codes = ("45378", "45385")
    descriptions = {
        "45378": "Colonoscopy to look inside the colon, with no tissue removed",
        "45385": "Colonoscopy with polyp removal using a wire snare",
    }
    text = "Patients identified as high risk for colon cancer are eligible for screening."

    assert structural_cue(text, "45385", codes, descriptions) is None
    assert structural_cue("Colon inspection is covered.", "45385", codes, descriptions)


def test_note_sentences_keep_shorthand_together() -> None:
    notes = "CC: hand numbness. L leg weakness + tingling; exam c/w neuropathy. Plan -> NCS."

    assert note_sentences(notes) == [
        "CC: hand numbness.",
        "L leg weakness + tingling; exam c/w neuropathy.",
        "Plan -> NCS.",
    ]


def test_the_threshold_is_the_fifth_percentile_of_real_evidence() -> None:
    pairs = [(f"criterion {i}", f"evidence {i}") for i in range(20)]

    class Fixed:
        def scores(self, criterion: str, candidates: list[str]) -> list[float]:
            return [int(criterion.split()[1]) / 100 for _ in candidates]

    assert calibrate(pairs, Fixed()) == 0.0  # nearest rank: the 1st of 20 values
    pairs = [(f"criterion {i}", f"evidence {i}") for i in range(1, 101)]
    assert calibrate(pairs, Fixed()) == 0.05


def test_check_5_records_where_each_cue_came_from() -> None:
    names = {case.name: case for case in planted_cases()}
    lookups = planted_lookups()

    flags, cues = check_not_applicable(
        names["5: NOT_APPLICABLE with a related note sentence"].record, lookups, WordOverlap(), 0.34
    )
    assert flags == [] and [c["result"] for c in cues] == ["cue found"]
    assert cues[0]["source"] == "notes"

    flags, cues = check_not_applicable(
        names["5: NOT_APPLICABLE cleared by a structural cue"].record, lookups, WordOverlap(), 0.34
    )
    assert flags == [] and cues[0]["result"] == "structural"


def test_other_checks_leave_the_correct_base_record_alone() -> None:
    names = {case.name: case for case in planted_cases()}
    record = names["1: APPROVE line, diagnosis covered"].record

    assert check_decision_rule(record) == ([], 0)
    assert check_evidence(record)[0] == []
    assert check_criterion_ids(record) == []


def test_cpt_descriptors_are_removed_from_source_rows() -> None:
    row = '57204,45,70450,101,1,"COMPUTED TOMOGRAPHY, HEAD; WITHOUT",Ct head,N,2026-05-05 18:30:56'

    redacted = redact_hcpc_row(row)

    fields = next(csv.reader(io.StringIO(redacted)))
    assert "COMPUTED" not in redacted and "Ct head" not in redacted
    assert fields[:5] == ["57204", "45", "70450", "101", "1"]
    assert fields[7:] == ["N", "2026-05-05 18:30:56"]


def _flags(check: int, count: int) -> list[Flag]:
    return [
        Flag(
            check=check,
            split="test",
            record_id=f"DEC-TE-{check}{n:04d}",
            line_no=1,
            what="w",
            left="l",
            right="r",
            look_up="x",
            score=n / 100 if check == 5 else None,
        )
        for n in range(count)
    ]


def test_the_review_sample_is_small_seeded_and_includes_the_lowest_scores() -> None:
    flags = [*_flags(1, 10), *_flags(2, 1), *_flags(3, 0), *_flags(4, 0), *_flags(5, 40)]

    rows = review_sample(flags)

    per_check = {c: [r for r in rows if r.check == c] for c in CHECK_NAMES}
    assert len(per_check[1]) == 3 and len(per_check[2]) == 1 and per_check[3] == []
    assert len(per_check[5]) == 5
    lowest = sorted(f.score for f in flags if f.check == 5)[:2]
    assert set(lowest) <= {r.score for r in per_check[5]}  # the 2 lowest are always shown
    assert rows == review_sample(flags)  # seed 42: the same rows every run


def test_the_review_file_has_the_required_header_and_columns() -> None:
    flags = [*_flags(1, 5), *_flags(2, 5), *_flags(3, 5), *_flags(4, 5), *_flags(5, 50)]
    rows = review_sample(flags)
    summary = {
        "records": "2,600",
        "lines": "3,335",
        "counts": ["1 MCD: 5"],
        "methods": ["Check 1 uses app/db/raw.read_article_diagnoses"],
        "self_test": "Checker self-test: 12/12 planted cases behaved as expected",
    }

    text = review_markdown(summary, rows)

    lines = text.splitlines()
    assert lines[0].startswith("# ")
    assert lines[2] == "For each row write REAL ERROR, FALSE ALARM or UNSURE."
    assert "Checker self-test: 12/12" in text
    assert f"Estimated review time: {2 * len(rows)} minutes" in text
    assert 2 * len(rows) <= 35
    header = next(line for line in lines if line.startswith("| #"))
    assert [c.strip() for c in header.strip("|").split("|")] == [
        "#",
        "Check",
        "Record ID",
        "What was flagged",
        "Evidence (side by side)",
        "Where to look it up",
        "Your verdict",
        "Notes",
    ]
