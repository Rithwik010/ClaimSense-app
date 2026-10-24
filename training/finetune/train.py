"""QLoRA fine-tuning of Gemma 4 E2B on a Kaggle GPU (INSTRUCTIONS.md §10, P4.3).

Runs on the training machine only (NVIDIA GPU, Unsloth); never on the laptop. In a Kaggle notebook
with the private dataset attached (`prepare_kaggle.py` builds it):

    !pip install --upgrade unsloth unsloth_zoo
    !python /kaggle/input/claimsense-decision/finetune/train.py \\
        --data /kaggle/input/claimsense-decision --out /kaggle/working/claimsense

Steps: count exact tokens and stop if a record is longer than the max length; train on responses
only with early stopping on validation loss; save the LoRA adapter, the merged GGUF (Q4_K_M), the
config, the length report, the training log, one rendered example and the installed versions.

One GPU only: Kaggle's "T4 x2" would otherwise split Gemma 4 across two devices, which its
multimodal layers do not support. T4s have no bf16 and Gemma 4 does not train in fp16, so training
runs in float32 there. A smoke run prints the estimated time of the full run. If the GGUF export
fails, the adapter is already saved: rerun with `--export-from <out>/adapter`.

The GGUF export writes a 16-bit merge and a 16-bit GGUF before the Q4_K_M file (about 21 GB), more
than Kaggle's 20 GB output folder holds. It works in `--gguf-work-dir` (default /tmp, Kaggle's
larger scratch disk) and copies only the final Q4_K_M file into `<out>/gguf`.

Across sessions (model v3, D-V3-9): `--stop-after-hours` (or `--stop-after-steps`) saves a
checkpoint and stops before Kaggle's session limit; the next session attaches that session's output
and passes `--resume-from` (a checkpoint folder, or a folder holding checkpoint-* folders: the
latest is used). The trainer restores the weights, optimizer, scheduler, random state and the place
in the data, so the step count and the loss carry on. `--memory-probe` runs one forward and
backward pass on the longest training record, writes the peak GPU memory to
<out>/memory-probe.json and stops; the timing notebook then trains in a new process, which puts
that file in its training log. (Probing in the training process left Unsloth's compiled loss
needing gradients, and the first evaluation failed: the timing run of 24 Oct.)

The training log also holds, per step, its seconds (step begin to step end, so evaluations and
saves are apart), its tokens and the ids of the records it trained on (read in the collator, matched
to the training records by their token ids); the step, learning rate and optimizer state when
training begins (after a resume: those of the checkpoint); and when each checkpoint was saved. The
timing runs use them for the token-based projection and the resume check (the team's conditions of
24 Oct). `--stop-after-hours` counts from `--session-start` (the notebook's start, epoch seconds)
when given, so a session ends before Kaggle's 12-hour limit.
"""

import argparse
import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from data import (  # noqa: E402  (a sibling file on Kaggle; training.finetune.data in the repo)
    CONFIG,
    length_report,
    quantized_files,
    read_jsonl,
    supports_system_role,
    to_chat,
    token_count,
    turn_markers,
    warmup_steps,
)

GGUF_WORK_DIR = Path("/tmp/claimsense-gguf")
GGUF_SPACE_NEEDED_GB = 22


def export_gguf(model, tokenizer, out: Path, quantization: str, work: Path) -> None:  # noqa: ANN001
    """Export on the scratch disk, keep only the final quantized file in the output folder."""
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    free_gb = shutil.disk_usage(work).free / 1e9
    print(f"GGUF export in {work}: {free_gb:.1f} GB free (needs about {GGUF_SPACE_NEEDED_GB})")
    if free_gb < GGUF_SPACE_NEEDED_GB:
        raise SystemExit(f"not enough space in {work}; pass --gguf-work-dir on a bigger disk")
    model.save_pretrained_gguf(str(work), tokenizer, quantization_method=quantization)
    written = [p for p in work.parent.glob(f"{work.name}*/**/*") if p.is_file()]
    finals = quantized_files(written, quantization)
    if not finals:
        names = sorted(p.name for p in written if p.suffix == ".gguf")
        raise SystemExit(f"no {quantization} GGUF among the exported files: {names}")
    target = out / "gguf"
    target.mkdir(parents=True, exist_ok=True)
    for path in finals:
        shutil.copy2(path, target / path.name)
        print(f"kept {target / path.name} ({path.stat().st_size / 1e9:.2f} GB)")
    for leftover in work.parent.glob(f"{work.name}*"):
        shutil.rmtree(leftover, ignore_errors=True)  # the 16-bit merge and intermediate GGUF


