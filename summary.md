# ClaimSense — Project summary

**Status as of 2026-09-28 (IST).** `main` is as of 2026-09-24. Data-verification work from
2026-09-24 to 2026-09-28 is on the branch `v1-data-verification` and is **not merged into `main`
yet** (section 6).
Sources: `PROGRESS_LOG.md`, `DECISIONS.md`, `INSTRUCTIONS.md`, `docs/results.md`, the code itself,
and the `v1-data-verification` branch. Team: Manideep3183, rohanpagadala, Rithwik010.

---

## 1. What ClaimSense is, in one minute

A doctor's office sends a health insurance company a **claim** (the standard paper/electronic form
is called **CMS-1500**). The insurer has to answer three questions for every service on it:

1. **Is the claim valid?** Right codes, real member, real provider, filed on time, and so on.
2. **Is the service covered and medically necessary** for this patient, according to the plan and
   the coverage policy?
3. **How much does the plan pay and how much does the patient owe?**

ClaimSense automates the first draft of those answers and splits the work so each part is done by
the tool that is trustworthy for it:

| Question | Who answers it | Why |
|---|---|---|
| Is the claim valid? | **Deterministic rules** (plain code) | Factual checks; must be exact and repeatable |
| Is the service covered? | **A small AI model** (fine-tuned Gemma 4, running locally) reading the clinical notes against retrieved policy criteria | Needs reading comprehension; the model only *recommends* |
| How much is paid? | **A deterministic calculator** (integer cents only) | Money must never come from an AI |
| Final decision | **A human reviewer** | Every AI recommendation is reviewed before it is final |

Every step is written to an **append-only audit log**, and every explanation is built from the
recorded decision, never from the model's free text. **All data is synthetic**: no real patients.

---

## 2. Status at a glance

| Area | State |
|---|---|
| Foundations (project, database, contracts, walking skeleton) | ✅ Done |
| Knowledge base and training data | ✅ Done |
| AI model fine-tuned and running locally | ✅ Done: `claimsense-decision:v1` in Ollama |
| AI model accuracy | 🟡 **Big improvement, target missed**: macro-F1 **0.672** (base model 0.345, target 0.90) |
| Rules engine | 🟡 1 of 13 rules built (R05 eligibility); 90 test cases already written for the rest |
| Calculator | 🟡 Copay path only; 56 test cases already written for the rest |
| Human review, explanations, scanned-form OCR | 🟡 / ⬜ Partly started or not started |
| Evaluation report and demo (Phase 6) | ⬜ Not started |
| Data verification (V1a labels, V1b policy sources) | 🟡 Reports done on the `v1-data-verification` branch; human review pending; not merged |
| Model v2 plan | 🟡 13 decisions recorded (new rules R14 and R15, corrected criteria, no retrieval cap); not built yet |
| Tests | `main`: 770 pass, 19 skipped, 1 failing. Verification branch: 828 pass, 19 skipped, the same 1 failing (a missing data-file extraction, not a code bug) |

Legend: ✅ done · 🟡 partly done · ⬜ not started

**Roadmap: 15 of 29 tasks done, 10 in progress, 4 not started.**

```text
Phase 1  Foundations              ██████████  5/5 done
Phase 2  Rules + calculator       ██░░░░░░░░  1/5 done, 4 in progress
Phase 3  Knowledge + datasets     ██████████  5/5 done
Phase 4  AI model                 ████████░░  4/5 done, 1 in progress (accuracy target)
Phase 5  Integration              ░░░░░░░░░░  0/6 done, 5 in progress
Phase 6  Evaluation + demo        ░░░░░░░░░░  0/3
```

The team deliberately did the AI-model work first (Phases 3–4) because the model has to be trained
**once** against a frozen set of inputs. The rules engine and calculator (Phase 2) are pure code with
all their test cases already written, so they can be finished in parallel without touching the model.

---

## 3. Architecture

### 3.1 How a claim flows through the system

