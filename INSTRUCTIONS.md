# ClaimSense — Implementation Instructions for Claude Code

**Version:** 1.0 · **Date:** 2026-09-21 · **Owner:** ClaimSense team (CBIT AI & DS, Batch 113)

This file is the single source of truth for **what** to build and **how**. It is a reference:
read the section that matches your current task before planning. Do not load or summarize the
whole file for every task.

If this file, `DECISIONS.md` and a request conflict, **stop and ask**. Never resolve a conflict
on your own.

---

## Contents

1. How to use this file
2. Project summary
3. Hard rules (never break these)
4. Scope: in and out
5. Architecture and processing flow
6. Tech stack (locked)
7. Repository layout
8. Component specifications
   - 8.1 Contracts
   - 8.2 Intake
   - 8.3 Rules engine
   - 8.4 Context assembly
   - 8.5 SLM decision
   - 8.6 Calculator
   - 8.7 Explainability
   - 8.8 Human decision review
   - 8.9 Audit and logging
   - 8.10 API
   - 8.11 Frontend
   - 8.12 Settings
9. Data specifications
10. Model specifications (Gemma 4)
11. Roadmap: phases, tasks, acceptance criteria
12. Working rules for Claude Code
13. Stop-and-ask triggers
14. Definition of done
15. Glossary

---

## 1. How to use this file

- `CLAUDE.md` (loaded automatically) holds the short list of hard rules. This file holds the details.
- Each task has an ID such as **P2.3** (Phase 2, task 3). A typical request is:
  *"Do task P2.3. Read §11 P2.3 and the sections it references, then show me your plan."*
- Read `DECISIONS.md` before planning. It records decisions made after this file was written
  and overrides this file where they differ.
- One task per session. Run `/clear` between tasks.

---

## 2. Project summary

ClaimSense processes **CMS-1500 professional health claims**. Deterministic rules check hard
requirements. A **fine-tuned Gemma 4 small language model** evaluates coverage and medical
necessity using plan data and retrieved coverage criteria, and recommends a decision per
service line. A **deterministic calculator** computes all amounts. Every SLM recommendation is
**reviewed by a human** before it becomes final, and every step is audited and explainable.

All data is **synthetic**. There is no real patient data (PHI) anywhere in the project.

---

## 3. Hard rules (never break these)

| # | Rule |
|---|---|
| H1 | **The SLM never produces a dollar amount.** All amounts come from `app/calculator`. |
| H2 | **All money is integer cents. All percentages are integer basis points** (20% = 2000). Never use `float` for money. |
| H3 | `app/rules` and `app/calculator` must **not** import `app/ml`, `app/rag` or any model library. Enforced by import-linter. |
| H4 | **Every SLM recommendation goes to human decision review.** Nothing the SLM outputs is final. |
| H5 | **Rule failures are handled automatically** (REJECT / DENY / PEND) with no human step. A failure caused by a field extracted below the confidence threshold becomes **REJECT, never DENY**. |
| H6 | **Never invent insurance, coding or clinical rules, codes, criteria or reason-code mappings.** They come only from files in `data/raw/`, `data/curated/`, the database, or `DECISIONS.md`. If something is missing, stop and ask. |
| H7 | **No external model APIs.** All inference runs locally through Ollama. No OpenAI, Anthropic, Google or other hosted model calls anywhere in application code. |
| H8 | **Synthetic data only.** Never add real patient, member or claim data. |
| H9 | **Never commit** `data/raw/`, `data/generated/`, `confidential/`, model weights (`*.gguf`, `*.safetensors`), `.env`, or any secret. |
| H10 | **Never copy AMA CPT descriptor text** into the repository or the knowledge base. Use the team-written short descriptions in `data/curated/procedure_descriptions.csv`. |
| H11 | **Contracts in `app/domain/contracts.py` are frozen.** Do not add, remove or rename fields. Propose changes and wait for approval. |
| H12 | **Golden test expected values are human-written.** Never change them to make a test pass. If you think one is wrong, stop and ask. |
| H13 | **Never push to `main`.** Work on a branch, open a pull request. |
| H14 | **No new dependencies** beyond §6 without approval. |
| H15 | **Explanations are built from recorded data**, never from free-form model text written after the decision. |
| H16 | **Plan facts** (deductibles, copays, limits, exclusions) come from the **database**. RAG is used **only** for coverage criteria and citations. |

---

## 4. Scope: in and out

**In scope**

- CMS-1500 professional claims, original claims only (claim frequency code `1`)
- Electronic intake: claim JSON in our 837P-shaped format, and digital PDFs rendered by our generator
- Paper intake: scanned or image CMS-1500 forms produced by our generator, read with OCR
- Rules engine, calculator, fine-tuned SLM decision, RAG over coverage criteria, explainability,
  human decision review, audit trail, evaluation scripts, React web UI (D-UI-1)

**Out of scope** (do not build unless `DECISIONS.md` adds it)

- Any large language model or hosted model API
- Pharmacy claims (NCPDP), UB-04 institutional claims, dental claims
- Parsing live X12 EDI files (837/835/270/271)
- Corrected or void claims (frequency codes 7 and 8)
- Member Q&A chatbot, operations copilot, fraud/SIU module, denial-classifier model
- Cloud deployment, multi-tenant configuration, production authentication
- Async job queues (Redis/RQ): the pipeline is synchronous; this is a stretch item only
- extract-lora (fine-tuned extraction): stretch item only, if OCR misses its target

---

## 5. Architecture and processing flow

```text
Claim received
  ├─ Electronic (JSON or digital PDF) → direct parse
  └─ Paper / scanned                  → OCR per form box
        │
  IntakeClaim + confidence per field
        │
  RULES ENGINE ── claim-level failure ──▶ automatic REJECT / DENY / PEND (final, audited)
        │
      PASS (with flags; some lines may be denied by line-level rules)
        │
  CONTEXT ASSEMBLY: plan facts from DB + coverage criteria from RAG
        │
  SLM (fine-tuned Gemma 4): per-line APPROVE / PEND / DENY, criteria, benefit category, complexity
        │
  OUTPUT VALIDATION (deterministic)
        │
  CALCULATOR: exact amounts for approved lines
        │
  EXPLAINABILITY RECORD
        │
  HUMAN DECISION REVIEW (tier: QUICK / STANDARD / FULL)
        │
  FINAL DECISION + accumulator update + audit
```

