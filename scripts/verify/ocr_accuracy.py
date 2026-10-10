"""P5.1: field accuracy of the scanned-form OCR (app/intake/ocr.py) against ground truth.

Claims come from the synthetic claims corpus (data/generated/claims/claims.jsonl). Each claim's
scan is rendered here with the form renderer (training/generate/forms.py: hand-filled values,
skew, blur, speckle, JPEG; value noise on 20% of forms) and given to the OCR as a two-page
image-only PDF, the way a scanned claim is uploaded. The first DEV_CLAIMS claims, under the
development seed, are the development set the OCR was tuned on. The held-out set is every other
claim under its own seed; the OCR's settings were fixed before each held-out run.

Ground truth is what the renderer wrote on each form (`ScanResult.values`, typos and blank boxes
included). A field is correct when the text read equals the text written (whitespace collapsed);
the target is 90% field accuracy over the boxes that hold a value (INSTRUCTIONS.md P5.1). Also
reported: blank boxes read as blank, accuracy by kind of field, how well the confidence flags the
wrong reads (threshold EXTRACTION_CONFIDENCE_MIN, 0.85), and the clinical notes (exact and
character similarity), which the target does not count.

    uv run python -m scripts.verify.ocr_accuracy [--set heldout|dev] [--limit N] [--workers 8]
"""

import argparse
import difflib
import io
import json
import random
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

from PIL import Image

from app.domain.contracts import IntakeClaim
from app.intake.field_formats import kind
from app.intake.form_codec import to_form_values
from app.intake.layout import ALL_PAGE_ONE_BOXES, NOTES_BOX, PRIMARY_PAID_BOXES
from app.intake.ocr import page_images, read_scan
from training.generate.forms import render_scan

ROOT = Path(__file__).resolve().parents[2]
CLAIMS = ROOT / "data" / "generated" / "claims"
OUT = ROOT / "data" / "generated" / "eval" / "ocr"
REPORT = ROOT / "docs" / "results-ocr.md"
DEV_CLAIMS = 25
DEV_SEED = "ocr-dev-20261010"
HELDOUT_SEED = "ocr-heldout-2-20261010"
# The first held-out run (seed ocr-heldout-20261010) came before three fixes the test fixture of
# tests/unit/test_ocr.py exposed (words far apart in a text box, the spacing of modifiers and
# primary payments, procedure-code positions); its result is kept in the report.
FIRST_HELDOUT = {"seed": "ocr-heldout-20261010", "field_accuracy": 0.9318, "fields": 5202}
THRESHOLD = 0.85
FIELDS = [box.field for box in ALL_PAGE_ONE_BOXES + PRIMARY_PAID_BOXES]


def records() -> list[dict[str, Any]]:
    lines = (CLAIMS / "claims.jsonl").read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line]


def scanned_pdf(pages: list[Image.Image]) -> bytes:
    """An image-only PDF of the scanned pages, as a scanner writes it."""
    buffer = io.BytesIO()
    first, *rest = [page.convert("L") for page in pages]
    first.save(buffer, format="PDF", save_all=True, append_images=rest, resolution=150)
    return buffer.getvalue()


def case(record: dict[str, Any], seed: str) -> dict[str, Any]:
    claim = IntakeClaim.model_validate(record["claim"])
    scan = render_scan(to_form_values(claim), random.Random(f"{seed}-{claim.claim_id}"))
    written, noise = scan.values, scan.noise
    pages = page_images(scanned_pdf(scan.pages))
    reads = read_scan(pages)
    fields = []
    for field in FIELDS:
        want = " ".join(written.get(field, "").split())
        read = reads.get(field)
        got = " ".join(read.text.split()) if read else ""
        fields.append(
            {
                "field": field,
                "kind": kind(field),
                "written": want,
                "read": got,
                "confidence": read.confidence if read else None,
                "correct": got == want,
            }
        )
    notes_want = " ".join(written.get("clinical_notes", "").split())
    notes = reads.get(NOTES_BOX.field)
    notes_got = " ".join(notes.text.split()) if notes else ""
    return {
        "claim_id": claim.claim_id,
        "value_noise": noise.get("value"),
        "skew_degrees": noise["visual"]["skew_degrees"],
        "fields": fields,
        "notes_exact": notes_got == notes_want,
        "notes_similarity": difflib.SequenceMatcher(None, notes_got, notes_want).ratio(),
    }


