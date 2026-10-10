# Golden test cases

Expected values are synthesized before the code they test, with worked steps, and spot-checked by
the team (DECISIONS.md 2026-09-21). **Never change an expected value to make a test pass (H12).**
If one looks wrong, stop and ask.

| Folder | Cases | Tested by |
|---|---|---|
| `rules/` | 90 | P2.3 rules engine (`tests/unit/test_rules_golden.py`) |
| `calculator/` | 56 | P2.4 calculator (`tests/unit/test_calculator_golden.py`) |
| `e2e/` | 30 | P5.6 end-to-end pipeline |
| `e2e_v2/` | 10 | Policy set v2 versions of the e2e cases that cite a retired v1 criterion; **engine-derived** expected values, not hand-checked (D-GOLD-9, D-GOLD-10; `tests/e2e/test_e2e_golden_v2.py`) |
| `rag/` | 50 queries | P3.3 retrieval (recall@3), policy set v1 |
| `rag/v2_criteria.json` | 51 codes | Policy set v2 exact lookup snapshot (D-RAG-2; `tests/unit/test_retrieval_v2.py`) |
| `blind_review/` | 30 claims | P6.1 reviewer agreement |

`tests/unit/test_golden_files.py` checks that every file is well formed: contracts validate, codes
exist, reason codes are mapped, and totals add up. The engines themselves are tested against these
files in their own tasks.

## Rules cases (`rules/*.json`)

Each file holds `{"cases": [...]}`. A case has:

- `given.claim`: the claim as received (a raw dict, so R01–R03 cases can hold invalid data);
  `given.source_format`; `given.field_confidences` (only fields below 1.0 are listed);
  `given.reference_additions` (authorizations or existing claims added to `rules/reference.json`).
- `expected.claim_outcome` (PASS / REJECT / DENY / PEND) and `expected.status`.
- `expected.failures`: every failing rule as `{rule_id, outcome, reason_code, line_no}`, after the
  H5 conversion. Group A/B failures have `line_no: null`.
- `expected.line_outcomes`: per line, only when the claim reaches Group C; `null` otherwise.
- `expected.flags`: claim-level flags (`OON`). Line flags (`NCCI_BYPASS`) are in `line_outcomes`.
- `worked_steps` and `sources`.

Plans, benefits, exclusions, NCCI, MUE, ICD-10-CM and place-of-service codes come from the loaded
curated and raw data.

### Rules assumptions (confirmed by the team in G1-G2)

Reviewed in the G1-G2 golden-test spot-check (`data/verification/reviews/G_summary.md`): every
rules assumption was accepted except A-R3, which changes in v2 (D-GOLD-3, below). The engine
(P2.3a) implements them as written here. Its H5 field mapping is the G1 mapping with `member_id`
added to R07 and R09 (D-GOLD-4, D-GOLD-5); each rule's fields are in its `fields_used`.

| ID | Assumption |
|---|---|
| A-R1 | Network status comes from the billing NPI's `provider_networks` row for the member's plan; no row means out of network. |
| A-R2 | R06 checks the billing NPI and every rendering NPI. Rules that need a provider record (R07–R10) skip a provider that is not found. |
| A-R3 | R11 applies to two lines with the same date of service. **Rules v1 (frozen for model v1, `data/curated/ncci_bypass_modifiers.csv`):** XE, XP, XS or XU on either line bypasses an edit with modifier indicator 1. **From `RULES_VERSION` 2.1.0 (D-RULE-8, amending D-GOLD-3):** any NCCI PTP-associated modifier of the 2026 NCCI Policy Manual (Chapter I section E, page I-14; `data/curated/ncci_ptp_modifiers.csv`) bypasses where the manual places it: 59, XE, XP, XS, XU on either line but not on an E&M line; 24, 25, 57 on an E&M line paired with a non-E&M code, 25 only when that code's PFS global period is 000, 010 or XXX (page I-16) and 57 only when it is 090 (page I-13); 58, 78, 79 on a non-E&M line; 27, 91 on either line; anatomic modifiers only when both lines carry one and they share none (page I-17). E&M lines are the in-scope office visit codes. A bypass is PASS with the flag NCCI_BYPASS. |
| A-R4 | R12 adds the units of the same code on the same date of service (every in-scope code has MUE adjudication indicator 2 or 3, a date-of-service edit) and denies every line of that code and date. |
| A-R5 | R09 (provider type) and R10 (authorization provider) use each line's rendering NPI. |
| A-R6 | Duplicate key: member, billing NPI, date of service, procedure code. Existing claims with status REJECTED are ignored. |
| A-R7 | Group A reports every failure it can detect and stops; Group B evaluates all its rules. |
| A-R8 | Contract validation errors map to rules: missing field → R01, code format → R02, NPI format or check digit → R03. |
| A-R9 | `field_confidences` keys are dotted paths with 0-based indexes (`service_lines.0.units`). "Below the threshold" means strictly less than `EXTRACTION_CONFIDENCE_MIN` (0.85). |
| A-R10 | A claim that passes keeps status RECEIVED and continues to context assembly. |
| A-R11 | A line failing several Group C rules lists every reason code in rule order (R11, R12, R13). |

