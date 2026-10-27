"""Prompt tokens against the model's context window, by attachment pages (the team's request of
25 Oct: the multi-page intake's page limit, D-DOC-3). Report only.

Counts the full prompt (system and user message, through the model's chat template) of v3 records
with the base model's tokenizer: Ollama's `gemma4:e2b` (the tokenizer v2 and v3 share; the decision
models themselves are not used), `num_ctx` raised so nothing is cut and one token generated, its
`prompt_eval_count`. The records: every 3-page claim of the rendered set (data/generated/v3/
rendered/index.json; notes stuck in a loop were left out of it) and a spread of 2-page ones. From
them a line fits prompt tokens against the notes' rendered lines (training/generate/forms.py
`notes_lines`), and the largest prompt is estimated for each number of pages: the most tokens
outside the notes seen, plus every attachment page full (`notes_capacity()` lines each). A claim
fits when its prompt plus the answer's budget (`num_predict`) is at most `num_ctx`, both from v2's
evaluated settings (training/finetune/evaluated/claimsense-decision-v2.json).

    uv run python -m scripts.verify.v3_prompt_tokens [--ollama http://localhost:11434]
"""

import argparse
import json
import random

import httpx

from training.finetune.modelfile import evaluated
from training.generate.forms import notes_capacity
from training.generate.v3.config import OUT_DIR

COUNTER = "gemma4:e2b"
SPREAD = 30  # 2-page claims added to the fit
SEED = 20261025


def count(url: str, messages: list[dict]) -> int:
    reply = httpx.post(
        f"{url}/api/chat",
        json={
            "model": COUNTER,
            "messages": messages,
            "stream": False,
            "think": False,
            "options": {"num_ctx": 32768, "num_predict": 1, "temperature": 0},
        },
        timeout=600,
    )
    reply.raise_for_status()
    return reply.json()["prompt_eval_count"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--ollama", default="http://localhost:11434")
    args = parser.parse_args()
    index = json.loads((OUT_DIR / "rendered" / "index.json").read_text())["claims"]
    records = {}
    for split in {c["split"] for c in index}:
        for line in (OUT_DIR / "final" / f"{split}.jsonl").open():
            record = json.loads(line)
            records[record["metadata"]["record_id"]] = record
    three = [c for c in index if c["pages"] >= 3]
    two = random.Random(SEED).sample([c for c in index if c["pages"] == 2], SPREAD)
    rows = []
    for claim in three + two:
        record = records[claim["record_id"]]
        messages = record["messages"][:2]

        lines = claim["note_lines"]
        tokens = count(args.ollama, messages)
        rows.append(
            {
                "record_id": claim["record_id"],
                "pages": claim["pages"],
                "note_lines": lines,
                "prompt_characters": sum(len(m["content"]) for m in messages),
                "prompt_tokens": tokens,
            }
        )

    n = len(rows)
    mx = sum(r["note_lines"] for r in rows) / n
    my = sum(r["prompt_tokens"] for r in rows) / n
    slope = sum((r["note_lines"] - mx) * (r["prompt_tokens"] - my) for r in rows) / sum(
        (r["note_lines"] - mx) ** 2 for r in rows
    )
    outside = max(r["prompt_tokens"] - slope * r["note_lines"] for r in rows)
    pinned = evaluated("claimsense-decision:v2")
    num_ctx = pinned["requests"]["first"]["num_ctx"]
    answer = pinned["requests"]["first"]["num_predict"]
    capacity = notes_capacity()
    estimate = {}
    for pages in range(2, 9):
        prompt = round(outside + slope * capacity * (pages - 1))
        estimate[pages] = {
            "notes_lines": capacity * (pages - 1),
            "largest_prompt_tokens": prompt,
            "with_answer_budget": prompt + answer,
            "fits": prompt + answer <= num_ctx,
        }
    longest = max((r for r in rows if r["pages"] >= 3), key=lambda r: r["note_lines"])
    report = {
        "counted_with": COUNTER,
        "num_ctx": num_ctx,
        "answer_budget_num_predict": answer,
        "prompt_budget": num_ctx - answer,
        "records_counted": n,
        "tokens_per_notes_line": round(slope, 2),
        "most_tokens_outside_the_notes": round(outside),
        "longest_three_page_render": longest,
        "estimate_by_pages": estimate,
        "largest_page_count_that_fits": max(p for p, e in estimate.items() if e["fits"]),
        "counted": rows,
    }
    (OUT_DIR / "prompt_tokens.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k != "counted"}, indent=2))


if __name__ == "__main__":
    main()
