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
