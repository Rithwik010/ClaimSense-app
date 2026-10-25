"""Model v3's GGUF exports on a CPU-only Kaggle session, so no GPU quota (D-V3-26).

The route, the same in the test and for the real exports:

1. the adapter merged into the 16-bit base weights (`BASE`, bfloat16) with PEFT, never into the
   4-bit base the training loaded;
2. v2's chat template (read from v2's GGUF, data/generated/v3/v2_chat_template.jinja) written into
   the merged model, so the GGUF carries the same one;
3. llama.cpp's converter and quantizer from Unsloth's installer at the pinned release
   `CONVERTER_TAG` (Unsloth's own export would take the latest release, and needs a GPU): conversion
   to a 16-bit GGUF, then quantization to Q4_K_M, v2's type, under v3's own names in a v3-only
   folder (`FOLDER`, `GGUF_NAMES`; D-V3-27);
4. the packaging side by side with v2's (scripts/verify/gguf_packaging.py `summary`, the same
   fields): quantization type, size, chat-template hash, tokenizer details, tensor types;
5. Ollama (the laptop's version) loads it under a throwaway name with the evaluated Modelfile
   settings (v2's, only the model name and the weights differ), answers one validation record
   (`num_predict` cut to `TEST_TOKENS` on CPU), and the model is deleted. claimsense-decision:v2 and
   :v3 are never created or touched.

`--test`: the timing run's step-20 checkpoint, and first Unsloth's own export with its test-only
CPU switch, for the record (expected to fail: Unsloth needs a GPU). Without it: the finished
training session's `adapter` (the lowest validation loss) and `adapter-final` into
`claimsense-decision-v3/`, as claimsense-decision-v3-best.Q4_K_M.gguf and
claimsense-decision-v3-final.Q4_K_M.gguf, where the stage 5 evaluation finds them (registered there
as claimsense-decision:v3-best and :v3-final).

    uv run python -m scripts.kaggle.v3_export --test
    uv run python -m scripts.kaggle.v3_export --source claimsense-finetune-v3-full-2
    uvx kaggle kernels push -p data/generated/kaggle/kernel-v3-export[-test]

Every step's result goes to the folder's report.json.
"""

import argparse
import inspect
import json
from pathlib import Path

from scripts.verify import gguf_packaging
from training.finetune.modelfile import evaluated
from training.finetune.prepare_kaggle_v3 import PINNED, USER
from training.generate.common import GENERATED_DIR
from training.generate.v3.config import OUT_DIR as V3_DIR

CONVERTER_TAG = "b11798-mix-f8a7950"  # unslothai/llama.cpp's latest release on 24 Oct
BASE = "unsloth/gemma-4-E2B-it"  # the 16-bit weights
BASE_REVISION = "d36bdd3855c82a6a1a23f7c459b749f5724ae75d"  # main since 17 Jul 2026 (D-V3-31)
FOLDER = "claimsense-decision-v3"  # v3 only: its own folder and names, never v2's (D-V3-27)
GGUF_NAMES = {
    "best": "claimsense-decision-v3-best.Q4_K_M.gguf",
    "final": "claimsense-decision-v3-final.Q4_K_M.gguf",
    "test": "claimsense-exporttest-step20.Q4_K_M.gguf",
}
TEST_MODEL = "claimsense-exporttest-20261024"
TEST_TOKENS = 1536  # the real answer budget (v2's num_predict), so the answer can end by itself
V2_PACKAGING = V3_DIR / "v2_gguf_packaging.json"
V2_TEMPLATE = V3_DIR / "v2_chat_template.jinja"


def setup(sources: str) -> str:
    return f"""import glob, json, os, subprocess, sys, time, hashlib
REPORT = {{}}
OUT = '/kaggle/working/__FOLDER__'
WORK = '/tmp/v3-export'
os.makedirs(OUT, exist_ok=True); os.makedirs(WORK, exist_ok=True)
def save():
    json.dump(REPORT, open(f'{{OUT}}/report.json', 'w'), indent=2)
def step(name, ok, **found):
    REPORT[name] = {{'ok': ok, **found}}
    save()
    print(name, ok, json.dumps(found)[:2000], flush=True)
DATA = os.path.dirname(glob.glob('/kaggle/input/**/train_mix.jsonl', recursive=True)[0])
TRAIN = glob.glob('/kaggle/input/**/finetune/train.py', recursive=True)[0]
ADAPTERS = {sources}
print(ADAPTERS, DATA, TRAIN)
PINNED = {json.dumps(list(PINNED))}
subprocess.run([sys.executable, '-m', 'pip', 'install', '--quiet', *PINNED], check=True)
V2 = json.loads({json.dumps(json.dumps(json.loads(V2_PACKAGING.read_text())[0]))})
V2_TEMPLATE = {json.dumps(V2_TEMPLATE.read_text())}
"""


