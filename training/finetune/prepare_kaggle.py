"""Build the folder to upload as a PRIVATE Kaggle dataset, and the notebook that trains on it.

The records contain CPT codes, so the dataset must stay private (SOURCES.md). This script only
writes files under `data/generated/kaggle/`; uploading is done by a team member.

    uv run python -m training.finetune.prepare_kaggle --kaggle-user <username>
    uv run python -m training.finetune.prepare_kaggle --kaggle-user <username> --model-version 2
    uv run python -m training.finetune.prepare_kaggle --kaggle-user <username> --model-version 2 \
        --kernels   # also the kernel folders to push with the Kaggle CLI

Kernel folders (`kaggle kernels push -p <folder>`): `kernel-v2-smoke` and `kernel-v2-full` (one
private notebook, claimsense-finetune-v2, pushed as two versions) and the prepared E4B variant
(`kernel-v2-e4b-timing`, `kernel-v2-e4b-full`: unsloth/gemma-4-E4B-it, 4-bit QLoRA, same settings;
the timing run trains 20 steps to project the full run, D-MODEL-3).

Model v2 (Part 2 step 5): the v2 dataset (data/generated/decision_v2/, prompt decision_v3, policy
set v2), the same QLoRA settings as model v1 (its longest record is 2,761 tokens, under the max
length 3,072), the dataset also as a zip to upload, and a notebook writing to
`/kaggle/working/claimsense-v2`.
"""

import argparse
import json
import shutil
from pathlib import Path

from training.generate.common import GENERATED_DIR

HERE = Path(__file__).resolve().parent
DATASET_SLUG = "claimsense-decision"
V2 = {
    "slug": "claimsense-decision-v2",
    "notebook": "claimsense-finetune-v2.ipynb",
    "out": "/kaggle/working/claimsense-v2",
    "prompt_version": "decision_v3",
    "policy_set": "v2",
}


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
EXTRA = "{smoke_extra}" if SMOKE else ""
OUT = "/kaggle/working/claimsense-smoke" if SMOKE else "{out}"
"""


SMOKE_EXTRA = "--limit 50 --epochs 1 --eval-limit 20 --eval-steps 3 --no-gguf"
FIND_DATASET = FIND_DATASET.replace("{smoke_extra}", SMOKE_EXTRA)


def notebook(
    dataset_slug: str,
    version: int = 1,
    out: str = "/kaggle/working/claimsense",
    smoke: bool = True,
    base_model: str | None = None,
    smoke_extra: str | None = None,
) -> dict:
    """`smoke_extra` replaces the smoke run's training arguments (the E4B timing run)."""
    title = (
        "# ClaimSense decision model v2: QLoRA fine-tuning (dataset v2, prompt decision_v3)"
        if version == 2
        else "# ClaimSense decision model: QLoRA fine-tuning (P4.3)"
    )
    cells = [
        (
            "markdown",
            f"{title}\n\n"
            "Accelerator: GPU T4 (the script uses one GPU). Internet: on. Input: the private "
            f"`{dataset_slug}` dataset.\nRun the smoke test first (`SMOKE = True`), then the full "
            "run (`SMOKE = False`). Outputs: `adapter/`, `gguf/`, `training-log.json`, "
            "`lengths.json`, `config.json`, `pip-freeze.txt`.",
        ),
        ("code", "!nvidia-smi\n!pip install --upgrade --quiet unsloth unsloth_zoo"),
        (
            "code",
            FIND_DATASET.replace("{out}", out)
            .replace("SMOKE = True", f"SMOKE = {smoke}")
            .replace("/kaggle/working/claimsense-smoke", f"{out}-smoke")
            .replace(SMOKE_EXTRA, smoke_extra or SMOKE_EXTRA),
        ),
        (
            "code",
            "!python {TRAIN} --data {DATA} --out {OUT} {EXTRA}"
            + (f" --base-model {base_model}" if base_model else ""),
        ),
        (
            "code",
            "import json\n"
            "print(open(f'{OUT}/lengths.json').read())\n"
            "log = json.load(open(f'{OUT}/training-log.json'))\n"
            "print({k: v for k, v in log.items() if k != 'history'})\n"
            "!ls -la {OUT}\n"
            "!ls -la {OUT}/gguf 2>/dev/null || echo 'no GGUF yet (smoke run or export cell)'",
        ),
    ]
    cells.append(
        (
            "code",
            "# GGUF export from the saved adapter, only when there is no GGUF yet: tests the\n"
            "# export on the smoke adapter, and retries it if the full run's export failed.\n"
            "import glob\n"
            "!df -h /kaggle/working /tmp\n"
            "if not glob.glob(f'{OUT}/gguf/*.gguf'):\n"
            "    !python {TRAIN} --data {DATA} --out {OUT} --export-from {OUT}/adapter\n"
            "!ls -la {OUT}/gguf",
        )
    )
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


