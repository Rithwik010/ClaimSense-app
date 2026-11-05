# Golden test spot-check (Task G1)

For one reviewer. Work out each case by hand from the inputs shown, using only the quoted INSTRUCTIONS.md text and the assumptions below, then fill in the blank cells. Amounts are in cents. Mark each assumption and each H5 field mapping ACCEPT or CHANGE.

**Do not open G_spotcheck_answers.csv until every cell is filled.** The same goes for G_golden_checks.csv, which holds the details of the automatic checks with expected amounts.

Estimated time: 90 minutes (10 rules cases x 3 minutes, 10 calculator cases x 6 minutes).

## Automatic checks (134 rules cases, 56 calculator cases)

Findings: violations 0, conflicts with later decisions 5, cases to review against D-RULE-1 32. Only case IDs are shown here, so the sheet stays blind.

| Check | Cases checked | Findings | Cases |
|---|---|---|---|
| Calculator: plan pays + member pays = max(0, allowed - primary paid) | 56 | 0 | - |
| Calculator: allowed <= billed | 56 | 0 | - |
| Calculator: no negative amounts | 56 | 0 | - |
| Calculator: member pays <= remaining out-of-pocket maximum | 56 | 0 | - |
| Calculator: deductible applied <= remaining deductible | 56 | 0 | - |
| Calculator: copay <= allowed | 56 | 0 | - |
| Calculator: denied or pended lines pay 0 | 56 | 0 | - |
| Calculator: integer cents only | 56 | 0 | - |
| Calculator: totals = sum of lines (A8) | 56 | 0 | - |
| Calculator: accumulators after = before + the claim's cost share (A5) | 56 | 0 | - |
| Rules: exactly one expected outcome | 134 | 0 | - |
| Rules: status matches the outcome | 134 | 0 | - |
| Rules: targeted rule exists in section 8.3 | 134 | 0 | - |
| Rules: failure matches section 8.3 | 134 | 0 | - |
| Rules: line number matches the rule's group | 134 | 0 | - |
| Rules: Group A stops the claim | 134 | 0 | - |
| Rules: Group B stops the claim | 134 | 0 | - |
| Rules: outcome follows the group order | 134 | 0 | - |
| Rules: H5: a failure on a low-confidence field becomes REJECT | 134 | 0 | - |
| Rules: H5 applied without a low-confidence field the rule uses | 134 | 0 | - |
| Rules: R14 (D-ESI-3) would deny this ESI line | 134 | 1 | R14-03 (line 1) |
| Rules: R15 (D-DX-1) would deny this line | 134 | 4 | R11-15 (line 1), R11-16 (line 1), R15-03 (line 1), R15-06 (line 1) |
| Rules: D-RULE-1 candidate POL-BH-001.F3 may change this case | 134 | 2 | R20-01, R20-02 |
| Rules: D-RULE-1 candidate POL-DX-001.F7 may change this case | 134 | 1 | R16-01 |
| Rules: D-RULE-1 candidate POL-DX-002.F2 may change this case | 134 | 2 | R17-01, R17-02 |
| Rules: D-RULE-1 candidate POL-DX-002.F3 may change this case | 134 | 2 | R17-01, R17-02 |
| Rules: D-RULE-1 candidate POL-DX-002.F4 may change this case | 134 | 1 | R17-02 |
| Rules: D-RULE-1 candidate POL-IMG-001.F2 may change this case | 134 | 1 | X-04 |
| Rules: D-RULE-1 candidate POL-PAIN-001.F6 may change this case | 134 | 20 | R10-01, R10-02, R10-03, R10-04, R10-05, R10-09, R14-01, R14-02, R14-03, R14-04, R14-05, R14-06, R18-01, R18-02, R18-03, R18-04, R18-05, B-03, X-03, H5-02 |
| Rules: D-RULE-1 candidate POL-PAIN-002.F9 may change this case | 134 | 2 | R19-03, X-01 |
| Rules: D-RULE-1 candidate POL-SURG-003.F4 may change this case | 134 | 1 | X-05 |

D-ESI-1, D-ESI-2 and D-ESI-4 to D-ESI-7 change coverage-criterion labels, which the rules cases do not carry, so they do not apply here; D-ESI-3 is R14 above. Group C is R11-R13 (D8; INSTRUCTIONS.md section 8.3 item 3 now says so).

In total, the first calculator check compares plan pays + member pays with the sum over the approved lines of max(0, allowed - primary paid) (A8). That equals max(0, total allowed - total primary paid) unless one claim has lines where the primary paid more than allowed and lines where it paid less; cases where the two differ: 1.

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
| R11: cases that target it | 28 |
| R12: cases that target it | 9 |
| R13: cases that target it | 5 |
| R14: cases that target it | 7 |
| R15: cases that target it | 8 |
| R16: cases that target it | 2 |
| R17: cases that target it | 2 |
| R18: cases that target it | 6 |
| R19: cases that target it | 3 |
| R20: cases that target it | 2 |
| H5: cases that target it | 10 |
| Clean claim: every rule passes | 1 |
| R06 provider not found -> REJECT | 3 |
| R06 enrollment pending -> PEND | 3 |
| R08 out of network, not covered -> DENY | 3 |
| R08 out of network, covered -> PASS with flag OON | 4 |
| R11 column-2 line denied | 17 |
| R11 bypass modifier -> flag NCCI_BYPASS | 7 |
| H5 on a Group A rule | 2 |
| H5 on a Group B rule | 4 |
| H5 on a Group C rule | 2 |
| Group B: DENY and PEND together (DENY wins) | 2 |
| Group B: REJECT with DENY or PEND (REJECT wins, D8) | 1 |
| Group C: every line denied -> claim DENY | 10 |
| R14 (D-ESI-3): ESI with another block on the same date | 7 |
| R15 (D-DX-1): diagnoses do not satisfy the billing article | 8 |
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
| copay only | 18 |
| deductible not met | 9 |
| deductible partly met | 9 |
| deductible met | 18 |
| coinsurance | 24 |
| out-of-pocket maximum reached | 8 |
| out-of-network PPO | 8 |
| COB secondary | 7 |
| denied line in a multi-line claim | 2 |
| deductible spans lines | 1 |
| copay capped by the allowed amount | 2 |
| billed below the fee schedule | 6 |
| units > 1 | 8 |
| pended line | 2 |
| out-of-network copay category (A3) | 4 |
| COB: primary paid >= allowed | 2 |

## Golden assumptions (tests/golden/README.md, word for word)

| ID | Assumption | ACCEPT / CHANGE | Notes |
|---|---|---|---|
| A-R1 | Network status comes from the billing NPI's `provider_networks` row for the member's plan; no row means out of network. |  |  |
| A-R2 | R06 checks the billing NPI and every rendering NPI. Rules that need a provider record (R07–R10) skip a provider that is not found. |  |  |
| A-R3 | R11 applies to two lines with the same date of service. **Rules v1 (frozen for model v1, `data/curated/ncci_bypass_modifiers.csv`):** XE, XP, XS or XU on either line bypasses an edit with modifier indicator 1. **From `RULES_VERSION` 2.1.0 (D-RULE-8, amending D-GOLD-3):** any NCCI PTP-associated modifier of the 2026 NCCI Policy Manual (Chapter I section E, page I-14; `data/curated/ncci_ptp_modifiers.csv`) bypasses where the manual places it: 59, XE, XP, XS, XU on either line but not on an E&M line; 24, 25, 57 on an E&M line paired with a non-E&M code, 25 only when that code's PFS global period is 000, 010 or XXX (page I-16) and 57 only when it is 090 (page I-13); 58, 78, 79 on a non-E&M line; 27, 91 on either line; anatomic modifiers only when both lines carry one and they share none (page I-17). E&M lines are the in-scope office visit codes. A bypass is PASS with the flag NCCI_BYPASS. |  |  |
| A-R4 | R12 adds the units of the same code on the same date of service (every in-scope code has MUE adjudication indicator 2 or 3, a date-of-service edit) and denies every line of that code and date. |  |  |
| A-R5 | R09 (provider type) and R10 (authorization provider) use each line's rendering NPI. |  |  |
| A-R6 | Duplicate key: member, billing NPI, date of service, procedure code. Existing claims with status REJECTED are ignored. |  |  |
| A-R7 | Group A reports every failure it can detect and stops; Group B evaluates all its rules. |  |  |
| A-R8 | Contract validation errors map to rules: missing field → R01, code format → R02, NPI format or check digit → R03. |  |  |
| A-R9 | `field_confidences` keys are dotted paths with 0-based indexes (`service_lines.0.units`). "Below the threshold" means strictly less than `EXTRACTION_CONFIDENCE_MIN` (0.85). |  |  |
| A-R10 | A claim that passes keeps status RECEIVED and continues to context assembly. |  |  |
| A-R11 | A line failing several Group C rules lists every reason code in rule order (R11, R12, R13). |  |  |
| A1 | The fee schedule amount is per unit: fee for a line = fee x units; allowed = min(billed, fee x units). |  |  |
| A2 | A copay applies to every approved line in a COPAY category (per line, as §8.6 is written), even two lines on one day. |  |  |
| A3 | Out-of-network lines always use the plan's out-of-network deductible and coinsurance, including COPAY categories. |  |  |
| A4 | The out-of-pocket cap is filled in order deductible, copay, coinsurance; the part above the remaining maximum is dropped from the last components first. |  |  |
| A5 | Deductible, copays and coinsurance all count toward the out-of-pocket maximum (D7 covers copays). |  |  |
| A6 | COB: `deductible_cents`, `copay_cents` and `coinsurance_cents` show the normal cost share, and the accumulators grow by it; `plan_pays` = min(normal plan payment, allowed − primary paid), not below 0; `member_pays` = allowed − primary paid − plan pays, not below 0. |  |  |
| A7 | Denied and pended lines appear with `billed_cents` only; every other amount is 0. |  |  |
| A8 | Totals are sums over every line. |  |  |
| A9 | Contractual adjustment (billed − allowed) is in-network only; balance-bill exposure (billed − allowed) is out-of-network only and is not part of `member_pays`. |  |  |

## H5 field mapping used by the automatic checks

A failing rule becomes REJECT (H5) when one of these fields was read below 0.85.

