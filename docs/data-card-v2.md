# Decision dataset v2: data card

Generator decision-dataset-v3 (scenarios scenarios-v3), policy set v2, rules 2.1.0, prompt decision_v3, seed 20260921. Synthetic data only.

- Sizes: {'train': 2000, 'validation': 300, 'test': 300}.
- Retrieval: exact lookup v2: plan or ALL, effective date, criterion codes; no cap; file order; knowledge e47509cd64c4.
- Test-only policies (never in train or validation): ['POL-DX-001', 'POL-IMG-001', 'POL-IMG-002', 'POL-SURG-003']; test records using them: 100.
- Note styles: train and validation ['A', 'B', 'C']; style D (a numbered list mixing wordings A and B) only in the test split: {'D': 149, 'A': 52, 'B': 50, 'C': 49}.
- Labels: the line decision is derived from the statuses by `app.ml.derive` (D-DEC-1), the pipeline's own code; rule outcomes come from the rules engine with every claim's authorizations in the reference data (D-GEN-5).
- Add-on level codes (64480, 64484, 64491, 64492, 64494, 64495) stay out of scope: rule-only.
- Checks: 0 problems (checks_v2.py).

## Lengths (characters; tokens estimated at 3.5 characters each)

| Split | p50 | p95 | max | longest record |
|---|---|---|---|---|
| train | 7427 | 10114 | 10841 | DV2-TR-00695 |
| validation | 7456 | 10177 | 10719 | DV2-VA-00008 |
| test | 7192 | 9738 | 10663 | DV2-TE-00218 |

## train: line labels per policy

| Policy | Labels |
|---|---|
| POL-BH-001 | MODEL APPROVE 170, MODEL DENY 105, MODEL PEND 79, RULE DENY 3 |
| POL-CAR-001 | MODEL APPROVE 99, MODEL DENY 58, MODEL PEND 37, RULE DENY 11 |
| POL-CAR-002 | MODEL APPROVE 60, MODEL DENY 26, MODEL PEND 31, RULE DENY 4 |
| POL-DX-002 | MODEL APPROVE 69, MODEL DENY 63, MODEL PEND 19, RULE DENY 1 |
| POL-DX-003 | MODEL APPROVE 141, MODEL DENY 71, MODEL PEND 55, RULE DENY 31 |
| POL-FOOT-001 | MODEL APPROVE 98, MODEL DENY 14, MODEL PEND 41, RULE DENY 15 |
| POL-PAIN-001 | MODEL APPROVE 76, MODEL DENY 31, MODEL PEND 32, RULE DENY 8 |
| POL-PAIN-002 | MODEL APPROVE 160, MODEL DENY 55, MODEL PEND 66, RULE DENY 16 |
| POL-REHAB-001 | MODEL APPROVE 96, MODEL DENY 43, MODEL PEND 45, RULE DENY 38 |
| POL-SURG-001 | MODEL APPROVE 118, MODEL DENY 30, MODEL PEND 48, RULE DENY 9 |
| POL-SURG-002 | MODEL APPROVE 173, MODEL DENY 14, MODEL PEND 91, RULE DENY 27 |
| POL-SURG-004 | MODEL APPROVE 45, MODEL DENY 61, MODEL PEND 24, RULE DENY 13 |
| POL-WOUND-001 | MODEL APPROVE 178, MODEL DENY 27, MODEL PEND 96, RULE DENY 17 |
| office visit | MODEL APPROVE 84 |

## train: line labels per scenario

