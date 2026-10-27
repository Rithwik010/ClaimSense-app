"""Kaggle rounds for generator v3 (Phases 3 and 4; SPEC.md "Kaggle").

A round is one private dataset and one private notebook run on a T4 x2:

1. writer B (`llm.writer_b`) writes the notes its sheets need, then writer C (`llm.writer_c`);
2. the verifier (`llm.verifier`) answers for every writer A note waiting for it and for every note
   the writers wrote in this session.

`prepare_round` writes data/generated/v3/kaggle/round<N>/ with:

- `dataset/`: writers.jsonl, verify.jsonl, run.json, kaggle_stage.py and a private
  dataset-metadata.json;
- `kernel/`: the notebook and a private kernel-metadata.json (GPU, internet for the model
  downloads).

Before anything is uploaded, `upload_problems` checks every file:

- no AMA CPT descriptor text;
- no e-mail, phone or social security number pattern;
- only private metadata.

The jobs hold no names: a patient appears as age and sex only.

Upload and run (Kaggle CLI through uvx, D-TRAIN-1):

    uvx kaggle datasets create -p <round>/dataset   # later rounds: datasets version -m ...
    uvx kaggle quota                                # GPU hours left this week
    uvx kaggle kernels push -p <round>/kernel
    uvx kaggle kernels status manideep3183/claimsense-v3-llm
    uvx kaggle kernels output manideep3183/claimsense-v3-llm -p <round>/output
"""

import json
import re
import shutil
import zlib
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from training.generate.v3.config import HERE, OUT_DIR, config
from training.generate.v3.dataset import (
    gate_rows,
    latest,
    load_sheets,
    needs_note,
    read_jsonl,
    write_jsonl,
)
from training.generate.v3.llm import (
    JUDGE_SYSTEM,
    JUDGE_USER,
    VERIFIER_SYSTEM,
    VERIFIER_USER,
    judge_messages,
    statements,
    verifier_messages,
    writer_messages,
)

USER = "manideep3183"
KERNEL = "claimsense-v3-llm"
PII = {
    "e-mail address": re.compile(r"[\w.+-]+@[\w-]+\.[A-Za-z]{2,}"),
    "phone number": re.compile(r"\(?\b\d{3}\)?[-. ]\d{3}[-. ]\d{4}\b"),
    "social security number": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
}
# Assumed T4 x2 throughput, replaced by the pilot's measured numbers (llm.gpu_hours_estimate).
OUTPUT_TOKENS_PER_SECOND = 450
PROMPT_TOKENS_PER_SECOND = 3500
LOAD_SECONDS = 420  # install vLLM, download and load one model
CHARS_PER_TOKEN = 3.8


def _sampling(name: str) -> dict[str, Any]:
    llm = config()["llm"][name]
    return {
        "temperature": llm["temperature"],
        "top_p": llm.get("top_p", 1.0),
        "max_tokens": llm["max_tokens"],
    }


def run_config() -> dict[str, Any]:
    llm = config()["llm"]
    return {
        "vllm": llm["vllm"],
        "verifier_system": VERIFIER_SYSTEM,
        "verifier_user": VERIFIER_USER,
        "judge_system": JUDGE_SYSTEM,
        "judge_user": JUDGE_USER,
        "second_looks": bool(config()["verification"].get("second_look", True)),
        "stages": {
            name: {
                "kind": "verify" if name == "verifier" else "write",
                **({} if name == "verifier" else {"writer": name[-1].upper()}),
                "model": llm[name]["model"],
                "max_model_len": llm[name].get("max_model_len", llm["vllm"]["max_model_len"]),
                "max_num_seqs": llm[name].get("max_num_seqs", 256),
                **({"revision": llm[name]["revision"]} if llm[name].get("revision") else {}),
                **({"sampling": _sampling(name)} if name == "verifier" else {}),
            }
            for name in ("writer_b", "writer_c", "writer_d", "verifier")
        },
    }


