# Golden-test spot-check: comparison (Task G2)

The spot-check answers were computed by a separate Claude chat from the sheet's text only, without access to the repository or the answers file, and accepted by the reviewer. This is a Claude recomputation, not a blind human check, and not independent of the golden cases' author (also Claude). P-01 is not independent (the sheet leaked its outcome; fixed in G2). The rules sample is only partly blind, because the sheet names the rule each case exercises; the calculator cases show no expected values but list the assumptions each case relies on (C19 and C21 name A4, the out-of-pocket cap).

## Result

- Rules cases: 10 of 10 agree on outcome, reason codes and flags; 9 of the 9 independent cases.
- Calculator: 11 of 11 lines agree on all six amounts, exact to the cent (66 of 66 amounts).
- Mismatches: 0. No golden case was changed.
- Golden assumptions: ACCEPT 19, CHANGE 1; H5 field mapping: ACCEPT 12, CHANGE 2.

## Rules cases

Agreement means the same claim outcome, the same internal reason codes and the same flags (OON, NCCI_BYPASS).

| # | Case | My outcome | Expected (outcome, reason codes, flags) | Agrees | Independent |
|---|---|---|---|---|---|
| 1 | H5-02 | REJECT RJ_LOW_CONFIDENCE_FIELD | REJECT RJ_LOW_CONFIDENCE_FIELD | yes | yes |
| 2 | DUP-01 | REJECT RJ_DUPLICATE | REJECT RJ_DUPLICATE | yes | yes |
| 3 | R11-09 | PASS; line 2 flag NCCI_BYPASS | PASS flags NCCI_BYPASS | yes | yes |
| 4 | R03-04 | REJECT RJ_INVALID_NPI | REJECT RJ_INVALID_NPI | yes | yes |
| 5 | R02-01 | REJECT RJ_INVALID_CODE | REJECT RJ_INVALID_CODE | yes | yes |
| 6 | R09-01 | DENY DN_MISSING_REFERRAL | DENY DN_MISSING_REFERRAL | yes | yes |
| 7 | P-01 | PASS | PASS | yes | no: computed after the sheet leaked its outcome (fixed in G2) |
| 8 | R01-02 | REJECT RJ_MISSING_FIELD | REJECT RJ_MISSING_FIELD | yes | yes |
| 9 | R04-01 | REJECT RJ_MEMBER_NOT_FOUND | REJECT RJ_MEMBER_NOT_FOUND | yes | yes |
| 10 | R06-04 | DENY DN_NOT_ELIGIBLE (R06 PEND PD_PROVIDER_ENROLLMENT also recorded) | DENY DN_NOT_ELIGIBLE PD_PROVIDER_ENROLLMENT | yes | yes |

## Calculator cases

Amounts in cents: allowed / deductible applied / copay / coinsurance / plan pays / member pays.

| # | Case | Line | My amounts | Expected amounts | Agrees |
|---|---|---|---|---|---|
| 1 | C04 | 1 | 9000 / 0 / 2500 / 0 / 6500 / 2500 | 9000 / 0 / 2500 / 0 / 6500 / 2500 | yes |
| 2 | C10 | 1 | 24425 / 24425 / 0 / 0 / 0 / 24425 | 24425 / 24425 / 0 / 0 / 0 / 24425 | yes |
| 3 | C49 | 1 | 24425 / 24425 / 0 / 0 / 0 / 24425 | 24425 / 24425 / 0 / 0 / 0 / 24425 | yes |
| 4 | C30 | 1 | 13561 / 0 / 0 / 5424 / 8137 / 5424 | 13561 / 0 / 0 / 5424 / 8137 / 5424 | yes |
| 5 | C19 | 1 | 39621 / 0 / 0 / 5000 / 34621 / 5000 | 39621 / 0 / 0 / 5000 / 34621 / 5000 | yes |
| 6 | C21 | 1 | 16951 / 0 / 1000 / 0 / 15951 / 1000 | 16951 / 0 / 1000 / 0 / 15951 / 1000 | yes |
| 7 | C31 | 1 | 19540 / 0 / 0 / 9770 / 9770 / 9770 | 19540 / 0 / 0 / 9770 / 9770 / 9770 | yes |
| 8 | C41 | 1 | 13561 / 0 / 0 / 5424 / 7561 / 0 | 13561 / 0 / 0 / 5424 / 7561 / 0 | yes |
| 9 | C26 | 1 | 11899 / 0 / 2500 / 0 / 9399 / 2500 | 11899 / 0 / 2500 / 0 / 9399 / 2500 | yes |
| 9 | C26 | 2 | 0 / 0 / 0 / 0 / 0 / 0 | 0 / 0 / 0 / 0 / 0 / 0 | yes |
| 9 | C26 | 3 | 24591 / 24591 / 0 / 0 / 0 / 24591 | 24591 / 24591 / 0 / 0 / 0 / 24591 | yes |

## Mismatches

None: every answer agrees with the golden expected value.

## Assumptions and H5 mapping rows marked CHANGE

| Row | Verdict | Note |
|---|---|---|
| Assumption A-R3 | CHANGE | add modifier 59, the standard NCCI-associated modifier; check the full list in the NCCI Policy Manual; frozen for v1, so a v2 change |
| H5 R07 | CHANGE | add member_id: the filing window comes from the member's plan |
| H5 R09 | CHANGE | add member_id: referral rules come from the member's plan |

Accepted with a note:

- Assumption A2: matches §8.6 as written; real plans usually charge one copay per visit, consider in v2
- Assumption A6: design choice: some plans credit only what the member actually paid

## Effect of the CHANGE rows on the golden cases (report only; nothing changed)

- H5 check with member_id added to R07 and R09 (H5 mapping rows marked CHANGE): 0 findings on the 90 rules cases (0 with the G1 mapping); no golden rules case is affected.
- Golden rules cases with modifier 59 on a line (A-R3 marked CHANGE): 0; making 59 a bypass modifier changes no golden rules case.
