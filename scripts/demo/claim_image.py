"""Scanned images of a demo claim (PNG or JPEG, one image per page of our form) under a new claim
ID, for the checks that an image claim's original files show in the web app and that a claim can
be filed from its form's pages in several files (D-DOC-1, D-DOC-2; Playwright and `make e2e-api`).
The claim is demo claim 01 with its dates of service moved a week later (or more, with --days),
so it is not a duplicate of claim 01; the render seed is the first whose claim ID, member ID and
received date the OCR reads exactly (the fields a claim needs to be filed). Written outside the
repository (never committed); synthetic data only.

    uv run python -m scripts.demo.claim_image --claim-id CLM-IMG-0001 --out /tmp/claim.png
    uv run python -m scripts.demo.claim_image --claim-id CLM-IMG-0002 --out /tmp/p1.png \\
        --out-page2 /tmp/p2.png
"""

import argparse
import io
import json
import random
from datetime import date, timedelta
from pathlib import Path

from app.domain.contracts import IntakeClaim
from app.intake.form_codec import to_form_values
from app.intake.ocr import read_scan
from training.generate.forms import render_scan

ROOT = Path(__file__).resolve().parents[2]
CLAIM = ROOT / "demo" / "claims" / "01-approve-quick.json"
FILING = ("claim_id", "member_id", "received_date")


def claim(claim_id: str, days: int = 7) -> IntakeClaim:
    data = json.loads(CLAIM.read_text(encoding="utf-8"))
    data["claim_id"] = claim_id
    for line in data["service_lines"]:
        line["date_of_service"] = (
            date.fromisoformat(line["date_of_service"]) + timedelta(days=days)
        ).isoformat()
    return IntakeClaim.model_validate(data)


def images(claim_id: str, kind: str, days: int = 7, tries: int = 20) -> list[bytes]:
    """Each page of the claim's scanned form as an image file: page 1, the claim; page 2, its
    clinical note."""
    values = to_form_values(claim(claim_id, days))
    for attempt in range(tries):
        pages = render_scan(
            values, random.Random(f"claim-image-{attempt}"), value_noise_rate=0.0
        ).pages
        reads = read_scan(pages[:1])
        if all(field in reads and reads[field].text == values[field] for field in FILING):
            found = []
            for page in pages:
                buffer = io.BytesIO()
                page.convert("L").save(buffer, format=kind, dpi=(150, 150))
                found.append(buffer.getvalue())
            return found
    raise SystemExit(f"no render in {tries} seeds reads the claim ID, member ID and received date")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--claim-id", required=True)
    parser.add_argument("--out", type=Path, required=True, help="page 1")
    parser.add_argument("--out-page2", type=Path, help="page 2 (the clinical note), if wanted")
    parser.add_argument("--format", choices=("png", "jpeg"), default="png")
    parser.add_argument("--days", type=int, default=7, help="days to move the dates of service")
    args = parser.parse_args()
    first, second = images(args.claim_id, args.format.upper(), args.days)
    args.out.write_bytes(first)
    print(args.out)
    if args.out_page2:
        args.out_page2.write_bytes(second)
        print(args.out_page2)


if __name__ == "__main__":
    main()
