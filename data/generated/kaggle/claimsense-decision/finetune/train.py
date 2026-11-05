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

FULL_TRAIN_RECORDS = 2000


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
    parser.add_argument("--export-from", type=Path, help="only export GGUF from a saved adapter")
    parser.add_argument("--gguf-work-dir", type=Path, default=GGUF_WORK_DIR)
    args = parser.parse_args()
    os.environ.setdefault("CUDA_VISIBLE_DEVICES", "0")  # before torch initialises CUDA
    config = {**CONFIG, "max_seq_length": args.max_seq_length, "num_train_epochs": args.epochs}
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
    from transformers import EarlyStoppingCallback
    from trl import SFTConfig, SFTTrainer

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

    def texts(split: str) -> list[str]:
        records = read_jsonl(args.data / f"{split}.jsonl")
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
    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=Dataset.from_dict({"text": train_texts}),
        eval_dataset=Dataset.from_dict({"text": validation_texts}),
        args=SFTConfig(
            output_dir=str(out / "checkpoints"),
            dataset_text_field="text",
            max_seq_length=config["max_seq_length"],
            per_device_train_batch_size=config["per_device_train_batch_size"],
            per_device_eval_batch_size=1,
            gradient_accumulation_steps=config["gradient_accumulation_steps"],
            num_train_epochs=config["num_train_epochs"],
            learning_rate=config["learning_rate"],
            warmup_steps=warmup_steps(len(train_texts), config["num_train_epochs"]),
            weight_decay=config["weight_decay"],
            lr_scheduler_type=config["lr_scheduler_type"],
            optim=config["optim"],
            bf16=bf16,
            fp16=False,  # Gemma 4 does not train in fp16; without bf16 (T4) Unsloth uses float32
            logging_steps=10,
            eval_strategy="steps",
            eval_steps=args.eval_steps,
            save_strategy="steps",
            save_steps=args.eval_steps,
            save_total_limit=2,
            load_best_model_at_end=True,
            metric_for_best_model="eval_loss",
            greater_is_better=False,
            seed=config["seed"],
            report_to="none",
        ),
        callbacks=[
            EarlyStoppingCallback(early_stopping_patience=config["early_stopping_patience"])
        ],
    )
    trainer = train_on_responses_only(
        trainer, instruction_part=instruction_part, response_part=response_part
    )
    started = time.time()
    result = trainer.train()
    runtime = time.time() - started
    steps = max(trainer.state.global_step, 1)
    evals = sum(1 for entry in trainer.state.log_history if "eval_loss" in entry)
    full_steps = (
        math.ceil(
            FULL_TRAIN_RECORDS
            / (config["per_device_train_batch_size"] * config["gradient_accumulation_steps"])
        )
        * CONFIG["num_train_epochs"]
    )
    log = {
        "train_runtime_seconds": round(runtime),
        "seconds_per_step": round(runtime / steps, 1),
        "evaluations": evals,
        "estimated_full_run_hours_without_evals": round(runtime / steps * full_steps / 3600, 1),
        "train_loss": result.training_loss,
        "best_eval_loss": trainer.state.best_metric,
        "best_checkpoint": trainer.state.best_model_checkpoint,
        "history": trainer.state.log_history,
        "gpu": torch.cuda.get_device_name(0),
        "precision": "bf16" if bf16 else "float32",
    }
    (out / "training-log.json").write_text(json.dumps(log, indent=2))
    model.save_pretrained(str(out / "adapter"))
    tokenizer.save_pretrained(str(out / "adapter"))
    if not args.no_gguf:
        export_gguf(model, tokenizer, out, config["gguf_quantization"], args.gguf_work_dir)
    print(json.dumps({k: v for k, v in log.items() if k != "history"}, indent=2))


if __name__ == "__main__":
    main()
