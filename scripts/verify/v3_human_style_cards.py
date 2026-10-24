"""Hand-check cards for the LLM-written human-style test set (D-V3-15, D-V3-19). Report only.

One card per record of data/generated/v3/final/test_human_style.jsonl: the policy and whether it is
test-only, each line's code and label, and for each criterion the model is shown (the record's
context package) the fact sheet's status, its label status and what the note must say (the fact's
wordings and values) or must not say (a missing fact's wording, an absent fact's forbidden words);
then the gate's quote for each documented fact and the note exactly as the model sees it (with the
noise layer). Writes data/generated/v3/hand_check_human_style.md, which is not committed (the notes
stay in data/generated); the verdicts go to training/generate/v3/hand_checks/human_style.json.

    uv run python -m scripts.verify.v3_human_style_cards
"""

import json
from typing import Any

from training.generate.v3.config import OUT_DIR
from training.generate.v3.dataset import load_sheets, read_jsonl

OUT = OUT_DIR / "hand_check_human_style.md"


def asked(fact: dict[str, Any]) -> str:
    if fact["status"] == "missing":
        return f"not stated; the claim lacks: {fact.get('missing_text')}"
    if fact["status"] == "absent":
        words = ", ".join(fact.get("forbidden") or []) or "anything that makes it apply"
        return f"does not apply; must not say: {words}"
    text = fact.get("text") or {}
    found = f"says: {text.get('A') or text.get('B')}"
    if fact.get("values"):
        found += f" (values {', '.join(fact['values'])})"
    if fact["status"] == "contradicted":
        found += f"; first says {fact.get('original')}, then corrects it"
    return found


def card(record: dict[str, Any], inputs: dict[str, Any], sheet: dict[str, Any]) -> list[str]:
    meta = record["metadata"]
    note = inputs["claim"]["clinical_notes"]
    facts = {f.get("criterion_id"): f for f in sheet["facts"]}
    lines = [
        f"## {meta['record_id']} ({sheet['sheet_id']}, attempt {meta.get('attempt')})",
        "",
        f"- policies: {', '.join(sheet['policy_ids'])}; "
        f"{'test-only policy' if sheet['unseen_policy'] else 'policy seen in training'}; "
        f"claim {sheet['label']['claim_decision']}; tricky: {', '.join(sheet['tricky']) or 'none'}",
        f"- patient: {sheet['patient']['age']} {sheet['patient']['sex']}; visit "
        f"{sheet['visit_date']}; diagnoses: "
        + ", ".join(f"{d['code']} {d['description']}" for d in sheet["diagnoses"]),
    ]
    for line in inputs["context"]["lines"]:
        label = next(x for x in sheet["lines"] if x["line_no"] == line["line_no"])
        lines.append(
            f"- line {line['line_no']} {line['procedure_code']} {label['description']}: "
            f"{label['label']['decision']} ({label['label']['source']})"
        )
        for criterion in line["criteria"]:
            fact = facts.get(criterion["criterion_id"])
            status = f"{fact['status']} -> {fact['label_status']}" if fact else "no fact"
            lines += [
                f"  - {criterion['criterion_id']} [{status}]: {criterion['text']}",
                f"    - {asked(fact)}" if fact else "    - (not on the fact sheet)",
            ]
    lines += ["", "```text", note, "```", ""]
    return lines


def main() -> None:
    sheets = load_sheets(OUT_DIR)
    final = OUT_DIR / "final"
    records = read_jsonl(final / "test_human_style.jsonl")
    inputs = read_jsonl(final / "test_human_style_inputs.jsonl")
    out = ["# Hand check: the LLM-written human-style test set", "", "Synthetic data only.", ""]
    for record, given in zip(records, inputs, strict=True):
        out += card(record, given, sheets[record["metadata"]["sheet_id"]])
    OUT.write_text("\n".join(out), encoding="utf-8")
    print(json.dumps({"cards": len(records), "file": str(OUT)}))


if __name__ == "__main__":
    main()
