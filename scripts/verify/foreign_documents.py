"""B5: what the intake does with files that are not our form, or our form turned, tilted or
shifted. Builds each case (synthetic: a PDF and images that are not our form, made here with
PyMuPDF and Pillow; our own form rendered by training/generate/forms.py), reads it as the upload
routes do (`read_claim_file`, `read_claim_files`) and prints the outcome: read (with how many
fields match the form as written) or refused, with the message the provider sees.

With --shifts it also measures how well the box reader reads a page moved sideways or up and
down (the tolerance the label check uses, app/intake/form_check.py), on the development scans.
With --margins N it measures every printed label on the first N held-out scans of
scripts/verify/ocr_accuracy.py (both pages): how many are in place per page against the number
required, and how far the worst one is from the limits, i.e. how far genuine scans are from
being refused.

    uv run python -m scripts.verify.foreign_documents [--shifts] [--margins N] [--json OUT]
"""

import argparse
import io
import json
import random
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

import pymupdf
from PIL import Image, ImageDraw

from app.domain.contracts import IntakeClaim
from app.intake.files import UnreadableFile, read_claim_file, read_claim_files
from app.intake.form_codec import from_form_values, to_form_values
from app.intake.layout import ALL_PAGE_ONE_BOXES, PAGE_WIDTH
from app.intake.ocr import page_images
from scripts.verify.ocr_accuracy import DEV_CLAIMS, DEV_SEED, records, scanned_pdf
from training.generate.forms import ScanResult, render_pdf, render_scan

SCAN_DPI = 150
DEMO_CLAIM = Path(__file__).resolve().parents[2] / "demo" / "claims" / "01-approve-quick.json"
UNRELATED = (
    "Minutes of the community garden committee. The spring planting starts in April; volunteers "
    "bring their own gloves. The compost bins near the east gate are full and will be turned on "
    "Saturday morning. Next meeting: the first Tuesday of the month at seven in the library."
)


# --- Files that are not our form -------------------------------------------------------------


def unrelated_pdf(pages: int = 1) -> bytes:
    """A valid PDF with a text layer of unrelated prose (letter size, like our form)."""
    with pymupdf.open() as doc:
        for number in range(pages):
            page = doc.new_page(width=612, height=792)
            heading = f"Garden committee newsletter, page {number + 1}"
            page.insert_text((72, 60), heading, fontsize=14)
            page.insert_textbox(pymupdf.Rect(72, 90, 540, 700), UNRELATED * 4, fontsize=10)
        return doc.tobytes()


def unrelated_page_image() -> Image.Image:
    """A letter-size page image (150 dpi) of unrelated typed text and a table."""
    page = Image.new("L", (round(8.5 * SCAN_DPI), 11 * SCAN_DPI), 255)
    draw = ImageDraw.Draw(page)
    draw.text((90, 60), "GARDEN COMMITTEE NEWSLETTER", fill=0, font_size=36)
    for row in range(30):
        draw.text((90, 150 + row * 44), UNRELATED[row * 7 : row * 7 + 60], fill=0, font_size=22)
    for row in range(8):
        draw.rectangle((700, 300 + row * 60, 1150, 340 + row * 60), outline=0, width=2)
    return page


def image_bytes(image: Image.Image, kind: str = "PNG") -> bytes:
    out = io.BytesIO()
    image.convert("L").save(out, format=kind, dpi=(SCAN_DPI, SCAN_DPI))
    return out.getvalue()


# --- Our form, turned, tilted or shifted -----------------------------------------------------


def scan(claim: IntakeClaim, seed: int | str = 5) -> ScanResult:
    """A scanned copy of the claim's form, without value noise."""
    return render_scan(to_form_values(claim), random.Random(seed), value_noise_rate=0.0)


def turned(page: Image.Image, degrees: int) -> Image.Image:
    """The page turned counter-clockwise by a multiple of 90 degrees (as scanned on its side)."""
    return page.rotate(degrees, expand=True)


def tilted(page: Image.Image, degrees: float) -> Image.Image:
    """The page tilted (counter-clockwise) by `degrees`, white where the paper was not."""
    return page.rotate(degrees, resample=Image.Resampling.BICUBIC, fillcolor=255)


def shifted(page: Image.Image, dx: float, dy: float) -> Image.Image:
    """The page moved right by dx and down by dy points (as fed off-centre into a scanner)."""
    scale = page.width / PAGE_WIDTH
    out = Image.new("L", page.size, 255)
    out.paste(page.convert("L"), (round(dx * scale), round(dy * scale)))
    return out


