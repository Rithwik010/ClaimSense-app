"""Model v3 against model v2: docs/results-v3.md and data/generated/eval/v3study/results-v3.json
(the Model metrics page reads the JSON), written from the result files of the v3 study.

Every number comes from a result file in data/generated/eval/v3study/ (`scripts/verify/v3_laptop.py`
on the laptop; `training/evaluate/kaggle_eval.py` on Kaggle), and each is labelled with the machine
it was measured on, from the file:

- `<model>-<set>.json`: each model's scores on a set, with the evidence guard as the pipeline runs
  (`guard_on`), on its main set (notes stuck in a loop left out, D-V3-29); `engine` names Ollama
  and, on Kaggle, the T4 GPU; a label ending in `_laptop` was measured on the demo laptop;
- `compare-v3_best-<set>.json`: the paired v3 - v2 differences with their 95% intervals (Kaggle);
- `<model>_laptop30-clean.json`: D-MODEL-5's 30 claims timed on the demo laptop (D-V3-34).

    uv run python -m scripts.verify.results_v3 [--study data/generated/eval/v3study]
"""

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
STUDY = ROOT / "data" / "generated" / "eval" / "v3study"
OUT_MD = ROOT / "docs" / "results-v3.md"
# (set, title, what its notes are)
SETS = (
    ("clean", "Clean notes", "the v2 test set; notes from the v1 and v2 templates"),
    ("test_messy", "Messy notes", "v3's test set; abbreviations, typos, long histories"),
    ("test_unseen_style", "Unseen writing style", "messy notes by a writer v3 never trained on"),
    ("human_style", "Human-style notes", "written by a local LLM as a physician would (D-V3-15)"),
)
# (v2 label, v3 label) of the runs compared on each machine
RUNS = (("v2_laptop", "v3_best_laptop"), ("v2", "v3_best"))
MAIN_SET = "main set (no looping notes)"  # D-V3-29


def machine(report: dict[str, Any]) -> str:
    engine = ", ".join(report["engine"]).replace("ollama", "Ollama")
    if report["model"].endswith("_laptop"):
        return f"the demo laptop ({engine})"
    return f"Kaggle, T4 GPU ({engine.removesuffix(' T4')})"


def scores(report: dict[str, Any]) -> dict[str, Any]:
    guard = report["guard_on"]["main_set"]
    return {
        "claims": guard["records"],
        "macro_f1": guard["macro_f1"],
        "valid_output": guard["valid_output_rate"],
        "line_accuracy": guard["line_accuracy"],
        "deny_precision": guard["deny_precision"],
        "wrong_approvals": guard["wrong_approvals"],
        "criterion_accuracy": guard["criterion_accuracy"],
    }


def rows(study: Path) -> list[dict[str, Any]]:
    found = []
    for name, title, notes in SETS:
        for v2_label, v3_label in RUNS:
            v2_path, v3_path = study / f"{v2_label}-{name}.json", study / f"{v3_label}-{name}.json"
            if not (v2_path.exists() and v3_path.exists()):
                continue
            v2, v3 = json.loads(v2_path.read_text()), json.loads(v3_path.read_text())
            if machine(v2) != machine(v3) or scores(v2)["claims"] != scores(v3)["claims"]:
                raise SystemExit(f"{name}: {v2_label} and {v3_label} differ in claims or machine")
            ci95 = draws = None
            compare = study / f"compare-{v3_label}-{name}.json"
            if compare.exists():
                found_f1 = json.loads(compare.read_text())["guard_on"][MAIN_SET]["macro_f1"]
                ci95, draws = found_f1["ci95"], found_f1["draws"]
            found.append(
                {
                    "set": name,
                    "title": title,
                    "notes": notes,
                    "claims": scores(v3)["claims"],
                    "left_out_looping": len(v3["guard_on"]["main_set"]["left_out_looping"]),
                    "machine": machine(v3),
                    "v2": scores(v2),
                    "v3": scores(v3),
                    "macro_f1_difference_ci95": ci95,
                    "draws": draws,
                    "files": [v2_path.name, v3_path.name] + ([compare.name] if ci95 else []),
                }
            )
    return found