```text
        CMS-1500 claim (JSON, digital PDF, or scanned image)
                               │
          ┌────────────────────▼────────────────────┐
     1    │ INTAKE                                   │  ✅ JSON  ✅ digital PDF  ⬜ OCR
          │ → IntakeClaim + confidence per field     │
          └────────────────────┬────────────────────┘
                               │
          ┌────────────────────▼────────────────────┐   fails   ┌─────────────────────────┐
     2    │ RULES ENGINE  R01–R13 (plain code)       │──────────▶│ Automatic REJECT / DENY │
          │ codes, NPI, member, eligibility, timely  │           │ / PEND — final, audited,│
          │ filing, network, referral, prior auth,   │           │ no human step           │
          │ NCCI bundling, unit limits, exclusions   │           └─────────────────────────┘
          └────────────────────┬────────────────────┘  🟡 only R05 built so far
                               │ passes (some lines may be denied by line-level rules)
          ┌────────────────────▼────────────────────┐
     3    │ CONTEXT ASSEMBLY                         │  ✅
          │ plan facts from Postgres                 │
          │ + coverage criteria retrieved from Qdrant│
          └────────────────────┬────────────────────┘
                               │
          ┌────────────────────▼────────────────────┐
     4    │ AI MODEL (fine-tuned Gemma 4, Ollama)    │  ✅ runs locally, ~5.5 s per claim
          │ per line: APPROVE / PEND / DENY,         │
          │ each criterion MET / NOT_MET /           │
          │ NOT_DOCUMENTED / NOT_APPLICABLE + quote  │
          │ — never any dollar amount                │
          └────────────────────┬────────────────────┘
                               │
          ┌────────────────────▼────────────────────┐
     5    │ OUTPUT VALIDATION (plain code)           │  ✅
          │ bad or inconsistent answer → every line  │
          │ PEND, claim goes to FULL review          │
          └────────────────────┬────────────────────┘
                               │
          ┌────────────────────▼────────────────────┐
     6    │ CALCULATOR (plain code, integer cents)   │  🟡 in-network copay only
          │ allowed, deductible, copay, coinsurance, │
          │ out-of-pocket cap, COB, plan pays        │
          └────────────────────┬────────────────────┘
                               │
          ┌────────────────────▼────────────────────┐
     7    │ DECISION RECORD + EXPLANATION            │  ✅ record  ⬜ explanation
          │ claim decision derived by code;          │
          │ review tier QUICK / STANDARD / FULL      │
          └────────────────────┬────────────────────┘
                               │
          ┌────────────────────▼────────────────────┐
     8    │ HUMAN REVIEW: ACCEPT or OVERRIDE         │  🟡 tiers computed;
          │ (reason required) → FINAL_* status,      │     review actions not built
          │ accumulators updated                     │
          └─────────────────────────────────────────┘

     Every step writes an insert-only AUDIT event (✅)
```

**Claim decision** is computed by code from the line decisions, never by the model:
any PEND → PEND; all DENY → DENY; all APPROVE → APPROVE; a mix of APPROVE and DENY → PARTIAL.

**Review tier** is also computed by code:

| Tier | When |
|---|---|
| FULL | Any line denied by the model, complexity HIGH, or the model's output was invalid |
| STANDARD | Any PEND, complexity MEDIUM, total allowed ≥ $1,000, or a low-confidence field |
| QUICK | Everything approved, complexity LOW, below the dollar threshold |

**Claim statuses:** `RECEIVED` → one of `REJECTED`, `DENIED_BY_RULE`, `PENDED_BY_RULE` (final, no
human) or `AWAITING_REVIEW` → `FINAL_APPROVED` / `FINAL_PARTIAL` / `FINAL_DENIED` / `FINAL_PENDED`.
Allowed transitions are an explicit table in `app/workflow/states.py`; anything else raises an error.

### 3.2 What runs where (runtime architecture)

Everything runs on a laptop. There are **no external AI APIs**: the model runs locally through Ollama.

