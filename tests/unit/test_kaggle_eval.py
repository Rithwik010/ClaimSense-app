"""The Kaggle evaluation runner (training/evaluate/kaggle_eval.py) loads without qdrant_client: the
Kaggle image does not have it, and step 8's third attempt failed on that import (24 Oct)."""

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


def test_the_upload_check_still_needs_the_generator() -> None:
    """prepare() imports the v3 upload check itself, so it keeps working on the laptop."""
    from training.evaluate import kaggle_eval

    assert "upload_problems" not in vars(kaggle_eval)
    from training.generate.v3.kaggle import upload_problems

    assert callable(upload_problems)
