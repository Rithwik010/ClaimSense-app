# ClaimSense progress log

A running record of what has been done, decided and learned, so every team member can pick up the
project at the current state. Times are IST (UTC+05:30). **Newest status first; the timeline below
is oldest first. Append to the timeline; never rewrite past entries.**

Entry format: `YYYY-MM-DD HH:MM | who | area | what happened (commit, file or result)`. Times come
from commits, log files and Kaggle's clock (converted from UTC); `~` marks an estimated time.

Team: Manideep3183, rohanpagadala, Rithwik010. Work sessions so far: Manideep3183 with Claude Code.

---

## 1. Current status (2026-09-24 IST)

| Area | State |
|---|---|
| **Fine-tuning (P4.3)** | **Done.** 500 steps / 2 epochs / 3 h 02 min on a Kaggle T4, best eval loss **0.001711** (checkpoint 500). GGUF in `data/generated/models/claimsense-decision-v1/` (not in git). |
| **Model in Ollama (P4.5)** | **Done.** `claimsense-decision:v1` (3.4 GB Q4_K_M), Modelfile copies the base model's `RENDERER`/`PARSER gemma4`. |
| **Evaluation (P4.4)** | **Done, target missed.** 300/300: valid output **94%** (was 73%), macro-F1 **0.672** (was 0.345), target is 0.90. See the timeline entry and `docs/results.md`. |
| Baseline (P4.2) | **Done** (300/300, Ollama 0.34.1): valid output 73%, line accuracy 0.42, macro-F1 **0.345**, criterion status 0.63. See `docs/results.md`. |
| **Why the target is missed** | Fully measured, not guessed: note register 0.144 of the 0.228 gap; the model contradicting its own statuses 0.027 (fixable deterministically, no retraining); the NOT_APPLICABLE / NOT_DOCUMENTED boundary; and the dropped second line (**a decoding problem, not a training one**). |
| **Retrieval (P3.3)** | **Ablation: worth 0.376 of macro-F1.** Without the retrieved criteria the model denies nothing at all (DENY F1 0.000) and invents policy ids. |
| **Label verification (V1a)** | **Done, report only.** Checks 1-4 found no problems in 2,600 records; check 5 cannot verify most NOT_APPLICABLE labels automatically. ESI labels conflict with LCD L33906; fixing them would not close the gap to 0.90 (estimated test macro-F1 0.6732 -> 0.6677). Decisions for the v2 bundle are recorded (section 4). |
| Readiness gate | **9/9 automated checks pass.** Team review items still open (section 4). |
| Git | **`main` is pushed** (2026-09-24, force-push after removing the co-author lines from history: GitHub `main` `d0fd690` -> `efb088f`). `v1-data-verification` holds the V1a work and decisions as its own branch on GitHub, **not merged into `main`**. |
| Laptop services | Docker (Postgres, Qdrant) and Ollama running. |
| Tests | 770 pass, 19 skipped, **1 failing**: `test_ncci_pairs_include_known_edits`, because `data/raw/ncci-ptp/ccipra-v323r0-f1/` holds only the `.xlsx` and the pair (11042, 97597) lives in that file's `.txt`. Unrelated to the model work. |

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
| **Build the v2 bundle (decided, not built):** D-ESI-1 to D-ESI-7 (ESI criteria, R14, limitation-5 exclusion, consistent two_policy notes, criterion types), D-GEN-1 and D-GEN-2 (notes must carry the evidence their labels claim; NOT_MET never chosen by retrieval rank), D-DX-1 (R15, `DN_DX_NOT_SUPPORTED`), D-RAG-1 (no top-k cap). Regenerate the dataset and retrain once, together; model v1 and its data stay frozen until then. Also: POL-PAIN-001 c5 must include the LCD's path for a repeat ESI after a poor first response (after 14 days, different approach, level or medication, rationale documented); R14 must not treat add-on level codes or bilateral use of the same code as another block. | team | `DECISIONS.md` |
| Read the 20-record review packet (`data/generated/readiness/sample-records.md`; contains CPT codes: share privately, never commit) | team | `DECISIONS.md` |
| Spot-check 3 coverage policies against their LCDs | team | `DECISIONS.md` |
| Fill in the blind-review sheet before seeing model output | team | `tests/golden/blind_review/review_sheet.csv` |
| Sign off: prompt `decision_v2`; retrieval (code filter, top 5); max length 3072; visit limits out of v1; NCCI bypass modifiers XE/XP/XS/XU (59 and 25 not added) | team | `DECISIONS.md` |
| Confirm the golden assumptions (`tests/golden/README.md`) and spot-check 10 rules + 10 calculator cases | team | `DECISIONS.md` |
| AMA CPT license question (SOURCES.md) | team | `DECISIONS.md` |
| Extract `ccipra-v323r0-f1.txt` into `data/raw/ncci-ptp/ccipra-v323r0-f1/` (only the `.xlsx` is there), which fixes the one failing test | Manideep3183 | timeline |
| v1 unchanged (frozen). From v2, decision criteria come from exact lookup with no cap (D-RAG-1); vector search is used for the explanation collections (P5.4). | team | `DECISIONS.md` |
| Keep Ollama on 0.34.1 until the fine-tuned model is evaluated (decline the 0.34.2 update) | Manideep3183 | timeline |
| **Decide how to close the P4.4 gap** (macro-F1 0.672 vs 0.90). Measured 2026-09-23: note register accounts for 0.144 of the 0.228 gap, so training on more registers is necessary but **not sufficient** - the remaining 0.084 is the PEND bias and multi-line handling, which are there on the training register too | team | `DECISIONS.md` |
| Decide which note registers to train on, given that template B is the only held-out register we have: mixing B into training spends it | team | `DECISIONS.md` |
| Fix the output faults, which are not caused by the register: line 2 dropped on multi-line claims (11 on test, 5 on validation, mostly `same_profile_multi`), runaway answers truncated at 12-15k characters (5 on test, 3 on validation) | next session | timeline |
| **Decide whether the line decision is derived from the criterion statuses** instead of taken from the model's `decision` field (worth 0.027 macro-F1 today, and makes the answer internally consistent by construction). Touches `app/workflow/decisions.py` and the validator, not `contracts.py`. The derivation must include the NCCI_BYPASS branch; re-measure the 0.672 -> 0.699 estimate with it. | team | `DECISIONS.md` |
| ~~Check that every NOT_APPLICABLE criterion has a positive cue in the notes, and sharpen that definition in the prompt, before the next training run~~ **Closed:** Answered by V1a check 5 and D-GEN-1; implemented in the v2 generator. | — | `DECISIONS.md` |
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