def round_jobs(
    limit: int | None = None,
    out_dir: Path = OUT_DIR,
    looks_only: bool = False,
    rejudge: bool = False,
    only: tuple[str, ...] = (),
    new_only: bool = False,
) -> tuple[list[dict], list[dict]]:
    """Writer jobs (B and C sheets that need a note) and verifier jobs (writer A notes whose
    latest attempt has no verifier answer yet, and the second looks the gate waits for). `limit`:
    at most that many per writer (a pilot). `looks_only`: only the second looks, from the gate run
    in memory (before its official rerun writes gate.jsonl)."""
    sheets = load_sheets(out_dir)
    if looks_only:
        notes = latest(read_jsonl(out_dir / "notes.jsonl"))
        answers = {(v["sheet_id"], v["attempt"]): v for v in read_jsonl(out_dir / "verifier.jsonl")}
        looks = []
        for row in gate_rows(out_dir, ("judge",) if rejudge else ())[0]:
            if row["looks"]:
                note = notes[row["sheet_id"]]
                found = (answers.get((row["sheet_id"], note["attempt"])) or {}).get("answers")
                looks += second_looks(sheets[row["sheet_id"]], note, row["looks"], found or {})
        return [], looks
    needed = needs_note(out_dir)
    writers: list[dict] = []
    per_writer: dict[str, int] = {}
    for sheet_id, attempt in sorted(needed.items()):
        sheet = sheets[sheet_id]
        writer = sheet["writer"]
        if writer not in ("B", "C", "D") or (only and writer not in only):
            continue
        if new_only and attempt != 1:  # sheets never written: no rewrites of earlier notes
            continue
        if limit is not None and per_writer.get(writer, 0) >= limit:
            continue
        per_writer[writer] = per_writer.get(writer, 0) + 1
        name = f"writer_{writer.lower()}"
        writers.append(
            {
                "job_id": f"{sheet_id}#{attempt}",
                "sheet_id": sheet_id,
                "attempt": attempt,
                "writer": writer,
                "seed": zlib.crc32(f"{sheet['seed']}#{attempt}".encode()) % (2**31),
                "messages": writer_messages(sheet, attempt),
                "sampling": _sampling(name),
                "statements": [
                    {
                        "id": s["id"],
                        "statement": s["statement"],
                        "fact_id": s["fact_id"],
                        "expect": s["expect"],
                    }
                    for s in statements(sheet)
                ],
            }
        )
    notes = latest(read_jsonl(out_dir / "notes.jsonl"))
    answered = {(v["sheet_id"], v["attempt"]) for v in read_jsonl(out_dir / "verifier.jsonl")}
    gate = read_jsonl(out_dir / "gate.jsonl")
    failed = {  # failed the local checks already (run the gate first): rewritten, not verified
        (g["sheet_id"], g["attempt"]) for g in gate if not g["passed"] and not g["pending"]
    }
    skip = answered | failed
    verify: list[dict] = []
    count = 0
    for sheet_id, note in sorted(notes.items()):
        if (sheet_id, note["attempt"]) in skip or (only and note["writer"] not in only):
            continue
        if note["writer"] != "A" and note.get("spans") is None and sheet_id in needed:
            continue  # a model note to be rewritten this round
        if limit is not None and note["writer"] == "A" and count >= limit:
            continue
        count += note["writer"] == "A"
        items = statements(sheets[sheet_id])
        verify.append(
            {
                "job_id": f"verify-{sheet_id}#{note['attempt']}",
                "sheet_id": sheet_id,
                "attempt": note["attempt"],
                "writer": note["writer"],
                "seed": 0,
                "messages": verifier_messages(note["note"], items),
                "statements": items,  # the stage's second looks need them, and the note
                "note": note["note"],
            }
        )
    answers = {(v["sheet_id"], v["attempt"]): v for v in read_jsonl(out_dir / "verifier.jsonl")}
    for row in gate:  # earlier notes whose leak finding waits for the second look
        note = notes.get(row["sheet_id"])
        if row.get("looks") and note and note["attempt"] == row["attempt"]:
            found = (answers.get((row["sheet_id"], note["attempt"])) or {}).get("answers")
            verify += second_looks(sheets[row["sheet_id"]], note, row["looks"], found or {})
    return writers, verify


