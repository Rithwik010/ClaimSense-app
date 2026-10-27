"""Is the v3 gate filtering out the mess? (team check before round 4, 19 Oct). Report only.

From data/generated/v3/ (sheets.jsonl, notes.jsonl, gate.jsonl, verifier.jsonl):

1. Failure reasons, by writer, of each sheet's latest gated note: missing fact (a documented fact
   not found, its quote not in the note or too short), leaked fact (a missing or absent fact found
   by the local check or by the verifier), number mismatch (a quote without the fact's values),
   outcome word, label mismatch (the label recomputed from the verified facts differs, the
   correction before the copied statement, the target invalid), verifier error (unreadable).
2. Passed against failed and against what the fact sheets asked for, by writer: tricky-fact types
   (borderline, contradiction, hedged mention, negated exclusion, copy-forward), note length and
   abbreviation rate. A ratio under 1 means the passing notes hold less of it than asked.
3. A seeded sample of failed notes (20 of writer B, 20 of writer C) written out for a hand check:
   hand_check.md, with each failure, the fact sheet's statement, the verifier's answer and the note.
4. Sheets dropped after every attempt, by tricky-fact type and by policy.
5. The coverage cells (training/generate/v3/coverage.py) on the training sheets whose note passed,
   against the floors.
6. Visit limits: every sheet checked again (training/generate/v3/visits.py).

    uv run python -m scripts.verify.v3_gate_analysis [--out data/generated/v3/gate_analysis.json]
"""

import argparse
import json
import random
import re
import statistics
from collections import Counter
from pathlib import Path
from typing import Any

from app.db.curated import load_curated
from training.generate.common import DEFAULT_SEED
from training.generate.reference import generate_reference
from training.generate.scenarios_v2 import reference_dicts
from training.generate.v3.config import OUT_DIR, config, phrases
from training.generate.v3.coverage import below, cell_counts, policy_of
from training.generate.v3.dataset import latest, load_sheets, read_jsonl
from training.generate.v3.llm import statements
from training.generate.v3.visits import over_limit_lines, usage_index

CATEGORIES = (
    ("verifier error", re.compile(r"verifier answer unreadable")),
    ("outcome word", re.compile(r"^leakage")),
    ("number mismatch", re.compile(r"lacks the values")),
    ("leaked fact", re.compile(r"(missing|absent) fact appears|the verifier found the")),
    (
        "missing fact",
        re.compile(r"documented fact not found|quote is not in the note|shorter than"),
    ),
    (
        "label mismatch",
        re.compile(
            r"recomputed|not verified|no fact for|comes before the copied|placeholder|"
            r"target invalid|evidence guard|quote not in the note"
        ),
    ),
)
TRICKY = {
    "borderline": "borderline",
    "contradiction": "contradiction",
    "uncertainty": "hedged mention",
    "negation": "negated exclusion",
}
WORD = re.compile(r"[A-Za-z][A-Za-z'/&+-]*")


SENTENCE = re.compile(r"[^.!?\n]+[.!?]?")


def closest(note: str, statement: str, k: int = 2) -> list[tuple[float, str]]:
    """The note's sentences sharing the most of the statement's words (for the hand check)."""
    wanted = {w.lower() for w in WORD.findall(statement)} | set(re.findall(r"\d+", statement))
    if not wanted:
        return []
    scored = []
    for match in SENTENCE.finditer(note):
        text = match.group(0).strip()
        words = {w.lower() for w in WORD.findall(text)} | set(re.findall(r"\d+", text))
        if words:
            scored.append((len(wanted & words) / len(wanted), text[:240]))
    return sorted(scored, reverse=True)[:k]


def category(failure: str) -> str:
    return next((name for name, pattern in CATEGORIES if pattern.search(failure)), "other")


def features(sheet: dict[str, Any], row: dict[str, Any], shorts: set[str]) -> dict[str, float]:
    note = row
    words = row["note"].split()
    found = {label: float(tag in sheet["tricky"]) for tag, label in TRICKY.items()}
    found["copy-forward"] = float(bool(sheet["style"].get("copy_forward")))
    found["history (past episode)"] = float(bool(sheet["distractors"].get("past")))
    habit = sheet["style"].get("habit")
    found["terse abbreviated style"] = float(habit == "terse_abbreviated")
    found["dictated style"] = float(habit == "dictated")
    found["noise edits (writer A)"] = float(sum((note.get("noise") or {}).values()))
    found["words"] = float(len(words))
    found["abbreviations per 100 words"] = (
        100 * sum(w.lower().strip(".,;:()") in shorts for w in words) / max(1, len(words))
    )
    return found


def compare(rows: list[tuple[dict, dict, str]], shorts: set[str]) -> dict[str, Any]:
    """Shares (and medians for length and abbreviations) asked, passed and failed."""
    asked = [features(s, n, shorts) for s, n, _ in rows]
    passed = [features(s, n, shorts) for s, n, st in rows if st == "passed"]
    failed = [features(s, n, shorts) for s, n, st in rows if st == "failed"]
    out: dict[str, Any] = {}
    for key in asked[0] if asked else []:

        def summary(values: list[dict[str, float]], key: str = key) -> float:
            numbers = [v[key] for v in values]
            if not numbers:
                return 0.0
            if key in ("words", "abbreviations per 100 words", "noise edits (writer A)"):
                return round(statistics.median(numbers), 2)
            return round(sum(numbers) / len(numbers), 3)

        a, p, f = summary(asked), summary(passed), summary(failed)
        out[key] = {
            "asked": a,
            "passed": p,
            "failed": f,
            "passed_to_asked": round(p / a, 2) if a else None,
        }
    return out


