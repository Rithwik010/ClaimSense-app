"""Generator v3 on real fact sheets (needs data/raw for the code tables; skipped in CI).

- fact sheet -> label: the label recomputed from the facts with v2's derivation equals the target,
  borderline statuses follow the policy threshold, a correction decides a contradiction;
- writer A notes pass the gate, with every target quote an exact substring of the note;
- the gate catches planted faults: a missing fact written in, a documented fact taken out, an
  outcome word, a quote that lost its values;
- the claim form stays within contracts.py and the form's limits;
- distractor diagnoses are real ICD-10-CM FY2027 codes;
- writer prompts hold no patient names, and a Kaggle round passes the upload check.
"""

import random
from pathlib import Path

import pytest

from app.db import raw
from app.domain.contracts import SLMOutput
from training.generate.codebook import load_codebook
from training.generate.v3.config import borderline_met, borderlines, config, phrases
from training.generate.v3.dataset import build_sheets, latest, load_sheets, read_jsonl, write_a
from training.generate.v3.llm import statements, writer_messages
from training.generate.v3.verify import check_note, filled_target, label_problems

pytestmark = pytest.mark.skipif(not raw.raw_available(), reason="data/raw/ not present")


@pytest.fixture(scope="module")
def out(tmp_path_factory: pytest.TempPathFactory) -> Path:
    folder = tmp_path_factory.mktemp("v3")
    build_sheets(config()["seed"], folder, limit=24)
    write_a(folder)
    return folder


@pytest.fixture(scope="module")
def sheets(out: Path) -> dict:
    return load_sheets(out)


@pytest.fixture(scope="module")
def notes(out: Path) -> dict:
    return latest(read_jsonl(out / "notes.jsonl"))


def spans_of(note: dict) -> dict:
    return {k: tuple(v) for k, v in note["spans"].items()}


def no_findings(sheet: dict) -> dict:
    return {s["fact_id"]: None for s in statements(sheet)}


def test_sheets_per_split_and_writer(sheets: dict) -> None:
    splits = {s["split"] for s in sheets.values()}
    assert splits == {"train", "validation", "test_messy", "test_unseen_style", "handwritten"}
    writers = {(s["split"], s["writer"]) for s in sheets.values()}
    assert ("test_unseen_style", "C") in writers and ("handwritten", "H") in writers
    assert not {w for split, w in writers if split in ("train", "validation")} - {"A", "B"}


def test_the_label_recomputed_from_the_facts_is_the_target(sheets: dict, notes: dict) -> None:
    for sheet_id, note in notes.items():
        sheet = sheets[sheet_id]
        facts = {f["fact_id"]: f for f in sheet["facts"]}
        assert label_problems(sheet, spans_of(note), facts) == [], sheet_id


def test_every_target_criterion_has_a_fact(sheets: dict) -> None:
    for sheet in sheets.values():
        target = SLMOutput.model_validate(sheet["label"]["target"])
        have = {
            (n, f["criterion_id"])
            for f in sheet["facts"]
            if f["kind"] == "criterion"
            for n in f.get("lines") or []
        }
        for line in target.lines:
            for result in line.criteria:
                assert (line.line_no, result.criterion_id) in have, sheet["sheet_id"]


def test_borderline_statuses_follow_the_threshold(sheets: dict) -> None:
    table = borderlines()
    found = 0
    for sheet in sheets.values():
        for fact in sheet["facts"]:
            if not fact["status"].startswith("borderline"):
                continue
            found += 1
            info = fact["borderline"]
            borderline = table[info["criterion_id"]]
            form = next(
                f
                for f in borderline.forms
                if info["case"] in [dict(c) for c in (*f.above, *f.below)]
            )
            met = borderline_met(borderline, form, info["case"])
            assert met == (fact["status"] == "borderline_above")
            assert fact["label_status"] == ("MET" if met else "NOT_MET")
    assert found


def test_a_correction_comes_after_its_copied_statement(sheets: dict, notes: dict) -> None:
    checked = 0
    for sheet_id, note in notes.items():
        for fact in sheets[sheet_id]["facts"]:
            if fact["status"] == "contradicted":
                spans = note["spans"]
                assert spans[f"{fact['fact_id']}:original"][0] < spans[fact["fact_id"]][0]
                checked += 1
    assert checked


def test_writer_a_notes_pass_the_gate_with_exact_quotes(sheets: dict, notes: dict) -> None:
    for sheet_id, note in notes.items():
        sheet = sheets[sheet_id]
        result = check_note(sheet, note["note"], spans_of(note), no_findings(sheet))
        assert result.passed, (sheet_id, result.failures)
        target, problems = filled_target(sheet, note["note"], result.spans)
        assert problems == [] and target is not None
        for line in target.lines:
            for criterion in line.criteria:
                if criterion.status.value in ("MET", "NOT_MET"):
                    assert criterion.evidence in note["note"]


