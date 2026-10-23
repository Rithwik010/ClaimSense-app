"""Decision-model evaluation on Kaggle (model v3 study, D-V3-13): the same scorer as on the laptop
(training/evaluate/model.py), with Ollama on a T4 x2.

`prepare` writes data/generated/kaggle/<name>/ with:

- `dataset/` (PRIVATE: the records hold CPT codes):
  - `code/`: app/ and training/ (Python files only) and data/curated/, the scorer's imports;
  - `sets/<set>/shard-<n>/`: each test set as test.jsonl, test_inputs.jsonl and summary.json, cut
    into shards so both GPUs work;
  - `models/<key>.json`: the model name, the Modelfile (its FROM is filled in on Kaggle) and the
    SHA-256 its GGUF must have; `run.json`: the jobs and the Ollama version;
- `kernel/`: the notebook. It installs the laptop's Ollama version, starts one server per GPU
  (OLLAMA_NUM_PARALLEL=1: answers one at a time, as on the laptop), finds each model's GGUF in its
  training notebook's output, checks its SHA-256, creates the model from the pinned Modelfile,
  and runs every (model, set, shard) job on the server its shard is given to. The predictions,
  with each raw answer, go to /kaggle/working/eval/.

The Modelfiles are built here from the laptop's `ollama show <base> --modelfile`
(training/finetune/modelfile.py) and must equal the model's evaluated settings
(training/finetune/evaluated/<model>.json); a model without that file yet (v3 before its pinning)
must equal v2's, so both are decoded the same way.

    uv run python -m training.evaluate.kaggle_eval prepare --name eval-messy-v2 --models v2 \\
        --sets test_messy
    uv run python -m training.evaluate.kaggle_eval collect --name eval-messy-v2   # after download

`collect` merges the shards of each (model, set) into data/generated/eval/v3study/<model>-<set>
.jsonl.
"""

import argparse
import json
import re
import shutil
from pathlib import Path
from typing import Any

import httpx

from training.finetune.modelfile import build, differences, evaluated, settings
from training.generate.common import GENERATED_DIR
from training.generate.v3.config import OUT_DIR as V3_DIR
from training.generate.v3.kaggle import upload_problems

ROOT = Path(__file__).resolve().parents[2]
USER = "manideep3183"
KERNEL = "claimsense-v3-eval"
BASE = "gemma4:e2b"
SHARDS = 2  # one per T4
MODELS = {
    "v2": {
        "name": "claimsense-decision:v2",
        "evaluated": "claimsense-decision-v2",
        "kernel": "claimsense-finetune-v2",
    },
    "v3": {
        "name": "claimsense-decision:v3",
        "evaluated": "claimsense-decision-v3",
        "kernel": "claimsense-finetune-v3-full-2",
    },
}
SETS = {  # name -> (folder, split)
    "clean": (GENERATED_DIR / "decision_v2", "test"),
    "test_messy": (V3_DIR / "final", "test_messy"),
    "test_unseen_style": (V3_DIR / "final", "test_unseen_style"),
    "human_style": (V3_DIR / "final", "test_human_style"),  # LLM-written human-style test set
}
STUDY_DIR = GENERATED_DIR / "eval" / "v3study"
PIP = [
    "pydantic==2.13.5",
    "pydantic-settings==2.15.0",
    "httpx==0.28.1",
    "ollama==0.6.2",
    "python-dotenv==1.2.3",
]


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def model_entry(key: str, ollama_url: str = "http://127.0.0.1:11434") -> dict[str, Any]:
    """The model's Modelfile (FROM to be filled in on Kaggle) and the GGUF hash it must have."""
    spec = MODELS[key]
    base = httpx.post(f"{ollama_url}/api/show", json={"model": BASE}, timeout=30).json()[
        "modelfile"
    ]
    text = re.sub(r"^FROM .*$", "FROM __GGUF__", build(Path("__GGUF__"), base), flags=re.M)
    pinned = evaluated(spec["name"]) or evaluated(MODELS["v2"]["name"])
    if pinned is None:
        raise SystemExit("v2's evaluated settings are missing")
    found = differences(pinned["settings"], settings(text))
    if found:
        raise SystemExit(f"{key}: the Modelfile would differ from the pinned settings: {found}")
    own = evaluated(spec["name"])
    return {
        "key": key,
        "name": spec["name"],
        "kernel": f"{USER}/{spec['kernel']}",
        "modelfile": text,
        "weights_sha256": own["weights_sha256"] if own else None,
        "ollama": pinned["ollama"],
    }


