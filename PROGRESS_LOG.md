# ClaimSense progress log

A running record of what has been done, decided and learned, so every team member can pick up the
project at the current state. Times are IST (UTC+05:30). **Newest status first; the timeline below
is oldest first. Append to the timeline; never rewrite past entries.**

Entry format: `YYYY-MM-DD HH:MM | who | area | what happened (commit, file or result)`. Times come
from commits, log files and Kaggle's clock (converted from UTC); `~` marks an estimated time.

Team: Manideep3183, rohanpagadala, Rithwik010. Work sessions so far: Manideep3183 with Claude Code.

---

## 1. Current status (2026-09-23 11:25 IST)

| Area | State |
|---|---|
| **Fine-tuning (P4.3)** | **Done.** 500 steps / 2 epochs / 3 h 02 min on a Kaggle T4, best eval loss **0.001711** (checkpoint 500). GGUF in `data/generated/models/claimsense-decision-v1/` (not in git). |
| **Model in Ollama (P4.5)** | **Done.** `claimsense-decision:v1` (3.4 GB Q4_K_M), Modelfile copies the base model's `RENDERER`/`PARSER gemma4`. |
| **Evaluation (P4.4)** | **Done, target missed.** 300/300: valid output **94%** (was 73%), macro-F1 **0.672** (was 0.345), target is 0.90. See the timeline entry and `docs/results.md`. |
| Baseline (P4.2) | **Done** (300/300, Ollama 0.34.1): valid output 73%, line accuracy 0.42, macro-F1 **0.345**, criterion status 0.63. See `docs/results.md`. |
| Readiness gate | **9/9 automated checks pass.** Team review items still open (section 4). |
| Git | Local `main` is **52 commits ahead of `origin/main`: not pushed yet.** Teammates see none of this until a team member says "push". |
| Laptop services | Docker (Postgres, Qdrant) and Ollama running. |
| Tests | Last full run with all services up: 782 passed (CI-skipped tests need `data/raw/`, Postgres, the embedding model or a live model). |

### Roadmap status (INSTRUCTIONS.md §11)

| Phase | Done | Partly done | Not started |
|---|---|---|---|
| 1 Foundations | P1.1, P1.2, P1.3, P1.4 (contracts approved 2026-09-22), P1.5 | | |
| 2 Rules and calculator | P2.2 | P2.1 (seed: curated, ICD-10, fees, reference; missing NCCI, MUE, POS), P2.3 (R05 only), P2.4 (in-network copay only), P2.5 (status table only) | |
| 3 Knowledge and datasets | P3.1, P3.2, P3.3 (coverage_policies collection), P3.4, P3.5 (v2, real retrieval) | | |
| 4 Model | P4.1, P4.2, P4.3, P4.5 | **P4.4 (measured; below the 0.90 target)** | |
| 5 Integration | | P5.1 (digital PDF only), P5.2 (context with retrieval), P5.3 (tiers only), P5.5 (skeleton page), P5.6 (golden set written) | P5.4 |
| 6 Evaluation and demo | | | P6.1, P6.2, P6.3 |

---

## 2. Frozen for model v1: do not change without a team decision and retraining

