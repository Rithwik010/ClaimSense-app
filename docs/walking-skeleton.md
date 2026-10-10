# Walking skeleton (P1.5)

One JSON claim goes through every stage of the pipeline in its simplest form:

```text
POST /v1/claims/intake  ->  claim stored (RECEIVED), audit INTAKE_COMPLETED
POST /v1/claims/{id}/process
    rule R05 (eligibility)      -> DENY: DENIED_BY_RULE, audit AUTO_OUTCOME (final, no model)
    context (plan facts, retrieved criteria) -> audit CONTEXT_ASSEMBLED
    base gemma4:e2b via Ollama  -> output validation -> audit SLM_RECOMMENDED or OUTPUT_INVALID
    calculator (COPAY lines)    -> audit CALCULATED
    decision record (version 1) -> AWAITING_REVIEW with claim decision and review tier
GET /v1/claims/{id}, GET /v1/claims/{id}/audit
Web page: submit, process, show the record and the audit trail (Streamlit at the time; now the React app, D-UI-2)
```

## Run it

```bash
docker compose up -d --wait                       # Postgres and Qdrant
uv run alembic upgrade head
uv run python -m training.generate.reference      # members, providers, ... (if not generated yet)
uv run python -m app.db.seed                      # curated data, codes and fees, reference data
uv run uvicorn app.api.main:app                   # terminal 1: API on :8000
cd frontend-web && npm ci && npm run dev         # terminal 2: web app on :5173 (or: make demo)
```

Ollama must be running with `gemma4:e2b` pulled. `/health` reports the database, Qdrant and Ollama.
The sample claim (`tests/e2e/sample_claim.json`) is the E2E-14 office visit. It needs member
`MBR-000020` and provider `2186976371` from the generated reference data. Each submission gets a
new claim ID.

## Tests

- `tests/e2e/test_walking_skeleton.py`: golden cases E2E-14 (office visit approved, QUICK) and
  E2E-05 (R05 DENY) through the API, with the model stubbed; also invalid model output,
  request errors, and a model that cannot be reached. Runs in CI with Postgres.
- `tests/e2e/test_live_model.py`: the sample claim through the real model. It is opt-in:
  `CLAIMSENSE_LIVE_MODEL=1 uv run pytest tests/e2e/test_live_model.py`.
- Golden cases for R05 (`test_rules_eligibility.py`) and the copay calculator
  (`test_calculator_copay.py`), plus unit tests for output validation, review tiers, claim
  decisions and status transitions.

## What the base model does

In the first P1.5 run (no retrieval yet), base `gemma4:e2b` invented a criterion ID
(`POL-C-111.c1`). Output validation rejected it: the line became PEND with `MODEL_OUTPUT_INVALID`
and the claim went to FULL review. This is the intended behaviour for an untrained model; the
baseline (`docs/results.md`) measures it on the test split. The model answers in about 3 seconds on
the M5 laptop with thinking disabled.

## Not in the skeleton yet

| Missing | Until then | Task |
|---|---|---|
| Rules other than R05, duplicates, H5 | An unknown member or billing provider returns 422, and the claim stays RECEIVED | P2.3 |
| Deductible/coinsurance, out-of-network, COB | 422 when an approved line needs them | P2.4 |
| Coverage criteria from retrieval | Built (P3.3); run `uv run python -m app.rag.knowledge` once so Qdrant has the collection | done |
| PDF and scanned intake | JSON only | P5.1 |
| Review, finalization, accumulator update | Records stop at AWAITING_REVIEW | P5.3 |
| Explanation text, role header | Not returned | P5.4, P5.5 |
| NCCI, MUE and place-of-service tables in the seed | Not loaded | P2.1 |
