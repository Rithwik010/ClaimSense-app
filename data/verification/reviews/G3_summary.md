# New calculator golden cases: independent check (Task G3)

The answers were computed by a separate Claude chat from G3_new_cases_sheet.md only, without access to the repository, the staged cases or any expected amount. This is a Claude recomputation, not a blind human check, and not independent of the cases' author (also Claude). The sheet showed the inputs and the quoted section 8.6 steps only: no titles, expected values, worked steps, situations or per-case assumption names; A1-A9 were listed once for every case.

- Cases: C53, C54, C55, C56 (8 lines); amounts compared: 48; agree: 48; mismatches: 0.
- Added to tests/golden/calculator/: C53 (multi_line.json), C54 (copay.json), C55 (coordination_of_benefits.json), C56 (out_of_pocket_max.json); golden calculator cases 52 -> 56.
- C55 line 2 depends on assumption A6: line 1's deductible counts toward the accumulators although the primary paid more than line 1's allowed amount, so line 2 takes no deductible.

## Comparison (allowed / deductible / copay / coinsurance / plan pays / member pays)

| Case | Line | Answer | Expected | Agree |
|---|---|---|---|---|
| C53 | 1 | 24591 / 24591 / 0 / 0 / 0 / 24591 | 24591 / 24591 / 0 / 0 / 0 / 24591 | yes |
| C53 | 2 | 39621 / 5409 / 0 / 10264 / 23948 / 15673 | 39621 / 5409 / 0 / 10264 / 23948 / 15673 | yes |
| C54 | 1 | 2800 / 0 / 2800 / 0 / 0 / 2800 | 2800 / 0 / 2800 / 0 / 0 / 2800 | yes |
| C55 | 1 | 24591 / 20000 / 0 / 459 / 0 / 0 | 24591 / 20000 / 0 / 459 / 0 / 0 | yes |
| C55 | 2 | 16951 / 0 / 0 / 1695 / 15256 / 1695 | 16951 / 0 / 0 / 1695 / 15256 / 1695 | yes |
| C56 | 1 | 16951 / 0 / 4000 / 0 / 12951 / 4000 | 16951 / 0 / 4000 / 0 / 12951 / 4000 | yes |
| C56 | 2 | 39621 / 10000 / 0 / 1000 / 28621 / 11000 | 39621 / 10000 / 0 / 1000 / 28621 / 11000 | yes |
| C56 | 3 | 7266 / 0 / 0 / 0 / 7266 / 0 | 7266 / 0 / 0 / 0 / 7266 / 0 | yes |

## Mismatches

None: every answer agrees with the expected value.

## Coverage: cost-share situations (calculator)

| Situation | Golden cases before (52) | After (56) |
|---|---|---|
| copay only | 17 | 18 |
| deductible not met | 9 | 9 |
| deductible partly met | 6 | 9 |
| deductible met | 18 | 18 |
| coinsurance | 21 | 24 |
| out-of-pocket maximum reached | 7 | 8 |
| out-of-network PPO | 8 | 8 |
| COB secondary | 6 | 7 |
| denied line in a multi-line claim | 2 | 2 |
| deductible spans lines | **none** | 1 |
| copay capped by the allowed amount | 1 | 2 |
| billed below the fee schedule | 5 | 6 |
| units > 1 | 7 | 8 |
| pended line | 2 | 2 |
| out-of-network copay category (A3) | 4 | 4 |
| COB: primary paid >= allowed | 1 | 2 |
