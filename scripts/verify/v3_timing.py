"""The v3 timing run, summed up (D-V3-13, D-V3-22; go / no-go items e and f). Report only.

From the downloaded outputs of the two timing notebooks (training/finetune/prepare_kaggle_v3.py):
`kernel-v3-timing` (25 steps; an evaluation of the fixed validation subset and a checkpoint at steps
10 and 20, the best of the two kept) and `kernel-v3-resume` (steps 21 to 25 again, in a new session,
resumed from the first one's step-20 checkpoint). The training log holds each step's seconds (step
begin to step end), tokens and records (training/finetune/train.py).

- the projected full run, from tokens (the team's rule of 24 Oct): the seconds per training token of
  steps 6 to 25 (the first 5 include compilation) x every token of the training mix, plus the
  validation passes (`SAVE_STEPS` apart) x their measured time; at most `LIMIT_HOURS`. The
  checkpoint saves and each session's set-up are shown beside it;
- validation and the best checkpoint: both evaluations ran, on a subset holding the longest
  validation record; each validation loss is a finite number on the training loss's scale (between
  `LOSS_SCALE` times smaller and larger than the mean training loss of the 10 steps before it); the
  best checkpoint is the one with the lower validation loss, and its adapter was saved; each
  validation pass's peak GPU memory, apart from training's;
- the resume check: the resumed session begins at the checkpoint's step with its learning rate,
  schedule and optimizer state; its steps 21 to 25 repeat the first run's losses, learning rates and
  records (by id), which are the records after step 20's, not the first ones of the data;
- peak GPU memory against the T4's, with the memory probe of 24 Oct (`--probe-log`, D-V3-20), and
  the longest record's tokens against the token limit.

Writes data/generated/v3/timing/summary.json (read by scripts/verify/v3_readiness.py).

`--partial` reads a timing run that stopped before writing training-log.json (the run of 24 Oct
failed in its step-20 evaluation): the seconds per step are the median gap between the kernel
log's loss lines after the first 5 steps, the evaluation's speed comes from its progress bar, and
the memory probe from its printed line; there is no resume check (`complete` is false).

    uv run python -m scripts.verify.v3_timing --timing <dir> --resume <dir> --probe-log <dir>
        --max-seq-length N
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


LIMIT_HOURS = 19  # go / no-go item (f), D-V3-22
LOSS_SCALE = 5
WARM_UP_STEPS = 5


def losses(log: dict[str, Any], steps: range, field: str = "loss") -> dict[int, float]:
    return {
        h["step"]: h[field]
        for h in log["history"]
        if "loss" in h and field in h and h["step"] in steps
    }


def close(a: dict[int, float], b: dict[int, float]) -> bool:
    return (
        bool(a)
        and a.keys() == b.keys()
        and all(abs(a[k] - b[k]) <= 1e-3 * max(1.0, abs(a[k])) for k in a)
    )


def probe_of(folder: Path | None) -> dict[str, Any]:
    """The memory probe's printed line in a kernel log (the run of 24 Oct, D-V3-20)."""
    for log in sorted(folder.glob("*.log")) if folder else []:
        entries = json.loads(log.read_text())
        found = re.search(r"memory probe: (\{.*?\})", "".join(e.get("data", "") for e in entries))
        if found:
            return json.loads(found.group(1))
    return {}


