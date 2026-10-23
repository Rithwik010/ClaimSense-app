"""One model stage of a v3 Kaggle round (runs inside the private Kaggle notebook, not locally).

    python kaggle_stage.py --run run.json --stage writer_b --data <dataset dir> --out <dir>

A stage loads one open-weight model with vLLM and answers its jobs in one batch:

- writer_b, writer_c: `writers.jsonl` jobs of that writer (chat messages) -> notes_out.jsonl;
- verifier: `verify.jsonl` jobs (writer A notes and earlier notes' second looks, messages ready)
  and every note the writers wrote in this session (messages built from run.json's verifier
  template and the job's statements) -> verifier_out.jsonl; then the second looks at what it
  found (D-V3-12): for a missing fact the judge (`judge-` jobs: does the cited passage alone
  establish it?), for an exclusion the verifier asked again about that fact alone (`look-`).

Each stage is its own process, so the GPUs are free again when it exits. It records the model's
Hugging Face revision, the vLLM version, tokens and seconds (timings_<stage>.json).
"""

import argparse
import json
import os
import time
from pathlib import Path

os.environ.setdefault("VLLM_USE_V1", "0")


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def revision(model: str) -> str | None:
    try:
        from huggingface_hub import HfApi

        return HfApi().model_info(model).sha
    except Exception:  # noqa: BLE001  (offline or rate limited: recorded as unknown)
        return None


def verifier_messages(run: dict, note: str, statements: list[dict]) -> list[dict]:
    listed = "\n".join(f"{s['id']}. {s['statement']}" for s in statements)
    return [
        {"role": "system", "content": run["verifier_system"]},
        {"role": "user", "content": run["verifier_user"].format(note=note, statements=listed)},
    ]


def judge_messages(run: dict, passage: str, statement: str) -> list[dict]:
    return [
        {"role": "system", "content": run["judge_system"]},
        {"role": "user", "content": run["judge_user"].format(passage=passage, statement=statement)},
    ]


def quotes(text: str) -> dict[int, str]:
    """{statement id: quote} for the statements the verifier quoted (llm.parse_verifier's rule)."""
    start, end = text.find("{"), text.rfind("}")
    try:
        answers = json.loads(text[start : end + 1]).get("answers")
    except (ValueError, AttributeError):
        return {}
    found = {}
    for answer in answers if isinstance(answers, list) else []:
        if isinstance(answer, dict) and isinstance(answer.get("id"), int):
            quote = answer.get("quote")
            if isinstance(quote, str) and quote.strip().strip(".'\"").lower() not in NO_QUOTE:
                found[answer["id"]] = quote
    return found


NO_QUOTE = {"", "null", "none", "n/a", "na", "not stated", "not found", "no"}


