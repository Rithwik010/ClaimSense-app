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
backward pass on the longest training record first and records the peak GPU memory.
"""

import argparse
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

    started = time.time()

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
    probe = None
    if args.memory_probe:  # the longest record, forward and backward, before training
        longest = max(train_texts, key=lambda text: token_count(tokenizer, text))
        batch = tokenizer(text=longest, return_tensors="pt").to(model.device)
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
        del batch, loss
        torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats()
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
        "peak_gpu_memory_gb": round(torch.cuda.max_memory_allocated() / 1e9, 2),
        "memory_probe": probe,
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