def shifted_pdf(pdf: bytes, dx: float, dy: float) -> bytes:
    """A digital PDF of our form with every page's content moved by (dx, dy) points."""
    with pymupdf.open(stream=pdf, filetype="pdf") as source, pymupdf.open() as out:
        for index, page in enumerate(source):
            new = out.new_page(width=page.rect.width, height=page.rect.height)
            new.show_pdf_page(page.rect + (dx, dy, dx, dy), source, index)
        return out.tobytes()


# --- The cases -------------------------------------------------------------------------------


def demo_claim() -> IntakeClaim:
    """Demo claim 01 (synthetic, committed in demo/claims/)."""
    return IntakeClaim.model_validate_json(DEMO_CLAIM.read_text(encoding="utf-8"))


def cases() -> dict[str, Callable[[], list[bytes]]]:
    """Case name -> the files uploaded (one file: POST /v1/claims/intake/file; several:
    /intake/files)."""
    claim = demo_claim()
    pages = scan(claim).pages
    first, second = pages
    digital = render_pdf(to_form_values(claim))
    return {
        "PDF with unrelated text": lambda: [unrelated_pdf()],
        "PNG of an unrelated page": lambda: [image_bytes(unrelated_page_image())],
        "JPEG of an unrelated page": lambda: [image_bytes(unrelated_page_image(), "JPEG")],
        "image-only PDF of an unrelated page": lambda: [scanned_pdf([unrelated_page_image()])],
        "our scan (PNG), upright": lambda: [image_bytes(first)],
        "our scan turned 90 degrees": lambda: [image_bytes(turned(first, 90))],
        "our scan turned 180 degrees": lambda: [image_bytes(turned(first, 180))],
        "our scan turned 270 degrees": lambda: [image_bytes(turned(first, 270))],
        "our two-page scan (PDF) turned 90 degrees": lambda: [
            scanned_pdf([turned(page, 90) for page in pages])
        ],
        "our scan tilted 10 degrees": lambda: [image_bytes(tilted(first, 10))],
        "our scan tilted -10 degrees (JPEG)": lambda: [image_bytes(tilted(first, -10), "JPEG")],
        "our scan tilted 4 degrees": lambda: [image_bytes(tilted(first, 4))],
        "our scan shifted 8 points right": lambda: [image_bytes(shifted(first, 8, 0))],
        "our scan shifted 4 points down": lambda: [image_bytes(shifted(first, 0, 4))],
        "our page 2 alone": lambda: [image_bytes(second)],
        "our digital PDF shifted 8 points down": lambda: [shifted_pdf(digital, 0, 8)],
        "two files: page 1, then an unrelated page": lambda: [
            image_bytes(first),
            image_bytes(unrelated_page_image()),
        ],
        "two files: page 1 turned 90 degrees, page 2": lambda: [
            image_bytes(turned(first, 90)),
            image_bytes(second),
        ],
        "two files: page 1, then page 2 tilted 10 degrees": lambda: [
            image_bytes(first),
            image_bytes(tilted(second, 10)),
        ],
    }


def _leaves(value: Any, path: str = "") -> dict[str, Any]:
    """Every leaf of a claim dictionary by its path (service_lines.0.units, ...)."""
    if isinstance(value, dict):
        return {
            k: v for key, item in value.items() for k, v in _leaves(item, f"{path}{key}.").items()
        }
    if isinstance(value, list):
        return {
            k: v for i, item in enumerate(value) for k, v in _leaves(item, f"{path}{i}.").items()
        }
    return {path.rstrip("."): value}


def outcome(files: list[bytes], written: dict[str, str]) -> dict[str, Any]:
    """Read as the upload routes read; how many claim fields match the claim the form holds
    (page 1's boxes, parsed as the readers parse them)."""
    try:
        claim, _, source = read_claim_file(files[0]) if len(files) == 1 else read_claim_files(files)
    except UnreadableFile as exc:
        return {"result": "refused (422)", "message": str(exc)}
    page_one = {box.field for box in ALL_PAGE_ONE_BOXES}
    want = _leaves(from_form_values({f: v for f, v in written.items() if f in page_one}))
    got = _leaves(claim)
    same = sum(got.get(path) == value for path, value in want.items())
    return {
        "result": f"read ({source.value})",
        "message": f"{same} of {len(want)} claim fields as written",
    }


def report() -> list[dict[str, Any]]:
    written = to_form_values(demo_claim())
    rows = []
    for name, build in cases().items():
        rows.append({"case": name, **outcome(build(), written)})
        print(f"| {name} | {rows[-1]['result']} | {rows[-1]['message']} |", flush=True)
    return rows


# --- How far a page may be off and still read well (--shifts) --------------------------------


SHIFTS = [(0, dy) for dy in (-4, -3, -2, -1, 0, 1, 2, 3, 4)] + [
    (dx, 0) for dx in (-8, -6, -4, -2, 2, 4, 6, 8)
]


