"""The Kaggle evaluation runner (training/evaluate/kaggle_eval.py) loads without qdrant_client: the
Kaggle image does not have it, and step 8's third attempt failed on that import (24 Oct)."""

import json
import subprocess
import sys

RUNNER = """
import sys
sys.modules["qdrant_client"] = None  # importing it now raises ImportError
import training.evaluate.kaggle_eval as kaggle_eval
from app.ml.client import OllamaDecisionModel
from training.evaluate.model import run
assert callable(kaggle_eval.run_jobs) and callable(run) and OllamaDecisionModel
"""


def test_the_kaggle_runner_imports_without_qdrant() -> None:
    done = subprocess.run([sys.executable, "-c", RUNNER], capture_output=True, text=True)
    assert done.returncode == 0, done.stderr[-2000:]


def test_skip_leaves_out_only_the_named_model_and_set(tmp_path, monkeypatch) -> None:  # noqa: ANN001
    """Stage 5: v2 runs on the test sets it is compared on, not on validation (D-V3-23)."""
    from training.evaluate import kaggle_eval

    entry = {"ollama": "0.34.1", "kernel": "k", "name": "m", "weights_sha256": "0" * 64}
    monkeypatch.setattr(kaggle_eval, "copy_code", lambda dataset: None)
    monkeypatch.setattr(kaggle_eval, "model_entry", lambda key, url: entry)
    monkeypatch.setattr(kaggle_eval, "write_set", lambda s, dataset: {"shard-0": 2, "shard-1": 2})
    skip = frozenset({"v2:validation"})
    found = kaggle_eval.prepare(
        "t", ["v2", "v3_final"], ["clean", "validation"], tmp_path, skip=skip
    )
    run = json.loads((tmp_path / "t" / "dataset" / "run.json").read_text())
    pairs = sorted({(job["model"], job["set"]) for job in run["jobs"]})
    assert pairs == [("v2", "clean"), ("v3_final", "clean"), ("v3_final", "validation")]
    assert found["jobs"] == 6 and {job["gpu"] for job in run["jobs"]} == {0, 1}


def test_the_upload_check_still_needs_the_generator() -> None:
    """prepare() imports the v3 upload check itself, so it keeps working on the laptop."""
    from training.evaluate import kaggle_eval

    assert "upload_problems" not in vars(kaggle_eval)
    from training.generate.v3.kaggle import upload_problems

    assert callable(upload_problems)
