# Golden test spot-check (Task G1)

For one reviewer. Work out each case by hand from the inputs shown, using only the quoted INSTRUCTIONS.md text and the assumptions below, then fill in the blank cells. Amounts are in cents. Mark each assumption and each H5 field mapping ACCEPT or CHANGE.

**Do not open G_spotcheck_answers.csv until every cell is filled.** The same goes for G_golden_checks.csv, which holds the details of the automatic checks with expected amounts.

Estimated time: 84 minutes (10 rules cases x 3 minutes, 9 calculator cases x 6 minutes).

## Automatic checks (90 rules cases, 52 calculator cases)

Findings: violations 0, conflicts with later decisions 6, cases to review against D-RULE-1 9. Only case IDs are shown here, so the sheet stays blind.

| Check | Cases checked | Findings | Cases |
|---|---|---|---|
| Calculator: plan pays + member pays = max(0, allowed - primary paid) | 52 | 0 | - |
| Calculator: allowed <= billed | 52 | 0 | - |
| Calculator: no negative amounts | 52 | 0 | - |
| Calculator: member pays <= remaining out-of-pocket maximum | 52 | 0 | - |
| Calculator: deductible applied <= remaining deductible | 52 | 0 | - |
| Calculator: copay <= allowed | 52 | 0 | - |
| Calculator: denied or pended lines pay 0 | 52 | 0 | - |
| Calculator: integer cents only | 52 | 0 | - |
| Calculator: totals = sum of lines (A8) | 52 | 0 | - |
| Calculator: accumulators after = before + the claim's cost share (A5) | 52 | 0 | - |
| Rules: exactly one expected outcome | 90 | 0 | - |
| Rules: status matches the outcome | 90 | 0 | - |
| Rules: targeted rule exists in section 8.3 | 90 | 0 | - |
| Rules: failure matches section 8.3 | 90 | 0 | - |
| Rules: line number matches the rule's group | 90 | 0 | - |
| Rules: Group A stops the claim | 90 | 0 | - |
| Rules: Group B stops the claim | 90 | 0 | - |
| Rules: outcome follows the group order | 90 | 0 | - |
| Rules: H5: a failure on a low-confidence field becomes REJECT | 90 | 0 | - |
| Rules: H5 applied without a low-confidence field the rule uses | 90 | 0 | - |
| Rules: R14 (D-ESI-3) would deny this ESI line | 90 | 0 | - |
| Rules: R15 (D-DX-1) would deny this line | 90 | 6 | R11-02 (line 1), R11-03 (line 1), R11-03 (line 2), R11-07 (line 2), R11-08 (line 2), X-02 (line 1) |
| Rules: D-RULE-1 candidate POL-PAIN-001.F6 may change this case | 90 | 8 | R10-01, R10-02, R10-03, R10-04, R10-05, R10-09, B-03, H5-02 |
| Rules: D-RULE-1 candidate POL-PAIN-002.F9 may change this case | 90 | 1 | X-01 |

D-ESI-1, D-ESI-2 and D-ESI-4 to D-ESI-7 change coverage-criterion labels, which the rules cases do not carry, so they do not apply here; D-ESI-3 is R14 above. Group C is R11-R13 (D8; INSTRUCTIONS.md section 8.3 item 3 now says so).

In total, the first calculator check compares plan pays + member pays with the sum over the approved lines of max(0, allowed - primary paid) (A8). That equals max(0, total allowed - total primary paid) unless one claim has lines where the primary paid more than allowed and lines where it paid less; cases where the two differ: 0.

### Coverage: rules

| Rule or variant | Golden cases |
|---|---|
| R01: cases that target it | 6 |
| R02: cases that target it | 7 |
| R03: cases that target it | 5 |
| R04: cases that target it | 3 |
| DUP: cases that target it | 4 |
| R05: cases that target it | 7 |
| R06: cases that target it | 6 |
| R07: cases that target it | 10 |
| R08: cases that target it | 8 |
| R09: cases that target it | 5 |
| R10: cases that target it | 13 |
| R11: cases that target it | 12 |
| R12: cases that target it | 7 |
| R13: cases that target it | 5 |
| H5: cases that target it | 10 |
| Clean claim: every rule passes | 1 |
| R06 provider not found -> REJECT | 3 |
| R06 enrollment pending -> PEND | 3 |
| R08 out of network, not covered -> DENY | 3 |
| R08 out of network, covered -> PASS with flag OON | 4 |
| R11 column-2 line denied | 8 |
| R11 bypass modifier -> flag NCCI_BYPASS | 2 |
| H5 on a Group A rule | 2 |
| H5 on a Group B rule | 4 |
| H5 on a Group C rule | 1 |
| Group B: DENY and PEND together (DENY wins) | 2 |
| Group B: REJECT with DENY or PEND (REJECT wins, D8) | 1 |
| Group C: every line denied -> claim DENY | 3 |
| R14 (D-ESI-3): ESI with another block on the same date | **none** |
| R15 (D-DX-1): diagnoses do not satisfy the billing article | **none** |
| D-RULE-1 candidate POL-BH-001.F3: Rule: testing hours billed above 8 need documented necessity for the extended testing. | **none** |
| D-RULE-1 candidate POL-DX-001.F7: Rule: a home sleep test billed with a parasomnia diagnosis. | **none** |
| D-RULE-1 candidate POL-DX-002.F2: Rule: nerve conduction without needle EMG on the claim is usually not necessary, except carpal tunnel syndrome with high pre-test probability (codes plus diagnosis). | **none** |
| D-RULE-1 candidate POL-DX-002.F3: Rule: nerve conduction is paid once per nerve, whatever the number of sites or methods (units). | **none** |
| D-RULE-1 candidate POL-DX-002.F4: Rule: a separate paraspinal EMG code is not expected with the extremity EMG code for the paraspinals of that extremity (codes billed together). | **none** |
| D-RULE-1 candidate POL-IMG-001.F2: Any same-day imaging rule must allow scans of different body areas on the same day. | **none** |
| D-RULE-1 candidate POL-PAIN-001.F6: Rule: same-session levels from codes and units: transforaminal at most 2 levels; caudal or interlaminar 1 level and not bilateral. | **none** |
| D-RULE-1 candidate POL-PAIN-002.F9: Rule: one spinal region and at most 2 levels per session; other blocks on the same day need their own documented necessity. | **none** |
| D-RULE-1 candidate POL-SURG-003.F4: Any same-day rule must allow stab phlebectomy of the same vein with ablation when the criteria are met. | **none** |

### Coverage: cost-share situations (calculator)

| Situation | Golden cases |
|---|---|
| copay only | 17 |
| deductible not met | 9 |
| deductible partly met | 6 |
| deductible met | 18 |
| coinsurance | 21 |
| out-of-pocket maximum reached | 7 |
| out-of-network PPO | 8 |
| COB secondary | 6 |
| denied line in a multi-line claim | 2 |
| deductible spans lines | **none** |
| copay capped by the allowed amount | 1 |
| billed below the fee schedule | 5 |
| units > 1 | 7 |
| pended line | 2 |
| out-of-network copay category (A3) | 4 |
| COB: primary paid >= allowed | 1 |

No calculator case to sample for: deductible spans lines.

## Golden assumptions (tests/golden/README.md, word for word)