## Calculator cases (`calculator/*.json`)

`given`: plan, network, accumulators before the claim (for that network), the fee schedule entries
used (`inn_allowed_cents` / `oon_allowed_cents` per unit, D6), lines with the final decision and
benefit category, and other coverage. `expected.amounts` is a `CostBreakdown`;
`expected.accumulators_after` holds the working accumulators after the claim (stored accumulators
change only at finalization, §8.6).

### Calculator assumptions (confirmed by the team in G1-G2)

Accepted in the G1-G2 spot-check (`data/verification/reviews/G_summary.md`), A2 and A6 with a note
to consider in v2 (one copay per visit; crediting only what the member actually paid).

| ID | Assumption |
|---|---|
| A1 | The fee schedule amount is per unit: fee for a line = fee x units; allowed = min(billed, fee x units). |
| A2 | A copay applies to every approved line in a COPAY category (per line, as §8.6 is written), even two lines on one day. |
| A3 | Out-of-network lines always use the plan's out-of-network deductible and coinsurance, including COPAY categories. |
| A4 | The out-of-pocket cap is filled in order deductible, copay, coinsurance; the part above the remaining maximum is dropped from the last components first. |
| A5 | Deductible, copays and coinsurance all count toward the out-of-pocket maximum (D7 covers copays). |
| A6 | COB: `deductible_cents`, `copay_cents` and `coinsurance_cents` show the normal cost share, and the accumulators grow by it; `plan_pays` = min(normal plan payment, allowed − primary paid), not below 0; `member_pays` = allowed − primary paid − plan pays, not below 0. |
| A7 | Denied and pended lines appear with `billed_cents` only; every other amount is 0. |
| A8 | Totals are sums over every line. |
| A9 | Contractual adjustment (billed − allowed) is in-network only; balance-bill exposure (billed − allowed) is out-of-network only and is not part of `member_pays`. |

## End-to-end cases (`e2e/cases.json`)

These cases are pinned to policy set v1 (D-GOLD-8). The 21 that cite no retired v1 criterion also run on policy set v2 with the same expected values; the other 10 have v2 versions in `e2e_v2/cases.json`, whose inputs are mapped from these by `scripts/verify/e2e_v2_cases.py` and whose expected values are the engine's output (`expected_source`; D-GOLD-9).

Each case gives the claim (`given.claim`), its source format, field confidences, the reference
records it needs (member, providers, network rows, authorizations, accumulators, existing claims),
the model answer to use when the model is stubbed, and the reviewer's action. Expected values:

- `rules`: the rule outcome. Claims stopped by rules end there (`recommendation: null`).
- `recommendation`: whether the model output is valid, the line decisions and who made them
  (RULE / MODEL / VALIDATION), the derived claim decision, the review tier (§8.5) and the amounts.
- `final`: status, line decisions after review, amounts after the calculator re-runs, and the stored
  accumulators after finalization.

Claims and model answers come from the scenario engine (`training/generate/scenarios.py`); tiers,
statuses and amounts are worked out step by step with the calculator assumptions above.
`DIGITAL_PDF` cases are rendered and parsed by the runner; the `SCANNED` cases stub intake with the
given confidences (OCR accuracy is measured in P5.1). The review tier's high-dollar threshold is
`REVIEW_HIGH_DOLLAR_CENTS` = 100000 and the confidence threshold 0.85.

## RAG queries (`rag/queries.json`)

A query, procedure code, plan and date of service, and the criterion IDs that should appear in the
top 3. An empty list (with `why_empty`) means no policy is relevant: an office visit, a procedure
outside the scope, or a date of service before every policy's effective date. The file states the
recall@3 metric and the P3.3 target (0.85).

## Blind review (`blind_review/`)

`claims.json` holds 30 claims exactly as the model sees them (`review_view`), and
`review_sheet.csv` one row per line to decide. Reviewers fill in the sheet **before** seeing any
model output. The generator's labels are written by `uv run python -m training.generate.blind_review`
to `data/generated/blind_review/answer_key.json` (never committed); do not open it until the sheet is
complete. The test suite checks that the generator still reproduces the committed claims.
