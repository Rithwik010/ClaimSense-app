"""The v3 training run's pace after a session (D-V3-25). Report only; the training chain
(scripts/kaggle/v3_train.sh) reads its JSON to decide what to run next.

From the training log of a session's downloaded output (training/finetune/train.py):

- `state`: `finished` (the last step: the adapters are saved), `stopped_early` (early stopping
  ended it before the last step: the team wants every step, D-V3-30), `paused` (the
  session's safety stop: its checkpoint is the result) or `crashed` (no training log: the step is
  then its latest checkpoint's, and the pace the timing run's, data/generated/v3/timing/
  summary.json);
- the last step reached, of the run's steps (one epoch of the training mix);
- the seconds per step this session measured (training-loop time over its steps, validation passes
  and saves included);
- `projected_training_hours`: every step of the run at that pace (the run's training and
  validation, as go / no-go item f counts them);
- `remaining_hours`: the steps left at that pace, plus `FINAL_SESSION_HOURS` for the last session's
  set-up and last save.

    uv run python -m scripts.verify.v3_pace <session output folder>
"""

import json
import sys
from pathlib import Path

from training.generate.v3.config import OUT_DIR

FINAL_SESSION_HOURS = 0.15  # set-up and the last save (the GGUF exports run on CPU, D-V3-26)
TIMING = OUT_DIR / "timing" / "summary.json"


def crashed(folder: Path) -> dict:
    states = [json.loads(p.read_text()) for p in folder.rglob("trainer_state.json")]
    timing = json.loads(TIMING.read_text())
    per_step = timing["projected_full_run_hours"] * 3600 / timing["full_run_steps"]
    total = timing["full_run_steps"]
    step = max((s["global_step"] for s in states), default=0)
    return {
        "state": "crashed",
        "checkpoint": bool(states),
        "last_step": step,
        "full_run_steps": total,
        "seconds_per_step": round(per_step, 1),
        "projected_training_hours": timing["projected_full_run_hours"],
        "remaining_hours": round((total - step) * per_step / 3600 + FINAL_SESSION_HOURS, 2),
    }


def pace(folder: Path) -> dict:
    found = sorted(folder.rglob("training-log.json"))
    if not found:
        return crashed(folder)
    log = json.loads(found[0].read_text())
    steps = max(log["last_step"] - log["first_step"], 1)
    per_step = log["train_runtime_seconds"] / steps
    total = log["full_run_steps"]
    left = max(total - log["last_step"], 0)
    return {
        "state": ("finished" if not left else "stopped_early") if log["finished"] else "paused",
        "checkpoint": any(folder.rglob("trainer_state.json")),
        "first_step": log["first_step"],
        "last_step": log["last_step"],
        "full_run_steps": total,
        "seconds_per_step": round(per_step, 1),
        "session_hours": log.get("session_hours"),
        "projected_training_hours": round(total * per_step / 3600, 2),
        "remaining_hours": round(left * per_step / 3600 + FINAL_SESSION_HOURS, 2) if left else 0,
        "best_checkpoint": log.get("best_checkpoint"),
    }


if __name__ == "__main__":
    print(json.dumps(pace(Path(sys.argv[1]))))