def gate_analysis(out_dir: Path = OUT_DIR) -> dict[str, Any]:
    sheets = load_sheets(out_dir)
    notes = latest(read_jsonl(out_dir / "notes.jsonl"))
    gate = {g["sheet_id"]: g for g in read_jsonl(out_dir / "gate.jsonl")}
    verifier = {(v["sheet_id"], v["attempt"]): v for v in read_jsonl(out_dir / "verifier.jsonl")}
    limit = config()["verification"]["max_regenerations"] + 1
    shorts = {short.lower() for _, short in phrases("abbreviations")["pairs"] if len(short) > 1}
    report: dict[str, Any] = {}

    rows: dict[str, list[tuple[dict, dict, str]]] = {}
    reasons: dict[str, Counter[str]] = {}
    notes_by_reason: dict[str, Counter[str]] = {}
    for sheet_id, note in notes.items():
        result = gate.get(sheet_id)
        if result is None or result["attempt"] != note["attempt"] or result["pending"]:
            continue
        writer = note["writer"]
        state = "passed" if result["passed"] else "failed"
        rows.setdefault(writer, []).append((sheets[sheet_id], note, state))
        kinds = [category(f) for f in result["failures"]]
        reasons.setdefault(writer, Counter()).update(kinds)
        notes_by_reason.setdefault(writer, Counter()).update(set(kinds))
    report["1_failure_reasons"] = {
        w: {
            "notes_gated": len(rows[w]),
            "notes_failed": sum(st == "failed" for *_, st in rows[w]),
            "notes_with_reason": dict(notes_by_reason.get(w, Counter()).most_common()),
            "failures": dict(reasons.get(w, Counter()).most_common()),
        }
        for w in sorted(rows)
    }
    report["2_passed_vs_failed"] = {w: compare(rows[w], shorts) for w in sorted(rows)}

    rng = random.Random(20261019)
    picks = []
    for writer in ("B", "C"):
        failed = sorted(
            (s["sheet_id"] for s, _, st in rows.get(writer, []) if st == "failed"),
        )
        picks += rng.sample(failed, min(20, len(failed)))
    lines = ["# Hand check: failed notes (writers B and C)", "", "Synthetic data only.", ""]
    for sheet_id in picks:
        sheet, note, result = sheets[sheet_id], notes[sheet_id], gate[sheet_id]
        answers = (verifier.get((sheet_id, note["attempt"])) or {}).get("answers") or {}
        listed = {s["fact_id"]: s for s in statements(sheet)}
        lines += [f"## {sheet_id} (writer {note['writer']}, attempt {note['attempt']})", ""]
        for failure in result["failures"]:
            fid = (
                failure.split(":")[0]
                if ":original" not in failure
                else ":".join(failure.split(":")[:2])
            )
            item = listed.get(fid) or listed.get(fid.split(":")[0]) or {}
            lines += [
                f"- {failure}",
                f"  - statement ({item.get('expect', '?')}): {item.get('statement', '-')}",
                f"  - verifier: {answers.get(fid)!r}",
            ]
            for score, sentence in closest(note["note"], item.get("statement") or ""):
                lines.append(f"  - closest in the note ({score:.2f}): {sentence}")
        lines += [
            "",
            f"<details><summary>note ({len(note['note'].split())} words)</summary>",
            "",
            "```text",
            note["note"],
            "```",
            "</details>",
            "",
        ]
    (out_dir / "hand_check.md").write_text("\n".join(lines), encoding="utf-8")
    report["3_hand_check_sample"] = picks

    dropped = [
        sheets[sid]
        for sid, note in notes.items()
        if note["attempt"] >= limit
        and (g := gate.get(sid))
        and g["attempt"] == note["attempt"]
        and not g["passed"]
        and not g["pending"]
    ]
    report["4_dropped_after_all_attempts"] = {
        "sheets": len(dropped),
        "by_writer": dict(Counter(s["writer"] for s in dropped)),
        "by_split": dict(Counter(s["split"] for s in dropped)),
        "by_tricky_type": dict(Counter(TRICKY[t] for s in dropped for t in s["tricky"])),
        "by_policy": dict(Counter(p for s in dropped for p in s["policy_ids"]).most_common()),
    }

    passed_train = [
        sheets[sid]
        for sid, g in gate.items()
        if g["passed"]
        and sheets[sid]["split"] == "train"
        and notes.get(sid, {}).get("attempt") == g["attempt"]
    ]
    floors = config()["top_up"]["floors"]
    counts = cell_counts(passed_train)
    for cell in cell_counts(s for s in sheets.values() if s["split"] == "train"):
        counts.setdefault(cell, 0)
    short = below(counts, floors)
    report["5_coverage_on_passed_training_notes"] = {
        "passed_training_sheets": len(passed_train),
        "by_writer": dict(Counter(s["writer"] for s in passed_train)),
        "cells": len(counts),
        "cells_under_floor": {f"{k} {n}": counts[(k, n)] for (k, n) in short},
        "policies_of_short_cells": sorted({policy_of(n.split()[0]) for _, n in short}),
    }

    reference = generate_reference(DEFAULT_SEED)[0]
    plan_of = {m["member_id"]: m["plan_id"] for m in reference.members}
    usage = usage_index(reference_dicts(reference.visit_usage))
    curated = load_curated(config()["policy_set"])
    over = [
        s["sheet_id"]
        for s in sheets.values()
        if over_limit_lines(
            s["inputs"]["claim"], s["inputs"]["rules_outcome"], plan_of, usage, curated
        )
    ]
    report["6_visit_limits"] = {"sheets_checked": len(sheets), "sheets_over_a_limit": len(over)}
    return report


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data", type=Path, default=OUT_DIR)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    report = gate_analysis(args.data)
    print(json.dumps(report, indent=2))
    if args.out:
        args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