UNSLOTH_ON_CPU = """# A. Unsloth's own export (train.py --export-from), with its CPU switch
started = time.time()
try:
    done = subprocess.run([sys.executable, TRAIN, '--export-from', ADAPTERS['test'], '--out',
                           f'{WORK}/unsloth', '--data', DATA,
                           '--gguf-work-dir', f'{WORK}/unsloth-gguf'],
                          env=dict(os.environ, UNSLOTH_ALLOW_CPU='1'), capture_output=True,
                          text=True, timeout=1800)
    ok, tail = done.returncode == 0, (done.stdout + done.stderr)[-1500:]
except subprocess.TimeoutExpired as exc:
    ok, tail = False, f'stopped after 30 minutes: {str(exc.stdout or "")[-800:]}'
step('A_unsloth_export_on_cpu', ok, seconds=round(time.time() - started), last_output=tail)
# the record attempt is not part of the route: the report's other steps decide
"""

TOOLS = f"""# llama.cpp from Unsloth's installer at the pinned release
started = time.time()
os.environ['UNSLOTH_ZOO_DISABLE_GPU_INIT'] = '1'
os.environ['UNSLOTH_LLAMA_CPP_CONVERTER_TAG'] = '{CONVERTER_TAG}'
import unsloth_zoo
from unsloth_zoo.llama_cpp import install_llama_cpp
found = install_llama_cpp(gpu_support=False)
quantizer, converter = (found if isinstance(found, tuple) else (None, None))[:2]
info = glob.glob(os.path.expanduser('~/.unsloth/llama.cpp/UNSLOTH_PREBUILT_INFO.json'))
step('llama_cpp', bool(quantizer and converter), seconds=round(time.time() - started),
     unsloth_zoo=unsloth_zoo.__version__, quantizer=str(quantizer), converter=str(converter),
     pinned_tag='{CONVERTER_TAG}', installed=json.load(open(info[0])) if info else None)
gguf_py = glob.glob(os.path.expanduser('~/.unsloth/llama.cpp/**/gguf-py'), recursive=True)
sys.path[:0] = gguf_py[:1]
try:
    import gguf
except ImportError:  # the bundle without gguf-py: the package (a reader only here)
    subprocess.run([sys.executable, '-m', 'pip', 'install', '--quiet', 'gguf'], check=True)
"""

PACKAGING = "# the packaging summary (scripts/verify/gguf_packaging.py)\n" + (
    "import hashlib, os\nfrom collections import Counter\n"
    + inspect.getsource(gguf_packaging.summary)
)