| Rule | Fields used | Section 8.3 text it was read from | ACCEPT / CHANGE | Notes |
|---|---|---|---|---|
| R01 | the missing field itself (the cases do not name it, so not checked) | Required fields present |  |  |
| R02 | diagnoses, service_lines.*.procedure_code, service_lines.*.place_of_service, service_lines.*.modifiers, service_lines.*.date_of_service | Codes valid: ICD-10-CM for the date-of-service fiscal year, procedure code in code table, place-of-service code, modifier format |  |  |
| R03 | billing_npi, service_lines.*.rendering_npi, referring_npi | NPI check digits valid (billing, rendering, referring) |  |  |
| R04 | member_id | Member ID found |  |  |
| DUP | member_id, billing_npi, service_lines.*.date_of_service, service_lines.*.procedure_code | same member, provider, date of service, procedure code as an existing claim |  |  |
| R05 | member_id, service_lines.*.date_of_service | Member eligible on every date of service (coverage start/end) |  |  |
| R06 | billing_npi, service_lines.*.rendering_npi | Provider enrolled (not found → REJECT; enrollment pending → PEND) |  |  |
| R07 | received_date, service_lines.*.date_of_service, billing_npi | Timely filing: received date − last date of service ≤ plan window (in-network vs out-of-network window from plan config) |  |  |
| R08 | billing_npi, member_id | Network: out-of-network and plan does not cover out-of-network → DENY; covered → PASS with flag `OON` |  |  |
| R09 | referring_npi, service_lines.*.rendering_npi | Referral: plan requires referral for this provider type and no referring NPI |  |  |
| R10 | member_id, service_lines.*.procedure_code, service_lines.*.rendering_npi, service_lines.*.date_of_service | Prior authorization: code requires auth per plan benefits, and no matching auth (member, provider, code, date range) |  |  |
| R11 | service_lines.*.procedure_code, service_lines.*.modifiers, service_lines.*.date_of_service | NCCI procedure-to-procedure pair on the same claim: if the pair allows a bypass (modifier indicator 1) and an NCCI PTP-associated modifier is reported where the 2026 NCCI Policy Manual places it (D-RULE-8, `data/curated/ncci_ptp_modifiers.csv`: 59 and X modifiers not on an E&M line; 24, 25, 57 on an E&M paired with a procedure, 25 with a 000/010/XXX global period, 57 with 090; 58, 78, 79 on a procedure; 27, 91 on either line; anatomic modifiers on both lines for different sites) → PASS with flag `NCCI_BYPASS` (the model and the reviewer check the documentation); otherwise deny the column-2 line |  |  |
| R12 | service_lines.*.units, service_lines.*.procedure_code, service_lines.*.date_of_service (the failing line only) | Units exceed the medically unlikely edit limit |  |  |
| R13 | service_lines.*.procedure_code, member_id (the failing line only) | Procedure code on the plan's fixed exclusion list |  |  |

## Rules cases (10, seed 42)

How the rules apply (INSTRUCTIONS.md section 8.3, word for word):

> 1. **Group A (data integrity)**: R01–R04. If any fails → claim outcome **REJECT**; stop.
> 2. **Group B (hard requirements)**: R05–R10. Evaluate **all**, record every failure. Outcome precedence: DENY over PEND. Any failure → claim stops with that outcome.
> 3. **Group C (line level)**: R11–R13, then rules v2 R14–R20 (P2.3b; D-RULE-2 to D-RULE-7). Every rule runs on every line; a line's reason codes and flags are listed in rule order and the first reason is the primary one. A failing line is denied; the claim continues with the remaining lines. If every line is denied → claim outcome DENY. A flag never denies: a rule denies only when the LCD or article is explicit and the check needs nothing beyond the claim; a limit worded "usually" or with a documented exception gives a flag for the model and the reviewer.
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
|  |  |

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
|  |  |

### Rules case 3 (R07-04)

Rule it exercises (INSTRUCTIONS.md section 8.3, word for word):

| ID | Rule | Failure outcome | Internal reason code |
|---|---|---|---|
| R07 | Timely filing: received date − last date of service ≤ plan window (in-network vs out-of-network window from plan config) | DENY | `DN_LATE_FILING` |
| R08 | Network: out-of-network and plan does not cover out-of-network → DENY; covered → PASS with flag `OON` | DENY | `DN_OUT_OF_NETWORK` |

**Claim** (source format JSON):

| Field | Value |
|---|---|
| claim_id | GR-R07-04 |
| member_id | MBR-G00001 |
| patient.first_name | Asha |
| patient.last_name | Rao |
| patient.date_of_birth | 1981-04-02 |
| patient.sex | F |
| patient.address | 12 Elm St, Austin, TX, 78701 |
| subscriber_is_patient | True |
| billing_npi | 1000000103 |
| billing_tin | 080000010 |
| referring_npi | (null) |
| prior_auth_number | (null) |
| received_date | 2027-04-05 |
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
| 1 | 2026-10-06 | 11 | 99213 | (empty) | A = M5416 | 1 | 19000 | 1000000103 |

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
- Billing NPI 1000000103: Golden Oon Pcp Provider, PRIMARY_CARE, ENROLLED
- Rendering NPI 1000000103: Golden Oon Pcp Provider, PRIMARY_CARE, ENROLLED
- Network row for billing NPI 1000000103 and plan PLN-PPO-GOLD: out of network (A-R1)
- Authorizations for this member: none
- Existing claims for this member: none
- NCCI pairs among the claim's codes: none found
- MUE 99213: at most 2 units per date of service (3 Date of Service Edit: Clinical)

