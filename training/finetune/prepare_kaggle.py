"""Build the folder to upload as a PRIVATE Kaggle dataset, and the notebook that trains on it.

The records contain CPT codes, so the dataset must stay private (SOURCES.md). This script only
writes files under `data/generated/kaggle/`; uploading is done by a team member.

    uv run python -m training.finetune.prepare_kaggle --kaggle-user <username>
"""

import argparse
import json
import shutil
from pathlib import Path

from training.generate.common import GENERATED_DIR

HERE = Path(__file__).resolve().parent
DATASET_SLUG = "claimsense-decision"


FIND_DATASET = """import glob, os

# Finds the attached private dataset wherever Kaggle mounts it (any name, flattened or not).
data_files = glob.glob("/kaggle/input/**/train.jsonl", recursive=True)
scripts = glob.glob("/kaggle/input/**/train.py", recursive=True)
assert data_files, "Add Input: attach the private ClaimSense dataset"
assert scripts, "train.py not found in the dataset: upload the finetune folder too"
DATA = os.path.dirname(data_files[0])
TRAIN = scripts[0]
assert os.path.exists(os.path.join(os.path.dirname(TRAIN), "data.py")), "data.py missing"
print("data:", DATA)
print("script:", TRAIN)
print(sorted(os.listdir(DATA)))

# Smoke test first (a few minutes): SMOKE = True. Full training run: SMOKE = False.
SMOKE = True
EXTRA = "--limit 50 --epochs 1 --eval-limit 20 --eval-steps 3 --no-gguf" if SMOKE else ""
OUT = "/kaggle/working/claimsense-smoke" if SMOKE else "/kaggle/working/claimsense"
"""


def notebook(dataset_slug: str) -> dict:
    cells = [
        (
            "markdown",
            "# ClaimSense decision model: QLoRA fine-tuning (P4.3)\n\n"
            "Accelerator: GPU T4 (the script uses one GPU). Internet: on. Input: the private "
            f"`{dataset_slug}` dataset.\nRun the smoke test first (`SMOKE = True`), then the full "
            "run (`SMOKE = False`). Outputs: `adapter/`, `gguf/`, `training-log.json`, "
            "`lengths.json`, `config.json`, `pip-freeze.txt`.",
        ),
        ("code", "!nvidia-smi\n!pip install --upgrade --quiet unsloth unsloth_zoo"),
        ("code", FIND_DATASET),
        ("code", "!python {TRAIN} --data {DATA} --out {OUT} {EXTRA}"),
        (
            "code",
            "import json\n"
            "print(open(f'{OUT}/lengths.json').read())\n"
            "log = json.load(open(f'{OUT}/training-log.json'))\n"
            "print({k: v for k, v in log.items() if k != 'history'})\n"
            "!ls -la {OUT} {OUT}/gguf",
        ),
    ]
    return {
        "cells": [
            {
                "cell_type": kind,
                "metadata": {},
                "source": source,
                **({"execution_count": None, "outputs": []} if kind == "code" else {}),
            }
            for kind, source in cells
        ],
        "metadata": {"kernelspec": {"name": "python3", "display_name": "Python 3"}},
        "nbformat": 4,
        "nbformat_minor": 5,
    }


def prepare(decision_dir: Path, out_dir: Path, kaggle_user: str, slug: str = DATASET_SLUG) -> Path:
    summary = json.loads((decision_dir / "summary.json").read_text())
    if summary.get("retrieval", "simulated") == "simulated":
        raise SystemExit("the dataset was built with simulated retrieval; regenerate it first")
    dataset = out_dir / DATASET_SLUG
    if dataset.exists():
        shutil.rmtree(dataset)
    (dataset / "finetune").mkdir(parents=True)
    for split in ("train", "validation", "test"):
        shutil.copy(decision_dir / f"{split}.jsonl", dataset / f"{split}.jsonl")
    shutil.copy(decision_dir / "summary.json", dataset / "summary.json")
    for name in ("train.py", "data.py"):
        shutil.copy(HERE / name, dataset / "finetune" / name)
    (dataset / "dataset-metadata.json").write_text(
        json.dumps(
            {
                "title": "ClaimSense decision dataset (private)",
                "id": f"{kaggle_user}/{slug}",
                "isPrivate": True,
                "licenses": [{"name": "other"}],
            },
            indent=2,
        )
    )
    (out_dir / "claimsense-finetune.ipynb").write_text(json.dumps(notebook(slug), indent=1))
    return dataset


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--kaggle-user", required=True)
    parser.add_argument("--slug", default=DATASET_SLUG, help="the dataset's name in its URL")
    parser.add_argument("--decision-dir", type=Path, default=GENERATED_DIR / "decision")
    parser.add_argument("--out", type=Path, default=GENERATED_DIR / "kaggle")
    args = parser.parse_args()
    dataset = prepare(args.decision_dir, args.out, args.kaggle_user, args.slug)
    print(f"dataset folder: {dataset}")
    print(f"notebook: {args.out / 'claimsense-finetune.ipynb'}")
    print("Upload the folder as a PRIVATE Kaggle dataset, then import the notebook.")


if __name__ == "__main__":
    main()