def timing(
    timing_dir: Path, resume_dir: Path, records: int, max_seq_length: int, probe_dir: Path | None
) -> dict:
    run = log_of(timing_dir)
    again = log_of(resume_dir)
    by_step = {s["step"]: s for s in run["steps"]}
    resumed = {s["step"]: s for s in again["steps"]}
    timed = [s for s in run["steps"] if s["step"] > WARM_UP_STEPS and s["seconds"]]
    per_token = sum(s["seconds"] for s in timed) / sum(s["tokens"] for s in timed)
    evals = [h for h in run["history"] if "eval_runtime" in h]
    eval_seconds = statistics.mean(h["eval_runtime"] for h in evals) if evals else None
    eval_at = {h["step"]: h["eval_runtime"] for h in evals}
    save_seconds = [
        s["seconds_after_step"] - eval_at.get(s["step"], 0) for s in run["saves"]
    ]  # a save's own time, without the evaluation before it
    batch = CONFIG["per_device_train_batch_size"] * CONFIG["gradient_accumulation_steps"]
    full_steps = math.ceil(records / batch)  # one epoch
    full_evals = full_steps // SAVE_STEPS
    training_hours = per_token * run["train_tokens_total"] / 3600
    validation_hours = full_evals * (eval_seconds or 0) / 3600
    projected = training_hours + validation_hours
    saves_hours = full_evals * statistics.mean(save_seconds) / 3600 if save_seconds else None

    steps = range(21, 26)
    began = again["training_began"]
    resume = {
        "first_step_of_the_new_session": again["first_step"],
        "training_began": began,
        "begins_at_the_checkpoint": began["global_step"] == 20 and again["first_step"] == 20,
        "optimizer_state_loaded": began["optimizer_params_with_state"] > 0
        and began["optimizer_state_steps"] == [20.0],
        "scheduler_continues": began["scheduler_steps"] == 20,
        "losses": {"first_run": losses(run, steps), "resumed": losses(again, steps)},
        "learning_rates": {
            "first_run": losses(run, steps, "learning_rate"),
            "resumed": losses(again, steps, "learning_rate"),
        },
        "grad_norms": {
            "first_run": losses(run, steps, "grad_norm"),
            "resumed": losses(again, steps, "grad_norm"),
        },
        "records_at_step_20_first_run": by_step[20]["records"],
        "records_at_step_21": {
            "first_run": by_step[21]["records"],
            "resumed": resumed.get(21, {}).get("records"),
        },
        "records_at_step_1_first_run": by_step[1]["records"],
    }
    resume["same_losses"] = close(*resume["losses"].values())
    resume["same_learning_rates"] = close(*resume["learning_rates"].values())
    resume["same_records"] = all(
        resumed.get(n, {}).get("records") == by_step[n]["records"] for n in steps
    )
    resume["not_the_start_of_the_data"] = resumed.get(21, {}).get("records") != by_step[1][
        "records"
    ] and not (set(resumed.get(21, {}).get("records") or []) & set(by_step[20]["records"]))
    resume["matches"] = all(
        resume[k]
        for k in (
            "begins_at_the_checkpoint",
            "optimizer_state_loaded",
            "scheduler_continues",
            "same_losses",
            "same_learning_rates",
            "same_records",
            "not_the_start_of_the_data",
        )
    )

    best = run.get("best_checkpoint") or ""
    lowest = min(evals, key=lambda h: h["eval_loss"])["step"] if evals else None
    adapter = sorted(timing_dir.rglob("adapter/adapter_model.safetensors"))
    validation = {
        "evaluations": {h["step"]: h["eval_loss"] for h in evals},
        "best_checkpoint": best.rsplit("/", 1)[-1],
        "best_is_the_lowest": bool(evals) and best.endswith(f"checkpoint-{lowest}"),
        "best_adapter_saved": bool(adapter),
        "checkpoints_saved": sorted(s["step"] for s in run["saves"]),
    }
    trained = losses(run, range(1, 10_000))
    normal = []
    for h in evals:
        before = [trained[k] for k in range(h["step"] - 9, h["step"] + 1) if k in trained]
        scale = statistics.mean(before) if before else None
        value = h["eval_loss"]
        normal.append(
            {
                "step": h["step"],
                "eval_loss": value,
                "mean_training_loss_before": round(scale, 4) if scale else None,
                "normal": scale is not None
                and math.isfinite(value)
                and scale / LOSS_SCALE <= value <= scale * LOSS_SCALE,
            }
        )
    longest = run.get("validation_longest") or {}
    validation["losses"] = normal
    validation["longest_validation_record"] = longest
    validation["memory_gb"] = {
        "training_peak": run.get("peak_gpu_memory_gb"),
        "validation_peaks": {v["step"]: v["peak_gb"] for v in run.get("validation_memory") or []},
    }
    validation["works"] = (
        len(evals) >= 2
        and validation["best_is_the_lowest"]
        and validation["best_adapter_saved"]
        and all(n["normal"] for n in normal)
        and bool(longest.get("record_id"))
        and len(validation["memory_gb"]["validation_peaks"]) == len(evals)
    )

    probe = run.get("memory_probe") or probe_of(probe_dir)
    total = probe.get("gpu_total_gb")
    peak = max(run.get("peak_gpu_memory_gb") or 0, probe.get("peak_gb") or 0)
    return {
        "complete": True,
        "gpu": run.get("gpu"),
        "precision": run.get("precision"),
        "seconds_per_token": round(per_token, 6),
        "tokens_timed": sum(s["tokens"] for s in timed),
        "steps_timed": [timed[0]["step"], timed[-1]["step"]],
        "seconds_per_step": round(statistics.mean(s["seconds"] for s in timed), 1),
        "full_run_records": records,
        "full_run_tokens": run["train_tokens_total"],
        "full_run_steps": full_steps,
        "evaluations": full_evals,
        "evaluation_records": EVAL_LIMIT,
        "evaluation_seconds": round(eval_seconds, 1) if eval_seconds else None,
        "training_hours": round(training_hours, 2),
        "validation_hours": round(validation_hours, 2),
        "projected_full_run_hours": round(projected, 2),
        "limit_hours": LIMIT_HOURS,
        "within_limit": projected <= LIMIT_HOURS,
        "beside_it": {
            "checkpoint_saves_hours": round(saves_hours, 2) if saves_hours else None,
            "set_up_seconds_per_session": run.get("seconds_before_training"),
        },
        "validation_and_best_checkpoint": validation,
        "peak_memory_gb": peak,
        "training_peak_memory_gb": run.get("peak_gpu_memory_gb"),
        "gpu_total_gb": total,
        "fits_t4_memory": total is not None and peak < total,
        "longest_record_tokens": probe.get("tokens"),
        "max_seq_length": max_seq_length,
        "resume": resume,
        "resume_matches": resume["matches"],
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
    parser.add_argument("--probe-log", type=Path, help="the kernel log of the memory probe's run")
    parser.add_argument("--max-seq-length", type=int, required=True)
    args = parser.parse_args()
    records = sum(1 for _ in (OUT_DIR / "final" / "train_mix.jsonl").open())
    if args.partial:
        report = partial(args.timing, records, args.max_seq_length)
    elif args.resume is None:
        raise SystemExit("--resume is needed unless --partial")
    else:
        report = timing(args.timing, args.resume, records, args.max_seq_length, args.probe_log)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
