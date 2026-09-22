"""QLoRA fine-tuning of Gemma 4 E2B on a Kaggle GPU (INSTRUCTIONS.md §10, P4.3).

Runs on the training machine only (NVIDIA GPU, Unsloth); never on the laptop. In a Kaggle notebook
with the private dataset attached (`prepare_kaggle.py` builds it):

    !pip install --upgrade unsloth unsloth_zoo
    !python /kaggle/input/claimsense-decision/finetune/train.py \\
        --data /kaggle/input/claimsense-decision --out /kaggle/working/claimsense

Steps: count exact tokens and stop if a record is longer than the max length; train on responses
only with early stopping on validation loss; save the LoRA adapter, the merged GGUF (Q4_K_M), the
config, the length report, the training log, one rendered example and the installed versions.
"""

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from data import (  # noqa: E402  (a sibling file on Kaggle; training.finetune.data in the repo)
    CONFIG,
    length_report,
    read_jsonl,
    supports_system_role,
    to_chat,
    turn_markers,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data", type=Path, required=True, help="folder with train/validation")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--max-seq-length", type=int, default=CONFIG["max_seq_length"])
    parser.add_argument("--epochs", type=float, default=CONFIG["num_train_epochs"])
    parser.add_argument("--limit", type=int, help="first N training records (smoke test)")
    parser.add_argument("--no-gguf", action="store_true")
    args = parser.parse_args()
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
        if split == "train" and args.limit:
            records = records[: args.limit]
        return [
            render(to_chat(r["messages"], system_role), False).removeprefix("<bos>")
            for r in records
        ]

    train_texts, validation_texts = texts("train"), texts("validation")
    lengths = {
        split: [len(tokenizer(text=t, add_special_tokens=True)["input_ids"]) for t in items]
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
    )
    bf16 = torch.cuda.is_bf16_supported()
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
            warmup_ratio=config["warmup_ratio"],
            weight_decay=config["weight_decay"],
            lr_scheduler_type=config["lr_scheduler_type"],
            optim=config["optim"],
            bf16=bf16,
            fp16=not bf16,  # T4 and P100 have no bf16 (§10: bf16 where supported)
            logging_steps=10,
            eval_strategy="steps",
            eval_steps=config["eval_every_steps"],
            save_strategy="steps",
            save_steps=config["eval_every_steps"],
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
    log = {
        "train_runtime_seconds": round(time.time() - started),
        "train_loss": result.training_loss,
        "best_eval_loss": trainer.state.best_metric,
        "best_checkpoint": trainer.state.best_model_checkpoint,
        "history": trainer.state.log_history,
        "gpu": torch.cuda.get_device_name(0),
        "precision": "bf16" if bf16 else "fp16",
    }
    (out / "training-log.json").write_text(json.dumps(log, indent=2))
    model.save_pretrained(str(out / "adapter"))
    tokenizer.save_pretrained(str(out / "adapter"))
    if not args.no_gguf:
        model.save_pretrained_gguf(
            str(out / "gguf"), tokenizer, quantization_method=config["gguf_quantization"]
        )
    print(json.dumps({k: v for k, v in log.items() if k != "history"}, indent=2))


if __name__ == "__main__":
    main()