| ID | Assumption | ACCEPT / CHANGE | Notes |
|---|---|---|---|
| A-R1 | Network status comes from the billing NPI's `provider_networks` row for the member's plan; no row means out of network. | ACCEPT |  |
| A-R2 | R06 checks the billing NPI and every rendering NPI. Rules that need a provider record (R07–R10) skip a provider that is not found. | ACCEPT |  |
| A-R3 | R11 applies to two lines with the same date of service. A bypass modifier on either line counts. Bypass modifiers are `data/curated/ncci_bypass_modifiers.csv` (XE, XP, XS, XU). | CHANGE | add modifier 59, the standard NCCI-associated modifier; check the full list in the NCCI Policy Manual; frozen for v1, so a v2 change |
| A-R4 | R12 adds the units of the same code on the same date of service (every in-scope code has MUE adjudication indicator 2 or 3, a date-of-service edit) and denies every line of that code and date. | ACCEPT |  |
| A-R5 | R09 (provider type) and R10 (authorization provider) use each line's rendering NPI. | ACCEPT |  |
| A-R6 | Duplicate key: member, billing NPI, date of service, procedure code. Existing claims with status REJECTED are ignored. | ACCEPT |  |
| A-R7 | Group A reports every failure it can detect and stops; Group B evaluates all its rules. | ACCEPT |  |
| A-R8 | Contract validation errors map to rules: missing field → R01, code format → R02, NPI format or check digit → R03. | ACCEPT |  |
| A-R9 | `field_confidences` keys are dotted paths with 0-based indexes (`service_lines.0.units`). "Below the threshold" means strictly less than `EXTRACTION_CONFIDENCE_MIN` (0.85). | ACCEPT |  |
| A-R10 | A claim that passes keeps status RECEIVED and continues to context assembly. | ACCEPT |  |
| A-R11 | A line failing several Group C rules lists every reason code in rule order (R11, R12, R13). | ACCEPT |  |
| A1 | The fee schedule amount is per unit: fee for a line = fee x units; allowed = min(billed, fee x units). | ACCEPT |  |
| A2 | A copay applies to every approved line in a COPAY category (per line, as §8.6 is written), even two lines on one day. | ACCEPT | matches §8.6 as written; real plans usually charge one copay per visit, consider in v2 |
| A3 | Out-of-network lines always use the plan's out-of-network deductible and coinsurance, including COPAY categories. | ACCEPT |  |
| A4 | The out-of-pocket cap is filled in order deductible, copay, coinsurance; the part above the remaining maximum is dropped from the last components first. | ACCEPT |  |
| A5 | Deductible, copays and coinsurance all count toward the out-of-pocket maximum (D7 covers copays). | ACCEPT |  |
| A6 | COB: `deductible_cents`, `copay_cents` and `coinsurance_cents` show the normal cost share, and the accumulators grow by it; `plan_pays` = min(normal plan payment, allowed − primary paid), not below 0; `member_pays` = allowed − primary paid − plan pays, not below 0. | ACCEPT | design choice: some plans credit only what the member actually paid |
| A7 | Denied and pended lines appear with `billed_cents` only; every other amount is 0. | ACCEPT |  |
| A8 | Totals are sums over every line. | ACCEPT |  |
| A9 | Contractual adjustment (billed − allowed) is in-network only; balance-bill exposure (billed − allowed) is out-of-network only and is not part of `member_pays`. | ACCEPT |  |

## H5 field mapping used by the automatic checks

A failing rule becomes REJECT (H5) when one of these fields was read below 0.85.

| Rule | Fields used | Section 8.3 text it was read from | ACCEPT / CHANGE | Notes |
|---|---|---|---|---|
| R01 | the missing field itself (the cases do not name it, so not checked) | Required fields present | ACCEPT |  |
| R02 | diagnoses, service_lines.*.procedure_code, service_lines.*.place_of_service, service_lines.*.modifiers, service_lines.*.date_of_service | Codes valid: ICD-10-CM for the date-of-service fiscal year, procedure code in code table, place-of-service code, modifier format | ACCEPT |  |
| R03 | billing_npi, service_lines.*.rendering_npi, referring_npi | NPI check digits valid (billing, rendering, referring) | ACCEPT |  |
| R04 | member_id | Member ID found | ACCEPT |  |
| DUP | member_id, billing_npi, service_lines.*.date_of_service, service_lines.*.procedure_code | same member, provider, date of service, procedure code as an existing claim | ACCEPT |  |
| R05 | member_id, service_lines.*.date_of_service | Member eligible on every date of service (coverage start/end) | ACCEPT |  |
| R06 | billing_npi, service_lines.*.rendering_npi | Provider enrolled (not found → REJECT; enrollment pending → PEND) | ACCEPT |  |
| R07 | received_date, service_lines.*.date_of_service, billing_npi | Timely filing: received date − last date of service ≤ plan window (in-network vs out-of-network window from plan config) | CHANGE | add member_id: the filing window comes from the member's plan |
| R08 | billing_npi, member_id | Network: out-of-network and plan does not cover out-of-network → DENY; covered → PASS with flag `OON` | ACCEPT |  |
| R09 | referring_npi, service_lines.*.rendering_npi | Referral: plan requires referral for this provider type and no referring NPI | CHANGE | add member_id: referral rules come from the member's plan |
| R10 | member_id, service_lines.*.procedure_code, service_lines.*.rendering_npi, service_lines.*.date_of_service | Prior authorization: code requires auth per plan benefits, and no matching auth (member, provider, code, date range) | ACCEPT |  |
| R11 | service_lines.*.procedure_code, service_lines.*.modifiers, service_lines.*.date_of_service | NCCI procedure-to-procedure pair on the same claim: if the pair allows a bypass modifier and one is present → PASS with flag `NCCI_BYPASS` (SLM checks documentation); otherwise deny the column-2 line | ACCEPT |  |
| R12 | service_lines.*.units, service_lines.*.procedure_code, service_lines.*.date_of_service (the failing line only) | Units exceed the medically unlikely edit limit | ACCEPT |  |
| R13 | service_lines.*.procedure_code, member_id (the failing line only) | Procedure code on the plan's fixed exclusion list | ACCEPT |  |

## Rules cases (10, seed 42)

How the rules apply (INSTRUCTIONS.md section 8.3, word for word):

> 1. **Group A (data integrity)**: R01–R04. If any fails → claim outcome **REJECT**; stop.
> 2. **Group B (hard requirements)**: R05–R10. Evaluate **all**, record every failure. Outcome precedence: DENY over PEND. Any failure → claim stops with that outcome.
> 3. **Group C (line level)**: R11–R13. A failing line is denied; the claim continues with the remaining lines. If every line is denied → claim outcome DENY.
> 4. **H5 conversion**: if a failing rule's `fields_used` includes a field below the confidence threshold → outcome becomes **REJECT** with reason `RJ_LOW_CONFIDENCE_FIELD`.

> **Duplicate claims** (same member, provider, date of service, procedure code as an existing claim) → REJECT `RJ_DUPLICATE`.

DECISIONS.md D8, word for word: Rule order (D8): Group A = R01–R04 and the duplicate check (any failure → REJECT, stop). Group B = R05–R10, all evaluated, precedence REJECT > DENY > PEND. Group C = R11–R13 (line-level).

### Rules case 1 (H5-02)

Rule it exercises (INSTRUCTIONS.md section 8.3, word for word):

| ID | Rule | Failure outcome | Internal reason code |
|---|---|---|---|
| R10 | Prior authorization: code requires auth per plan benefits, and no matching auth (member, provider, code, date range) | DENY | `DN_NO_AUTH` |

> 4. **H5 conversion**: if a failing rule's `fields_used` includes a field below the confidence threshold → outcome becomes **REJECT** with reason `RJ_LOW_CONFIDENCE_FIELD`.

**Claim** (source format SCANNED):

| Field | Value |
|---|---|
| claim_id | GR-H5-02 |
| member_id | MBR-G00001 |
| patient.first_name | Asha |
| patient.last_name | Rao |
| patient.date_of_birth | 1981-04-02 |
| patient.sex | F |
| patient.address | 12 Elm St, Austin, TX, 78701 |
| subscriber_is_patient | True |
| billing_npi | 1000000020 |
| billing_tin | 080000002 |
| referring_npi | (null) |
| prior_auth_number | (null) |
| received_date | 2026-10-20 |
| frequency_code | 1 |
| other_coverage | (null) |
| clinical_notes | (empty) |

**Diagnoses:**

| Pointer | Code | In ICD-10-CM FY2027 |
|---|---|---|
| A | M5416 | yes: Radiculopathy, lumbar region |

**Service lines:**

| Line | Date of service | Place of service | Code | Modifiers | Diagnoses (pointer = code) | Units | Charge (cents) | Rendering NPI |
|---|---|---|---|---|---|---|---|---|
| 1 | 2026-10-06 | 11 | 62323 | (empty) | A = M5416 | 1 | 55000 | 1000000020 |

**Code lookups:**

- Procedure code 62323: in the code table; policy POL-PAIN-001; possible categories PAIN_MANAGEMENT; Epidural steroid injection between the vertebrae, lower back, with imaging guidance
- Place of service 11: Office
- NCCI bypass modifiers: XE, XP, XS, XU

**Field confidences below 1.0** (threshold 0.85, strictly below; A-R9):

- service_lines.0.procedure_code = 0.8