| My outcome (REJECT / DENY / PEND / PASS and reason code; line outcomes if any) | Notes |
|---|---|
|  |  |

### Rules case 4 (R06-02)

Rule it exercises (INSTRUCTIONS.md section 8.3, word for word):

| ID | Rule | Failure outcome | Internal reason code |
|---|---|---|---|
| R06 | Provider enrolled (not found → REJECT; enrollment pending → PEND) | REJECT / PEND | `RJ_PROVIDER_NOT_FOUND` / `PD_PROVIDER_ENROLLMENT` |

**Claim** (source format JSON):

| Field | Value |
|---|---|
| claim_id | GR-R06-02 |
| member_id | MBR-G00001 |
| patient.first_name | Asha |
| patient.last_name | Rao |
| patient.date_of_birth | 1981-04-02 |
| patient.sex | F |
| patient.address | 12 Elm St, Austin, TX, 78701 |
| subscriber_is_patient | True |
| billing_npi | 1000000111 |
| billing_tin | 080000011 |
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
| 1 | 2026-10-06 | 11 | 99213 | (empty) | A = M5416 | 1 | 19000 | 1000000111 |

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
- Billing NPI 1000000111: Golden Pending Provider, PRIMARY_CARE, PENDING
- Rendering NPI 1000000111: Golden Pending Provider, PRIMARY_CARE, PENDING
- Network row for billing NPI 1000000111 and plan PLN-PPO-GOLD: in network (A-R1)
- Authorizations for this member: none
- Existing claims for this member: none
- NCCI pairs among the claim's codes: none found
- MUE 99213: at most 2 units per date of service (3 Date of Service Edit: Clinical)

| My outcome (REJECT / DENY / PEND / PASS and reason code; line outcomes if any) | Notes |
|---|---|
|  |  |

### Rules case 5 (R18-01)

Rule it exercises (INSTRUCTIONS.md section 8.3, word for word):

| ID | Rule | Failure outcome | Internal reason code |
|---|---|---|---|
| R18 | Transforaminal ESI levels per date above 2 on a side deny the add-on lines on that side (an RT or LT line counts on its side, modifier 50 or no side modifier on both; each unit of an add-on level code is one level, the primary code the first); an interlaminar or caudal ESI with modifier 50 | Line DENY | `DN_ESI_LEVELS` |

**Claim** (source format JSON):

| Field | Value |
|---|---|
| claim_id | GR-R18-01 |
| member_id | MBR-G00001 |
| patient.first_name | Jordan |
| patient.last_name | Lee |
| patient.date_of_birth | 1970-05-14 |
| patient.sex | F |
| patient.address | 12 Elm St, Austin, TX, 78701 |
| subscriber_is_patient | True |
| billing_npi | 1000000020 |
| billing_tin | 080000009 |
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
| 1 | 2026-10-06 | 11 | 62323 | 50 | A = M5416 | 1 | 50000 | 1000000020 |

**Code lookups:**

- Procedure code 62323: in the code table; policy POL-PAIN-001; possible categories PAIN_MANAGEMENT; Epidural steroid injection between the vertebrae, lower back, with imaging guidance
- Place of service 11: Office
- NCCI bypass modifiers: XE, XP, XS, XU

**Field confidences below 1.0** (threshold 0.85, strictly below; A-R9):

- none

**Reference data:**

- Member MBR-G00001: plan PLN-PPO-GOLD, coverage 2026-01-01 to open
- Plan PLN-PPO-GOLD (PPO): filing window 90 days in network, 180 days out of network; out-of-network care covered: yes; referral required for: none; fixed exclusions: none
- Benefit PLN-PPO-GOLD / PAIN_MANAGEMENT (code 62323): covered yes, prior authorization required, visit limit none, DEDUCTIBLE_COINSURANCE
- Billing NPI 1000000020: Golden Pain Provider, PAIN_MEDICINE, ENROLLED
- Rendering NPI 1000000020: Golden Pain Provider, PAIN_MEDICINE, ENROLLED
- Network row for billing NPI 1000000020 and plan PLN-PPO-GOLD: in network (A-R1)
- Authorization AUTH-R18-01-1: provider 1000000020, code 62323, 2026-10-01 to 2026-12-31, units no limit
- Existing claims for this member: none
- NCCI pairs among the claim's codes: none found
- MUE 62323: at most 1 unit per date of service (3 Date of Service Edit: Clinical)

| My outcome (REJECT / DENY / PEND / PASS and reason code; line outcomes if any) | Notes |
|---|---|
|  |  |

### Rules case 6 (R03-01)

Rule it exercises (INSTRUCTIONS.md section 8.3, word for word):

| ID | Rule | Failure outcome | Internal reason code |
|---|---|---|---|
| R03 | NPI check digits valid (billing, rendering, referring) | REJECT | `RJ_INVALID_NPI` |

