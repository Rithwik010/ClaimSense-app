"""Generator v3 (training/generate/v3/SPEC.md): the parts that need no data/raw (run in CI).

- SPEC.md and config.yaml name the same parameters;
- the leakage scan finds outcome words and IDs, and no phrase-bank sentence has one;
- noise never changes a protected span, a number, a date or a negation word;
- quotes are found exactly (or with only whitespace differences), and the verifier's answers parse;
- the verifier's evidence for a missing fact fails a note, as does a missing documented fact;
- every borderline case gives the status its side needs, from the policy threshold.
"""

import random
import re
from pathlib import Path

import pytest

from training.generate.scenarios_v2 import load_templates_v2
from training.generate.v3 import noise
from training.generate.v3.config import (
    BorderlineForm,
    borderline_met,
    borderlines,
    config,
    criteria_phrases,
    leaks,
    phrases,
)
from training.generate.v3.llm import clean_note, parse_verifier
from training.generate.v3.segments import Segment, render
from training.generate.v3.verify import check_note, locate, missing_matches, near_duplicates

SPEC = Path(__file__).resolve().parents[2] / "training" / "generate" / "v3" / "SPEC.md"


def leaf_paths(value: object, prefix: str = "") -> list[str]:
    if isinstance(value, dict):
        found = []
        for key, item in value.items():
            found += leaf_paths(item, f"{prefix}.{key}" if prefix else str(key))
        return found
    return [prefix]


def test_spec_names_every_config_parameter() -> None:
    named = set(re.findall(r"`([a-z_][a-z0-9_.<>*]*)`", SPEC.read_text(encoding="utf-8")))
    prefixes = {re.sub(r"\.(\*|<[^>]+>)$", "", n) for n in named}
    uncovered = []
    for path in leaf_paths(config()):
        parts = path.split(".")
        ancestors = {".".join(parts[: i + 1]) for i in range(len(parts))}
        if not ancestors & prefixes:
            uncovered.append(path)
    assert uncovered == []


@pytest.mark.parametrize(
    ("text", "found"),
    [
        ("The patient denies fever.", ["denies"]),
        ("Results are pending.", ["pending"]),
        ("The wound is covered with gauze.", ["covered"]),
        ("This is medically necessary.", ["medically necessary"]),
        ("Per POL-PAIN-001 criterion .c10", ["POL-PAIN-001", ".c10"]),
        ("Status MET by review", ["MET"]),
        ("Goals were met; approximately 6 weeks after appendectomy.", []),
    ],
)
def test_the_leakage_scan(text: str, found: list[str]) -> None:
    assert [w for w in leaks(text)] == found or sorted(leaks(text)) == sorted(found)


METADATA = {
    "source",
    "topics",
    "code",
    "kind",
    "section",
    "with_not_met",
    "rule",
    "checks",
    "derive",
    "date_slot",
    "replace",
    "placement",
    "slots",
    "exclude",
    "names",
}


def test_no_phrase_bank_sentence_leaks() -> None:
    sentences: list[str] = []

    def collect(value: object) -> None:
        if isinstance(value, str):
            sentences.append(value)
        elif isinstance(value, dict):
            for key, item in value.items():
                if key not in METADATA:
                    collect(item)
        elif isinstance(value, list):
            for item in value:
                collect(item)

    for name in ("criteria", "sections", "abbreviations"):
        collect(phrases(name))
    leaked = [s for s in sentences if leaks(s)]
    assert leaked == []


def test_v3_sentences_use_only_the_slots_of_their_v2_sentences() -> None:
    t = load_templates_v2()
    slot = re.compile(r"\{(\w+)\}")
    problems = []
    for criterion_id, extra in criteria_phrases().items():
        v2 = t.criteria[criterion_id]
        for state in ("met", "not_met", "situation"):
            known = {
                s
                for sentences in getattr(v2, state).values()
                for sentence in sentences
                for s in slot.findall(sentence)
            }
            profile_slots = {
                name for profile in t.profiles[criterion_id.split(".")[0]] for name in profile.slots
            } | {"units"}
            for sentences in getattr(extra, state).values():
                for sentence in sentences:
                    unknown = set(slot.findall(sentence)) - known - profile_slots
                    if unknown:
                        problems.append(f"{criterion_id} {state}: {sorted(unknown)}")
    assert problems == []


def test_every_borderline_case_gives_its_sides_status() -> None:
    for borderline in borderlines().values():
        for form in borderline.forms:
            for case in form.above:
                assert borderline_met(borderline, form, case), (borderline.criterion_id, case)
            for case in form.below:
                assert not borderline_met(borderline, form, case), (borderline.criterion_id, case)


