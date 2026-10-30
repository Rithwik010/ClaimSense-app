"""Extra demo claims (the user's request after the demo run of 30 Oct): nine more claims of v3's
held-out test sets, beyond the nine demo claims (scripts/demo/build_claims.py), for showing more
claims through the whole pipeline. Written to demo/extra/: six as JSON, two as digital PDFs of our
form (read from the text layer) and one as a scanned PDF (read by OCR; a render that the OCR reads
exactly, apart from the free-text notes, as `build_claims.clean_scan` picks it).

Each claim is a v3 test record's claim under a CLM-EXTRA claim ID, its notes without trailing
blanks (a form cannot print them); none needs a prior authorization, none repeats a demo claim,
and none repeats another extra claim, so none is rejected as a duplicate. The path each takes
(D-DEMO-1's method: v3 on Kaggle, then the pipeline on the laptop) is in docs/DEMO.md.

    uv run python -m scripts.demo.build_extra_claims
"""

import json

from app.domain.contracts import IntakeClaim
from app.intake.form_codec import to_form_values
from scripts.demo.build_claims import OUT, clean_scan, v3_records
from training.generate.forms import notes_capacity, notes_lines, render_pdf

EXTRA = OUT / "extra"
# demo file -> (v3 test record, how it is filed)
CLAIMS: dict[str, tuple[str, str]] = {
    "10-approve-quick-pt-eval": ("DV3-TM-00376", "json"),
    "11-pend-psych-testing": ("DV3-TM-00310", "json"),
    "12-deny-ultrasound": ("DV3-TM-00088", "json"),
    "13-partial-colonoscopy-ncci": ("DV3-TM-00368", "json"),
    "14-approve-visit-and-holter": ("DV3-TU-00085", "json"),
    "15-pend-manual-therapy": ("DV3-TM-00268", "json"),
    "16-digital-partial-debridement-ncci": ("DV3-TM-00607", "digital"),
    "17-digital-deny-ultrasound": ("DV3-TM-00187", "digital"),
    "18-scanned-approve-ultrasound": ("DV3-TU-00017", "scan"),
}


def build() -> list[str]:
    records = v3_records()
    EXTRA.mkdir(parents=True, exist_ok=True)
    written = []
    for name, (source, kind) in CLAIMS.items():
        record = records[source]
        if record.get("authorizations"):
            raise SystemExit(f"{name}: {source} needs a prior authorization")
        claim = dict(record["claim"], claim_id=f"CLM-EXTRA-{name[:2]}")
        claim["clinical_notes"] = claim["clinical_notes"].rstrip()
        if kind == "json":
            path = EXTRA / f"{name}.json"
            path.write_text(json.dumps(claim, indent=2) + "\n", encoding="utf-8")
        else:
            values = to_form_values(IntakeClaim.model_validate(claim))
            long_notes = len(notes_lines(values["clinical_notes"])) > notes_capacity()
            pdf = (
                render_pdf(values, continued=long_notes)
                if kind == "digital"
                else clean_scan(name, values)
            )
            path = EXTRA / f"{name}.pdf"
            path.write_bytes(pdf)
        written.append(f"{path.relative_to(OUT.parent)} <- {source} ({kind})")
    return written


if __name__ == "__main__":
    for line in build():
        print(line)
