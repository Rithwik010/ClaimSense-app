# Golden test cases

Expected values are synthesized before the code they test, with worked steps, and spot-checked by
the team (DECISIONS.md 2026-09-21). **Never change an expected value to make a test pass (H12).**
If one looks wrong, stop and ask.

| Folder | Cases | Tested by |
|---|---|---|
| `rules/` | 90 | P2.3 rules engine |
| `calculator/` | 52 | P2.4 calculator |
| `e2e/` | 30 | P5.6 end-to-end pipeline |
| `rag/` | 45 queries | P3.3 retrieval (recall@3) |
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

### Rules assumptions (to be confirmed by the team)

| ID | Assumption |
|---|---|
| A-R1 | Network status comes from the billing NPI's `provider_networks` row for the member's plan; no row means out of network. |
| A-R2 | R06 checks the billing NPI and every rendering NPI. Rules that need a provider record (R07–R10) skip a provider that is not found. |
| A-R3 | R11 applies to two lines with the same date of service. A bypass modifier on either line counts. Bypass modifiers are `data/curated/ncci_bypass_modifiers.csv` (XE, XP, XS, XU). |
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

### Calculator assumptions (to be confirmed by the team)

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

## Other sets

- `e2e/`: full claims with the reference records they need, the model answer to use when the model
  is stubbed, the expected rule outcome, line decisions, review tier, amounts and final status.
- `rag/queries.json`: a query, plan and date of service, and the criterion IDs that should appear in
  the top 3 (an empty list means no policy is relevant).
- `blind_review/`: claims for reviewers to decide before they see the model output. The generator
  labels are in `blind_review/answer_key.json`; reviewers must not open it until they are done.