- 16:28 | Manideep3183 + Claude | repo | CLAUDE.md, INSTRUCTIONS.md (v1.0 spec), SETUP.md, first DECISIONS.md rows (`365dea4`).
- 17:14 | team | process | No pull requests: local `p<phase>.<task>` branches merged into `main`, push only on request (`36204cf`, `0a0078e`). Laptop recorded: Apple M5, 16 GB, no NVIDIA GPU.
- 17:45 | Claude | P1.1 | uv project, ruff, pytest, import-linter, pre-commit, GitHub Actions CI (`c70a481`, `211b55d`).
- 17:57 | Claude | P1.2 | docker compose (Postgres, Qdrant), settings, structlog, `/health` (`12d90de`, `af63323`).
- 21:49 | team | data | Public sources received into `data/raw/` and listed in SOURCES.md: ICD-10-CM FY2027, HCPCS Oct 2026, NCCI PTP v323r0, MUE, PFS RVU26A, MCD LCDs and articles, CARC/RARC, POS, NUCC 1500, SBC template (`31b1643`, `9351b86`, `3518b35`). CPT license question flagged.
- 22:10 | team | decision | Curated data and golden cases synthesized by Claude, spot-checked by the team (`c3cdfc1`).
- 22:31 | Claude | curated | Procedure scope (office visits + 17 LCD-based coverage policies, 60 codes), 5 fictional plans, benefits, exclusions, fee rule (D6), reason-code map (`7831add`).
- 22:36 | Claude | P1.3 | SQLAlchemy models, Alembic migration 0001 (`b7fbd79`).
- 22:39 | Claude | P1.4 | Draft contracts for review (`0569665`).
- 23:01 | Claude | P2.2 | Reference generator: 500 members, 100 providers, networks, 150 authorizations, other coverage, accumulators, visit usage (`e3deb28`).
- 23:10 | Claude | golden | 90 rules cases, 52 calculator cases with worked steps (`3bf17f5`).
- 23:12 | Claude | P3.2 | SBC generator (`d7af11d`).
- 23:38 | Claude | P3.4 | Scenario engine, 230-claim corpus, digital PDF and scanned-form renderer (`57c3527`).
- 23:40 | Claude | P3.5 | Decision dataset v1 (2000/300/300, simulated retrieval), leakage checks, data card (`ba3bcda`).
- 23:47 | Claude | golden | 30 end-to-end cases, 50 RAG queries, 30 blind-review claims; 11 data-generation choices recorded in DECISIONS.md (`beb4a7c`, `001b779`).