E4B = "unsloth/gemma-4-E4B-it"
# E4B timing run (D-MODEL-3): 20 training steps (160 records, batch 1 x 8 accumulation), one
# evaluation on 40 validation records, then the notebook's GGUF export cell: step, evaluation and
# export times to project the full run.
E4B_TIMING = "--limit 160 --epochs 1 --eval-limit 40 --eval-steps 20 --no-gguf"
KERNELS = {  # folder -> (kernel slug, smoke, base model, output folder, smoke arguments)
    "kernel-v2-smoke": ("claimsense-finetune-v2", True, None, V2["out"], None),
    "kernel-v2-full": ("claimsense-finetune-v2", False, None, V2["out"], None),
    "kernel-v2-e4b-timing": (
        "claimsense-finetune-v2-e4b",
        True,
        E4B,
        V2["out"] + "-e4b",
        E4B_TIMING,
    ),
    "kernel-v2-e4b-full": ("claimsense-finetune-v2-e4b", False, E4B, V2["out"] + "-e4b", None),
}


def kernels(out_dir: Path, kaggle_user: str, dataset_slug: str) -> list[Path]:
    """The private kernel folders for model v2 (notebook and kernel-metadata.json each)."""
    folders = []
    for folder, (slug, smoke, base_model, out, extra) in KERNELS.items():
        path = out_dir / folder
        if path.exists():
            shutil.rmtree(path)
        path.mkdir(parents=True)
        code = f"{slug}.ipynb"
        (path / code).write_text(
            json.dumps(notebook(dataset_slug, 2, out, smoke, base_model, extra), indent=1)
        )
        (path / "kernel-metadata.json").write_text(
            json.dumps(
                {
                    "id": f"{kaggle_user}/{slug}",
                    "title": slug,
                    "code_file": code,
                    "language": "python",
                    "kernel_type": "notebook",
                    "is_private": True,
                    "enable_gpu": True,
                    "enable_tpu": False,
                    "enable_internet": True,
                    "dataset_sources": [f"{kaggle_user}/{dataset_slug}"],
                    "competition_sources": [],
                    "kernel_sources": [],
                    "model_sources": [],
                },
                indent=2,
            )
        )
        folders.append(path)
    return folders


def prepare(
    decision_dir: Path,
    out_dir: Path,
    kaggle_user: str,
    slug: str = DATASET_SLUG,
    version: int = 1,
) -> Path:
    summary = json.loads((decision_dir / "summary.json").read_text())
    if summary.get("retrieval", "simulated") == "simulated":
        raise SystemExit("the dataset was built with simulated retrieval; regenerate it first")
    if version == 2:
        for key in ("prompt_version", "policy_set"):
            if summary.get(key) != V2[key]:
                raise SystemExit(f"not a v2 dataset: {key} is {summary.get(key)!r}")
        if summary["checks"]["problems"]:
            raise SystemExit("the v2 dataset has check problems; regenerate it")
    dataset = out_dir / (V2["slug"] if version == 2 else DATASET_SLUG)
    if dataset.exists():
        shutil.rmtree(dataset)
    (dataset / "finetune").mkdir(parents=True)
    for split in ("train", "validation", "test"):
        shutil.copy(decision_dir / f"{split}.jsonl", dataset / f"{split}.jsonl")
    shutil.copy(decision_dir / "summary.json", dataset / "summary.json")
    for extra in ("data-card.md", "token_lengths.json"):
        if version == 2 and (decision_dir / extra).exists():
            shutil.copy(decision_dir / extra, dataset / extra)
    for name in ("train.py", "data.py"):
        shutil.copy(HERE / name, dataset / "finetune" / name)
    (dataset / "dataset-metadata.json").write_text(
        json.dumps(
            {
                "title": "ClaimSense decision dataset"
                + (" v2" if version == 2 else "")
                + " (private)",
                "id": f"{kaggle_user}/{slug}",
                "isPrivate": True,
                "licenses": [{"name": "other"}],
            },
            indent=2,
        )
    )
    if version == 2:
        (out_dir / V2["notebook"]).write_text(json.dumps(notebook(slug, 2, V2["out"]), indent=1))
        shutil.make_archive(str(out_dir / V2["slug"]), "zip", dataset)
    else:
        (out_dir / "claimsense-finetune.ipynb").write_text(json.dumps(notebook(slug), indent=1))
    return dataset


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--kaggle-user", required=True)
    parser.add_argument("--slug", help="the dataset's name in its URL")
    parser.add_argument("--decision-dir", type=Path)
    parser.add_argument("--out", type=Path, default=GENERATED_DIR / "kaggle")
    parser.add_argument("--model-version", type=int, choices=(1, 2), default=1)
    parser.add_argument("--kernels", action="store_true", help="v2: also the kernel folders")
    args = parser.parse_args()
    v2 = args.model_version == 2
    decision_dir = args.decision_dir or GENERATED_DIR / ("decision_v2" if v2 else "decision")
    slug = args.slug or (V2["slug"] if v2 else DATASET_SLUG)
    dataset = prepare(decision_dir, args.out, args.kaggle_user, slug, args.model_version)
    print(f"dataset folder: {dataset}")
    if v2:
        print(f"zip to upload: {args.out / (V2['slug'] + '.zip')}")
    print(f"notebook: {args.out / (V2['notebook'] if v2 else 'claimsense-finetune.ipynb')}")
    if v2 and args.kernels:
        for folder in kernels(args.out, args.kaggle_user, slug):
            print(f"kernel folder: {folder}")
    print("Upload the folder as a PRIVATE Kaggle dataset, then import the notebook.")


if __name__ == "__main__":
    main()
