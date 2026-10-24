"""The GGUF export and Ollama load, tested without GPU quota (the team's request of 24 Oct).

Writes data/generated/kaggle/kernel-v3-export-test/: a CPU-only Kaggle notebook (no GPU, so no GPU
quota) that attaches the timing run's output and the private v3 dataset, installs the pinned
training stack (training/finetune/prepare_kaggle_v3.py `PINNED`), and on the step-20 checkpoint:

A. Unsloth's own export, as train.py `--export-from` runs it, with Unsloth's test-only CPU switch
   (`UNSLOTH_ALLOW_CPU=1`): Unsloth needs a GPU, so this is expected to fail; the result is kept.
B. The same steps by hand: the adapter merged into the 16-bit base with PEFT (as Unsloth merges);
   llama.cpp's converter and quantizer from Unsloth's own installer (`install_llama_cpp`) at the
   pinned release `CONVERTER_TAG` (without the pin Unsloth takes the latest release at export
   time); conversion to a 16-bit GGUF and quantization to Q4_K_M; then Ollama (the laptop's
   version) loads it under the throwaway name `TEST_MODEL` with the evaluated Modelfile settings,
   answers one validation record (`num_predict` cut to `TEST_TOKENS` on CPU), and the model is
   deleted. claimsense-decision:v2 and :v3 are never created or touched.

Every step's result goes to /kaggle/working/export-test/report.json.

    uv run python -m scripts.kaggle.export_test
    uvx kaggle kernels push -p data/generated/kaggle/kernel-v3-export-test
"""

import json

from training.finetune.modelfile import evaluated
from training.finetune.prepare_kaggle_v3 import PINNED, USER
from training.generate.common import GENERATED_DIR

SLUG = "claimsense-v3-export-test"
FOLDER = GENERATED_DIR / "kaggle" / "kernel-v3-export-test"
CONVERTER_TAG = "b11798-mix-f8a7950"  # unslothai/llama.cpp's latest release on 24 Oct
TEST_MODEL = "claimsense-exporttest-20261024"
TEST_TOKENS = 256
BASE = "unsloth/gemma-4-E2B-it"

SETUP = f"""import glob, json, os, subprocess, sys, time
REPORT = {{}}
OUT = '/kaggle/working/export-test'
WORK = '/tmp/export-test'
os.makedirs(OUT, exist_ok=True); os.makedirs(WORK, exist_ok=True)
def save():
    json.dump(REPORT, open(f'{{OUT}}/report.json', 'w'), indent=2)
def step(name, ok, **found):
    REPORT[name] = {{'ok': ok, **found}}; save(); print(name, ok, found, flush=True)
CKPT = os.path.dirname(glob.glob('/kaggle/input/**/claimsense-finetune-v3-timing/**/checkpoint-20/'
                                 'adapter_config.json', recursive=True)[0])
DATA = os.path.dirname(glob.glob('/kaggle/input/**/train_mix.jsonl', recursive=True)[0])
TRAIN = glob.glob('/kaggle/input/**/finetune/train.py', recursive=True)[0]
print(CKPT, DATA, TRAIN)
PINNED = [{", ".join(repr(p) for p in PINNED)}]
subprocess.run([sys.executable, '-m', 'pip', 'install', '--quiet', *PINNED], check=True)
"""

ATTEMPT_A = """# A. Unsloth's own export (train.py --export-from), CPU switch on: expected to fail
started = time.time()
done = subprocess.run([sys.executable, TRAIN, '--export-from', CKPT, '--out', f'{WORK}/unsloth',
                       '--data', DATA, '--gguf-work-dir', f'{WORK}/unsloth-gguf'],
                      env=dict(os.environ, UNSLOTH_ALLOW_CPU='1'), capture_output=True, text=True)
tail = (done.stdout + done.stderr)[-1500:]
step('A_unsloth_export_on_cpu', done.returncode == 0, seconds=round(time.time() - started),
     last_output=tail)
"""

MERGE = f"""# B1. merge the adapter into the 16-bit base, as Unsloth does before converting
started = time.time()
import torch, transformers, peft
from transformers import AutoModelForImageTextToText, AutoProcessor
from peft import PeftModel
base = AutoModelForImageTextToText.from_pretrained('{BASE}', torch_dtype=torch.bfloat16)
merged = PeftModel.from_pretrained(base, CKPT).merge_and_unload()
merged.save_pretrained(f'{{WORK}}/merged', safe_serialization=True)
AutoProcessor.from_pretrained('{BASE}').save_pretrained(f'{{WORK}}/merged')
del base, merged
step('B1_merge', True, seconds=round(time.time() - started), transformers=transformers.__version__,
     peft=peft.__version__, adapter=json.load(open(f'{{CKPT}}/adapter_config.json'))
     .get('base_model_name_or_path'))
"""