### 2026-09-22

- 16:59 | Manideep3183 | env | Ollama 0.34.1 with `gemma4:e2b` running (Ollama later offered 0.34.2; not installed).
- 17:15 | Claude | P1.5 | Walking skeleton: JSON claim → R05 → context → base `gemma4:e2b` → validation → copay calculator → decision record → audit → Streamlit (`107766b`). Live run: 2.8 s; the base model invented a criterion ID, so validation set PEND and FULL review.
- ~17:40 | team | plan | Agreed: train the model **once**; freeze everything the model sees first; fine-tune on Kaggle (laptop has no NVIDIA GPU).
- ~17:50 | Claude | finding | Real retrieval returns criteria of the covering policy that do not apply to the claim; with `met: true/false` they could only be "not documented" (wrong PEND). Proposed a four-value criterion status.
- 18:10 | Claude | P3.1 | Coverage policy format checker; all 17 policies pass (`6d46dcc`).
- 18:15 | team | decision | **Contracts approved and frozen** with `CriterionResult.status` (MET / NOT_MET / NOT_DOCUMENTED / NOT_APPLICABLE); prompt `decision_v2` (list every retrieved criterion); stricter output validation (`d2fbd92`, DECISIONS.md 2026-09-22).
- 18:21 | Claude | P3.3 | Retrieval shared by pipeline and generators (Qdrant, plan and date filters) (`2e1b044`).
- 18:29 | Claude | P4 tooling | Model evaluation, Kaggle fine-tuning package, readiness gate, docs (`6fb191c`).
- 18:42 | Manideep3183 | env | Embedding model `bge-small-en-v1.5` downloaded (own terminal; the sandbox blocked it).
- 18:45 | Claude | P3.3 | Measured on generated claims: top 3 over all policies missed a needed criterion in 27% of lines. Procedure-code filter + top 5: 100% of needed criteria, no other-policy noise, none for office visits. Golden recall@3 0.978 (target 0.85), recall@5 1.0 (`c90ff8b`). `RAG_TOP_K` default 3 → 5 (needs team sign-off).
- 18:47 | Claude | P3.3 | Qdrant `coverage_policies` built: 57 criteria, knowledge version `36cfc77305a5`.
- 18:48 | Claude | P3.5 | Dataset v2 regenerated with real retrieval: 2000/300/300, 0 check problems, 0 missed criteria, 100 unseen-policy test records, longest about 2,500 tokens; blind-review set and claim corpus regenerated (`50d9286`).
- ~18:52 | Claude | P4.2 | Baseline of base `gemma4:e2b` on the 300 test records started (about 8 s per record).
- ~18:55 | Claude | readiness | Gate: 8/9 pass (parity, retrieval target, no misses, lengths, blind review); check 9 waits for the baseline.
- ~19:00 | Manideep3183 | Kaggle | Private dataset `manideep3183/claimsense` uploaded; notebook imported.
- ~19:05 | Manideep3183 | Kaggle | Smoke test 1 failed: model split across 2 GPUs (`cuda:0` vs `cuda:1`); token counts read as 1.
- 19:16 | Claude | P4.3 | Fixes: one GPU, token counting via the text tokenizer, float32 explicit, warmup steps, smoke run prints a time estimate (`1c6c61d`, `654f2bb`).
- 19:27 | Manideep3183 | Kaggle | Smoke test 2 passed: validation loss 0.46 → 0.24 in 7 steps; estimate 4.7 h.
- 19:32 | Manideep3183 | env | Ollama app quit by mistake: baseline stopped at 226/300.
- 19:34 | Claude | P4.2 | Evaluation records the Ollama version, refuses to mix versions, retries dropped connections (`7f7a9bf`). Baseline resumed on 0.34.1; later paused at 237/300 when the laptop session ended (Docker also stopped).
- 20:18 | Manideep3183 | Kaggle | Smoke test 3: training fine (27.8 s/step); GGUF export failed: needs 21.2 GB, `/kaggle/working` had 19 GB.
- 20:21 | Claude | P4.3 | Export in `/tmp`, keep only the Q4_K_M file (`acb5a1e`, `7f2758a`).
- 20:42 | Manideep3183 | Kaggle | Smoke test 4: GGUF export succeeded, `gemma-4-e2b-it.Q4_K_M.gguf` 3.43 GB. Whole Kaggle path verified.
- 20:48 | Claude | P4.3 | Keep the `mmproj` GGUF as well, in case Ollama needs it (`0d764d5`); Manideep3183 uploaded the new `data.py`.
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

