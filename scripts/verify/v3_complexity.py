"""How complex the training notes and claims are: decision data v1, v2 and v3 (the v3 pilot),
measured the same way, for the v3 report (training/generate/v3/SPEC.md).

Per dataset:

- **Notes:** length (words, sentences); sections; numbers and dates; negation words, hedged
  mentions, abbreviations, corrections and copy-forward blocks per note.
- **Variety:**
  - template reuse: the share of sentences that also appear, word for word, in five or more other
    notes;
  - distinct sentences;
  - vocabulary per 10,000 words;
  - near-duplicate notes: 5-word shingles, Jaccard 0.8 or more, on a sample.
- **Evidence share:** how much of a note is the evidence the target quotes (the rest is context
  the model must read past).
- **Claims:** lines, diagnoses, dates of service and modifiers.
- **Labels:** line decisions and the claim's complexity.

    uv run python -m scripts.verify.v3_complexity \\
        --v1 ../ClaimSense/data/generated/decision --v2 ../ClaimSense/data/generated/decision_v2 \\
        --v3 data/generated/v3/pilot [--out data/generated/v3/complexity.json]
"""

import argparse
import json
import random
import re
import statistics
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

from training.generate.v3.config import phrases

SENTENCE = re.compile(r"[^.!?;\n]+[.!?;]?")
WORD = re.compile(r"[A-Za-z][A-Za-z'/-]*")
NUMBER = re.compile(r"\b\d+(?:[./]\d+)*\b")
DATE = re.compile(r"\b\d{1,2}/\d{1,2}/\d{4}\b|\b\d{4}-\d{2}-\d{2}\b")
HEADER = re.compile(r"^\s*[A-Za-z][A-Za-z /&()-]{1,40}:\s*$|^[A-Z][A-Z /&()-]{2,40}:", re.MULTILINE)
NEGATION = re.compile(
    r"\b(no|not|without|never|none|negative|absent|neither|nor|cannot)\b|n't\b", re.I
)
HEDGE = re.compile(
    r"\b(possible|possibly|may|might|unclear|uncertain|unsure|suspected|rule out|r/o|wonders|"
    r"not sure|cannot say)\b|\?\w",
    re.I,
)
CORRECTION = re.compile(r"\b(Correction|Addendum|Update after chart review|Clarification):", re.I)
COPIED = re.compile(r"copied|carried forward|prior note \(", re.I)
SAMPLE = 400


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def _abbreviations() -> set[str]:
    return {short.lower() for _, short in phrases("abbreviations")["pairs"] if len(short) > 1}