```text
   Browser
      │
      ▼
 ┌───────────────┐   HTTP only    ┌────────────────────────────┐
 │ React web app │ ─────────────▶ │ FastAPI  (app/api)          │
 │ frontend-web/ │ (Vite proxy)   │ runs the synchronous        │
 │ :5173         │                │ pipeline (app/workflow)     │
 └───────────────┘                └──────┬────────┬────────┬───┘
                                         │        │        │
                              SQLAlchemy │        │ qdrant │ ollama
                                         ▼        ▼        ▼
                              ┌────────────┐ ┌─────────┐ ┌────────────────────────┐
                              │ PostgreSQL │ │ Qdrant  │ │ Ollama (native app)    │
                              │ :5432      │ │ :6333   │ │ :11434                 │
                              │ Docker     │ │ Docker  │ │ claimsense-decision:v1 │
                              │ plans,     │ │ policy  │ │ (Gemma 4 E2B, 3.4 GB)  │
                              │ members,   │ │ criteria│ └────────────────────────┘
                              │ claims,    │ │ vectors │
                              │ audit log  │ └─────────┘
                              └────────────┘
```

| Layer | Technology |
|---|---|
| Language / packaging | Python 3.11, `uv` |
| API | FastAPI, uvicorn, Pydantic v2 |
| Database | PostgreSQL 18, SQLAlchemy 2.0, Alembic |
| Vector search | Qdrant, fastembed with `BAAI/bge-small-en-v1.5` |
| Model serving | Ollama (local) |
| Model training | Unsloth QLoRA on a Kaggle T4 GPU |
| Frontend | React web app (Vite, TypeScript; D-UI-1, D-UI-2; Streamlit until 2026-10-10) |
| Quality gates | ruff, pytest, import-linter, pre-commit, GitHub Actions CI |

### 3.3 Code structure and built-in guardrails

```text
app/
├── domain/       frozen data contracts (IntakeClaim, RulesOutcome, SLMOutput, DecisionRecord ...)
├── intake/       read claims (JSON, digital PDF; OCR later)
├── rules/        R01–R13           ─┐  may NOT import the AI, retrieval or model libraries
├── calculator/   money, in cents   ─┘  (enforced automatically by import-linter)
├── context/      plan facts + retrieved criteria → ContextPackage
├── rag/          embeddings, Qdrant ingestion, retrieval
├── ml/           prompt, Ollama client, output validator
├── workflow/     pipeline, status table, derived decisions
├── review/       review tiers (review actions to come)
├── explain/      explanations from the decision record (not started)
├── audit/        insert-only audit events
├── db/           tables, migration, seed loaders, policy format checker
├── api/          FastAPI routes
└── core/         settings, logging
frontend-web/     React web app — talks to the API over HTTP only, never imports app/
training/
├── generate/     synthetic members, providers, claims, notes, forms, dataset
├── finetune/     Kaggle QLoRA training + GGUF export + Ollama Modelfile
├── evaluate/     model and retrieval evaluation
└── readiness.py  9 automated checks that must pass before training
```

Three import rules are checked on every CI run: rules and calculator never touch AI code; the
domain contracts depend on nothing else; the frontend never imports the application.

### 3.4 Data architecture

```text
 data/raw/   public CMS / X12 files (codes, fees, NCCI, MUE, coverage LCDs, CARC/RARC)
   │         downloaded by people, never committed
   ▼
 data/curated/   committed; plans and benefits are FICTIONAL, criteria cite their LCD source
   │  5 plans (PPO Gold, PPO Silver, HMO, EPO, HDHP) · 60 procedure codes in scope
   │  17 coverage policies (57 criteria) · exclusions · fee rule · reason-code map
   │
   ├── app/db/seed.py ───────────▶ PostgreSQL (plans, benefits, fees, codes, members, providers,
   │                                authorizations, accumulators)
   └── app/rag/knowledge.py ─────▶ Qdrant collection `coverage_policies`
                                    (one vector per criterion, knowledge version 36cfc77305a5)
                    │
                    ▼
 training/generate/   scenario → label → claim → clinical notes → rendered forms
                    │  (ground truth first, then everything else is generated from it)
                    ▼
 data/generated/decision/   train 2,000 / validation 300 / test 300 (never committed)
                    │  test uses different note wording and 4 policies never seen in training
                    ▼
 Kaggle T4 GPU: QLoRA fine-tune of Gemma 4 E2B (3 h 02 min)
                    ▼
 GGUF Q4_K_M (3.4 GB) → Ollama Modelfile → claimsense-decision:v1
                    ▼
 training/evaluate/model.py → docs/results.md
```

