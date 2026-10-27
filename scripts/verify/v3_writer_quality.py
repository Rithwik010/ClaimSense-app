"""How the model writers' notes (B and C) follow their prompt (training/generate/v3/llm.py), from
data/generated/v3/notes.jsonl, sheets.jsonl and gate.jsonl. Report only.

Per writer:

- length: words against the style card's target, and the share inside the prompt's band (85% to
  115% of the target) and under it;
- echo: notes that copy the request's own wording ("Background to work into", "current
  medicines:", "[Exam]", ...);
- empty sections: lines saying only that there is nothing to report ("No relevant admissions");
- corrections: for each contradicted fact whose quotes the gate found, whether the correction comes
  in a later paragraph than the copied statement, and under an Assessment heading;
- the gate: passed, failed and pending notes.

    uv run python -m scripts.verify.v3_writer_quality [--out data/generated/v3/writer_quality.json]
"""

import argparse
import json
import re
import statistics
from collections import Counter
from pathlib import Path
from typing import Any

from training.generate.v3.config import OUT_DIR
from training.generate.v3.dataset import latest, load_sheets, read_jsonl

ECHO = re.compile(
    r"Background to work into|unrelated to the reason for the visit|current medicines:|"
    r"a resolved problem from the past|in the Assessment, these diagnoses|routine lines|"
    r"\[(Exam|History|Results|Assessment|Plan|History of present illness)[^\]]*\]|"
    r"must state each of these facts|hedged, unconfirmed possibility",
    re.IGNORECASE,
)
EMPTY = re.compile(
    r"^\W*(\w[\w /&]{0,30}:)?\s*(no relevant|none reported|nothing to report|not applicable|"
    r"no pertinent|n/?a)\b[^.\n]{0,40}\.?\s*$",
    re.IGNORECASE | re.MULTILINE,
)
ASSESSMENT = re.compile(r"^\W*(assessment|impression|a/p|a:|assessment and plan)", re.I | re.M)


def correction_placement(note: str, spans: dict[str, list[int]], fact_id: str) -> dict[str, bool]:
    start_copy, _ = spans[f"{fact_id}:original"]
    start_fix, _ = spans[fact_id]
    between = note[start_copy:start_fix]
    headings = list(ASSESSMENT.finditer(note[:start_fix]))
    return {
        "after": start_fix > start_copy,
        "later_paragraph": "\n\n" in between
        or bool(re.search(r"\n\s*[A-Z][A-Za-z /]{2,30}:", between)),
        "under_assessment": bool(headings) and headings[-1].start() > start_copy,
    }


def writer_quality(out_dir: Path = OUT_DIR) -> dict[str, Any]:
    sheets = load_sheets(out_dir)
    notes = latest(read_jsonl(out_dir / "notes.jsonl"))
    gate = {g["sheet_id"]: g for g in read_jsonl(out_dir / "gate.jsonl")}
    found: dict[str, Any] = {}
    for writer in ("B", "C"):
        rows = [(sid, n) for sid, n in notes.items() if n["writer"] == writer]
        if not rows:
            continue
        ratios, words = [], []
        echo = empty = 0
        placements: Counter[str] = Counter()
        status: Counter[str] = Counter()
        for sheet_id, note in rows:
            text = note["note"]
            target = sheets[sheet_id]["style"]["target_words"]
            n = len(text.split())
            words.append(n)
            ratios.append(n / target)
            echo += bool(ECHO.search(text))
            empty += bool(EMPTY.search(text))
            result = gate.get(sheet_id)
            if result is None or result["attempt"] != note["attempt"]:
                status["not gated"] += 1
                continue
            status[
                "pending" if result["pending"] else "passed" if result["passed"] else "failed"
            ] += 1
            for fact in sheets[sheet_id]["facts"]:
                spans = result.get("spans") or {}
                fid = fact["fact_id"]
                if fact["status"] == "contradicted" and fid in spans and f"{fid}:original" in spans:
                    for key, ok in correction_placement(text, spans, fid).items():
                        placements[f"{key} {'yes' if ok else 'no'}"] += 1
        found[writer] = {
            "notes": len(rows),
            "words_median": statistics.median(words),
            "target_ratio_median": round(statistics.median(ratios), 2),
            "inside_length_band": round(sum(0.85 <= r <= 1.15 for r in ratios) / len(rows), 3),
            "under_length_band": round(sum(r < 0.85 for r in ratios) / len(rows), 3),
            "echo_share": round(echo / len(rows), 3),
            "empty_section_share": round(empty / len(rows), 3),
            "corrections": dict(sorted(placements.items())),
            "gate": dict(status),
        }
    return found


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data", type=Path, default=OUT_DIR)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    report = writer_quality(args.data)
    print(json.dumps(report, indent=2))
    if args.out:
        args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