### 2026-09-24

- ~00:30 | Claude | P3.3 | **The retriever has two mechanisms, and only one of them is doing any work.** (1) An exact filter: keep a criterion only if its policy covers this procedure code, applies to this plan (or ALL) and was effective on or before the date of service - boolean, no ML. (2) Embedding similarity over whatever survives, keeping the top 5. Measured on the curated set: **no procedure code has more than 5 criteria** (12 policies have 3, four have 4, one has 5), so the top-5 limit **never truncates**, and the ranking cannot change *which* criteria reach the prompt - only the order they are listed in. A deterministic lookup keyed on procedure code would produce byte-identical prompts today. This does not mean the vector index is useless: it means the synthetic policy set is too small to exercise it, and ranking starts to matter as soon as one code maps to more than 5 criteria, which is what a real LCD corpus looks like. For the report, the honest phrasing is that retrieval supplies the criteria deterministically and the index is there for scale this corpus does not yet reach. Raised because a team member said retrieval was not important: the criteria are worth 0.376 of macro-F1, the embedding ranking is currently worth nothing, and both statements are true at once.

- ~01:10 | Claude | P4.4 | **PEND bias diagnosed; it is three separate things, and one is free to fix.** (a) **The model contradicts its own criterion statuses.** The prompt's decision rule is mechanical - any NOT_MET means DENY, otherwise any NOT_DOCUMENTED means PEND, otherwise APPROVE - so the decision is a function of the statuses. On 7.9% of valid test lines (27) and 2.1% of validation lines (7) the model answers PEND while its own statuses imply APPROVE (16) or DENY (11); it never contradicts itself in the other direction. **Recomputing each decision from the model's own statuses raises test macro-F1 0.672 -> 0.699 and line accuracy 0.700 -> 0.738, with no retraining** (validation 0.816 -> 0.819, so this is mostly a test-split effect). The validator does not currently catch this: it rejects APPROVE with a NOT_MET or NOT_DOCUMENTED criterion, but not PEND without one. (b) **Status errors that push a line to PEND**: MET -> NOT_DOCUMENTED (47 on test, 5 in-distribution - the register problem) and NOT_MET -> NOT_DOCUMENTED (19 on test), which turns a denial into a pend. (c) **The NOT_APPLICABLE / NOT_DOCUMENTED boundary is genuinely unclear**, and this is the residual in-distribution error: 30 of 61 status errors on validation (49%) are on that boundary, in **both** directions (NOT_DOCUMENTED -> NOT_APPLICABLE 20, which *misses* a pend; NOT_APPLICABLE -> NOT_DOCUMENTED 10, which invents one), spread thinly across many criteria (worst single criterion: 4). Errors in both directions, spread thin, is the signature of an under-determined label rather than something the model failed to learn. The generator's rule (`scenarios.py:996`) is that a criterion is NOT_APPLICABLE when it is not in the scenario profile's criteria list - a generator-internal variable - while the prompt tells the model "the criterion is about a situation this claim is not in", which it can only judge if the notes carry a positive cue that the criterion is off-topic. **Before the next training run, check whether every NOT_APPLICABLE case has such a cue in the notes, and sharpen the prompt's definition.** That is a prompt and data change, so it belongs in the same bundle as the register fix.