**Synthetic reference data:** 500 members (some terminated), 100 providers (valid NPIs, some
unenrolled or out-of-network), 150 prior authorizations (some expired or for the wrong code),
other coverage records, accumulators and visit usage.

**Dates and code versions:** dates of service 2026-10-01 to 2026-12-31; ICD-10-CM FY2027,
HCPCS October 2026, NCCI PTP v323r0, MUE 2026-10-01, Physician Fee Schedule RVU26A.
Allowed amount = national non-facility fee × 125% in-network, × 100% out-of-network.

---

## 4. What works end to end today

The **walking skeleton** runs one JSON claim through every stage in its simplest form:

```text
POST /v1/claims/intake           → claim stored as RECEIVED
POST /v1/claims/{id}/process     → R05 → context + retrieval → model → validation
                                   → copay calculator → decision record → AWAITING_REVIEW
GET  /v1/claims/{id}             → the decision record
GET  /v1/claims/{id}/audit       → the audit trail
Web page (Streamlit at the time) → submit, process, view record and audit trail
```

Not yet possible: rules other than R05 (an unknown member or provider returns an error),
deductible/coinsurance/out-of-network/COB amounts, PDF or scanned uploads through the API, the
review queue, accept/override, finalization, explanations, and the plan endpoint.

---

## 5. The AI model: what was built and how well it works

### 5.1 How it was trained

| Item | Value |
|---|---|
| Base model | Gemma 4 E2B instruction-tuned (`unsloth/gemma-4-E2B-it`) |
| Method | QLoRA (4-bit base, LoRA r=16, alpha 16), attention + MLP layers, vision layers frozen |
| Data | 2,000 training records, each: prompt `decision_v2` + claim + rules result + plan benefits + retrieved criteria → target answer |
| Run | 500 steps, 2 epochs, 3 h 02 min on a Kaggle Tesla T4 (float32) |
| Export | GGUF Q4_K_M (3.43 GB), served by Ollama 0.34.1 as `claimsense-decision:v1` |

### 5.2 Results on the 300 held-out test claims

| Measure | Base Gemma 4 | **Fine-tuned v1** | Fine-tuned, no retrieved criteria |
|---|---|---|---|
| Valid, well-formed answers | 73% | **94%** | 91% |
| Line decision accuracy | 0.42 | **0.70** | 0.52 |
| Macro-F1 (target ≥ 0.90) | 0.345 | **0.672** | 0.296 |
| Criterion status accuracy | 0.63 | **0.80** | — |
| Evidence quoted word for word | 0.70 | **0.98** | — |
| Claim decision accuracy | 0.43 | **0.68** | 0.47 |
| Median time per claim | 9.6 s | **5.5 s** | 1.5 s |

What this means in plain terms:

- **Fine-tuning roughly doubled accuracy** and made the model faster and far more disciplined.
- **It never wrongly denies**: DENY precision is 1.00. Its mistake is caution: it sends too many
  lines to PEND ("needs more information"), which a human then reviews. That is the safe
  direction to be wrong in.
- **It generalises to new policies**: accuracy on the 4 policies never seen in training (0.69) is
  the same as on seen ones (0.70).
- **Retrieval matters a lot**: without the retrieved coverage criteria, macro-F1 falls from 0.672
  to 0.296, the model denies nothing at all, and it starts inventing policy IDs. Retrieval is worth
  more (0.376) than fine-tuning (0.327); the two together are what works.

### 5.3 Why the 0.90 target was missed (measured, not guessed)

The gap is 0.228. The team diagnosed where it comes from:

| Cause | Share of the gap | Fix | Needs retraining? |
|---|---|---|---|
| **Wording.** Test notes are deliberately written in a different style from the training notes. The model says "not documented" when the fact is there in unfamiliar words. On same-style notes it scores 0.816. | 0.144 | Train on more writing styles | Yes |
| **Self-contradiction.** On ~8% of lines the model says PEND even though its own criterion answers imply APPROVE or DENY. | 0.027 | Compute the line decision from the criterion answers in code | No |
| **Unclear label boundary** between "not applicable" and "not documented". Errors go both ways and are spread thin — a sign the definition is fuzzy, not that the model failed to learn. | part of the rest | Decided for v2: every criterion gets a type (requirement, exclusion, conditional) that fixes what silence in the notes means, and notes must carry the evidence their labels claim (D-ESI-6, D-GEN-1) | Yes |
| **Dropped second line** on claims whose two lines need identical answers (16 records). A decoding quirk: at temperature 0 the model deterministically skips it. | part of the 6% invalid | One seeded retry at temperature 0.7, only when the answer is invalid (recovers 5–8 of 16) | No |
| **Runaway answers** (5 records, 12–15k characters). | part of the 6% invalid | Output capped at 1,536 tokens (already done) | No |

