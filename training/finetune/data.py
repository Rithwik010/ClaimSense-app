"""Training-data helpers with no GPU dependencies, so they are unit-tested on the laptop and copied
to Kaggle next to `train.py` (standard library only).

INSTRUCTIONS.md §10: the tokenizer's Gemma 4 chat template; if it has no system role, the system
instructions go at the start of the first user message; loss on the responses only; thinking off.
"""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

# §10 starting configuration. Max length 3072 keeps every record (the longest are estimated at about
# 2,700 tokens); the script counts exact tokens and stops if any record is longer.
CONFIG: dict[str, Any] = {
    "base_model": "unsloth/gemma-4-E2B-it",
    "chat_template": "gemma-4",
    "max_seq_length": 3072,
    "load_in_4bit": True,
    "lora_r": 16,
    "lora_alpha": 16,
    "lora_dropout": 0.0,
    "finetune_vision_layers": False,
    "finetune_language_layers": True,
    "finetune_attention_modules": True,
    "finetune_mlp_modules": True,
    "per_device_train_batch_size": 1,
    "gradient_accumulation_steps": 8,
    "learning_rate": 2e-4,
    "num_train_epochs": 2,
    "warmup_ratio": 0.03,
    "weight_decay": 0.01,
    "lr_scheduler_type": "linear",
    "optim": "adamw_8bit",
    "eval_every_steps": 125,
    "early_stopping_patience": 2,
    "seed": 20260921,
    "gguf_quantization": "q4_k_m",
}

Render = Callable[[list[dict[str, str]], bool], str]  # (messages, add_generation_prompt) -> text


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def supports_system_role(render: Render) -> bool:
    marker = "SYSTEM-ROLE-PROBE"
    try:
        text = render(
            [{"role": "system", "content": marker}, {"role": "user", "content": "u"}], False
        )
    except Exception:  # noqa: BLE001  (templates raise their own errors for unknown roles)
        return False
    return marker in text


def to_chat(messages: list[dict[str, str]], system_role: bool) -> list[dict[str, str]]:
    """The record's system, user and assistant messages; without a system role the instructions
    start the first user message."""
    if system_role or messages[0]["role"] != "system":
        return messages
    system, user, *rest = messages
    return [{"role": "user", "content": f"{system['content']}\n\n{user['content']}"}, *rest]


def turn_markers(render: Render) -> tuple[str, str]:
    """(instruction part, response part) for loss on responses only, read from the template itself:
    the text that opens a user turn and the text that opens the model's answer."""
    user = "USER-TURN-PROBE"
    without = render([{"role": "user", "content": user}], False)
    with_prompt = render([{"role": "user", "content": user}], True)
    if not with_prompt.startswith(without) or with_prompt == without:
        raise ValueError("the chat template adds no generation prompt")
    response_part = with_prompt[len(without) :]
    instruction_part = without[: without.index(user)]
    for bos in ("<bos>", "<s>"):
        instruction_part = instruction_part.removeprefix(bos)
    if not instruction_part.strip() or not response_part.strip():
        raise ValueError("could not find the turn markers in the chat template")
    return instruction_part, response_part


def length_report(lengths: list[int], max_len: int) -> dict[str, Any]:
    ordered = sorted(lengths)
    return {
        "records": len(ordered),
        "p50": ordered[len(ordered) // 2],
        "p95": ordered[int(0.95 * (len(ordered) - 1))],
        "max": ordered[-1],
        "max_seq_length": max_len,
        "over_max": sum(1 for n in ordered if n > max_len),
    }
