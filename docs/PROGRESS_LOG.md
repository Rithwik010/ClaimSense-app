# ClaimSense progress log

A running record of what has been done, decided and learned, so every team member can pick up the
project at the current state. Times are IST (UTC+05:30). **Newest status first; the timeline below
is oldest first. Append to the timeline; never rewrite past entries.**

Entry format: `YYYY-MM-DD HH:MM | who | area | what happened (commit, file or result)`. Times come
from commits, log files and Kaggle's clock (converted from UTC); `~` marks an estimated time.

Team: Manideep3183, rohanpagadala, Rithwik010. Work sessions so far: Manideep3183 with Claude Code.

---

## 1. Current status (2026-09-22 22:31 IST)

| Area | State |
|---|---|
| **Fine-tuning** | **Running on Kaggle** (full run, started after 20:48; about 4.5 h). Notebook: Manideep3183's Kaggle account, private. Dataset: `manideep3183/claimsense` (private). |
| Baseline (P4.2) | Paused at **237/300** test records (`data/generated/eval/baseline-gemma4-e2b.*`, on Manideep's laptop). Resumes where it stopped; must finish on **Ollama 0.34.1**. |
| Readiness gate | 8/9 automated checks pass; check 9 waits for the baseline. Team review items open (section 4). |
| Git | Local `main` is **46 commits ahead of `origin/main`: not pushed yet.** Teammates see none of this until a team member says "push". |
| Laptop services | Docker (Postgres, Qdrant) and Ollama stopped at the time of writing. |
| Tests | Last full run with all services up: 782 passed (CI-skipped tests need `data/raw/`, Postgres, the embedding model or a live model). |

### Roadmap status (INSTRUCTIONS.md §11)

| Phase | Done | Partly done | Not started |
|---|---|---|---|
| 1 Foundations | P1.1, P1.2, P1.3, P1.4 (contracts approved 2026-09-22), P1.5 | | |
| 2 Rules and calculator | P2.2 | P2.1 (seed: curated, ICD-10, fees, reference; missing NCCI, MUE, POS), P2.3 (R05 only), P2.4 (in-network copay only), P2.5 (status table only) | |
| 3 Knowledge and datasets | P3.1, P3.2, P3.3 (coverage_policies collection), P3.4, P3.5 (v2, real retrieval) | | |
| 4 Model | P4.1 | P4.2 (237/300), **P4.3 running** | P4.4, P4.5 |
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
| Finish the baseline on Ollama 0.34.1 (decline the pending 0.34.2 update until then) | Manideep3183 | timeline |
| After training: P4.5 import, P4.4 evaluation, retrieval ablation (eval mode not built yet) | next session | timeline |
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

<!-- Next entry goes here. Example:
- 2026-09-23 01:30 | Manideep3183 | P4.3 | Full run finished: best eval loss ..., runtime ...; files downloaded to data/generated/models/claimsense-decision-v1/.
-->
