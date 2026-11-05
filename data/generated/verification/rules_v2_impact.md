# P2.3b planning: impact of the proposed rules v2

## Code facts

| Code | MUE | PFS global days |
|---|---|---|
| 36475 | 1 | 000 |
| 36478 | 1 | 000 |
| 37765 | 1 | 010 |
| 62321 | 1 | 000 |
| 62323 | 1 | 000 |
| 64479 | 1 | 000 |
| 64480 | 4 | ZZZ |
| 64483 | 1 | 000 |
| 64484 | 4 | ZZZ |
| 64490 | 1 | 000 |
| 64491 | 1 | ZZZ |
| 64492 | 1 | ZZZ |
| 64493 | 1 | 000 |
| 64494 | 1 | ZZZ |
| 64495 | 1 | ZZZ |
| 64633 | 1 | 010 |
| 64634 | 4 | ZZZ |
| 64635 | 1 | 010 |
| 64636 | 4 | ZZZ |
| 70450 | 3 | XXX |
| 70551 | 2 | XXX |
| 70553 | 2 | XXX |
| 72141 | 1 | XXX |
| 95800 | 1 | XXX |
| 95801 | 1 | XXX |
| 95806 | 1 | XXX |
| 95860 | 1 | XXX |
| 95861 | 1 | XXX |
| 95863 | 1 | XXX |
| 95864 | 1 | XXX |
| 95865 | 1 | XXX |
| 95866 | 1 | XXX |
| 95867 | 1 | XXX |
| 95868 | 1 | XXX |
| 95869 | 1 | XXX |
| 95870 | 4 | XXX |
| 95872 | 4 | XXX |
| 95885 | 4 | ZZZ |
| 95886 | 4 | ZZZ |
| 95887 | 1 | ZZZ |
| 95907 | 1 | XXX |
| 95908 | 1 | XXX |
| 95909 | 1 | XXX |
| 95910 | 1 | XXX |
| 95911 | 1 | XXX |
| 95912 | 1 | XXX |
| 95913 | 1 | XXX |
| 96130 | 1 | XXX |
| 96131 | 7 | ZZZ |
| 96136 | 1 | XXX |
| G0398 | 1 | XXX |
| G0399 | 1 | XXX |
| G0400 | 1 | XXX |

NCCI pairs active on 2026-11-01 (column 1/column 2 (modifier indicator)):

- ESI with facet injection: none
- ESI with ESI: 62321/64479 (1), 62321/64480 (0), 62323/64483 (1), 62323/64484 (1)
- radiofrequency with ESI: 64633/62321 (1), 64633/62323 (1), 64633/64479 (1), 64633/64483 (1), 64634/62321 (1), 64634/62323 (1), 64634/64479 (1), 64634/64483 (1), 64635/62321 (1), 64635/62323 (1), 64635/64479 (1), 64635/64483 (1), 64636/62321 (1), 64636/62323 (1), 64636/64479 (1), 64636/64483 (1)
- ablation (36475, 36478) with stab phlebectomy (37765): none
- imaging (70450, 70551, 70553, 72141): 70553/70551 (1)
- nerve conduction with nerve conduction: 95908/95907 (0), 95909/95907 (0), 95909/95908 (0), 95910/95907 (0), 95910/95908 (0), 95910/95909 (0), 95911/95907 (0), 95911/95908 (0), 95911/95909 (0), 95911/95910 (0), 95912/95907 (0), 95912/95908 (0), 95912/95909 (0), 95912/95910 (0), 95912/95911 (0), 95913/95907 (0), 95913/95908 (0), 95913/95909 (0), 95913/95910 (0), 95913/95911 (0), 95913/95912 (0)
- extremity needle EMG (95860-95864) with 95869 or 95870: 95860/95869 (1), 95860/95870 (1), 95861/95869 (1), 95861/95870 (1), 95863/95869 (1), 95863/95870 (1), 95864/95869 (1), 95864/95870 (1)

Billing article CPT groups:

- A56651 group 1: 62321, 62323, 64479, 64480, 64483, 64484
- A56923 group 1: 95782, 95783, 95800, 95801, 95805, 95806, 95807, 95808, 95810, 95811, G0398, G0399, G0400
- A56923 group 2: 95999
- A57478 group 1: 51785, 92265, 95860, 95861, 95863, 95864, 95865, 95866, 95867, 95868, 95869, 95870, 95872, 95873, 95874, 95885, 95886, 95887, 95905, 95907, 95908, 95909, 95910, 95911, 95912, 95913, 95933, 95937, 95999, G0255
- A57787 group 1: 64490, 64491, 64493, 64494, 64633, 64634, 64635, 64636
- A57787 group 2: 0213T, 0214T, 0215T, 0216T, 0217T, 0218T, 0219T, 0220T, 0221T, 0222T, 64492, 64495