def _quantiles(values: Sequence[float]) -> dict[str, float]:
    if not values:
        return {}
    ordered = sorted(values)
    return {
        "mean": round(statistics.fmean(ordered), 1),
        "median": ordered[len(ordered) // 2],
        "p90": ordered[int(0.9 * (len(ordered) - 1))],
        "max": ordered[-1],
    }


def shingles(text: str, size: int = 5) -> set[str]:
    words = [w.lower() for w in WORD.findall(text)]
    return {" ".join(words[i : i + size]) for i in range(max(0, len(words) - size + 1))}


def note_metrics(notes: Sequence[str]) -> dict[str, Any]:
    abbreviations = _abbreviations()
    sentences_per_note = [
        [s.strip() for s in SENTENCE.findall(n) if len(s.split()) >= 3] for n in notes
    ]
    per_100 = lambda pattern: _quantiles(  # noqa: E731
        [100 * len(pattern.findall(n)) / max(1, len(n.split())) for n in notes]
    )
    rng = random.Random(1)
    sample = rng.sample(list(notes), min(SAMPLE, len(notes)))
    grams = [shingles(n) for n in sample]
    near = 0
    for i, a in enumerate(grams):
        for j, b in enumerate(grams):
            if i != j and a and b and len(a & b) / len(a | b) >= 0.8:
                near += 1
                break
    return {
        "notes": len(notes),
        "words": _quantiles([len(n.split()) for n in notes]),
        "sentences": _quantiles([len(s) for s in sentences_per_note]),
        "sections_per_note": _quantiles([len(HEADER.findall(n)) for n in notes]),
        "numbers_per_note": _quantiles([len(NUMBER.findall(n)) for n in notes]),
        "dates_per_note": _quantiles([len(DATE.findall(n)) for n in notes]),
        "negations_per_100_words": per_100(NEGATION),
        "hedges_per_note": _quantiles([len(HEDGE.findall(n)) for n in notes]),
        "abbreviations_per_100_words": _quantiles(
            [
                100 * sum(w.lower() in abbreviations for w in n.split()) / max(1, len(n.split()))
                for n in notes
            ]
        ),
        "notes_with_a_correction": round(
            sum(bool(CORRECTION.search(n)) for n in notes) / len(notes), 3
        ),
        "notes_with_copied_text": round(sum(bool(COPIED.search(n)) for n in notes) / len(notes), 3),
        **variety(notes),
        "near_duplicate_share": round(near / max(1, len(sample)), 3),
    }


EQUAL_SAMPLE = 24  # notes per draw: the smallest v3 pilot set, so every dataset is measured alike
DRAWS = 20


def variety(notes: Sequence[str]) -> dict[str, float]:
    """Sentence reuse and vocabulary on equal samples (EQUAL_SAMPLE notes, DRAWS draws), since
    both change with how many notes are counted."""
    rng = random.Random(7)
    reuse, distinct, vocab = [], [], []
    for _ in range(DRAWS):
        sample = rng.sample(list(notes), min(EQUAL_SAMPLE, len(notes)))
        per_note = [{s.strip() for s in SENTENCE.findall(n) if len(s.split()) >= 3} for n in sample]
        counts = Counter(s for sentences in per_note for s in sentences)
        total = sum(len(x) for x in per_note) or 1
        reuse.append(sum(1 for x in per_note for s in x if counts[s] >= 3) / total)
        distinct.append(len(counts) / total)
        words = [w.lower() for n in sample for w in WORD.findall(n)][:2000]
        vocab.append(len(set(words)))
    return {
        "template_reuse_in_24_notes": round(statistics.fmean(reuse), 3),
        "distinct_sentences_in_24_notes": round(statistics.fmean(distinct), 3),
        "distinct_words_in_2000_words": round(statistics.fmean(vocab), 1),
    }


def evidence_share(note: str, target: Mapping[str, Any]) -> float:
    quotes = {
        c["evidence"]
        for line in target.get("lines", [])
        for c in line.get("criteria", [])
        if c.get("status") in ("MET", "NOT_MET") and c.get("evidence") in note
    }
    return sum(len(q) for q in quotes) / max(1, len(note))


def claim_metrics(
    claims: Sequence[Mapping[str, Any]], targets: Sequence[Mapping[str, Any]]
) -> dict:
    lines = [len(c["service_lines"]) for c in claims]
    return {
        "lines_per_claim": dict(sorted(Counter(lines).items())),
        "lines_mean": round(statistics.fmean(lines), 2),
        "diagnoses_per_claim": _quantiles([len(c["diagnoses"]) for c in claims]),
        "dates_per_claim": _quantiles(
            [len({line["date_of_service"] for line in c["service_lines"]}) for c in claims]
        ),
        "modifiers_per_claim": _quantiles(
            [sum(len(line["modifiers"]) for line in c["service_lines"]) for c in claims]
        ),
        "evidence_share_of_note": _quantiles(
            [
                round(evidence_share(c["clinical_notes"], t), 3)
                for c, t in zip(claims, targets, strict=True)
            ]
        ),
        "line_decisions": dict(
            Counter(line["decision"] for t in targets for line in t.get("lines", []))
        ),
        "complexity": dict(Counter(t.get("complexity") for t in targets)),
    }


def decision_dataset(folder: Path) -> dict[str, Any]:
    inputs: list[dict[str, Any]] = []
    for split in ("train", "validation", "test"):
        inputs += read_jsonl(folder / f"{split}_inputs.jsonl")
    claims = [i["claim"] for i in inputs]
    targets = [i["target"] for i in inputs]
    return {
        "source": str(folder),
        "notes_measured": note_metrics([c["clinical_notes"] for c in claims]),
        "claims": claim_metrics(claims, targets),
    }


def v3_pilot(folder: Path) -> dict[str, Any]:
    sheets = {s["sheet_id"]: s for s in read_jsonl(folder / "sheets.jsonl")}
    notes = read_jsonl(folder / "notes.jsonl")
    by_writer: dict[str, list[tuple[str, dict]]] = {}
    shares: dict[str, list[float]] = {}
    for row in notes:
        by_writer.setdefault(row["writer"], []).append((row["note"], sheets[row["sheet_id"]]))
        spans = [v for k, v in (row.get("spans") or {}).items() if ":" not in k]
        if row.get("spans") is not None:
            shares.setdefault(row["writer"], []).append(
                round(sum(end - start for start, end in spans) / max(1, len(row["note"])), 3)
            )
    out_dir = folder / "kaggle"
    for path in sorted(out_dir.glob("round*/output/output/notes_out.jsonl")):
        for row in read_jsonl(path):
            by_writer.setdefault(row["writer"] + " (unverified)", []).append(
                (row["text"], sheets[row["sheet_id"]])
            )
    found: dict[str, Any] = {"source": str(folder), "writers": {}}
    for writer, rows in sorted(by_writer.items()):
        claims = [s["inputs"]["claim"] | {"clinical_notes": n} for n, s in rows]
        targets = [s["label"]["target"] for _, s in rows]
        found["writers"][writer] = {
            "notes_measured": note_metrics([n for n, _ in rows]),
            "claims": claim_metrics(claims, targets),
            "tricky": dict(Counter(t for _, s in rows for t in s["tricky"])),
        }
        if writer in shares:  # v3 targets hold placeholders: the share comes from the spans
            found["writers"][writer]["claims"]["evidence_share_of_note"] = _quantiles(
                shares[writer]
            )
    all_sheets = list(sheets.values())
    found["all_sheets"] = {
        "sheets": len(all_sheets),
        "claims": claim_metrics(
            [s["inputs"]["claim"] for s in all_sheets], [s["label"]["target"] for s in all_sheets]
        ),
        "tricky": dict(Counter(t for s in all_sheets for t in s["tricky"])),
        "fact_statuses": dict(Counter(f["status"] for s in all_sheets for f in s["facts"])),
    }
    return found


def main(argv: Iterable[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--v1", type=Path, required=True)
    parser.add_argument("--v2", type=Path, required=True)
    parser.add_argument("--v3", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(list(argv) if argv is not None else None)
    report = {
        "v1": decision_dataset(args.v1),
        "v2": decision_dataset(args.v2),
        "v3_pilot": v3_pilot(args.v3),
    }
    text = json.dumps(report, indent=2)
    if args.out:
        args.out.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
