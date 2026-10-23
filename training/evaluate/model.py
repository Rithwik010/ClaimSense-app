"""Decision-model evaluation on the test split (INSTRUCTIONS.md §10; P4.2 baseline, P4.4).

Each test record's system and user messages go to the model through the pipeline's Ollama client
(SLMOutput schema, temperature 0, fixed seed, thinking off). The answer is used exactly as in the
pipeline: validated, asked once more when invalid (D-DEC-1: another seed), an answer still invalid
turns every line into PEND, and each valid line's decision is derived from its statuses (D-DEC-1,
with the indication-group rule when the criteria carry group tags). `--prompt decision_v2`
re-renders a v2 record's inputs with model v1's prompt (the v2 comparison, D-POL-2). Metrics:

- line decisions (the pipeline's effective decisions): accuracy, macro-F1, per-class precision and
  recall, confusion matrix; also on valid answers only
- valid-output rate and the most common validation errors
- criterion statuses, benefit category, reasons, complexity and claim decision (valid answers)
- evidence fidelity: MET / NOT_MET evidence quoted word for word from the notes
- latency; and a split by seen vs unseen (test-only) policies and by scenario type

Predictions are appended to `data/generated/eval/<label>.jsonl` as they arrive (a stopped run
resumes); metrics go to `<label>.json` and `docs/results.md`. Follow progress with
`tail -f data/generated/eval/<label>.log`. Every prediction records the Ollama version; a run does
not resume on a different version (results would mix engines). A dropped connection is retried
twice before the run stops.

    uv run python -m training.evaluate.model --model gemma4:e2b --label baseline-gemma4-e2b
"""

import argparse
import hashlib
import json
import statistics
import time
from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import Any

from sklearn.metrics import confusion_matrix, precision_recall_fscore_support

from app.db.curated import load_curated
from app.domain.contracts import (
    ContextPackage,
    CriterionStatus,
    FinalLineDecision,
    LineDecision,
    RulesOutcome,
)
from app.ml.client import DecisionModel, ModelUnavailable
from app.ml.evidence import evidence_guard
from app.ml.validate import validate_output
from app.workflow.decisions import derive_claim_decision, final_line_decisions
from training.generate.common import GENERATED_DIR

DECISIONS = ["APPROVE", "PEND", "DENY"]
EVAL_DIR = GENERATED_DIR / "eval"
DATASET_DIR = GENERATED_DIR / "decision"
RESULTS_MD = Path(__file__).resolve().parents[2] / "docs" / "results.md"
RETRY_WAITS_SECONDS = (15, 45)


def complete_with_retry(
    model: DecisionModel,
    system: str,
    user: str,
    sleep: Callable[[float], None] = time.sleep,
    attempt: int = 1,
) -> str:
    """Transport failures only (the server restarting); an invalid answer's one retry is the
    caller's (`attempt=2`, as in the pipeline)."""
    for wait in (*RETRY_WAITS_SECONDS, None):
        try:
            return model.complete(system, user, attempt=attempt)
        except ModelUnavailable:
            if wait is None:
                raise
            sleep(wait)
    raise AssertionError("unreachable")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def _share(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 4) if denominator else None


def _decision_metrics(gold: list[str], predicted: list[str]) -> dict[str, Any]:
    if not gold:
        return {"lines": 0}
    precision, recall, f1, support = precision_recall_fscore_support(
        gold, predicted, labels=DECISIONS, zero_division=0
    )
    present = [i for i, n in enumerate(support) if n]
    return {
        "lines": len(gold),
        "accuracy": _share(sum(g == p for g, p in zip(gold, predicted, strict=True)), len(gold)),
        "macro_f1": round(float(sum(f1[i] for i in present) / len(present)), 4),
        "per_class": {
            label: {
                "precision": round(float(precision[i]), 4),
                "recall": round(float(recall[i]), 4),
                "f1": round(float(f1[i]), 4),
                "support": int(support[i]),
            }
            for i, label in enumerate(DECISIONS)
        },
        "confusion_matrix": {
            "labels": DECISIONS,
            "rows_gold_columns_predicted": confusion_matrix(
                gold, predicted, labels=DECISIONS
            ).tolist(),
        },
    }


