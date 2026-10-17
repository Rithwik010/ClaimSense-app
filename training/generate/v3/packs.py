"""Check packs and the hand-written set (generator v3, Phase 5; SPEC.md). Synthetic data only.

- `check_packs/checklist_50.md`: 50 random notes, each with its fact sheet summary, labels and a
  checklist for the team (every documented fact stated, no missing fact, the label right, reads
  like a note).
- `check_packs/realism_20.md`: 20 other notes with no labels or facts, and a 1-to-5 realism rating
  each, for an optional rating by the sponsor contact.
- `handwritten/`: the 30 fact sheets as one-page briefs, the one-page writing guide, and an empty
  `notes/` folder for the notes (`<sheet_id>.txt`), which then go through the same gate.
"""

import json
import random
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from training.generate.v3.config import config

DISCLAIMER = (
    "Synthetic data only: every patient, provider, claim and note here is generated for the "
    "ClaimSense prototype."
)


def _sentence(texts: Mapping[str, str] | None) -> str:
    if not texts:
        return ""
    return texts.get("A") or next(iter(texts.values()))


def fact_lines(sheet: Mapping[str, Any]) -> list[str]:
    lines = []
    for fact in sheet["facts"]:
        label = fact.get("label_status") or "-"
        where = (fact.get("placement") or {}).get("section", "")
        what = fact.get("criterion_id") or fact["kind"]
        if fact["status"] in ("missing", "absent"):
            text = fact.get("missing_text") or ("not in play" if fact["status"] == "absent" else "")
        else:
            text = _sentence(fact.get("text"))
        extra = []
        if fact["status"] == "contradicted":
            extra.append(f"copied statement: {_sentence(fact.get('original'))}")
        if fact.get("hedge"):
            extra.append(f"hedged: {_sentence(fact['hedge'])}")
        if fact.get("negated"):
            extra.append(f"negative: {_sentence(fact['negated'])}")
        if fact.get("borderline"):
            b = fact["borderline"]
            extra.append(f"borderline {b['case']} vs {b['checks']}")
        suffix = f" ({'; '.join(extra)})" if extra else ""
        lines.append(
            f"- {fact['fact_id']} {what} [{fact['status']} -> {label}, {where}]: {text}{suffix}"
        )
    return lines


def check_packs(
    folder: Path,
    final: Mapping[str, Sequence[tuple[dict, dict]]],
    sheets: Mapping[str, Mapping[str, Any]],
) -> None:
    out = folder / "check_packs"
    out.mkdir(parents=True, exist_ok=True)
    rows = [(r, s) for split in final.values() for r, s in split]
    rng = random.Random(f"{config()['seed']}-packs")
    rng.shuffle(rows)
    checklist, realism = rows[:50], rows[50:70]
    parts = [
        "# v3 check pack: 50 notes with their facts and labels",
        "",
        DISCLAIMER,
        "",
        "For each note, tick what holds. Report anything wrong with the record ID.",
        "",
    ]
    for record, sidecar in checklist:
        meta = record["metadata"]
        sheet = sheets[meta["sheet_id"]]
        labels = ", ".join(
            f"line {x['line_no']} {x['decision']} ({x['source']})" for x in meta["line_labels"]
        )
        parts += [
            f"## {meta['record_id']} ({meta['split']}, writer {meta['writer']}, "
            f"{meta['scenario_type']}, {meta['note_words']} words)",
            "",
            f"Labels: {labels}; claim {meta['claim_decision']}; tricky: "
            f"{', '.join(meta['tricky']) or 'none'}.",
            "",
            "Facts:",
            *fact_lines(sheet),
            "",
            "```text",
            sidecar["claim"]["clinical_notes"],
            "```",
            "",
            "- [ ] every documented fact is stated, with its numbers and dates",
            "- [ ] no missing fact is stated or implied",
            "- [ ] the labels follow from the facts",
            "- [ ] it reads like a real clinic note",
            "",
        ]
    (out / "checklist_50.md").write_text("\n".join(parts), encoding="utf-8")
    parts = [
        "# v3 realism rating: 20 notes",
        "",
        DISCLAIMER,
        "",
        "Rate how much each note reads like a real outpatient note: 1 (clearly artificial) to 5 "
        "(could be real). A word on why helps. No clinical judgement is asked for.",
        "",
    ]
    for i, (record, sidecar) in enumerate(realism, start=1):
        parts += [
            f"## Note {i} ({record['metadata']['record_id']})",
            "",
            "```text",
            sidecar["claim"]["clinical_notes"],
            "```",
            "",
            "Rating (1-5): ____   Comment: ______________________________",
            "",
        ]
    (out / "realism_20.md").write_text("\n".join(parts), encoding="utf-8")
    (out / "packs.json").write_text(
        json.dumps(
            {
                "checklist": [r["metadata"]["record_id"] for r, _ in checklist],
                "realism": [r["metadata"]["record_id"] for r, _ in realism],
            },
            indent=2,
        )
    )


