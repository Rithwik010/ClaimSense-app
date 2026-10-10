"""The stored decision dataset v2 against the pipeline's line derivation as it is now.

Each record's gold answer goes through the evidence guard (D-EVID-1) and `final_line_decisions`
(rules outcome, gold SLMOutput, context package from `<split>_inputs.jsonl`), as the pipeline runs
them; the decision, source and reason codes must equal the record's `line_labels`, and the guard
must change nothing (the gold MET evidence is quoted from the notes). Run after any change to
app/ml/derive.py, app/ml/evidence.py or app/workflow/decisions.py (D-DEC-1, D-DEC-2, D-EVID-1): a
difference means the stored labels, and the model trained on them, no longer match what the
pipeline does.

    uv run python -m scripts.verify.derive_parity
"""

import json
from pathlib import Path

from app.domain.contracts import ContextPackage, RulesOutcome, SLMOutput
from app.ml.evidence import evidence_guard
from app.ml.validate import ValidationResult
from app.workflow.decisions import final_line_decisions

DATASET = Path(__file__).resolve().parents[2] / "data" / "generated" / "decision_v2"


def main() -> None:
    total, different, guard_changes = 0, [], 0
    for split in ("train", "validation", "test"):
        records = (DATASET / f"{split}.jsonl").read_text(encoding="utf-8").splitlines()
        inputs = (DATASET / f"{split}_inputs.jsonl").read_text(encoding="utf-8").splitlines()
        for record_line, input_line in zip(records, inputs, strict=True):
            record, given = json.loads(record_line), json.loads(input_line)
            checked, notes = evidence_guard(
                ValidationResult(SLMOutput.model_validate(given["target"]), ()),
                given["claim"]["clinical_notes"],
            )
            decisions = final_line_decisions(
                RulesOutcome.model_validate(given["rules_outcome"]),
                checked,
                ContextPackage.model_validate(given["context"]),
            )
            guard_changes += len(notes)
            got = [(d.decision.value, d.source, d.reason_codes) for d in decisions]
            want = [
                (label["decision"], label["source"], label["reason_codes"])
                for label in record["metadata"]["line_labels"]
            ]
            total += 1
            if got != want:
                different.append(f"{record['metadata']['record_id']}: {got} != {want}")
    print(
        f"{total} records; {len(different)} differ from the pipeline's derivation; "
        f"the evidence guard changed {guard_changes} gold criteria"
    )
    for line in different[:20]:
        print(f"  {line}")
    if different or guard_changes:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
