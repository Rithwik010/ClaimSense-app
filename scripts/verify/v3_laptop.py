"""Model v3 on the laptop: the team's checks of 27 Oct before claimsense-decision:v3. Report only.

- `timing`: the same 30 clean records D-MODEL-5 timed v2 and E4B on (the first 30 of the v2 test
  set, data/generated/decision_v2/test.jsonl), on the idle laptop with the demo stack running and
  nothing else at work. The model is loaded first with one request outside the timing, as v2's was
  (its first record took 6 s). Median and p95 seconds per claim, the retry included
  (training/evaluate/model.py `run`).
- `clean`: all 300 clean records on the laptop. Predictions go to data/generated/eval/v3study/
  <label>-clean.jsonl, scored by scripts/verify/v3_eval_report.py exactly as the Kaggle ones.

Request settings are the pipeline's (D-MODEL-7), against the Ollama at OLLAMA_URL. A run starts
from scratch: an earlier prediction file of the same label is removed first.

Repeatability on the 9 demo claims, 3 rounds (D-MODEL-7) is scripts/verify/repeatability.py
`demo_claims`, run from the worktree whose stack serves the API on :8000 (it resets that stack
before each round), with the API and the reset on the model:

    MODEL_NAME=claimsense-decision:v3-best uv run python -c \\
        "from scripts.verify.repeatability import demo_claims; raise SystemExit(not demo_claims(3))"

    uv run python -m scripts.verify.v3_laptop timing --model claimsense-decision:v3-best \\
        --label v3_best_laptop30
    uv run python -m scripts.verify.v3_laptop clean --model claimsense-decision:v3-best \\
        --label v3_best_laptop
"""

import argparse
import json

import httpx

from app.core.settings import get_settings
from app.ml.client import OllamaDecisionModel
from training.evaluate.kaggle_eval import STUDY_DIR
from training.evaluate.model import run
from training.generate.decision_dataset_v2 import OUT_DIR as DATASET_V2
from training.generate.scenarios_v2 import TEST_ONLY_POLICIES

TIMED = 30  # D-MODEL-5's 30 claims


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("what", choices=("timing", "clean"))
    parser.add_argument("--model", required=True)
    parser.add_argument("--label", required=True, help="the model's name in the report files")
    args = parser.parse_args()
    url = get_settings().ollama_url
    version = httpx.get(f"{url}/api/version", timeout=10).json()["version"]
    loaded = httpx.post(  # load the model before the timed claims, as v2's run had it loaded
        f"{url}/api/generate", json={"model": args.model, "keep_alive": -1}, timeout=600
    )
    loaded.raise_for_status()
    label = f"{args.label}-clean"
    STUDY_DIR.mkdir(parents=True, exist_ok=True)
    for suffix in (".jsonl", ".json", ".log"):
        (STUDY_DIR / f"{label}{suffix}").unlink(missing_ok=True)
    report = run(
        OllamaDecisionModel(url, args.model),
        label,
        dataset_dir=DATASET_V2,
        out_dir=STUDY_DIR,
        limit=TIMED if args.what == "timing" else None,
        engine=f"ollama {version}",
        prompt="record",
        test_only=set(TEST_ONLY_POLICIES),
    )
    metrics = report["metrics"]
    print(
        json.dumps(
            {
                "model": args.model,
                "records": metrics["records"],
                "latency_ms": metrics["latency_ms"],
                "valid_output_rate": metrics["valid_output_rate"],
                "macro_f1_guard_off": metrics["decisions"].get("macro_f1"),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
