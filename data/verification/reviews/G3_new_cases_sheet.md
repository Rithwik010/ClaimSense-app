# New calculator golden cases: independent check (Task G3)

For one reviewer, or a separate Claude chat that sees only this sheet (D-GOLD-2). Work out each case by hand from the inputs shown, using only the quoted INSTRUCTIONS.md text and the assumptions below, then fill in the blank cells. Amounts are in cents.

**Do not open data/generated/verification/new_golden/ until every cell is filled.**

Estimated time: 24 minutes (4 calculator cases x 6 minutes).

## Assumptions (tests/golden/README.md, word for word; they apply to every case)

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

## Calculator cases (4)

How the calculator works (INSTRUCTIONS.md section 8.6, word for word):

> Pure functions. Input: approved lines, plan, benefit rows, fee schedule, accumulators, COB data. Use `decimal.Decimal` for intermediate percentage math, `ROUND_HALF_UP` to whole cents, then `int`.

> Per approved line, in service-line order:

### Calculator case 1 (C53)

Steps it exercises (INSTRUCTIONS.md section 8.6, word for word):

> 1. **Allowed amount**: in-network → `min(billed, fee_schedule.inn_allowed_cents)`; out-of-network → `min(billed, fee_schedule.oon_allowed_cents)`.

> 3. **Member cost share** by the benefit's `cost_share_rule`:

> - `DEDUCTIBLE_COINSURANCE`: deductible applied = min(remaining deductible, allowed); coinsurance = (allowed − deductible applied) × coinsurance_bps ÷ 10000.

> 4. **Out-of-pocket maximum**: member cost share capped at the remaining out-of-pocket amount (separate in-network and out-of-network maximums).

> 5. **Plan pays** = allowed − member cost share.

> 7. Update **working** accumulators for later lines on the same claim.

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
| 1 | 24591 | 24591 | 0 | 0 | 0 | 24591 |
| 2 | 39621 | 5409 | 0 | 10264 | 23948 | 15673 |

Notes:

### Calculator case 2 (C54)

Steps it exercises (INSTRUCTIONS.md section 8.6, word for word):

> 1. **Allowed amount**: in-network → `min(billed, fee_schedule.inn_allowed_cents)`; out-of-network → `min(billed, fee_schedule.oon_allowed_cents)`.

> 3. **Member cost share** by the benefit's `cost_share_rule`:

> - `COPAY`: copay = min(copay_cents, allowed); deductible does not apply.

> 4. **Out-of-pocket maximum**: member cost share capped at the remaining out-of-pocket amount (separate in-network and out-of-network maximums).

> 5. **Plan pays** = allowed − member cost share.

- Plan PLN-EPO (EPO), IN_NETWORK: deductible 100000, coinsurance 2500 basis points, out-of-pocket maximum 450000 (cents)
- Accumulators before the claim (IN_NETWORK): deductible met 30000, out-of-pocket met 30000 (cents)

| Benefit category | Cost share rule | Copay (cents) |
|---|---|---|
| OFFICE_VISIT_SPECIALIST | COPAY | 6000 |

| Code | Fee in network (cents per unit) | Fee out of network (cents per unit) |
|---|---|---|
| 99211 | 3048 | 2438 |

| Line | Code | Units | Billed (cents) | Decision | Benefit category |
|---|---|---|---|---|---|
| 1 | 99211 | 1 | 2800 | APPROVE | OFFICE_VISIT_SPECIALIST |

- Other coverage: none

| Line | Allowed | Deductible applied | Copay | Coinsurance | Plan pays | Member pays |
|---|---|---|---|---|---|---|
| 1 | 2800 | 0 | 2800 | 0 | 0 | 2800 |

Notes:

### Calculator case 3 (C55)

Steps it exercises (INSTRUCTIONS.md section 8.6, word for word):

> 1. **Allowed amount**: in-network → `min(billed, fee_schedule.inn_allowed_cents)`; out-of-network → `min(billed, fee_schedule.oon_allowed_cents)`.

> 3. **Member cost share** by the benefit's `cost_share_rule`:

> - `DEDUCTIBLE_COINSURANCE`: deductible applied = min(remaining deductible, allowed); coinsurance = (allowed − deductible applied) × coinsurance_bps ÷ 10000.

> 4. **Out-of-pocket maximum**: member cost share capped at the remaining out-of-pocket amount (separate in-network and out-of-network maximums).

> 5. **Plan pays** = allowed − member cost share.

> 6. **COB (our plan secondary)**: secondary pays min(normal plan payment, allowed − primary paid), not below 0; member pays the remainder, not below 0. *(Team default: traditional COB. See `DECISIONS.md`.)*

> 7. Update **working** accumulators for later lines on the same claim.

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
| 1 | 24591 | 20000 | 0 | 459 | 0 | 0 |
| 2 | 16951 | 0 | 0 | 1695 | 15256 | 1695 |

Notes:

### Calculator case 4 (C56)

Steps it exercises (INSTRUCTIONS.md section 8.6, word for word):

> 1. **Allowed amount**: in-network → `min(billed, fee_schedule.inn_allowed_cents)`; out-of-network → `min(billed, fee_schedule.oon_allowed_cents)`.

> 3. **Member cost share** by the benefit's `cost_share_rule`:

> - `COPAY`: copay = min(copay_cents, allowed); deductible does not apply.

> - `DEDUCTIBLE_COINSURANCE`: deductible applied = min(remaining deductible, allowed); coinsurance = (allowed − deductible applied) × coinsurance_bps ÷ 10000.

> 4. **Out-of-pocket maximum**: member cost share capped at the remaining out-of-pocket amount (separate in-network and out-of-network maximums).

> 5. **Plan pays** = allowed − member cost share.

> 7. Update **working** accumulators for later lines on the same claim.

- Plan PLN-HMO (HMO), IN_NETWORK: deductible 25000, coinsurance 2000 basis points, out-of-pocket maximum 400000 (cents)
- Accumulators before the claim (IN_NETWORK): deductible met 15000, out-of-pocket met 385000 (cents)

| Benefit category | Cost share rule | Copay (cents) |
|---|---|---|
| ADVANCED_IMAGING | DEDUCTIBLE_COINSURANCE | - |
| OFFICE_VISIT_SPECIALIST | COPAY | 4000 |
| REHAB_THERAPY | COPAY | 3000 |

| Code | Fee in network (cents per unit) | Fee out of network (cents per unit) |
|---|---|---|
| 70553 | 39621 | 31697 |
| 97110 | 3633 | 2906 |
| 99214 | 16951 | 13561 |

| Line | Code | Units | Billed (cents) | Decision | Benefit category |
|---|---|---|---|---|---|
| 1 | 99214 | 1 | 27000 | APPROVE | OFFICE_VISIT_SPECIALIST |
| 2 | 70553 | 1 | 60000 | APPROVE | ADVANCED_IMAGING |
| 3 | 97110 | 2 | 12000 | APPROVE | REHAB_THERAPY |

- Other coverage: none

| Line | Allowed | Deductible applied | Copay | Coinsurance | Plan pays | Member pays |
|---|---|---|---|---|---|---|
| 1 | 16951 | 0 | 4000 | 0 | 12951 | 4000 |
| 2 | 39621 | 10000 | 0 | 1000 | 28621 | 11000 |
| 3 | 7266 | 0 | 0 | 0 | 7266 | 0 |

Notes:
