"""P6.1 (INSTRUCTIONS.md §11): regenerate docs/results.md and data/generated/eval/results.json.

Every number comes from a measurement this script runs or a report a committed script wrote:

- rules and calculator: the golden test files, run here with pytest (pass counts);
- end-to-end golden claims: the golden end-to-end tests, run here (need Postgres);
- extraction: the OCR field accuracy on held-out scans (scripts/verify/ocr_accuracy.py);
- retrieval: recall@3 no longer applies (D-RAG-1, D-RAG-2: policy set v2 is an exact lookup by
  code with no cap, tested against the policy files);
- model: the evaluation reports (training/evaluate/), and the evidence-guard rows
  (scripts/verify/v2_errors.py);
- latency per stage: the `claim_processed` lines of the API log (data/generated/logs/api.log,
  written by `make demo-up`), so the claims the API processed;
- reviewer agreement and review time: not measured (no real reviewers have used the system).

    uv run python -m scripts.verify.results_report
"""

import json
import re
import statistics
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
EVAL = ROOT / "data" / "generated" / "eval"
LOG = ROOT / "data" / "generated" / "logs" / "api.log"
OUT_MD = ROOT / "docs" / "results.md"
OUT_JSON = EVAL / "results.json"
SUITES = {
    "rules golden cases": ["tests/unit/test_rules_golden.py"],
    "calculator golden cases": ["tests/unit/test_calculator_golden.py"],
    "end-to-end golden claims": ["tests/e2e/test_e2e_golden.py", "tests/e2e/test_e2e_golden_v2.py"],
}
MODEL_REPORTS = {
    "Base gemma4:e2b (v1 test set)": EVAL / "baseline-gemma4-e2b.json",
    "Model v1 (v1 test set)": EVAL / "finetuned-v1.json",
    "Model v1 (v2 test set)": EVAL / "v2" / "v2data-model-v1.json",
    "Model v2 (v2 test set)": EVAL / "v2" / "v2data-model-v2.json",
    "Model E4B (v2 test set, evidence guard on)": EVAL / "v2" / "v2data-model-e4b.json",
}
STAGES = ("rules_ms", "context_ms", "model_ms", "calculator_ms", "duration_ms")
NOT_MEASURED = "not measured"
RECALL_NOTE = "not applicable: policy set v2 is an exact lookup by code (D-RAG-1, D-RAG-2)"


def pytest_counts(paths: list[str]) -> dict[str, int]:
    run = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            "-p",
            "no:warnings",
            *paths,
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    tail = run.stdout.strip().splitlines()[-1] if run.stdout.strip() else ""
    counts = {k: int(n) for n, k in re.findall(r"(\d+) (passed|failed|skipped|error)", tail)}
    return {k: counts.get(k, 0) for k in ("passed", "failed", "skipped", "error")}