Takeaway: **more training data alone would land near 0.82, not 0.90.** Reaching the target needs
the no-retraining fixes plus a retrain with more note styles and a sharper prompt.

### 5.4 A finding about retrieval

The retriever does two things: an exact filter (policy covers this procedure code, applies to this
plan, effective on the date of service) and then similarity ranking with a top-5 limit. In the
current policy set **no procedure code has more than 5 criteria**, so the ranking never changes
*which* criteria the model sees — the filter alone decides. The criteria are essential; the vector
ranking will only start to matter at the scale of a real policy library.

Decided for v2 (D-RAG-1, on the verification branch): the decision criteria come from the exact
lookup with **no top-k cap**; vector search is kept for the explanation collections (P5.4).
Model v1 keeps its current retrieval.

---

## 6. Data verification and the v2 plan (branch `v1-data-verification`, not merged)

Between 2026-09-24 and 2026-09-28 the training labels and the coverage policies were checked
against their Medicare sources. Both checks are **reports only**: no label, policy or generator
has been changed yet, and model v1 and its data stay frozen.

### V1a — are the training labels right? (`scripts/verify/label_checks.py`)

- **Checks 1–4 found no problems** in 2,600 records (3,335 decided lines): diagnoses support the
  approved and pended lines; every decision follows from its criterion statuses; all 4,046 MET
  evidence quotes appear word for word in the notes; every labelled criterion was retrieved.
- **Check 5 cannot verify most NOT_APPLICABLE labels automatically.** This is the same weak spot
  the model evaluation found.
- **Epidural steroid injection (ESI) labels conflict with LCD L33906.** The LCD applies every
  indication to every injection; the generator did not. Fixing the labels would **not** close the
  gap to 0.90 (estimated test macro-F1 0.6732 → 0.6677), because the v1 notes lack what the
  corrected labels require.
- Found 391 lines where the diagnosis does not fit the procedure, which led to rule R15 (below).

### V1b — do the policies match their LCDs? (`scripts/verify/policy_sources.py`)

- **All 57 criteria cite a word-for-word LCD excerpt** (`data/curated/policy_sources.csv`), and none
  contains AMA CPT descriptor text.
- **72 findings** where the simplified policies differ from the LCDs: 4 wrong criteria, 52 missing
  criteria, 16 candidates for deterministic rules. The 4 wrong criteria change at most 6 v1 labels
  (all POL-REHAB-001 PENDs).
- **Human review is pending** in two short sittings (about 28 and 34 minutes).

### What v2 will change (decided and recorded in `DECISIONS.md` on the branch; not built)

| Decision | Change |
|---|---|
| D-ESI-1 to D-ESI-7 | ESI criteria follow LCD L33906: all indications apply to every injection, clearer MET conditions, a new exclusion for non-specific back pain, consistent notes, and new rule **R14** (an ESI is denied when another block is billed the same day) |
| D-ESI-6 | Every criterion gets a type (requirement, exclusion, conditional) that fixes what silence in the notes means |
| D-GEN-1, D-GEN-2 | The generator must write the evidence its labels claim, and never picks a NOT_MET criterion by retrieval rank |
| D-DX-1 | New rule **R15**: a line whose diagnoses do not fit the procedure is denied automatically (`DN_DX_NOT_SUPPORTED`); the model never sees it |
| D-RAG-1 | Decision criteria come from the exact lookup with no top-k cap |
| D-RULE-1 | Rules that need a patient's earlier claims (7 of 16 candidates) are deferred as a known limitation; v2 builds the 9 single-claim candidates, R14 and R15 |
| D-SCOPE-1 | v2 fixes all wrong criteria after review, plus the top-impact missing criteria; the rest are documented as known gaps |