**Reference data:**

- Member MBR-G00001: plan PLN-PPO-GOLD, coverage 2026-01-01 to open
- Plan PLN-PPO-GOLD (PPO): filing window 90 days in network, 180 days out of network; out-of-network care covered: yes; referral required for: none; fixed exclusions: none
- Benefit PLN-PPO-GOLD / PAIN_MANAGEMENT (code 62323): covered yes, prior authorization required, visit limit none, DEDUCTIBLE_COINSURANCE
- Billing NPI 1000000020: Golden Pain Provider, PAIN_MEDICINE, ENROLLED
- Rendering NPI 1000000020: Golden Pain Provider, PAIN_MEDICINE, ENROLLED
- Network row for billing NPI 1000000020 and plan PLN-PPO-GOLD: in network (A-R1)
- Authorizations for this member: none
- Existing claims for this member: none
- NCCI pairs among the claim's codes: none found
- MUE 62323: at most 1 unit per date of service (3 Date of Service Edit: Clinical)

| My outcome (REJECT / DENY / PEND / PASS and reason code; line outcomes if any) | Notes |
|---|---|
| REJECT RJ_LOW_CONFIDENCE_FIELD | R10 fails (auth required, none on file), which would be DENY DN_NO_AUTH; procedure code read at 0.80, a field R10 uses, so H5 gives REJECT |

### Rules case 2 (DUP-01)

Rule it exercises (INSTRUCTIONS.md section 8.3, word for word):

> **Duplicate claims** (same member, provider, date of service, procedure code as an existing claim) → REJECT `RJ_DUPLICATE`.

**Claim** (source format JSON):

| Field | Value |
|---|---|
| claim_id | GR-DUP-01 |
| member_id | MBR-G00001 |
| patient.first_name | Asha |
| patient.last_name | Rao |
| patient.date_of_birth | 1981-04-02 |
| patient.sex | F |
| patient.address | 12 Elm St, Austin, TX, 78701 |
| subscriber_is_patient | True |
| billing_npi | 1000000012 |
| billing_tin | 080000001 |
| referring_npi | (null) |
| prior_auth_number | (null) |
| received_date | 2026-10-20 |
| frequency_code | 1 |
| other_coverage | (null) |
| clinical_notes | (empty) |

**Diagnoses:**

| Pointer | Code | In ICD-10-CM FY2027 |
|---|---|---|
| A | M5416 | yes: Radiculopathy, lumbar region |

**Service lines:**

| Line | Date of service | Place of service | Code | Modifiers | Diagnoses (pointer = code) | Units | Charge (cents) | Rendering NPI |
|---|---|---|---|---|---|---|---|---|
| 1 | 2026-10-06 | 11 | 99213 | (empty) | A = M5416 | 1 | 19000 | 1000000012 |

**Code lookups:**

- Procedure code 99213: in the code table; policy none; possible categories OFFICE_VISIT_PCP, OFFICE_VISIT_SPECIALIST; Office visit for an existing patient, low-complexity problem
- Place of service 11: Office
- NCCI bypass modifiers: XE, XP, XS, XU

**Field confidences below 1.0** (threshold 0.85, strictly below; A-R9):

- none

**Reference data:**

- Member MBR-G00001: plan PLN-PPO-GOLD, coverage 2026-01-01 to open
- Plan PLN-PPO-GOLD (PPO): filing window 90 days in network, 180 days out of network; out-of-network care covered: yes; referral required for: none; fixed exclusions: none
- Benefit PLN-PPO-GOLD / OFFICE_VISIT_PCP (code 99213): covered yes, prior authorization not required, visit limit none, copay 2500
- Benefit PLN-PPO-GOLD / OFFICE_VISIT_SPECIALIST (code 99213): covered yes, prior authorization not required, visit limit none, copay 5000
- Billing NPI 1000000012: Golden Pcp Provider, PRIMARY_CARE, ENROLLED
- Rendering NPI 1000000012: Golden Pcp Provider, PRIMARY_CARE, ENROLLED
- Network row for billing NPI 1000000012 and plan PLN-PPO-GOLD: in network (A-R1)
- Authorizations for this member: none
- Existing claim CLM-EXIST-01: billing NPI 1000000012, date of service 2026-10-06, code 99213, status AWAITING_REVIEW
- NCCI pairs among the claim's codes: none found
- MUE 99213: at most 2 units per date of service (3 Date of Service Edit: Clinical)

| My outcome (REJECT / DENY / PEND / PASS and reason code; line outcomes if any) | Notes |
|---|---|
| REJECT RJ_DUPLICATE | same member, billing NPI, date and 99213 as CLM-EXIST-01, status not REJECTED |

### Rules case 3 (R11-09)

Rule it exercises (INSTRUCTIONS.md section 8.3, word for word):

| ID | Rule | Failure outcome | Internal reason code |
|---|---|---|---|
| R11 | NCCI procedure-to-procedure pair on the same claim: if the pair allows a bypass modifier and one is present → PASS with flag `NCCI_BYPASS` (SLM checks documentation); otherwise deny the column-2 line | Line DENY | `DN_NCCI_BUNDLED` |

**Claim** (source format JSON):

| Field | Value |
|---|---|
| claim_id | GR-R11-09 |
| member_id | MBR-G00001 |
| patient.first_name | Asha |
| patient.last_name | Rao |
| patient.date_of_birth | 1981-04-02 |
| patient.sex | F |
| patient.address | 12 Elm St, Austin, TX, 78701 |
| subscriber_is_patient | True |
| billing_npi | 1000000061 |
| billing_tin | 080000006 |
| referring_npi | (null) |
| prior_auth_number | (null) |
| received_date | 2026-10-20 |
| frequency_code | 1 |
| other_coverage | (null) |
| clinical_notes | (empty) |

**Diagnoses:**

| Pointer | Code | In ICD-10-CM FY2027 |
|---|---|---|
| A | K921 | yes: Melena |

**Service lines:**

| Line | Date of service | Place of service | Code | Modifiers | Diagnoses (pointer = code) | Units | Charge (cents) | Rendering NPI |
|---|---|---|---|---|---|---|---|---|
| 1 | 2026-10-06 | 22 | 45385 | (empty) | A = K921 | 1 | 100000 | 1000000061 |
| 2 | 2026-10-06 | 22 | 45380 | XS | A = K921 | 1 | 96000 | 1000000061 |

**Code lookups:**

- Procedure code 45380: in the code table; policy POL-SURG-002; possible categories ENDOSCOPY, PREVENTIVE_CARE; Colonoscopy with tissue sample (biopsy)
- Procedure code 45385: in the code table; policy POL-SURG-002; possible categories ENDOSCOPY, PREVENTIVE_CARE; Colonoscopy with polyp removal using a wire snare
- Place of service 22: On Campus-Outpatient Hospital
- NCCI bypass modifiers: XE, XP, XS, XU

**Field confidences below 1.0** (threshold 0.85, strictly below; A-R9):

- none

**Reference data:**

- Member MBR-G00001: plan PLN-PPO-GOLD, coverage 2026-01-01 to open
- Plan PLN-PPO-GOLD (PPO): filing window 90 days in network, 180 days out of network; out-of-network care covered: yes; referral required for: none; fixed exclusions: none
- Benefit PLN-PPO-GOLD / ENDOSCOPY (code 45380): covered yes, prior authorization not required, visit limit none, DEDUCTIBLE_COINSURANCE
- Benefit PLN-PPO-GOLD / PREVENTIVE_CARE (code 45380): covered yes, prior authorization not required, visit limit none, copay 0
- Benefit PLN-PPO-GOLD / ENDOSCOPY (code 45385): covered yes, prior authorization not required, visit limit none, DEDUCTIBLE_COINSURANCE
- Benefit PLN-PPO-GOLD / PREVENTIVE_CARE (code 45385): covered yes, prior authorization not required, visit limit none, copay 0
- Billing NPI 1000000061: Golden Gi Provider, GASTROENTEROLOGY, ENROLLED
- Rendering NPI 1000000061: Golden Gi Provider, GASTROENTEROLOGY, ENROLLED
- Network row for billing NPI 1000000061 and plan PLN-PPO-GOLD: in network (A-R1)
- Authorizations for this member: none
- Existing claims for this member: none
- NCCI pair 45385 / 45380 (column-2 code 45380): modifier indicator 1, effective 2002-04-01
- MUE 45380: at most 1 unit per date of service (2 Date of Service Edit: Policy)
- MUE 45385: at most 1 unit per date of service (2 Date of Service Edit: Policy)

