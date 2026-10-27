"""The v3 training run continues across sessions (D-V3-25, D-V3-30). Report only.

From each session's training log (data/generated/v3/kaggle-runs/full-<n>/output/, the small files
the training chain downloads; train.py logs each step's records and the state training began with):

- each session begins at the step the one before ended: its first step, its global step at
  `training_began`, its scheduler's step count and every optimizer state's step all equal the
  previous session's last step;
- the learning rate follows the schedule: linear warmup to the peak, then linear decay to zero at
  the last step (the rate the session began with is the schedule after its first step - 1 steps;
  a logged step's rate, the one that step used, the schedule after the steps before it);
- the record order continues: the steps are numbered without a gap or a repeat across sessions, no
  record is trained twice, and once the last step is reached every record of the training mix has
  been trained exactly once (one full pass, D-V3-30).

The order itself repeating an uninterrupted run was shown by the resume check (D-V3-28).

    uv run python -m scripts.verify.v3_continuity
"""

import json

from training.finetune.data import CONFIG, warmup_steps
from training.generate.v3.config import OUT_DIR

RUNS = OUT_DIR / "kaggle-runs"
STAGES = ("full-1", "full-2", "full-3")


def log_of(stage: str) -> dict | None:
    found = sorted((RUNS / stage / "output").rglob("training-log.json"))
    return json.loads(found[0].read_text()) if found else None


def scheduled(step: int, total: int, warmup: int, peak: float) -> float:
    """The learning rate after `step` optimizer steps (transformers' linear schedule)."""
    if step < warmup:
        return peak * step / max(1, warmup)
    return peak * max(0.0, (total - step) / max(1, total - warmup))


def continuity() -> dict:
    mix = [
        json.loads(line)["metadata"]["record_id"]
        for line in (OUT_DIR / "final/train_mix.jsonl").open()
    ]
    peak = CONFIG["learning_rate"]
    sessions, problems = [], []
    seen: dict[str, int] = {}
    previous = None
    steps_so_far: list[int] = []
    for stage in STAGES:
        log = log_of(stage)
        if log is None:
            continue
        total = log["full_run_steps"]
        batch = CONFIG["per_device_train_batch_size"] * CONFIG["gradient_accumulation_steps"]
        epochs = total / -(-len(mix) // batch)  # the sessions run with --epochs 1, not v2's 2
        warmup = warmup_steps(len(mix), epochs)
        began = log.get("training_began") or {}
        row = {
            "stage": stage,
            "first_step": log["first_step"],
            "last_step": log["last_step"],
            "finished": log["finished"],
            "training_began": began,
        }
        if previous is not None:
            expected = previous["last_step"]
            checks = {
                "first step": log["first_step"] == expected,
                "global step": began.get("global_step") == expected,
                "scheduler": began.get("scheduler_steps") == expected,
                "optimizer state": began.get("optimizer_state_steps") == [float(expected)],
                "learning rate": began.get("learning_rate") is not None
                and abs(began["learning_rate"] - scheduled(expected, total, warmup, peak))
                <= 1e-3 * peak,
            }
            row["continues"] = checks
            problems += [f"{stage}: {name}" for name, ok in checks.items() if not ok]
        rates = [
            (h["step"], h["learning_rate"])
            for h in log["history"]
            if "learning_rate" in h and "loss" in h
        ]
        # a logged step's rate is the one it used: the schedule after the steps before it
        off = [
            s
            for s, r in rates
            if abs(r - scheduled(s - 1, total, warmup, peak)) > 1e-3 * peak + 1e-9
        ]
        row["learning_rates_logged"] = len(rates)
        row["learning_rates_off_schedule"] = off[:5]
        if off:
            problems.append(f"{stage}: {len(off)} learning rates off the schedule")
        for step in log["steps"]:
            steps_so_far.append(step["step"])
            for record in step["records"]:
                if record in seen:
                    problems.append(
                        f"{record} trained at step {seen[record]} and again at {step['step']}"
                    )
                seen[record] = step["step"]
        sessions.append(row)
        previous = log
    numbered = steps_so_far == list(range(1, len(steps_so_far) + 1))
    if not numbered:
        problems.append("the steps are not numbered 1, 2, ... without a gap or a repeat")
    done = previous is not None and previous["last_step"] == previous["full_run_steps"]
    full_pass = set(seen) == set(mix) and len(seen) == len(mix)
    if done and not full_pass:
        problems.append(f"{len(set(mix) - set(seen))} records never trained")
    return {
        "sessions": sessions,
        "steps_logged": len(steps_so_far),
        "records_trained": len(seen),
        "records_in_the_mix": len(mix),
        "every_record_once": full_pass if done else None,
        "problems": problems[:20],
        "ok": not problems and numbered,
    }


if __name__ == "__main__":
    print(json.dumps(continuity(), indent=2))
