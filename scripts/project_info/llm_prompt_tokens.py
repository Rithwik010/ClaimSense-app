"""SLM vs general LLM token comparison: an ESTIMATE (docs/PROJECT_INFO.md section 7.4).

No LLM is called. For the same claims as section 7.3 (the rows of
`data/generated/project_info/token_usage_<set>.json`), this builds the prompt a general LLM without
our fine-tuning would need, and counts its tokens with tiktoken's `o200k_base` encoding:

1. system: the decision_v3 system prompt the SLM gets (the record's own system message);
2. output schema: the SLMOutput JSON schema as text (the SLM gets it as Ollama's `format`, which
   constrains decoding and is not part of its prompt);
3. worked examples: three fixed examples from the v2 training split (the first single-line record
   whose claim decision is APPROVE, PEND and DENY), each as its user message and target answer;
4. user: the record's own user message (claim, rules result, plan benefits, the criteria shown);
5. policy documents: the full text of every v2 coverage policy the claim's criteria come from
   (`data/curated/coverage_policies/v2/<policy>.md`, every criterion with its type, codes and
   source), not only the criteria the exact lookup returns for each line.

Output tokens, two estimates:
- without reasoning: the SLM's own final answer for that claim (from section 7.3), counted with
  o200k_base; a general LLM is assumed to answer with the same JSON;
- with step-by-step reasoning: that JSON plus one reasoning paragraph per criterion it lists (the
  criterion's ID, type and text, the evidence it quotes and the status) and one sentence per line
  (its decision), built from the record's context and the answer and counted the same way. Real
  reasoning may be longer or shorter; this only shows the scale.

The SLM's prompt is also counted with o200k_base, so the ratio compares like with like; Ollama's
Gemma counts (section 7.3) include Gemma's chat-template tokens and use another tokenizer.

    uv run --with tiktoken python -m scripts.project_info.llm_prompt_tokens --set clean \
        --dataset ../ClaimSense/data/generated/decision_v2 --split test \
        --train ../ClaimSense/data/generated/decision_v2/train.jsonl
"""

import argparse
import json
import statistics
from pathlib import Path
from typing import Any

import tiktoken

from app.domain.contracts import SLMOutput
from training.evaluate.model import read_jsonl

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "data" / "generated" / "project_info"
POLICIES = ROOT / "data" / "curated" / "coverage_policies" / "v2"
ENCODING = "o200k_base"


def examples(train: Path) -> list[dict[str, Any]]:
    """The first single-line training record for each claim decision: APPROVE, PEND, DENY."""
    wanted = ["APPROVE", "PEND", "DENY"]
    found: dict[str, dict[str, Any]] = {}
    for record in read_jsonl(train):
        meta = record["metadata"]
        model_lines = [x for x in meta["line_labels"] if x["source"] == "MODEL"]
        decision = meta["claim_decision"]
        if decision in wanted and decision not in found and len(model_lines) == 1:
            found[decision] = record
        if len(found) == len(wanted):
            break
    return [found[d] for d in wanted]


def examples_text(chosen: list[dict[str, Any]]) -> str:
    parts = ["WORKED EXAMPLES"]
    for n, record in enumerate(chosen, start=1):
        parts.append(f"Example {n}, input:\n{record['messages'][1]['content']}")
        parts.append(f"Example {n}, correct answer:\n{record['messages'][2]['content']}")
    return "\n\n".join(parts)


def policy_documents(context: dict[str, Any]) -> str:
    ids = sorted({c["policy_id"] for line in context["lines"] for c in line["criteria"]})
    texts = []
    for policy_id in ids:
        raw = (POLICIES / f"{policy_id}.md").read_text(encoding="utf-8")
        _, front, body = raw.split("---", 2)
        title = next(x for x in front.splitlines() if x.startswith("title:"))
        sources = next(x for x in front.splitlines() if x.startswith("sources:"))
        texts.append(f"POLICY {policy_id}\n{title}\n{sources}\n{body.strip()}")
    return "POLICY DOCUMENTS\n\n" + "\n\n".join(texts) if texts else ""