All of these are bundled: the dataset is regenerated and the model retrained **once**, together.

**Caveat:** some V1a impact numbers (including the 0.6732 → 0.6677 estimate) came from scratchpad
scripts that were lost, so they cannot be reproduced from code. The branch's `CLAUDE.md` now requires
any code that produces data or report numbers to live under `scripts/` and be committed.

---

## 7. Phase-by-phase progress

| Phase | Done | In progress | Not started |
|---|---|---|---|
| **1 Foundations** | P1.1 tooling + CI · P1.2 Docker, settings, `/health` · P1.3 database + migration · P1.4 contracts (frozen 2026-09-22) · P1.5 walking skeleton | | |
| **2 Rules + calculator** | P2.2 reference data generator | P2.1 seed loaders (NCCI, MUE, place-of-service missing) · P2.3 rules (R05 only) · P2.4 calculator (copay only) · P2.5 workflow (status table only) | |
| **3 Knowledge + datasets** | P3.1 policy checker · P3.2 plan-summary (SBC) generator · P3.3 retrieval (recall@3 0.978, target 0.85) · P3.4 claim + form generator · P3.5 decision dataset v2 | | |
| **4 AI model** | P4.1 prompt, client, validator · P4.2 baseline · P4.3 fine-tuning · P4.5 Ollama export | P4.4 evaluation (measured; below 0.90 target) | |
| **5 Integration** | | P5.1 intake (digital PDF only) · P5.2 context in pipeline · P5.3 review (tiers only) · P5.5 UI (one page) · P5.6 end-to-end golden set (written) | P5.4 explanations |
| **6 Evaluation + demo** | | | P6.1 metrics report · P6.2 demo script · P6.3 README + limitations |

Test assets already written and waiting for code: **90 rules cases**, **56 calculator cases** (each
with worked steps), **30 end-to-end claims**, **50 retrieval queries**, **30 blind-review claims**.

---

## 8. What the team can work on next

**In parallel now** (none of these touch what the model was trained on):

| Task | Notes |
|---|---|
| P2.3 Rules R01–R13, duplicates, low-confidence conversion | 90 golden cases; line flags must match the generator's rule mirror in `training/generate/codebook.py` |
| P2.4 Full calculator | 56 golden cases; extend `app/calculator/engine.py` |
| P2.1 Remaining loaders | NCCI, MUE and place-of-service tables into Postgres |
| P2.5 Workflow | Automatic rule outcomes with audit events |
| P5.1 Scanned-form OCR | `app/intake/layout.py` already defines the box coordinates |
| P5.3 Review actions | Accept / override, calculator re-run, finalization, accumulator update |
| P5.4 Explanations | Jinja2 templates built from the decision record |

**Model v2 work** (decided, not built): review the V1b findings (two sittings), merge
`v1-data-verification` into `main`, then build the v2 bundle from section 6, regenerate the
dataset and retrain once.

**Team decisions waiting** (to be recorded in `DECISIONS.md`):

1. How to close the accuracy gap (0.672 → 0.90), and which note styles to train on.
2. Derive each line's decision from its criterion answers in code (+0.027, no retraining). The
   derivation must include the NCCI-bypass case; re-measure the estimate with it.
3. Retry policy: one seeded retry at temperature 0.7, only for invalid answers.
4. Sign-offs: prompt `decision_v2`, max length 3,072, NCCI bypass modifiers.
5. Spot-checks: 3 coverage policies vs. their LCDs; 10 rules + 10 calculator golden cases; the
   20-record review packet; fill in the blind-review sheet before seeing model output.
6. The AMA CPT licence question (`SOURCES.md`).

Resolved since 2026-09-24: whether the vector index stays (D-RAG-1: exact lookup for decision
criteria from v2), and how to make NOT_APPLICABLE checkable (D-ESI-6, D-GEN-1).

**Housekeeping:** extract `ccipra-v323r0-f1.txt` into `data/raw/ncci-ptp/ccipra-v323r0-f1/` (fixes the
one failing test); record the base model's exact Hugging Face revision in the training log; rebuild
the end-to-end golden model answers for prompt v2.

### What must not change without a team decision and retraining