def _shift_case(args: tuple[dict[str, Any], float, float]) -> tuple[float, float, int, int]:
    from app.intake.ocr import read_box, straighten

    record, dx, dy = args
    claim = IntakeClaim.model_validate(record["claim"])
    written = render_scan(to_form_values(claim), random.Random(f"{DEV_SEED}-{claim.claim_id}"))
    page = straighten(page_images(scanned_pdf(written.pages))[0])
    moved = shifted(page, dx, dy)
    boxes = [box for box in ALL_PAGE_ONE_BOXES if written.values.get(box.field)]
    right = sum(
        (read := read_box(moved, box)) is not None and read.text == written.values[box.field]
        for box in boxes
    )
    return dx, dy, right, len(boxes)


def shift_tolerance(claims: int = 6) -> dict[str, float]:
    """Box-read accuracy of development scans moved by each shift (points), read without the
    label check (the reader alone)."""
    chosen = records()[: min(claims, DEV_CLAIMS)]
    jobs = [(record, dx, dy) for dx, dy in SHIFTS for record in chosen]
    totals: dict[tuple[float, float], list[int]] = {}
    with ProcessPoolExecutor(6) as pool:
        for dx, dy, right, total in pool.map(_shift_case, jobs):
            counts = totals.setdefault((dx, dy), [0, 0])
            counts[0] += right
            counts[1] += total
    result = {f"dx {dx:+g} dy {dy:+g}": round(r / n, 3) for (dx, dy), (r, n) in totals.items()}
    for key, value in result.items():
        print(f"{key}: {value}")
    return result


# --- How far genuine scans are from being refused (--margins) ----------------------------------


def _margin_case(record: dict[str, Any]) -> list[dict[str, Any]]:
    from app.intake.form_check import REQUIRED
    from app.intake.ocr import labels_seen, straighten
    from scripts.verify.ocr_accuracy import HELDOUT_SEED

    claim = IntakeClaim.model_validate(record["claim"])
    written = render_scan(to_form_values(claim), random.Random(f"{HELDOUT_SEED}-{claim.claim_id}"))
    pages = []
    for index, page in enumerate(page_images(scanned_pdf(written.pages))):
        seen = labels_seen(straighten(page), index)
        pages.append(
            {
                "claim_id": claim.claim_id,
                "page": index,
                "in_place": sum(label.in_place for label in seen),
                "labels": len(seen),
                "required": REQUIRED[index],
                "max_dx": max(abs(label.dx) for label in seen if label.dx is not None),
                "max_dy": max(abs(label.dy) for label in seen if label.dy is not None),
                "min_similarity": min(
                    (label.similarity for label in seen if label.similarity is not None),
                    default=None,
                ),
                "out_of_place": [label.label.text for label in seen if not label.in_place],
            }
        )
    return pages


def margins(claims: int) -> dict[str, Any]:
    """Labels in place on held-out scans, per page of the form."""
    chosen = records()[DEV_CLAIMS:][:claims]
    with ProcessPoolExecutor(6) as pool:
        pages = [page for found in pool.map(_margin_case, chosen) for page in found]
    summary: dict[str, Any] = {"claims": len(chosen)}
    for index in (0, 1):
        on = [p for p in pages if p["page"] == index]
        counts: dict[int, int] = {}
        for p in on:
            counts[p["in_place"]] = counts.get(p["in_place"], 0) + 1
        missed: dict[str, int] = {}
        for p in on:
            for text in p["out_of_place"]:
                missed[text] = missed.get(text, 0) + 1
        summary[f"page {index + 1}"] = {
            "labels": on[0]["labels"],
            "required": on[0]["required"],
            "pages_by_labels_in_place": dict(sorted(counts.items())),
            "refused": sum(p["in_place"] < p["required"] for p in on),
            "fewest_in_place": min(p["in_place"] for p in on),
            "labels_out_of_place": missed,
        }
    print(json.dumps(summary, indent=2))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--shifts", action="store_true", help="also measure the shift tolerance")
    parser.add_argument("--margins", type=int, default=0, help="held-out scans to measure")
    parser.add_argument("--json", help="write the outcomes (and shifts) to this JSON file")
    args = parser.parse_args()
    print("| Case | Result | Message |\n|---|---|---|")
    found: dict[str, Any] = {"cases": report()}
    if args.margins:
        found["margins"] = margins(args.margins)
    if args.shifts:
        found["shifts"] = shift_tolerance()
    if args.json:
        with open(args.json, "w", encoding="utf-8") as out:
            json.dump(found, out, indent=2)


if __name__ == "__main__":
    main()