**Claim** (source format JSON):

| Field | Value |
|---|---|
| claim_id | GR-R03-01 |
| member_id | MBR-G00001 |
| patient.first_name | Asha |
| patient.last_name | Rao |
| patient.date_of_birth | 1981-04-02 |
| patient.sex | F |
| patient.address | 12 Elm St, Austin, TX, 78701 |
| subscriber_is_patient | True |
| billing_npi | 1234567890 |
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
- Billing NPI 1234567890: not in the provider records
- Rendering NPI 1000000012: Golden Pcp Provider, PRIMARY_CARE, ENROLLED
- Network row for billing NPI 1234567890 and plan PLN-PPO-GOLD: no row (A-R1)
- Authorizations for this member: none
- Existing claims for this member: none
- NCCI pairs among the claim's codes: none found
- MUE 99213: at most 2 units per date of service (3 Date of Service Edit: Clinical)

| My outcome (REJECT / DENY / PEND / PASS and reason code; line outcomes if any) | Notes |
|---|---|
|  |  |

### Rules case 7 (R02-01)

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
|  |  |

### Rules case 8 (R09-02)

Rule it exercises (INSTRUCTIONS.md section 8.3, word for word):

| ID | Rule | Failure outcome | Internal reason code |
|---|---|---|---|
| R09 | Referral: plan requires referral for this provider type and no referring NPI | DENY | `DN_MISSING_REFERRAL` |

**Claim** (source format JSON):

| Field | Value |
|---|---|
| claim_id | GR-R09-02 |
| member_id | MBR-G00002 |
| patient.first_name | Daniel |
| patient.last_name | Okafor |
| patient.date_of_birth | 1975-09-14 |
| patient.sex | M |
| patient.address | 12 Elm St, Austin, TX, 78701 |
| subscriber_is_patient | True |
| billing_npi | 1000000079 |
| billing_tin | 080000007 |
| referring_npi | 1000000012 |
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
- Referring NPI 1000000012: Golden Pcp Provider, PRIMARY_CARE, ENROLLED
- Network row for billing NPI 1000000079 and plan PLN-HMO: in network (A-R1)
- Authorizations for this member: none
- Existing claims for this member: none
- NCCI pairs among the claim's codes: none found
- MUE 99214: at most 2 units per date of service (3 Date of Service Edit: Clinical)

| My outcome (REJECT / DENY / PEND / PASS and reason code; line outcomes if any) | Notes |
|---|---|
|  |  |

### Rules case 9 (R11-07)

Rule it exercises (INSTRUCTIONS.md section 8.3, word for word):

| ID | Rule | Failure outcome | Internal reason code |
|---|---|---|---|
| R11 | NCCI procedure-to-procedure pair on the same claim: if the pair allows a bypass (modifier indicator 1) and an NCCI PTP-associated modifier is reported where the 2026 NCCI Policy Manual places it (D-RULE-8, `data/curated/ncci_ptp_modifiers.csv`: 59 and X modifiers not on an E&M line; 24, 25, 57 on an E&M paired with a procedure, 25 with a 000/010/XXX global period, 57 with 090; 58, 78, 79 on a procedure; 27, 91 on either line; anatomic modifiers on both lines for different sites) → PASS with flag `NCCI_BYPASS` (the model and the reviewer check the documentation); otherwise deny the column-2 line | Line DENY | `DN_NCCI_BUNDLED` |

**Claim** (source format JSON):

| Field | Value |
|---|---|
| claim_id | GR-R11-07 |
| member_id | MBR-G00001 |
| patient.first_name | Asha |
| patient.last_name | Rao |
| patient.date_of_birth | 1981-04-02 |
| patient.sex | F |
| patient.address | 12 Elm St, Austin, TX, 78701 |
| subscriber_is_patient | True |
| billing_npi | 1000000053 |
| billing_tin | 080000005 |
| referring_npi | (null) |
| prior_auth_number | (null) |
| received_date | 2026-10-20 |
| frequency_code | 1 |
| other_coverage | (null) |
| clinical_notes | (empty) |

**Diagnoses:**

| Pointer | Code | In ICD-10-CM FY2027 |
|---|---|---|
| A | L97412 | yes: Non-pressure chronic ulcer of right heel and midfoot with fat layer exposed |

**Service lines:**

| Line | Date of service | Place of service | Code | Modifiers | Diagnoses (pointer = code) | Units | Charge (cents) | Rendering NPI |
|---|---|---|---|---|---|---|---|---|
| 1 | 2026-10-06 | 11 | 97597 | (empty) | A = L97412 | 1 | 20500 | 1000000053 |
| 2 | 2026-10-06 | 11 | 11042 | (empty) | A = L97412 | 1 | 26500 | 1000000053 |

**Code lookups:**

- Procedure code 11042: in the code table; policy POL-WOUND-001; possible categories MINOR_PROCEDURES; Removal of dead tissue from a wound down to the fat layer, first 20 square cm or less
- Procedure code 97597: in the code table; policy POL-WOUND-001; possible categories MINOR_PROCEDURES; Selective removal of dead tissue from an open wound, first 20 square cm or less
- Place of service 11: Office
- NCCI bypass modifiers: XE, XP, XS, XU