def without_criteria(inputs: dict[str, Any]) -> dict[str, Any]:
    """The same record with no retrieved criteria (P4.4 ablation): the claim, the rules result and
    the plan benefits stay, so the only thing removed is what retrieval contributed."""
    context = {**inputs["context"]}
    context["lines"] = [{**line, "criteria": []} for line in context["lines"]]
    return {**inputs, "context": context}


def ablated_user_message(inputs: dict[str, Any], lookups: Any) -> str:
    """Re-render the prompt from the stripped context, so the wording matches the live pipeline."""
    from app.domain.contracts import IntakeClaim
    from app.ml.prompt import render_user_message

    return render_user_message(
        IntakeClaim.model_validate(inputs["claim"]),
        RulesOutcome.model_validate(inputs["rules_outcome"]),
        ContextPackage.model_validate(inputs["context"]),
        lookups,
    )


def score_record(
    record: dict[str, Any], inputs: dict[str, Any], text: str, guard: bool = True
) -> dict[str, Any]:
    """Compare one answer with the record's target, the way the pipeline would use it (decisions
    derived from the statuses, D-DEC-1). `guard=False` scores the answer without the evidence
    guard (D-EVID-1), as model v2 was evaluated before the guard."""
    rules = RulesOutcome.model_validate(inputs["rules_outcome"])
    context = ContextPackage.model_validate(inputs["context"])
    target = json.loads(record["messages"][-1]["content"])
    result = validate_output(text, rules, context)
    checked = evidence_guard(result, inputs["claim"]["clinical_notes"])[0] if guard else result
    effective = {
        d.line_no: d.decision.value
        for d in final_line_decisions(rules, checked, context)
        if d.source != "RULE"
    }
    gold_lines = {line["line_no"]: line for line in target["lines"]}
    predicted_lines = (
        {line.line_no: line for line in result.output.lines}
        if result.valid and result.output
        else {}
    )
    notes = inputs["claim"]["clinical_notes"]
    criteria = []
    for line_no, gold in gold_lines.items():
        answer = predicted_lines.get(line_no)
        statuses = {c.criterion_id: c for c in answer.criteria} if answer else {}
        for criterion in gold["criteria"]:
            predicted = statuses.get(criterion["criterion_id"])
            criteria.append(
                {
                    "gold": criterion["status"],
                    "predicted": predicted.status.value if predicted else None,
                    "quoted": (
                        predicted.evidence in notes
                        if predicted
                        and predicted.status in (CriterionStatus.MET, CriterionStatus.NOT_MET)
                        else None
                    ),
                }
            )
    rule_lines = [
        FinalLineDecision(
            line_no=label["line_no"],
            decision=LineDecision(label["decision"]),
            benefit_category=None,
            source="RULE",
            reason_codes=label["reason_codes"],
        )
        for label in record["metadata"]["line_labels"]
        if label["source"] == "RULE"
    ]
    model_lines = [
        FinalLineDecision(
            line_no=n,
            decision=LineDecision(v),
            benefit_category=None,
            source="MODEL",
            reason_codes=[],
        )
        for n, v in effective.items()
    ]
    return {
        "record_id": record["metadata"]["record_id"],
        "valid": result.valid,
        "errors": list(result.errors),
        "lines": [
            {
                "line_no": n,
                "gold": gold_lines[n]["decision"],
                "predicted": effective.get(n, "PEND"),
                "category_ok": (
                    predicted_lines[n].benefit_category == gold_lines[n]["benefit_category"]
                    if n in predicted_lines
                    else None
                ),
                "reasons_ok": (
                    list(predicted_lines[n].reasons) == gold_lines[n]["reasons"]
                    if n in predicted_lines
                    else None
                ),
            }
            for n in gold_lines
        ],
        "criteria": criteria,
        "complexity_ok": (
            result.output.complexity.value == target["complexity"]
            if result.valid and result.output
            else None
        ),
        "claim_decision_ok": derive_claim_decision(rule_lines + model_lines).value
        == record["metadata"]["claim_decision"],
    }