| Scenario | Labels |
|---|---|
| approve_single | MODEL APPROVE 357 |
| deny_criterion | MODEL DENY 201 |
| deny_exclusion | MODEL DENY 133 |
| extended_testing | MODEL APPROVE 105, MODEL DENY 51, MODEL PEND 45 |
| facet_two_regions | MODEL APPROVE 72, MODEL DENY 24, MODEL PEND 24 |
| ncci_bypass | MODEL APPROVE 208, MODEL PEND 126 |
| ncs_without_emg | MODEL APPROVE 22, MODEL DENY 46, MODEL PEND 12 |
| office_plus_procedure | MODEL APPROVE 175, MODEL DENY 17, MODEL PEND 24 |
| office_same_day | MODEL APPROVE 154, MODEL DENY 26, MODEL PEND 76, RULE DENY 38 |
| office_visit | MODEL APPROVE 84 |
| pend_missing | MODEL PEND 217 |
| rule_denied_line | MODEL APPROVE 104, MODEL DENY 22, MODEL PEND 29, RULE DENY 155 |
| same_profile_multi | MODEL APPROVE 158, MODEL DENY 54, MODEL PEND 65 |
| two_policy | MODEL APPROVE 128, MODEL DENY 24, MODEL PEND 46 |

Flags shown in train: {'NCCI_BYPASS': 276, 'NCS_WITHOUT_EMG': 80, 'FACET_TWO_REGIONS': 120, 'EXTENDED_TESTING': 201}; note styles: {'A': 653, 'C': 670, 'B': 677}.

## validation: line labels per policy

| Policy | Labels |
|---|---|
| POL-BH-001 | MODEL APPROVE 26, MODEL DENY 8, MODEL PEND 7, RULE DENY 1 |
| POL-CAR-001 | MODEL APPROVE 20, MODEL DENY 15, MODEL PEND 2, RULE DENY 1 |
| POL-CAR-002 | MODEL APPROVE 9, MODEL DENY 3 |
| POL-DX-002 | MODEL APPROVE 6, MODEL DENY 9, MODEL PEND 4 |
| POL-DX-003 | MODEL APPROVE 25, MODEL DENY 8, MODEL PEND 4 |
| POL-FOOT-001 | MODEL APPROVE 15, MODEL DENY 4, MODEL PEND 8, RULE DENY 3 |
| POL-PAIN-001 | MODEL APPROVE 9, MODEL DENY 4, MODEL PEND 5, RULE DENY 3 |
| POL-PAIN-002 | MODEL APPROVE 21, MODEL DENY 9, MODEL PEND 10, RULE DENY 2 |
| POL-REHAB-001 | MODEL APPROVE 15, MODEL DENY 6, MODEL PEND 10, RULE DENY 10 |
| POL-SURG-001 | MODEL APPROVE 20, MODEL DENY 2, MODEL PEND 11, RULE DENY 2 |
| POL-SURG-002 | MODEL APPROVE 28, MODEL DENY 2, MODEL PEND 23, RULE DENY 3 |
| POL-SURG-004 | MODEL APPROVE 6, MODEL DENY 4, MODEL PEND 1, RULE DENY 1 |
| POL-WOUND-001 | MODEL APPROVE 27, MODEL DENY 7, MODEL PEND 17, RULE DENY 3 |
| office visit | MODEL APPROVE 14 |

## validation: line labels per scenario

| Scenario | Labels |
|---|---|
| approve_single | MODEL APPROVE 57 |
| deny_criterion | MODEL DENY 30 |
| deny_exclusion | MODEL DENY 18 |
| extended_testing | MODEL APPROVE 12, MODEL DENY 3, MODEL PEND 3 |
| facet_two_regions | MODEL APPROVE 8, MODEL DENY 4, MODEL PEND 6 |
| ncci_bypass | MODEL APPROVE 26, MODEL PEND 22 |
| ncs_without_emg | MODEL APPROVE 2, MODEL DENY 7, MODEL PEND 1 |
| office_plus_procedure | MODEL APPROVE 23, MODEL DENY 2, MODEL PEND 1 |
| office_same_day | MODEL APPROVE 30, MODEL DENY 4, MODEL PEND 15, RULE DENY 7 |
| office_visit | MODEL APPROVE 14 |
| pend_missing | MODEL PEND 29 |
| rule_denied_line | MODEL APPROVE 10, MODEL DENY 3, MODEL PEND 9, RULE DENY 22 |
| same_profile_multi | MODEL APPROVE 32, MODEL DENY 2, MODEL PEND 7 |
| two_policy | MODEL APPROVE 27, MODEL DENY 8, MODEL PEND 9 |

