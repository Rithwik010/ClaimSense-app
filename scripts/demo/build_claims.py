"""Demo claims (demo plan item 8): one synthetic claim per path the demo shows, written to
demo/claims/ with the prior authorizations they need (demo/authorizations.jsonl), so that
`make demo-reset` gives every path on a clean database.

Each claim is a claim of v3's held-out test sets (data/generated/v3/final/<split>_inputs.jsonl:
messy notes, a writing style v3 never trained on, and the LLM-written human-style notes, D-V3-15;
never in training or validation) under a demo claim ID, so the demo shows the notes model v3 was
built for (D-DEMO-1). Each was picked because v3 took it down its path on Kaggle and again on the
laptop through the pipeline; `scripts/verify/repeatability.py` `demo_claims` checks that before a
merge. Claim 05 keeps only the line R15 denies, so that every line is denied by the rule.
Synthetic data only; no CPT descriptor text (checked below).

| File | Path |
|---|---|
| 01 | clean approve -> QUICK -> accept -> finalize: accumulators and visit usage change |
| 02 | model PEND (missing documentation) -> STANDARD |
| 03 | model DENY -> FULL -> a reviewer overrides the line with a reason -> amounts recompute |
| 04 | PARTIAL: a line denied by a rule (NCCI, R11) and an approved line |
| 05 | every line denied by a rules v2 rule (R15) -> DENIED_BY_RULE, read-only |
| 06 | REJECT: the billing NPI fails its check digit (R03) |
| 07 | duplicate of 01 under another claim ID -> RJ_DUPLICATE (submit after 01) |
| 08 | clean scanned form -> OCR -> decision |
| 09 | scanned form, billing NPI mistyped -> read at confidence 0 -> RJ_LOW_CONFIDENCE_FIELD |

    uv run python -m scripts.demo.build_claims
"""

import json
import random
from pathlib import Path
from typing import Any

from app.domain.contracts import IntakeClaim
from app.intake.form_codec import to_form_values
from app.intake.ocr import page_images, read_scan
from scripts.verify.ocr_accuracy import scanned_pdf
from scripts.verify.policy_sources import cpt_descriptors, redact
from training.generate.forms import render_scan
from training.generate.v3.config import OUT_DIR as V3_DIR

ROOT = Path(__file__).resolve().parents[2]
SPLITS = ("test_messy", "test_unseen_style", "test_human_style")  # v3's held-out test sets
OUT = ROOT / "demo"
SCAN_SEED = "demo-20261011"  # scans: the first seed the OCR reads exactly (`clean_scan`)

# demo file -> (v3 test record, how the demo copy differs)
CLAIMS: dict[str, tuple[str, str]] = {
    "01-approve-quick": ("DV3-TM-00287", "json"),
    "02-pend-standard": ("DV3-TM-00281", "json"),
    "03-deny-full-override": ("DV3-TM-00065", "json"),
    "04-partial-ncci": ("DV3-TU-00095", "json"),
    "05-rule-deny-r15": ("DV3-TM-00183", "json"),
    "06-reject-invalid-npi": ("DV3-TM-00367", "invalid-npi"),
    "07-duplicate-of-01": ("DV3-TM-00287", "json"),
    "08-scanned-clean": ("DV3-TU-00018", "scan"),
    "09-scanned-low-confidence": ("DV3-HW-00075", "scan-npi-typo"),
}
KEEP_LINES = {"05-rule-deny-r15": (2,)}  # its line 1 goes to the model; line 2 R15 denies


def v3_records() -> dict[str, dict[str, Any]]:
    """v3's held-out test records by record ID (data/generated/v3, not committed)."""
    found = {}
    for split in SPLITS:
        for line in (V3_DIR / "final" / f"{split}_inputs.jsonl").read_text("utf-8").splitlines():
            if line.strip():
                record = json.loads(line)
                found[record["record_id"]] = record
    return found


def demo_claim(name: str, number: int, record: dict[str, Any]) -> dict[str, Any]:
    """The record's claim as demo claim `number`: its demo claim ID, and only the lines kept."""
    claim = dict(record["claim"], claim_id=f"CLM-DEMO-{number:02d}")
    keep = KEEP_LINES.get(name)
    if keep:
        lines = [line for line in claim["service_lines"] if line["line_no"] in keep]
        claim["service_lines"] = [dict(line, line_no=n) for n, line in enumerate(lines, start=1)]
    return claim


def broken_check_digit(npi: str) -> str:
    """The NPI with its last digit changed, so the Luhn check fails."""
    return npi[:-1] + str((int(npi[-1]) + 1) % 10)


def clean_scan(name: str, values: dict[str, str], tries: int = 40) -> bytes:
    """A scanned copy that the OCR reads exactly, apart from the free-text clinical note: the
    first render seed whose every other field reads as written (the demo shows a decision, not an
    OCR slip; OCR accuracy itself is measured in docs/results-ocr.md)."""
    for attempt in range(tries):
        scan = render_scan(
            values, random.Random(f"{SCAN_SEED}-{name}-{attempt}"), value_noise_rate=0.0
        )
        pdf = scanned_pdf(scan.pages)
        reads = read_scan(page_images(pdf))
        wrong = [
            f
            for f, text in values.items()
            if f != "clinical_notes" and (f not in reads or reads[f].text != text)
        ]
        if not wrong:
            return pdf
    raise SystemExit(f"{name}: no render in {tries} seeds reads every field exactly")


def build() -> list[str]:
    records = v3_records()
    (OUT / "claims").mkdir(parents=True, exist_ok=True)
    authorizations: dict[str, dict[str, Any]] = {}
    written = []
    for number, (name, (source, kind)) in enumerate(CLAIMS.items(), start=1):
        record = records[source]
        claim = demo_claim(name, number, record)
        for auth in record.get("authorizations", []):
            authorizations[auth["auth_number"]] = auth
        if kind == "invalid-npi":
            claim["billing_npi"] = broken_check_digit(claim["billing_npi"])
        if kind.startswith("scan"):
            values = to_form_values(IntakeClaim.model_validate(claim))
            if kind == "scan-npi-typo":
                values["billing_npi"] = broken_check_digit(values["billing_npi"])
            pdf = clean_scan(name, values)
            path = OUT / "claims" / f"{name}.pdf"
            path.write_bytes(pdf)
        else:
            path = OUT / "claims" / f"{name}.json"
            path.write_text(json.dumps(claim, indent=2) + "\n", encoding="utf-8")
        written.append(f"{path.relative_to(ROOT)} <- {source} ({kind})")
    # No AMA CPT descriptor text in any demo claim (CLAUDE.md).
    codes = {
        line["procedure_code"]
        for s, _ in CLAIMS.values()
        for line in records[s]["claim"]["service_lines"]
    }
    found = sum(
        redact(json.dumps(records[s]["claim"]), cpt_descriptors(codes))[1]
        for s, _ in CLAIMS.values()
    )
    if found:
        raise SystemExit(f"{found} CPT descriptor text(s) in the demo claims")
    (OUT / "authorizations.jsonl").write_text(
        "".join(json.dumps(a, sort_keys=True) + "\n" for _, a in sorted(authorizations.items())),
        encoding="utf-8",
    )
    return written


if __name__ == "__main__":
    for line in build():
        print(line)