| My outcome (REJECT / DENY / PEND / PASS and reason code; line outcomes if any) | Notes |
|---|---|
| PASS; line 2 flag NCCI_BYPASS | pair 45385/45380 allows bypass (indicator 1); XS on line 2; other rules pass |

### Rules case 4 (R03-04)

Rule it exercises (INSTRUCTIONS.md section 8.3, word for word):

| ID | Rule | Failure outcome | Internal reason code |
|---|---|---|---|
| R03 | NPI check digits valid (billing, rendering, referring) | REJECT | `RJ_INVALID_NPI` |

**Claim** (source format JSON):

| Field | Value |
|---|---|
| claim_id | GR-R03-04 |
| member_id | MBR-G00001 |
| patient.first_name | Asha |
| patient.last_name | Rao |
| patient.date_of_birth | 1981-04-02 |
| patient.sex | F |
| patient.address | 12 Elm St, Austin, TX, 78701 |
| subscriber_is_patient | True |
| billing_npi | 123456789 |
| billing_tin | 080000001 |
| referring_npi | (null) |
| prior_auth_number | (null) |
| received_date | 2026-10-20 |
| frequency_code | 1 |
| other_coverage | (null) |
| clinical_notes | (empty) |

**Diagnoses:**

| Pointer | Code | In ICD-10-CM FY2027 |
|---|---|---|
| A | M5416 | yes: Radiculopathy, lumbar region |

**Service lines:**

| Line | Date of service | Place of service | Code | Modifiers | Diagnoses (pointer = code) | Units | Charge (cents) | Rendering NPI |
|---|---|---|---|---|---|---|---|---|
| 1 | 2026-10-06 | 11 | 99213 | (empty) | A = M5416 | 1 | 19000 | 1000000012 |

**Code lookups:**

- Procedure code 99213: in the code table; policy none; possible categories OFFICE_VISIT_PCP, OFFICE_VISIT_SPECIALIST; Office visit for an existing patient, low-complexity problem
- Place of service 11: Office
- NCCI bypass modifiers: XE, XP, XS, XU

**Field confidences below 1.0** (threshold 0.85, strictly below; A-R9):

- none

**Reference data:**

- Member MBR-G00001: plan PLN-PPO-GOLD, coverage 2026-01-01 to open
- Plan PLN-PPO-GOLD (PPO): filing window 90 days in network, 180 days out of network; out-of-network care covered: yes; referral required for: none; fixed exclusions: none
- Benefit PLN-PPO-GOLD / OFFICE_VISIT_PCP (code 99213): covered yes, prior authorization not required, visit limit none, copay 2500
- Benefit PLN-PPO-GOLD / OFFICE_VISIT_SPECIALIST (code 99213): covered yes, prior authorization not required, visit limit none, copay 5000
- Billing NPI 123456789: not in the provider records
- Rendering NPI 1000000012: Golden Pcp Provider, PRIMARY_CARE, ENROLLED
- Network row for billing NPI 123456789 and plan PLN-PPO-GOLD: no row (A-R1)
- Authorizations for this member: none
- Existing claims for this member: none
- NCCI pairs among the claim's codes: none found
- MUE 99213: at most 2 units per date of service (3 Date of Service Edit: Clinical)

| My outcome (REJECT / DENY / PEND / PASS and reason code; line outcomes if any) | Notes |
|---|---|
| REJECT RJ_INVALID_NPI | billing NPI has 9 digits (A-R8 to R03); Group A stops before R06 |

### Rules case 5 (R02-01)

Rule it exercises (INSTRUCTIONS.md section 8.3, word for word):

| ID | Rule | Failure outcome | Internal reason code |
|---|---|---|---|
| R02 | Codes valid: ICD-10-CM for the date-of-service fiscal year, procedure code in code table, place-of-service code, modifier format | REJECT | `RJ_INVALID_CODE` |

**Claim** (source format JSON):

| Field | Value |
|---|---|
| claim_id | GR-R02-01 |
| member_id | MBR-G00001 |
| patient.first_name | Asha |
| patient.last_name | Rao |
| patient.date_of_birth | 1981-04-02 |
| patient.sex | F |
| patient.address | 12 Elm St, Austin, TX, 78701 |
| subscriber_is_patient | True |
| billing_npi | 1000000012 |
| billing_tin | 080000001 |
| referring_npi | (null) |
| prior_auth_number | (null) |
| received_date | 2026-10-20 |
| frequency_code | 1 |
| other_coverage | (null) |
| clinical_notes | (empty) |

**Diagnoses:**

| Pointer | Code | In ICD-10-CM FY2027 |
|---|---|---|
| A | M54.1 | no |

**Service lines:**

| Line | Date of service | Place of service | Code | Modifiers | Diagnoses (pointer = code) | Units | Charge (cents) | Rendering NPI |
|---|---|---|---|---|---|---|---|---|
| 1 | 2026-10-06 | 11 | 99213 | (empty) | A = M54.1 | 1 | 19000 | 1000000012 |

**Code lookups:**

- Procedure code 99213: in the code table; policy none; possible categories OFFICE_VISIT_PCP, OFFICE_VISIT_SPECIALIST; Office visit for an existing patient, low-complexity problem
- Place of service 11: Office
- NCCI bypass modifiers: XE, XP, XS, XU

**Field confidences below 1.0** (threshold 0.85, strictly below; A-R9):

- none

**Reference data:**

- Member MBR-G00001: plan PLN-PPO-GOLD, coverage 2026-01-01 to open
- Plan PLN-PPO-GOLD (PPO): filing window 90 days in network, 180 days out of network; out-of-network care covered: yes; referral required for: none; fixed exclusions: none
- Benefit PLN-PPO-GOLD / OFFICE_VISIT_PCP (code 99213): covered yes, prior authorization not required, visit limit none, copay 2500
- Benefit PLN-PPO-GOLD / OFFICE_VISIT_SPECIALIST (code 99213): covered yes, prior authorization not required, visit limit none, copay 5000
- Billing NPI 1000000012: Golden Pcp Provider, PRIMARY_CARE, ENROLLED
- Rendering NPI 1000000012: Golden Pcp Provider, PRIMARY_CARE, ENROLLED
- Network row for billing NPI 1000000012 and plan PLN-PPO-GOLD: in network (A-R1)
- Authorizations for this member: none
- Existing claims for this member: none
- NCCI pairs among the claim's codes: none found
- MUE 99213: at most 2 units per date of service (3 Date of Service Edit: Clinical)

| My outcome (REJECT / DENY / PEND / PASS and reason code; line outcomes if any) | Notes |
|---|---|
| REJECT RJ_INVALID_CODE | "M54.1" is not a valid FY2027 code as written |

### Rules case 6 (R09-01)

Rule it exercises (INSTRUCTIONS.md section 8.3, word for word):

| ID | Rule | Failure outcome | Internal reason code |
|---|---|---|---|
| R09 | Referral: plan requires referral for this provider type and no referring NPI | DENY | `DN_MISSING_REFERRAL` |

**Claim** (source format JSON):

| Field | Value |
|---|---|
| claim_id | GR-R09-01 |
| member_id | MBR-G00002 |
| patient.first_name | Daniel |
| patient.last_name | Okafor |
| patient.date_of_birth | 1975-09-14 |
| patient.sex | M |
| patient.address | 12 Elm St, Austin, TX, 78701 |
| subscriber_is_patient | True |
| billing_npi | 1000000079 |
| billing_tin | 080000007 |
| referring_npi | (null) |
| prior_auth_number | (null) |
| received_date | 2026-10-20 |
| frequency_code | 1 |
| other_coverage | (null) |
| clinical_notes | (empty) |

**Diagnoses:**

| Pointer | Code | In ICD-10-CM FY2027 |
|---|---|---|
| A | R002 | yes: Palpitations |

**Service lines:**

| Line | Date of service | Place of service | Code | Modifiers | Diagnoses (pointer = code) | Units | Charge (cents) | Rendering NPI |
|---|---|---|---|---|---|---|---|---|
| 1 | 2026-10-06 | 11 | 99214 | (empty) | A = R002 | 1 | 27000 | 1000000079 |