The model being trained learned exactly these. A change breaks train/live parity (the readiness
gate's check 5) and means regenerating the dataset and retraining.

| Frozen item | Where |
|---|---|
| Contracts, especially `SLMOutput`, `CriterionResult.status`, `ContextPackage` | `app/domain/contracts.py` |
| System prompt and user-message layout | `app/ml/prompts/decision_v2.txt`, `app/ml/prompt.py` |
| Retrieval: chunk text, embedding model `BAAI/bge-small-en-v1.5`, query text, procedure-code filter, top 5, min score 0 | `app/rag/`, `app/core/settings.py` |
| Coverage policies and procedure scope (knowledge version `36cfc77305a5`) | `data/curated/coverage_policies/`, `data/curated/procedure_scope.csv` |
| Label logic and scenario engine | `training/generate/` |
| Rule flags shown to the model (`NCCI_BYPASS`, line denials) | the generator's rule mirror; the P2.3 engine must produce the same |

Dataset v2 fingerprints (`shasum`, first 12 characters): train `295cc6b1d3af`, validation
`6478d11211a2`, test `afaa098ffc72`. The Kaggle copy is the source of truth for training.

---

## 3. What teammates can work on in parallel now

These do not touch the frozen items above.

| Task | Notes |
|---|---|
| P2.3 rules R01–R13, duplicates, H5 | 90 golden cases in `tests/golden/rules/`. Line flags must match the generator's mirror (`training/generate/codebook.py`, `line_rule_outcomes`) |
| P2.4 full calculator | 52 golden cases in `tests/golden/calculator/`; extend `app/calculator/engine.py` |
| P2.1 remaining loaders | NCCI, MUE, place of service into Postgres; `app/db/seed.py` |
| P2.5 workflow | `app/workflow/states.py` has the status table |
| P5.1 scanned-form intake (OCR) | `app/intake/layout.py`, `app/intake/digital_pdf.py` exist |
| P5.4 explanations | Jinja2 from the decision record; also the `plan_documents`, `code_reference`, `carc_rarc` collections |
| Team review (section 4) | Needed before the model is accepted |

Working rules (CLAUDE.md, DECISIONS.md): branch `p<phase>.<task>-<name>`, tests first for rules,
calculator and validators, merge into `main` locally, **push only when a team member says so, no
pull requests**. Never commit `data/raw/`, `data/generated/`, `confidential/`, model files or `.env`.
Pull before starting; tell the team which task you take (add a timeline entry).

---

## 4. Open items

| Item | Owner | Where to record |
|---|---|---|
| Push `main` to GitHub so teammates can pull | team decision | — |
| Read the 20-record review packet (`data/generated/readiness/sample-records.md`; contains CPT codes: share privately, never commit) | team | `DECISIONS.md` |
| Spot-check 3 coverage policies against their LCDs | team | `DECISIONS.md` |
| Fill in the blind-review sheet before seeing model output | team | `tests/golden/blind_review/review_sheet.csv` |
| Sign off: prompt `decision_v2`; retrieval (code filter, top 5); max length 3072; visit limits out of v1; NCCI bypass modifiers XE/XP/XS/XU (59 and 25 not added) | team | `DECISIONS.md` |
| Confirm the golden assumptions (`tests/golden/README.md`) and spot-check 10 rules + 10 calculator cases | team | `DECISIONS.md` |
| AMA CPT license question (SOURCES.md) | team | `DECISIONS.md` |
| Keep Ollama on 0.34.1 until the fine-tuned model is evaluated (decline the 0.34.2 update) | Manideep3183 | timeline |
| **Decide how to close the P4.4 gap** (macro-F1 0.672 vs 0.90). Measured 2026-09-23: note register accounts for 0.144 of the 0.228 gap, so training on more registers is necessary but **not sufficient** - the remaining 0.084 is the PEND bias and multi-line handling, which are there on the training register too | team | `DECISIONS.md` |
| Decide which note registers to train on, given that template B is the only held-out register we have: mixing B into training spends it | team | `DECISIONS.md` |
| Fix the output faults, which are not caused by the register: line 2 dropped on multi-line claims (11 on test, 5 on validation, mostly `same_profile_multi`), runaway answers truncated at 12-15k characters (5 on test, 3 on validation) | next session | timeline |
| **Decide the retry policy for invalid answers**: first attempt at temperature 0, and only when the answer is invalid, one seeded retry at temperature 0.7. Measured to recover 5-8 of the 16 dropped-line records per attempt; reproducibility is kept because every attempt is seeded | team | `DECISIONS.md` |
| Record the exact Hugging Face revision of the base model in the training log (not done) | next session | `training/finetune/train.py` |
| Rebuild the golden end-to-end model answers for prompt v2 and real retrieval (P5.6) | later | `tests/golden/e2e/` |

---

## 5. Set up a machine at the current state

```bash
git pull                                   # after the push
uv sync
cp .env.example .env
docker compose up -d --wait                # Postgres, Qdrant
uv run alembic upgrade head
# data/raw/: public source files from the team's shared folder (SOURCES.md); never commit them
uv run python -m training.generate.reference          # members, providers, ... (deterministic)
uv run python -m app.db.seed                          # curated data, codes, fees, reference data
uv run hf download qdrant/bge-small-en-v1.5-onnx-q --cache-dir data/generated/models/fastembed
uv run python -m app.rag.knowledge                    # Qdrant collection, knowledge 36cfc77305a5
uv run python -m training.generate.decision_dataset   # compare shasum with section 2
uv run pytest
```

Run the API and page: `uv run uvicorn app.api.main:app` and `uv run streamlit run frontend/app.py`
(Ollama with `gemma4:e2b` pulled). Guides: `docs/walking-skeleton.md`, `docs/training-readiness.md`,
`docs/fine-tuning.md`, `docs/data-card.md`, `docs/contracts-review.md`.

If a regenerated dataset's fingerprints differ from section 2 (different CPU, for example), use the
Kaggle copy for anything model-related.

---

## 6. Known issues and lessons

- **Quitting the Ollama app stops evaluations.** Evaluation resumes where it stopped and refuses to
  mix Ollama versions; keep Ollama on 0.34.1 until the baseline and the fine-tuned evaluation are done.
- **Docker Desktop can stop** (laptop sleep, restarts): database tests then *skip* locally (CI
  requires them). Run `open -a Docker && docker compose up -d --wait`.
- **Large Hugging Face downloads stall inside Claude Code's sandbox;** run them in your own terminal.
- **zsh:** do not type `<` and `>` around placeholders (`--kaggle-user manideep3183`, not
  `<manideep3183>`).
- **Kaggle:** "T4 x2" must be used as one GPU (the script sets `CUDA_VISIBLE_DEVICES=0`); Gemma 4
  trains in float32 on T4 (no bf16, fp16 unsupported); `/kaggle/working` holds only 20 GB, so the
  GGUF export runs in `/tmp` and keeps only the Q4_K_M file and the `mmproj` file; the dataset mounts
  at `/kaggle/input/datasets/<user>/<slug>/...` and the notebook finds files by search, so keep only
  one `train.py` in the dataset.
- **Base model behaviour:** base `gemma4:e2b` often cites criteria that were not retrieved or skips
  some; output validation turns these into PEND and FULL review. This is what fine-tuning targets.

---

## 7. Timeline (oldest first)

### 2026-09-21

- 16:28 | Manideep3183 + Claude | repo | CLAUDE.md, INSTRUCTIONS.md (v1.0 spec), SETUP.md, first DECISIONS.md rows (`7ede1ff`).
- 17:14 | team | process | No pull requests: local `p<phase>.<task>` branches merged into `main`, push only on request (`795aabe`, `7691fa2`). Laptop recorded: Apple M5, 16 GB, no NVIDIA GPU.
- 17:45 | Claude | P1.1 | uv project, ruff, pytest, import-linter, pre-commit, GitHub Actions CI (`e409cb3`, `97ede6c`).
- 17:57 | Claude | P1.2 | docker compose (Postgres, Qdrant), settings, structlog, `/health` (`8897f66`, `d0fd690`).
- 21:49 | team | data | Public sources received into `data/raw/` and listed in SOURCES.md: ICD-10-CM FY2027, HCPCS Oct 2026, NCCI PTP v323r0, MUE, PFS RVU26A, MCD LCDs and articles, CARC/RARC, POS, NUCC 1500, SBC template (`9e90ba0`, `36d03d4`, `f6a707d`). CPT license question flagged.
- 22:10 | team | decision | Curated data and golden cases synthesized by Claude, spot-checked by the team (`3b26d58`).
- 22:31 | Claude | curated | Procedure scope (office visits + 17 LCD-based coverage policies, 60 codes), 5 fictional plans, benefits, exclusions, fee rule (D6), reason-code map (`76f83d7`).
- 22:36 | Claude | P1.3 | SQLAlchemy models, Alembic migration 0001 (`a6a5be6`).
- 22:39 | Claude | P1.4 | Draft contracts for review (`fc46147`).
- 23:01 | Claude | P2.2 | Reference generator: 500 members, 100 providers, networks, 150 authorizations, other coverage, accumulators, visit usage (`b123da5`).
- 23:10 | Claude | golden | 90 rules cases, 52 calculator cases with worked steps (`99848c3`).
- 23:12 | Claude | P3.2 | SBC generator (`729dac8`).
- 23:38 | Claude | P3.4 | Scenario engine, 230-claim corpus, digital PDF and scanned-form renderer (`f12a636`).
- 23:40 | Claude | P3.5 | Decision dataset v1 (2000/300/300, simulated retrieval), leakage checks, data card (`7d2cb50`).
- 23:47 | Claude | golden | 30 end-to-end cases, 50 RAG queries, 30 blind-review claims; 11 data-generation choices recorded in DECISIONS.md (`b3c7696`, `a9daf90`).

### 2026-09-22

- 16:59 | Manideep3183 | env | Ollama 0.34.1 with `gemma4:e2b` running (Ollama later offered 0.34.2; not installed).
- 17:15 | Claude | P1.5 | Walking skeleton: JSON claim → R05 → context → base `gemma4:e2b` → validation → copay calculator → decision record → audit → Streamlit (`f874940`). Live run: 2.8 s; the base model invented a criterion ID, so validation set PEND and FULL review.
- ~17:40 | team | plan | Agreed: train the model **once**; freeze everything the model sees first; fine-tune on Kaggle (laptop has no NVIDIA GPU).
- ~17:50 | Claude | finding | Real retrieval returns criteria of the covering policy that do not apply to the claim; with `met: true/false` they could only be "not documented" (wrong PEND). Proposed a four-value criterion status.
- 18:10 | Claude | P3.1 | Coverage policy format checker; all 17 policies pass (`ba7ed2f`).
- 18:15 | team | decision | **Contracts approved and frozen** with `CriterionResult.status` (MET / NOT_MET / NOT_DOCUMENTED / NOT_APPLICABLE); prompt `decision_v2` (list every retrieved criterion); stricter output validation (`bb3a59e`, DECISIONS.md 2026-09-22).
- 18:21 | Claude | P3.3 | Retrieval shared by pipeline and generators (Qdrant, plan and date filters) (`4c159fd`).
- 18:29 | Claude | P4 tooling | Model evaluation, Kaggle fine-tuning package, readiness gate, docs (`21ebef6`).
- 18:42 | Manideep3183 | env | Embedding model `bge-small-en-v1.5` downloaded (own terminal; the sandbox blocked it).
- 18:45 | Claude | P3.3 | Measured on generated claims: top 3 over all policies missed a needed criterion in 27% of lines. Procedure-code filter + top 5: 100% of needed criteria, no other-policy noise, none for office visits. Golden recall@3 0.978 (target 0.85), recall@5 1.0 (`78bdfde`). `RAG_TOP_K` default 3 → 5 (needs team sign-off).
- 18:47 | Claude | P3.3 | Qdrant `coverage_policies` built: 57 criteria, knowledge version `36cfc77305a5`.
- 18:48 | Claude | P3.5 | Dataset v2 regenerated with real retrieval: 2000/300/300, 0 check problems, 0 missed criteria, 100 unseen-policy test records, longest about 2,500 tokens; blind-review set and claim corpus regenerated (`91fd07a`).
- ~18:52 | Claude | P4.2 | Baseline of base `gemma4:e2b` on the 300 test records started (about 8 s per record).
- ~18:55 | Claude | readiness | Gate: 8/9 pass (parity, retrieval target, no misses, lengths, blind review); check 9 waits for the baseline.
- ~19:00 | Manideep3183 | Kaggle | Private dataset `manideep3183/claimsense` uploaded; notebook imported.
- ~19:05 | Manideep3183 | Kaggle | Smoke test 1 failed: model split across 2 GPUs (`cuda:0` vs `cuda:1`); token counts read as 1.
- 19:16 | Claude | P4.3 | Fixes: one GPU, token counting via the text tokenizer, float32 explicit, warmup steps, smoke run prints a time estimate (`4cb559a`, `d5c0fb8`).
- 19:27 | Manideep3183 | Kaggle | Smoke test 2 passed: validation loss 0.46 → 0.24 in 7 steps; estimate 4.7 h.
- 19:32 | Manideep3183 | env | Ollama app quit by mistake: baseline stopped at 226/300.
- 19:34 | Claude | P4.2 | Evaluation records the Ollama version, refuses to mix versions, retries dropped connections (`a56d5e5`). Baseline resumed on 0.34.1; later paused at 237/300 when the laptop session ended (Docker also stopped).
- 20:18 | Manideep3183 | Kaggle | Smoke test 3: training fine (27.8 s/step); GGUF export failed: needs 21.2 GB, `/kaggle/working` had 19 GB.
- 20:21 | Claude | P4.3 | Export in `/tmp`, keep only the Q4_K_M file (`c7e1417`, `0bbe513`).
- 20:42 | Manideep3183 | Kaggle | Smoke test 4: GGUF export succeeded, `gemma-4-e2b-it.Q4_K_M.gguf` 3.43 GB. Whole Kaggle path verified.
- 20:48 | Claude | P4.3 | Keep the `mmproj` GGUF as well, in case Ollama needs it (`588ba9a`); Manideep3183 uploaded the new `data.py`.
- ~21:00 | Manideep3183 | **P4.3** | **Full fine-tuning run started on Kaggle** (Save & Run All, Commit; about 4.5 h). Expected outputs in `claimsense/`: `gguf/*.Q4_K_M.gguf`, `gguf/*mmproj*.gguf`, `training-log.json`, `adapter/`.
- 22:31 | Claude | docs | This progress log written.

- 22:46 | Claude | P4.2 | **Baseline finished** (300/300, base `gemma4:e2b`, Ollama 0.34.1): valid output **73%**, line accuracy **0.422**, macro-F1 **0.345**, criterion status 0.633, evidence quoted 0.703, benefit category 1.00, complexity 0.279, claim decision 0.433, latency p50 9.6 s. Unseen policies score like seen ones (0.423 vs 0.422). Commonest failures: deciding a line that was denied by rules, and citing criteria that were not retrieved. Written to `docs/results.md`; this is the "before" number for P4.4 (target macro-F1 >= 0.90).
- 22:48 | Claude | readiness | **Gate 9/9 automated checks pass** (dataset current, real retrieval, record checks, recall@3 0.978, train/live parity, no retrieval misses, lengths, blind review, baseline). Team review items remain open.

### 2026-09-23

- ~00:28 | Manideep3183 | **P4.3** | **Full fine-tuning run finished on Kaggle** (Save & Run All): 500 steps, 2 epochs, **3 h 02 min** on a Tesla T4 in float32, 21.9 s/step. Train loss 0.754 -> 0.001 (run average 0.029); eval loss **0.01617 -> 0.004891 -> 0.002308 -> 0.001711** at steps 125/250/375/500, so the best checkpoint is the last one and early stopping never triggered. Token lengths: train p50 1367 / max 2408, validation max 2370, **0 records over the 3072 limit**; the Gemma 4 template does take a system role (markers `<|turn>user` / `<|turn>model`). GGUF export wrote `gemma-4-e2b-it.Q4_K_M.gguf` (3.43 GB) and `gemma-4-e2b-it.F16-mmproj.gguf` (0.99 GB).
- 10:24-10:38 | Manideep3183 | P4.3 | Downloaded both GGUF files, `training-log.json`, `lengths.json`, `config.json` and `pip-freeze.txt` into `data/generated/models/claimsense-decision-v1/` (git-ignored). Verified: GGUF headers correct, sizes match Kaggle byte for byte.
- 10:40 | Claude | **P4.5** | Built the Modelfile (copies the base model's `TEMPLATE`, `RENDERER gemma4`, `PARSER gemma4`) and ran `ollama create claimsense-decision:v1`. Loads in ~1.1 s and answers. Ollama still **0.34.1**, the engine the baseline used.
- 10:41-11:15 | Claude | P4.4 | Evaluation on the 300-record test split. The background shell was killed at record 288 when the session ended; the run is resumable, so rerunning the same command finished records 289-300 without repeating work. Lesson: the resume design paid for itself twice now.
- ~11:20 | Claude | **P4.4** | **Fine-tuned model evaluated, 300/300, Ollama 0.34.1.** Every headline metric beats the baseline: valid output **0.73 -> 0.94**, line accuracy **0.422 -> 0.700**, macro-F1 **0.345 -> 0.672**, criterion status 0.633 -> 0.804, evidence quoted word for word 0.703 -> **0.981**, complexity 0.279 -> 0.720, claim decision 0.433 -> 0.680, benefit category stays 1.00, latency p50 9.6 s -> **5.5 s**. Unseen policies score like seen ones (0.691 vs 0.703), so policy generalisation holds. **The P4.4 target of macro-F1 >= 0.90 is not met (0.672).** DENY precision is **1.00** (it never wrongly denies) but recall is 0.575; PEND precision is 0.345, i.e. the model over-PENDs: 51 of 202 gold APPROVE lines and 44 of 120 gold DENY lines come back PEND. Root cause in the criterion statuses: **MET -> NOT_DOCUMENTED 47 times** (27 of them on the APPROVE-turned-PEND records), so it fails to recognise a criterion as documented when the test split's note templates (set B) word it differently from training (set A) - a wording-generalisation gap, not a policy one, which matches an eval loss of 0.0017 on same-template validation data. Two output faults remain: 11 records drop line 2 of a multi-line claim, and 5 records run away to 12-15k characters and get truncated (together the 6% invalid). Regressions worth noting: `approve_single` 0.939 -> 0.692, `rule_denied_line` 0.667 -> 0.400, `same_profile_multi` valid rate 0.913 -> 0.609. Big wins: `office_visit` 0.00 -> 1.00, `office_same_day` 0.154 -> 0.846, `office_plus_procedure` 0.125 -> 0.781, `deny_dx` 0.161 -> 0.903, `pend_missing` 0.167 -> 0.867. Written to `docs/results.md`.

- ~12:10 | Claude | P4.4 | **Diagnostic: the same model on the validation split** (`--split` added to the evaluator; validation is template A and seen policies, so it is the same-wording, same-policy ceiling). **macro-F1 0.816 on A against 0.672 on B**; line accuracy 0.846 vs 0.700, criterion status 0.922 vs 0.804, evidence quoted 1.00 vs 0.981, complexity 0.851 vs 0.720, claim decision 0.860 vs 0.680. Valid output is 0.94 on both. **The note register explains 0.144 of the 0.228 gap to the 0.90 target (63%), and 0.084 remains even in-distribution.** Confirmed by the error mix: MET -> NOT_DOCUMENTED (47 on B, the top error there) disappears on A. Three faults are *not* caused by the register and survive on A: PEND is over-predicted (precision 0.604 even on A; 21 gold APPROVE and 22 gold DENY lines become PEND), line 2 is dropped on 5 records (4 of them `same_profile_multi`, the same scenario as on B), and 3 answers still run away and get truncated. Conclusion for the retrain decision: **more note registers alone would land near 0.82, not 0.90** - the PEND bias and the multi-line handling need fixing too. Also worth recording as a lesson: the training run's validation loss was 0.0017 (near zero) while task macro-F1 on the same records is 0.816, so teacher-forced token loss says very little about free-generation accuracy.

- ~13:05 | Claude | P4.4 | **Retrieval ablation** (`--ablate-criteria`: the retrieved criteria are removed from the context and the prompt is re-rendered, so COVERAGE_CRITERIA reads "No criteria retrieved." exactly as it does live when retrieval finds nothing; claim, rules result and plan benefits unchanged). Same model, same 300 test records: **macro-F1 0.672 -> 0.296**, line accuracy 0.700 -> 0.523, claim decision 0.680 -> 0.467, latency p50 5471 -> 1455 ms. **Without retrieval the model denies nothing at all**: DENY precision, recall and F1 are all 0.000, with all 120 gold DENY lines coming back APPROVE (82) or PEND (38), and it approves 95% of everything. Invented policy ids reappear as validation errors (`POL-MINOR-010.c1`, `POL-EXCL-010.c1`, `POL-A-101.c1` were never retrieved) - the base model's failure mode, which retrieval plus the validator exists to stop. Retrieval is worth 0.376 of macro-F1, more than fine-tuning's 0.327 gain over the base model; the two are complementary (retrieval supplies the facts, fine-tuning the discipline to use them).
- ~13:20 | Claude | P4.4 | **The dropped second line is a decoding problem, not a data or training one.** All 16 affected records (11 test, 5 validation) are claims where both lines need an **identical answer block** - same criteria set, same statuses, same decision, same benefit category, differing only in `line_no`. The correlation is total: 0 drops when the benefit categories differ (0/54), when the gold decisions differ (0/58), or when line 2 has no criteria (0/32). Not data scarcity either: training contains 301 records with identical criteria on every line. Probes on the 16 records, in order: `repeat_penalty` 1.1 (Ollama's default) vs 1.0 - **0/16 both**, so not the repeat penalty; three different seeds - 0/16 each, but that probe was vacuous because seeds do nothing at temperature 0; **temperature 0.7 - 5/16 and 8/16 complete**. So the model can produce the second line and greedy decoding deterministically discards it at one token position. Retraining would not have fixed this. Proposal for the team (not implemented): keep the first attempt at temperature 0, and on an invalid answer only, retry with temperature 0.7 and a fixed seed - reproducibility is preserved because every attempt is seeded, and the decision record would say which attempt answered.
- ~13:25 | Claude | P4.4 | **Runaway cap**: `num_predict = 1536` in `app/ml/client.py`. The longest valid answer across the baseline, the fine-tuned run and the validation diagnostic is 3,080 characters (about 880 tokens), so the cap is roughly twice the longest real answer and cannot truncate a usable one; it ends the 12-15k-character loops early instead of letting them run 45-83 s.

<!-- Next entry goes here. Example:
- 2026-09-23 01:30 | Manideep3183 | P4.3 | Full run finished: best eval loss ..., runtime ...; files downloaded to data/generated/models/claimsense-decision-v1/.
-->
