"""Model v2 and v3 on the v3 study's test sets, scored from their Kaggle predictions (D-V3-13).
Report only.

The predictions (data/generated/eval/v3study/<model>-<set>.jsonl, `kaggle_eval collect`) keep each
raw answer, so every answer is scored here twice with the pipeline's scorer
(training/evaluate/model.py `score_record`): with the evidence guard (D-EVID-1) and without it.
For each, the metrics the team asked for:

- valid output: answers that pass the output schema and validation (after the one retry);
- line accuracy and macro-F1 over APPROVE / PEND / DENY of the lines the model decides (an invalid
  answer's lines count as PEND, as in the pipeline);
- criterion accuracy: criterion statuses equal to the label's, on valid answers;
- DENY precision: of the lines the model denies, the share the label denies;
- wrong approvals: lines the label pends or denies that the model approves (count and share);

every metric also for the claims on a policy seen in training and on a test-only policy, beside the
total (so a set's style effect shows apart from its new-policy effect); and errors broken down by
tricky-fact type, note length and lines per claim (v3 sets; the clean v2 set has no tricky facts).
Writes data/generated/eval/v3study/<model>-<set>.json.

    uv run python -m scripts.verify.v3_eval_report [--only v2-test_messy]
"""

import argparse
import json
from typing import Any

from training.evaluate.kaggle_eval import SETS, STUDY_DIR, read_jsonl
from training.evaluate.model import score_record, summarize
from training.generate.scenarios_v2 import TEST_ONLY_POLICIES
from training.generate.v3.config import OUT_DIR as V3_DIR
from training.generate.v3.dataset import TRICKY_OF, load_sheets

LENGTHS = ((0, 250, "under 250 words"), (250, 400, "250-399"), (400, 600, "400-599"))


def length_band(words: int) -> str:
    return next((name for low, high, name in LENGTHS if low <= words < high), "600 or more")


def line_stats(scored: list[dict[str, Any]]) -> dict[str, Any]:
    lines = [line for s in scored for line in s["lines"]]
    denied = [line for line in lines if line["predicted"] == "DENY"]
    should_not = [line for line in lines if line["gold"] in ("PEND", "DENY")]
    wrong_approvals = sum(line["predicted"] == "APPROVE" for line in should_not)
    return {
        "lines": len(lines),
        "line_accuracy": round(sum(x["gold"] == x["predicted"] for x in lines) / len(lines), 4)
        if lines
        else None,
        "deny_precision": round(sum(x["gold"] == "DENY" for x in denied) / len(denied), 4)
        if denied
        else None,
        "wrong_approvals": wrong_approvals,
        "wrong_approval_share": round(wrong_approvals / len(should_not), 4) if should_not else None,
    }


def breakdowns(
    scored: list[dict[str, Any]], metas: dict[str, dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    sheets = load_sheets(V3_DIR)
    groups: dict[str, list[dict[str, Any]]] = {}

    def add(name: str, row: dict[str, Any]) -> None:
        groups.setdefault(name, []).append(row)

    for row in scored:
        meta = metas[row["record_id"]]
        sheet = sheets.get(meta.get("sheet_id", ""))
        if sheet is not None:
            kinds = [name for name, has in TRICKY_OF.items() if has(sheet)]
            for name in kinds or ["none"]:
                add(f"tricky: {name}", row)
        if "note_words" in meta:
            add(f"length: {length_band(meta['note_words'])}", row)
        lines = meta.get("lines") or len(meta.get("line_labels") or [])
        add(f"lines per claim: {lines}", row)
    return {
        name: {"records": len(rows), **line_stats(rows)} for name, rows in sorted(groups.items())
    }


def test_only(meta: dict[str, Any]) -> bool:
    """Whether a record's claim is on a policy never seen in training (v3: its sheet's flag;
    v2: a test-only policy among its policies)."""
    if "unseen_policy" in meta:
        return bool(meta["unseen_policy"])
    return bool(set(meta.get("policy_ids") or []) & set(TEST_ONLY_POLICIES))


def metrics(rows: list[dict[str, Any]], metas: dict[str, dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"records": 0}
    summary = summarize(rows, metas)
    decisions = summary["decisions"]
    return {
        "records": len(rows),
        "valid_output_rate": summary["valid_output_rate"],
        "macro_f1": decisions.get("macro_f1"),
        "per_class_f1": {k: v["f1"] for k, v in (decisions.get("per_class") or {}).items()},
        "criterion_accuracy": summary["criterion_status_accuracy"],
        "retried": sum((r.get("attempts") or 1) > 1 for r in rows),
        **line_stats(rows),
    }


def report(model: str, set_name: str) -> dict[str, Any]:
    folder, split = SETS[set_name]
    records = {r["metadata"]["record_id"]: r for r in read_jsonl(folder / f"{split}.jsonl")}
    inputs = {i["record_id"]: i for i in read_jsonl(folder / f"{split}_inputs.jsonl")}
    predictions = read_jsonl(STUDY_DIR / f"{model}-{set_name}.jsonl")
    metas = {rid: r["metadata"] for rid, r in records.items()}
    found: dict[str, Any] = {
        "model": model,
        "set": set_name,
        "records": len(records),
        "predicted": len(predictions),
        "engine": sorted({p.get("engine") for p in predictions}),
    }

    def scored_with(guard: bool) -> list[dict[str, Any]]:
        rows = []
        for p in predictions:
            row = score_record(records[p["record_id"]], inputs[p["record_id"]], p["output"], guard)
            rows.append({**row, "latency_ms": p.get("latency_ms"), "attempts": p.get("attempts")})
        return rows

    for guard in (True, False):
        rows = scored_with(guard)
        seen = [r for r in rows if not test_only(metas[r["record_id"]])]
        unseen = [r for r in rows if test_only(metas[r["record_id"]])]
        found["guard_on" if guard else "guard_off"] = {
            **metrics(rows, metas),
            "confusion": summarize(rows, metas)["decisions"].get("confusion_matrix"),
            # the team's addition of 23 Oct: style and new-policy effects apart
            "by_policy": {
                "total": metrics(rows, metas),
                "policy seen in training": metrics(seen, metas),
                "test-only policy": metrics(unseen, metas),
            },
            "breakdowns": breakdowns(rows, metas),
        }
    return found


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--only", nargs="*", help="<model>-<set> names, default: every file")
    args = parser.parse_args()
    names = args.only or sorted(p.stem for p in STUDY_DIR.glob("*.jsonl"))
    for name in names:
        model, set_name = name.split("-", 1)
        result = report(model, set_name)
        (STUDY_DIR / f"{name}.json").write_text(json.dumps(result, indent=2) + "\n")
        on, off = result["guard_on"], result["guard_off"]
        print(
            f"{name}: {result['predicted']} of {result['records']}; macro-F1 guard on "
            f"{on['macro_f1']} off {off['macro_f1']}; valid {on['valid_output_rate']}; "
            f"line acc {on['line_accuracy']}; DENY precision {on['deny_precision']}"
        )


if __name__ == "__main__":
    main()