- 20:05 | Manideep3183 | verification | **Label verification V1a and its two follow-ups (branch `v1-data-verification`); report only, no label or generator changed.** Outputs in `data/generated/verification/` (git-ignored).
  - **Checks 1-4 clean** (`scripts/verify/label_checks.py`, `e06e598`) on 2,600 records and 3,335 decided lines: every checkable APPROVE (1,341) and PEND (677) line has a diagnosis the MCD article covers (the 357 office-visit lines have no billing article and were not checkable), and all 226 diagnosis-based denials are uncovered; every decision follows from its criterion statuses (66 NCCI-bypass PEND lines exempt by the prompt's rule); all 4,046 MET evidence strings are word for word in the notes; all 10,038 labelled criteria were retrieved. **Check 5 cannot verify most NOT_APPLICABLE labels:** a related sentence is only a triage signal, and 67 of 3,677 had none.
  - **ESI findings:** the generator marks c2 and c3 NOT_APPLICABLE on every repeat injection (plus 5 first injections labelled like repeats) and c4 NOT_APPLICABLE on every first injection, while LCD L33906 applies all indications to every ESI and adds c5 for repeats. Decisions D-ESI-1 to D-ESI-6 (`474cf9c`) and D-ESI-7 record the LCD reading.
  - **Impact (estimate):** on 176 headline ESI lines, 234 status labels change and **95 decisions go from APPROVE to PEND**, because the v1 notes lack what the decisions require (guidance with contrast; a baseline score and duration on repeats). Test macro-F1 on the headline set **0.6732 -> 0.6677** (0.6692 with R14 and limitation 5), so **fixing labels does not close the gap to 0.90**.
  - **391 diagnosis-mismatch lines** across 17 policies, all gold DENY: the 226 diagnosis-based denials of the deny_dx scenarios plus 165 in other scenarios (two_policy 51, same_profile_multi 45, office_plus_procedure 30, rule_denied_line 21, office_same_day 11, deny_criterion 5, deny_exclusion 2). They carry 393 NOT_MET labels because two deny_exclusion lines (DEC-TE-00027, DEC-TE-00085) have NOT_MET on both POL-SURG-003 c1 and c3. The NOT_MET sits on the first applicable criterion in retrieval order in 381 of 393 cases and **off the indication criterion in 47%** (183 of 393).
  - **R14 affects 32 ESI lines** (24 in two_policy, 20 would become DENY); **21 two_policy records have contradictory notes**.
  - **New decisions:** D-GEN-1, D-GEN-2, D-DX-1 (R15, `DN_DX_NOT_SUPPORTED`), D-RAG-1. All are v2-bundle changes.
  - **History rewrite and force-push:** the Claude co-author line was removed from all 73 commits; the rewrite changed no file (`git diff 9d0900e 579e94d` is empty). Old `main` tip `9d0900e` (kept locally as `backup/pre-rewrite`), new tip `efb088f`, which adds `e33992a` updating 34 commit IDs in this log and nothing else. Force-pushed with a lease on `d0fd690`; `setup-docs` was already gone from GitHub. Pull request #1's pinned ref still shows 3 old commits; only GitHub Support can remove it. Harmless: those commits differ only by the co-author line; no action planned.

<!-- Next entry goes here. Example:
- 2026-09-23 01:30 | Manideep3183 | P4.3 | Full run finished: best eval loss ..., runtime ...; files downloaded to data/generated/models/claimsense-decision-v1/.
-->
