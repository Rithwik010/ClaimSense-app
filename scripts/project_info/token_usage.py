"""Token usage of the decision model (docs/PROJECT_INFO.md section 7.3).

Each record's system and user messages go to the model through the pipeline's own client
(`app.ml.client.OllamaDecisionModel.complete`: the SLMOutput schema as the format,
`request_options(attempt)`, thinking off, keep_alive -1). The client's `chat` call is wrapped only
to keep Ollama's whole response, so nothing about the request changes. As in the pipeline
(`app/workflow/pipeline.py`), an invalid first answer gets one retry (attempt 2). Ollama reports
`prompt_eval_count` (input tokens) and `eval_count` (output tokens) for every call.

Records are sent one at a time. Before the sample, one cache probe sends the first record twice:
if the two `prompt_eval_count` values differ, Ollama's prompt cache lowers the count and the report
says so.

Sets (one per run):
- clean: decision_v2 test records (the first N, by default the 30 claims of the latency runs,
  DV2-TE-00001 to DV2-TE-00030), notes as generator v2 writes them;
- messy: v3 test_messy records from a v3 build (`--dataset` pointing at its `final/` folder).

Output (git-ignored, aggregates and per-record counts; the answers are kept for section 7.4):
`data/generated/project_info/token_usage_<set>.json`.

    uv run python -m scripts.project_info.token_usage --set clean \
        --dataset ../ClaimSense/data/generated/decision_v2 --split test --limit 30
    uv run python -m scripts.project_info.token_usage --set messy \
        --dataset ../claimsense-v3/data/generated/v3/final --split test_messy --limit 30
"""

import argparse
import json
import statistics
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.domain.contracts import RulesOutcome
from app.ml.client import OllamaDecisionModel, request_options
from app.ml.prompt import lines_to_decide
from training.evaluate.model import answer_valid, read_jsonl

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "data" / "generated" / "project_info"
MODEL = "claimsense-decision:v2"
HOST = "http://localhost:11434"


class RecordingModel:
    """The pipeline's client with its `chat` call wrapped to keep each response."""

    def __init__(self, host: str, name: str) -> None:
        self.model = OllamaDecisionModel(host, name)
        self.responses: list[Any] = []
        chat = self.model._client.chat

        def recording_chat(*args: Any, **kwargs: Any) -> Any:
            response = chat(*args, **kwargs)
            self.responses.append(response)
            return response

        self.model._client.chat = recording_chat  # type: ignore[method-assign]

    def complete(self, system: str, user: str, attempt: int) -> tuple[str, dict[str, Any]]:
        text = self.model.complete(system, user, attempt=attempt)
        r = self.responses[-1]
        return text, {
            "attempt": attempt,
            "options": request_options(attempt),
            "prompt_eval_count": r.prompt_eval_count,
            "eval_count": r.eval_count,
            "total_ms": round((r.total_duration or 0) / 1e6, 1),
            "load_ms": round((r.load_duration or 0) / 1e6, 1),
            "prompt_eval_ms": round((r.prompt_eval_duration or 0) / 1e6, 1),
            "eval_ms": round((r.eval_duration or 0) / 1e6, 1),
        }


