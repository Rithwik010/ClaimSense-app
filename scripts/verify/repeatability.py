"""Same claim, same answer (D-MODEL-7): fixed request settings give the same answer every time.
Every first attempt is greedy (temperature 0, seed MODEL_SEED); the one retry after an
invalid first answer samples at RETRY_TEMPERATURE with its own fixed seed (D-DEC-1).

1. Retry path: the v2 test claims whose first answer was invalid in the evaluation, each run 3 times
   through the client exactly as the evaluation ran them (first attempt, then the retry when the
   first is invalid). Every run's final answer must equal the other runs' and the answer the
   evaluation stored (data/generated/eval/v2/v2data-model-v2.jsonl).
2. The nine demo claims through the API (running on :8000), in 3 rounds with `make demo-reset`
   before each (a claim can be filed once) and after the last: each claim's status, review tier,
   line decisions and criterion statuses must be the same in every round.

    uv run python -m scripts.verify.repeatability [--runs 3] [--skip-demo]
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import httpx

from app.core.settings import get_settings
from app.ml.client import OllamaDecisionModel
from training.evaluate.model import answer_valid, read_jsonl, score_record
from training.generate.decision_dataset_v2 import OUT_DIR as DATASET_V2

ROOT = Path(__file__).resolve().parents[2]
STORED = ROOT / "data" / "generated" / "eval" / "v2" / "v2data-model-v2.jsonl"
CLAIMS = ROOT / "demo" / "claims"
API = "http://localhost:8000"
MODEL = "claimsense-decision:v2"


def retry_path(runs: int, only: list[str] | None = None) -> bool:
    stored = {r["record_id"]: r for r in read_jsonl(STORED)}
    retried = only or sorted(rid for rid, r in stored.items() if r["attempts"] > 1)
    records = {r["metadata"]["record_id"]: r for r in read_jsonl(DATASET_V2 / "test.jsonl")}
    inputs = {i["record_id"]: i for i in read_jsonl(DATASET_V2 / "test_inputs.jsonl")}
    model = OllamaDecisionModel(get_settings().ollama_url, MODEL)
    ok = True
    print(f"Retry path: {len(retried)} test claims retried in the evaluation, {runs} runs each")
    for record_id in retried:
        system, user = (m["content"] for m in records[record_id]["messages"][:2])
        firsts, retries, answers, decisions = [], [], [], []
        for _ in range(runs):
            text = model.complete(system, user)
            firsts.append(text)
            if not answer_valid(text, inputs[record_id]):
                text = model.complete(system, user, attempt=2)
                retries.append(text)
            answers.append(text)
            scored = score_record(records[record_id], inputs[record_id], text)
            decisions.append((scored["valid"], tuple(x["predicted"] for x in scored["lines"])))
        same = len(set(answers)) == 1 and answers[0] == stored[record_id]["output"]
        ok &= same
        detail = (
            "identical to each other and to the evaluation"
            if same
            else f"{len(set(firsts))} different first answers, {len(set(retries))} different"
            f" retry answers in {len(retries)} retries; final (valid, line decisions) per run"
            f" {decisions}; evaluation {stored[record_id]['valid']},"
            f" {tuple(x['predicted'] for x in stored[record_id]['lines'])}"
        )
        print(f"  {'ok  ' if same else 'FAIL'} {record_id}: {detail}")
    return ok


def outcome(record: dict[str, Any]) -> dict[str, Any]:
    slm = record.get("slm_output") or {}
    return {
        "status": record["status"],
        "review_tier": record.get("review_tier"),
        "lines": [(d["line_no"], d["decision"]) for d in record.get("line_decisions", [])],
        "criteria": [
            (line["line_no"], c["criterion_id"], c["status"])
            for line in slm.get("lines", [])
            for c in line.get("criteria", [])
        ],
    }


def demo_round(api: httpx.Client) -> dict[str, dict[str, Any]]:
    results = {}
    for path in sorted(CLAIMS.iterdir()):
        if path.suffix == ".json":
            filed = api.post("/v1/claims/intake", json=json.loads(path.read_text()))
        else:
            filed = api.post("/v1/claims/intake/file", content=path.read_bytes())
        filed.raise_for_status()
        body = filed.json()  # an IntakeResult, or a claim filed with contract errors
        claim_id = body["claim"]["claim_id"] if "claim" in body else body["claim_id"]
        processed = api.post(f"/v1/claims/{claim_id}/process")
        processed.raise_for_status()
        results[path.name] = outcome(processed.json())
    return results


def reset() -> None:
    subprocess.run(["make", "demo-reset"], cwd=ROOT, check=True, capture_output=True)


def demo_claims(runs: int) -> bool:
    api = httpx.Client(base_url=API, timeout=300)
    rounds = []
    print(f"Demo claims: {runs} rounds through the API, a reset before each")
    for n in range(runs):
        reset()
        rounds.append(demo_round(api))
        print(f"  round {n + 1} done")
    reset()
    ok = True
    for name, first in rounds[0].items():
        same = all(r[name] == first for r in rounds[1:])
        ok &= same
        lines = " ".join(f"{no}:{d}" for no, d in first["lines"]) or "-"
        print(
            f"  {'ok  ' if same else 'FAIL'} {name}: {first['status']}, lines {lines},"
            f" {len(first['criteria'])} criteria" + ("" if same else " - rounds differ")
        )
    return ok


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--skip-demo", action="store_true")
    parser.add_argument("--record", action="append", help="only these test records (repeat)")
    args = parser.parse_args()
    ok = retry_path(args.runs, args.record)
    if not args.skip_demo:
        ok &= demo_claims(args.runs)
    print("All identical." if ok else "Differences found.")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
