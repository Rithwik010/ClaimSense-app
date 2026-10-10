"""Exact token counts of the longest decision records (Part 2 step 2): each record's messages
(system, user and the assistant target) are sent to the local Ollama base model, whose
`prompt_eval_count` is the number of tokens the Gemma 4 chat template gives them. The model is
unloaded after every request (`keep_alive: 0`), so no cached prefix lowers a count. Compared with
the training maximum length (`MAX_LENGTH` of training/finetune).

    uv run python -m scripts.verify.token_lengths data/generated/decision_v2 [--top 12]
"""

import argparse
import json
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[2]
TRAINING_MAX_LENGTH = 3072  # model v1's QLoRA run (docs/fine-tuning.md)
SPLITS = ("train", "validation", "test")


def tokens(messages: list[dict[str, str]], model: str, host: str) -> int:
    response = httpx.post(
        f"{host}/api/chat",
        json={
            "model": model,
            "messages": messages,
            "stream": False,
            "keep_alive": 0,
            "think": False,
            "options": {"num_predict": 1, "temperature": 0},
        },
        timeout=300,
    )
    response.raise_for_status()
    return int(response.json()["prompt_eval_count"])


def longest(dataset: Path, top: int) -> list[dict[str, Any]]:
    records = []
    for split in SPLITS:
        for line in (dataset / f"{split}.jsonl").read_text(encoding="utf-8").splitlines():
            record = json.loads(line)
            size = sum(len(m["content"]) for m in record["messages"])
            records.append({"split": split, "size": size, "record": record})
    return sorted(records, key=lambda r: -r["size"])[:top]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--top", type=int, default=12)
    parser.add_argument("--model", default="gemma4:e2b")
    parser.add_argument("--host", default="http://localhost:11434")
    args = parser.parse_args()
    rows = []
    for item in longest(args.dataset, args.top):
        record = item["record"]
        count = tokens(record["messages"], args.model, args.host)
        rows.append(
            {
                "record_id": record["metadata"]["record_id"],
                "split": item["split"],
                "characters": item["size"],
                "tokens": count,
                "characters_per_token": round(item["size"] / count, 2),
            }
        )
        print(json.dumps(rows[-1]))
    report = {
        "model": args.model,
        "training_max_length": TRAINING_MAX_LENGTH,
        "longest_tokens": max(r["tokens"] for r in rows),
        "over_max_length": sum(r["tokens"] > TRAINING_MAX_LENGTH for r in rows),
        "records": rows,
    }
    (args.dataset / "token_lengths.json").write_text(json.dumps(report, indent=2) + "\n")
    print(
        f"longest {report['longest_tokens']} tokens vs max length {TRAINING_MAX_LENGTH}; "
        f"{report['over_max_length']} of the {len(rows)} longest records are over it"
    )


if __name__ == "__main__":
    main()