def describe(values: list[float]) -> dict[str, float]:
    """Mean, median and p95 (nearest rank, as the evaluation's p95: index int(0.95 * (n - 1)))."""
    ordered = sorted(values)
    return {
        "n": len(ordered),
        "mean": round(statistics.fmean(ordered), 1),
        "median": round(statistics.median(ordered), 1),
        "p95": round(ordered[int(0.95 * (len(ordered) - 1))], 1),
        "min": ordered[0],
        "max": ordered[-1],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--set", required=True, choices=["clean", "messy"])
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--split", required=True)
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--host", default=HOST)
    args = parser.parse_args()

    records = read_jsonl(args.dataset / f"{args.split}.jsonl")[: args.limit]
    inputs = {i["record_id"]: i for i in read_jsonl(args.dataset / f"{args.split}_inputs.jsonl")}
    model = RecordingModel(args.host, args.model)

    first = records[0]
    system, user = first["messages"][0]["content"], first["messages"][1]["content"]
    probe = [model.complete(system, user, attempt=1)[1] for _ in range(2)]
    cache_probe = {
        "record_id": first["metadata"]["record_id"],
        "prompt_eval_counts": [p["prompt_eval_count"] for p in probe],
        "same": probe[0]["prompt_eval_count"] == probe[1]["prompt_eval_count"],
    }
    print(json.dumps({"cache_probe": cache_probe}), flush=True)

    rows = []
    for n, record in enumerate(records, start=1):
        record_id = record["metadata"]["record_id"]
        system, user = record["messages"][0]["content"], record["messages"][1]["content"]
        rules = RulesOutcome.model_validate(inputs[record_id]["rules_outcome"])
        model_lines = len(lines_to_decide(rules))
        t0 = time.perf_counter()
        text, call = model.complete(system, user, attempt=1)
        calls = [call]
        valid = answer_valid(text, inputs[record_id])
        if not valid:  # the pipeline's one retry (D-DEC-1)
            text, call = model.complete(system, user, attempt=2)
            calls.append(call)
            valid = answer_valid(text, inputs[record_id])
        row = {
            "record_id": record_id,
            "model_lines": model_lines,
            "system_characters": len(system),
            "user_characters": len(user),
            "attempts": len(calls),
            "valid": valid,
            "calls": calls,
            "input_tokens": sum(c["prompt_eval_count"] for c in calls),
            "output_tokens": sum(c["eval_count"] for c in calls),
            "first_input_tokens": calls[0]["prompt_eval_count"],
            "first_output_tokens": calls[0]["eval_count"],
            "retry_tokens": sum(c["prompt_eval_count"] + c["eval_count"] for c in calls[1:]),
            "client_ms": round((time.perf_counter() - t0) * 1000, 1),
            "answer": text,
        }
        rows.append(row)
        print(
            f"{n}/{len(records)} {record_id} lines={model_lines} attempts={len(calls)} "
            f"in={row['input_tokens']} out={row['output_tokens']} {row['client_ms']:.0f}ms",
            flush=True,
        )

    def per_line(key: str) -> list[float]:
        return [r[key] / r["model_lines"] for r in rows if r["model_lines"]]

    summary = {
        "set": args.set,
        "dataset": str(args.dataset),
        "split": args.split,
        "records": len(rows),
        "first_record": rows[0]["record_id"],
        "last_record": rows[-1]["record_id"],
        "model": args.model,
        "measured_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "cache_probe": cache_probe,
        "model_lines": sum(r["model_lines"] for r in rows),
        "retried_records": sum(r["attempts"] > 1 for r in rows),
        "valid_records": sum(r["valid"] for r in rows),
        "per_claim": {
            "input_tokens": describe([r["input_tokens"] for r in rows]),
            "output_tokens": describe([r["output_tokens"] for r in rows]),
            "first_attempt_input_tokens": describe([r["first_input_tokens"] for r in rows]),
            "first_attempt_output_tokens": describe([r["first_output_tokens"] for r in rows]),
            "client_ms": describe([r["client_ms"] for r in rows]),
        },
        "per_line": {
            "input_tokens": describe(per_line("input_tokens")),
            "output_tokens": describe(per_line("output_tokens")),
        },
        "retry": {
            "extra_tokens_total": sum(r["retry_tokens"] for r in rows),
            "extra_tokens_per_claim_mean": round(
                sum(r["retry_tokens"] for r in rows) / len(rows), 1
            ),
            "all_tokens_total": sum(r["input_tokens"] + r["output_tokens"] for r in rows),
        },
        "rows": rows,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"token_usage_{args.set}.json"
    out.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "rows"}, indent=2))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