def model_row(name: str, path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    metrics = json.loads(path.read_text())["metrics"]
    decisions = metrics["decisions"]
    return {
        "model": name,
        "records": metrics["records"],
        "valid_output": metrics["valid_output_rate"],
        "line_accuracy": decisions.get("accuracy"),
        "macro_f1": decisions.get("macro_f1"),
        "deny_precision": decisions.get("per_class", {}).get("DENY", {}).get("precision"),
        "criterion_accuracy": metrics.get("criterion_status_accuracy"),
        "latency_p50_ms": metrics.get("latency_ms", {}).get("p50"),
        "latency_p95_ms": metrics.get("latency_ms", {}).get("p95"),
    }


def latency() -> dict[str, Any]:
    if not LOG.exists():
        return {"source": f"{LOG.relative_to(ROOT)} not found", "claims": 0}
    rows = []
    for line in LOG.read_text(encoding="utf-8", errors="replace").splitlines():
        if '"claim_processed"' not in line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    out: dict[str, Any] = {"source": str(LOG.relative_to(ROOT)), "claims": len(rows)}
    for stage in STAGES:
        values = sorted(r[stage] for r in rows if stage in r)
        if values:
            out[stage] = {
                "claims": len(values),
                "median": round(statistics.median(values), 1),
                "max": values[-1],
            }
    return out


def guard_rows() -> list[dict[str, Any]]:
    rows = []
    for name in ("v2-errors.json", "e4b-errors.json"):
        path = EVAL / "v2" / name
        if path.exists():
            for row in json.loads(path.read_text())["guard"]["rows"]:
                rows.append({**row, "model": row["model"].replace("v2", name.split("-")[0])})
    return rows


def main() -> None:
    suites = {name: pytest_counts(paths) for name, paths in SUITES.items()}
    ocr_path = EVAL / "ocr" / "heldout_summary.json"
    ocr = json.loads(ocr_path.read_text()) if ocr_path.exists() else None
    models = [row for name, path in MODEL_REPORTS.items() if (row := model_row(name, path))]
    result = {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "rules_and_calculator": suites,
        "extraction": (
            {
                "held_out_claims": ocr["claims"],
                "fields": ocr["fields_written"],
                "field_accuracy": ocr["field_accuracy"],
                "blank_read_as_blank": ocr["blank_read_as_blank"],
                "target": 0.90,
            }
            if ocr
            else NOT_MEASURED
        ),
        "retrieval_recall_at_3": RECALL_NOTE,
        "models": models,
        "evidence_guard": guard_rows(),
        "macro_f1_target": 0.90,
        "latency_per_stage_ms": latency(),
        "reviewer_agreement": NOT_MEASURED,
        "review_time": NOT_MEASURED,
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    OUT_MD.write_text(markdown(result), encoding="utf-8")
    print(markdown(result))


def fmt(value: Any, digits: int = 4) -> str:
    if value is None:
        return "-"
    return f"{value:.{digits}f}" if isinstance(value, float) else str(value)


def markdown(r: dict[str, Any]) -> str:
    lines = [
        "# Results",
        "",
        f"Generated by `scripts/verify/results_report.py` on {r['generated']};"
        " do not edit by hand.",
        "Synthetic data only. The same numbers are in `data/generated/eval/results.json`.",
        "",
        "## Rules and calculator",
        "",
        "| Suite | Passed | Failed | Skipped |",
        "|---|---|---|---|",
        *[
            f"| {name} | {c['passed']} | {c['failed'] + c['error']} | {c['skipped']} |"
            for name, c in r["rules_and_calculator"].items()
        ],
        "",
        "## Extraction (scanned forms)",
        "",
    ]
    ocr = r["extraction"]
    if isinstance(ocr, dict):
        lines += [
            f"Field accuracy {ocr['field_accuracy']:.4f} on {ocr['fields']} fields of"
            f" {ocr['held_out_claims']} held-out scans (target {ocr['target']:.2f}); blank boxes"
            f" read as blank {ocr['blank_read_as_blank']:.4f} (`docs/results-ocr.md`).",
        ]
    else:
        lines.append(f"Field accuracy: {ocr}.")
    lines += [
        "",
        "## Retrieval",
        "",
        f"Recall@3: {r['retrieval_recall_at_3']}.",
        "",
        "## Decision model",
        "",
        f"Target: macro-F1 at least {r['macro_f1_target']:.2f} on line decisions.",
        "",
        "| Model | Records | Valid output | Line accuracy | Macro-F1 | DENY precision |"
        " Criterion accuracy | Latency p50 (ms) | Latency p95 (ms) |",
        "|---|---|---|---|---|---|---|---|---|",
        *[
            f"| {m['model']} | {m['records']} | {fmt(m['valid_output'])} |"
            f" {fmt(m['line_accuracy'])} |"
            f" {fmt(m['macro_f1'])} | {fmt(m['deny_precision'])} | {fmt(m['criterion_accuracy'])} |"
            f" {fmt(m['latency_p50_ms'])} | {fmt(m['latency_p95_ms'])} |"
            for m in r["models"]
        ],
        "",
        "Evidence guard (D-EVID-1), on the stored answers:",
        "",
        "| Model | Line accuracy | Macro-F1 | DENY precision | Wrong approvals |",
        "|---|---|---|---|---|",
        *[
            f"| {g['model']} | {fmt(g['line_accuracy'])} | {fmt(g['macro_f1'])} |"
            f" {fmt(g['deny_precision'])} | {g['wrong_approvals']} |"
            for g in r["evidence_guard"]
        ],
        "",
        "## Latency per stage",
        "",
    ]
    lat = r["latency_per_stage_ms"]
    if lat.get("claims"):
        lines += [
            f"From the `claim_processed` lines of `{lat['source']}` ({lat['claims']} claims"
            " processed through the API; claims the rules decide stop after the rules).",
            "",
            "| Stage | Claims | Median (ms) | Max (ms) |",
            "|---|---|---|---|",
            *[
                f"| {stage.removesuffix('_ms')} | {v['claims']} | {v['median']} | {v['max']} |"
                for stage, v in lat.items()
                if isinstance(v, dict)
            ],
        ]
    else:
        lines.append(f"Not measured: {lat['source']}.")
    lines += [
        "",
        "## Human review",
        "",
        f"Reviewer agreement: {r['reviewer_agreement']}. Review time: {r['review_time']}. No real"
        " reviewers have used the system; the review flow is tested with scripted reviews only.",
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    main()
