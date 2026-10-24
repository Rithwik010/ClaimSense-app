"""Model v3 on Kaggle (D-V3-9): the private dataset and the notebooks; this script pushes nothing.

The dataset (`data/generated/kaggle/claimsense-decision-v3/`, PRIVATE: the records hold CPT codes)
holds the v3 training mix, the v3 validation split and the training scripts. Fine-tuning starts from
the base model with v2's QLoRA settings (training/finetune/data.py), for one epoch over the mix.

Kernel folders (`uvx kaggle kernels push -p <folder>`):

- `kernel-v3-timing`: the timing run. 25 steps with an evaluation and a checkpoint at steps 10 and
  20 (so the best checkpoint is chosen from two) and one at step 25; it writes the exact token
  lengths of every record, and its log each step's seconds, tokens and records. The memory probe
  (`train.py --memory-probe`, its own process) ran on 24 Oct and is not repeated (D-V3-20).
- `kernel-v3-resume`: attaches the timing run's output and resumes from its step-20 checkpoint for
  steps 21 to 25. Its losses, learning rates and records must repeat the timing run's steps 21 to
  25, from the checkpoint's step, schedule and optimizer state: the resume check.
- `kernel-v3-full-1` and `kernel-v3-full-2`: the full run in two sessions. Each stops itself, with a
  checkpoint, `SESSION_HOURS` after its notebook started, before Kaggle's 12-hour limit (and saves
  one every `SAVE_STEPS` steps); the second attaches the first's output, resumes from its latest
  checkpoint and finishes, with two GGUF exports: the
  checkpoint with the lowest validation loss (`adapter`, `gguf/`) and the final one
  (`adapter-final`, `final/gguf/`). Every evaluation uses the first `EVAL_LIMIT` validation
  records (D-V3-13).

    uv run python -m training.finetune.prepare_kaggle_v3 --max-seq-length 4096
"""

import argparse
import json
import shutil
from pathlib import Path

from training.generate.common import GENERATED_DIR
from training.generate.v3.config import OUT_DIR as V3_DIR
from training.generate.v3.kaggle import upload_problems

HERE = Path(__file__).resolve().parent
USER = "manideep3183"
SLUG = "claimsense-decision-v3"
SESSION_HOURS = 11  # the safety stop, from the notebook's start: under Kaggle's 12 h (24 Oct)
SAVE_STEPS = 125
EVAL_LIMIT = 150  # the fixed validation subset (its first 150 records) of every evaluation
TIMING = (
    f"--max-steps 25 --save-steps 10 --eval-steps 10 --eval-limit {EVAL_LIMIT} --logging-steps 1"
)
KERNELS = {  # folder -> (kernel slug, output folder, arguments, source kernel, resume from)
    "kernel-v3-timing": (
        "claimsense-finetune-v3-timing",
        "/kaggle/working/claimsense-v3-timing",
        f"{TIMING} --no-gguf",
        None,
        None,
    ),
    "kernel-v3-resume": (
        "claimsense-finetune-v3-resume",
        "/kaggle/working/claimsense-v3-resume",
        f"{TIMING} --no-gguf",
        "claimsense-finetune-v3-timing",
        "checkpoint-20",
    ),
    "kernel-v3-full-1": (
        "claimsense-finetune-v3-full-1",
        "/kaggle/working/claimsense-v3",
        f"--epochs 1 --save-steps {SAVE_STEPS} --eval-limit {EVAL_LIMIT} "
        f"--stop-after-hours {SESSION_HOURS} --session-start {{T0}} --no-gguf",
        None,
        None,
    ),
    "kernel-v3-full-2": (
        "claimsense-finetune-v3-full-2",
        "/kaggle/working/claimsense-v3",
        f"--epochs 1 --save-steps {SAVE_STEPS} --eval-limit {EVAL_LIMIT} "
        f"--stop-after-hours {SESSION_HOURS} --session-start {{T0}}",
        "claimsense-finetune-v3-full-1",
        "latest",
    ),
}


def notebook(title: str, out: str, extra: str, source: str | None, resume: str | None) -> dict:
    find = (
        "import glob, os\n"
        "found = glob.glob('/kaggle/input/**/train_mix.jsonl', recursive=True)\n"
        "assert found, 'attach the private claimsense-decision-v3 dataset'\n"
        "DATA = os.path.dirname(found[0])\n"
        "TRAIN = glob.glob('/kaggle/input/**/finetune/train.py', recursive=True)[0]\n"
        f"OUT = '{out}'\n"
        "RESUME = ''\n"
    )
    if resume == "latest":
        find += (
            f"RESUME = '--resume-from ' + os.path.dirname(glob.glob('/kaggle/input/**/{source}/"
            "**/trainer_state.json', recursive=True)[0]).rsplit('/checkpoint-', 1)[0]\n"
        )
    elif resume:
        find += (
            f"RESUME = '--resume-from ' + os.path.dirname(glob.glob('/kaggle/input/**/{source}/"
            f"**/{resume}/trainer_state.json', recursive=True)[0])\n"
        )
    find += "print(DATA, TRAIN, RESUME)\n"
    probe = "--memory-probe" in extra.split()
    extra = " ".join(a for a in extra.split() if a != "--memory-probe")
    command = (
        "!python {TRAIN} --data {DATA} --out {OUT} --train-split train_mix "
        "--max-seq-length {MAX_SEQ} "
    )
    cells = [
        ("markdown", f"# {title}\n\nSynthetic data only; private dataset and notebook."),
        (
            "code",
            "import time\nT0 = time.time()  # the session's start, for the safety stop\n"
            "!nvidia-smi\n!pip install --upgrade --quiet unsloth unsloth_zoo",
        ),
        ("code", find),
        *(  # in its own process: a probe in the training process breaks the first evaluation
            [("code", "# the longest record's peak GPU memory\n" + command + "--memory-probe")]
            if probe
            else []
        ),
        ("code", command + extra + " {RESUME}"),
        *(
            [
                (
                    "code",
                    "# the final checkpoint's GGUF too (stage 5 compares it with the best one);\n"
                    "# only when training finished (a session stopped early has no adapter-final)\n"
                    "if os.path.exists(f'{OUT}/adapter-final'):\n"
                    "    !python {TRAIN} --export-from {OUT}/adapter-final --out {OUT}/final "
                    "--data {DATA} --max-seq-length {MAX_SEQ}",
                )
            ]
            if title.endswith("full-2")
            else []
        ),
        (
            "code",
            "import json\n"
            "log = json.load(open(f'{OUT}/training-log.json'))\n"
            "print(json.dumps({k: v for k, v in log.items() if k != 'history'}, indent=1))\n"
            "print([(h.get('step'), h.get('loss'), h.get('eval_loss')) for h in log['history']])\n"
            "!ls -la {OUT} {OUT}/checkpoints",
        ),
    ]
    return {
        "cells": [
            {
                "cell_type": kind,
                "metadata": {},
                "source": source_text,
                **({"execution_count": None, "outputs": []} if kind == "code" else {}),
            }
            for kind, source_text in cells
        ],
        "metadata": {"kernelspec": {"name": "python3", "display_name": "Python 3"}},
        "nbformat": 4,
        "nbformat_minor": 5,
    }


def prepare(max_seq_length: int, out_dir: Path = GENERATED_DIR / "kaggle") -> list[Path]:
    final = V3_DIR / "final"
    dataset = out_dir / SLUG
    if dataset.exists():
        shutil.rmtree(dataset)
    (dataset / "finetune").mkdir(parents=True)
    for name in ("train_mix.jsonl", "validation.jsonl", "stats.json"):
        shutil.copy(final / name, dataset / name)
    for name in ("train.py", "data.py"):
        shutil.copy(HERE / name, dataset / "finetune" / name)
    (dataset / "dataset-metadata.json").write_text(
        json.dumps(
            {
                "title": "ClaimSense decision dataset v3 (private)",
                "id": f"{USER}/{SLUG}",
                "isPrivate": True,
                "licenses": [{"name": "other"}],
            },
            indent=2,
        )
    )
    folders = [dataset]
    for folder, (slug, out, extra, source, resume) in KERNELS.items():
        path = out_dir / folder
        if path.exists():
            shutil.rmtree(path)
        path.mkdir(parents=True)
        book = notebook(f"ClaimSense model v3: {slug}", out, extra, source, resume)
        text = json.dumps(book, indent=1).replace("{MAX_SEQ}", str(max_seq_length))
        (path / f"{slug}.ipynb").write_text(text)
        (path / "kernel-metadata.json").write_text(
            json.dumps(
                {
                    "id": f"{USER}/{slug}",
                    "title": slug,
                    "code_file": f"{slug}.ipynb",
                    "language": "python",
                    "kernel_type": "notebook",
                    "is_private": True,
                    "enable_gpu": True,
                    "machine_shape": "NvidiaTeslaT4",
                    "enable_tpu": False,
                    "enable_internet": True,
                    "dataset_sources": [f"{USER}/{SLUG}"],
                    "competition_sources": [],
                    "kernel_sources": [f"{USER}/{source}"] if source else [],
                    "model_sources": [],
                },
                indent=2,
            )
        )
        folders.append(path)
    problems = upload_problems(folders)
    if problems:
        raise SystemExit("upload check failed:\n" + "\n".join(problems[:40]))
    return folders


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--max-seq-length", type=int, required=True)
    parser.add_argument("--out", type=Path, default=GENERATED_DIR / "kaggle")
    args = parser.parse_args()
    for folder in prepare(args.max_seq_length, args.out):
        print(folder)


if __name__ == "__main__":
    main()