**Field confidences below 1.0** (threshold 0.85, strictly below; A-R9):

- none

**Reference data:**

- Member MBR-G00001: plan PLN-PPO-GOLD, coverage 2026-01-01 to open
- Plan PLN-PPO-GOLD (PPO): filing window 90 days in network, 180 days out of network; out-of-network care covered: yes; referral required for: none; fixed exclusions: none
- Benefit PLN-PPO-GOLD / MINOR_PROCEDURES (code 11042): covered yes, prior authorization not required, visit limit none, DEDUCTIBLE_COINSURANCE
- Benefit PLN-PPO-GOLD / MINOR_PROCEDURES (code 97597): covered yes, prior authorization not required, visit limit none, DEDUCTIBLE_COINSURANCE
- Billing NPI 1000000053: Golden Wound Provider, WOUND_CARE, ENROLLED
- Rendering NPI 1000000053: Golden Wound Provider, WOUND_CARE, ENROLLED
- Network row for billing NPI 1000000053 and plan PLN-PPO-GOLD: in network (A-R1)
- Authorizations for this member: none
- Existing claims for this member: none
- NCCI pair 11042 / 97597 (column-2 code 97597): modifier indicator 1, effective 2005-01-01
- MUE 11042: at most 1 unit per date of service (2 Date of Service Edit: Policy)
- MUE 97597: at most 1 unit per date of service (3 Date of Service Edit: Clinical)

| My outcome (REJECT / DENY / PEND / PASS and reason code; line outcomes if any) | Notes |
|---|---|
|  |  |

### Rules case 10 (R19-03)

Rule it exercises (INSTRUCTIONS.md section 8.3, word for word):

| ID | Rule | Failure outcome | Internal reason code |
|---|---|---|---|
| R19 | Third-level facet code (64492, 64495) → DENY; facet codes of both spinal regions on one date → PASS with flag `FACET_TWO_REGIONS` | Line DENY / Flag | `DN_FACET_LEVELS` |

**Claim** (source format JSON):

| Field | Value |
|---|---|
| claim_id | GR-R19-03 |
| member_id | MBR-G00001 |
| patient.first_name | Jordan |
| patient.last_name | Lee |
| patient.date_of_birth | 1970-05-14 |
| patient.sex | F |
| patient.address | 12 Elm St, Austin, TX, 78701 |
| subscriber_is_patient | True |
| billing_npi | 1000000020 |
| billing_tin | 080000009 |
| referring_npi | (null) |
| prior_auth_number | (null) |
| received_date | 2026-10-20 |
| frequency_code | 1 |
| other_coverage | (null) |
| clinical_notes | (empty) |

**Diagnoses:**

| Pointer | Code | In ICD-10-CM FY2027 |
|---|---|---|
| A | M47812 | yes: Spondylosis without myelopathy or radiculopathy, cervical region |
| B | M47816 | yes: Spondylosis without myelopathy or radiculopathy, lumbar region |

**Service lines:**

| Line | Date of service | Place of service | Code | Modifiers | Diagnoses (pointer = code) | Units | Charge (cents) | Rendering NPI |
|---|---|---|---|---|---|---|---|---|
| 1 | 2026-10-06 | 11 | 64490 | (empty) | A = M47812 | 1 | 50000 | 1000000020 |
| 2 | 2026-10-06 | 11 | 64493 | (empty) | B = M47816 | 1 | 50000 | 1000000020 |

**Code lookups:**

- Procedure code 64490: in the code table; policy POL-PAIN-002; possible categories PAIN_MANAGEMENT; Facet joint nerve block injection, neck or upper back, first level
- Procedure code 64493: in the code table; policy POL-PAIN-002; possible categories PAIN_MANAGEMENT; Facet joint nerve block injection, lower back, first level
- Place of service 11: Office
- NCCI bypass modifiers: XE, XP, XS, XU

**Field confidences below 1.0** (threshold 0.85, strictly below; A-R9):

- none

**Reference data:**

- Member MBR-G00001: plan PLN-PPO-GOLD, coverage 2026-01-01 to open
- Plan PLN-PPO-GOLD (PPO): filing window 90 days in network, 180 days out of network; out-of-network care covered: yes; referral required for: none; fixed exclusions: none
- Benefit PLN-PPO-GOLD / PAIN_MANAGEMENT (code 64490): covered yes, prior authorization required, visit limit none, DEDUCTIBLE_COINSURANCE
- Benefit PLN-PPO-GOLD / PAIN_MANAGEMENT (code 64493): covered yes, prior authorization required, visit limit none, DEDUCTIBLE_COINSURANCE
- Billing NPI 1000000020: Golden Pain Provider, PAIN_MEDICINE, ENROLLED
- Rendering NPI 1000000020: Golden Pain Provider, PAIN_MEDICINE, ENROLLED
- Network row for billing NPI 1000000020 and plan PLN-PPO-GOLD: in network (A-R1)
- Authorization AUTH-R19-03-1: provider 1000000020, code 64490, 2026-10-01 to 2026-12-31, units no limit
- Authorization AUTH-R19-03-2: provider 1000000020, code 64493, 2026-10-01 to 2026-12-31, units no limit
- Existing claims for this member: none
- NCCI pairs among the claim's codes: none found
- MUE 64490: at most 1 unit per date of service (2 Date of Service Edit: Policy)
- MUE 64493: at most 1 unit per date of service (2 Date of Service Edit: Policy)

