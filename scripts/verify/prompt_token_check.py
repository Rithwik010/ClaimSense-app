"""The prompt token guard counts what Ollama counts (D-DOC-3). Report only.

For real prompts (system and user messages of decision records: the given JSONL files, the longest
first and a spread of the rest), compares app/ml/tokens.py `prompt_tokens` with the
`prompt_eval_count` Ollama reports for the same messages, on the base model `COUNTER` (the decision
models' tokenizer and chat renderer; the decision models themselves are not used), with the
pipeline's context size. Each prompt is counted fresh (`keep_alive` 0: the model is unloaded after
every request, so no earlier prompt is in its cache), then once more right away, warm, to see
whether Ollama's cache lowers its count (with Ollama 0.34.1 it did not: 25 Oct, 26 prompts).
Every fresh count must equal the guard's; any difference is listed. Writes
data/generated/eval/prompt_token_check.json.

    uv run python -m scripts.verify.prompt_token_check <records.jsonl> [...] [--count 25]
"""

import argparse
import json
from pathlib import Path

import httpx

from app.core.settings import get_settings
from app.ml.client import MODEL_NUM_CTX
from app.ml.tokens import prompt_tokens

COUNTER = "gemma4:e2b"


def ollama_count(url: str, system: str, user: str, keep_alive: int | str) -> int:
    reply = httpx.post(
        f"{url}/api/chat",
        json={
            "model": COUNTER,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
            "think": False,
            "keep_alive": keep_alive,
            "options": {"num_ctx": MODEL_NUM_CTX, "num_predict": 1, "temperature": 0},
        },
        timeout=600,
    )
    reply.raise_for_status()
    return reply.json()["prompt_eval_count"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("records", nargs="+", type=Path)
    parser.add_argument("--count", type=int, default=25)
    args = parser.parse_args()
    settings = get_settings()
    prompts = []
    for path in args.records:
        for line in path.open(encoding="utf-8"):
            record = json.loads(line)
            system, user = record["messages"][0]["content"], record["messages"][1]["content"]
            prompts.append((record["metadata"]["record_id"], system, user))
    prompts.sort(key=lambda p: -len(p[2]))
    longest = prompts[: args.count // 2]
    rest = prompts[args.count // 2 :]
    step = max(1, len(rest) // (args.count - len(longest)))
    chosen = longest + rest[::step][: args.count - len(longest)]
    rows = []
    for record_id, system, user in chosen:
        ours = prompt_tokens(system, user, settings.prompt_tokenizer)
        fresh = ollama_count(settings.ollama_url, system, user, 0)
        warm_first = ollama_count(settings.ollama_url, system, user, "1m")
        warm = ollama_count(settings.ollama_url, system, user, 0)
        rows.append(
            {
                "record_id": record_id,
                "characters": len(system) + len(user),
                "guard": ours,
                "ollama_fresh": fresh,
                "ollama_warm": warm,
                "ollama_load_then": warm_first,
                "difference": fresh - ours,
            }
        )
        print(json.dumps(rows[-1]), flush=True)
    report = {
        "counted_with": COUNTER,
        "num_ctx": MODEL_NUM_CTX,
        "prompts": len(rows),
        "equal_when_fresh": sum(r["difference"] == 0 for r in rows),
        "differences": sorted({r["difference"] for r in rows}),
        "warm_lower_by": sorted({r["ollama_fresh"] - r["ollama_warm"] for r in rows})[:5],
        "largest_prompt_tokens": max(r["guard"] for r in rows),
        "rows": rows,
    }
    out = Path(__file__).resolve().parents[2] / "data/generated/eval/prompt_token_check.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k != "rows"}, indent=2))


if __name__ == "__main__":
    main()