def first_with(sheets: dict, notes: dict, status: str) -> tuple[dict, dict, dict]:
    for sheet_id, note in notes.items():
        for fact in sheets[sheet_id]["facts"]:
            if fact["status"] == status and (fact.get("forbidden") or fact.get("text")):
                return sheets[sheet_id], note, fact
    raise AssertionError(f"no {status} fact in the sample")


def test_the_gate_catches_a_missing_fact_written_in(sheets: dict, notes: dict) -> None:
    sheet, note, fact = first_with(sheets, notes, "missing")
    planted = note["note"] + "\n" + fact["forbidden"][0].replace("{", "").replace("}", "")
    result = check_note(sheet, planted, spans_of(note), no_findings(sheet))
    assert any("missing fact appears" in f for f in result.failures)


def test_the_gate_catches_a_documented_fact_taken_out(sheets: dict, notes: dict) -> None:
    sheet, note, fact = first_with(sheets, notes, "documented")
    spans = {k: v for k, v in spans_of(note).items() if k != fact["fact_id"]}
    result = check_note(sheet, note["note"], spans, no_findings(sheet))
    assert any(f"{fact['fact_id']}: documented fact not found" in f for f in result.failures)


def test_the_gate_catches_an_outcome_word_and_a_quote_without_its_values(
    sheets: dict, notes: dict
) -> None:
    sheet, note, _ = first_with(sheets, notes, "documented")
    result = check_note(sheet, note["note"] + " Claim pended.", spans_of(note), no_findings(sheet))
    assert any(f.startswith("leakage") for f in result.failures)
    with_values = next(
        (s, n, f)
        for s, n in ((sheets[i], n) for i, n in notes.items())
        for f in s["facts"]
        if f.get("values") and f["fact_id"] in n["spans"] and f["status"] == "documented"
    )
    sheet, note, fact = with_values
    spans = spans_of(note)
    start, _ = spans[fact["fact_id"]]
    spans[fact["fact_id"]] = (start, start + 1)  # a quote cut short
    result = check_note(sheet, note["note"], spans, no_findings(sheet))
    assert any("lacks the values" in f or "shorter than" in f for f in result.failures)


def test_the_claim_form_stays_within_the_limits(sheets: dict) -> None:
    form = config()["claim_form"]
    lines_seen = set()
    for sheet in sheets.values():
        claim = sheet["inputs"]["claim"]
        lines_seen.add(len(claim["service_lines"]))
        assert len(claim["service_lines"]) <= form["max_lines"]
        assert len(claim["diagnoses"]) <= form["max_diagnoses"]
        for line in claim["service_lines"]:
            assert len(line["diagnosis_pointers"]) <= form["max_pointers_per_line"]
            assert len(line["modifiers"]) <= form["max_modifiers"]
    assert max(lines_seen) >= 3


def test_a_side_in_the_note_matches_the_side_of_the_diagnosis(sheets: dict) -> None:
    checked = 0
    for sheet in sheets.values():
        named = " ".join(d["description"].lower() for d in sheet["diagnoses"])
        sides = {s for s in ("right", "left") if s in named}
        if len(sides) != 1:
            continue
        for fact in sheet["facts"]:
            side = (fact.get("slots") or {}).get("side")
            if side:
                assert side[0].upper() == next(iter(sides))[0].upper(), sheet["sheet_id"]
                checked += 1
    assert checked


def test_distractor_diagnoses_are_real_codes() -> None:
    icd10 = set(load_codebook().icd10)
    codes = {c["code"] for c in phrases("sections")["conditions"]}
    assert codes - icd10 == set()


def test_writer_prompts_hold_no_patient_names(sheets: dict) -> None:
    for sheet in random.Random(1).sample(list(sheets.values()), 20):
        text = " ".join(m["content"] for m in writer_messages(sheet))
        patient = sheet["inputs"]["claim"]["patient"]
        assert patient["last_name"] not in text and patient["first_name"] not in text.split()


def test_a_kaggle_round_passes_the_upload_check(out: Path) -> None:
    from training.generate.v3.kaggle import prepare_round

    summary = prepare_round(1, limit=4, out_dir=out)
    assert summary["upload_check"] == "passed"
    assert summary["writer_jobs"]["B"] == 4 and summary["writer_jobs"]["C"] == 4
    assert summary["gpu_hours_estimate"]["total"] > 0
