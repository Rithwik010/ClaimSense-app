"""One model stage of a v3 Kaggle round (runs inside the private Kaggle notebook, not locally).

    python kaggle_stage.py --run run.json --stage writer_b --data <dataset dir> --out <dir>

A stage loads one open-weight model with vLLM and answers its jobs in one batch:

- writer_b, writer_c: `writers.jsonl` jobs of that writer (chat messages) -> notes_out.jsonl;
- verifier: `verify.jsonl` jobs (writer A notes, messages ready) and every note the writers wrote in
  this session (messages built from run.json's verifier template and the job's statements)
  -> verifier_out.jsonl.

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

    if stage["kind"] == "write":
        jobs = [
            j for j in read_jsonl(args.data / "writers.jsonl") if j["writer"] == stage["writer"]
        ]
        items = [(j, j["messages"], j["sampling"]) for j in jobs]
        out_path = args.out / "notes_out.jsonl"
    else:
        items = [
            (j, j["messages"], stage["sampling"]) for j in read_jsonl(args.data / "verify.jsonl")
        ]
        written = {j["job_id"]: j for j in read_jsonl(args.data / "writers.jsonl")}
        for row in read_jsonl(args.out / "notes_out.jsonl"):
            job = written[row["job_id"]]
            messages = verifier_messages(run, row["text"], job["statements"])
            items.append(
                ({**job, "job_id": f"verify-{row['job_id']}"}, messages, stage["sampling"])
            )
        out_path = args.out / "verifier_out.jsonl"
    done = {row["job_id"] for row in read_jsonl(out_path)}  # a rerun skips what is saved
    items = [item for item in items if item[0]["job_id"] not in done]
    if not items:
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
        gpu_memory_utilization=settings["gpu_memory_utilization"],
        seed=0,
    )
    loaded = time.time()
    tokenizer = llm.get_tokenizer()
    model_revision = revision(stage["model"])
    prompt_tokens = output_tokens = 0
    size = int(settings.get("chunk_size", 256))
    budget = float(settings.get("stage_hours", {}).get(args.stage, 1e9)) * 3600
    done_jobs = 0
    for first in range(0, len(items), size):  # saved after each chunk
        if time.time() - started > budget:  # the rest waits for the next round
            print(f"{args.stage}: time budget reached, {done_jobs}/{len(items)} done", flush=True)
            break
        chunk = items[first : first + size]
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
                prompt_tokens += len(output.prompt_token_ids)
                output_tokens += len(choice.token_ids)
                f.write(
                    json.dumps(
                        {
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
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
        done_jobs = min(first + size, len(items))
        print(f"{args.stage}: {done_jobs}/{len(items)}", flush=True)
    finished = time.time()
    timing = {
        "stage": args.stage,
        "model": stage["model"],
        "revision": model_revision,
        "vllm": vllm.__version__,
        "attention_backend": args.backend,
        "jobs": len(items),
        "done": done_jobs,
        "load_seconds": round(loaded - started, 1),
        "generate_seconds": round(finished - loaded, 1),
        "prompt_tokens": prompt_tokens,
        "output_tokens": output_tokens,
    }
    (args.out / f"timings_{args.stage}.json").write_text(json.dumps(timing, indent=2))
    print(json.dumps(timing))


if __name__ == "__main__":
    main()
