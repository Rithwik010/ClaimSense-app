"""Resuming fine-tuning in a second Kaggle session (D-V3-9): the checkpoint `--resume-from` picks.
The resume itself (step count and loss carrying on) is proved on the GPU in the timing run."""

import json
from pathlib import Path

import pytest

from training.finetune.train import latest_checkpoint


def checkpoint(root: Path, step: int) -> Path:
    path = root / "claimsense" / "checkpoints" / f"checkpoint-{step}"
    path.mkdir(parents=True)
    (path / "trainer_state.json").write_text(json.dumps({"global_step": step}))
    return path


def test_the_latest_checkpoint_under_a_session_output_is_picked(tmp_path: Path) -> None:
    for step in (125, 250, 1000):
        checkpoint(tmp_path, step)
    (tmp_path / "claimsense" / "checkpoints" / "checkpoint-2000").mkdir()  # no state: incomplete

    assert latest_checkpoint(tmp_path).name == "checkpoint-1000"


def test_a_checkpoint_folder_is_used_as_given(tmp_path: Path) -> None:
    given = checkpoint(tmp_path, 20)
    checkpoint(tmp_path, 40)

    assert latest_checkpoint(given) == given


def test_no_checkpoint_stops(tmp_path: Path) -> None:
    with pytest.raises(SystemExit, match="no checkpoint"):
        latest_checkpoint(tmp_path)