def export_cell(name: str, target: str) -> str:
    return f"""# {name}: merge into the 16-bit base, v2's chat template, convert, quantize, compare
started = time.time()
import torch, transformers, peft
from transformers import AutoModelForImageTextToText, AutoProcessor
from peft import PeftModel
adapter = ADAPTERS['{name}']
merged_dir = f'{{WORK}}/{name}-merged'
# the merge runs in bfloat16 (Gemma 4 does not run in float16); f16 is only the GGUF made for
# quantization, below, checked for overflow
base = AutoModelForImageTextToText.from_pretrained('{BASE}', revision='{BASE_REVISION}',
                                                   torch_dtype=torch.bfloat16)
base_commit = getattr(base.config, '_commit_hash', None)
merged = PeftModel.from_pretrained(base, adapter).merge_and_unload()
dtypes = sorted({{str(p.dtype) for p in merged.parameters()}})
merged.save_pretrained(merged_dir, safe_serialization=True)
AutoProcessor.from_pretrained('{BASE}', revision='{BASE_REVISION}').save_pretrained(merged_dir)
del base, merged
config = json.load(open(f'{{merged_dir}}/tokenizer_config.json'))
config['chat_template'] = V2_TEMPLATE
config['eos_token'] = '<eos>'  # v2's end token (id 1); the base's tokenizer names <turn|> (106)
json.dump(config, open(f'{{merged_dir}}/tokenizer_config.json', 'w'), indent=2)
text = json.load(open(f'{{merged_dir}}/config.json')).get('text_config', {{}})
first_shared = text['num_hidden_layers'] - text.get('num_kv_shared_layers', 0)
# the later layers reuse the earlier layers' keys and values: their own are never used
UNUSED = {{f'blk.{{i}}.{{t}}.weight' for i in range(first_shared, text['num_hidden_layers'])
          for t in ('attn_k', 'attn_v', 'attn_k_norm')}}
open(f'{{merged_dir}}/chat_template.jinja', 'w').write(V2_TEMPLATE)
if os.path.exists(f'{{merged_dir}}/chat_template.json'):
    os.remove(f'{{merged_dir}}/chat_template.json')
step('{name}_merge', base_commit == '{BASE_REVISION}', seconds=round(time.time() - started),
     base='{BASE}', base_commit=base_commit, dtypes=dtypes,
     adapter_base=json.load(open(f'{{adapter}}/adapter_config.json')).get('base_model_name_or_path'),
     transformers=transformers.__version__, peft=peft.__version__)
started = time.time()
done = subprocess.run([sys.executable, str(converter), merged_dir, '--outtype', 'f16',
                       '--outfile', f'{{WORK}}/{name}-f16.gguf'], capture_output=True, text=True)
# f16 holds bfloat16's range only up to 65504: any tensor that overflowed would be inf or NaN
import numpy as np
from gguf import GGUFReader
overflowed, largest = [], 0.0
for tensor in GGUFReader(f'{{WORK}}/{name}-f16.gguf').tensors:
    if tensor.tensor_type.name == 'F16':
        values = np.asarray(tensor.data)
        if not np.isfinite(values).all():
            overflowed.append(tensor.name)
        largest = max(largest, float(np.nanmax(np.abs(values[np.isfinite(values)]), initial=0)))
step('{name}_convert', done.returncode == 0 and not overflowed,
     seconds=round(time.time() - started), f16_overflowed=overflowed[:10],
     largest_f16_magnitude=largest, last_output=(done.stdout + done.stderr)[-800:])
os.makedirs('{target}', exist_ok=True)
gguf = '{target}/{GGUF_NAMES[name]}'
started = time.time()
# v2's own type for every tensor both files hold: Q4_K_M's mix rule picks attn_v's type by layer
# position, and with the unused shared-layer tensors left out it picks other layers than v2's
overrides = [arg for n, t in sorted(V2['tensor_names'].items()) if t in ('Q4_K', 'Q6_K')
             for arg in ('--tensor-type', '^' + n.replace('.', '[.]') + '$=' + t.lower())]
done = subprocess.run([str(quantizer), *overrides, f'{{WORK}}/{name}-f16.gguf', gguf, 'Q4_K_M'],
                      capture_output=True, text=True)
step('{name}_quantize', done.returncode == 0 and os.path.exists(gguf),
     seconds=round(time.time() - started), last_output=(done.stdout + done.stderr)[-600:])
if os.path.exists(f'{{WORK}}/{name}-f16.gguf'):
    os.remove(f'{{WORK}}/{name}-f16.gguf')
found = summary(gguf, names=True)
digest = hashlib.sha256()
with open(gguf, 'rb') as f:
    for block in iter(lambda: f.read(1 << 24), b''):
        digest.update(block)
same = {{key: found[key] == V2[key] for key in
        ('architecture', 'file_type', 'quantization_version', 'chat_template_sha256',
         'tokenizer', 'tensors', 'tensor_types')}}
ours, theirs = found.pop('tensor_names'), V2['tensor_names']
general = sorted(set(V2['general']) | set(found['general']))
missing = sorted(set(theirs) - set(ours))
extra = sorted(set(ours) - set(theirs))
retyped = {{n: [theirs[n], ours[n]] for n in set(ours) & set(theirs) if ours[n] != theirs[n]}}
# packaged as v2 except the unused shared-layer tensors the newer llama.cpp leaves out (their
# absence also changes the tensor counts, so `tensors` and `tensor_types` are not compared whole)
as_v2 = all(same[k] for k in ('architecture', 'file_type', 'quantization_version',
                              'chat_template_sha256', 'tokenizer'))
only_unused = set(missing) == UNUSED and not extra and not retyped
step('{name}_packaging', as_v2 and only_unused, sha256=digest.hexdigest(), same_as_v2=same,
     missing_from_v2s_tensors=len(missing), missing_are_the_unused_shared_layer_tensors=only_unused,
     shared_layers=[first_shared, text['num_hidden_layers'] - 1], extra_tensors=extra,
     retyped_tensors=retyped,
     side_by_side={{'v2': {{k: v for k, v in V2.items() if k != 'tensor_names'}}, '{name}': found}},
     general_differences={{k: [V2['general'].get(k), found['general'].get(k)] for k in general
                          if V2['general'].get(k) != found['general'].get(k)}})
"""