**Code lookups:**

- Procedure code 99214: in the code table; policy none; possible categories OFFICE_VISIT_PCP, OFFICE_VISIT_SPECIALIST; Office visit for an existing patient, moderately complex problem
- Place of service 11: Office
- NCCI bypass modifiers: XE, XP, XS, XU

**Field confidences below 1.0** (threshold 0.85, strictly below; A-R9):

- none

**Reference data:**

- Member MBR-G00002: plan PLN-HMO, coverage 2026-01-01 to open
- Plan PLN-HMO (HMO): filing window 90 days in network, 90 days out of network; out-of-network care covered: no; referral required for: ALLERGY_IMMUNOLOGY, CARDIOLOGY, GASTROENTEROLOGY, NEUROLOGY, OPHTHALMOLOGY, PAIN_MEDICINE, PHYSICAL_THERAPY, PLASTIC_SURGERY, PODIATRY, PSYCHOLOGY, RADIOLOGY, SLEEP_MEDICINE, VASCULAR_SURGERY, WOUND_CARE; fixed exclusions: 95044
- Benefit PLN-HMO / OFFICE_VISIT_PCP (code 99214): covered yes, prior authorization not required, visit limit none, copay 2000
- Benefit PLN-HMO / OFFICE_VISIT_SPECIALIST (code 99214): covered yes, prior authorization not required, visit limit none, copay 4000
- Billing NPI 1000000079: Golden Card Provider, CARDIOLOGY, ENROLLED
- Rendering NPI 1000000079: Golden Card Provider, CARDIOLOGY, ENROLLED
- Network row for billing NPI 1000000079 and plan PLN-HMO: in network (A-R1)
- Authorizations for this member: none
- Existing claims for this member: none
- NCCI pairs among the claim's codes: none found
- MUE 99214: at most 2 units per date of service (3 Date of Service Edit: Clinical)

| My outcome (REJECT / DENY / PEND / PASS and reason code; line outcomes if any) | Notes |
|---|---|
| DENY DN_MISSING_REFERRAL | HMO requires referral for cardiology; rendering provider is cardiology; no referring NPI |

### Rules case 7 (P-01)

Rule it exercises (INSTRUCTIONS.md section 8.3, word for word):

Every rule in the section 8.3 table.

**Claim** (source format JSON):

| Field | Value |
|---|---|
| claim_id | GR-P-01 |
| member_id | MBR-G00001 |
| patient.first_name | Asha |
| patient.last_name | Rao |
| patient.date_of_birth | 1981-04-02 |
| patient.sex | F |
| patient.address | 12 Elm St, Austin, TX, 78701 |
| subscriber_is_patient | True |
| billing_npi | 1000000012 |
| billing_tin | 080000001 |
| referring_npi | (null) |
| prior_auth_number | (null) |
| received_date | 2026-10-20 |
| frequency_code | 1 |
| other_coverage | (null) |
| clinical_notes | (empty) |

**Diagnoses:**

| Pointer | Code | In ICD-10-CM FY2027 |
|---|---|---|
| A | M5416 | yes: Radiculopathy, lumbar region |

**Service lines:**

| Line | Date of service | Place of service | Code | Modifiers | Diagnoses (pointer = code) | Units | Charge (cents) | Rendering NPI |
|---|---|---|---|---|---|---|---|---|
| 1 | 2026-10-06 | 11 | 99213 | (empty) | A = M5416 | 1 | 19000 | 1000000012 |

**Code lookups:**

- Procedure code 99213: in the code table; policy none; possible categories OFFICE_VISIT_PCP, OFFICE_VISIT_SPECIALIST; Office visit for an existing patient, low-complexity problem
- Place of service 11: Office
- NCCI bypass modifiers: XE, XP, XS, XU

**Field confidences below 1.0** (threshold 0.85, strictly below; A-R9):

- none

**Reference data:**

- Member MBR-G00001: plan PLN-PPO-GOLD, coverage 2026-01-01 to open
- Plan PLN-PPO-GOLD (PPO): filing window 90 days in network, 180 days out of network; out-of-network care covered: yes; referral required for: none; fixed exclusions: none
- Benefit PLN-PPO-GOLD / OFFICE_VISIT_PCP (code 99213): covered yes, prior authorization not required, visit limit none, copay 2500
- Benefit PLN-PPO-GOLD / OFFICE_VISIT_SPECIALIST (code 99213): covered yes, prior authorization not required, visit limit none, copay 5000
- Billing NPI 1000000012: Golden Pcp Provider, PRIMARY_CARE, ENROLLED
- Rendering NPI 1000000012: Golden Pcp Provider, PRIMARY_CARE, ENROLLED
- Network row for billing NPI 1000000012 and plan PLN-PPO-GOLD: in network (A-R1)
- Authorizations for this member: none
- Existing claims for this member: none
- NCCI pairs among the claim's codes: none found
- MUE 99213: at most 2 units per date of service (3 Date of Service Edit: Clinical)

| My outcome (REJECT / DENY / PEND / PASS and reason code; line outcomes if any) | Notes |
|---|---|
| PASS | every rule passes; status stays RECEIVED (A-R10). Not independent: computed after the sheet leak |

### Rules case 8 (R01-02)

Rule it exercises (INSTRUCTIONS.md section 8.3, word for word):

| ID | Rule | Failure outcome | Internal reason code |
|---|---|---|---|
| R01 | Required fields present | REJECT | `RJ_MISSING_FIELD` |

**Claim** (source format JSON):

| Field | Value |
|---|---|
| claim_id | GR-R01 |
| member_id | MBR-G00001 |
| patient.first_name | Asha |
| patient.last_name | Rao |
| patient.date_of_birth | 1981-04-02 |
| patient.sex | F |
| patient.address | 12 Elm St, Austin, TX, 78701 |
| subscriber_is_patient | True |
| billing_npi | 1000000012 |
| billing_tin | 080000001 |
| referring_npi | (null) |
| prior_auth_number | (null) |
| received_date | 2026-10-20 |
| frequency_code | 1 |
| other_coverage | (null) |
| clinical_notes | (empty) |

**Diagnoses:**

| Pointer | Code | In ICD-10-CM FY2027 |
|---|---|---|
| A | M5416 | yes: Radiculopathy, lumbar region |

**Service lines:**

| Line | Date of service | Place of service | Code | Modifiers | Diagnoses (pointer = code) | Units | Charge (cents) | Rendering NPI |
|---|---|---|---|---|---|---|---|---|
| 1 | 2026-10-06 | 11 | (missing) | (empty) | A = M5416 | 1 | 19000 | 1000000012 |

**Code lookups:**

- Place of service 11: Office
- NCCI bypass modifiers: XE, XP, XS, XU

**Field confidences below 1.0** (threshold 0.85, strictly below; A-R9):

- none

**Reference data:**

- Member MBR-G00001: plan PLN-PPO-GOLD, coverage 2026-01-01 to open
- Plan PLN-PPO-GOLD (PPO): filing window 90 days in network, 180 days out of network; out-of-network care covered: yes; referral required for: none; fixed exclusions: none
- Billing NPI 1000000012: Golden Pcp Provider, PRIMARY_CARE, ENROLLED
- Rendering NPI 1000000012: Golden Pcp Provider, PRIMARY_CARE, ENROLLED
- Network row for billing NPI 1000000012 and plan PLN-PPO-GOLD: in network (A-R1)
- Authorizations for this member: none
- Existing claims for this member: none
- NCCI pairs among the claim's codes: none found

| My outcome (REJECT / DENY / PEND / PASS and reason code; line outcomes if any) | Notes |
|---|---|
| REJECT RJ_MISSING_FIELD | line 1 procedure code missing |

### Rules case 9 (R04-01)

Rule it exercises (INSTRUCTIONS.md section 8.3, word for word):

| ID | Rule | Failure outcome | Internal reason code |
|---|---|---|---|
| R04 | Member ID found | REJECT | `RJ_MEMBER_NOT_FOUND` |

**Claim** (source format JSON):

| Field | Value |
|---|---|
| claim_id | GR-R04-01 |
| member_id | MBR-999999 |
| patient.first_name | Sam |
| patient.last_name | Doe |
| patient.date_of_birth | 1980-01-01 |
| patient.sex | U |
| patient.address | 12 Elm St, Austin, TX, 78701 |
| subscriber_is_patient | True |
| billing_npi | 1000000012 |
| billing_tin | 080000001 |
| referring_npi | (null) |
| prior_auth_number | (null) |
| received_date | 2026-10-20 |
| frequency_code | 1 |
| other_coverage | (null) |
| clinical_notes | (empty) |