def reasoning_text(answer: str, context: dict[str, Any]) -> str:
    """One paragraph per listed criterion and one sentence per line (see the module docstring)."""
    try:
        output = SLMOutput.model_validate_json(answer)
    except ValueError:
        return ""
    criteria = {c["criterion_id"]: c for line in context["lines"] for c in line["criteria"]}
    paragraphs = []
    for line in output.lines:
        for result in line.criteria:
            known = criteria.get(result.criterion_id, {})
            paragraphs.append(
                f"Line {line.line_no}, criterion {result.criterion_id} "
                f"({known.get('criterion_type') or 'criterion'}): {known.get('text', '')} "
                f'The notes say: "{result.evidence}" So its status is {result.status.value}.'
            )
        paragraphs.append(
            f"Line {line.line_no}: from these statuses the decision is {line.decision.value}."
        )
    return "\n\n".join(paragraphs)


def describe(values: list[float]) -> dict[str, float]:
    ordered = sorted(values)
    return {
        "mean": round(statistics.fmean(ordered), 1),
        "median": round(statistics.median(ordered), 1),
        "p95": round(ordered[int(0.95 * (len(ordered) - 1))], 1),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--set", required=True, choices=["clean", "messy"])
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--split", required=True)
    parser.add_argument("--train", type=Path, required=True)
    args = parser.parse_args()

    enc = tiktoken.get_encoding(ENCODING)

    def count(text: str) -> int:
        return len(enc.encode(text))

    measured = json.loads((OUT_DIR / f"token_usage_{args.set}.json").read_text())
    records = {
        r["metadata"]["record_id"]: r for r in read_jsonl(args.dataset / f"{args.split}.jsonl")
    }
    inputs = {i["record_id"]: i for i in read_jsonl(args.dataset / f"{args.split}_inputs.jsonl")}
    chosen = examples(args.train)
    schema = "OUTPUT JSON SCHEMA\n" + json.dumps(SLMOutput.model_json_schema(), indent=2)
    shared = {"output_schema": count(schema), "worked_examples": count(examples_text(chosen))}

    rows = []
    for m in measured["rows"]:
        record = records[m["record_id"]]
        context = inputs[m["record_id"]]["context"]
        system, user = record["messages"][0]["content"], record["messages"][1]["content"]
        parts = {
            "system": count(system),
            **shared,
            "user": count(user),
            "policy_documents": count(policy_documents(context)),
        }
        json_out = count(m["answer"])
        reasoning = count(reasoning_text(m["answer"], context))
        llm_in = sum(parts.values())
        rows.append(
            {
                "record_id": m["record_id"],
                "model_lines": m["model_lines"],
                "slm_input_gemma": m["input_tokens"],
                "slm_output_gemma": m["output_tokens"],
                "slm_input_o200k": parts["system"] + parts["user"],
                "slm_output_o200k": json_out,
                "llm_input_o200k": llm_in,
                "llm_parts_o200k": parts,
                "llm_output_no_reasoning_o200k": json_out,
                "llm_output_with_reasoning_o200k": json_out + reasoning,
                "input_ratio_o200k": round(llm_in / (parts["system"] + parts["user"]), 2),
                "input_ratio_vs_gemma": round(llm_in / m["input_tokens"], 2),
            }
        )

    def col(key: str) -> list[float]:
        return [r[key] for r in rows]

    summary = {
        "set": args.set,
        "encoding": ENCODING,
        "tiktoken": tiktoken.__version__,
        "records": len(rows),
        "examples": [r["metadata"]["record_id"] for r in chosen],
        "shared_parts_o200k": shared,
        "llm_parts_mean_o200k": {
            k: round(statistics.fmean(r["llm_parts_o200k"][k] for r in rows), 1)
            for k in rows[0]["llm_parts_o200k"]
        },
        "per_claim": {
            k: describe(col(k))
            for k in (
                "slm_input_gemma",
                "slm_output_gemma",
                "slm_input_o200k",
                "slm_output_o200k",
                "llm_input_o200k",
                "llm_output_no_reasoning_o200k",
                "llm_output_with_reasoning_o200k",
                "input_ratio_o200k",
                "input_ratio_vs_gemma",
            )
        },
        "per_1000_claims": {
            k: round(statistics.fmean(col(k)) * 1000)
            for k in (
                "slm_input_gemma",
                "slm_output_gemma",
                "llm_input_o200k",
                "llm_output_no_reasoning_o200k",
                "llm_output_with_reasoning_o200k",
            )
        },
        "rows": rows,
    }
    out = OUT_DIR / f"llm_prompt_tokens_{args.set}.json"
    out.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "rows"}, indent=2))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