def timing(study: Path) -> dict[str, Any] | None:
    """Median and p95 seconds per claim of D-MODEL-5's 30 claims on the demo laptop."""
    found = {}
    for model, label in (("v2", "v2_laptop30-clean"), ("v3", "v3_best_laptop30-clean")):
        path = study / f"{label}.json"
        if not path.exists():
            return None
        metrics = json.loads(path.read_text())["metrics"]
        latency = metrics["latency_ms"]
        found[model] = {
            "claims": metrics["records"],
            "p50_ms": latency["p50"],
            "p95_ms": latency["p95"],
            "file": path.name,
        }
    return {"machine": "the demo laptop", **found}


def f3(value: float) -> str:
    return f"{value:.3f}"


def markdown(result: dict[str, Any]) -> str:
    out = [
        "# Results: model v3 against model v2",
        "",
        "Written by `scripts/verify/results_v3.py` from the result files in",
        "`data/generated/eval/v3study/` (not committed); every number below is from those files",
        "and names the machine it was measured on. Scores are with the evidence guard, as the",
        "pipeline runs (D-EVID-1), on each set's main set: notes stuck in a loop are left out",
        "(D-V3-29).",
        "Macro-F1 is over the line decisions APPROVE, PEND and DENY. All claims are synthetic. The",
        "demo uses `claimsense-decision:v3` (D-V3-34).",
        "",
        *(
            f"- {r['title']}, {r['machine']}: {r['left_out_looping']} claims left out as looping."
            for r in result["sets"]
            if r["left_out_looping"]
        ),
        "",
        "## Line-decision macro-F1",
        "",
        "| Set | Notes | Claims | Measured on | v2 | v3 | v3 - v2, 95% interval |",
        "|---|---|---:|---|---:|---:|---|",
    ]
    for r in result["sets"]:
        ci = r["macro_f1_difference_ci95"]
        interval = f"{ci[0]:+.3f} to {ci[1]:+.3f}" if ci else "not computed"
        out.append(
            f"| {r['title']} | {r['notes']} | {r['claims']} | {r['machine']} |"
            f" {f3(r['v2']['macro_f1'])} | {f3(r['v3']['macro_f1'])} | {interval} |"
        )
    out += [
        "",
        "The intervals are paired bootstrap intervals over the claims"
        f" ({max(r['draws'] or 0 for r in result['sets']):,} draws); one above zero means v3 is"
        " better on that set beyond chance.",
        "",
        "## Each measure",
        "",
        "| Set | Measured on | Model | Valid output | Line accuracy | DENY precision"
        " | Wrong approvals | Criterion accuracy |",
        "|---|---|---|---:|---:|---:|---:|---:|",
    ]
    for r in result["sets"]:
        for model in ("v2", "v3"):
            s = r[model]
            out.append(
                f"| {r['title']} | {r['machine']} | {model} | {f3(s['valid_output'])} |"
                f" {f3(s['line_accuracy'])} | {f3(s['deny_precision'])} | {s['wrong_approvals']} |"
                f" {f3(s['criterion_accuracy'])} |"
            )
    out += [
        "",
        "Wrong approvals: lines approved that should have been pended or denied. Valid output:",
        "answers the pipeline can use; an unusable answer pends its lines and sends the claim to",
        "FULL review. v3's valid output is under D-MODEL-3's gate; the team accepted it (D-V3-34).",
    ]
    t = result["timing"]
    if t:
        out += [
            "",
            "## Time per claim",
            "",
            f"D-MODEL-5's {t['v3']['claims']} claims on {t['machine']}, with the stack running:",
            "",
            "| Model | Median | p95 | File |",
            "|---|---:|---:|---|",
        ]
        for model in ("v2", "v3"):
            m = t[model]
            seconds = f"{m['p50_ms'] / 1000:.1f} s | {m['p95_ms'] / 1000:.1f} s"
            out.append(f"| {model} | {seconds} | `{m['file']}` |")
    out += ["", "## Result files", ""]
    for r in result["sets"]:
        files = ", ".join(f"`{name}`" for name in r["files"])
        out.append(f"- {r['title']}, {r['machine']}: {files}")
    return "\n".join(out) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--study", type=Path, default=STUDY)
    args = parser.parse_args()
    result = {"sets": rows(args.study), "timing": timing(args.study)}
    if not result["sets"]:
        raise SystemExit(f"no v3 study result files in {args.study}")
    (args.study / "results-v3.json").write_text(json.dumps(result, indent=2) + "\n", "utf-8")
    OUT_MD.write_text(markdown(result), encoding="utf-8")
    print(f"wrote {OUT_MD.relative_to(ROOT)} and {args.study / 'results-v3.json'}")


if __name__ == "__main__":
    main()