**Diagnoses:**

| Pointer | Code | In ICD-10-CM FY2027 |
|---|---|---|
| A | M5416 | yes: Radiculopathy, lumbar region |

**Service lines:**

| Line | Date of service | Place of service | Code | Modifiers | Diagnoses (pointer = code) | Units | Charge (cents) | Rendering NPI |
|---|---|---|---|---|---|---|---|---|
| 1 | 2026-10-06 | 11 | 99213 | (empty) | A = M5416 | 1 | 19000 | 1000000012 |

**Code lookups:**

- Procedure code 99213: in the code table; policy none; possible categories OFFICE_VISIT_PCP, OFFICE_VISIT_SPECIALIST; Office visit for an existing patient, low-complexity problem
- Place of service 11: Office
- NCCI bypass modifiers: XE, XP, XS, XU

**Field confidences below 1.0** (threshold 0.85, strictly below; A-R9):

- none

**Reference data:**

- Member MBR-999999: not in the member records
- Billing NPI 1000000012: Golden Pcp Provider, PRIMARY_CARE, ENROLLED
- Rendering NPI 1000000012: Golden Pcp Provider, PRIMARY_CARE, ENROLLED
- Authorizations for this member: none
- Existing claims for this member: none
- NCCI pairs among the claim's codes: none found
- MUE 99213: at most 2 units per date of service (3 Date of Service Edit: Clinical)

| My outcome (REJECT / DENY / PEND / PASS and reason code; line outcomes if any) | Notes |
|---|---|
| REJECT RJ_MEMBER_NOT_FOUND | MBR-999999 not in member records |

### Rules case 10 (R06-04)

Rule it exercises (INSTRUCTIONS.md section 8.3, word for word):

| ID | Rule | Failure outcome | Internal reason code |
|---|---|---|---|
| R05 | Member eligible on every date of service (coverage start/end) | DENY | `DN_NOT_ELIGIBLE` |
| R06 | Provider enrolled (not found → REJECT; enrollment pending → PEND) | REJECT / PEND | `RJ_PROVIDER_NOT_FOUND` / `PD_PROVIDER_ENROLLMENT` |

**Claim** (source format JSON):

| Field | Value |
|---|---|
| claim_id | GR-R06-04 |
| member_id | MBR-G00006 |
| patient.first_name | Tom |
| patient.last_name | Becker |
| patient.date_of_birth | 1959-01-30 |
| patient.sex | M |
| patient.address | 12 Elm St, Austin, TX, 78701 |
| subscriber_is_patient | True |
| billing_npi | 1000000111 |
| billing_tin | 080000011 |
| referring_npi | (null) |
| prior_auth_number | (null) |
| received_date | 2026-11-12 |
| frequency_code | 1 |
| other_coverage | (null) |
| clinical_notes | (empty) |

**Diagnoses:**

| Pointer | Code | In ICD-10-CM FY2027 |
|---|---|---|
| A | M5416 | yes: Radiculopathy, lumbar region |

**Service lines:**

| Line | Date of service | Place of service | Code | Modifiers | Diagnoses (pointer = code) | Units | Charge (cents) | Rendering NPI |
|---|---|---|---|---|---|---|---|---|
| 1 | 2026-11-05 | 11 | 99213 | (empty) | A = M5416 | 1 | 19000 | 1000000111 |

**Code lookups:**

- Procedure code 99213: in the code table; policy none; possible categories OFFICE_VISIT_PCP, OFFICE_VISIT_SPECIALIST; Office visit for an existing patient, low-complexity problem
- Place of service 11: Office
- NCCI bypass modifiers: XE, XP, XS, XU

**Field confidences below 1.0** (threshold 0.85, strictly below; A-R9):

- none

**Reference data:**

- Member MBR-G00006: plan PLN-PPO-GOLD, coverage 2025-01-01 to 2026-10-31
- Plan PLN-PPO-GOLD (PPO): filing window 90 days in network, 180 days out of network; out-of-network care covered: yes; referral required for: none; fixed exclusions: none
- Benefit PLN-PPO-GOLD / OFFICE_VISIT_PCP (code 99213): covered yes, prior authorization not required, visit limit none, copay 2500
- Benefit PLN-PPO-GOLD / OFFICE_VISIT_SPECIALIST (code 99213): covered yes, prior authorization not required, visit limit none, copay 5000
- Billing NPI 1000000111: Golden Pending Provider, PRIMARY_CARE, PENDING
- Rendering NPI 1000000111: Golden Pending Provider, PRIMARY_CARE, PENDING
- Network row for billing NPI 1000000111 and plan PLN-PPO-GOLD: in network (A-R1)
- Authorizations for this member: none
- Existing claims for this member: none
- NCCI pairs among the claim's codes: none found
- MUE 99213: at most 2 units per date of service (3 Date of Service Edit: Clinical)

| My outcome (REJECT / DENY / PEND / PASS and reason code; line outcomes if any) | Notes |
|---|---|
| DENY DN_NOT_ELIGIBLE (R06 PEND PD_PROVIDER_ENROLLMENT also recorded) | service 2026-11-05 after coverage end 2026-10-31 gives R05 DENY; provider pending gives R06 PEND; DENY beats PEND in Group B |

## Calculator cases (9, seed 42: one per situation)

Situations, in order: copay only; deductible not met; deductible partly met; deductible met; coinsurance; out-of-pocket maximum reached; out-of-network PPO; COB secondary; denied line in a multi-line claim; deductible spans lines.

How the calculator works (INSTRUCTIONS.md section 8.6, word for word):

> Pure functions. Input: approved lines, plan, benefit rows, fee schedule, accumulators, COB data. Use `decimal.Decimal` for intermediate percentage math, `ROUND_HALF_UP` to whole cents, then `int`.

> Per approved line, in service-line order:

### Calculator case 1 (C04)

Steps it exercises (INSTRUCTIONS.md section 8.6, word for word):

> 1. **Allowed amount**: in-network → `min(billed, fee_schedule.inn_allowed_cents)`; out-of-network → `min(billed, fee_schedule.oon_allowed_cents)`.

> 3. **Member cost share** by the benefit's `cost_share_rule`:

> - `COPAY`: copay = min(copay_cents, allowed); deductible does not apply.

> 4. **Out-of-pocket maximum**: member cost share capped at the remaining out-of-pocket amount (separate in-network and out-of-network maximums).

> 5. **Plan pays** = allowed − member cost share.

Assumptions the case names (tests/golden/README.md): none named

- Plan PLN-PPO-GOLD (PPO), IN_NETWORK: deductible 50000, coinsurance 2000 basis points, out-of-pocket maximum 300000 (cents)
- Accumulators before the claim (IN_NETWORK): deductible met 0, out-of-pocket met 0 (cents)

| Benefit category | Cost share rule | Copay (cents) |
|---|---|---|
| OFFICE_VISIT_PCP | COPAY | 2500 |

| Code | Fee in network (cents per unit) | Fee out of network (cents per unit) |
|---|---|---|
| 99213 | 11899 | 9519 |

| Line | Code | Units | Billed (cents) | Decision | Benefit category |
|---|---|---|---|---|---|
| 1 | 99213 | 1 | 9000 | APPROVE | OFFICE_VISIT_PCP |

- Other coverage: none

| Line | Allowed | Deductible applied | Copay | Coinsurance | Plan pays | Member pays |
|---|---|---|---|---|---|---|
| 1 | 9000 | 0 | 2500 | 0 | 6500 | 2500 |

Notes: billed below fee, so allowed = billed

### Calculator case 2 (C10)

Steps it exercises (INSTRUCTIONS.md section 8.6, word for word):

> 1. **Allowed amount**: in-network → `min(billed, fee_schedule.inn_allowed_cents)`; out-of-network → `min(billed, fee_schedule.oon_allowed_cents)`.

> 3. **Member cost share** by the benefit's `cost_share_rule`:

> - `DEDUCTIBLE_COINSURANCE`: deductible applied = min(remaining deductible, allowed); coinsurance = (allowed − deductible applied) × coinsurance_bps ÷ 10000.