Flags shown in validation: {'NCCI_BYPASS': 45, 'NCS_WITHOUT_EMG': 10, 'FACET_TWO_REGIONS': 18, 'EXTENDED_TESTING': 18}; note styles: {'B': 97, 'A': 100, 'C': 103}.

## test: line labels per policy

| Policy | Labels |
|---|---|
| POL-BH-001 | MODEL APPROVE 19, MODEL DENY 5, MODEL PEND 13 |
| POL-CAR-001 | MODEL APPROVE 13, MODEL DENY 11, MODEL PEND 4, RULE DENY 1 |
| POL-CAR-002 | MODEL APPROVE 7, MODEL DENY 4, MODEL PEND 2 |
| POL-DX-001 | MODEL APPROVE 15, MODEL DENY 8, MODEL PEND 5, RULE DENY 1 |
| POL-DX-002 | MODEL APPROVE 6, MODEL DENY 9, MODEL PEND 2 |
| POL-DX-003 | MODEL APPROVE 14, MODEL DENY 6, MODEL PEND 10, RULE DENY 1 |
| POL-FOOT-001 | MODEL APPROVE 12, MODEL DENY 2, MODEL PEND 3, RULE DENY 2 |
| POL-IMG-001 | MODEL APPROVE 22, MODEL DENY 12, MODEL PEND 17, RULE DENY 1 |
| POL-IMG-002 | MODEL APPROVE 3, MODEL DENY 8, MODEL PEND 6, RULE DENY 3 |
| POL-PAIN-001 | MODEL APPROVE 1, MODEL DENY 5, MODEL PEND 3 |
| POL-PAIN-002 | MODEL APPROVE 6, MODEL DENY 4, MODEL PEND 5, RULE DENY 3 |
| POL-REHAB-001 | MODEL APPROVE 9, MODEL DENY 4, MODEL PEND 1, RULE DENY 4 |
| POL-SURG-001 | MODEL APPROVE 15, MODEL DENY 1, MODEL PEND 7, RULE DENY 1 |
| POL-SURG-002 | MODEL APPROVE 14, MODEL DENY 2, MODEL PEND 12, RULE DENY 1 |
| POL-SURG-003 | MODEL APPROVE 23, MODEL DENY 3, MODEL PEND 4, RULE DENY 3 |
| POL-SURG-004 | MODEL APPROVE 11, MODEL DENY 4, MODEL PEND 1, RULE DENY 2 |
| POL-WOUND-001 | MODEL APPROVE 25, MODEL PEND 11, RULE DENY 2 |
| office visit | MODEL APPROVE 7 |

## test: line labels per scenario

| Scenario | Labels |
|---|---|
| approve_single | MODEL APPROVE 58 |
| deny_criterion | MODEL DENY 29 |
| deny_exclusion | MODEL DENY 23 |
| extended_testing | MODEL APPROVE 12, MODEL PEND 6 |
| facet_two_regions | MODEL APPROVE 2, MODEL DENY 2, MODEL PEND 4 |
| ncci_bypass | MODEL APPROVE 20, MODEL PEND 16 |
| ncs_without_emg | MODEL APPROVE 1, MODEL DENY 6, MODEL PEND 2 |
| office_plus_procedure | MODEL APPROVE 35, MODEL DENY 3, MODEL PEND 2 |
| office_same_day | MODEL APPROVE 22, MODEL DENY 1, MODEL PEND 6, RULE DENY 3 |
| office_visit | MODEL APPROVE 7 |
| pend_missing | MODEL PEND 42 |
| rule_denied_line | MODEL APPROVE 13, MODEL DENY 7, MODEL PEND 2, RULE DENY 22 |
| same_profile_multi | MODEL APPROVE 24, MODEL DENY 5, MODEL PEND 18 |
| two_policy | MODEL APPROVE 28, MODEL DENY 12, MODEL PEND 8 |

Flags shown in test: {'NCCI_BYPASS': 31, 'NCS_WITHOUT_EMG': 9, 'FACET_TWO_REGIONS': 8, 'EXTENDED_TESTING': 18}; note styles: {'D': 149, 'A': 52, 'B': 50, 'C': 49}.