def test_a_strict_threshold_is_strict() -> None:
    headache = borderlines()["POL-IMG-001.c2"]
    form: BorderlineForm = headache.forms[0]
    assert not borderline_met(headache, form, {"days": 14})  # "more than two weeks"
    assert borderline_met(headache, form, {"days": 15})


def segments_with_fact() -> list[Segment]:
    return [
        Segment("History of present illness:", "hpi", "header"),
        Segment("\n", "hpi", "sep"),
        Segment("The patient reports no relief with physical therapy and medication", "hpi"),
        Segment(" ", "hpi", "sep"),
        Segment(
            "The pain has lasted 6 weeks, with no relief from physical therapy.",
            "hpi",
            fact_id="F1",
            protected=True,
        ),
        Segment("\n\n", "hpi", "sep"),
        Segment("Plan:", "plan", "header"),
        Segment("\n", "plan", "sep"),
        Segment("The patient will return without delay on 11/02/2026 for evaluation.", "plan"),
    ]


def test_noise_never_changes_a_protected_span_number_date_or_negation() -> None:
    original = segments_with_fact()
    text, spans = render(original)
    fact = text[spans["F1"][0] : spans["F1"][1]]
    for seed in range(200):
        noised, report = noise.apply(original, random.Random(seed))
        out, out_spans = render(noised)
        assert out[out_spans["F1"][0] : out_spans["F1"][1]] == fact
        assert "11/02/2026" in out
        assert re.search(r"\bno\b", out.split("The pain")[0])  # a negation word kept
        assert re.search(r"\bwithout\b", out)


def test_noise_reports_what_it_did() -> None:
    reports = [noise.apply(segments_with_fact(), random.Random(s))[1] for s in range(300)]
    assert any(r["abbreviation_swaps"] for r in reports)
    assert any(r["typos"] for r in reports)


def test_free_text_segments_protect_the_quotes() -> None:
    text = "Pain x6 wks despite PT. Exam with tenderness and normal strength."
    spans = {"F1": (0, 23)}
    segments = noise.free_text_segments(text, spans)
    assert [s.protected for s in segments] == [True, False]
    noised, _ = noise.apply(segments, random.Random(1), sections=False)
    assert render(noised)[0].startswith("Pain x6 wks despite PT.")


def test_quotes_are_found_exactly_or_across_whitespace_only() -> None:
    note = "Exam:\nThe pain has  lasted\n6 weeks. Plan: injection."
    assert locate(note, "Plan: injection.") == (note.index("Plan"), len(note))
    start, end = locate(note, "The pain has lasted 6 weeks.")
    assert note[start:end] == "The pain has  lasted\n6 weeks."
    assert locate(note, "The pain has lasted 8 weeks.") is None
    assert locate(note, "") is None


def test_a_missing_fact_is_found_by_its_content_words() -> None:
    note = "Symptoms have lasted several weeks despite therapy and anti-inflammatory medicine."
    template = (
        "Symptoms have lasted {weeks} weeks despite {therapy} and anti-inflammatory medicine."
    )
    assert missing_matches(note, [template])
    assert not missing_matches("Gait is steady.", [template])


def test_the_verifier_answer_parses_and_a_bad_one_does_not() -> None:
    answer = 'Sure.\n{"answers": [{"id": 1, "quote": "Pain x6 wks."}, {"id": 2, "quote": null}]}'
    assert parse_verifier(answer) == {1: "Pain x6 wks.", 2: None}
    with pytest.raises(ValueError):
        parse_verifier("no json here")


def test_model_wrappers_are_removed() -> None:
    assert clean_note("Here is the note:\nCC: back pain.") == "CC: back pain."
    assert clean_note("```\nCC: back pain.\n```") == "CC: back pain."


def minimal_sheet() -> dict:
    return {
        "sheet_id": "S-TEST",
        "writer": "B",
        "facts": [
            {
                "fact_id": "F1",
                "kind": "criterion",
                "status": "documented",
                "label_status": "MET",
                "text": {"A": "The pain has lasted 6 weeks despite physical therapy."},
                "values": ["6"],
            },
            {
                "fact_id": "F2",
                "kind": "criterion",
                "status": "missing",
                "label_status": "NOT_DOCUMENTED",
                "missing_text": "A pain score recorded before treatment",
                "forbidden": ["The patient rates pain {pain}/10 on a numeric scale today."],
            },
        ],
    }


NOTE = "HPI: Pain x6 weeks despite PT, no better. Exam: tender lumbar paraspinals."


def test_the_verifier_finding_a_missing_fact_fails_the_note() -> None:
    note = NOTE + " Pain is 7 of 10 today."
    answers = {"F1": "Pain x6 weeks despite PT, no better.", "F2": "Pain is 7 of 10 today."}
    result = check_note(minimal_sheet(), note, None, answers, {"F2": "Pain is 7 of 10 today."})
    assert any("verifier found the missing fact" in f for f in result.failures)