GUIDE = """# Writing guide: the v3 hand-written notes

{disclaimer}

You get {count} one-page briefs, one per claim. Write the clinic note for each, the way you
would write a real outpatient note, and save it as `notes/<sheet ID>.txt`. Every note goes
through the same checks as the generated ones, and the set is kept apart to test the model.

**Put in**
- Every fact under "State these", each in a sentence of its own, with its numbers and dates
  exactly as given. Reword everything else freely.
- A contradiction as described: first the old statement (as text copied from an earlier
  visit), later the correction, starting with the marker given.
- The hedged mentions as possibilities only, and the negatives as negatives.
- The distractors (history, medications, allergies, social history), anywhere they fit.

**Leave out**
- Anything about the topics under "Leave out", even in passing.
- These words, or any form of them: approve, deny (including "denies"), pend, pending,
  reject, covered, coverage, medically necessary. Write "no", "reports no" or "negative for".
- Names, phone numbers, addresses and any real person or place. Use the age and sex only.
- Codes for criteria or policies (POL-..., c4 and so on).

**Style**
Your own: sections, abbreviations and dictation-style sentences are all welcome. Aim for the
length given (150 to 900 words). One note per brief; don't copy text between notes.
"""


def handwritten_pack(folder: Path, sheets: Sequence[Mapping[str, Any]]) -> None:
    out = folder / "handwritten"
    (out / "notes").mkdir(parents=True, exist_ok=True)
    (out / "WRITING_GUIDE.md").write_text(
        GUIDE.format(disclaimer=DISCLAIMER, count=len(sheets)), encoding="utf-8"
    )
    for sheet in sheets:
        state, leave = [], []
        for fact in sheet["facts"]:
            if fact["status"] == "missing" and fact.get("missing_text"):
                leave.append(fact["missing_text"])
            elif fact.get("text") and fact["status"] != "absent":
                line = _sentence(fact["text"])
                if fact["status"] == "contradicted":
                    line = (
                        f"first, as copied from an earlier visit: {_sentence(fact['original'])} "
                        f'Later: "{fact["marker"]} {line}"'
                    )
                state.append(line)
            if fact.get("hedge"):
                state.append(f"(as a possibility only) {_sentence(fact['hedge'])}")
            if fact.get("negated"):
                state.append(f"(a negative) {_sentence(fact['negated'])}")
        dis = sheet["distractors"]
        patient = sheet["patient"]
        brief = [
            f"# {sheet['sheet_id']}",
            "",
            f"{sheet['clinic']['name']}, {sheet['clinic']['visit'].lower()} on "
            f"{sheet['visit_date']}. Patient: {patient['age']}-year-old {patient['sex_words'][0]}. "
            f"About {sheet['style']['target_words']} words.",
            "",
            "## State these",
            *[f"- {s}" for s in state],
            "",
            "## Leave out",
            *([f"- {x}" for x in leave] or ["- (nothing in particular)"]),
            "",
            "## Distractors",
            f"- History: {'; '.join(c['text'][0] for c in dis['conditions']) or 'none'}",
            f"- Medications: {'; '.join(m[0] for m in dis['medications']) or 'none'}",
            f"- Allergies: {dis['allergies'][0]}",
            f"- Social: {' '.join(s[0] for s in dis['social'])}",
            "",
            "## On the claim",
            "- Diagnoses: "
            + "; ".join(f"{d['description']} ({d['code']})" for d in sheet["diagnoses"]),
            f"- Plan: {'; '.join(sheet.get('procedures') or []) or 'office visit'}",
        ]
        (out / f"{sheet['sheet_id']}.md").write_text("\n".join(brief) + "\n", encoding="utf-8")
    (out / "sheets.jsonl").write_text(
        "".join(json.dumps(s, ensure_ascii=False) + "\n" for s in sheets), encoding="utf-8"
    )