def second_looks(run: dict, sampling: dict, verified: list[dict], jobs: dict) -> list[tuple]:
    """For each missing or absent fact the verifier found: the judge (a missing fact: does the
    cited passage alone establish it?) or the verifier asked again about that fact alone (an
    exclusion)."""
    items = []
    short = {**sampling, "max_tokens": 32}
    for row in verified:
        base = row["job_id"].removeprefix("verify-")
        job = jobs.get(base)
        if job is None:
            continue
        found = quotes(row["text"])
        for statement in job["statements"]:
            quote = found.get(statement["id"])
            if statement.get("expect") != "absent" or not quote:
                continue
            look = {
                **job,
                "job_id": f"{statement.get('check', 'look')}-{base}:{statement['fact_id']}",
            }
            if statement.get("check") == "judge":
                items.append((look, judge_messages(run, quote, statement["statement"]), short))
            else:
                alone = verifier_messages(run, job["note"], [{**statement, "id": 1}])
                items.append((look, alone, sampling))
    return items


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--stage", required=True)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--backend", default="auto", help="the attention backend this try uses")
    args = parser.parse_args()
    run = json.loads(args.run.read_text(encoding="utf-8"))
    stage = run["stages"][args.stage]
    args.out.mkdir(parents=True, exist_ok=True)

    jobs: dict[str, dict] = {}  # verified notes, by "<sheet>#<attempt>": statements and note
    if stage["kind"] == "write":
        mine = [
            j for j in read_jsonl(args.data / "writers.jsonl") if j["writer"] == stage["writer"]
        ]
        items = [(j, j["messages"], j["sampling"]) for j in mine]
        out_path = args.out / "notes_out.jsonl"
    else:
        items = []
        for j in read_jsonl(args.data / "verify.jsonl"):
            items.append((j, j["messages"], stage["sampling"]))
            if j["job_id"].startswith("verify-") and j.get("statements"):
                jobs[j["job_id"].removeprefix("verify-")] = j
        written = {j["job_id"]: j for j in read_jsonl(args.data / "writers.jsonl")}
        for row in read_jsonl(args.out / "notes_out.jsonl"):
            job = {**written[row["job_id"]], "note": row["text"]}
            jobs[row["job_id"]] = job
            messages = verifier_messages(run, row["text"], job["statements"])
            items.append(
                ({**job, "job_id": f"verify-{row['job_id']}"}, messages, stage["sampling"])
            )
        out_path = args.out / "verifier_out.jsonl"
    done = {row["job_id"] for row in read_jsonl(out_path)}  # a rerun skips what is saved
    items = [item for item in items if item[0]["job_id"] not in done]
    if stage["kind"] == "verify":
        verified = [r for r in read_jsonl(out_path) if r["job_id"].startswith("verify-")]
        pending_looks = [
            i
            for i in second_looks(run, stage["sampling"], verified, jobs)
            if i[0]["job_id"] not in done
        ]
    else:
        pending_looks = []
    if not items and not pending_looks and not (stage["kind"] == "verify" and jobs):
        print(f"{args.stage}: no jobs")
        return

    import vllm
    from vllm import LLM, SamplingParams

    settings = run["vllm"]
    started = time.time()
    llm = LLM(
        model=stage["model"],
        dtype=settings["dtype"],
        tensor_parallel_size=settings["tensor_parallel_size"],
        max_model_len=stage.get("max_model_len", settings["max_model_len"]),
        max_num_seqs=stage.get("max_num_seqs", 256),
        gpu_memory_utilization=settings["gpu_memory_utilization"],
        seed=0,
    )
    loaded = time.time()
    tokenizer = llm.get_tokenizer()
    model_revision = revision(stage["model"])
    size = int(settings.get("chunk_size", 256))
    budget = float(settings.get("stage_hours", {}).get(args.stage, 1e9)) * 3600
    totals = {"jobs": 0, "done": 0, "prompt_tokens": 0, "output_tokens": 0}

    def generate(batch: list[tuple]) -> None:
        totals["jobs"] += len(batch)
        for first in range(0, len(batch), size):  # saved after each chunk
            if time.time() - started > budget:  # the rest waits for the next round
                print(f"{args.stage}: time budget reached", flush=True)
                return
            chunk = batch[first : first + size]
            prompts = [
                tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
                for _, messages, _ in chunk
            ]
            params = [
                SamplingParams(
                    temperature=s["temperature"],
                    top_p=s.get("top_p", 1.0),
                    max_tokens=s["max_tokens"],
                    seed=int(job.get("seed", 0)),
                )
                for job, _, s in chunk
            ]
            outputs = llm.generate(prompts, params)
            with out_path.open("a", encoding="utf-8") as f:
                for (job, _, _), output in zip(chunk, outputs, strict=True):
                    choice = output.outputs[0]
                    totals["prompt_tokens"] += len(output.prompt_token_ids)
                    totals["output_tokens"] += len(choice.token_ids)
                    row = {
                        "job_id": job["job_id"],
                        "sheet_id": job["sheet_id"],
                        "attempt": job["attempt"],
                        "writer": job.get("writer"),
                        "text": choice.text,
                        "finish_reason": choice.finish_reason,
                        "model": stage["model"],
                        "revision": model_revision,
                        "prompt_tokens": len(output.prompt_token_ids),
                        "output_tokens": len(choice.token_ids),
                    }
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
            totals["done"] += len(chunk)
            print(f"{args.stage}: {totals['done']}/{totals['jobs']}", flush=True)

    generate(items)
    if stage["kind"] == "verify":  # the second looks at what this pass (or an earlier try) found
        done = {row["job_id"] for row in read_jsonl(out_path)}
        verified = [r for r in read_jsonl(out_path) if r["job_id"].startswith("verify-")]
        looks = second_looks(run, stage["sampling"], verified, jobs)
        generate([i for i in looks if i[0]["job_id"] not in done])
    finished = time.time()
    timing = {
        "stage": args.stage,
        "model": stage["model"],
        "revision": model_revision,
        "vllm": vllm.__version__,
        "attention_backend": args.backend,
        **totals,
        "load_seconds": round(loaded - started, 1),
        "generate_seconds": round(finished - loaded, 1),
    }
    (args.out / f"timings_{args.stage}.json").write_text(json.dumps(timing, indent=2))
    print(json.dumps(timing))


if __name__ == "__main__":
    main()