TOOLS = f"""# B2. llama.cpp from Unsloth's installer at the pinned release
started = time.time()
os.environ['UNSLOTH_ZOO_DISABLE_GPU_INIT'] = '1'
os.environ['UNSLOTH_LLAMA_CPP_CONVERTER_TAG'] = '{CONVERTER_TAG}'
import unsloth_zoo
from unsloth_zoo.llama_cpp import install_llama_cpp
found = install_llama_cpp(gpu_support=False)
quantizer, converter = (found if isinstance(found, tuple) else (None, None))[:2]
info = glob.glob(os.path.expanduser('~/.unsloth/llama.cpp/UNSLOTH_PREBUILT_INFO.json'))
step('B2_llama_cpp', bool(quantizer and converter), seconds=round(time.time() - started),
     unsloth_zoo=unsloth_zoo.__version__, quantizer=str(quantizer), converter=str(converter),
     installed=json.load(open(info[0])) if info else None)
"""

CONVERT = """# B3. convert to a 16-bit GGUF, then quantize to Q4_K_M
started = time.time()
done = subprocess.run([sys.executable, str(converter), f'{WORK}/merged', '--outtype', 'bf16',
                       '--outfile', f'{WORK}/model-bf16.gguf'], capture_output=True, text=True)
step('B3_convert', done.returncode == 0, seconds=round(time.time() - started),
     last_output=(done.stdout + done.stderr)[-1500:])
started = time.time()
done = subprocess.run([str(quantizer), f'{WORK}/model-bf16.gguf', f'{WORK}/model-Q4_K_M.gguf',
                       'Q4_K_M'], capture_output=True, text=True)
gguf = f'{WORK}/model-Q4_K_M.gguf'
size = os.path.getsize(gguf) if os.path.exists(gguf) else 0
step('B4_quantize', done.returncode == 0 and size > 0, seconds=round(time.time() - started),
     gguf_gb=round(size / 1e9, 2), last_output=(done.stdout + done.stderr)[-800:])
"""


def ollama_cell() -> str:
    pinned = evaluated("claimsense-decision:v2")
    lines = ["FROM __GGUF__"] + [
        f"{key} {value}" for key, values in pinned["settings"].items() for value in values
    ]
    first = {**pinned["requests"]["first"], "num_predict": TEST_TOKENS}
    return f"""# B5. Ollama {pinned["ollama"]} loads it as a throwaway model, answers once; deleted
started = time.time()
subprocess.run('which zstd || (apt-get update -qq && apt-get install -y -qq zstd)', shell=True)
subprocess.run('curl -fsSL https://ollama.com/install.sh | OLLAMA_VERSION={pinned["ollama"]} sh',
               shell=True, check=True)
server = subprocess.Popen(['ollama', 'serve'], stdout=open(f'{{OUT}}/ollama.log', 'w'),
                          stderr=subprocess.STDOUT, env=dict(os.environ, OLLAMA_NO_CLOUD='1'))
time.sleep(10)
open(f'{{WORK}}/Modelfile', 'w').write({json.dumps(chr(10).join(lines))}.replace(
    '__GGUF__', f'{{WORK}}/model-Q4_K_M.gguf'))
made = subprocess.run(['ollama', 'create', '{TEST_MODEL}', '-f', f'{{WORK}}/Modelfile'],
                      capture_output=True, text=True)
record = json.loads(open(f'{{DATA}}/validation.jsonl').readline())
import urllib.request
answer, error = None, None
try:
    body = json.dumps({{'model': '{TEST_MODEL}', 'stream': False, 'think': False,
                       'messages': record['messages'][:2],
                       'options': {json.dumps(first)}}}).encode()
    reply = urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:11434/api/chat', body,
                                   {{'Content-Type': 'application/json'}}), timeout=3600)
    answer = json.loads(reply.read())
except Exception as exc:  # noqa: BLE001
    error = repr(exc)
removed = subprocess.run(['ollama', 'rm', '{TEST_MODEL}'], capture_output=True, text=True)
left = subprocess.run(['ollama', 'list'], capture_output=True, text=True).stdout
server.terminate()
text = (answer or {{}}).get('message', {{}}).get('content', '')
step('B5_ollama', made.returncode == 0 and bool(text), seconds=round(time.time() - started),
     created=made.returncode == 0, create_output=(made.stdout + made.stderr)[-400:], error=error,
     record=record['metadata']['record_id'], answer_start=text[:300],
     eval_count=(answer or {{}}).get('eval_count'), prompt_eval_count=(answer or {{}}).get(
     'prompt_eval_count'), deleted=removed.returncode == 0, models_left=left)
print(json.dumps(REPORT, indent=1))
"""


def main() -> None:
    cells = [
        (
            "markdown",
            "# ClaimSense v3: GGUF export and Ollama load test (CPU only)\n\nSynthetic data.",
        ),
        ("code", SETUP),
        ("code", ATTEMPT_A),
        ("code", MERGE),
        ("code", TOOLS),
        ("code", CONVERT),
        ("code", ollama_cell()),
    ]
    book = {
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
    FOLDER.mkdir(parents=True, exist_ok=True)
    (FOLDER / f"{SLUG}.ipynb").write_text(json.dumps(book, indent=1))
    (FOLDER / "kernel-metadata.json").write_text(
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
                "enable_internet": True,
                "dataset_sources": [f"{USER}/claimsense-decision-v3"],
                "competition_sources": [],
                "kernel_sources": [f"{USER}/claimsense-finetune-v3-timing"],
                "model_sources": [],
            },
            indent=2,
        )
    )
    print(FOLDER)


if __name__ == "__main__":
    main()
