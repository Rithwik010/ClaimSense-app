# Fine-tuning on Kaggle (P4.3 – P4.5)

Training runs on a Kaggle GPU; the laptop prepares the data and serves the result through Ollama.
Start only when `docs/training-readiness.md` is complete.

## 1. Prepare the upload (laptop)

```bash
uv run python -m training.finetune.prepare_kaggle --kaggle-user manideep3183 --slug claimsense
```

This writes `data/generated/kaggle/claimsense-decision/` (train, validation and test records,
`summary.json`, the training scripts and `dataset-metadata.json` marked private) and
`data/generated/kaggle/claimsense-finetune.ipynb`. It refuses a dataset built with simulated
retrieval.

## 2. Upload (Kaggle website)

1. Datasets → New dataset → upload the contents of the `claimsense-decision` folder (the team's
   dataset is `manideep3183/claimsense`). Set visibility to **Private**. The records contain CPT
   codes; never make the dataset public.
2. Code → New notebook → File → Import notebook → `claimsense-finetune.ipynb`.
3. Notebook settings: Accelerator **GPU T4** (or P100), Internet **on**, Add Input → the private
   dataset. Keep the notebook private. The notebook finds the dataset wherever Kaggle mounts it.

## 3. Train (Kaggle notebook)

Run all cells. The script:

- installs the latest Unsloth (§10 known issue), records installed versions (`pip-freeze.txt`)
- loads `unsloth/gemma-4-E2B-it` in 4-bit, applies the Gemma 4 chat template (system text moved
  into the first user turn if the template has no system role), thinking off
- counts exact tokens and stops if any record exceeds 3072 (`lengths.json`)
- trains QLoRA (r 16, alpha 16, dropout 0, attention + MLP, vision/audio frozen, lr 2e-4, batch 1 ×
  gradient accumulation 8, 2 epochs, fp16 on T4/P100) on responses only, with early stopping on
  validation loss
- saves `adapter/`, `gguf/` (Q4_K_M), `training-log.json`, `config.json`, `example.txt`

Run it first with `SMOKE = True` (50 records, 1 epoch, no GGUF; a few minutes) to check Unsloth,
Gemma 4 and the chat template on Kaggle; then set `SMOKE = False` for the real run (roughly 1–3
hours on a T4).

## 4. Serve (laptop)

Download `gguf/*.gguf` and the logs from the notebook output into
`data/generated/models/claimsense-decision-v1/`, then:

```bash
uv run python -m training.finetune.modelfile --gguf data/generated/models/claimsense-decision-v1/<file>.gguf --version 1
ollama create claimsense-decision:v1 -f data/generated/models/claimsense-decision-v1/Modelfile
```

The Modelfile copies the base model's chat handling (`RENDERER gemma4`, `PARSER gemma4`), so the
fine-tuned model formats chats like the baseline did.

## 5. Evaluate (P4.4, laptop)

```bash
uv run python -m training.evaluate.model --model claimsense-decision:v1 --label finetuned-v1
```

Compare with the baseline in `docs/results.md` (target macro-F1 >= 0.90). If it passes, set
`MODEL_NAME=claimsense-decision:v1` in `.env` and record the result in `DECISIONS.md`.

---

# Model v2: step by step (dataset v2, prompt decision_v3)

Same QLoRA settings as model v1 (`training/finetune/data.py`): the longest v2 record is 2,762
tokens (exact count, `data/generated/decision_v2/token_lengths.json`), under the max length 3,072.
Expect the full run to take about as long as v1's (3 h on a T4).

## 1. Laptop: build the upload

```bash
uv run python -m training.generate.decision_dataset --policy-set v2      # about 20 s; all checks must pass
uv run python -m scripts.verify.token_lengths data/generated/decision_v2  # needs Ollama running
uv run python -m training.finetune.prepare_kaggle --kaggle-user manideep3183 --model-version 2
```

This writes `data/generated/kaggle/claimsense-decision-v2/` (train, validation and test records,
`summary.json`, `data-card.md`, `token_lengths.json`, the training scripts and a private
`dataset-metadata.json`), the same folder as `claimsense-decision-v2.zip`, and the notebook
`claimsense-finetune-v2.ipynb`. Expected fingerprints (`shasum`, first 12): train `eb096e5a1d87`,
validation `25af4201b87d`, test `b4b4eacb1458`.

## 2. Kaggle website: dataset and notebook

1. kaggle.com → **Datasets** → **New Dataset** → drag in `claimsense-decision-v2.zip` (Kaggle
   unpacks it). Title: "ClaimSense decision dataset v2". Visibility: **Private** (the records
   contain CPT codes). Create.
2. **Code** → **New Notebook** → **File** → **Import Notebook** → choose
   `claimsense-finetune-v2.ipynb`.
3. Right panel, **Session options**: Accelerator **GPU T4 x2** or **GPU P100** (the script uses
   one GPU); Internet **on**; Persistence **Files only**. **Add Input** → **Your Work** →
   Datasets → the private v2 dataset.
4. Keep the notebook private.

## 3. Smoke test (about 10 minutes)

1. The third cell has `SMOKE = True`. Click **Run All**.
2. Check the output: the token report says 0 records over 3072; training runs a few steps; the
   export cell writes a GGUF from the smoke adapter (this proves the export works).
3. If it fails, send me the last 40 lines of the failing cell.

## 4. Full run (about 3 hours)

1. Set `SMOKE = False` in the third cell. **Save Version** → **Save & Run All (Commit)** so it
   keeps running when you close the tab.
2. When the version finishes, open it → **Output** → `claimsense-v2/`. Download:
   - `gguf/gemma-4-e2b-it.Q4_K_M.gguf` (about 3.4 GB) into
     `data/generated/models/claimsense-decision-v2/gguf/`
   - `training-log.json`, `lengths.json`, `config.json`, `pip-freeze.txt` into
     `data/generated/models/claimsense-decision-v2/`
   If the GGUF is missing, run the export cell again in an interactive session on the saved
   `adapter/` (it only exports when there is no GGUF yet).

## 5. Laptop: serve it as `claimsense-decision:v2`

The Modelfile is already written (`data/generated/models/claimsense-decision-v2/Modelfile`, the
base model's chat handling, as for v1); it expects the GGUF name above. If the file name differs:
`uv run python -m training.finetune.modelfile --gguf <path> --version 2`.

```bash
ollama create claimsense-decision:v2 -f data/generated/models/claimsense-decision-v2/Modelfile
ollama run claimsense-decision:v2 "hello"    # loads; any answer is fine
```

For the pipeline (`.env`): `MODEL_NAME=claimsense-decision:v2`, `PROMPT_VERSION=decision_v3`,
`POLICY_SET=v2`.

## 6. Laptop: evaluate both models (about 40 minutes)

```bash
uv run python -m training.evaluate.compare_v2
tail -f data/generated/eval/v2/v2data-model-v2.log     # progress, in another terminal
```

Model v1 runs on the v2 test inputs with its own prompt (decision_v2), model v2 with decision_v3;
answers are used as the pipeline uses them (one retry when invalid, decisions derived from the
statuses). Model v1's predictions are already in `data/generated/eval/v2/` (a run resumes), so
only model v2 runs. The table is written to `docs/results-v2.md`.
