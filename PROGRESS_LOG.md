# ClaimSense progress log

A running record of what has been done, decided and learned, so every team member can pick up the
project at the current state. Times are IST (UTC+05:30). **Newest status first; the timeline below
is oldest first. Append to the timeline; never rewrite past entries.**

Entry format: `YYYY-MM-DD HH:MM | who | area | what happened (commit, file or result)`. Times come
from commits, log files and Kaggle's clock (converted from UTC); `~` marks an estimated time.

Team: Manideep3183, rohanpagadala, Rithwik010. Work sessions so far: Manideep3183 with Claude Code.

---

## 1. Current status (2026-10-09 IST)

| Area | State |
|---|---|
| **Fine-tuning (P4.3)** | **Done.** 500 steps / 2 epochs / 3 h 02 min on a Kaggle T4, best eval loss **0.001711** (checkpoint 500). GGUF in `data/generated/models/claimsense-decision-v1/` (not in git). |
| **Model in Ollama (P4.5)** | **Done.** `claimsense-decision:v1` (3.4 GB Q4_K_M), Modelfile copies the base model's `RENDERER`/`PARSER gemma4`. |
| **Evaluation (P4.4)** | **Done, target missed.** 300/300: valid output **94%** (was 73%), macro-F1 **0.672** (was 0.345), target is 0.90. See the timeline entry and `docs/results.md`. |
| Baseline (P4.2) | **Done** (300/300, Ollama 0.34.1): valid output 73%, line accuracy 0.42, macro-F1 **0.345**, criterion status 0.63. See `docs/results.md`. |
| **Why the target is missed** | Fully measured, not guessed: note register 0.144 of the 0.228 gap; the model contradicting its own statuses 0.027 (fixable deterministically, no retraining); the NOT_APPLICABLE / NOT_DOCUMENTED boundary; and the dropped second line (**a decoding problem, not a training one**). |
| **Retrieval (P3.3)** | **Ablation: worth 0.376 of macro-F1.** Without the retrieved criteria the model denies nothing at all (DENY F1 0.000) and invents policy ids. |
| **Label verification (V1a)** | **Done, report only.** Checks 1-4 found no problems in 2,600 records; check 5 cannot verify most NOT_APPLICABLE labels automatically. ESI labels conflict with LCD L33906; fixing them would not close the gap to 0.90 (estimated test macro-F1 0.6732 -> 0.6677). Decisions for the v2 bundle are recorded (section 4). |
| **Policy source check (V1b)** | **Done, report only; reviewed in V1d.** All 57 criteria cite a word-for-word LCD excerpt (`data/curated/policy_sources.csv`); 72 findings against the LCDs (WRONG CRITERION 4, MISSING CRITERION 52, RULE CANDIDATE 16). The 4 wrong criteria change at most 6 v1 labels (all POL-REHAB-001 PENDs). D-RULE-1 and D-SCOPE-1 set the v2 scope. |
| **Data verification (V1)** | **Complete (2026-10-02).** V1a labels, V1b policy sources and completeness, V1c model disagreements, V1d review verdicts (filled sheets and summary in `data/verification/reviews/`). D-V2-1, D-V2-2, D-GEN-3, D-GEN-4, D-REV-1 and D-LIM-1 feed the v2 bundle; v1 data and model unchanged. |
| **Golden tests (G1-G2)** | **Spot-checked (2026-10-03).** Automatic checks: 0 violations on 52 calculator and 90 rules cases. The spot-check (10 rules, 9 calculator cases) agrees with every expected value (Claude recomputation in a separate chat, accepted by the reviewer). 5 rules cases conflict with R15 (D-GOLD-1); new cases to add (D-GOLD-2). G3 (2026-10-04): C53-C56 added after a separate Claude chat's answers agreed on all 48 amounts; 56 calculator cases. G4 (2026-10-09): 31 rules v2 cases, 218/218 cells agree; 121 rules cases. G5 (2026-10-09): 13 R11 cases, 104/104 cells agree; 134 rules cases. |
| **Rules engine (P2.3a, P2.3b)** | **Rules v1 and v2 built (2026-10-09).** R01–R20, duplicates, H5, `RULES_VERSION` 2.1.0 (R11 bypasses with the NCCI Policy Manual's PTP-associated modifiers, D-RULE-8); all 134 golden rules cases pass; dataset parity is the stored v1 outcomes plus 461 listed v2 changes, with 0 other differences. The pipeline runs it since P2.5, on a database-backed reference. Merged into `main` (`00a0201`; P2.3c `28af00f`). |
| **Rule tables (P2.1)** | Place of service, procedure codes (20,591), ICD-10-CM FY2027, MUE and NCCI loaded in full with provenance (`reference_sources`). |
| **Calculator (P2.4)** | Full §8.6 calculator built (2026-10-04); all 56 golden cases and 5,000 random claims pass; the pipeline uses it (`CALCULATOR_VERSION` 1.0.0). |
| **Human review (P5.3)** | **Done (2026-10-09).** Review queue, open, accept or override, finalization; all 18 golden review cases match their golden finals end to end. Merged into `main` (`7575d36`); CI run 37828554505 passed. |
| **Raw data** | 66 files listed with size and SHA-256 in `data/raw_manifest.csv` (with the download URL where recorded: the ICD-10-CM FY2027 tabular, the 2026 NCCI Policy Manual and the NCCI add-on code edits 2026 Q4, added 2026-10-09); a test fails on a missing or changed file (D-DATA-1). NCCI part f1 was restored from the original download (2026-10-03) and is read from its `.txt` again; the `.xlsx` fallback stays (SOURCES.md). Regenerating the decision dataset reproduces the v1 fingerprints exactly (checked in G2). |
| Readiness gate | **9/9 automated checks pass.** Team review items still open (section 4). |
| Git | **`main` is pushed** (2026-09-24, force-push after removing the co-author lines from history: GitHub `main` `d0fd690` -> `efb088f`). `v1-data-verification` (V1a-V1d) merged into `main` by V1d (`--no-ff`, normal push); teammate commit `04d0759` (summary.md) kept. `g1-golden-spotcheck` (G1-G2) merged into `main` by G2 (`--no-ff`, normal push). `p2.3a-rules-engine` (P2.3a) merged into `main` (`--no-ff`, normal push). `p5.3-review-finalization` (P5.3) merged into `main` (`--no-ff`, normal push; merge `7575d36`). `p2.3b-rules-v2` (P2.3b) merged into `main` (`--no-ff`, normal push; merge `00a0201`). `p2.3c-ncci-modifiers` (P2.3c) merged into `main` (`--no-ff`, normal push; merge `28af00f`). |
| Laptop services | Docker (Postgres, Qdrant) and Ollama running. |
| Tests | 2,111 pass, 1 skipped (the opt-in live-model test), **0 failing**, with Docker running. Without Docker, the database and Qdrant tests are skipped. CI (run 37936773272 on `28af00f`): 1,758 passed, 55 skipped. The 55 need `data/raw/`, the model v1 dataset, the cached embedding model or the opt-in live model; 299 tests are not collected without `data/raw/` (the raw-backed variants of the 134 golden rules cases in the file and database tests, and of the 31 end-to-end row checks), while their fixture variants run. |

### Roadmap status (INSTRUCTIONS.md §11)

| Phase | Done | Partly done | Not started |
|---|---|---|---|
| 1 Foundations | P1.1, P1.2, P1.3, P1.4 (contracts approved 2026-09-22), P1.5 | | |
| 2 Rules and calculator | P2.1, P2.2, P2.3 (P2.3a v1 rules, P2.3b rules v2), P2.4, P2.5 | | |
| 3 Knowledge and datasets | P3.1, P3.2, P3.3 (coverage_policies collection), P3.4, P3.5 (v2, real retrieval) | | |
| 4 Model | P4.1, P4.2, P4.3, P4.5 | **P4.4 (measured; below the 0.90 target)** | |
| 5 Integration | P5.3 | P5.1 (digital PDF only), P5.2 (context with retrieval), P5.5 (skeleton page), P5.6 (golden set written) | P5.4 |
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
| P2.3b rules R14, R15 and the D-RULE-1 single-claim rules | v2 rules (D-ESI-3, D-DX-1, D-RULE-1); new golden cases first (D-GOLD-2). P2.3a (R01–R13, duplicates, H5) is done |
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
| **Build the v2 bundle (decided, not built):** D-ESI-1 to D-ESI-7 (ESI criteria, R14, limitation-5 exclusion, consistent two_policy notes, criterion types), D-GEN-1 and D-GEN-2 (notes must carry the evidence their labels claim; NOT_MET never chosen by retrieval rank), D-DX-1 (R15, `DN_DX_NOT_SUPPORTED`; R14 and R15 are built in rules v2, P2.3b, the dataset changes are not), D-RAG-1 (no top-k cap), D-V2-1 and D-V2-2 (policy text fixes and findings from the V1b review), D-GEN-3 (exclusion criteria are never MET), D-GEN-4 (notes consistent across the lines of a claim), D-GEN-5 (every reference a generated claim makes exists in the reference data; parity extended to Groups A and B). Regenerate the dataset and retrain once, together; model v1 and its data stay frozen until then. Also: POL-PAIN-001 c5 must include the LCD's path for a repeat ESI after a poor first response (after 14 days, different approach, level or medication, rationale documented); R14 must not treat add-on level codes or bilateral use of the same code as another block. | team | `DECISIONS.md` |
| Read the 20-record review packet (`data/generated/readiness/sample-records.md`; contains CPT codes: share privately, never commit) | team | `DECISIONS.md` |
| Spot-check 3 coverage policies against their LCDs | team | `DECISIONS.md` |
| Fill in the blind-review sheet before seeing model output | team | `tests/golden/blind_review/review_sheet.csv` |
| Sign off: prompt `decision_v2`; retrieval (code filter, top 5); max length 3072; visit limits out of v1; NCCI bypass modifiers XE/XP/XS/XU (59 and 25 not added; the engine uses the manual's full list since P2.3c, D-RULE-8, the generator keeps XE/XP/XS/XU until generator v2) | team | `DECISIONS.md` |
| ~~Confirm the golden assumptions (`tests/golden/README.md`) and spot-check 10 rules + 10 calculator cases~~ **Closed: G1-G2** (`data/verification/reviews/`; D-GOLD-3 to D-GOLD-5). | — | `DECISIONS.md` |
| AMA CPT license question (SOURCES.md) | team | `DECISIONS.md` |
| ~~Extract `ccipra-v323r0-f1.txt` into `data/raw/ncci-ptp/ccipra-v323r0-f1/` (only the `.xlsx` is there), which fixes the one failing test~~ **Closed: G2.** The `.txt` could not be restored (CMS download blocked); part f1 is read from its official `.xlsx`, shown equal to the `.txt` on f2-f4 (SOURCES.md); the test passes. | — | timeline |
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
| **Golden updates:** ~~the five L97419 rules cases get a diagnosis A58565 covers, and R15 gets its own cases (D-GOLD-1)~~ **done in P2.3b** (L97412; R14-R20 cases checked on G4); ~~new calculator cases for a deductible split across two lines, a second copay capped by the allowed amount and a second primary-paid-at-least-allowed COB case (P2.4)~~ **done in G3** (C53-C56); ~~new cases for R14, R15 and the single-claim D-RULE-1 rules (P2.3b)~~ **done in P2.3b** (31 cases, G4); the deferred D-RULE-1 rules (earlier claims) still need cases when built, each accepted only after an independent check (D-GOLD-2) | team | `DECISIONS.md` |
| ~~**Review V1b, sitting 1** (about 28 min): 14 Part 1 rows in `data/generated/verification/B_policy_sources_review.md`; write MATCHES / DIFFERENT MEANING / NOT IN SOURCE / UNSURE~~ **Closed: reviewed in V1d** (`data/verification/reviews/`, D-V2-1). | — | timeline |
| ~~**Review V1b, sitting 2** (about 34 min): the 4 WRONG CRITERION findings, the 5 top-impact findings and 3 controls; write ADD IN V2 / NOT NEEDED / UNSURE. The other 63 findings are known gaps (D-SCOPE-1)~~ **Closed: reviewed in V1d** (`data/verification/reviews/`, D-V2-2). | — | `DECISIONS.md` |
| ~~Switch the pipeline from the R05-only path (rules version 0.1.0) to the full v1 engine after P2.1 loads NCCI, MUE, place of service and the full code table.~~ **Closed: P2.1/P2.5.** | — | timeline |
| R02: check HCPCS termination dates against the date of service (1,322 terminated codes currently count as valid); candidate v2 refinement. | team | `DECISIONS.md` |
| R10 matches on member, provider, code and date, not on the claim's prior-authorization number (2 dataset claims pass with an unknown number); v2 question. | team | `DECISIONS.md` |
| ~~Dates of service before 2026-10-01 raise `MissingReference` (only FY2027 ICD-10 is loaded); P2.1 must load FY2026 or handle this explicitly before the pipeline switches to the full engine.~~ **Closed: P2.5** (a 503, the claim stays RECEIVED; loading FY2026 is the item below). | — | timeline |
| Propose an optional `calculator_version` on the `Versions` contract plus a `decision_records` migration column (recorded in the CALCULATED audit event until then); a dedicated field for a calculation-failure reason could join it (today an `output_errors` entry prefixed `CALCULATION_FAILED:`) | team | `DECISIONS.md` |
| Load ICD-10-CM FY2026 (add the CMS file to data/raw/ and the manifest, D-DATA-1, then the seed) so claims with a date of service before 2026-10-01 can run; until then they get a 503 and stay RECEIVED | team | timeline |
| **Add-on level codes out of scope** (64480, 64484, 64491, 64492, 64494, 64495): the synthetic data never bills them and they may have no fee rows. The generator v2 task decides whether to bring them into scope (fee rows, policy code lists, generated claims) or keep them rule-only and document the limit. | team | `DECISIONS.md` |
| **Evaluate with rules v2 in place:** model v1's 0.672 was measured before R14 and R15 took lines away from the model; the v2 evaluation scores both v1 and v2 with rules v2, on the same corrected test set. | team | timeline |
| ~~**Modifier 59 (D-GOLD-3)** is the next task (P2.3c), now that the NCCI Policy Manual is in `data/raw/`; it lands before the v2 data is regenerated.~~ **Done in P2.3c** (D-RULE-8: the manual's full list of NCCI PTP-associated modifiers with their placement). | — | timeline |
| **Generator v2: the new R11 modifiers.** The v1 dataset bills only XS. Generate 25 on same-day office visits with minor procedures (000, 010 or XXX global), 57 with 090-day procedures, 59 and X modifiers on procedure lines, and RT/LT at different sites, with notes that support or fail each bypass (D-RULE-8). | team | `DECISIONS.md` |
| **Prompt v2: NCCI_BYPASS wording per modifier.** Today the flag asks the model to check for "a separate, distinct service"; for 25 it should check for a significant, separately identifiable E&M, and for 57 a decision for surgery (D-RULE-8). | team | `DECISIONS.md` |
| Before measuring end-to-end metrics on dataset claims (P6.1), resolve D-GEN-5: 1,072 of the 2,600 dataset claims refer to authorizations missing from the reference data and would be denied by R10 before the model. Fixed by the v2 regeneration; if P6 measures model v1 end to end, add the missing authorizations to the reference data first (a data fix, not a label change). | team | `DECISIONS.md` |

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
- **A raw file can vanish without anything failing.** The NCCI part f1 `.txt` disappeared from
  `data/raw/` on 2026-09-22 and was only noticed in G2, when the blind-review reproducibility test
  ran with Docker up. Since then `data/raw_manifest.csv` (D-DATA-1) lists every raw file with its
  SHA-256, and a test fails when one is missing or changed. Keep a backup of `data/raw/`.
- **Large Hugging Face downloads stall inside Claude Code's sandbox;** run them in your own terminal.
- **zsh:** do not type `<` and `>` around placeholders (`--kaggle-user manideep3183`, not
  `<manideep3183>`).
- **Kaggle:** "T4 x2" must be used as one GPU (the script sets `CUDA_VISIBLE_DEVICES=0`); Gemma 4
  trains in float32 on T4 (no bf16, fp16 unsupported); `/kaggle/working` holds only 20 GB, so the
  GGUF export runs in `/tmp` and keeps only the Q4_K_M file and the `mmproj` file; the dataset mounts
  at `/kaggle/input/datasets/<user>/<slug>/...` and the notebook finds files by search, so keep only
  one `train.py` in the dataset.
- **Known limitation, `reviewer_id` length (P5.3):** the `ReviewAction` contract sets no maximum,
  but the audit trail's actor column holds 64 characters, so a longer reviewer ID is refused with
  422 (no contract change, team decision 2026-10-09).
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

### 2026-09-28

- 12:52 | Manideep3183 | verification | **Policy source and completeness check V1b (branch `v1-data-verification`: `1d56f24`, `c6d8e0c` and the wrap-up commit); report only, no policy, label or generator changed.** Takeaway: the policies are simplified versions of their LCDs (72 findings), but the 4 wrong criteria change at most 6 v1 labels (all POL-REHAB-001 PENDs); the main label risk remains the NOT_APPLICABLE handling found in V1a. Checker `scripts/verify/policy_sources.py`; outputs in `data/generated/verification/` (git-ignored).
  - **Sources (Part 1):** all 57 criteria cite an LCD excerpt in `data/curated/policy_sources.csv`; all 57 are word for word in the MCD text (similarity 1.0, none NOT FOUND) and none contains AMA CPT descriptor text. 30 flagged for review: composite 26 (17 composite only), differing values 7, low meaning similarity 5, outside the coverage field 1; the 3 POL-PAIN-001 flags were already decided in V1a.
  - **Completeness (Part 2):** 1,060 LCD items (161 background blocks skipped): mapped to an excerpt 127, covered by a paraphrase 161, already decided 8, affects decisions 207, rule candidate 24, out of scope 533. The 917 item judgments (`data/verification/B_completeness_classification.csv`, tracked, overwrite-guarded) are **Claude-proposed and not yet reviewed**; 7 of them correct keyword-rule misfires.
  - **Keyword rules misfire:** 7 of 23 rule classifications were wrong (30%), all among the 10 items the rules called rule candidates (billing keywords 3, frequency keywords 4). The 13 out-of-scope rule classifications are checked only through 3 review controls.
  - **72 findings**, each one proposed v2 change to one policy and together holding all 231 gap items once: WRONG CRITERION 4, MISSING CRITERION 52, RULE CANDIDATE 16 (7 need a patient's earlier claims; 9 are single-claim, 2 of them limits on same-day rules).
  - **Wrong criteria, lines the error could change** (codes: billing-article covered codes by ICD-10-CM FY2027 description): POL-SURG-004.F1 congenital ptosis or palsy **0** (18 codes, A56439); POL-DX-003.F1 food allergy on 95024 **0** (52 codes, A57531); 95024 is the only intradermal code in scope; POL-CAR-002.F1 c2 on 93268 **0**; POL-REHAB-001.F1 evaluation lines with c2 NOT_MET or NOT_DOCUMENTED **15** (train 13: DENY 8, PEND 5; validation 1 PEND; test 1 DENY), of which **6** (all `pend_missing` PENDs, e.g. DEC-TR-00916) could become APPROVE; the other 9 are diagnosis mismatches that R15 denies first.
  - **Lost scratchpad scripts** (CLAUDE.md now requires such code under `scripts/`): `esi_impact.py`, `extra_records.py`, `judge.py`, `write_sources.py`. **No longer reproducible from code:**
    - all of A_impact.md, including the V1a entry's numbers: 222 ESI lines (176 headline; 46 excluded: 21 contradictory notes, 25 diagnosis mismatch, 3 conflicting duration); 234 status labels and 95 decisions changed; 3 of 11 changed test decisions fix a model error; macro-F1 0.6732 -> 0.6677 (accuracy 0.6875) and 0.6692 (accuracy 0.6893); the pattern-agreement percentages; 391 diagnosis-mismatch lines (226 + 165 by scenario), 393 NOT_MET labels, 381 of 393 on the first applicable criterion, 183 of 393 (47%) off the indication criterion; R14 on 32 ESI lines (24 two_policy, 20 would become DENY);
    - all of A_extra_records.md: 5 of 69 NOT_APPLICABLE c2/c3 lines with no previous injection (train 3, validation 1, test 1; the V1a entry's "5 first injections labelled like repeats"), the phrase counts (54, 44, 10, 8) and the explicit no-injection count (0);
    - the 910 original judgments cannot be re-derived and the excerpt choice cannot be re-run; every V1b number is reproducible from the tracked files.
  - **New decisions:** D-RULE-1, D-SCOPE-1. Checks pass except the known NCCI test (f1.txt not extracted).

### 2026-10-02

- 13:00 | Manideep3183 | verification | **Data verification V1 complete: model disagreement review V1c and review verdicts V1d (branch `v1-data-verification`: `b73a31f`, `374a4db` and the V1d commit; merged into `main`).** Report only: no data, label, policy or generator changed. Scripts `scripts/verify/model_disagreements.py` and `scripts/verify/review_verdicts.py`; the filled review sheets and their summary are tracked in `data/verification/reviews/`.
  - **V1c:** claimsense-decision:v1 on the 300 test records (282 valid answers) disagrees with gold **319 times**: 203 of 1,036 criterion statuses and 116 of 386 line decisions (27 of them invalid answers, PEND). Counts equal the evaluator's saved summary. **95 (30%) are already explained** by known label problems (76 records): diagnosis mismatch 51 status + 20 decision, ESI lines 9 + 7, POL-REHAB-001 evaluation lines 9 + 2, two_policy contradictory notes 3 + 1 (7 disagreements in two groups). **224 (70%) are not**, led by MET -> NOT_DOCUMENTED (43 of 47 unexplained), MET -> NOT_APPLICABLE (31 of 31), the NA/ND boundary (20 of 48) and APPROVE -> PEND (45 of 51). Reproducible again from committed code: the 391 diagnosis-mismatch lines (all gold DENY) and the 21 D-ESI-5 records from the lost `esi_impact.py`.
  - **How each review was done:** A (V1a label flags): verdicts decided with Claude's help during V1a. B (V1b, two sittings): verdicts suggested by Claude and accepted by the reviewer. C (V1c disagreements): statuses are Claude's reading, accepted by the reviewer (not a blind review).
  - **Review counts:** A (5): REAL ERROR 5 (all POL-PAIN-001.c2 on repeat ESIs, as D-ESI-1 expects). B sitting 1 (14): MATCHES 8, DIFFERENT MEANING 4 (CAR-002.c1, CAR-002.c3, PAIN-002.c4, SURG-002.c2), NOT IN SOURCE 1 (FOOT-001.c3), UNSURE 1 (CAR-001.c1); both controls MATCHES. B sitting 2 (12): ADD IN V2 8, NOT NEEDED 4 (WOUND-001.F5 and the 3 controls, so the keyword rule's out-of-scope calls held). C (12): LABEL RIGHT 5, MODEL RIGHT 4, UNSURE 3. By error type: MET -> NOT_DOCUMENTED 3 of 3 LABEL RIGHT; NOT_MET -> NOT_DOCUMENTED 2 of 3 LABEL RIGHT, 1 UNSURE; NA/ND boundary 1 MODEL RIGHT, 1 UNSURE; MET -> NOT_APPLICABLE 3 of 4 MODEL RIGHT, 1 UNSURE.
  - **Conclusions:** the V1c sample shows MET -> NOT_DOCUMENTED and NOT_MET -> NOT_DOCUMENTED errors are mostly the model's (note wording), while MET -> NOT_APPLICABLE errors are mostly a label convention problem (exclusion criteria labelled MET; D-GEN-3). The sample is small (3, 3 and 4 rows).
  - **New decisions:** D-V2-1, D-V2-2, D-GEN-3, D-GEN-4, D-REV-1, D-LIM-1. Known limitations (D-LIM-1): V1b sitting 1 row 12 (CAR-001.c1); V1c rows 4 (DEC-TE-00044), 6 (DEC-TE-00177, contradictory notes) and 11 (DEC-TE-00138). Checks pass except the known NCCI test.

### 2026-10-03

- 17:06 | Manideep3183 | verification | **Golden-test spot-check G1 and G2 (branch `g1-golden-spotcheck`: `f4bb9fd` and the G2 commit; merged into `main`).** Report only: no golden case, rules code or calculator code changed. Scripts `scripts/verify/golden_checks.py` (checks and spot-check sheet) and `scripts/verify/golden_compare.py` (answers and comparison); the filled sheet and `G_summary.md` are tracked in `data/verification/reviews/`.
  - **Automatic checks on every golden case** (52 calculator, 90 rules): **0 violations** of the cost-share rules (plan pays + member pays = max(0, allowed − primary paid), allowed ≤ billed, the remaining deductible and out-of-pocket maximum, copay ≤ allowed, denied and pended lines pay 0, whole cents, totals and accumulators) or of section 8.3 (one outcome, group order with D8, H5). INSTRUCTIONS.md section 8.3 item 3 now says Group C is R11–R13.
  - **R15 conflicts:** 6 lines in 5 rules cases (R11-02, R11-03 lines 1 and 2, R11-07, R11-08, X-02) bill 11042 or 97597 with L97419, which billing article A58565 does not cover, so R15 (D-DX-1) would deny them (D-GOLD-1). No R14 conflicts. 9 cases carry codes a D-RULE-1 candidate covers (PAIN-001.F6: 8 ESI cases; PAIN-002.F9: X-01), to review when those rules are built.
  - **Coverage gaps:** no golden case for R14, R15 or the 9 single-claim D-RULE-1 rules; no calculator case splits the deductible across two lines, and only one each caps a copay at the allowed amount or has the primary paying at least the allowed amount (D-GOLD-2). Thin: H5 on a Group C rule (1 case), REJECT winning in Group B (1).
  - **Spot-check:** 10 rules and 9 calculator cases (no case exists for a deductible spanning lines). **10 of 10 rules cases agree** on outcome, reason codes and flags (9 of 9 independent) and **all 66 calculator amounts agree**, exact to the cent; no golden case is wrong. The spot-check answers were computed by a separate Claude chat from the sheet's text only, without access to the repository or the answers file, and accepted by the reviewer. This is a Claude recomputation, not a blind human check, and not independent of the golden cases' author (also Claude). P-01 is not independent (the sheet leaked its outcome; fixed in G2). The rules sample is only partly blind, because the sheet names the rule each case exercises; the calculator cases show no expected values but list the assumptions each case relies on (C19 and C21 name A4, the out-of-pocket cap).
  - **Reviewer verdicts:** golden assumptions ACCEPT 19, CHANGE 1 (A-R3: add modifier 59 in v2, D-GOLD-3); H5 mapping ACCEPT 12, CHANGE 2 (R07 and R09 also use member_id, D-GOLD-4 and D-GOLD-5). Neither change affects any golden rules case (re-checked in G2).
  - **Fixed in G2:** the sheet's wording gave away P-01's outcome; `app/db/raw.read_place_of_service_codes` cut 40 of 52 place-of-service names at the PDF's first line break (22 read "On Campus-") and now reads the name column whole (the generator loads these names but never uses them).
  - **Reproducibility failure found:** with Docker and Qdrant running, `test_blind_review_is_reproducible` failed: 17 of the 30 blind-review claims regenerated differently (CLM-BLIND-001 lost its NCCI_BYPASS flag; claims 015–030 diverged). Cause: the NCCI part f1 `.txt` (`ccipra-v323r0-f1.TXT`) had been missing from `data/raw/` since 2026-09-22, so the generator found no edit whose column-1 code is below 25405 (such as 11042/97597). G2's changes were not the cause: the test failed the same way with the original reader.
  - **f1 read from its official `.xlsx`:** the `.txt` could not be restored (no copy in the repository, ~/Downloads, ~/Desktop or ~/Documents; ~/claimsense-backups does not exist; the CMS download was blocked, access denied), so `app/db/raw.py` reads a part from its official `.xlsx` (same CMS release) when its `.txt` is missing; recorded in SOURCES.md. For f2–f4 the `.xlsx` gives exactly the `.txt`'s edit records (code pairs, modifier indicators, effective and deletion dates; 1,962,488 records together); f1's `.xlsx` has 675,157 records (the CMS page's count) and contains (11042, 97597); f1–f4 total 2,637,645, as in SOURCES.md.
  - **Raw-data manifest (D-DATA-1):** `data/raw_manifest.csv` lists the 62 files in `data/raw/` (409,804,716 bytes) with size and SHA-256 (macOS `.DS_Store` excluded); a test fails if a listed file is missing or changed and reports unlisted files; `scripts/verify/raw_manifest.py --update` rewrites it (first written 2026-10-03).
  - **Reproducibility confirmed:** the full suite passes with Docker and Qdrant running (906 passed, 1 skipped: the opt-in live-model test; 0 failed), including `test_ncci_pairs_include_known_edits` (the long-standing failure is fixed) and the blind-review test (all 30 claims identical to `claims.json`). The readiness gate's train/live parity check found 0 differences on 75 sampled records (25 per split). The decision dataset regenerated into a temporary folder has exactly the section 2 fingerprints (train `295cc6b1d3af`, validation `6478d11211a2`, test `afaa098ffc72`) and identical inputs files.
  - **New decisions:** D-GOLD-1 to D-GOLD-5, D-DATA-1.
- 20:22 | Manideep3183 | P2.3a | **Rules engine, v1 rules (branch `p2.3a-rules-engine`, `2b38bad`..`07b7aeb`; merged into `main`).** Group A (R01–R04, duplicates; contract errors map to R01/R02/R03, A-R8), Group B (R05–R10, all evaluated, REJECT > DENY > PEND, D8), Group C (R11–R13, the generator's mirror algorithm; bypass modifiers XE/XP/XS/XU, 59 is v2 per D-GOLD-3), H5 with the G1 mapping plus member_id on R07 and R09 (D-GOLD-4, D-GOLD-5); every rule result lists its `fields_used`. `RULES_VERSION` 1.0.0. R14, R15 and the D-RULE-1 rules are P2.3b.
  - **Golden:** 90 of 90 rules cases pass (outcome, status, failures, line outcomes, flags); no case changed.
  - **Parity (frozen for model v1):** 0 differences on 2,600 train/validation/test records in claim outcome, OON flag, line outcomes and the prompt's RULES_RESULT text (`scripts/verify/rules_parity.py`, `tests/unit/test_rules_parity.py`).
  - **Full engine on the dataset (report only):** 1,072 of 2,600 claims would stop at R10 (DN_NO_AUTH): 996 carry a prior-authorization number not in the reference data, 76 a number belonging to another member's authorization (numbering reused from the claim corpus). No member or provider is missing. D-GEN-5.
  - **R05** now names every date of service (G1 mapping): the cautious reading, more REJECTs and fewer wrong denials. **Code table** for R02: PFS RVU26A ∪ HCPCS October 2026 (20,591 codes).
  - **Pipeline:** unchanged in behaviour (R05 only), now recorded as rules version 0.1.0 until it switches to the full engine.
  - **NCCI part f1 restored:** the team supplied the original f1 download. Its `.xlsx` is byte-identical (SHA-256) to the one in `data/raw/`, and its `.TXT` parses to exactly the same 675,157 edit records, including (11042, 97597). The `.TXT` was moved into `data/raw/ncci-ptp/ccipra-v323r0-f1/` (not committed) and the copy in the repository root removed; `data/raw_manifest.csv` was rewritten deliberately with `--update` (D-DATA-1): 63 files, 460,751,103 bytes, the f1 `.TXT` added and nothing else changed. f1 is read from its `.txt` again; the `.xlsx` fallback stays (SOURCES.md). With Docker running, the NCCI tests (the `.xlsx` gives the same edits as the `.txt` for f1–f4), the blind-review reproducibility test and dataset parity pass.
  - **Tests:** 1,071 pass, 1 skipped. New decision: D-GEN-5.
- 20:48 | Manideep3183 | P2.3a-ci | **Golden rules cases run in CI (branch `p2.3a-ci-fixture`, `fb02580`..`f485e34`; merged into `main`).** `scripts/verify/rules_fixture.py` writes `tests/golden/rules/raw_subset.json`, the raw rows the 90 cases need: 8 ICD-10-CM, 16 procedure and 2 place-of-service codes, 11 NCCI edits, 16 MUE limits; codes, dates, indicators and limits only, and codes missing from the real tables (99999, M541, POS 00) stay absent. Where `data/raw/` is present every case runs with both the raw tables and the fixture, and a freshness test requires the fixture to equal a fresh extraction; without it (CI, or `CLAIMSENSE_IGNORE_RAW=1`) the cases run on the fixture alone. The rules "codes exist" check in `test_golden_files.py` uses the fixture too, so it also runs in CI; the calculator consistency check still needs `data/raw/` (P2.4). Checked in a worktree with no `data/raw/`: all 90 pass. Tests: 1,166 pass, 1 skipped. New decision: D-CI-1.

### 2026-10-04

- 11:03 | Manideep3183 | P2.4-G, G3 | **Four new calculator golden cases (D-GOLD-2), checked and added (branch `p2.4g-calculator-golden`: `44b8511` and the G3 commit; merged into `main`).** `scripts/verify/new_calculator_cases.py` drafted C53 (deductible split across two lines), C54 (copay capped by the allowed amount; billed and fee both below the copay), C55 (COB: the primary paid more than the allowed amount on line 1 and nothing on line 2) and C56 (out-of-pocket maximum reached on line 2 of three), with expected amounts and worked steps following §8.6 and A1-A9. The same computation reproduces all 52 earlier golden calculator cases, amounts and worked steps word for word.
  - **Independent check:** the answers were computed by a separate Claude chat from the blind sheet `G3_new_cases_sheet.md` only (inputs and the quoted §8.6 steps; no titles, expected values, worked steps, situations or per-case assumption names), without access to the repository, the staged cases or any expected amount. This is a Claude recomputation, not a blind human check, and not independent of the cases' author (also Claude). **All 48 amounts agree**, exact to the cent (`scripts/verify/g3_compare.py`; filled sheet and summary in `data/verification/reviews/`).
  - **C55 line 2 depends on assumption A6:** line 1's deductible counts toward the accumulators although the primary paid more than line 1's allowed amount, so line 2 takes no deductible.
  - **Golden set:** 52 -> 56 calculator cases (README updated; the count in `summary.md`, a teammate's file, corrected from 52 to 56 as a factual fix); 0 invariant violations on all 56. Coverage: "deductible spans lines" none -> 1; "copay capped by the allowed amount" and "COB: primary paid >= allowed" 1 -> 2; "out-of-pocket maximum reached" 7 -> 8. D-GOLD-2's calculator cases are done; its rules cases (R14, R15, D-RULE-1) remain for P2.3b.
  - **CI runner pinned** to `ubuntu-24.04` (GitHub moves `ubuntu-latest` to Ubuntu 26 on 2026-10-19).
  - **Tests:** 1,241 pass, 1 skipped.

### 2026-10-05

- 10:42 | Manideep3183 | P2.4 | **Full calculator (branch `p2.4-calculator`: `651951a`..`2a5fa40` and the final P2.4 commit; merged into `main`).** §8.6 with A1-A9 in `app/calculator/engine.py`: allowed amount (A1), contractual adjustment or balance-bill exposure (A9), COPAY and DEDUCTIBLE_COINSURANCE with out-of-network lines on deductible and coinsurance (A3), the out-of-pocket cap filled deductible, copay, coinsurance (A4, A5), working accumulators across lines (stored ones never written), COB as secondary (A6), denied and pended lines (A7), totals (A8). Built from §8.6 and A1-A9 only; it shares no code with `scripts/verify/new_calculator_cases.py` (each rounds with Python's Decimal ROUND_HALF_UP). `CALCULATOR_VERSION` 1.0.0.
  - **Golden:** all 56 calculator cases pass (amounts, totals, accumulators after); no case changed; they run in CI.
  - **Property tests:** 5,000 seeded random claims pass every `golden_checks` invariant; every cost-share situation appears at least 20 times; a broken COB formula or a missing cap is caught.
  - **CI fixture (D-CI-2):** `tests/golden/calculator/raw_subset.json` (17 codes and their PFS RVUs) lets the golden fee-consistency check run without `data/raw/`; a freshness test keeps it current.
  - **Pipeline:** switched from the copay-only path to the full calculator (the database holds plans, benefits, fees and accumulators; the claim carries the primary payments). `calculator_version` is recorded in the CALCULATED audit event. A calculation error is audited as CALCULATION_FAILED and the claim goes to FULL review with the reason in `output_errors` and no amounts: an approved line whose code has no fee, or out-of-network care on a plan with no out-of-network terms (both with an end-to-end test); migration 0002 adds the event type, and INSTRUCTIONS.md §8.9 lists it.
  - **Tests:** 1,391 pass, 1 skipped. New decision: D-CI-2.
- 11:14 | Manideep3183 | P2.1, P2.5 | **Rule tables in the database; the pipeline runs the full v1 rules engine (branch `p2.1-rules-data-pipeline`, `915f058`..`67353c8` and the final commit; merged into `main`).** Migration 0003 keys NCCI rows by a surrogate id with their published order (`source_order`; the PTP table repeats a key in 261 rows) and adds `reference_sources`. The seed loads place of service (52), the full procedure code table (20,591), ICD-10-CM FY2027 (74,879), MUE (15,212) and NCCI (2,637,645) in full, each with its source files' SHA-256 from the manifest; 5.4 s, NCCI 305 MB; loading again changes nothing.
  - **Database-backed reference** (`reference_for_claim`, per claim; the rules stay pure): 0 differences from the file-backed reference on the 90 golden rules cases (fixture and raw) and on all 2,600 dataset records, which still match the generator's rule mirror and the RULES_RESULT text.
  - **Pipeline (P2.5):** `RULES_VERSION` 1.0.0; a rule failure is final (REJECTED, DENIED_BY_RULE, PENDED_BY_RULE) with an AUTO_OUTCOME event and every rule result's `fields_used`, and never reaches the model; Group C denials and flags pass through. A JSON claim failing the contract is filed when R01-R03 report every error (errors in INTAKE_COMPLETED) and is then rejected; one without a claim ID, member ID or received date is refused. A date of service before FY2027 (none in any data set, blind review counted by dates only) gets a 503 and stays RECEIVED. R08 now denies out-of-network care on a plan without out-of-network cover before the calculator. The review page handles both intake responses and shows a claim's contract errors (tested against the real API).
  - **All 30 golden end-to-end claims** pass through the pipeline with every expected value unchanged; their database comes from the committed fixtures, extended to the end-to-end claims (D-CI-3), so they run in CI.
  - **Tests:** 1,608 pass, 1 skipped. New decision: D-CI-3.

### 2026-10-09

- 00:29 | Manideep3183 | P5.3 | **Human review actions and finalization (branch `p5.3-review-finalization`, `18363a4`..`f90d876`; merged into `main` as `7575d36`, `--no-ff`, normal push; CI run 37828554505 passed, 1,438 passed and 46 skipped).**
  - `GET /v1/review/queue`: tier order or oldest first; reviewer role through the `X-Role` header.
  - `POST /v1/claims/{id}/review/open` and `POST /v1/claims/{id}/review`: ACCEPT, or OVERRIDE with a reason for each line; reviewers never enter amounts.
  - Lines denied by R11–R13 cannot be overridden (D-REV-2).
  - Finalization recomputes the amounts against the stored accumulators under a claim-then-member lock (D-REV-3). It updates accumulators and visit usage for approved lines, FINAL_PENDED included (D-REV-7, D-REV-8).
  - Approved contract change: `LineOverride.benefit_category` (D-REV-4).
  - A failed calculation refuses the review (D-REV-5). Review time runs from the reviewer's latest REVIEW_OPENED (D-REV-6, on the database clock; migration 0004).
  - The review page has Accept and Submit, read-only rule lines and a category choice where needed.
  - **All 18 golden review cases** match their golden finals end to end, covering every final status.
  - **Tests:** 1,663 pass, 1 skipped. New decisions: D-REV-2 to D-REV-8.

- 18:00 | Manideep3183 | P2.3b | **Rules v2: R14 to R20 (branch `p2.3b-rules-v2`, `37ab24f`..`87484e5`; merged into `main` as `00a0201`, `--no-ff`, normal push; CI run 37930242869 on `main` passed, 1,637 passed and 52 skipped).**
  - The rules: R14, an ESI with another block on the same date, and its add-ons (D-ESI-3, D-RULE-7); R15, the line's diagnoses against its billing article (D-DX-1, D-RULE-4); R16, a home sleep test for a parasomnia; R17, a flag for nerve conduction without EMG; R18, ESI levels per side; R19, a third-level facet code, and a flag for two spinal regions; R20, a flag above 8 hours of testing.
  - A rule denies only when the source is explicit (D-RULE-2). `RULES_VERSION` 2.0.0; CARC/RARC rows added.
  - **Data:** curated code roles and diagnosis sets; migration 0005 `article_icd10_covered`, 41,680 rows; the ICD-10-CM FY2027 tabular added to `data/raw`, confirming G47.5 and M71.3 "Synovial cyst NOS"; the raw manifest gains `source_url`; the 2026 NCCI Policy Manual added for P2.3c.
  - **Impact:** the first reproducible check of the V1a numbers, matched exactly (391 diagnosis-mismatch lines; R14 on 32 lines, 20 becoming DENY). The approved R15 catches 390 + 12 lines and R17 flags 27 test lines.
  - **Golden:** 31 rules cases checked on sheet G4 by a separate Claude Code session, 218/218 cells agree; rules cases 90 -> 121; E2E-17 becomes a rule outcome, E2E-23's line 1 a rule denial, and E2E-32 is new; D-GOLD-1 done (L97412).
  - **Parity:** 461 listed v2 changes, equal to the independent checks; 0 other differences.
  - **Tests:** 1,930 pass, 1 skipped. CI: 1,637 passed, 52 skipped; the gap is the 242 `data/raw` variants of the golden rules cases and 51 `data/raw` skips. New decisions: D-RULE-2 to D-RULE-7, D-GOLD-6, D-CI-4.

- 18:57 | Manideep3183 | P2.3c | **NCCI modifiers (branch `p2.3c-ncci-modifiers`, `00b4466`..`5c6b655`; merged into `main` as `28af00f`, `--no-ff`, normal push; CI run 37936773272 on `main` passed, 1,758 passed and 55 skipped).**
  - **R11:** bypasses with the 2026 NCCI Policy Manual's PTP-associated modifiers where the manual places them (D-RULE-8): 59 and X modifiers not on an E&M; 25 and 57 by the paired code's global period; anatomic modifiers for different sites. Each bypass is PASS with NCCI_BYPASS. `RULES_VERSION` 2.1.0 under the new version convention (D-RULE-9).
  - **Raw data:** the NCCI Policy Manual 2026 and the add-on code edits (2026 Q4) added with source URLs; 66 files in the manifest.
  - **Data:** `ncci_ptp_modifiers.csv` (44 modifiers, checked against page I-14); migration 0006 `procedure_codes.global_days`; add-on/primary pairs now read from the AOC file, orphan add-ons still 0 (D-RULE-5).
  - **Tables:** the file-backed reference reads every billed code, with a row-by-row test against the database for all golden rules cases and e2e claims (D-CI-5).
  - **Golden:** 13 R11 cases checked on sheet G5 by a normal Claude chat without repository access, 104/104 cells agree; rules cases 121 -> 134; R11-06 reworded (D-GOLD-7).
  - **Impact:** 0 changed lines in the existing golden cases, the e2e claims and the dataset.
  - **History:** the branch was rebuilt once to remove CPT modifier text (force-push with a lease, branch only). CLAUDE.md now treats CPT text in CMS manuals as AMA text.
  - **Tests:** 2,111 pass, 1 skipped. CI: 1,758 passed, 55 skipped; the 299-test gap is the `data/raw` variants. New decisions: D-RULE-8, D-RULE-9, D-GOLD-7, D-CI-5.

<!-- Next entry goes here. Example:
- 2026-09-23 01:30 | Manideep3183 | P4.3 | Full run finished: best eval loss ..., runtime ...; files downloaded to data/generated/models/claimsense-decision-v1/.
-->