def latest_checkpoint(path: Path) -> Path:
    """`path` itself when it is a checkpoint, else its checkpoint-* folder with the most steps."""
    if (path / "trainer_state.json").exists():
        return path
    found = sorted(
        (p for p in path.rglob("checkpoint-*") if (p / "trainer_state.json").exists()),
        key=lambda p: int(p.name.split("-")[-1]),
    )
    if not found:
        raise SystemExit(f"no checkpoint in {path}")
    return found[-1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data", type=Path, required=True, help="folder with train/validation")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--max-seq-length", type=int, default=CONFIG["max_seq_length"])
    parser.add_argument("--epochs", type=float, default=CONFIG["num_train_epochs"])
    parser.add_argument("--limit", type=int, help="first N training records (smoke test)")
    parser.add_argument("--eval-limit", type=int, help="first N validation records (smoke test)")
    parser.add_argument("--eval-steps", type=int, default=CONFIG["eval_every_steps"])
    parser.add_argument("--no-gguf", action="store_true")
    parser.add_argument(
        "--no-eval",
        action="store_true",
        help="no evaluations during training (E4B: they run out of T4 memory); keeps the last step",
    )
    parser.add_argument("--export-from", type=Path, help="only export GGUF from a saved adapter")
    parser.add_argument("--gguf-work-dir", type=Path, default=GGUF_WORK_DIR)
    parser.add_argument(
        "--base-model", default=CONFIG["base_model"], help="e.g. unsloth/gemma-4-E4B-it"
    )
    parser.add_argument("--train-split", default="train", help="e.g. train_mix (model v3)")
    parser.add_argument("--max-steps", type=int, help="a fixed number of steps (timing runs)")
    parser.add_argument("--save-steps", type=int, help="checkpoint every N steps (default: evals)")
    parser.add_argument("--logging-steps", type=int, default=10)
    parser.add_argument("--stop-after-steps", type=int, help="save and stop at this step")
    parser.add_argument("--stop-after-hours", type=float, help="save and stop after this long")
    parser.add_argument("--session-start", type=float, help="epoch seconds the session began")
    parser.add_argument(
        "--eval-longest",
        action="store_true",
        help="add the longest validation record to the evaluated subset (the timing runs)",
    )
    parser.add_argument("--resume-from", type=Path, help="a checkpoint, or a folder holding them")
    parser.add_argument("--memory-probe", action="store_true")
    args = parser.parse_args()
    os.environ.setdefault("CUDA_VISIBLE_DEVICES", "0")  # before torch initialises CUDA
    config = {
        **CONFIG,
        "base_model": args.base_model,
        "max_seq_length": args.max_seq_length,
        "num_train_epochs": args.epochs,
    }
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    (out / "config.json").write_text(json.dumps(config, indent=2))
    versions = subprocess.run(
        [sys.executable, "-m", "pip", "freeze"], capture_output=True, text=True, check=False
    ).stdout
    (out / "pip-freeze.txt").write_text(versions)

    from unsloth import FastModel  # noqa: I001  (Unsloth must be imported before transformers)
    from unsloth.chat_templates import get_chat_template, train_on_responses_only
    import torch
    from datasets import Dataset
    from transformers import EarlyStoppingCallback, TrainerCallback
    from trl import SFTConfig, SFTTrainer

    started = args.session_start or time.time()

    class StopAndSave(TrainerCallback):
        """Save and stop at `--stop-after-steps` or after `--stop-after-hours` (a session's end);
        `paused` tells a session's end from the end of training (last step or early stopping)."""

        paused = False

        def on_step_end(self, _args, state, control, **_kwargs):  # noqa: ANN001, ANN201
            by_steps = args.stop_after_steps and state.global_step >= args.stop_after_steps
            by_time = (
                args.stop_after_hours and time.time() - started >= args.stop_after_hours * 3600
            )
            if by_steps or by_time:
                control.should_save = True
                control.should_training_stop = True
                self.paused = True
            return control

    if args.export_from:
        model, tokenizer = FastModel.from_pretrained(
            model_name=str(args.export_from),
            max_seq_length=config["max_seq_length"],
            load_in_4bit=config["load_in_4bit"],
        )
        export_gguf(model, tokenizer, out, config["gguf_quantization"], args.gguf_work_dir)
        return

    model, tokenizer = FastModel.from_pretrained(
        model_name=config["base_model"],
        max_seq_length=config["max_seq_length"],
        load_in_4bit=config["load_in_4bit"],
        full_finetuning=False,
    )
    tokenizer = get_chat_template(tokenizer, chat_template=config["chat_template"])

    def render(messages: list[dict[str, str]], add_generation_prompt: bool) -> str:
        return tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=add_generation_prompt,
            enable_thinking=False,  # §10: thinking disabled; ignored by templates without it
        )

    system_role = supports_system_role(render)
    instruction_part, response_part = turn_markers(render)

    full_records = len(read_jsonl(args.data / f"{args.train_split}.jsonl"))
    train_ids = [
        r["metadata"]["record_id"]
        for r in read_jsonl(args.data / f"{args.train_split}.jsonl")[: args.limit or None]
    ]

    def texts(split: str) -> list[str]:
        records = read_jsonl(args.data / f"{args.train_split if split == 'train' else split}.jsonl")
        limit = args.limit if split == "train" else args.eval_limit
        if limit:
            records = records[:limit]
        return [
            render(to_chat(r["messages"], system_role), False).removeprefix("<bos>")
            for r in records
        ]

    train_texts, validation_texts = texts("train"), texts("validation")
    validation_longest = None
    if args.eval_longest:  # the validation pass's memory on the longest record (24 Oct)
        every = read_jsonl(args.data / "validation.jsonl")
        rendered = [
            render(to_chat(r["messages"], system_role), False).removeprefix("<bos>") for r in every
        ]
        counts = [token_count(tokenizer, t) for t in rendered]
        index = max(range(len(counts)), key=counts.__getitem__)
        within = not args.eval_limit or index < args.eval_limit
        if not within:
            validation_texts.append(rendered[index])
        validation_longest = {
            "record_id": every[index]["metadata"]["record_id"],
            "tokens": counts[index],
            "in_the_first_records": within,
            "evaluated_records": len(validation_texts),
        }
        print("longest validation record:", json.dumps(validation_longest), flush=True)
    lengths = {
        split: [token_count(tokenizer, t) for t in items]
        for split, items in (("train", train_texts), ("validation", validation_texts))
    }
    report = {
        split: length_report(values, config["max_seq_length"]) for split, values in lengths.items()
    }
    report["system_role"] = system_role
    report["turn_markers"] = [instruction_part, response_part]
    (out / "lengths.json").write_text(json.dumps(report, indent=2))
    (out / "example.txt").write_text(train_texts[0])
    print(json.dumps(report, indent=2), flush=True)
    if any(report[s]["over_max"] for s in ("train", "validation")):
        raise SystemExit(
            f"records longer than {config['max_seq_length']} tokens: raise --max-seq-length"
        )

    model = FastModel.get_peft_model(
        model,
        finetune_vision_layers=config["finetune_vision_layers"],
        finetune_language_layers=config["finetune_language_layers"],
        finetune_attention_modules=config["finetune_attention_modules"],
        finetune_mlp_modules=config["finetune_mlp_modules"],
        r=config["lora_r"],
        lora_alpha=config["lora_alpha"],
        lora_dropout=config["lora_dropout"],
        bias="none",
        random_state=config["seed"],
        use_gradient_checkpointing="unsloth",
    )
    bf16 = torch.cuda.is_bf16_supported()
    print(f"GPUs visible: {torch.cuda.device_count()}; precision: {'bf16' if bf16 else 'float32'}")
    probe_file = out / "memory-probe.json"
    probe = json.loads(probe_file.read_text()) if probe_file.exists() else None
    if args.memory_probe:  # the longest record, forward and backward, then stop (see above)
        longest = max(train_texts, key=lambda text: token_count(tokenizer, text))
        batch = tokenizer(text=longest, return_tensors="pt").to(model.device)
        model.train()  # as the trainer runs it: gradient checkpointing works in training mode only
        torch.cuda.reset_peak_memory_stats()
        loss = model(**batch, labels=batch["input_ids"]).loss
        loss.backward()
        model.zero_grad(set_to_none=True)
        probe = {
            "tokens": int(batch["input_ids"].shape[1]),
            "peak_gb": round(torch.cuda.max_memory_allocated() / 1e9, 2),
            "gpu_total_gb": round(torch.cuda.get_device_properties(0).total_memory / 1e9, 2),
        }
        print("memory probe:", json.dumps(probe), flush=True)
        probe_file.write_text(json.dumps(probe, indent=2))
        return
    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=Dataset.from_dict({"text": train_texts}),
        eval_dataset=None if args.no_eval else Dataset.from_dict({"text": validation_texts}),
        args=SFTConfig(
            output_dir=str(out / "checkpoints"),
            dataset_text_field="text",
            max_seq_length=config["max_seq_length"],
            per_device_train_batch_size=config["per_device_train_batch_size"],
            per_device_eval_batch_size=1,
            gradient_accumulation_steps=config["gradient_accumulation_steps"],
            num_train_epochs=config["num_train_epochs"],
            max_steps=args.max_steps or -1,
            learning_rate=config["learning_rate"],
            warmup_steps=warmup_steps(len(train_texts), config["num_train_epochs"]),
            weight_decay=config["weight_decay"],
            lr_scheduler_type=config["lr_scheduler_type"],
            optim=config["optim"],
            bf16=bf16,
            fp16=False,  # Gemma 4 does not train in fp16; without bf16 (T4) Unsloth uses float32
            logging_steps=args.logging_steps,
            eval_strategy="no" if args.no_eval else "steps",
            eval_steps=None if args.no_eval else args.eval_steps,
            save_strategy="steps",
            save_steps=args.save_steps or args.eval_steps,
            save_total_limit=3,
            load_best_model_at_end=not args.no_eval,
            metric_for_best_model=None if args.no_eval else "eval_loss",
            greater_is_better=False,
            seed=config["seed"],
            report_to="none",
        ),
        callbacks=[stopper := StopAndSave()]
        + (
            []
            if args.no_eval
            else [EarlyStoppingCallback(early_stopping_patience=config["early_stopping_patience"])]
        ),
    )
    trainer = train_on_responses_only(
        trainer, instruction_part=instruction_part, response_part=response_part
    )
    evaluation_step = trainer.prediction_step

    def prediction_step(model, inputs, prediction_loss_only, ignore_keys=None):  # noqa: ANN001, ANN202
        """Unsloth 2026.10.8's evaluation returns a loss that still requires grad, although it runs
        under torch.no_grad, and the trainer's numpy() on it fails (the timing runs of 24 Oct):
        detach it, which also frees whatever it holds."""
        loss, logits, labels = evaluation_step(
            model, inputs, prediction_loss_only, ignore_keys=ignore_keys
        )
        return (loss.detach() if loss is not None else None), logits, labels

    trainer.prediction_step = prediction_step
    evaluate = trainer.evaluate
    memory = {"training_peak": 0.0, "validation": []}

    def evaluate_with_memory(*eval_args, **eval_kwargs):  # noqa: ANN002, ANN003, ANN202
        """Peak GPU memory of each validation pass, apart from training's."""
        memory["training_peak"] = max(memory["training_peak"], torch.cuda.max_memory_allocated())
        torch.cuda.reset_peak_memory_stats()
        found = evaluate(*eval_args, **eval_kwargs)
        memory["validation"].append(
            {
                "step": trainer.state.global_step,
                "peak_gb": round(torch.cuda.max_memory_allocated() / 1e9, 2),
                "eval_loss": found.get("eval_loss"),
            }
        )
        torch.cuda.reset_peak_memory_stats()
        return found

    trainer.evaluate = evaluate_with_memory

    def key(ids) -> str:  # noqa: ANN001  (a list or a tensor of token ids)
        values = ids.tolist() if hasattr(ids, "tolist") else list(ids)
        return hashlib.sha1(json.dumps(values).encode()).hexdigest()

    rows = trainer.train_dataset["input_ids"]
    if len(rows) != len(train_ids):
        raise SystemExit(f"{len(rows)} tokenized training rows for {len(train_ids)} records")
    position = {key(ids): i for i, ids in enumerate(rows)}
    train_tokens_total = sum(len(ids) for ids in rows)
    del rows
    collated: list[tuple[int, int]] = []  # (record position, tokens) per training micro-batch
    collator = trainer.data_collator

    def recording(features):  # noqa: ANN001, ANN202
        for feature in features:  # validation rows match no training row and are not counted
            found = position.get(key(feature["input_ids"]))
            if found is not None:
                collated.append((found, len(feature["input_ids"])))
        return collator(features)

    trainer.data_collator = recording

    class Steps(TrainerCallback):
        """The state at the start (or resume) of training, each step's seconds, and the saves."""

        def __init__(self) -> None:
            self.begun: dict = {}
            self.began: dict[int, float] = {}
            self.ended: dict[int, float] = {}
            self.saves: list[dict] = []

        def on_train_begin(self, _args, state, control, optimizer=None, lr_scheduler=None, **_):  # noqa: ANN001, ANN201
            inner = getattr(optimizer, "optimizer", optimizer)
            per_param = list(getattr(inner, "state", {}).values())
            steps = sorted({float(v["step"]) for v in per_param if "step" in v})
            self.begun = {
                "global_step": state.global_step,
                "learning_rate": lr_scheduler.get_last_lr()[0] if lr_scheduler else None,
                "scheduler_steps": getattr(lr_scheduler, "last_epoch", None),
                "optimizer_params_with_state": len(per_param),
                "optimizer_state_steps": steps[:3],
            }
            print("training begins:", json.dumps(self.begun), flush=True)

        def on_step_begin(self, _args, state, control, **_kwargs):  # noqa: ANN001, ANN201
            self.began.setdefault(state.global_step + 1, time.time())

        def on_step_end(self, _args, state, control, **_kwargs):  # noqa: ANN001, ANN201
            self.ended[state.global_step] = time.time()

        def on_save(self, _args, state, control, **_kwargs):  # noqa: ANN001, ANN201
            after = time.time() - self.ended.get(state.global_step, time.time())
            self.saves.append({"step": state.global_step, "seconds_after_step": round(after, 1)})

    trainer.add_callback(steps_seen := Steps())
    resume = latest_checkpoint(args.resume_from) if args.resume_from else None
    first_step = 0
    if resume and resume.parent.resolve() != (out / "checkpoints").resolve():
        # an earlier session's checkpoints into this run's folder (the same path in both
        # sessions), so its best checkpoint is still there when the best one is loaded at the end
        (out / "checkpoints").mkdir(parents=True, exist_ok=True)
        for earlier in resume.parent.glob("checkpoint-*"):
            if not (out / "checkpoints" / earlier.name).exists():
                shutil.copytree(earlier, out / "checkpoints" / earlier.name)
        resume = out / "checkpoints" / resume.name
    if resume:
        first_step = json.loads((resume / "trainer_state.json").read_text())["global_step"]
        print(f"resuming from {resume} at step {first_step}", flush=True)
    train_started = time.time()
    result = trainer.train(resume_from_checkpoint=str(resume) if resume else None)
    runtime = time.time() - train_started
    steps = max(trainer.state.global_step - first_step, 1)
    evals = sum(1 for entry in trainer.state.log_history if "eval_loss" in entry)
    full_steps = math.ceil(
        math.ceil(
            full_records
            / (config["per_device_train_batch_size"] * config["gradient_accumulation_steps"])
        )
        * config["num_train_epochs"]
    )
    finished = not stopper.paused  # the last step, or early stopping on the validation loss
    per_step = config["per_device_train_batch_size"] * config["gradient_accumulation_steps"]
    step_rows = []
    for n in range(first_step + 1, trainer.state.global_step + 1):
        batch = collated[(n - first_step - 1) * per_step : (n - first_step) * per_step]
        began, ended = steps_seen.began.get(n), steps_seen.ended.get(n)
        step_rows.append(
            {
                "step": n,
                "seconds": round(ended - began, 2) if began and ended else None,
                "tokens": sum(t for _, t in batch),
                "records": [train_ids[i] for i, _ in batch],
            }
        )
    log = {
        "train_runtime_seconds": round(runtime),
        "first_step": first_step,
        "last_step": trainer.state.global_step,
        "max_steps": trainer.state.max_steps,
        "finished": finished,
        "seconds_per_step": round(runtime / steps, 1),
        "evaluations": evals,
        "full_run_records": full_records,
        "full_run_steps": full_steps,
        "estimated_full_run_hours_without_evals": round(runtime / steps * full_steps / 3600, 1),
        "peak_gpu_memory_gb": round(
            max(memory["training_peak"], torch.cuda.max_memory_allocated()) / 1e9, 2
        ),  # training only: each validation pass's peak is under validation_memory
        "validation_memory": memory["validation"],
        "validation_longest": validation_longest,
        "memory_probe": probe,
        "train_tokens_total": train_tokens_total,
        "training_began": steps_seen.begun,
        "steps": step_rows,
        "collated_beyond_last_step": [
            train_ids[i] for i, _ in collated[len(step_rows) * per_step :]
        ],
        "saves": steps_seen.saves,
        "session_hours": round((time.time() - started) / 3600, 2),
        "seconds_before_training": round(train_started - started),  # set-up, loading, tokenizing
        "train_loss": result.training_loss,
        "best_eval_loss": trainer.state.best_metric,
        "best_checkpoint": trainer.state.best_model_checkpoint,
        "history": trainer.state.log_history,
        "gpu": torch.cuda.get_device_name(0),
        "precision": "bf16" if bf16 else "float32",
    }
    (out / "training-log.json").write_text(json.dumps(log, indent=2))
    if not finished:  # a session stopped early: its checkpoint is the result; the next resumes
        print(json.dumps({k: v for k, v in log.items() if k != "history"}, indent=2))
        return
    model.save_pretrained(str(out / "adapter"))  # the lowest validation loss (loaded at the end)
    tokenizer.save_pretrained(str(out / "adapter"))
    final = latest_checkpoint(out / "checkpoints")  # the last step trained: the final model
    shutil.copytree(
        final,
        out / "adapter-final",
        ignore=shutil.ignore_patterns("optimizer.pt", "scheduler.pt", "rng_state*.pth"),
        dirs_exist_ok=True,
    )
    log["final_checkpoint"] = final.name
    (out / "training-log.json").write_text(json.dumps(log, indent=2))
    if not args.no_gguf:
        export_gguf(model, tokenizer, out, config["gguf_quantization"], args.gguf_work_dir)
    print(json.dumps({k: v for k, v in log.items() if k != "history"}, indent=2))


if __name__ == "__main__":
    main()