> 4. **Out-of-pocket maximum**: member cost share capped at the remaining out-of-pocket amount (separate in-network and out-of-network maximums).

> 5. **Plan pays** = allowed − member cost share.

Assumptions the case names (tests/golden/README.md): none named

- Plan PLN-PPO-GOLD (PPO), IN_NETWORK: deductible 50000, coinsurance 2000 basis points, out-of-pocket maximum 300000 (cents)
- Accumulators before the claim (IN_NETWORK): deductible met 0, out-of-pocket met 0 (cents)

| Benefit category | Cost share rule | Copay (cents) |
|---|---|---|
| ADVANCED_IMAGING | DEDUCTIBLE_COINSURANCE | - |

| Code | Fee in network (cents per unit) | Fee out of network (cents per unit) |
|---|---|---|
| 70551 | 24425 | 19540 |

| Line | Code | Units | Billed (cents) | Decision | Benefit category |
|---|---|---|---|---|---|
| 1 | 70551 | 1 | 39000 | APPROVE | ADVANCED_IMAGING |

- Other coverage: none

| Line | Allowed | Deductible applied | Copay | Coinsurance | Plan pays | Member pays |
|---|---|---|---|---|---|---|
| 1 | 24425 | 24425 | 0 | 0 | 0 | 24425 |

Notes: deductible not met; all of allowed to deductible

### Calculator case 3 (C49)

Steps it exercises (INSTRUCTIONS.md section 8.6, word for word):

> 1. **Allowed amount**: in-network → `min(billed, fee_schedule.inn_allowed_cents)`; out-of-network → `min(billed, fee_schedule.oon_allowed_cents)`.

> 3. **Member cost share** by the benefit's `cost_share_rule`:

> - `DEDUCTIBLE_COINSURANCE`: deductible applied = min(remaining deductible, allowed); coinsurance = (allowed − deductible applied) × coinsurance_bps ÷ 10000.

> 4. **Out-of-pocket maximum**: member cost share capped at the remaining out-of-pocket amount (separate in-network and out-of-network maximums).

> 5. **Plan pays** = allowed − member cost share.

Assumptions the case names (tests/golden/README.md): none named

- Plan PLN-PPO-GOLD (PPO), IN_NETWORK: deductible 50000, coinsurance 2000 basis points, out-of-pocket maximum 300000 (cents)
- Accumulators before the claim (IN_NETWORK): deductible met 25575, out-of-pocket met 25575 (cents)

| Benefit category | Cost share rule | Copay (cents) |
|---|---|---|
| ADVANCED_IMAGING | DEDUCTIBLE_COINSURANCE | - |

| Code | Fee in network (cents per unit) | Fee out of network (cents per unit) |
|---|---|---|
| 70551 | 24425 | 19540 |

| Line | Code | Units | Billed (cents) | Decision | Benefit category |
|---|---|---|---|---|---|
| 1 | 70551 | 1 | 39000 | APPROVE | ADVANCED_IMAGING |

- Other coverage: none

| Line | Allowed | Deductible applied | Copay | Coinsurance | Plan pays | Member pays |
|---|---|---|---|---|---|---|
| 1 | 24425 | 24425 | 0 | 0 | 0 | 24425 |

Notes: remaining deductible 24425 equals allowed

### Calculator case 4 (C30)

Steps it exercises (INSTRUCTIONS.md section 8.6, word for word):

> 1. **Allowed amount**: in-network → `min(billed, fee_schedule.inn_allowed_cents)`; out-of-network → `min(billed, fee_schedule.oon_allowed_cents)`.

> 2. **Contractual adjustment** (in-network) = billed − allowed. **Balance-bill exposure** (out-of-network) = billed − allowed (reported, not paid).

> 3. **Member cost share** by the benefit's `cost_share_rule`:

> - `COPAY`: copay = min(copay_cents, allowed); deductible does not apply.

> - `DEDUCTIBLE_COINSURANCE`: deductible applied = min(remaining deductible, allowed); coinsurance = (allowed − deductible applied) × coinsurance_bps ÷ 10000.

> - Out-of-network lines use the plan's out-of-network deductible and coinsurance.

> 4. **Out-of-pocket maximum**: member cost share capped at the remaining out-of-pocket amount (separate in-network and out-of-network maximums).

> 5. **Plan pays** = allowed − member cost share.

Assumptions the case names (tests/golden/README.md): A3, A9

- Plan PLN-PPO-GOLD (PPO), OUT_OF_NETWORK: deductible 100000, coinsurance 4000 basis points, out-of-pocket maximum 600000 (cents)
- Accumulators before the claim (OUT_OF_NETWORK): deductible met 100000, out-of-pocket met 120000 (cents)

| Benefit category | Cost share rule | Copay (cents) |
|---|---|---|
| OFFICE_VISIT_SPECIALIST | COPAY | 5000 |

| Code | Fee in network (cents per unit) | Fee out of network (cents per unit) |
|---|---|---|
| 99214 | 16951 | 13561 |

| Line | Code | Units | Billed (cents) | Decision | Benefit category |
|---|---|---|---|---|---|
| 1 | 99214 | 1 | 27000 | APPROVE | OFFICE_VISIT_SPECIALIST |

- Other coverage: none

| Line | Allowed | Deductible applied | Copay | Coinsurance | Plan pays | Member pays |
|---|---|---|---|---|---|---|
| 1 | 13561 | 0 | 0 | 5424 | 8137 | 5424 |

Notes: out of network (A3): 40% of 13561 = 5424.4, rounded to 5424; balance-bill 13439 not in member pays (A9)

### Calculator case 5 (C19)

Steps it exercises (INSTRUCTIONS.md section 8.6, word for word):

> 1. **Allowed amount**: in-network → `min(billed, fee_schedule.inn_allowed_cents)`; out-of-network → `min(billed, fee_schedule.oon_allowed_cents)`.

> 3. **Member cost share** by the benefit's `cost_share_rule`:

> - `DEDUCTIBLE_COINSURANCE`: deductible applied = min(remaining deductible, allowed); coinsurance = (allowed − deductible applied) × coinsurance_bps ÷ 10000.

> 4. **Out-of-pocket maximum**: member cost share capped at the remaining out-of-pocket amount (separate in-network and out-of-network maximums).

> 5. **Plan pays** = allowed − member cost share.

Assumptions the case names (tests/golden/README.md): A4

- Plan PLN-PPO-GOLD (PPO), IN_NETWORK: deductible 50000, coinsurance 2000 basis points, out-of-pocket maximum 300000 (cents)
- Accumulators before the claim (IN_NETWORK): deductible met 50000, out-of-pocket met 295000 (cents)

| Benefit category | Cost share rule | Copay (cents) |
|---|---|---|
| ADVANCED_IMAGING | DEDUCTIBLE_COINSURANCE | - |

| Code | Fee in network (cents per unit) | Fee out of network (cents per unit) |
|---|---|---|
| 70553 | 39621 | 31697 |

| Line | Code | Units | Billed (cents) | Decision | Benefit category |
|---|---|---|---|---|---|
| 1 | 70553 | 1 | 60000 | APPROVE | ADVANCED_IMAGING |

- Other coverage: none

| Line | Allowed | Deductible applied | Copay | Coinsurance | Plan pays | Member pays |
|---|---|---|---|---|---|---|
| 1 | 39621 | 0 | 0 | 5000 | 34621 | 5000 |

Notes: 20% = 7924.2 rounded to 7924, capped at remaining out-of-pocket 5000 (A4)

### Calculator case 6 (C21)

Steps it exercises (INSTRUCTIONS.md section 8.6, word for word):

> 1. **Allowed amount**: in-network → `min(billed, fee_schedule.inn_allowed_cents)`; out-of-network → `min(billed, fee_schedule.oon_allowed_cents)`.

> 3. **Member cost share** by the benefit's `cost_share_rule`:

> - `COPAY`: copay = min(copay_cents, allowed); deductible does not apply.

> 4. **Out-of-pocket maximum**: member cost share capped at the remaining out-of-pocket amount (separate in-network and out-of-network maximums).

> 5. **Plan pays** = allowed − member cost share.

Assumptions the case names (tests/golden/README.md): A4

- Plan PLN-PPO-GOLD (PPO), IN_NETWORK: deductible 50000, coinsurance 2000 basis points, out-of-pocket maximum 300000 (cents)
- Accumulators before the claim (IN_NETWORK): deductible met 50000, out-of-pocket met 299000 (cents)