### Claim status values

| Status | Meaning |
|---|---|
| `RECEIVED` | Intake complete |
| `REJECTED` | Rule failure: data problem; returned to provider (final) |
| `DENIED_BY_RULE` | Rule failure: hard requirement not met (final) |
| `PENDED_BY_RULE` | Rule failure: information not yet available (e.g. provider enrollment pending) |
| `AWAITING_REVIEW` | SLM recommendation and calculation ready for a human |
| `FINAL_APPROVED` | Reviewer confirmed; all lines approved |
| `FINAL_PARTIAL` | Reviewer confirmed; some lines approved, some denied |
| `FINAL_DENIED` | Reviewer confirmed; all lines denied |
| `FINAL_PENDED` | Reviewer confirmed that information is missing |

Allowed transitions are defined as an explicit table in `app/workflow/states.py`. Any other
transition raises an error. No state-machine library is used.

---

## 6. Tech stack (locked)

| Area | Allowed |
|---|---|
| Language / packaging | Python 3.11, `uv` |
| API | `fastapi`, `uvicorn` |
| Validation / settings | `pydantic` v2, `pydantic-settings` |
| Database | PostgreSQL, `sqlalchemy` 2.0, `alembic`, `psycopg` (v3) |
| Vector store | Qdrant (Docker), `qdrant-client`, `fastembed` |
| Model serving | Ollama (native install), `ollama` Python client |
| Intake | `pymupdf`, `pytesseract` (+ Tesseract binary), `pillow` |
| Templates | `jinja2` |
| HTTP client (frontend → API) | the browser's `fetch` through the Vite dev proxy |
| Frontend | React web app in `frontend-web/` (D-UI-1, D-UI-2): Node.js + npm, Vite, React, TypeScript, React Router, Tailwind CSS, TanStack Query, shadcn/ui components (Radix), Motion for animation, fonts bundled with @fontsource; light theme only. Tests: Vitest, React Testing Library, Playwright; lint: ESLint. Streamlit was removed (D-UI-2) |
| Logging | `structlog` |
| Synthetic data | `faker`, `reportlab`, `pyyaml` |
| Evaluation | `pandas`, `scikit-learn` |
| Dev tools | `pytest`, `pytest-cov`, `ruff`, `import-linter`, `pre-commit` |
| Training (training machine only, separate dependency group `train`) | `unsloth` (NVIDIA) or `mlx-lm` (Apple Silicon), `transformers`, `peft`, `trl`, `datasets`, `bitsandbytes` (NVIDIA only) |
| Model export | `llama.cpp` tools or Unsloth's GGUF export |

Anything else needs approval (H14).

---

## 7. Repository layout

```text
claimsense/
├── CLAUDE.md                 # short hard rules (auto-loaded)
├── INSTRUCTIONS.md           # this file
├── DECISIONS.md              # decision log (overrides this file where different)
├── SOURCES.md                # public data sources, versions, licenses
├── SETUP.md                  # human setup steps
├── pyproject.toml
├── docker-compose.yml        # postgres, qdrant
├── .importlinter
├── app/
│   ├── domain/contracts.py   # frozen Pydantic contracts
│   ├── intake/               # parsing, OCR, confidence
│   ├── rules/                # rules engine (no ML imports)
│   ├── calculator/           # money (no ML imports)
│   ├── context/              # plan facts from DB + RAG retrieval call
│   ├── ml/                   # Ollama client, prompts, output validation
│   ├── rag/                  # ingestion, retrieval
│   ├── explain/              # decision record → explanation (Jinja2)
│   ├── review/               # review tiers, review actions
│   ├── workflow/             # pipeline orchestration, states
│   ├── audit/                # append-only audit events
│   ├── db/                   # SQLAlchemy models, session, seed loaders
│   ├── api/                  # FastAPI routes
│   └── core/                 # settings, logging
├── migrations/               # Alembic
├── frontend-web/             # React web app (Vite, TypeScript; D-UI-1)
├── training/
│   ├── generate/             # synthetic data generators
│   ├── finetune/             # QLoRA scripts
│   └── evaluate/             # evaluation scripts
├── scripts/                  # one-off utilities (seeding, metrics report)
├── tests/
│   ├── unit/
│   ├── golden/rules/         # hand-written JSON cases
│   ├── golden/calculator/    # hand-written JSON cases
│   └── e2e/
├── data/
│   ├── raw/                  # public downloads (gitignored)
│   ├── curated/              # team-written, committed: plans, policies, descriptions
│   └── generated/            # regenerable outputs (gitignored)
├── docs/
└── confidential/             # local only (gitignored)
```

### Import-linter contracts (`.importlinter`)

- `app.rules`, `app.calculator` → forbidden to import `app.ml`, `app.rag`, `ollama`, `qdrant_client`, `fastembed`
- `app.domain` → forbidden to import any other `app.*` package
- `frontend` → forbidden to import `app.*` (it calls the API over HTTP only)

---

## 8. Component specifications

### 8.1 Contracts (`app/domain/contracts.py`)

Frozen after task P1.4. Minimum content:

| Model | Key fields |
|---|---|
| `ServiceLine` | line_no, date_of_service, place_of_service, procedure_code, modifiers, diagnosis_pointers, units, charge_cents, rendering_npi |
| `IntakeClaim` | claim_id, member_id, patient (name, dob, sex, address), subscriber_is_patient, billing_npi, billing_tin, referring_npi, prior_auth_number, diagnoses (1–12), service_lines (≥1), clinical_notes, received_date, frequency_code, other_coverage (optional: primary payer paid amounts per line) |
| `FieldConfidence` | field path → confidence 0–1 |
| `IntakeResult` | claim, field_confidences, source_format (JSON / DIGITAL_PDF / SCANNED) |
| `RuleResult` | rule_id, passed, outcome, reason_code, detail, fields_used |
| `RulesOutcome` | claim_outcome (REJECT / DENY / PEND / PASS), rule_results, line_outcomes, flags |
| `CriterionResult` | criterion_id, met, evidence |
| `SLMLine` | line_no, decision (APPROVE / PEND / DENY), benefit_category, criteria, reasons, missing_information |
| `SLMOutput` | lines, complexity (LOW / MEDIUM / HIGH) |
| `LineAmounts` | line_no, billed, allowed, contractual_adjustment, deductible, copay, coinsurance, cob_primary_paid, plan_pays, member_pays, balance_bill_exposure (all cents) |
| `CostBreakdown` | lines, totals |
| `DecisionRecord` | claim_id, status, rules_outcome, context_refs, slm_output, claim_decision (derived), amounts, review_tier, versions, timestamps |
| `ReviewAction` | claim_id, reviewer_id, action (ACCEPT / OVERRIDE), line_overrides, reason, timestamp |
| `LineOverride` | line_no, decision (APPROVE / PEND / DENY), reason (required, not blank), benefit_category (optional; APPROVE only, one of the line's candidate categories; D-REV-4) |

The **claim-level decision is derived by code** from line decisions (§8.5), never produced by the SLM.

### 8.2 Intake (`app/intake/`)

| Source | Method | Confidence |
|---|---|---|
| JSON | Validate directly against `IntakeClaim` | 1.0 for every field |
| Digital PDF (our renderer) | PyMuPDF text extraction from known box coordinates | 1.0 if parsed and validated; lower if a field fails its format check |
| Scanned / image | Render page to image (PyMuPDF), crop each box by coordinates, `pytesseract.image_to_data` | Field confidence = lowest word confidence ÷ 100; set to 0 if the value fails its format validator |

- Box coordinates are defined once in `app/intake/layout.py` and match our synthetic renderer
  (§9.4). They are **not** valid for official printed CMS-1500 forms; document this limitation.
- Threshold: `EXTRACTION_CONFIDENCE_MIN` (default 0.85).
- Low-confidence fields do **not** stop a claim by themselves. They are recorded, used by rule
  H5 (if a rule fails on them → REJECT), and highlighted in decision review.

### 8.3 Rules engine (`app/rules/`)

Pure functions over `IntakeResult` + reference data from the DB. Deterministic; no randomness,
no network calls other than the database.

**Evaluation order**

1. **Group A (data integrity)**: R01–R04. If any fails → claim outcome **REJECT**; stop.
2. **Group B (hard requirements)**: R05–R10. Evaluate **all**, record every failure.
   Outcome precedence: DENY over PEND. Any failure → claim stops with that outcome.
3. **Group C (line level)**: R11–R13, then rules v2 R14–R20 (P2.3b; D-RULE-2 to D-RULE-7). Every
   rule runs on every line; a line's reason codes and flags are listed in rule order and the first
   reason is the primary one. A failing line is denied; the claim continues with the remaining
   lines. If every line is denied → claim outcome DENY. A flag never denies: a rule denies only
   when the LCD or article is explicit and the check needs nothing beyond the claim; a limit
   worded "usually" or with a documented exception gives a flag for the model and the reviewer.
4. **H5 conversion**: if a failing rule's `fields_used` includes a field below the confidence
   threshold → outcome becomes **REJECT** with reason `RJ_LOW_CONFIDENCE_FIELD`.

| ID | Rule | Failure outcome | Internal reason code |
|---|---|---|---|
| R01 | Required fields present | REJECT | `RJ_MISSING_FIELD` |
| R02 | Codes valid: ICD-10-CM for the date-of-service fiscal year, procedure code in code table, place-of-service code, modifier format | REJECT | `RJ_INVALID_CODE` |
| R03 | NPI check digits valid (billing, rendering, referring) | REJECT | `RJ_INVALID_NPI` |
| R04 | Member ID found | REJECT | `RJ_MEMBER_NOT_FOUND` |
| R05 | Member eligible on every date of service (coverage start/end) | DENY | `DN_NOT_ELIGIBLE` |
| R06 | Provider enrolled (not found → REJECT; enrollment pending → PEND) | REJECT / PEND | `RJ_PROVIDER_NOT_FOUND` / `PD_PROVIDER_ENROLLMENT` |
| R07 | Timely filing: received date − last date of service ≤ plan window (in-network vs out-of-network window from plan config) | DENY | `DN_LATE_FILING` |
| R08 | Network: out-of-network and plan does not cover out-of-network → DENY; covered → PASS with flag `OON` | DENY | `DN_OUT_OF_NETWORK` |
| R09 | Referral: plan requires referral for this provider type and no referring NPI | DENY | `DN_MISSING_REFERRAL` |
| R10 | Prior authorization: code requires auth per plan benefits, and no matching auth (member, provider, code, date range) | DENY | `DN_NO_AUTH` |
| R11 | NCCI procedure-to-procedure pair on the same claim: if the pair allows a bypass (modifier indicator 1) and an NCCI PTP-associated modifier is reported where the 2026 NCCI Policy Manual places it (D-RULE-8, `data/curated/ncci_ptp_modifiers.csv`: 59 and X modifiers not on an E&M line; 24, 25, 57 on an E&M paired with a procedure, 25 with a 000/010/XXX global period, 57 with 090; 58, 78, 79 on a procedure; 27, 91 on either line; anatomic modifiers on both lines for different sites) → PASS with flag `NCCI_BYPASS` (the model and the reviewer check the documentation); otherwise deny the column-2 line | Line DENY | `DN_NCCI_BUNDLED` |
| R12 | Units exceed the medically unlikely edit limit | Line DENY | `DN_MUE_EXCEEDED` |
| R13 | Procedure code on the plan's fixed exclusion list | Line DENY | `DN_EXCLUDED` |
| R14 | ESI line with another block on the same date: a different ESI code or a facet joint injection (add-on level codes, radiofrequency denervation and the same code on another line are not blocks; a facet injection for a facet synovial cyst is the LCD's exception); the denied ESI's own add-on lines go with it (D-RULE-7) | Line DENY | `DN_MULTIPLE_BLOCKS` |
| R15 | The line's own diagnoses (its pointers) meet none of its code's billing-article alternatives (D-DX-1, D-RULE-4); codes without an article are not checked | Line DENY | `DN_DX_NOT_SUPPORTED` |
| R16 | Home sleep test line with a parasomnia diagnosis (G47.50–G47.59) among its own | Line DENY | `DN_HOME_TEST_PARASOMNIA` |
| R17 | Nerve conduction line with no needle EMG line anywhere on the claim → PASS with flag `NCS_WITHOUT_EMG` | Flag | — |
| R18 | Transforaminal ESI levels per date above 2 on a side deny the add-on lines on that side (an RT or LT line counts on its side, modifier 50 or no side modifier on both; each unit of an add-on level code is one level, the primary code the first); an interlaminar or caudal ESI with modifier 50 | Line DENY | `DN_ESI_LEVELS` |
| R19 | Third-level facet code (64492, 64495) → DENY; facet codes of both spinal regions on one date → PASS with flag `FACET_TWO_REGIONS` | Line DENY / Flag | `DN_FACET_LEVELS` |
| R20 | More than 8 hours from the testing codes on the claim (96130, 96131 one hour per unit; 96136 30 minutes) → PASS with flag `EXTENDED_TESTING` | Flag | — |

- **Conditional exclusions** (e.g. cosmetic vs. reconstructive, depending on diagnosis) are **not**
  rules. They belong to the SLM via coverage criteria.
- Code roles and diagnosis sets for R14–R20 are curated (`data/curated/rule_code_roles.csv`,
  `rule_diagnosis_sets.csv`, R15's columns in `diagnosis_support.csv`), each row citing its source
  in `data/raw/`; the billing articles' covered codes are the `article_icd10_covered` table.
- **Duplicate claims** (same member, provider, date of service, procedure code as an existing
  claim) → REJECT `RJ_DUPLICATE`.
- **External reason codes (CARC/RARC):** map each internal reason code to a code from the official
  list in `data/raw/`, stored in `data/curated/reason_code_map.csv`. The team fills this file.
  **Never guess a CARC number** (H6).
- The rules version is a constant `RULES_VERSION` in `app/rules/__init__.py`, bumped on every change.

### 8.4 Context assembly (`app/context/`)

For a claim that passed the rules:

1. From the database: plan type, the benefit row for each line's candidate categories, cost-share
   rules, visit limits and usage so far, exclusions list, flags from the rules engine.
2. From RAG (§9.3): **every** coverage criterion for the line's procedure code, filtered by plan
   ID (or `ALL`), effective date ≤ date of service and the criterion's own codes, with no top-k cap
   (D-RAG-1, D-RAG-2). Policy set v2 (`POLICY_SET`, the default) uses an exact lookup by code;
   policy set v1, kept only to reproduce model v1, ranks the covering policy's criteria by
   similarity and takes the top 5 (`RAG_TOP_K`).
3. Output: a `ContextPackage` with every item's ID and source, stored in the decision record.

### 8.5 SLM decision (`app/ml/`)

**Prompt:** versioned text files in `app/ml/prompts/` (e.g. `decision_v1.txt`), with sections:
`CLAIM`, `RULES_RESULT`, `PLAN_BENEFITS`, `COVERAGE_CRITERIA` (each criterion with its ID).
The prompt version is recorded in every decision record.

**Call:** Ollama, model from `MODEL_NAME`, JSON schema from `SLMOutput` passed as the structured
output format, temperature 0, fixed seed, thinking disabled.

**Deterministic validation after the call:**

| Check | On failure |
|---|---|
| Parses as `SLMOutput` | All lines → PEND, reason `MODEL_OUTPUT_INVALID`, tier FULL |
| Every rules-passed line appears exactly once | Same |
| Every `criterion_id` is one of the retrieved IDs | Same |
| DENY or PEND lines include at least one reason; PEND includes missing information | Same |

No automatic retries.

**Claim decision (derived by code):**

| Line decisions | Claim decision |
|---|---|
| Any PEND | PEND |
| All DENY | DENY |
| All APPROVE | APPROVE |
| Mix of APPROVE and DENY | PARTIAL |

Line denials from rules R11–R13 are included when deriving the claim decision.

**Review tier (computed by code, `app/review/tiers.py`):**

| Condition | Tier |
|---|---|
| Any line DENY by the SLM, or complexity HIGH, or output invalid | FULL |
| Any PEND, or complexity MEDIUM, or total allowed ≥ `REVIEW_HIGH_DOLLAR_CENTS`, or any low-confidence field | STANDARD |
| Otherwise (all APPROVE, complexity LOW, below threshold) | QUICK |

A model confidence score is **not** used yet. Adding one is an open decision for Phase 4.

### 8.6 Calculator (`app/calculator/`)

Pure functions. Input: approved lines, plan, benefit rows, fee schedule, accumulators, COB data.
Use `decimal.Decimal` for intermediate percentage math, `ROUND_HALF_UP` to whole cents, then `int`.

Per approved line, in service-line order:

1. **Allowed amount**: in-network → `min(billed, fee_schedule.inn_allowed_cents)`;
   out-of-network → `min(billed, fee_schedule.oon_allowed_cents)`.
2. **Contractual adjustment** (in-network) = billed − allowed. **Balance-bill exposure**
   (out-of-network) = billed − allowed (reported, not paid).
3. **Member cost share** by the benefit's `cost_share_rule`:
   - `COPAY`: copay = min(copay_cents, allowed); deductible does not apply.
   - `DEDUCTIBLE_COINSURANCE`: deductible applied = min(remaining deductible, allowed);
     coinsurance = (allowed − deductible applied) × coinsurance_bps ÷ 10000.
   - Out-of-network lines use the plan's out-of-network deductible and coinsurance.
4. **Out-of-pocket maximum**: member cost share capped at the remaining out-of-pocket amount
   (separate in-network and out-of-network maximums).
5. **Plan pays** = allowed − member cost share.
6. **COB (our plan secondary)**: secondary pays min(normal plan payment, allowed − primary paid),
   not below 0; member pays the remainder, not below 0. *(Team default: traditional COB. See
   `DECISIONS.md`.)*
7. Update **working** accumulators for later lines on the same claim.

- Denied and pended lines: plan pays 0; no cost share computed.
- **Stored accumulators change only when a claim is finalized by a reviewer**, never at
  recommendation time.
- The calculator never reads SLM text. It uses only line decisions and benefit categories.

### 8.7 Explainability (`app/explain/`)

Rendered with Jinja2 from the `DecisionRecord` only (H15). Sections:

1. Summary: claim decision, review tier, status
2. Rule checks: every rule, pass/fail, detail
3. Per line: decision, benefit category, each criterion met or not met with evidence and the
   cited policy ID and title
4. Amounts: billed, allowed, adjustments, deductible, copay, coinsurance, plan pays, member pays,
   per line and totals
5. Review: reviewer, action, override reasons
6. Versions: rules, model, prompt, policies

### 8.8 Human decision review (`app/review/`)

- Queue contains every claim in `AWAITING_REVIEW`, sortable by tier.
- Actions: **ACCEPT**, or **OVERRIDE** individual line decisions with a **required** reason.
- Reviewers **cannot enter amounts**. After an override, the calculator re-runs on the new line
  decisions.
- On finalization: status → `FINAL_*`, accumulators updated for approved lines, audit event written.
- Rule-failure claims (`REJECTED`, `DENIED_BY_RULE`, `PENDED_BY_RULE`) are **not** in this queue.
  They are listed read-only in the UI for visibility.
- An override changes a line's decision, its benefit category, or both (D-REV-4); lines denied by
  R11–R13 cannot be overridden (D-REV-2). Finalization recomputes the amounts against the stored
  accumulators under a claim-then-member lock (D-REV-3) and counts the approved lines of every
  final claim, `FINAL_PENDED` included (D-REV-7), and one visit per date of service of approved
  lines in a visit-limited category (D-REV-8); a calculation that fails refuses the review
  (D-REV-5).

### 8.9 Audit and logging (`app/audit/`, `app/core/logging.py`)

- Table `audit_events`: id, claim_id, event_type, actor (system or reviewer ID), payload (JSONB),
  rules_version, model_name, prompt_version, policy_versions, created_at. **Insert only**; no
  update or delete code paths.
- Event types: `INTAKE_COMPLETED`, `RULES_EVALUATED`, `CONTEXT_ASSEMBLED`, `SLM_RECOMMENDED`,
  `OUTPUT_INVALID`, `CALCULATED`, `CALCULATION_FAILED`, `EXPLANATION_BUILT`, `REVIEW_OPENED`,
  `REVIEW_ACCEPTED`, `REVIEW_OVERRIDDEN`, `FINALIZED`, `AUTO_OUTCOME`.
- `CALCULATION_FAILED` (P2.4) is written instead of `CALCULATED` when the calculator cannot run
  (for example no fee for an approved line, or out-of-network care on a plan without out-of-network
  terms); the claim then waits for FULL review without amounts.
- `REVIEW_OPENED` (P5.3, migration 0004) is written when a reviewer opens a claim awaiting review,
  with the reviewer as actor. `REVIEW_ACCEPTED` / `REVIEW_OVERRIDDEN` carry the reviewer, the
  action time, the overall reason, each overridden line's reason with its decision and category
  before and after, and the review time from the acting reviewer's latest `REVIEW_OPENED` (D-REV-6).
  `FINALIZED` carries the final status and totals, the accumulators and visit usage before and
  after, whether the amounts changed since review, and the calculator version. Override reasons
  are free text and stay in the audit trail; logs carry IDs only.
- Logs (structlog, JSON): IDs, route, duration, versions. **Never** names, addresses, dates of
  birth or clinical notes.

### 8.10 API (`app/api/`)

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Liveness, DB, Qdrant and Ollama reachability |
| POST | `/v1/claims/intake` | JSON body or file upload → `IntakeResult`; status RECEIVED |
| POST | `/v1/claims/{id}/process` | Rules → context → SLM → calculator → explanation; returns `DecisionRecord` |
| GET | `/v1/claims/{id}` | Decision record + rendered explanation |
| GET | `/v1/claims/{id}/audit` | Audit events in order |
| GET | `/v1/review/queue` | Claims awaiting review, optional `tier` filter and `sort` (`tier` or `processed`); reviewer role |
| POST | `/v1/claims/{id}/review/open` | `{reviewer_id}` → records `REVIEW_OPENED`, the start of the review time (D-REV-6); 409 unless `AWAITING_REVIEW`; reviewer role |
| POST | `/v1/claims/{id}/review` | `ReviewAction` → finalized `DecisionRecord`; 409 if already final or busy, 422 if refused; reviewer role |
| GET | `/v1/plans/{plan_id}` | Plan configuration |

Authentication: a simple role header (`provider`, `reviewer`, `admin`) checked by a dependency.
Prototype only; documented as such.

### 8.11 Frontend (`frontend-web/`, React; D-UI-1, D-UI-2)

Vite + React + TypeScript, React Router, Tailwind CSS, TanStack Query; components from shadcn/ui
(Radix), Motion as the only animation library, fonts bundled with @fontsource; light theme only.
The web app talks only to the FastAPI API, through the Vite dev proxy; it never imports app code or
touches the database. `make demo` starts the database containers, the API and the web app. The
earlier Streamlit app was removed (D-UI-2).

**Layout.** Top bar: app name, role switcher (Provider / Reviewer / Admin, sent as `X-Role`) and the
reviewer ID (remembered in the browser). Left navigation: Submit claim, Review queue, Claims, Rule
outcomes, Metrics.

| Page | Contents |
|---|---|
| Submit claim | Upload JSON, PDF or image; fields with confidence, low confidence highlighted; Process button; then go to the claim |
| Review queue | Tier, decision, total allowed, age; filter by tier |
| Review claim | Fields (low confidence highlighted), rule checks, each line's model decision with criteria, evidence, citations and amounts. Per line: a decision select, a required reason, a category select only when needed (D-REV-4); rule-denied lines read-only with their reason (D-REV-2). One "Accept all" and one "Submit changes" button, with a confirmation before finalizing. After submitting: final status and amounts, and the changed-amounts notice when it applies |
| Claim detail | Status, line decisions, amounts, the explanation (§8.7) and the audit trail as a timeline |
| Rule outcomes | Read-only list of REJECTED / DENIED_BY_RULE / PENDED_BY_RULE claims with reasons |
| Metrics | Model v1 vs v2 evaluation table and the targets; OCR field accuracy |

**Design.** White background, neutral greys, one accent colour, system font, 15–16 px base text,
generous spacing. CSS-only transitions of 150–200 ms that respect `prefers-reduced-motion`. Status
chips show text plus a muted colour: Approved (green), Needs information / Pended (amber), Denied
(red), Rejected (grey). Plain-language labels with short hints (e.g. "PEND: needs more
information"). One primary action per screen; loading skeletons, empty states, API errors in plain
words. Keyboard navigation, visible focus rings, labelled inputs, AA contrast.

**Tests.** Vitest + React Testing Library for the review form's validation and the status chips;
one local Playwright smoke test (submit JSON → process → open from the queue → accept → claim detail
shows the explanation and the audit trail); a CI job: `npm ci`, lint, typecheck, unit tests, build.

### 8.12 Settings (`app/core/settings.py`, from environment)

| Name | Default |
|---|---|
| `DATABASE_URL` | `postgresql+psycopg://claimsense:claimsense@localhost:5432/claimsense` |
| `QDRANT_URL` | `http://localhost:6333` |
| `OLLAMA_URL` | `http://localhost:11434` |
| `MODEL_NAME` | `gemma4:e2b` (replaced by the fine-tuned model name in Phase 4) |
| `EMBEDDING_MODEL` | fastembed default small English model (record the exact name in `DECISIONS.md`) |
| `POLICY_SET` | `v2` (policy set of the pipeline: `v1` or `v2`; D-POL-2) |
| `RAG_TOP_K` | 5 (policy set v1 only; v2 has no cap, D-RAG-1) |
| `EXTRACTION_CONFIDENCE_MIN` | 0.85 |
| `REVIEW_HIGH_DOLLAR_CENTS` | 100000 |

`.env.example` is committed; `.env` is not.

---

## 9. Data specifications

### 9.1 Public sources (`data/raw/`, downloaded by humans, listed in `SOURCES.md`)

NUCC 1500 manual and 837P crosswalk · ICD-10-CM codes and guidelines (one fiscal year matching the
synthetic dates of service) · HCPCS Level II · NCCI PTP and MUE files · Medicare Coverage Database
(NCD/LCD/Article CSVs) · CMS Physician Fee Schedule · Place of Service codes · CARC/RARC lists ·
CMS SBC template, sample and Uniform Glossary.

Loaders in `app/db/` read these into code tables. **Never** download files from code without a
human confirming the URL (H6).

### 9.2 Curated data (`data/curated/`, committed, written by the team)

| File | Contents |
|---|---|
| `plans.yaml` | ~5 plans (PPO, HMO, EPO): filing windows, OON coverage, referral rules, deductibles, copays, coinsurance (bps), OOP maxima |
| `benefits.yaml` | Plan × benefit category → covered, auth required, visit limit, cost-share rule |
| `exclusions.yaml` | Fixed exclusion code lists per plan |
| `procedure_descriptions.csv` | Team-written short descriptions for every procedure code used |
| `reason_code_map.csv` | Internal reason code → CARC/RARC (from the official list) |
| `coverage_policies/v1/POL-*.md`, `coverage_policies/v2/POL-*.md` | 15–25 coverage policies per policy set (format below; D-POL-2) |

**Coverage policy format.** Every criterion has a stable ID and at least one source reference:

```markdown
---
policy_id: POL-IMG-004
title: Lumbar spine MRI
procedure_codes: ["72148"]
plan_ids: ["ALL"]
effective_date: 2025-01-01
sources: ["<NCD/LCD/Article ID and retrieval date>"]
---
## POL-IMG-004.c1
<criterion text written by the team>

## POL-IMG-004.c2
<criterion text>
```

Policy set v2 adds to the front matter `policy_set: v2` and `replaces` (retired v1 ID → its new
IDs), and to each criterion a `Type:` line (requirement, exclusion or conditional), an optional
`Applies to:` line (the codes it is shown on), an optional `Group: indication` line and a `Source:`
line that cites LCD block IDs or manual sections. A changed meaning gets a new ID; numbers are
never reused (D-POL-1, D-POL-3).

Claude Code may help **format** policies and check them against their sources. It must **not
write clinical criteria** that are not in a cited source (H6).

### 9.3 Knowledge base (Qdrant)

| Collection | Source | Chunking |
|---|---|---|
| `coverage_policies_v1` | `data/curated/coverage_policies/v1/` (frozen for model v1) | One chunk per criterion ID |
| `coverage_policies_v2` | `data/curated/coverage_policies/v2/` | One chunk per criterion ID |
| `plan_documents` | SBCs generated from `plans.yaml` + `benefits.yaml` | One chunk per SBC section |
| `code_reference` | ICD-10 descriptions for codes used + relevant guideline sections | One chunk per code / section |
| `carc_rarc` | Codes in `reason_code_map.csv` with official descriptions | One chunk per code |

Payload metadata on every point: collection, policy_id, criterion_id, plan_ids, effective_date,
source, license; in `coverage_policies_v2` also the criterion's type, its own procedure codes and
its group (D-POL-3). Only the coverage policy collection of the pipeline's policy set feeds the SLM
prompt. **v2 retrieval is an exact lookup by code**: every criterion that matches the line's code,
plan and date, with no cap and in policy-file order (D-RAG-2). **Semantic search stays in the v1
collection** (to reproduce model v1) and in the explanation collections, which support
explanations.

### 9.4 Synthetic generators (`training/generate/`)

**Generate from ground truth outward:** scenario and label first, then the claim, then rendered
forms. Every record stores `generator_version`, `seed`, `scenario_type`, `policy_id`,
`template_id`.

| Generator | Output | Size |
|---|---|---|
| Reference data | members (~500, some terminated), providers (~100, valid NPIs, some unenrolled/OON), authorizations (~150, some expired or wrong code), other coverage (~50), accumulators | Seeded into Postgres |
| Claims | `IntakeClaim` JSON with scenario tag and expected outcomes | As needed by datasets below |
| Form renderer | Digital PDF + scanned-style image with noise (blur, skew, typos, missing boxes) from one layout defined in `app/intake/layout.py` | Per claim |
| Decision dataset | JSONL chat records: system + user (context package) + assistant (target `SLMOutput`) | 1,500–3,000 train / 300 validation / 300 test |

**Decision dataset scenarios (labels from coverage policies and code pairs in public sources):**
APPROVE (criteria met) · DENY not medically necessary (diagnosis does not support procedure) ·
DENY conditional exclusion · PEND missing documentation · PEND `NCCI_BYPASS` with insufficient
documentation · multi-line mixed outcomes · out-of-network flag · LOW/MEDIUM/HIGH complexity.

**Leakage and quality checks (script must pass before any training):**

- Claim fields and clinical notes contain none of: approve, approved, deny, denied, reject,
  pend, pended, "not covered", "medically necessary", "not medically necessary"
- Every target validates as `SLMOutput`; every criterion ID exists
- Test split: ~100 examples use **policies never seen in training**; different note templates
- Class distribution report written to the data card

### 9.5 Test sets (`tests/golden/`, human-written)

| Set | Size | Rule |
|---|---|---|
| Rules golden cases | ~80 (every rule and outcome, including H5 conversion) | Expected values written by humans (H12) |
| Calculator golden cases | ~50, amounts computed by hand | Must pass 100% |
| End-to-end claims | ~30 | One of every outcome |
| RAG evaluation | 40–50 queries → expected criterion IDs, including "no relevant policy" cases | Recall@3 |
| Blind review subset | ~30 claims | Reviewer decides before seeing the SLM output |

---

## 10. Model specifications (Gemma 4)

| Item | Value |
|---|---|
| Default base model | Gemma 4 E2B instruction-tuned (`google/gemma-4-E2B-it` / `unsloth/gemma-4-E2B-it`; Ollama `gemma4:e2b`) |
| Upgrade | Gemma 4 E4B only if E2B misses targets and the training machine fits it; record in `DECISIONS.md` |
| Method | QLoRA, 4-bit base |
| Starting config | r=16, alpha 16–32, dropout 0, attention + MLP projections, vision/audio layers frozen, max length 2048, batch 1–2, gradient accumulation 8, lr 2e-4, 1–3 epochs with early stopping on validation |
| Chat template | The tokenizer's Gemma 4 chat template (Unsloth: `get_chat_template(tokenizer, chat_template="gemma-4")`). If it has no system role, put instructions at the start of the first user message. |
| Training loss | Responses only |
| Precision | bf16 where supported |
| Thinking | Disabled in training data and inference |
| Known issue | Use the latest `unsloth` / `unsloth_zoo` (fixes garbage output on E2B/E4B when caching is disabled by gradient checkpointing) |
| Export | Merge adapter → GGUF (Q4_K_M) → Ollama `Modelfile` → model name `claimsense-decision:v<N>` |
| Inference | Temperature 0, fixed seed, JSON schema format, Pydantic validation |

**Evaluation (`training/evaluate/`)**: accuracy, macro-F1, per-class precision/recall, confusion
matrix, valid-output rate, criterion-level accuracy, latency. Comparisons: base E2B vs. E4B
(zero-shot), base vs. fine-tuned, fine-tuned with RAG vs. without RAG. Results saved as JSON in
`data/generated/eval/` and summarized in `docs/results.md`.

---

## 11. Roadmap: phases, tasks, acceptance criteria

Week numbers are targets. Each task = one GitHub issue = one branch = one pull request.

### Phase 0 — Setup (humans, `SETUP.md`)
Accounts, tools, repository, model pull, verification. Not a Claude Code phase.

### Phase 1 — Foundations (Week 1)

| Task | Work | Acceptance |
|---|---|---|
| P1.1 | `uv` project (Python 3.11), dependencies from §6 (no `train` group yet), ruff, pytest, import-linter (`.importlinter` per §7), pre-commit, GitHub Actions running lint + tests + import checks | `uv run pytest`, `uv run ruff check .`, `uv run lint-imports` pass locally and in CI |
| P1.2 | `docker-compose.yml` (Postgres, Qdrant), `.env.example`, settings (§8.12), structlog setup, `/health` endpoint | `docker compose up -d` then `/health` reports DB, Qdrant, Ollama status |
| P1.3 | SQLAlchemy models + first Alembic migration: plans, benefits, fee_schedule, members, providers, authorizations, other_coverage, accumulators, code tables, claims, decision_records, audit_events | `alembic upgrade head` on a fresh DB succeeds; downgrade works |
| P1.4 | Draft `app/domain/contracts.py` per §8.1 with validators (NPI check digit, code formats, cents ≥ 0). **Stop for team review; contracts are frozen after approval.** | Team approval recorded in `DECISIONS.md` |
| P1.5 | **Walking skeleton**: JSON claim → R05 only → base `gemma4:e2b` call with the `SLMOutput` schema → COPAY-only calculator → decision record → audit events → a page showing the record (Streamlit then; the React app since D-UI-2) | One sample claim runs end to end; e2e test passes |

### Phase 2 — Rules engine and calculator (Week 2)

| Task | Work | Acceptance |
|---|---|---|
| P2.1 | Loaders for curated YAML/CSV and public code files into the DB; seed script | Seed runs on a fresh DB; counts reported |
| P2.2 | Reference-data generator (§9.4) | Deterministic with a seed; NPIs valid; distribution report |
| P2.3 | Rules R01–R13, duplicate check, H5 conversion, `RULES_VERSION` | 100% of human-written rules golden cases pass |
| P2.4 | Calculator per §8.6 | 100% of calculator golden cases pass |
| P2.5 | Workflow states (§5) and automatic rule outcomes with audit events | Invalid transitions raise; rule-failure claims reach final states with reason codes |

### Phase 3 — Knowledge base and datasets (Weeks 2–3)

| Task | Work | Acceptance |
|---|---|---|
| P3.1 | Policy format checker (front matter, criterion IDs, sources present) | Every file in `coverage_policies/` passes |
| P3.2 | SBC generator from plans/benefits | Every number in each SBC matches the DB (test) |
| P3.3 | RAG ingestion (§9.3) and retrieval with plan/date filters | RAG evaluation recall@3 ≥ 0.85 |
| P3.4 | Claim generator + form renderer (§9.4) | Rendered forms re-parse (digital) to the original JSON exactly |
| P3.5 | Decision dataset generator, leakage checks, splits, data card | Checks pass; data card in `docs/` |

### Phase 4 — SLM (Weeks 3–4)

| Task | Work | Acceptance |
|---|---|---|
| P4.1 | Prompt `decision_v1`, Ollama client, output validation (§8.5) | Unit tests for every validation failure path |
| P4.2 | Baseline evaluation of base E2B (and E4B if hardware allows) on the test split | Results in `docs/results.md` |
| P4.3 | QLoRA fine-tuning script (`train` dependency group), run on the training machine | Adapter trained; training log and config saved |
| P4.4 | Evaluation of the fine-tuned model + RAG ablation | Macro-F1 and per-class metrics recorded; target macro-F1 ≥ 0.90 |
| P4.5 | Export to GGUF, Ollama `Modelfile`, switch `MODEL_NAME` | Fine-tuned model serves through Ollama and passes P4.1 tests |

### Phase 5 — Integration (Week 4)

| Task | Work | Acceptance |
|---|---|---|
| P5.1 | Intake for digital PDF and scanned images with confidences (§8.2) | Field accuracy ≥ 90% on held-out scanned forms |
| P5.2 | Context assembly (§8.4) wired into the pipeline | Context IDs stored in decision records |
| P5.3 | Review tiers, review actions, calculator re-run on override, finalization, accumulator update | Tests for every tier rule and override path |
| P5.4 | Explainability rendering (§8.7) | Every amount and reason in the explanation matches the record (test) |
| P5.5 | React web pages (§8.11, D-UI-1) | All pages work against the running API; Playwright smoke test passes |
| P5.6 | End-to-end golden claims | All e2e cases pass |

### Phase 6 — Evaluation and demo (Week 5)

| Task | Work | Acceptance |
|---|---|---|
| P6.1 | Metrics report script: rules and calculator pass rates, extraction accuracy, RAG recall@3, SLM metrics, latency per stage, reviewer agreement, review time | `docs/results.md` regenerated from scripts |
| P6.2 | Demo scenarios and script (one of every outcome) | Rehearsed run without manual fixes |
| P6.3 | README, architecture diagram, limitations section | Team review |

**Stretch items** (only if `DECISIONS.md` approves): async queue, extract-lora, E4B, hybrid
dense + sparse retrieval, model confidence score for tiers.

---

## 12. Working rules for Claude Code

1. **Start of task:** read `DECISIONS.md` and the sections of this file referenced by the task.
   Restate the task and its acceptance criteria in two or three lines.
2. **Plan first** when a task touches more than two files. Wait for approval.
3. **Tests first** for rules, calculator, validators and derivation logic. Golden cases already
   exist as human-written files; write code to satisfy them.
4. **Small steps:** make one change, run the tests, then continue.
5. **Branch naming:** `p<phase>.<task>-<short-name>`, e.g. `p2.3-rules-engine`.
6. **Before finishing:** run `uv run ruff check .`, `uv run ruff format --check .`,
   `uv run pytest`, `uv run lint-imports`. All must pass.
7. **Never** delete or weaken a test to make it pass.
8. **Do not update `DECISIONS.md`** unless a human asks you to record a decision they made.
9. **Keep sessions small:** one task per session; ask the human to `/clear` before the next.
10. **End every task with this report:**

```markdown
## Task report — <task ID>
- Summary:
- Files changed:
- Tests: added / run / result
- Acceptance criteria: met or not met, with evidence
- Decisions needed from the team:
- Follow-ups:
```

---

## 13. Stop-and-ask triggers

Stop and ask the human before continuing if any of these is true:

- A contract field needs to change (H11)
- A new dependency seems necessary (H14)
- An insurance, coding or clinical rule, code, criterion or CARC mapping is not in the data or
  `DECISIONS.md` (H6)
- A golden test expectation looks wrong (H12)
- Money logic is needed anywhere outside `app/calculator` (H1)
- A task seems to require something listed as out of scope (§4)
- The task touches `confidential/` or would send claim data over the network (H7, H9)
- This file, `DECISIONS.md` and the request disagree
- Acceptance criteria are not met after two attempts

---

## 14. Definition of done

A task is done when: its acceptance criteria are met with evidence; lint, format, tests and
import checks pass locally and in CI; no hard rule is broken; docs touched by the change are
updated; the task report is written; the pull request is opened and reviewed by a teammate.

---

## 15. Glossary

| Term | Meaning |
|---|---|
| Edit | An automated claim check (AHM term). Our rules R01–R13 are edits. |
| REJECT | Data problem; claim returned to the provider to correct and resubmit |
| DENY (by rule) | A hard requirement is not met; final, with a reason code |
| PEND (by rule) | Information not yet available; claim waits |
| Allowed amount | The maximum the plan recognizes for a service |
| Contractual adjustment | Billed − allowed, written off by an in-network provider |
| Copay / deductible / coinsurance | Member cost-share types |
| OOP max | Out-of-pocket maximum; caps member cost share per year |
| COB | Coordination of benefits between two plans |
| NCCI PTP | Procedure pairs that should not be billed together |
| MUE | Maximum units per code per day |
| CARC / RARC | Standard claim adjustment reason and remark codes |
| SBC | Summary of Benefits and Coverage document |
| Review tier | QUICK / STANDARD / FULL depth of human review |