| My outcome (REJECT / DENY / PEND / PASS and reason code; line outcomes if any) | Notes |
|---|---|
|  |  |

## Calculator cases (10, seed 42: one per situation)

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
| 1 |  |  |  |  |  |  |

Notes:

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
| 1 |  |  |  |  |  |  |

Notes:

### Calculator case 3 (C39)

Steps it exercises (INSTRUCTIONS.md section 8.6, word for word):

> 1. **Allowed amount**: in-network → `min(billed, fee_schedule.inn_allowed_cents)`; out-of-network → `min(billed, fee_schedule.oon_allowed_cents)`.

> 3. **Member cost share** by the benefit's `cost_share_rule`:

> - `DEDUCTIBLE_COINSURANCE`: deductible applied = min(remaining deductible, allowed); coinsurance = (allowed − deductible applied) × coinsurance_bps ÷ 10000.

> 4. **Out-of-pocket maximum**: member cost share capped at the remaining out-of-pocket amount (separate in-network and out-of-network maximums).

> 5. **Plan pays** = allowed − member cost share.

> 6. **COB (our plan secondary)**: secondary pays min(normal plan payment, allowed − primary paid), not below 0; member pays the remainder, not below 0. *(Team default: traditional COB. See `DECISIONS.md`.)*

Assumptions the case names (tests/golden/README.md): A6

- Plan PLN-PPO-GOLD (PPO), IN_NETWORK: deductible 50000, coinsurance 2000 basis points, out-of-pocket maximum 300000 (cents)
- Accumulators before the claim (IN_NETWORK): deductible met 20000, out-of-pocket met 20000 (cents)

| Benefit category | Cost share rule | Copay (cents) |
|---|---|---|
| ADVANCED_IMAGING | DEDUCTIBLE_COINSURANCE | - |

| Code | Fee in network (cents per unit) | Fee out of network (cents per unit) |
|---|---|---|
| 70551 | 24425 | 19540 |

| Line | Code | Units | Billed (cents) | Decision | Benefit category |
|---|---|---|---|---|---|
| 1 | 70551 | 1 | 39000 | APPROVE | ADVANCED_IMAGING |

- Other coverage (our plan is secondary): Northwind Health Plan; primary paid (cents): line 1 15000

| Line | Allowed | Deductible applied | Copay | Coinsurance | Plan pays | Member pays |
|---|---|---|---|---|---|---|
| 1 |  |  |  |  |  |  |

Notes:

### Calculator case 4 (C25)

Steps it exercises (INSTRUCTIONS.md section 8.6, word for word):

> 1. **Allowed amount**: in-network → `min(billed, fee_schedule.inn_allowed_cents)`; out-of-network → `min(billed, fee_schedule.oon_allowed_cents)`.

> 3. **Member cost share** by the benefit's `cost_share_rule`:

> - `COPAY`: copay = min(copay_cents, allowed); deductible does not apply.

> - `DEDUCTIBLE_COINSURANCE`: deductible applied = min(remaining deductible, allowed); coinsurance = (allowed − deductible applied) × coinsurance_bps ÷ 10000.

> 4. **Out-of-pocket maximum**: member cost share capped at the remaining out-of-pocket amount (separate in-network and out-of-network maximums).

> 5. **Plan pays** = allowed − member cost share.

> 7. Update **working** accumulators for later lines on the same claim.

Assumptions the case names (tests/golden/README.md): A4

- Plan PLN-PPO-SILVER (PPO), IN_NETWORK: deductible 150000, coinsurance 3000 basis points, out-of-pocket maximum 550000 (cents)
- Accumulators before the claim (IN_NETWORK): deductible met 150000, out-of-pocket met 540000 (cents)

| Benefit category | Cost share rule | Copay (cents) |
|---|---|---|
| ADVANCED_IMAGING | DEDUCTIBLE_COINSURANCE | - |
| DIAGNOSTIC_TESTS | DEDUCTIBLE_COINSURANCE | - |
| OFFICE_VISIT_SPECIALIST | COPAY | 7500 |

| Code | Fee in network (cents per unit) | Fee out of network (cents per unit) |
|---|---|---|
| 70553 | 39621 | 31697 |
| 93306 | 24591 | 19673 |
| 99214 | 16951 | 13561 |

| Line | Code | Units | Billed (cents) | Decision | Benefit category |
|---|---|---|---|---|---|
| 1 | 70553 | 1 | 60000 | APPROVE | ADVANCED_IMAGING |
| 2 | 99214 | 1 | 27000 | APPROVE | OFFICE_VISIT_SPECIALIST |
| 3 | 93306 | 1 | 39500 | APPROVE | DIAGNOSTIC_TESTS |

- Other coverage: none

| Line | Allowed | Deductible applied | Copay | Coinsurance | Plan pays | Member pays |
|---|---|---|---|---|---|---|
| 1 |  |  |  |  |  |  |
| 2 |  |  |  |  |  |  |
| 3 |  |  |  |  |  |  |

