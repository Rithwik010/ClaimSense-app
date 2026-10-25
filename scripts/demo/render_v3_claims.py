"""100 v3 claims rendered as documents, as a provider uploads them (the team's request, 25 Oct).

Each claim is rendered whole on the ClaimSense form (training/generate/forms.py): page 1 the claim,
page 2 its attachments, and as many further attachment pages as its notes need (`continued=True`;
nothing is cut, however long the notes). The point is to check ClaimSense on long, complex claims,
so the claims are not chosen to fit two pages (notes stuck in a loop are left out:
scripts/verify/v3_repetition.py): from each of validation, the messy test, the
unseen-style test and the LLM-written human-style test set (all four note writers), the
`LONGEST_PER_SET` with the longest notes and `PER_SET` - `LONGEST_PER_SET` more drawn with a fixed
seed. The formats rotate:

- `digital-pdf/<record>.pdf`: typed, with a text layer;
- `scanned-pdf/<record>.pdf`: hand-filled and scanned (skew, blur, speckle, JPEG), image only;
- `png/<record>/page-<n>.png`: the same scanned pages, one PNG per page.

The claim fields are written exactly (no value noise), so the expected intake result is the record's
own claim (`<split>_inputs.jsonl`). Writes data/generated/v3/rendered/ (not committed: synthetic
claims with CPT codes) with index.json and README.md (each claim's record, split, writer, pages,
format, files, policies, label, lines and words).

    uv run python -m scripts.demo.render_v3_claims
"""

import io
import json
import random
import shutil
from collections import Counter
from pathlib import Path

from app.domain.contracts import IntakeClaim
from app.intake.form_codec import to_form_values
from scripts.verify.ocr_accuracy import scanned_pdf
from scripts.verify.v3_repetition import looping
from training.generate.forms import notes_capacity, notes_lines, render_pdf, render_scan
from training.generate.v3.config import OUT_DIR

OUT = OUT_DIR / "rendered"
SETS = ("validation", "test_messy", "test_unseen_style", "test_human_style")
PER_SET = 25
LONGEST_PER_SET = 10
SEED = 20261025
FORMATS = ("digital-pdf", "scanned-pdf", "png")


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.open(encoding="utf-8") if line.strip()]


def pages_for(notes: str) -> int:
    return 1 + max(1, -(-len(notes_lines(notes)) // notes_capacity()))


def chosen() -> list[tuple[str, dict, dict]]:
    picked = []
    rng = random.Random(SEED)
    for split in SETS:
        final = OUT_DIR / "final"
        rows = list(
            zip(
                read_jsonl(final / f"{split}.jsonl"),
                read_jsonl(final / f"{split}_inputs.jsonl"),
                strict=True,
            )
        )
        rows = [r for r in rows if not looping(r[1]["claim"]["clinical_notes"])]
        by_length = sorted(rows, key=lambda r: -len(r[1]["claim"]["clinical_notes"]))
        longest = by_length[:LONGEST_PER_SET]
        rest = rng.sample(by_length[LONGEST_PER_SET:], PER_SET - LONGEST_PER_SET)
        picked += [(split, record, given) for record, given in longest + rest]
    return picked


def render(split: str, record: dict, given: dict, form: str) -> dict:
    meta = record["metadata"]
    record_id = meta["record_id"]
    claim = IntakeClaim.model_validate(given["claim"])
    values = to_form_values(claim)
    seed = random.Random(f"{SEED}-{record_id}")
    if form == "digital-pdf":
        path = OUT / form / f"{record_id}.pdf"
        path.write_bytes(render_pdf(values, continued=True))
        files = [path]
        import pymupdf

        with pymupdf.open(path) as doc:
            pages = doc.page_count
    else:
        scan = render_scan(values, seed, value_noise_rate=0.0, continued=True)
        pages = len(scan.pages)
        if form == "scanned-pdf":
            path = OUT / form / f"{record_id}.pdf"
            path.write_bytes(scanned_pdf(scan.pages))
            files = [path]
        else:
            folder = OUT / form / record_id
            folder.mkdir(parents=True, exist_ok=True)
            files = []
            for number, page in enumerate(scan.pages, start=1):
                buffer = io.BytesIO()
                page.convert("L").save(buffer, format="PNG", optimize=True)
                (folder / f"page-{number}.png").write_bytes(buffer.getvalue())
                files.append(folder / f"page-{number}.png")
    notes = claim.clinical_notes
    return {
        "record_id": record_id,
        "claim_id": claim.claim_id,
        "split": split,
        "writer": meta.get("writer"),
        "format": form,
        "pages": pages,
        "expected_pages": pages_for(notes),
        "files": [str(f.relative_to(OUT)) for f in files],
        "service_lines": len(claim.service_lines),
        "note_words": len(notes.split()),
        "note_lines": len(notes_lines(notes)),
        "policies": meta.get("policy_ids"),
        "claim_decision": meta.get("claim_decision"),
        "test_only_policy": meta.get("unseen_policy"),
    }


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    for form in FORMATS:
        (OUT / form).mkdir(parents=True)
    rows = [
        render(split, record, given, FORMATS[i % len(FORMATS)])
        for i, (split, record, given) in enumerate(chosen())
    ]
    pages = Counter(r["pages"] for r in rows)
    summary = {
        "claims": len(rows),
        "by_format": dict(Counter(r["format"] for r in rows)),
        "by_split": dict(Counter(r["split"] for r in rows)),
        "by_writer": dict(Counter(r["writer"] for r in rows)),
        "pages": dict(sorted(pages.items())),
        "over_two_pages": sum(n for p, n in pages.items() if p > 2),
        "png_files": sum(len(r["files"]) for r in rows if r["format"] == "png"),
        "notes_box_lines": notes_capacity(),
        "every_page_rendered": all(r["pages"] == r["expected_pages"] for r in rows),
    }
    (OUT / "index.json").write_text(json.dumps({"summary": summary, "claims": rows}, indent=2))
    lines = [
        "# v3 claims rendered as documents",
        "",
        "Synthetic data only. Made by scripts/demo/render_v3_claims.py; the expected intake result",
        "is each record's own claim in data/generated/v3/final/<split>_inputs.jsonl.",
        "",
        "| Record | Split | Writer | Format | Pages | Lines | Words | Label | Files |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        files = (
            ", ".join(r["files"])
            if r["format"] != "png"
            else f"png/{r['record_id']}/ x{r['pages']}"
        )
        lines.append(
            f"| {r['record_id']} | {r['split']} | {r['writer']} | {r['format']} | {r['pages']} "
            f"| {r['service_lines']} | {r['note_words']} | {r['claim_decision']} | {files} |"
        )
    (OUT / "README.md").write_text("\n".join(lines) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