Diagnosis sets (ICD-10-CM FY2027 titles):

- parasomnia (G47.50-G47.59): G4750 Parasomnia, unspecified [A56923 groups [2], A57787 groups []]; G4751 Confusional arousals [A56923 groups [2], A57787 groups []]; G4752 REM sleep behavior disorder [A56923 groups [1], A57787 groups []]; G4753 Recurrent isolated sleep paralysis [A56923 groups [1], A57787 groups []]; G4754 Parasomnia in conditions classified elsewhere [A56923 groups [2], A57787 groups []]; G4759 Other parasomnia [A56923 groups [2], A57787 groups []]
- synovial cyst (M71.3, to confirm against the tabular): M7130 Other bursal cyst, unspecified site [A56923 groups [], A57787 groups [1]]; M7138 Other bursal cyst, other site [A56923 groups [], A57787 groups [1]]

## CARC and RARC candidates (official text, data/raw/carc-rarc/2026-09-21)

- CARC 4 (current): The procedure code is inconsistent with the modifier used. Usage: Refer to the 835 Healthcare Policy Identification Segment (loop 2110 Service Payment Information REF), if present.
- CARC 11 (current): The diagnosis is inconsistent with the procedure. Usage: Refer to the 835 Healthcare Policy Identification Segment (loop 2110 Service Payment Information REF), if present.
- CARC 50 (current): These are non-covered services because this is not deemed a 'medical necessity' by the payer. Usage: Refer to the 835 Healthcare Policy Identification Segment (loop 2110 Service Payment Information REF), if present.
- CARC 58 (current): Treatment was deemed by the payer to have been rendered in an inappropriate or invalid place of service. Usage: Refer to the 835 Healthcare Policy Identification Segment (loop 2110 Service Payment Information REF), if present.
- CARC 96 (current): Non-covered charge(s). At least one Remark Code must be provided (may be comprised of either the NCPDP Reject Reason Code, or Remittance Advice Remark Code that is not an ALERT.) Usage: Refer to the 835 Healthcare Policy Identification Segment (loop 2110 Service Payment Information REF), if present.
- CARC 151 (current): Payment adjusted because the payer deems the information submitted does not support this many/frequency of services.
- CARC 167 (current): This (these) diagnosis(es) is (are) not covered. Usage: Refer to the 835 Healthcare Policy Identification Segment (loop 2110 Service Payment Information REF), if present.
- CARC 236 (current): This procedure or procedure/modifier combination is not compatible with another procedure or procedure/modifier combination provided on the same day according to the National Correct Coding Initiative or workers compensation state regulations/ fee schedule requirements.
- RARC M76 (current): Missing/incomplete/invalid diagnosis or condition.
- RARC N115 (current): This decision was based on a Local Coverage Determination (LCD). An LCD provides a guide to assist in determining whether a particular item or service is covered. A copy of this policy is available at www.cms.gov/mcd, or if you do not have web access, you may contact the contractor to request a copy of the LCD.
- RARC N130 (current): Consult plan benefit documents/guidelines for information about restrictions for this service.
- RARC N362 (current): The number of Days or Units of Service exceeds our acceptable maximum.
- RARC N386 (current): This decision was based on a National Coverage Determination (NCD). An NCD provides a coverage determination as to whether a particular item or service is covered. Visit CMS.gov and search for Medicare Coverage Database to find a copy of the policy.
- RARC N657 (current): This should be billed with the appropriate code for these services.

## Golden rules cases (90): changes

| Case | Line | Rule | Result | Detail |
|---|---|---|---|---|
| R14-01 | 1 | R14 | DENY DN_MULTIPLE_BLOCKS | 64483 with ['64493'] on 2026-10-06 |
| R14-06 | 1 | R14 | DENY DN_MULTIPLE_BLOCKS | 64483 with ['64493'] on 2026-10-06 |
| R14-06 | 2 | R14 | DENY DN_MULTIPLE_BLOCKS | 64484: add-on of the denied 64483 |
| R15-01 | 1 | R15 | DENY DN_DX_NOT_SUPPORTED | 93350: no supporting diagnosis among ['I10'] |
| R15-04 | 1 | R15 | DENY DN_DX_NOT_SUPPORTED | 45385: no supporting diagnosis among ['S36500A', 'S31609A'] |
| R15-07 | 1 | R15 | DENY DN_DX_NOT_SUPPORTED | 11720: no supporting diagnosis among ['E1151'] |
| R16-01 | 1 | R16 | DENY DN_HOME_TEST_PARASOMNIA | 95806 with ['G4750'] |
| R17-01 | 1 | R17 | FLAG NCS_WITHOUT_EMG | 95910 |
| R18-01 | 1 | R18 | DENY DN_ESI_LEVELS | bilateral |
| R18-03 | 2 | R18 | DENY DN_ESI_LEVELS | right 3 levels, left 0 |
| R19-01 | 3 | R19 | DENY DN_FACET_LEVELS | 64495 third level |
| R19-03 | 1 | R19 | FLAG FACET_TWO_REGIONS | 2026-10-06 |
| R19-03 | 2 | R19 | FLAG FACET_TWO_REGIONS | 2026-10-06 |
| R20-01 | 1 | R20 | FLAG EXTENDED_TESTING | 510 minutes |
| R20-01 | 2 | R20 | FLAG EXTENDED_TESTING | 510 minutes |
| R20-01 | 3 | R20 | FLAG EXTENDED_TESTING | 510 minutes |
| X-03 | 1 | R14 | DENY DN_MULTIPLE_BLOCKS | 62323 with ['64483'] on 2026-10-06 |
| X-03 | 2 | R14 | DENY DN_MULTIPLE_BLOCKS | 64483 with ['62323'] on 2026-10-06 |