def ollama_cell(name: str, target: str) -> str:
    pinned = evaluated("claimsense-decision:v2")
    lines = ["FROM __GGUF__"] + [
        f"{key} {value}" for key, values in pinned["settings"].items() for value in values
    ]
    first = {**pinned["requests"]["first"], "num_predict": TEST_TOKENS}
    return f"""# {name}: Ollama {pinned["ollama"]} loads it as a throwaway model, then deletes it
started = time.time()
if not os.path.exists('/usr/local/bin/ollama'):
    subprocess.run('which zstd || (apt-get update -qq && apt-get install -y -qq zstd)', shell=True)
    install = 'curl -fsSL https://ollama.com/install.sh | OLLAMA_VERSION={pinned["ollama"]} sh'
    subprocess.run(install, shell=True, check=True)
server = subprocess.Popen(['ollama', 'serve'], stdout=open(f'{{OUT}}/ollama-{name}.log', 'w'),
                          stderr=subprocess.STDOUT, env=dict(os.environ, OLLAMA_NO_CLOUD='1'))
time.sleep(10)
open(f'{{WORK}}/Modelfile', 'w').write({json.dumps(chr(10).join(lines))}.replace(
    '__GGUF__', '{target}/{GGUF_NAMES[name]}'))
throwaway = '{TEST_MODEL}-{name}'
made = subprocess.run(['ollama', 'create', throwaway, '-f', f'{{WORK}}/Modelfile'],
                      capture_output=True, text=True)
record = json.loads(open(f'{{DATA}}/validation.jsonl').readline())
import urllib.request
answer, error = None, None
try:
    body = json.dumps({{'model': throwaway, 'stream': False, 'think': False,
                       'messages': record['messages'][:2],
                       'options': {json.dumps(first)}}}).encode()
    reply = urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:11434/api/chat', body,
                                   {{'Content-Type': 'application/json'}}), timeout=3600)
    answer = json.loads(reply.read())
except Exception as exc:  # noqa: BLE001
    error = repr(exc)
removed = subprocess.run(['ollama', 'rm', throwaway], capture_output=True, text=True)
left = subprocess.run(['ollama', 'list'], capture_output=True, text=True).stdout
server.terminate(); server.wait()
text = (answer or {{}}).get('message', {{}}).get('content', '')
step('{name}_ollama', made.returncode == 0 and bool(text), seconds=round(time.time() - started),
     model=throwaway, created=made.returncode == 0,
     create_output=(made.stdout + made.stderr)[-400:],
     error=error, record=record['metadata']['record_id'], answer_start=text[:300],
     eval_count=(answer or {{}}).get('eval_count'),
     done_reason=(answer or {{}}).get('done_reason'),  # stop: it ended by itself (the end token)
     prompt_eval_count=(answer or {{}}).get('prompt_eval_count'),
     deleted=removed.returncode == 0, models_left=left)
"""


def notebook(test: bool, source: str) -> dict:
    if test:
        adapters = {
            "test": "os.path.dirname(glob.glob('/kaggle/input/**/claimsense-finetune-v3-timing/"
            "**/checkpoint-20/adapter_config.json', recursive=True)[0])"
        }
        exports = [("test", "/kaggle/working/claimsense-v3-export-test")]
    else:
        adapters = {
            name: f"os.path.dirname(glob.glob('/kaggle/input/**/{source}/**/claimsense-v3/"
            f"{folder}/adapter_config.json', recursive=True)[0])"
            for name, folder in (("best", "adapter"), ("final", "adapter-final"))
        }
        exports = [(name, f"/kaggle/working/{FOLDER}") for name in ("best", "final")]
    sources = "{" + ", ".join(f"{k!r}: {v}" for k, v in adapters.items()) + "}"
    out = "claimsense-v3-export-test" if test else FOLDER
    cells = [
        ("markdown", "# ClaimSense v3: GGUF export (CPU only)\n\nSynthetic data only."),
        ("code", setup(sources).replace("__FOLDER__", out)),
        *([("code", UNSLOTH_ON_CPU)] if test else []),
        ("code", TOOLS),
        ("code", PACKAGING),
    ]
    for name, target in exports:
        cells += [("code", export_cell(name, target)), ("code", ollama_cell(name, target))]
    cells.append(("code", "print(json.dumps(REPORT, indent=1))"))
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


def write(test: bool, source: str) -> Path:
    slug = "claimsense-v3-export-test" if test else "claimsense-v3-export"
    folder = GENERATED_DIR / "kaggle" / ("kernel-v3-export-test" if test else "kernel-v3-export")
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{slug}.ipynb").write_text(json.dumps(notebook(test, source), indent=1))
    (folder / "kernel-metadata.json").write_text(
        json.dumps(
            {
                "id": f"{USER}/{slug}",
                "title": slug,
                "code_file": f"{slug}.ipynb",
                "language": "python",
                "kernel_type": "notebook",
                "is_private": True,
                "enable_gpu": False,
                "enable_tpu": False,
                "enable_internet": True,
                "dataset_sources": [f"{USER}/claimsense-decision-v3"],
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
    parser.add_argument("--test", action="store_true", help="the timing run's step-20 checkpoint")
    parser.add_argument("--source", help="the training session that finished (its kernel slug)")
    args = parser.parse_args()
    if not args.test and not args.source:
        raise SystemExit("--source <kernel slug> is needed for the real exports")
    print(write(args.test, "claimsense-finetune-v3-timing" if args.test else args.source))


if __name__ == "__main__":
    main()
