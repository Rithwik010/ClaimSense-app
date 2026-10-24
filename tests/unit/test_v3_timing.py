"""The v3 timing summary (scripts/verify/v3_timing.py): the token-based projection, the validation
and best-checkpoint check, and the resume check, on made-up training logs."""

import json
from pathlib import Path

from scripts.verify.v3_timing import LIMIT_HOURS, timing


def ids(step: int) -> list[str]:
    return [f"R{8 * (step - 1) + i:05d}" for i in range(8)]


def history(steps: range, evals: dict[int, float]) -> list[dict]:
    rows = []
    for n in steps:
        rows.append({"step": n, "loss": 1.0 / n, "learning_rate": 1e-5 * n, "grad_norm": 2.0})
        if n in evals:
            rows.append({"step": n, "eval_loss": evals[n], "eval_runtime": 100.0})
    return rows


def write(folder: Path, log: dict) -> Path:
    folder.mkdir(parents=True)
    (folder / "training-log.json").write_text(json.dumps(log))
    return folder


def first_run(tmp_path: Path) -> Path:
    log = {
        "first_step": 0,
        "train_tokens_total": 10_000 * 2_000,
        "training_began": {"global_step": 0, "optimizer_params_with_state": 0},
        "steps": [
            {"step": n, "seconds": 40.0, "tokens": 16_000, "records": ids(n)} for n in range(1, 26)
        ],
        "history": history(range(1, 26), {10: 0.9, 20: 0.8}),
        "saves": [
            {"step": 10, "seconds_after_step": 130.0},
            {"step": 20, "seconds_after_step": 130.0},
            {"step": 25, "seconds_after_step": 30.0},
        ],
        "best_checkpoint": "/kaggle/working/claimsense-v3-timing/checkpoints/checkpoint-20",
        "peak_gpu_memory_gb": 9.0,
        "seconds_before_training": 400,
    }
    folder = write(tmp_path / "timing", log)
    (folder / "adapter").mkdir()
    (folder / "adapter" / "adapter_model.safetensors").write_bytes(b"x")
    return folder


def resumed_run(tmp_path: Path, records=ids) -> Path:  # noqa: ANN001
    log = {
        "first_step": 20,
        "training_began": {
            "global_step": 20,
            "learning_rate": 2e-4,
            "scheduler_steps": 20,
            "optimizer_params_with_state": 400,
            "optimizer_state_steps": [20.0],
        },
        "steps": [
            {"step": n, "seconds": 40.0, "tokens": 16_000, "records": records(n)}
            for n in range(21, 26)
        ],
        "history": history(range(21, 26), {}),
        "saves": [{"step": 25, "seconds_after_step": 30.0}],
    }
    return write(tmp_path / "resume", log)


def probe_log(tmp_path: Path) -> Path:
    folder = tmp_path / "probe"
    folder.mkdir()
    line = 'memory probe: {"tokens": 4416, "peak_gb": 10.49, "gpu_total_gb": 15.64}\n'
    (folder / "run.log").write_text(json.dumps([{"data": line}]))
    return folder


def test_projects_from_tokens_and_passes_the_checks(tmp_path: Path) -> None:
    report = timing(first_run(tmp_path), resumed_run(tmp_path), 10_000, 4608, probe_log(tmp_path))
    per_token = 40.0 / 16_000
    assert report["seconds_per_token"] == round(per_token, 6)
    assert report["steps_timed"] == [6, 25]
    assert report["training_hours"] == round(per_token * 20_000_000 / 3600, 2)  # 13.89
    assert report["validation_hours"] == round(10 * 100.0 / 3600, 2)  # 1,250 steps: 10 passes
    assert report["projected_full_run_hours"] <= LIMIT_HOURS and report["within_limit"]
    assert report["beside_it"]["checkpoint_saves_hours"] is not None
    assert report["validation_and_best_checkpoint"]["works"]
    assert report["peak_memory_gb"] == 10.49 and report["fits_t4_memory"]
    assert report["resume_matches"]
    assert report["resume"]["records_at_step_21"]["resumed"] == ids(21)


def test_a_resume_from_the_start_of_the_data_fails(tmp_path: Path) -> None:
    def from_the_start(step: int) -> list[str]:
        return ids(step - 20)

    report = timing(first_run(tmp_path), resumed_run(tmp_path, from_the_start), 10_000, 4608, None)
    assert not report["resume"]["same_records"]
    assert not report["resume"]["not_the_start_of_the_data"]
    assert not report["resume_matches"]


def test_a_fresh_optimizer_fails(tmp_path: Path) -> None:
    resume = resumed_run(tmp_path)
    log = json.loads((resume / "training-log.json").read_text())
    log["training_began"] |= {"optimizer_params_with_state": 0, "optimizer_state_steps": []}
    (resume / "training-log.json").write_text(json.dumps(log))
    report = timing(first_run(tmp_path), resume, 10_000, 4608, None)
    assert not report["resume"]["optimizer_state_loaded"] and not report["resume_matches"]