Notes:

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
| 1 |  |  |  |  |  |  |

Notes:

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
| 1 |  |  |  |  |  |  |

Notes:

### Calculator case 7 (C30)

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
| 1 |  |  |  |  |  |  |

Notes:

### Calculator case 8 (C55)

Steps it exercises (INSTRUCTIONS.md section 8.6, word for word):

> 1. **Allowed amount**: in-network → `min(billed, fee_schedule.inn_allowed_cents)`; out-of-network → `min(billed, fee_schedule.oon_allowed_cents)`.

> 3. **Member cost share** by the benefit's `cost_share_rule`:

> - `DEDUCTIBLE_COINSURANCE`: deductible applied = min(remaining deductible, allowed); coinsurance = (allowed − deductible applied) × coinsurance_bps ÷ 10000.

> 4. **Out-of-pocket maximum**: member cost share capped at the remaining out-of-pocket amount (separate in-network and out-of-network maximums).

> 5. **Plan pays** = allowed − member cost share.

> 6. **COB (our plan secondary)**: secondary pays min(normal plan payment, allowed − primary paid), not below 0; member pays the remainder, not below 0. *(Team default: traditional COB. See `DECISIONS.md`.)*

> 7. Update **working** accumulators for later lines on the same claim.

Assumptions the case names (tests/golden/README.md): A6

- Plan PLN-HDHP (PPO), IN_NETWORK: deductible 320000, coinsurance 1000 basis points, out-of-pocket maximum 650000 (cents)
- Accumulators before the claim (IN_NETWORK): deductible met 300000, out-of-pocket met 300000 (cents)

| Benefit category | Cost share rule | Copay (cents) |
|---|---|---|
| DIAGNOSTIC_TESTS | DEDUCTIBLE_COINSURANCE | - |
| OFFICE_VISIT_SPECIALIST | DEDUCTIBLE_COINSURANCE | - |

| Code | Fee in network (cents per unit) | Fee out of network (cents per unit) |
|---|---|---|
| 93306 | 24591 | 19673 |
| 99214 | 16951 | 13561 |

| Line | Code | Units | Billed (cents) | Decision | Benefit category |
|---|---|---|---|---|---|
| 1 | 93306 | 1 | 41000 | APPROVE | DIAGNOSTIC_TESTS |
| 2 | 99214 | 1 | 27000 | APPROVE | OFFICE_VISIT_SPECIALIST |

- Other coverage (our plan is secondary): Northwind Health Plan; primary paid (cents): line 1 30000

| Line | Allowed | Deductible applied | Copay | Coinsurance | Plan pays | Member pays |
|---|---|---|---|---|---|---|
| 1 |  |  |  |  |  |  |
| 2 |  |  |  |  |  |  |

Notes:

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
| 1 |  |  |  |  |  |  |
| 2 |  |  |  |  |  |  |
| 3 |  |  |  |  |  |  |

Notes:

### Calculator case 10 (C53)

Steps it exercises (INSTRUCTIONS.md section 8.6, word for word):

> 1. **Allowed amount**: in-network → `min(billed, fee_schedule.inn_allowed_cents)`; out-of-network → `min(billed, fee_schedule.oon_allowed_cents)`.

> 3. **Member cost share** by the benefit's `cost_share_rule`:

> - `DEDUCTIBLE_COINSURANCE`: deductible applied = min(remaining deductible, allowed); coinsurance = (allowed − deductible applied) × coinsurance_bps ÷ 10000.

> 4. **Out-of-pocket maximum**: member cost share capped at the remaining out-of-pocket amount (separate in-network and out-of-network maximums).

> 5. **Plan pays** = allowed − member cost share.

> 7. Update **working** accumulators for later lines on the same claim.

Assumptions the case names (tests/golden/README.md): none named

- Plan PLN-PPO-SILVER (PPO), IN_NETWORK: deductible 150000, coinsurance 3000 basis points, out-of-pocket maximum 550000 (cents)
- Accumulators before the claim (IN_NETWORK): deductible met 120000, out-of-pocket met 120000 (cents)

| Benefit category | Cost share rule | Copay (cents) |
|---|---|---|
| ADVANCED_IMAGING | DEDUCTIBLE_COINSURANCE | - |
| DIAGNOSTIC_TESTS | DEDUCTIBLE_COINSURANCE | - |

| Code | Fee in network (cents per unit) | Fee out of network (cents per unit) |
|---|---|---|
| 70553 | 39621 | 31697 |
| 93306 | 24591 | 19673 |

| Line | Code | Units | Billed (cents) | Decision | Benefit category |
|---|---|---|---|---|---|
| 1 | 93306 | 1 | 41000 | APPROVE | DIAGNOSTIC_TESTS |
| 2 | 70553 | 1 | 60000 | APPROVE | ADVANCED_IMAGING |

- Other coverage: none

| Line | Allowed | Deductible applied | Copay | Coinsurance | Plan pays | Member pays |
|---|---|---|---|---|---|---|
| 1 |  |  |  |  |  |  |
| 2 |  |  |  |  |  |  |

Notes:

