"""Why v3's two GGUFs differ (25 Oct): the training session's two adapters compared. Report only.

Session 2 ended at the last step with the lowest validation loss there (checkpoint-1250), so the
`adapter` the trainer saved (the best model, loaded at the end) and `adapter-final` (a copy of the
last checkpoint) should hold the same weights; yet their exports have different SHA-256
(dd4cf0ff... and 46a4c062...). This writes a CPU-only notebook (no GPU quota) that reads both
adapter_model.safetensors from the session's output and reports, per file, its SHA-256 and the
tensors' names, dtypes and shapes, and per tensor the largest absolute difference. Equal tensors
mean the merge or conversion is not bit-for-bit repeatable; different ones, that the two adapters
are not the same weights. The notebook's report.json is downloaded with
`uvx kaggle kernels output manideep3183/claimsense-v3-adapter-compare -p <dir>`.

    uv run python -m scripts.kaggle.v3_adapter_compare [--source claimsense-finetune-v3-full-2]
    uvx kaggle kernels push -p data/generated/kaggle/kernel-v3-adapter-compare
"""

import argparse
import json
from pathlib import Path

from training.finetune.prepare_kaggle_v3 import USER
from training.generate.common import GENERATED_DIR

SLUG = "claimsense-v3-adapter-compare"
CODE = r"""
import glob, hashlib, json, os
from safetensors.torch import load_file

def find(folder):
    pattern = f'/kaggle/input/**/{folder}/adapter_model.safetensors'
    found = sorted(glob.glob(pattern, recursive=True))
    assert len(found) == 1, (folder, found)
    return found[0]

files = {name: find(name) for name in ('adapter', 'adapter-final')}
report = {}
for name, path in files.items():
    report[name] = {
        'path': path,
        'bytes': os.path.getsize(path),
        'sha256': hashlib.sha256(open(path, 'rb').read()).hexdigest(),
    }
best, final = load_file(files['adapter']), load_file(files['adapter-final'])
report['same_names'] = sorted(best) == sorted(final)
report['only_in_adapter'] = sorted(set(best) - set(final))[:20]
report['only_in_final'] = sorted(set(final) - set(best))[:20]
diffs = {}
for key in sorted(set(best) & set(final)):
    a, b = best[key], final[key]
    row = {'dtypes': [str(a.dtype), str(b.dtype)], 'shape_equal': tuple(a.shape) == tuple(b.shape)}
    if row['shape_equal']:
        row['max_abs_diff'] = float((a.float() - b.float()).abs().max())
        row['equal'] = bool((a == b).all()) if a.dtype == b.dtype else False
    diffs[key] = row
report['tensors'] = len(diffs)
report['tensors_equal'] = sum(r.get('equal', False) for r in diffs.values())
report['dtypes'] = sorted({tuple(r['dtypes']) for r in diffs.values()})
report['largest_diff'] = max((r.get('max_abs_diff', 0.0) for r in diffs.values()), default=0.0)
report['examples'] = dict(list(diffs.items())[:5])
os.makedirs('/kaggle/working/compare', exist_ok=True)
json.dump(report, open('/kaggle/working/compare/report.json', 'w'), indent=2)
print(json.dumps({k: v for k, v in report.items() if k != 'examples'}, indent=2))
"""


def write(source: str) -> Path:
    folder = GENERATED_DIR / "kaggle" / "kernel-v3-adapter-compare"
    folder.mkdir(parents=True, exist_ok=True)
    notebook = {
        "cells": [{"cell_type": "code", "metadata": {}, "source": CODE, "outputs": []}],
        "metadata": {"kernelspec": {"name": "python3", "display_name": "Python 3"}},
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    (folder / f"{SLUG}.ipynb").write_text(json.dumps(notebook, indent=1))
    (folder / "kernel-metadata.json").write_text(
        json.dumps(
            {
                "id": f"{USER}/{SLUG}",
                "title": SLUG,
                "code_file": f"{SLUG}.ipynb",
                "language": "python",
                "kernel_type": "notebook",
                "is_private": True,
                "enable_gpu": False,
                "enable_tpu": False,
                "enable_internet": False,
                "dataset_sources": [],
                "competition_sources": [],
                "kernel_sources": [f"{USER}/{source}"],
                "model_sources": [],
            },
            indent=2,
        )
    )
    return folder


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source", default="claimsense-finetune-v3-full-2")
    print(write(parser.parse_args().source))


if __name__ == "__main__":
    main()
