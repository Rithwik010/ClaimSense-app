"""The v3 timing run, summed up (D-V3-13; go / no-go items e and f). Report only.

From the downloaded outputs of the two timing notebooks (training/finetune/prepare_kaggle_v3.py):
`kernel-v3-timing` (25 steps, a checkpoint and an evaluation of the fixed validation subset at step
20, the memory probe on the longest record) and `kernel-v3-resume` (steps 21 to 25 again, resumed
from the first one's step-20 checkpoint).

- seconds per training step (steps after the first few, which include compilation);
- the evaluation's time on the fixed subset (`EVAL_LIMIT` records);
- the projected full run: steps x seconds per step + evaluations x their time;
- peak GPU memory (training and the memory probe) against the T4's;
- the longest record's tokens against the token limit (the training script stops on any longer);
- the resume check: the losses of steps 21 to 25 in both notebooks.

Writes data/generated/v3/timing/summary.json (read by scripts/verify/v3_readiness.py).

`--partial` reads a timing run that stopped before writing training-log.json (the run of 24 Oct
failed in its step-20 evaluation): the seconds per step are the median gap between the kernel
log's loss lines after the first 5 steps, the evaluation's speed comes from its progress bar, and
the memory probe from its printed line; there is no resume check (`complete` is false).

    uv run python -m scripts.verify.v3_timing --timing <dir> --resume <dir> --max-seq-length N
    uv run python -m scripts.verify.v3_timing --timing <dir> --partial --max-seq-length N
"""

import argparse
import json
import math
import re
import statistics
from pathlib import Path
from typing import Any

from training.finetune.data import CONFIG
from training.finetune.prepare_kaggle_v3 import EVAL_LIMIT, SAVE_STEPS
from training.generate.v3.config import OUT_DIR

SUMMARY = OUT_DIR / "timing" / "summary.json"


def log_of(folder: Path) -> dict[str, Any]:
    found = sorted(folder.rglob("training-log.json"))
    if not found:
        raise SystemExit(f"no training-log.json under {folder}")
    return json.loads(found[0].read_text())


def losses(log: dict[str, Any], steps: range) -> dict[int, float]:
    return {h["step"]: h["loss"] for h in log["history"] if "loss" in h and h["step"] in steps}


def timing(timing_dir: Path, resume_dir: Path, records: int, max_seq_length: int) -> dict:
    run = log_of(timing_dir)
    again = log_of(resume_dir)
    evals = [h for h in run["history"] if "eval_runtime" in h]
    eval_seconds = evals[-1]["eval_runtime"] if evals else None
    batch = CONFIG["per_device_train_batch_size"] * CONFIG["gradient_accumulation_steps"]
    full_steps = math.ceil(records / batch)  # one epoch
    full_evals = full_steps // SAVE_STEPS
    per_step = run["seconds_per_step"]
    projected = (full_steps * per_step + full_evals * (eval_seconds or 0)) / 3600
    first, second = losses(run, range(21, 26)), losses(again, range(21, 26))
    same = (
        bool(first)
        and first.keys() == second.keys()
        and all(abs(first[s] - second[s]) <= 1e-3 * max(1.0, abs(first[s])) for s in first)
    )
    probe = run.get("memory_probe") or {}
    total = probe.get("gpu_total_gb")
    peak = max(run.get("peak_gpu_memory_gb") or 0, probe.get("peak_gb") or 0)
    return {
        "gpu": run.get("gpu"),
        "precision": run.get("precision"),
        "seconds_per_step": per_step,
        "full_run_records": records,
        "full_run_steps": full_steps,
        "evaluations": full_evals,
        "evaluation_records": EVAL_LIMIT,
        "evaluation_seconds": eval_seconds,
        "projected_full_run_hours": round(projected, 2),
        "peak_memory_gb": peak,
        "gpu_total_gb": total,
        "fits_t4_memory": total is not None and peak < total,
        "longest_record_tokens": probe.get("tokens"),
        "max_seq_length": max_seq_length,
        "resume_losses": {"first_run": first, "resumed": second},
        "resume_matches": same,
    }


def partial(timing_dir: Path, records: int, max_seq_length: int) -> dict:
    found = sorted(timing_dir.glob("*.log"))
    if not found:
        raise SystemExit(f"no kernel log under {timing_dir}")
    entries = json.loads(found[0].read_text())
    text = re.sub(r"\x1b\[[0-9;]*m", "", "".join(e.get("data", "") for e in entries))
    stamps = [e["time"] for e in entries if "'loss'" in e.get("data", "")]
    gaps = [b - a for a, b in zip(stamps, stamps[1:], strict=False)][5:]
    per_step = round(statistics.median(gaps), 1) if gaps else None
    bars = re.findall(r"(\d+)/" + str(EVAL_LIMIT) + r" \[\d+:\d+<[^,]*, *([0-9.]+)it/s\]", text)
    rate = float(bars[-1][1]) if bars else None  # evaluation records per second
    eval_seconds = round(EVAL_LIMIT / rate, 1) if rate else None
    probe_line = re.search(r"memory probe: (\{.*?\})", text)
    probe = json.loads(probe_line.group(1)) if probe_line else {}
    batch = CONFIG["per_device_train_batch_size"] * CONFIG["gradient_accumulation_steps"]
    full_steps = math.ceil(records / batch)
    full_evals = full_steps // SAVE_STEPS
    projected = (
        (full_steps * per_step + full_evals * (eval_seconds or 0)) / 3600 if per_step else None
    )
    error = re.findall(r"(?:RuntimeError|OutOfMemoryError|ValueError)[^\n]*", text)
    return {
        "complete": False,
        "steps_logged": len(stamps),
        "seconds_per_step": per_step,
        "seconds_per_step_range": [round(min(gaps), 1), round(max(gaps), 1)] if gaps else None,
        "full_run_records": records,
        "full_run_steps": full_steps,
        "evaluations": full_evals,
        "evaluation_records": EVAL_LIMIT,
        "evaluation_seconds": eval_seconds,
        "evaluation_seconds_from": f"{bars[-1][0]} of {EVAL_LIMIT} records" if bars else None,
        "projected_full_run_hours": round(projected, 2) if projected else None,
        "peak_memory_gb": probe.get("peak_gb"),
        "gpu_total_gb": probe.get("gpu_total_gb"),
        "fits_t4_memory": bool(probe) and probe["peak_gb"] < probe["gpu_total_gb"],
        "longest_record_tokens": probe.get("tokens"),
        "max_seq_length": max_seq_length,
        "resume_matches": None,
        "stopped_by": error[-1].strip() if error else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--timing", type=Path, required=True)
    parser.add_argument("--resume", type=Path)
    parser.add_argument("--partial", action="store_true", help="a run that stopped early")
    parser.add_argument("--max-seq-length", type=int, required=True)
    args = parser.parse_args()
    records = sum(1 for _ in (OUT_DIR / "final" / "train_mix.jsonl").open())
    if args.partial:
        report = partial(args.timing, records, args.max_seq_length)
    elif args.resume is None:
        raise SystemExit("--resume is needed unless --partial")
    else:
        report = timing(args.timing, args.resume, records, args.max_seq_length)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
