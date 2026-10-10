# Training readiness

The model is trained once. Everything that shapes what it sees or learns is frozen and checked
first. Run the gate on the laptop; it must print `automated checks: 9 passed, 0 failed`, and every
team item must be recorded before the Kaggle run.

```bash
docker compose up -d --wait                          # Postgres and Qdrant
uv run python -m app.db.seed                         # reference data in Postgres
uv run python -m app.rag.knowledge                   # coverage_policies_v1 and _v2 collections in Qdrant
uv run python -m training.generate.decision_dataset  # regenerate with real retrieval
uv run python -m training.generate.blind_review      # same retrieval for the blind-review set
uv run python -m training.evaluate.model --label baseline-gemma4-e2b   # P4.2 baseline
uv run python -m training.readiness                  # the gate
```

## What is frozen (a change after training means regenerating and retraining)

| Item | Where |
|---|---|
| Model output and the context shown to the model | `app/domain/contracts.py` (approved 2026-09-22) |
| System prompt and user message layout | `app/ml/prompts/decision_v2.txt`, `app/ml/prompt.py` |
| Label set: line decisions, the 3 model reason codes, benefit categories, complexity rule | prompt, `data/curated/` |
| Retrieval: criteria text, chunk format, embedding model, query text, top-k, minimum score | `data/curated/coverage_policies/v1/`, `app/rag/`, `.env` |
| Rule flags shown to the model (`NCCI_BYPASS`, rule denials) | golden rules assumptions |

## Automated checks (`training/readiness.py`)

| # | Check | Why |
|---|---|---|
| 1 | Dataset version, prompt version and system prompt text match the code | A prompt edit after generation would silently change what the model sees |
| 2 | The dataset was built with the live retriever; knowledge version and settings unchanged | Training must use the same retrieval as live use |
| 3 | Every record passes the leakage and quality checks; splits separated | Label and leakage errors are learned |
| 4 | Retrieval recall@3 >= 0.85 on the golden queries; nothing returned for "no policy" queries | P3.3 target |
| 5 | Train/live parity: the pipeline rebuilds sampled training prompts exactly | Catches any difference between generator and pipeline |
| 6 | Retrieval missed a planned criterion in at most 10% of records per split | Labels follow what was retrieved; misses must stay rare |
| 7 | Estimated token lengths fit the max length (3072) | The training script also counts exact tokens and stops if one is too long |
| 8 | The blind-review set uses the same retrieval | Reviewers see what the model sees |
| 9 | A baseline evaluation exists for this dataset | The "before" number for P4.4 |

## Team items (record in `DECISIONS.md` unless stated)

- [x] Contracts approved and frozen (2026-09-22)
- [ ] Prompt `decision_v2` read and accepted
- [ ] 3 policies spot-checked against their LCDs, including which criteria are conditional
- [ ] 20 sample records read: `data/generated/readiness/sample-records.md` (written by the gate)
- [ ] Blind-review sheet filled in (`tests/golden/blind_review/review_sheet.csv`) before seeing any
      model output; the gate then reports agreement with the labels, and disagreements are
      discussed (a label error found here is fixed before training)
- [ ] Visit limits stay out of v1; NCCI bypass modifiers stay XE, XP, XS, XU
- [ ] Max sequence length 3072 accepted
- [ ] Kaggle: phone-verified account, GPU and internet enabled, Gemma license accepted
- [ ] Dataset uploaded as a **private** Kaggle dataset (`docs/fine-tuning.md`)