def test_a_documented_fact_the_verifier_cannot_find_fails_the_note() -> None:
    result = check_note(minimal_sheet(), NOTE, None, {"F1": None, "F2": None})
    assert any("F1: documented fact not found" in f for f in result.failures)


def test_a_quote_without_the_facts_values_fails_the_note() -> None:
    result = check_note(
        minimal_sheet(), NOTE, None, {"F1": "Exam: tender lumbar paraspinals.", "F2": None}
    )
    assert any("lacks the values" in f for f in result.failures)


def test_a_quote_not_in_the_note_fails_it() -> None:
    result = check_note(
        minimal_sheet(), NOTE, None, {"F1": "Pain for 6 weeks despite PT.", "F2": None}
    )
    assert any("not in the note" in f for f in result.failures)


def test_a_missing_fact_written_in_the_note_fails_it_without_the_verifier() -> None:
    note = NOTE + " The patient rates pain 7/10 on a numeric scale today."
    result = check_note(minimal_sheet(), note, None, None)
    assert result.verifier_pending
    assert any("missing fact appears" in f for f in result.failures)


def test_an_outcome_word_fails_the_note() -> None:
    note = NOTE + " Denies fever."
    result = check_note(
        minimal_sheet(), note, None, {"F1": "Pain x6 weeks despite PT, no better.", "F2": None}
    )
    assert any(f.startswith("leakage") for f in result.failures)


def test_near_duplicates_across_splits_are_found() -> None:
    base = " ".join(f"word{i}" for i in range(80))
    found = near_duplicates(
        {"train": {"a": base}, "test": {"b": base + " extra", "c": "something else entirely here"}}
    )
    assert [(a, b) for a, b, _ in found] == [("a", "b")]


# --- Visit limits (D-V3-8) and coverage cells (D-V3-6) --------------------------------------------


def therapy_claim(days: list[str], member: str = "MBR-1") -> tuple[dict, dict]:
    claim = {
        "member_id": member,
        "service_lines": [
            {"line_no": i, "date_of_service": day, "procedure_code": "97110"}
            for i, day in enumerate(days, start=1)
        ],
    }
    rules = {"line_outcomes": [{"line_no": i, "outcome": "PASS"} for i in range(1, len(days) + 1)]}
    return claim, rules


def test_a_line_beyond_the_visit_limit_is_found_as_rule_r21_counts_it() -> None:
    from datetime import date

    from app.db.curated import load_curated
    from training.generate.v3.visits import over_limit_lines

    curated = load_curated("v2")
    plan = "PLN-HMO"  # REHAB_THERAPY: 20 visits a year
    limit = curated.benefit(plan, "REHAB_THERAPY").visit_limit
    claim, rules = therapy_claim(["2026-10-05", "2026-10-12", "2026-10-12"])
    usage = {("MBR-1", "REHAB_THERAPY", date(2026, 1, 1)): limit - 1}

    assert over_limit_lines(claim, rules, {"MBR-1": plan}, usage, curated) == [2, 3]
    assert over_limit_lines(claim, rules, {"MBR-1": plan}, {}, curated) == []
    rules["line_outcomes"][0]["outcome"] = "DENY"  # a denied date uses no visit
    assert over_limit_lines(claim, rules, {"MBR-1": plan}, usage, curated) == []
    january, _ = therapy_claim(["2027-01-11"])
    assert over_limit_lines(january, rules, {"MBR-1": plan}, usage, curated) == []


def test_a_fact_counts_only_on_a_line_the_model_decides() -> None:
    from training.generate.v3.coverage import sheet_cells

    sheet = {
        "inputs": {
            "context": {
                "lines": [{"line_no": 1, "criteria": [{"criterion_id": "POL-PAIN-001.c8"}]}]
            }
        },
        "label": {
            "target": {
                "lines": [
                    {
                        "line_no": 1,
                        "decision": "DENY",
                        "criteria": [{"criterion_id": "POL-PAIN-001.c8", "status": "NOT_MET"}],
                    }
                ]
            }
        },
        "facts": [
            {"kind": "criterion", "criterion_id": "POL-PAIN-001.c8", "status": "borderline_below",
             "lines": [1]},
            {"kind": "criterion", "criterion_id": "POL-SURG-002.c3", "status": "borderline_above",
             "lines": [2]},  # a line a rule denies: shown as decided, teaches no label
        ],
    }  # fmt: skip

    assert sheet_cells(sheet) == {
        ("policy_decision", "POL-PAIN-001 DENY"): 1,
        ("criterion_status", "POL-PAIN-001.c8 NOT_MET"): 1,
        ("tricky", "POL-PAIN-001 borderline"): 1,
        ("borderline", "POL-PAIN-001.c8 below"): 1,
    }