18 hits. With {'L97419': 'L97412'} in the D-GOLD-1 cases (R11-02, R11-03, R11-07, R11-08, X-02), checks still failing: none.

## Golden end-to-end claims (30): changes

| Case | Line | Rule | Result | Detail |
|---|---|---|---|---|
| E2E-23 | 1 | R15 | DENY DN_DX_NOT_SUPPORTED | 93350: no supporting diagnosis among ['I10'] |

1 hits.

## Model v1 dataset (2600 records): lines caught

Label = the line's current label (source and decision).

| Check | Result <- label | Train | Validation | Test | All |
|---|---|---|---|---|---|
| R14 | DENY DN_MULTIPLE_BLOCKS <- MODEL APPROVE | 10 | 4 | 1 | 15 |
| R14 | DENY DN_MULTIPLE_BLOCKS <- MODEL DENY | 8 | 0 | 0 | 8 |
| R14 | DENY DN_MULTIPLE_BLOCKS <- MODEL PEND | 4 | 1 | 0 | 5 |
| R14 | DENY DN_MULTIPLE_BLOCKS <- RULE DENY | 3 | 1 | 0 | 4 |
| R15 (group sets, as V1a) | DENY DN_DX_NOT_SUPPORTED <- MODEL DENY | 292 | 40 | 59 | 391 |
| R15 (group sets, as V1a) | DENY DN_DX_NOT_SUPPORTED <- RULE DENY | 9 | 2 | 1 | 12 |
| R15 (approved, article-exact) | DENY DN_DX_NOT_SUPPORTED <- MODEL DENY | 291 | 40 | 59 | 390 |
| R15 (approved, article-exact) | DENY DN_DX_NOT_SUPPORTED <- RULE DENY | 9 | 2 | 1 | 12 |
| R16 | none | 0 | 0 | 0 | 0 |
| R17 | FLAG NCS_WITHOUT_EMG <- MODEL APPROVE | 0 | 0 | 12 | 12 |
| R17 | FLAG NCS_WITHOUT_EMG <- MODEL DENY | 0 | 0 | 9 | 9 |
| R17 | FLAG NCS_WITHOUT_EMG <- MODEL PEND | 0 | 0 | 4 | 4 |
| R17 | FLAG NCS_WITHOUT_EMG <- RULE DENY | 0 | 0 | 2 | 2 |
| R18 | none | 0 | 0 | 0 | 0 |
| R19 | none | 0 | 0 | 0 | 0 |
| R20 | none | 0 | 0 | 0 | 0 |

## Comparison with V1a

- R15 (group sets) on lines the rules left to the model: 391 (MODEL DENY 391); V1a: 391, all DENY.
- R15 approved minus group sets: -1 lines.
- Lines whose R15 result differs between the v1 group sets and the approved definition (66982 on group 1 only, colonoscopy 2A first, foot care Q7-Q9): 66982 train MODEL DENY 1
- R14: 32 ESI lines; would become DENY 20, already DENY 12; V1a: 32 lines, 20 becoming DENY, 12 already DENY.
- R15 (group sets) by scenario, lines left to the model: deny_dx 226, two_policy 51, same_profile_multi 45, office_plus_procedure 30, rule_denied_line 21, office_same_day 11, deny_criterion 5, deny_exclusion 2
- A58565 lines that fail on their own diagnoses but pass on the claim's (the article says "the claim must have"): 0.
- R17-flagged lines without a carpal tunnel diagnosis labelled APPROVE or PEND (contradict L34594 cov-037; D-RULE-6): test MODEL APPROVE 8, test MODEL PEND 2 (total 10)
- Add-on codes billed in the dataset (CMS add-on code edits 2026 Q4): 95886 x 8, 96131 x 35
- Add-on lines that pass while their primary on the same date is denied by a rule (R11-R19; primaries from the CMS add-on code edits): none (total 0)
