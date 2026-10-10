"""Build the folder to upload as a PRIVATE Kaggle dataset, and the notebook that trains on it.

The records contain CPT codes, so the dataset must stay private (SOURCES.md). This script only
writes files under `data/generated/kaggle/`; uploading is done by a team member.

    uv run python -m training.finetune.prepare_kaggle --kaggle-user <username>
    uv run python -m training.finetune.prepare_kaggle --kaggle-user <username> --model-version 2

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
EXTRA = "--limit 50 --epochs 1 --eval-limit 20 --eval-steps 3 --no-gguf" if SMOKE else ""
OUT = "/kaggle/working/claimsense-smoke" if SMOKE else "{out}"
"""


def notebook(dataset_slug: str, version: int = 1, out: str = "/kaggle/working/claimsense") -> dict:
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
        ("code", FIND_DATASET.replace("{out}", out)),
        ("code", "!python {TRAIN} --data {DATA} --out {OUT} {EXTRA}"),
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
    args = parser.parse_args()
    v2 = args.model_version == 2
    decision_dir = args.decision_dir or GENERATED_DIR / ("decision_v2" if v2 else "decision")
    slug = args.slug or (V2["slug"] if v2 else DATASET_SLUG)
    dataset = prepare(decision_dir, args.out, args.kaggle_user, slug, args.model_version)
    print(f"dataset folder: {dataset}")
    if v2:
        print(f"zip to upload: {args.out / (V2['slug'] + '.zip')}")
    print(f"notebook: {args.out / (V2['notebook'] if v2 else 'claimsense-finetune.ipynb')}")
    print("Upload the folder as a PRIVATE Kaggle dataset, then import the notebook.")


if __name__ == "__main__":
    main()
