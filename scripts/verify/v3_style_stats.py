"""Style statistics of v3 notes (D-V3-15, D-V3-16). Report only.

For a group of notes:

- words per note (mean and median);
- abbreviations per 100 words: words that are one of the writers' short forms
  (phrases/abbreviations.yaml, two characters or more, any case);
- fragments: the share of sentences (split at . ; ! ? and line ends) of 6 words or fewer;
- headings per note: lines ending in a colon, or written in capitals.

Two comparisons:

- `writer-d`: the LLM-written human-style test set's first pass (every attempt-1 note) against
  its final set (the latest note of each sheet that passes the gate): the style must not drift
  as notes are rewritten to pass; and the final set as built into the dataset (with the noise
  layer's misspellings, data/generated/v3/final/test_human_style_inputs.jsonl);
- `writer-b`: writer B's latest notes that pass the gate against those it rejects (training,
  validation and the messy test): is the strict gate mostly rejecting the messiest notes?

    uv run python -m scripts.verify.v3_style_stats writer-d | writer-b
"""

import argparse
import json
import re
import statistics
from typing import Any

from training.generate.v3.config import OUT_DIR, phrases
from training.generate.v3.dataset import latest, load_sheets, read_jsonl

SENTENCE = re.compile(r"[^.;!?\n]+")
WORD = re.compile(r"[A-Za-z0-9][A-Za-z0-9/&'+.-]*")


def shorts() -> set[str]:
    return {short.lower() for _, short in phrases("abbreviations")["pairs"] if len(short) > 1}


def stats(texts: list[str]) -> dict[str, Any]:
    if not texts:
        return {"notes": 0}
    short = shorts()
    words = [len(t.split()) for t in texts]
    abbreviated = [
        100 * sum(w.lower().strip(".,;:()") in short for w in t.split()) / max(1, len(t.split()))
        for t in texts
    ]
    pieces = [len(WORD.findall(s)) for t in texts for s in SENTENCE.findall(t) if WORD.search(s)]
    headings = [
        sum(
            1
            for line in t.splitlines()
            if line.strip() and (line.strip().endswith(":") or line.strip().isupper())
        )
        for t in texts
    ]
    return {
        "notes": len(texts),
        "words_mean": round(statistics.mean(words), 1),
        "words_median": statistics.median(words),
        "abbreviations_per_100_words": round(statistics.mean(abbreviated), 2),
        "fragment_share": round(sum(n <= 6 for n in pieces) / len(pieces), 3),
        "headings_per_note": round(statistics.mean(headings), 2),
    }


def writer_d() -> dict[str, Any]:
    sheets = load_sheets(OUT_DIR)
    rows = read_jsonl(OUT_DIR / "notes.jsonl")
    gate = {g["sheet_id"]: g for g in read_jsonl(OUT_DIR / "gate.jsonl")}
    first = [r["note"] for r in rows if r["writer"] == "D" and r["attempt"] == 1]
    final = [
        n["note"]
        for sid, n in latest(rows).items()
        if n["writer"] == "D"
        and sheets[sid]["split"] == "test_human_style"
        and (g := gate.get(sid))
        and g["passed"]
        and g["attempt"] == n["attempt"]
    ]
    built = OUT_DIR / "final" / "test_human_style_inputs.jsonl"  # with the noise layer
    as_built = [i["claim"]["clinical_notes"] for i in read_jsonl(built)] if built.exists() else []
    return {"first_pass": stats(first), "final_set": stats(final), "as_built": stats(as_built)}


def writer_b() -> dict[str, Any]:
    gate = {g["sheet_id"]: g for g in read_jsonl(OUT_DIR / "gate.jsonl")}
    passing, rejected = [], []
    for sid, n in latest(read_jsonl(OUT_DIR / "notes.jsonl")).items():
        g = gate.get(sid)
        if n["writer"] != "B" or not g or g["attempt"] != n["attempt"] or g["pending"]:
            continue
        (passing if g["passed"] else rejected).append(n["note"])
    return {"passing": stats(passing), "rejected": stats(rejected)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("which", choices=("writer-d", "writer-b"))
    args = parser.parse_args()
    report = writer_d() if args.which == "writer-d" else writer_b()
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