def summarize(
    scored: list[dict[str, Any]],
    metas: dict[str, dict[str, Any]],
    test_only: set[str] | None = None,
) -> dict[str, Any]:
    """`test_only`: the policies never seen in training (default: policy set v1's TEST_ONLY)."""
    if test_only is None:
        test_only = {p for p, x in load_curated().policies.items() if x.split == "TEST_ONLY"}
    lines = [line for s in scored for line in s["lines"]]
    valid_lines = [line for s in scored if s["valid"] for line in s["lines"]]
    criteria = [c for s in scored if s["valid"] for c in s["criteria"]]
    quoted = [c["quoted"] for c in criteria if c["quoted"] is not None]
    latencies = [s["latency_ms"] for s in scored if "latency_ms" in s]
    groups: dict[str, list[dict[str, Any]]] = {}
    for s in scored:
        meta = metas[s["record_id"]]
        seen = "unseen_policies" if set(meta["policy_ids"]) & test_only else "seen_policies"
        groups.setdefault(seen, []).append(s)
        groups.setdefault(f"scenario:{meta['scenario_type']}", []).append(s)
        if "note_style" in meta:
            groups.setdefault(f"style:{meta['note_style']}", []).append(s)

    def flags(key: str) -> float | None:
        values = [line[key] for line in valid_lines if line[key] is not None]
        return _share(sum(values), len(values))

    return {
        "records": len(scored),
        "valid_output_rate": _share(sum(s["valid"] for s in scored), len(scored)),
        "top_errors": Counter(
            e.split(":")[-1].strip() if ":" in e else e for s in scored for e in s["errors"][:1]
        ).most_common(8),
        "decisions": _decision_metrics(
            [line["gold"] for line in lines], [line["predicted"] for line in lines]
        ),
        "decisions_valid_only": _decision_metrics(
            [line["gold"] for line in valid_lines], [line["predicted"] for line in valid_lines]
        ),
        "criterion_status_accuracy": _share(
            sum(c["gold"] == c["predicted"] for c in criteria), len(criteria)
        ),
        "criterion_status_confusion": Counter(
            f"{c['gold']}->{c['predicted']}" for c in criteria if c["gold"] != c["predicted"]
        ).most_common(8),
        "evidence_quoted_rate": _share(sum(quoted), len(quoted)),
        "benefit_category_accuracy": flags("category_ok"),
        "reasons_accuracy": flags("reasons_ok"),
        "complexity_accuracy": _share(
            sum(bool(s["complexity_ok"]) for s in scored if s["valid"]),
            sum(1 for s in scored if s["valid"]),
        ),
        "claim_decision_accuracy": _share(sum(s["claim_decision_ok"] for s in scored), len(scored)),
        "latency_ms": {
            "p50": round(statistics.median(latencies)) if latencies else None,
            "p95": round(sorted(latencies)[int(0.95 * (len(latencies) - 1))])
            if latencies
            else None,
        },
        "groups": {
            name: {
                "records": len(items),
                "valid_output_rate": _share(sum(s["valid"] for s in items), len(items)),
                "line_accuracy": _decision_metrics(
                    [line["gold"] for s in items for line in s["lines"]],
                    [line["predicted"] for s in items for line in s["lines"]],
                ).get("accuracy"),
            }
            for name, items in sorted(groups.items())
        },
    }