| Benefit category | Cost share rule | Copay (cents) |
|---|---|---|
| OFFICE_VISIT_SPECIALIST | COPAY | 5000 |

| Code | Fee in network (cents per unit) | Fee out of network (cents per unit) |
|---|---|---|
| 99214 | 16951 | 13561 |

| Line | Code | Units | Billed (cents) | Decision | Benefit category |
|---|---|---|---|---|---|
| 1 | 99214 | 1 | 27000 | APPROVE | OFFICE_VISIT_SPECIALIST |

- Other coverage: none

| Line | Allowed | Deductible applied | Copay | Coinsurance | Plan pays | Member pays |
|---|---|---|---|---|---|---|
| 1 | 16951 | 0 | 1000 | 0 | 15951 | 1000 |

Notes: copay 5000 capped at remaining out-of-pocket 1000 (A4)

### Calculator case 7 (C31)

Steps it exercises (INSTRUCTIONS.md section 8.6, word for word):

> 1. **Allowed amount**: in-network → `min(billed, fee_schedule.inn_allowed_cents)`; out-of-network → `min(billed, fee_schedule.oon_allowed_cents)`.

> 2. **Contractual adjustment** (in-network) = billed − allowed. **Balance-bill exposure** (out-of-network) = billed − allowed (reported, not paid).

> 3. **Member cost share** by the benefit's `cost_share_rule`:

> - `DEDUCTIBLE_COINSURANCE`: deductible applied = min(remaining deductible, allowed); coinsurance = (allowed − deductible applied) × coinsurance_bps ÷ 10000.

> - Out-of-network lines use the plan's out-of-network deductible and coinsurance.

> 4. **Out-of-pocket maximum**: member cost share capped at the remaining out-of-pocket amount (separate in-network and out-of-network maximums).

> 5. **Plan pays** = allowed − member cost share.

Assumptions the case names (tests/golden/README.md): A9

- Plan PLN-PPO-SILVER (PPO), OUT_OF_NETWORK: deductible 300000, coinsurance 5000 basis points, out-of-pocket maximum 1100000 (cents)
- Accumulators before the claim (OUT_OF_NETWORK): deductible met 300000, out-of-pocket met 310000 (cents)

| Benefit category | Cost share rule | Copay (cents) |
|---|---|---|
| ADVANCED_IMAGING | DEDUCTIBLE_COINSURANCE | - |

| Code | Fee in network (cents per unit) | Fee out of network (cents per unit) |
|---|---|---|
| 70551 | 24425 | 19540 |

| Line | Code | Units | Billed (cents) | Decision | Benefit category |
|---|---|---|---|---|---|
| 1 | 70551 | 1 | 39000 | APPROVE | ADVANCED_IMAGING |

- Other coverage: none

| Line | Allowed | Deductible applied | Copay | Coinsurance | Plan pays | Member pays |
|---|---|---|---|---|---|---|
| 1 | 19540 | 0 | 0 | 9770 | 9770 | 9770 |

Notes: out-of-network Silver plan, deductible met, 50%

### Calculator case 8 (C41)

Steps it exercises (INSTRUCTIONS.md section 8.6, word for word):

> 1. **Allowed amount**: in-network → `min(billed, fee_schedule.inn_allowed_cents)`; out-of-network → `min(billed, fee_schedule.oon_allowed_cents)`.

> 2. **Contractual adjustment** (in-network) = billed − allowed. **Balance-bill exposure** (out-of-network) = billed − allowed (reported, not paid).

> 3. **Member cost share** by the benefit's `cost_share_rule`:

> - `COPAY`: copay = min(copay_cents, allowed); deductible does not apply.

> - `DEDUCTIBLE_COINSURANCE`: deductible applied = min(remaining deductible, allowed); coinsurance = (allowed − deductible applied) × coinsurance_bps ÷ 10000.

> - Out-of-network lines use the plan's out-of-network deductible and coinsurance.

> 4. **Out-of-pocket maximum**: member cost share capped at the remaining out-of-pocket amount (separate in-network and out-of-network maximums).

> 5. **Plan pays** = allowed − member cost share.

> 6. **COB (our plan secondary)**: secondary pays min(normal plan payment, allowed − primary paid), not below 0; member pays the remainder, not below 0. *(Team default: traditional COB. See `DECISIONS.md`.)*

Assumptions the case names (tests/golden/README.md): A3, A6, A9

- Plan PLN-PPO-GOLD (PPO), OUT_OF_NETWORK: deductible 100000, coinsurance 4000 basis points, out-of-pocket maximum 600000 (cents)
- Accumulators before the claim (OUT_OF_NETWORK): deductible met 100000, out-of-pocket met 100000 (cents)

| Benefit category | Cost share rule | Copay (cents) |
|---|---|---|
| OFFICE_VISIT_SPECIALIST | COPAY | 5000 |

| Code | Fee in network (cents per unit) | Fee out of network (cents per unit) |
|---|---|---|
| 99214 | 16951 | 13561 |

| Line | Code | Units | Billed (cents) | Decision | Benefit category |
|---|---|---|---|---|---|
| 1 | 99214 | 1 | 27000 | APPROVE | OFFICE_VISIT_SPECIALIST |

- Other coverage (our plan is secondary): Northwind Health Plan; primary paid (cents): line 1 6000

| Line | Allowed | Deductible applied | Copay | Coinsurance | Plan pays | Member pays |
|---|---|---|---|---|---|---|
| 1 | 13561 | 0 | 0 | 5424 | 7561 | 0 |

Notes: normal plan payment 8137; secondary pays min(8137, 13561 - 6000 = 7561); member pays 0 (A6)

### Calculator case 9 (C26)

Steps it exercises (INSTRUCTIONS.md section 8.6, word for word):

> 1. **Allowed amount**: in-network → `min(billed, fee_schedule.inn_allowed_cents)`; out-of-network → `min(billed, fee_schedule.oon_allowed_cents)`.

> 3. **Member cost share** by the benefit's `cost_share_rule`:

> - `COPAY`: copay = min(copay_cents, allowed); deductible does not apply.

> - `DEDUCTIBLE_COINSURANCE`: deductible applied = min(remaining deductible, allowed); coinsurance = (allowed − deductible applied) × coinsurance_bps ÷ 10000.

> 4. **Out-of-pocket maximum**: member cost share capped at the remaining out-of-pocket amount (separate in-network and out-of-network maximums).

> 5. **Plan pays** = allowed − member cost share.

> 7. Update **working** accumulators for later lines on the same claim.

> - Denied and pended lines: plan pays 0; no cost share computed.

Assumptions the case names (tests/golden/README.md): A7

- Plan PLN-PPO-GOLD (PPO), IN_NETWORK: deductible 50000, coinsurance 2000 basis points, out-of-pocket maximum 300000 (cents)
- Accumulators before the claim (IN_NETWORK): deductible met 0, out-of-pocket met 0 (cents)

| Benefit category | Cost share rule | Copay (cents) |
|---|---|---|
| DIAGNOSTIC_TESTS | DEDUCTIBLE_COINSURANCE | - |
| OFFICE_VISIT_PCP | COPAY | 2500 |

| Code | Fee in network (cents per unit) | Fee out of network (cents per unit) |
|---|---|---|
| 93306 | 24591 | 19673 |
| 99213 | 11899 | 9519 |

| Line | Code | Units | Billed (cents) | Decision | Benefit category |
|---|---|---|---|---|---|
| 1 | 99213 | 1 | 19000 | APPROVE | OFFICE_VISIT_PCP |
| 2 | 99214 | 1 | 27000 | DENY | - |
| 3 | 93306 | 1 | 39500 | APPROVE | DIAGNOSTIC_TESTS |

- Other coverage: none

| Line | Allowed | Deductible applied | Copay | Coinsurance | Plan pays | Member pays |
|---|---|---|---|---|---|---|
| 1 | 11899 | 0 | 2500 | 0 | 9399 | 2500 |
| 2 | 0 | 0 | 0 | 0 | 0 | 0 |
| 3 | 24591 | 24591 | 0 | 0 | 0 | 24591 |

Notes: line 1: copay; does not touch the deductible / line 2: denied line (A7) / line 3: full deductible still remaining