The model learned exactly these, so changing any of them breaks train/live parity: the contracts
(`app/domain/contracts.py`), prompt `decision_v2` and message layout, the retrieval setup (embedding
model, query text, code filter, top 5), the coverage policies and procedure scope, the label logic in
`training/generate/`, and the rule flags shown to the model.

---

## 9. Ground rules the project follows

- The AI **never** produces a dollar amount; only `app/calculator` does.
- Money is **integer cents**; percentages are **integer basis points** (20% = 2000).
- Rule failures are automatic; a failure on a low-confidence (e.g. badly scanned) field becomes
  **REJECT, never DENY**, so an OCR error cannot deny someone's claim.
- **Every** AI recommendation goes to a human.
- No codes, clinical criteria or reason-code mappings are invented: codes come from public CMS files;
  every criterion cites its source LCD. Plan values are fictional.
- No external model APIs; synthetic data only; public source files, generated data and model
  weights are never committed.
- Test expectations are written before the code and are never changed to make a test pass.

---

## 10. How to run it

```bash
uv sync
cp .env.example .env                       # set MODEL_NAME=claimsense-decision:v1 to use the
                                           # fine-tuned model (the default is base gemma4:e2b)
docker compose up -d --wait                # Postgres + Qdrant
uv run alembic upgrade head
# put the public source files in data/raw/ (team shared folder; see SOURCES.md)
uv run python -m training.generate.reference
uv run python -m app.db.seed
uv run hf download qdrant/bge-small-en-v1.5-onnx-q --cache-dir data/generated/models/fastembed
uv run python -m app.rag.knowledge
uv run pytest

uv run uvicorn app.api.main:app            # API on :8000
cd frontend-web && npm run dev            # web app on :5173 (or: make demo)
```

Ollama must be running with the model pulled or created. Known hiccups: quitting the Ollama app stops
evaluations (they resume); if Docker stops, database tests skip locally; large Hugging Face downloads
should be run in your own terminal.

---

## 11. Where to read more

| Document | What it covers |
|---|---|
| `INSTRUCTIONS.md` | The full specification: architecture, components, roadmap |
| `DECISIONS.md` | Decisions made since the spec; wins where they differ |
| `PROGRESS_LOG.md` | Detailed timeline, open items, lessons learned |
| `docs/results.md` | Model evaluation numbers |
| `docs/walking-skeleton.md` | The end-to-end skeleton and how to run it |
| `docs/fine-tuning.md` | Training on Kaggle and serving through Ollama |
| `docs/data-card.md` | The training dataset |
| `docs/training-readiness.md` | The pre-training gate |
| `SOURCES.md` | Public data sources and licences |
| Branch `v1-data-verification` | V1a/V1b checks (`scripts/verify/`), `data/curated/policy_sources.csv`, the v2 decisions in `DECISIONS.md`, and the progress log to 2026-09-28 |

---

## 12. Glossary

| Term | Meaning |
|---|---|
| CMS-1500 | The standard claim form for professional (doctor) services in the US |
| ICD-10-CM | Diagnosis codes |
| CPT / HCPCS | Procedure codes |
| NPI | National Provider Identifier (10 digits with a check digit) |
| LCD | Local Coverage Determination: Medicare's published coverage criteria for a service |
| NCCI | National Correct Coding Initiative: pairs of procedures that should not be billed together |
| MUE | Medically Unlikely Edit: maximum units of a service per day |
| CARC / RARC | Standard reason codes sent back to providers explaining an adjustment or denial |
| COB | Coordination of Benefits: when another insurer pays first |
| Accumulators | Running totals of deductible and out-of-pocket spend for the year |
| APPROVE / PEND / DENY | Pay it / needs more information / will not pay |
| REJECT | Returned to the provider because the claim data itself is wrong |
| SLM | Small language model (here, Gemma 4 E2B) |
| RAG / retrieval | Looking up the relevant policy criteria and giving them to the model |
| QLoRA | A memory-efficient way to fine-tune a model on a single GPU |
| GGUF / Ollama | A compact model file format / the local program that runs it |
| Macro-F1 | Accuracy measure that weighs APPROVE, PEND and DENY equally, so a model can't score well by favouring one |