def run(
    model: DecisionModel,
    label: str,
    dataset_dir: Path = DATASET_DIR,
    out_dir: Path = EVAL_DIR,
    limit: int | None = None,
    engine: str = "unknown",
    sleep: Callable[[float], None] = time.sleep,
    split: str = "test",
    ablate_criteria: bool = False,
    prompt: str = "record",
    retry: bool = True,
    test_only: set[str] | None = None,
) -> dict[str, Any]:
    """`prompt`: "record" sends the record's own messages; "decision_v2" re-renders the record's
    inputs with model v1's prompt (for a v2 dataset)."""
    records = read_jsonl(dataset_dir / f"{split}.jsonl")
    inputs = {i["record_id"]: i for i in read_jsonl(dataset_dir / f"{split}_inputs.jsonl")}
    lookups = None
    v1_render = None
    if prompt == "decision_v2":
        v1_render = v1_prompt_renderer()
    if ablate_criteria:
        from training.generate.decision_dataset import prompt_lookups

        lookups = prompt_lookups()
        inputs = {record_id: without_criteria(i) for record_id, i in inputs.items()}
    summary_meta = json.loads((dataset_dir / "summary.json").read_text())
    if limit:
        records = records[:limit]
    out_dir.mkdir(parents=True, exist_ok=True)
    predictions_path = out_dir / f"{label}.jsonl"
    done = (
        {p["record_id"]: p for p in read_jsonl(predictions_path)}
        if predictions_path.exists()
        else {}
    )
    fingerprint = hashlib.sha256((dataset_dir / f"{split}.jsonl").read_bytes()).hexdigest()[:12]
    stale = {p.get("dataset_sha") for p in done.values()} - {fingerprint}
    if stale:
        raise SystemExit(
            f"{label}: earlier predictions were made on another version of {split}.jsonl "
            f"({sorted(map(str, stale))}, now {fingerprint}); use a new --label or delete them"
        )
    engines = {p.get("engine") for p in done.values()}
    if engines and engines != {engine}:
        raise SystemExit(
            f"{label}: earlier predictions used {sorted(map(str, engines))}, now {engine}; "
            "use a new --label (results must not mix engines)"
        )
    log = (out_dir / f"{label}.log").open("a", encoding="utf-8")
    started = time.perf_counter()
    with predictions_path.open("a", encoding="utf-8") as predictions:
        for n, record in enumerate(records, start=1):
            record_id = record["metadata"]["record_id"]
            if record_id in done:
                continue
            system, user = record["messages"][0]["content"], record["messages"][1]["content"]
            if lookups is not None:
                user = ablated_user_message(inputs[record_id], lookups)
            if v1_render is not None:
                system, user = v1_render(inputs[record_id])
            t0 = time.perf_counter()
            text = complete_with_retry(model, system, user, sleep)
            attempts = 1
            if retry and not answer_valid(text, inputs[record_id]):
                text = complete_with_retry(model, system, user, sleep, attempt=2)
                attempts = 2
            latency = round((time.perf_counter() - t0) * 1000, 1)
            scored = score_record(record, inputs[record_id], text)
            row = {
                **scored,
                "latency_ms": latency,
                "engine": engine,
                "dataset_sha": fingerprint,
                "attempts": attempts,
                "output": text,
            }
            predictions.write(json.dumps(row) + "\n")
            predictions.flush()
            done[record_id] = row
            decisions = " ".join(f"{x['gold'][0]}>{x['predicted'][0]}" for x in scored["lines"])
            log.write(
                f"{n}/{len(records)} {record_id} valid={scored['valid']} {decisions} "
                f"{latency:.0f}ms elapsed={time.perf_counter() - started:.0f}s\n"
            )
            log.flush()
    log.close()
    metas = {r["metadata"]["record_id"]: r["metadata"] for r in records}
    scored_rows = [done[r["metadata"]["record_id"]] for r in records]
    retried = sum(1 for row in scored_rows if row.get("attempts", 1) > 1)
    report = {
        "label": label,
        "model": model.name,
        "engine": engine,
        "split": split,
        "context": "no retrieved criteria" if ablate_criteria else "full",
        "prompt": prompt if prompt != "record" else summary_meta.get("prompt_version"),
        "retried_records": retried,
        "dataset": {
            "generator_version": summary_meta.get("generator_version"),
            "prompt_version": summary_meta.get("prompt_version"),
            "retrieval": summary_meta.get("retrieval"),
            "seed": summary_meta.get("seed"),
            "test_records": len(records),
        },
        "metrics": summarize(scored_rows, metas, test_only),
    }
    (out_dir / f"{label}.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def answer_valid(text: str, inputs: dict[str, Any]) -> bool:
    rules = RulesOutcome.model_validate(inputs["rules_outcome"])
    context = ContextPackage.model_validate(inputs["context"])
    return validate_output(text, rules, context).valid


def v1_prompt_renderer() -> Callable[[dict[str, Any]], tuple[str, str]]:
    """(system, user) of model v1's prompt decision_v2 for a v2 record's inputs: the same claim,
    rules outcome and v2 criteria, rendered the way model v1 was trained (D-POL-2)."""
    from app.domain.contracts import IntakeClaim
    from app.ml.prompt import PROMPT_VERSION, render_user_message, system_prompt
    from training.generate.decision_dataset_v2 import lookups_v2

    lookups = lookups_v2()
    system = system_prompt(PROMPT_VERSION)

    def render(inputs: dict[str, Any]) -> tuple[str, str]:
        user = render_user_message(
            IntakeClaim.model_validate(inputs["claim"]),
            RulesOutcome.model_validate(inputs["rules_outcome"]),
            ContextPackage.model_validate(inputs["context"]),
            lookups,
            PROMPT_VERSION,
        )
        return system, user

    return render


def results_markdown(eval_dir: Path = EVAL_DIR) -> str:
    """docs/results.md from every evaluation report (aggregates only; no claim data)."""
    reports = [json.loads(p.read_text()) for p in sorted(eval_dir.glob("*.json"))]
    rows = [
        "| Run | Model | Engine | Split | Context | Records | Valid output | Line accuracy "
        "| Macro-F1 | Criterion status | Evidence quoted | Unseen-policy accuracy "
        "| Latency p50 (ms) |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in reports:
        m = r["metrics"]
        unseen = m["groups"].get("unseen_policies", {}).get("line_accuracy")
        rows.append(
            f"| {r['label']} | {r['model']} | {r.get('engine', '-')} | "
            f"{r.get('split', 'test')} | {r.get('context', 'full')} | {m['records']} | "
            f"{m['valid_output_rate']} | "
            f"{m['decisions'].get('accuracy')} | {m['decisions'].get('macro_f1')} | "
            f"{m['criterion_status_accuracy']} | {m['evidence_quoted_rate']} | {unseen} | "
            f"{m['latency_ms']['p50']} |"
        )
    datasets = sorted({json.dumps(r["dataset"], sort_keys=True) for r in reports})
    return "\n".join(
        [
            "# Results",
            "",
            "Generated by `training/evaluate/model.py` from `data/generated/eval/*.json`; do not",
            "edit by hand. Target (P4.4): macro-F1 >= 0.90 on line decisions, **on the test",
            "split**. An invalid answer counts as PEND on every line, as in the pipeline.",
            "",
            "Validation-split rows are diagnostics, not results: those records share the training",
            "split's note templates and policies, and they chose the best checkpoint.",
            "",
            "Rows with context `no retrieved criteria` are the retrieval ablation. Their criterion",
            "and evidence columns are meaningless: the model was not given criteria to report on.",
            "",
            *rows,
            "",
            "Datasets:",
            "",
            *[f"- `{d}`" for d in datasets],
            "",
        ]
    )


def main() -> None:
    from app.core.settings import get_settings
    from app.ml.client import OllamaDecisionModel

    settings = get_settings()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--model", default=settings.model_name)
    parser.add_argument("--label", required=True)
    parser.add_argument("--limit", type=int)
    parser.add_argument(
        "--split",
        default="test",
        choices=("test", "validation"),
        help="validation is a diagnostic only: same note templates and policies as training",
    )
    parser.add_argument(
        "--ablate-criteria",
        action="store_true",
        help="remove the retrieved criteria from the prompt, to measure what retrieval contributes",
    )
    args = parser.parse_args()
    import httpx

    version = httpx.get(f"{settings.ollama_url}/api/version", timeout=10).json()["version"]
    report = run(
        OllamaDecisionModel(settings.ollama_url, args.model),
        args.label,
        limit=args.limit,
        engine=f"ollama {version}",
        split=args.split,
        ablate_criteria=args.ablate_criteria,
    )
    RESULTS_MD.write_text(results_markdown(), encoding="utf-8")
    metrics = report["metrics"]
    print(
        json.dumps(
            {k: metrics[k] for k in ("records", "valid_output_rate", "claim_decision_accuracy")}
            | {"macro_f1": metrics["decisions"].get("macro_f1")},
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