def second_looks(
    sheet: dict, note: dict, fact_ids: list[str], quoted: Mapping[str, str | None]
) -> list[dict]:
    """The second look at each of these missing or absent facts the verifier found (verify.py
    `check_note`: the finding counts only when the second look agrees): for a missing fact, the
    judge on the passage the verifier cited (`quoted`: its answers by fact); for an exclusion,
    the verifier asked again about that fact alone."""
    items = {item["fact_id"]: item for item in statements(sheet)}
    jobs = []
    for fid in fact_ids:
        item = items.get(fid)
        if item is None:
            continue
        judged = item.get("check") == "judge"
        if judged and not quoted.get(fid):
            continue
        jobs.append(
            {
                "job_id": f"{item.get('check', 'look')}-{sheet['sheet_id']}#{note['attempt']}"
                f":{fid}",
                "sheet_id": sheet["sheet_id"],
                "attempt": note["attempt"],
                "writer": note["writer"],
                "seed": 0,
                "messages": judge_messages(quoted[fid] or "", item["statement"])
                if judged
                else verifier_messages(note["note"], [{**item, "id": 1}]),
            }
        )
    return jobs


def estimate_hours(writers: list[dict], verify: list[dict]) -> dict[str, float]:
    """GPU session hours: model loads, prompt reading and writing, from the assumed throughput."""

    def tokens(messages: list[dict]) -> float:
        return sum(len(m["content"]) for m in messages) / CHARS_PER_TOKEN

    found: dict[str, float] = {}
    for writer in ("B", "C", "D"):
        jobs = [j for j in writers if j["writer"] == writer]
        if jobs:
            prompt = sum(tokens(j["messages"]) for j in jobs)
            output = len(jobs) * 750
            found[f"writer_{writer.lower()}"] = (
                LOAD_SECONDS + prompt / PROMPT_TOKENS_PER_SECOND + output / OUTPUT_TOKENS_PER_SECOND
            ) / 3600
    model_notes = len(writers)
    # second looks in the session: about a third of the absent statements get a finding
    looks = (
        sum(s["expect"] == "absent" for j in writers for s in j["statements"]) // 3
        if config()["verification"].get("second_look", True)
        else 0
    )
    jobs = len(verify) + model_notes + looks
    if jobs:
        prompt = sum(tokens(j["messages"]) for j in verify) + (model_notes + looks) * 1800
        found["verifier"] = (
            LOAD_SECONDS + prompt / PROMPT_TOKENS_PER_SECOND + jobs * 350 / OUTPUT_TOKENS_PER_SECOND
        ) / 3600
    found["total"] = sum(found.values())
    return {k: round(v, 2) for k, v in found.items()}


def notebook(round_no: int | str) -> dict[str, Any]:
    cells = [
        (
            "markdown",
            f"# ClaimSense v3 notes, round {round_no}\n\nWriters B and C, then the verifier, with "
            "vLLM on a T4 x2. Synthetic data only; private dataset and notebook.",
        ),
        (
            "code",
            "import glob, json, os, subprocess, sys\n"
            "found = glob.glob('/kaggle/input/**/run.json', recursive=True)\n"
            "assert found, 'attach the private claimsense-v3 round dataset'\n"
            "DATA = os.path.dirname(found[0])\n"
            "OUT = '/kaggle/working/output'\n"
            "os.makedirs(OUT, exist_ok=True)\n"
            "print(DATA, sorted(os.listdir(DATA)))\n"
            "run = json.load(open(os.path.join(DATA, 'run.json')))\n"
            "subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', "
            "'vllm==' + run['vllm']['version'], *run['vllm'].get('pip_pins', [])], check=True)\n"
            "import importlib.metadata as md\n"
            "print({p: md.version(p) for p in ('vllm', 'torch', 'transformers')})\n",
        ),
        (
            "code",
            "base = dict(os.environ, VLLM_USE_V1='1' if run['vllm']['use_v1_engine'] else '0')\n"
            "failed = []\n"
            "for stage in ('writer_b', 'writer_c', 'writer_d', 'verifier'):\n"
            "    for backend in run['vllm']['attention_backends']:\n"
            "        env = dict(base)\n"
            "        if backend != 'auto':\n"
            "            env['VLLM_ATTENTION_BACKEND'] = backend\n"
            "        print('=== stage', stage, 'attention', backend, flush=True)\n"
            "        done = subprocess.run([sys.executable, os.path.join(DATA, 'kaggle_stage.py'), "
            "'--run', os.path.join(DATA, 'run.json'), '--stage', stage, '--data', DATA, '--out', "
            "OUT, '--backend', backend], env=env)\n"
            "        if done.returncode == 0:\n"
            "            break\n"
            "    else:\n"
            "        failed.append(stage)  # the next stages still run on what exists\n"
            "        print('=== stage', stage, 'failed with every backend', flush=True)\n",
        ),
        (
            "code",
            "for name in sorted(os.listdir(OUT)):\n"
            "    path = os.path.join(OUT, name)\n"
            "    print(name, os.path.getsize(path))\n"
            "    if name.startswith('timings'):\n"
            "        print(open(path).read())\n"
            "if failed:\n"
            "    raise SystemExit(f'failed stages: {failed}')\n",
        ),
    ]
    return {
        "cells": [
            {
                "cell_type": kind,
                "metadata": {},
                "source": source,
                **({"outputs": [], "execution_count": None} if kind == "code" else {}),
            }
            for kind, source in cells
        ],
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }


def prepare_round(
    round_no: int | str,
    limit: int | None = None,
    out_dir: Path = OUT_DIR,
    looks_only: bool = False,
    rejudge: bool = False,
    only: tuple[str, ...] = (),
    new_only: bool = False,
) -> dict:
    folder = out_dir / "kaggle" / f"round{round_no}"
    dataset, kernel = folder / "dataset", folder / "kernel"
    for path in (dataset, kernel):
        if path.exists():
            shutil.rmtree(path)
        path.mkdir(parents=True)
    writers, verify = round_jobs(limit, out_dir, looks_only, rejudge, only, new_only)
    write_jsonl(dataset / "writers.jsonl", writers)
    write_jsonl(dataset / "verify.jsonl", verify)
    (dataset / "run.json").write_text(json.dumps(run_config(), indent=2), encoding="utf-8")
    shutil.copy(HERE / "kaggle_stage.py", dataset / "kaggle_stage.py")
    slug = f"claimsense-v3-round{round_no}"
    (dataset / "dataset-metadata.json").write_text(
        json.dumps(
            {
                "title": f"ClaimSense v3 notes round {round_no} (private)",
                "id": f"{USER}/{slug}",
                "isPrivate": True,
                "licenses": [{"name": "other"}],
            },
            indent=2,
        )
    )
    (kernel / f"{KERNEL}.ipynb").write_text(json.dumps(notebook(round_no), indent=1))
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
                "machine_shape": "NvidiaTeslaT4",  # T4 x2: vLLM needs compute 7.0 (no P100)
                "enable_tpu": False,
                "enable_internet": True,
                "dataset_sources": [f"{USER}/{slug}"],
                "competition_sources": [],
                "kernel_sources": [],
                "model_sources": [],
            },
            indent=2,
        )
    )
    problems = upload_problems([dataset, kernel])
    if problems:
        raise SystemExit("upload check failed:\n" + "\n".join(problems[:40]))
    return {
        "folder": str(folder),
        "writer_jobs": {w: sum(j["writer"] == w for j in writers) for w in ("B", "C", "D")},
        "verifier_jobs": len(verify) + len(writers),
        "second_looks_in_session": sum(
            s["expect"] == "absent" for j in writers for s in j["statements"]
        )
        if config()["verification"].get("second_look", True)
        else 0,
        "gpu_hours_estimate": estimate_hours(writers, verify),
        "upload_check": "passed",
    }


def upload_problems(folders: list[Path]) -> list[str]:
    from app.db.curated import load_curated
    from scripts.verify.policy_sources import cpt_descriptors

    descriptors = [d.lower() for d in cpt_descriptors(load_curated(config()["policy_set"]).scope)]
    problems = []
    for folder in folders:
        for path in sorted(folder.rglob("*")):
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            lowered = text.lower()
            for name, pattern in PII.items():
                if pattern.search(text):
                    problems.append(f"{path.name}: a {name} pattern")
            for descriptor in descriptors:
                if descriptor in lowered:
                    problems.append(f"{path.name}: AMA descriptor text {descriptor[:40]!r}")
                    break
            if path.name.endswith("metadata.json"):
                meta: Mapping[str, Any] = json.loads(text)
                if not (meta.get("isPrivate") or meta.get("is_private")):
                    problems.append(f"{path.name}: not private")
    return problems