def write_set(name: str, dataset: Path) -> dict[str, int]:
    folder, split = SETS[name]
    records_path = folder / f"{split}.jsonl"
    if not records_path.exists():
        return {}
    records = read_jsonl(records_path)
    inputs = {i["record_id"]: i for i in read_jsonl(folder / f"{split}_inputs.jsonl")}
    summary = folder / "summary.json"
    meta = (
        json.loads(summary.read_text())
        if summary.exists()
        else {"generator_version": "decision-dataset-v3", "prompt_version": "decision_v3"}
    )
    sizes = {}
    for n in range(SHARDS):
        part = records[n::SHARDS]
        out = dataset / "sets" / name / f"shard-{n}"
        write_jsonl(out / "test.jsonl", part)
        write_jsonl(out / "test_inputs.jsonl", [inputs[r["metadata"]["record_id"]] for r in part])
        (out / "summary.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
        sizes[f"shard-{n}"] = len(part)
    return sizes


def copy_code(dataset: Path) -> None:
    code = dataset / "code"
    for package in ("app", "training"):
        for path in (ROOT / package).rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            target = code / path.relative_to(ROOT)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(path, target)
    shutil.copytree(ROOT / "data" / "curated", code / "data" / "curated")


def notebook(title: str) -> dict[str, Any]:
    setup = (
        "import glob, json, os, subprocess, sys, time, hashlib\n"
        "found = glob.glob('/kaggle/input/**/run.json', recursive=True)\n"
        "found = [f for f in found if os.path.isdir(os.path.join(os.path.dirname(f), 'sets'))]\n"
        "assert found, 'attach the private evaluation dataset'\n"
        "DATA = os.path.dirname(found[0])\n"
        "run = json.load(open(os.path.join(DATA, 'run.json')))\n"
        "OUT = '/kaggle/working/eval'\n"
        "os.makedirs(OUT, exist_ok=True)\n"
        "subprocess.run('curl -fsSL https://ollama.com/install.sh | OLLAMA_VERSION=' "
        "+ run['ollama'] + ' sh', shell=True, check=True)\n"
        "subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', *run['pip']], check=True)\n"
        "print(subprocess.run(['ollama', '--version'], capture_output=True, text=True).stdout)\n"
    )
    servers = (
        "servers = {}\n"
        "for gpu in range(run['shards']):\n"
        "    port = 11434 + gpu\n"
        "    env = dict(os.environ, CUDA_VISIBLE_DEVICES=str(gpu),\n"
        "               OLLAMA_HOST=f'127.0.0.1:{port}', OLLAMA_NUM_PARALLEL='1',\n"
        "               OLLAMA_KEEP_ALIVE='-1', OLLAMA_NO_CLOUD='1')\n"
        "    log = open(f'{OUT}/ollama-{gpu}.log', 'w')\n"
        "    servers[gpu] = subprocess.Popen(['ollama', 'serve'], env=env,\n"
        "                                    stdout=log, stderr=log)\n"
        "time.sleep(10)\n"
        "def on(gpu, *args):\n"
        "    env = dict(os.environ, OLLAMA_HOST=f'127.0.0.1:{11434 + gpu}')\n"
        "    return subprocess.run(['ollama', *args], env=env, capture_output=True, text=True)\n"
        "for key, model in run['models'].items():\n"
        "    owner, slug = model['kernel'].split('/')\n"
        "    ggufs = glob.glob(f'/kaggle/input/{slug}/**/*Q4_K_M.gguf', recursive=True)\n"
        "    assert ggufs, f'no GGUF in the output of {model[\"kernel\"]}'\n"
        "    gguf = ggufs[0]\n"
        "    digest = hashlib.sha256()\n"
        "    with open(gguf, 'rb') as f:\n"
        "        for block in iter(lambda: f.read(1 << 24), b''):\n"
        "            digest.update(block)\n"
        "    sha = digest.hexdigest()\n"
        "    print(key, gguf, sha)\n"
        "    if model['weights_sha256']:\n"
        "        assert sha == model['weights_sha256'], f'{key}: not the evaluated weights'\n"
        "    json.dump({'gguf': gguf, 'sha256': sha}, open(f'{OUT}/{key}-weights.json', 'w'))\n"
        "    modelfile = f'/kaggle/working/{key}.Modelfile'\n"
        "    open(modelfile, 'w').write(model['modelfile'].replace('__GGUF__', gguf))\n"
        "    for gpu in servers:\n"
        "        made = on(gpu, 'create', model['name'], '-f', modelfile)\n"
        "        print(gpu, key, made.returncode, made.stderr[-300:])\n"
        "        assert made.returncode == 0\n"
    )
    jobs = (
        "sys.path.insert(0, os.path.join(DATA, 'code'))\n"
        "procs = []\n"
        "for gpu in servers:\n"
        "    mine = [j for j in run['jobs'] if j['gpu'] == gpu]\n"
        "    script = os.path.join(OUT, f'jobs-{gpu}.json')\n"
        "    json.dump(mine, open(script, 'w'))\n"
        "    env = dict(os.environ, PYTHONPATH=os.path.join(DATA, 'code'))\n"
        "    log = open(f'{OUT}/runner-{gpu}.log', 'w')\n"
        "    procs.append(subprocess.Popen([sys.executable, '-m',\n"
        "        'training.evaluate.kaggle_eval',\n"
        "        'run', '--jobs', script, '--data', DATA, '--out', OUT,\n"
        "        '--url', f'http://127.0.0.1:{11434 + gpu}'], env=env, stdout=log, stderr=log,\n"
        "        cwd='/kaggle/working'))\n"
        "while any(p.poll() is None for p in procs):\n"
        "    time.sleep(120)\n"
        "    for gpu in servers:\n"
        "        lines = open(f'{OUT}/runner-{gpu}.log').read().splitlines()\n"
        "        print(time.strftime('%H:%M:%S'), gpu, lines[-1:] , flush=True)\n"
        "print([p.returncode for p in procs])\n"
        "print(open(f'{OUT}/runner-0.log').read()[-3000:])\n"
    )
    cells = [
        ("markdown", f"# {title}\n\nSynthetic data only; private dataset and notebook."),
        ("code", "!nvidia-smi"),
        ("code", setup),
        ("code", servers),
        ("code", jobs),
    ]
    return {
        "cells": [
            {
                "cell_type": kind,
                "metadata": {},
                "source": text,
                **({"execution_count": None, "outputs": []} if kind == "code" else {}),
            }
            for kind, text in cells
        ],
        "metadata": {"kernelspec": {"name": "python3", "display_name": "Python 3"}},
        "nbformat": 4,
        "nbformat_minor": 5,
    }


def prepare(
    name: str, models: list[str], sets: list[str], out_dir: Path = GENERATED_DIR / "kaggle"
) -> dict[str, Any]:
    folder = out_dir / name
    dataset, kernel = folder / "dataset", folder / "kernel"
    for path in (dataset, kernel):
        if path.exists():
            shutil.rmtree(path)
        path.mkdir(parents=True)
    copy_code(dataset)
    from app.core.settings import get_settings

    url = get_settings().ollama_url  # the laptop's Ollama, for the base model's Modelfile
    entries = {key: model_entry(key, url) for key in models}
    written = {s: write_set(s, dataset) for s in sets}
    skipped = [s for s, sizes in written.items() if not sizes]
    jobs = []
    for key in models:
        for s, sizes in written.items():
            for n, shard in enumerate(sizes):
                jobs.append(
                    {
                        "model": key,
                        "set": s,
                        "shard": shard,
                        "gpu": n % SHARDS,
                        "label": f"{key}-{s}-{shard}",
                    }
                )
    ollama = {e["ollama"] for e in entries.values()}
    if len(ollama) != 1:
        raise SystemExit(f"the models were evaluated on different Ollama versions: {ollama}")
    run = {
        "ollama": ollama.pop(),
        "pip": PIP,
        "shards": SHARDS,
        "models": entries,
        "jobs": jobs,
    }
    (dataset / "run.json").write_text(json.dumps(run, indent=2), encoding="utf-8")
    slug = f"claimsense-v3-{name}"
    (dataset / "dataset-metadata.json").write_text(
        json.dumps(
            {
                "title": f"ClaimSense {name} (private)",
                "id": f"{USER}/{slug}",
                "isPrivate": True,
                "licenses": [{"name": "other"}],
            },
            indent=2,
        )
    )
    (kernel / f"{KERNEL}.ipynb").write_text(
        json.dumps(notebook(f"ClaimSense decision-model evaluation: {name}"), indent=1)
    )
    (kernel / "kernel-metadata.json").write_text(
        json.dumps(
            {
                "id": f"{USER}/{KERNEL}",
                "title": KERNEL,
                "code_file": f"{KERNEL}.ipynb",
                "language": "python",
                "kernel_type": "notebook",
                "is_private": True,
                "enable_gpu": True,
                "machine_shape": "NvidiaTeslaT4",
                "enable_tpu": False,
                "enable_internet": True,
                "dataset_sources": [f"{USER}/{slug}"],
                "competition_sources": [],
                "kernel_sources": sorted({e["kernel"] for e in entries.values()}),
                "model_sources": [],
            },
            indent=2,
        )
    )
    problems = upload_problems([dataset / "sets", dataset / "run.json", kernel])
    if problems:
        raise SystemExit("upload check failed:\n" + "\n".join(problems[:40]))
    return {
        "folder": str(folder),
        "jobs": len(jobs),
        "records": {s: sum(sizes.values()) for s, sizes in written.items()},
        "skipped_sets": skipped,
        "models": {
            k: {"name": e["name"], "sha256": e["weights_sha256"]} for k, e in entries.items()
        },
    }


def run_jobs(jobs_file: Path, data: Path, out: Path, url: str) -> None:
    """On Kaggle: each job's predictions through the scorer, against one Ollama server."""
    from app.ml.client import OllamaDecisionModel
    from training.evaluate.model import run

    jobs = json.loads(jobs_file.read_text())
    version = httpx.get(f"{url}/api/version", timeout=30).json()["version"]
    models = json.loads((data / "run.json").read_text())["models"]
    for job in jobs:
        model = OllamaDecisionModel(url, models[job["model"]]["name"])
        report = run(
            model,
            job["label"],
            dataset_dir=data / "sets" / job["set"] / job["shard"],
            out_dir=out,
            engine=f"ollama {version} T4",
        )
        metrics = report["metrics"]
        print(job["label"], metrics["records"], metrics["valid_output_rate"], flush=True)


def collect(name: str, out_dir: Path = GENERATED_DIR / "kaggle") -> dict[str, int]:
    """The downloaded predictions, the shards of each (model, set) merged, into STUDY_DIR."""
    run = json.loads((out_dir / name / "dataset" / "run.json").read_text())
    found = {}
    for job in run["jobs"]:
        path = next((out_dir / name / "output").rglob(f"{job['label']}.jsonl"), None)
        if path is None:
            continue
        key = f"{job['model']}-{job['set']}"
        found.setdefault(key, []).extend(read_jsonl(path))
    for key, rows in found.items():
        write_jsonl(STUDY_DIR / f"{key}.jsonl", rows)
    return {key: len(rows) for key, rows in found.items()}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    make = sub.add_parser("prepare")
    make.add_argument("--name", required=True)
    make.add_argument("--models", nargs="+", choices=sorted(MODELS), required=True)
    make.add_argument("--sets", nargs="+", choices=sorted(SETS), required=True)
    work = sub.add_parser("run")
    work.add_argument("--jobs", type=Path, required=True)
    work.add_argument("--data", type=Path, required=True)
    work.add_argument("--out", type=Path, required=True)
    work.add_argument("--url", required=True)
    take = sub.add_parser("collect")
    take.add_argument("--name", required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        print(json.dumps(prepare(args.name, args.models, args.sets), indent=2))
    elif args.command == "run":
        run_jobs(args.jobs, args.data, args.out, args.url)
    else:
        print(json.dumps(collect(args.name), indent=2))


if __name__ == "__main__":
    main()
