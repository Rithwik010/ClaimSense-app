"""docs/TRAINING.md and its loss curves (docs/training/*.png) for models v1, v2 and E4B, from the
Kaggle runs' own files: training-log.json (the trainer's history and summary), config.json and
lengths.json, downloaded into data/generated/models/. A number the run did not log is written
"not logged". The curves are drawn with Pillow (no plotting library).

    uv run python -m scripts.verify.training_report
"""

import json
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
MODELS = ROOT / "data" / "generated" / "models"
OUT = ROOT / "docs" / "TRAINING.md"
PNG = ROOT / "docs" / "training"
RUNS = {
    "v1": (
        "claimsense-decision:v1",
        MODELS / "claimsense-decision-v1",
        "decision dataset v1, prompt decision_v2",
    ),
    "v2": (
        "claimsense-decision:v2",
        MODELS / "claimsense-decision-v2" / "full" / "claimsense-v2",
        "decision dataset v2, prompt decision_v3",
    ),
    "e4b": (
        "claimsense-decision:e4b",
        MODELS / "claimsense-decision-e4b" / "full" / "claimsense-v2-e4b",
        "decision dataset v2, prompt decision_v3",
    ),
}
NOT_LOGGED = "not logged"
INK, MUTED, RULES, GREY = (27, 36, 51), (82, 92, 108), (218, 221, 227), (154, 163, 178)


def load(folder: Path, name: str) -> dict[str, Any] | None:
    path = folder / name
    return json.loads(path.read_text()) if path.exists() else None


def curve(name: str, history: list[dict[str, Any]], path: Path) -> None:
    """Training loss (ink) and evaluation loss (grey dots) by step, log scale."""
    import math

    train = [(h["step"], h["loss"]) for h in history if "loss" in h and "step" in h]
    evals = [(h["step"], h["eval_loss"]) for h in history if "eval_loss" in h]
    width, height, left, right, top, bottom = 900, 420, 70, 20, 40, 50
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()
    points = train + evals
    max_step = max(s for s, _ in points)
    low = math.log10(min(v for _, v in points))
    high = math.log10(max(v for _, v in points))

    def xy(step: float, value: float) -> tuple[float, float]:
        x = left + (width - left - right) * step / max_step
        y = top + (height - top - bottom) * (high - math.log10(value)) / (high - low or 1)
        return x, y

    for exponent in range(math.floor(low), math.ceil(high) + 1):
        if low <= exponent <= high:
            _, y = xy(0, 10**exponent)
            draw.line([(left, y), (width - right, y)], fill=RULES)
            draw.text((8, y - 6), f"1e{exponent}", fill=MUTED, font=font)
    draw.line([xy(s, v) for s, v in train], fill=INK, width=2)
    for s, v in evals:
        x, y = xy(s, v)
        draw.ellipse([x - 4, y - 4, x + 4, y + 4], fill=GREY)
    for step in range(0, max_step + 1, 100):
        x, _ = xy(step, 10**low)
        draw.text((x - 8, height - bottom + 10), str(step), fill=MUTED, font=font)
    draw.text(
        (left, 12),
        f"{name}: training loss (line) and evaluation loss (dots) by step, log scale",
        fill=INK,
        font=font,
    )
    image.save(path)


def settings(config: dict[str, Any] | None) -> dict[str, str | None]:
    if config is None:
        return {"lora": None, "optimizer": None, "batch": None}
    return {
        "lora": f"r {config['lora_r']}, alpha {config['lora_alpha']},"
        f" dropout {config['lora_dropout']}",
        "optimizer": f"{config['optim']}, learning rate {config['learning_rate']},"
        f" {config['lr_scheduler_type']}",
        "batch": f"{config['per_device_train_batch_size']} x"
        f" {config['gradient_accumulation_steps']} accumulation",
    }


def fmt(value: Any, unit: str = "") -> str:
    if value is None:
        return NOT_LOGGED
    if isinstance(value, float):
        return f"{value:.6f}{unit}" if value < 1 else f"{value:,.1f}{unit}"
    return f"{value}{unit}"


def main() -> None:
    PNG.mkdir(parents=True, exist_ok=True)
    rows = []
    for key, (model, folder, data) in RUNS.items():
        log, config, lengths = (
            load(folder, "training-log.json"),
            load(folder, "config.json"),
            load(folder, "lengths.json"),
        )
        if log is None:
            rows.append({"key": key, "model": model, "missing": True})
            continue
        history = log.get("history", [])
        steps = max((h.get("step", 0) for h in history), default=None)
        last_loss = next((h["loss"] for h in reversed(history) if "loss" in h), None)
        curve(model, history, PNG / f"loss-{key}.png")
        runtime = log.get("train_runtime_seconds")
        rows.append(
            {
                "key": key,
                "model": model,
                "data": data,
                "base": (config or {}).get("base_model"),
                "train": (lengths or {}).get("train", {}).get("records"),
                "validation": (lengths or {}).get("validation", {}).get("records"),
                **settings(config),
                "epochs": (config or {}).get("num_train_epochs"),
                "steps": steps,
                "gpu": log.get("gpu"),
                "precision": log.get("precision"),
                "runtime": f"{runtime / 3600:.2f} h ({runtime:,} s)" if runtime else None,
                "per_step": log.get("seconds_per_step"),
                "train_loss": log.get("train_loss"),
                "last_loss": last_loss,
                "best_eval": log.get("best_eval_loss"),
                "evaluations": log.get("evaluations"),
            }
        )
    OUT.write_text(markdown(rows), encoding="utf-8")
    print(markdown(rows))


def markdown(rows: list[dict[str, Any]]) -> str:
    fields = [
        ("Data", "data"),
        ("Base model", "base"),
        ("Training records", "train"),
        ("Validation records", "validation"),
        ("LoRA", "lora"),
        ("Optimizer", "optimizer"),
        ("Batch", "batch"),
        ("Epochs", "epochs"),
        ("Steps", "steps"),
        ("GPU", "gpu"),
        ("Precision", "precision"),
        ("Run time (training)", "runtime"),
        ("Seconds per step", "per_step"),
        ("Mean training loss", "train_loss"),
        ("Final logged training loss", "last_loss"),
        ("Evaluations during training", "evaluations"),
        ("Best evaluation loss", "best_eval"),
    ]
    present = [r for r in rows if not r.get("missing")]
    lines = [
        "# Training: models v1, v2 and E4B",
        "",
        "Generated by `scripts/verify/training_report.py` from each Kaggle run's",
        "training-log.json, config.json and lengths.json; do not edit by hand. All runs: QLoRA",
        "with Unsloth on one Kaggle T4, 4-bit base model, sequences up to 3,072 tokens, seed",
        "20260921, loss on the responses only. E4B trained without evaluations (they ran out of",
        "T4 memory, D-TRAIN-2).",
        "",
        "| | " + " | ".join(r["model"] for r in present) + " |",
        "|---|" + "---|" * len(present),
        *[f"| {label} | " + " | ".join(fmt(r[k]) for r in present) + " |" for label, k in fields],
        "",
    ]
    for r in present:
        lines += [f"![{r['model']} loss](training/loss-{r['key']}.png)", ""]
    for r in rows:
        if r.get("missing"):
            lines += [f"{r['model']}: training log not downloaded, not logged here.", ""]
    return "\n".join(lines)


if __name__ == "__main__":
    main()
