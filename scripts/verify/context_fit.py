"""Does every v2 test record fit the model's context window (num_ctx), prompt plus answer?

Ollama loads the decision models with a 4,096-token context by default (its VRAM-based default)
and with context shift on, so a prompt plus answer longer than num_ctx silently loses its oldest
tokens. For each record of data/generated/decision_v2/test.jsonl:

- model v1: its prompt decision_v2 re-rendered from the record's inputs (as the v2 evaluation
  sends it) plus its actual answer from data/generated/eval/v2/v2data-model-v1.jsonl (the gold
  answer where it has not answered yet);
- model v2: the record's own prompt decision_v3 plus the gold answer;
- both: the prompt plus the client's answer cap (MAX_OUTPUT_TOKENS), the worst case.

Estimate mode (default, no Ollama): tokens = characters / the lowest characters-per-token ratio
measured on the v2 records (token_lengths.json). Exact mode (--exact N): the N longest are
counted by Ollama, prompt and answer together (prompt_eval_count of the base model's chat
template over system, user and the answer as the model turn, keep_alive 0); do not run it while
an evaluation is using Ollama.

    uv run python -m scripts.verify.context_fit [--exact 12] [--num-ctx 4096]
"""

import argparse
import json
from pathlib import Path
from typing import Any

from app.ml.client import MAX_OUTPUT_TOKENS
from scripts.verify.token_lengths import tokens
from training.evaluate.model import v1_prompt_renderer

ROOT = Path(__file__).resolve().parents[2]
DATASET = ROOT / "data" / "generated" / "decision_v2"
PREDICTIONS_V1 = ROOT / "data" / "generated" / "eval" / "v2" / "v2data-model-v1.jsonl"
TEMPLATE_OVERHEAD = 32  # chat-template turn markers, generously


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def rows() -> list[dict[str, Any]]:
    render = v1_prompt_renderer()
    answers = {r["record_id"]: r.get("output") or "" for r in read_jsonl(PREDICTIONS_V1)}
    inputs = {r["record_id"]: r for r in read_jsonl(DATASET / "test_inputs.jsonl")}
    out = []
    for record in read_jsonl(DATASET / "test.jsonl"):
        rid = record["metadata"]["record_id"]
        system, user = render(inputs[rid])
        messages = {m["role"]: m["content"] for m in record["messages"]}
        gold = messages["assistant"]
        out.append(
            {
                "record_id": rid,
                "v1_messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "v1_prompt_chars": len(system) + len(user),
                "v1_answer_text": answers.get(rid) or gold,
                "v1_answer_chars": len(answers.get(rid) or gold),
                "v1_answered": bool(answers.get(rid)),
                "v2_messages": [
                    {"role": "system", "content": messages["system"]},
                    {"role": "user", "content": messages["user"]},
                ],
                "v2_prompt_chars": len(messages["system"]) + len(messages["user"]),
                "v2_answer_text": gold,
                "v2_answer_chars": len(gold),
            }
        )
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--num-ctx", type=int, default=4096)
    parser.add_argument("--exact", type=int, default=0, help="count the N longest with Ollama")
    parser.add_argument("--model", default="gemma4:e2b")
    parser.add_argument("--host", default="http://localhost:11434")
    args = parser.parse_args()
    lengths = json.loads((DATASET / "token_lengths.json").read_text())
    ratio = min(r["characters_per_token"] for r in lengths["records"])
    found = rows()
    report = {"num_ctx": args.num_ctx, "chars_per_token": ratio, "answer_cap": MAX_OUTPUT_TOKENS}
    for model in ("v1", "v2"):
        for r in found:
            r[f"{model}_prompt"] = round(r[f"{model}_prompt_chars"] / ratio) + TEMPLATE_OVERHEAD
            r[f"{model}_answer"] = round(r[f"{model}_answer_chars"] / ratio)
        if args.exact:
            sizes = [r[f"{model}_prompt_chars"] + r[f"{model}_answer_chars"] for r in found]
            order = sorted(range(len(found)), key=lambda i: -sizes[i])
            for r in (found[i] for i in order[: args.exact]):
                prompt = tokens(r[f"{model}_messages"], args.model, args.host)
                answer = {"role": "assistant", "content": r[f"{model}_answer_text"]}
                both = tokens([*r[f"{model}_messages"], answer], args.model, args.host)
                r[f"{model}_prompt"], r[f"{model}_answer"] = prompt, both - prompt
                r[f"{model}_exact"] = True
        totals = [r[f"{model}_prompt"] + r[f"{model}_answer"] for r in found]
        worst = [r[f"{model}_prompt"] + MAX_OUTPUT_TOKENS for r in found]
        report[model] = {
            "exact_counts": sum(bool(r.get(f"{model}_exact")) for r in found),
            "longest_prompt": max(r[f"{model}_prompt"] for r in found),
            "longest_answer": max(r[f"{model}_answer"] for r in found),
            "longest_prompt_plus_answer": max(totals),
            "over_num_ctx": sum(t > args.num_ctx for t in totals),
            "longest_prompt_plus_answer_cap": max(worst),
            "over_num_ctx_with_answer_cap": sum(t > args.num_ctx for t in worst),
            "records_over": [
                r["record_id"] for r, t in zip(found, totals, strict=True) if t > args.num_ctx
            ],
        }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