def summary(cases: list[dict[str, Any]]) -> dict[str, Any]:
    written = [f for c in cases for f in c["fields"] if f["written"]]
    blank = [f for c in cases for f in c["fields"] if not f["written"]]
    wrong = [f for f in written if not f["correct"]]
    right = [f for f in written if f["correct"]]
    by_kind: dict[str, list[int]] = {}
    for f in written:
        counts = by_kind.setdefault(f["kind"], [0, 0])
        counts[0] += f["correct"]
        counts[1] += 1

    def low(f: dict[str, Any]) -> bool:
        return f["confidence"] is None or f["confidence"] < THRESHOLD

    return {
        "claims": len(cases),
        "fields_written": len(written),
        "field_accuracy": round(len(right) / len(written), 4),
        "blank_boxes": len(blank),
        "blank_read_as_blank": round(sum(f["correct"] for f in blank) / len(blank), 4),
        "claims_all_fields_correct": sum(all(f["correct"] for f in c["fields"]) for c in cases),
        "wrong_reads_flagged_low": round(sum(map(low, wrong)) / len(wrong), 4) if wrong else None,
        "right_reads_at_or_above_threshold": round(sum(not low(f) for f in right) / len(right), 4),
        "by_kind": {k: round(c / n, 4) for k, (c, n) in sorted(by_kind.items())},
        "fields_per_kind": {k: n for k, (_, n) in sorted(by_kind.items())},
        "notes_exact": round(sum(c["notes_exact"] for c in cases) / len(cases), 4),
        "notes_similarity_mean": round(sum(c["notes_similarity"] for c in cases) / len(cases), 4),
        "most_missed_fields": Counter(f["field"] for f in wrong).most_common(10),
    }


def report(name: str, result: dict[str, Any]) -> str:
    r = result
    measures = "\n".join(
        f"| {name} | {value} |"
        for name, value in (
            (
                "Field accuracy (boxes with a value)",
                f"**{r['field_accuracy']:.4f}** ({r['fields_written']} fields)",
            ),
            ("Blank boxes read as blank", f"{r['blank_read_as_blank']:.4f} ({r['blank_boxes']})"),
            (
                "Claims with every field correct",
                f"{r['claims_all_fields_correct']} of {r['claims']}",
            ),
            (f"Wrong reads flagged below {THRESHOLD} confidence", r["wrong_reads_flagged_low"]),
            (
                f"Right reads at or above {THRESHOLD} confidence",
                f"{r['right_reads_at_or_above_threshold']:.4f}",
            ),
            ("Clinical notes read exactly", f"{r['notes_exact']:.4f}"),
            ("Clinical notes character similarity (mean)", f"{r['notes_similarity_mean']:.4f}"),
        )
    )
    rows = "\n".join(
        f"| {k} | {result['fields_per_kind'][k]} | {v:.4f} |" for k, v in result["by_kind"].items()
    )
    return f"""# OCR field accuracy ({name} set)

Generated by `scripts/verify/ocr_accuracy.py`; do not edit by hand. {result["claims"]} synthetic
claims, rendered with seed `{HELDOUT_SEED}` and read as image-only PDFs.
Target (P5.1): 90% field accuracy on the boxes that hold a value; clinical notes are not counted.

| Measure | Value |
|---|---|
{measures}

| Kind of field | Fields | Accuracy |
|---|---|---|
{rows}

Most missed fields: {", ".join(f"{f} ({n})" for f, n in result["most_missed_fields"]) or "none"}.

The first held-out run (seed `{FIRST_HELDOUT["seed"]}`), before three fixes found by the unit
test fixture (words far apart in a text box, the spacing of modifiers and primary payments,
procedure-code positions), gave {FIRST_HELDOUT["field_accuracy"]:.4f} on
{FIRST_HELDOUT["fields"]} fields. This run's seed was new, so its scans were not seen before.
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--set", choices=("heldout", "dev"), default="heldout")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    found = records()
    chosen = found[DEV_CLAIMS:] if args.set == "heldout" else found[:DEV_CLAIMS]
    if args.limit:
        chosen = chosen[: args.limit]
    heldout = args.set == "heldout"
    seed = HELDOUT_SEED if heldout else DEV_SEED
    with ProcessPoolExecutor(args.workers) as pool:
        cases = list(pool.map(case, chosen, [seed] * len(chosen)))
    result = summary(cases)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{args.set}.jsonl").write_text("".join(json.dumps(c) + "\n" for c in cases))
    (OUT / f"{args.set}_summary.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    if heldout and not args.limit:
        REPORT.write_text(report("held-out", result), encoding="utf-8")


if __name__ == "__main__":
    main()
