"""A scanned image of a demo claim (page one of our form, PNG or JPEG) under a new claim ID, for the
Playwright check that an image claim's original file shows in the web app (D-DOC-1). The claim is
demo claim 01 with its dates of service moved a week later, so it is not a duplicate of claim 01;
the render seed is the first whose claim ID, member ID and received date the OCR reads exactly (the
fields a claim needs to be filed). Written outside the repository (never committed); synthetic
data only.

    uv run python -m scripts.demo.claim_image --claim-id CLM-IMG-0001 --out /tmp/claim.png
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


def image(claim_id: str, kind: str, tries: int = 20) -> bytes:
    data = json.loads(CLAIM.read_text(encoding="utf-8"))
    data["claim_id"] = claim_id
    for line in data["service_lines"]:
        line["date_of_service"] = (
            date.fromisoformat(line["date_of_service"]) + timedelta(days=7)
        ).isoformat()
    values = to_form_values(IntakeClaim.model_validate(data))
    for attempt in range(tries):
        page = render_scan(
            values, random.Random(f"claim-image-{attempt}"), value_noise_rate=0.0
        ).pages[0]
        reads = read_scan([page])
        if all(field in reads and reads[field].text == values[field] for field in FILING):
            buffer = io.BytesIO()
            page.convert("L").save(buffer, format=kind, dpi=(150, 150))
            return buffer.getvalue()
    raise SystemExit(f"no render in {tries} seeds reads the claim ID, member ID and received date")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--claim-id", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--format", choices=("png", "jpeg"), default="png")
    args = parser.parse_args()
    args.out.write_bytes(image(args.claim_id, args.format.upper()))
    print(args.out)


if __name__ == "__main__":
    main()
