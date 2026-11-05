# Policies v2 and retrieval: impact before any policy change

## Dataset lines that reference a replaced v1 criterion

Shown: the line's prompt lists the criterion. Used: its gold status is not NOT_APPLICABLE (status counts). Lines decided by a rule have no gold criteria.

| v1 criterion | Decision | v2 IDs | Shown (train / validation / test) | Used, train | Used, validation | Used, test | Records |
|---|---|---|---|---|---|---|---|
| POL-CAR-001.c1 | D-V2-1 | c4 requirement + c5 exclusion | 122 / 14 / 17 | MET 70, NOT_DOCUMENTED 25, NOT_MET 27 | MET 8, NOT_DOCUMENTED 3, NOT_MET 3 | MET 13, NOT_DOCUMENTED 1, NOT_MET 3 | 153 |
| POL-CAR-002.c1 | D-V2-1, CAR-002.F1 note | c4 (48-hour list, with c2) | 158 / 22 / 17 | MET 55, NOT_DOCUMENTED 30, NOT_MET 29 | MET 1, NOT_DOCUMENTED 6, NOT_MET 7 | MET 3, NOT_DOCUMENTED 6, NOT_MET 4 | 197 |
| POL-CAR-002.c2 | D-V2-2 CAR-002.F1 | c4 (48-hour list, with c1) | 158 / 22 / 17 | MET 27, NOT_DOCUMENTED 17 | MET 5, NOT_DOCUMENTED 3 | MET 3, NOT_DOCUMENTED 1 | 197 |
| POL-CAR-002.c3 | D-V2-1 | c5 (up to 15 days) + c6 (30-day) | 158 / 22 / 17 | MET 53, NOT_DOCUMENTED 22, NOT_MET 37 | MET 8, NOT_DOCUMENTED 2, NOT_MET 2 | MET 5, NOT_DOCUMENTED 1, NOT_MET 2 | 197 |
| POL-DX-001.c2 | D-V2-1, Q6 | c4 exclusion (cov-109, cov-110) | 0 / 0 / 17 | - | - | MET 4, NOT_DOCUMENTED 2, NOT_MET 3 | 17 |
| POL-DX-001.c3 | D-POL-4 (extended triage B7) | c6 (repeat sleep study, home included) | 0 / 0 / 17 | - | - | MET 4, NOT_DOCUMENTED 2, NOT_MET 2 | 17 |
| POL-DX-003.c1 | D-V2-2 DX-003.F1 | c4 + c5 | 158 / 30 / 16 | MET 90, NOT_DOCUMENTED 12, NOT_MET 18 | MET 14, NOT_MET 5 | MET 6, NOT_DOCUMENTED 1, NOT_MET 5 | 161 |
| POL-FOOT-001.c3 | D-V2-1, Q4 | c6 exclusion (except as provided) | 170 / 13 / 13 | MET 78, NOT_DOCUMENTED 17, NOT_MET 75 | MET 9, NOT_MET 4 | MET 6, NOT_DOCUMENTED 1, NOT_MET 6 | 196 |
| POL-IMG-002.c2 | D-POL-4 (extended triage B20) | c5 exclusion (scoped exception) | 0 / 0 / 19 | - | - | MET 4, NOT_DOCUMENTED 4 | 19 |
| POL-PAIN-001.c2 | D-ESI-2 | c6 | 179 / 21 / 22 | MET 86, NOT_DOCUMENTED 33, NOT_MET 8 | MET 14, NOT_DOCUMENTED 1 | MET 7, NOT_DOCUMENTED 4 | 222 |
| POL-PAIN-001.c4 | D-ESI-7 | c7 | 179 / 21 / 22 | MET 41, NOT_DOCUMENTED 7, NOT_MET 4 | MET 4, NOT_DOCUMENTED 1, NOT_MET 1 | MET 10, NOT_MET 1 | 222 |
| POL-PAIN-001.c5 | D-ESI-2, V1a open item | c8 | 179 / 21 / 22 | MET 37, NOT_DOCUMENTED 12, NOT_MET 3 | MET 4, NOT_DOCUMENTED 2 | MET 7, NOT_DOCUMENTED 3, NOT_MET 1 | 222 |
| POL-PAIN-002.c4 | D-V2-1 | c5 | 139 / 27 / 16 | - | - | - | 182 |
| POL-REHAB-001.c2 | D-V2-2 REHAB-001.F1, F2 | c4 + c5 | 228 / 30 / 23 | MET 175, NOT_DOCUMENTED 25, NOT_MET 28 | MET 25, NOT_DOCUMENTED 2, NOT_MET 3 | MET 13, NOT_DOCUMENTED 5, NOT_MET 5 | 205 |
| POL-SURG-002.c1 | D-V2-2 SURG-002.F1 | c4 | 257 / 35 / 31 | MET 145, NOT_DOCUMENTED 33, NOT_MET 25 | MET 20, NOT_DOCUMENTED 6, NOT_MET 2 | MET 21, NOT_DOCUMENTED 6, NOT_MET 1 | 232 |
| POL-SURG-002.c2 | D-V2-1 | c5 | 257 / 35 / 31 | MET 26, NOT_DOCUMENTED 21, NOT_MET 7 | MET 3, NOT_DOCUMENTED 2, NOT_MET 2 | MET 2, NOT_DOCUMENTED 1 | 232 |
| POL-SURG-004.c1 | D-V2-2 SURG-004.F1 | c5 | 162 / 28 / 17 | MET 35, NOT_DOCUMENTED 9, NOT_MET 9 | MET 5, NOT_DOCUMENTED 1, NOT_MET 4 | MET 3, NOT_MET 2 | 207 |
| POL-SURG-004.c2 | D-V2-2 SURG-004.F1 | c6 | 162 / 28 / 17 | MET 76, NOT_DOCUMENTED 21, NOT_MET 65 | MET 18, NOT_DOCUMENTED 4, NOT_MET 6 | MET 6, NOT_DOCUMENTED 2, NOT_MET 9 | 207 |
| POL-SURG-004.c3 | D-V2-2 SURG-004.F1 | c7 | 162 / 28 / 17 | MET 77, NOT_DOCUMENTED 23, NOT_MET 62 | MET 16, NOT_DOCUMENTED 5, NOT_MET 7 | MET 5, NOT_DOCUMENTED 2, NOT_MET 10 | 207 |
| POL-SURG-004.c4 | D-V2-2 SURG-004.F1 | c8 | 162 / 28 / 17 | MET 45, NOT_DOCUMENTED 16, NOT_MET 48 | MET 10, NOT_DOCUMENTED 3, NOT_MET 5 | MET 5, NOT_MET 7 | 207 |
| POL-WOUND-001.c3 | D-V2-2 WOUND-001.F3 | c4 | 295 / 42 / 16 | MET 95, NOT_DOCUMENTED 30, NOT_MET 4 | MET 10, NOT_DOCUMENTED 4 | MET 2, NOT_DOCUMENTED 2 | 270 |

- Total: shown 4153, used 2517; records with any replaced criterion: 1967.

Lines of the policies that gain a new criterion (all of the policy's lines change):

- POL-PAIN-001 c9 exclusion (D-ESI-4): train 179 / validation 21 / test 22 lines
- POL-SURG-002 c6 exclusion (D-V2-2 SURG-002.F3) and c7 therapeutic indications (D-POL-4): train 257 / validation 35 / test 31 lines
- POL-DX-002 c4 conditional (D-RULE-6, Q9, L34594 cov-037): train 0 / validation 0 / test 38 lines
- POL-FOOT-001 c4 and c5 conditional, indication group (Q4, manual 290.C.3 and C.4): train 170 / validation 13 / test 13 lines
- POL-DX-001 c5 requirement on 95806 (D-POL-4, L35050 cov-107 and cov-108): train 0 / validation 0 / test 17 lines
- POL-SURG-001 c4 conditional, indication group (D-POL-4, L33558 cov-008): train 104 / validation 25 / test 7 lines

## v1 labels that D-GEN-3 contradicts (an exclusion criterion labelled MET)

| v1 criterion (proposed type exclusion) | MET (train / validation / test) | Records |
|---|---|---|
| POL-BH-001.c2 | 68 / 6 / 9 | 46 |
| POL-BH-001.c3 | 12 / 3 / 2 | 17 |
| POL-DX-002.c2 | 0 / 0 / 19 | 15 |
| POL-DX-002.c3 | 0 / 0 / 7 | 7 |
| POL-FOOT-001.c3 | 78 / 9 / 6 | 93 |
| POL-IMG-001.c4 | 0 / 0 / 0 | 0 |
| POL-IMG-002.c2 | 0 / 0 / 4 | 4 |
| POL-SURG-001.c2 | 68 / 12 / 3 | 83 |
| POL-SURG-003.c2 | 0 / 0 / 25 | 22 |
| POL-SURG-003.c3 | 0 / 0 / 25 | 22 |
| POL-SURG-004.c4 | 45 / 10 / 5 | 60 |

- Total MET on exclusion criteria: 416.

## Golden cases and tests that reference a replaced v1 criterion

- tests/golden/e2e/cases.json (31 cases): E2E-18 POL-SURG-004.c2 POL-SURG-004.c3 POL-SURG-004.c4; E2E-19 POL-CAR-002.c1; E2E-21 POL-SURG-002.c1; E2E-22 POL-REHAB-001.c2; E2E-23 POL-CAR-002.c2 POL-CAR-002.c3; E2E-24 POL-DX-003.c1; E2E-25 POL-CAR-002.c2 POL-CAR-002.c3; E2E-26 POL-SURG-002.c2; E2E-27 POL-SURG-004.c2 POL-SURG-004.c3 POL-SURG-004.c4; E2E-32 POL-CAR-001.c1 POL-CAR-002.c2 POL-CAR-002.c3
- tests/golden/rag/queries.json (50 queries, 53 expected IDs): RAG-08 POL-IMG-002.c2; RAG-09 POL-CAR-001.c1; RAG-12 POL-CAR-002.c1; RAG-13 POL-CAR-002.c1 POL-CAR-002.c3; RAG-14 POL-CAR-002.c2; RAG-15 POL-DX-001.c2; RAG-16 POL-DX-001.c3; RAG-20 POL-DX-003.c1; RAG-25 POL-PAIN-001.c2; RAG-26 POL-PAIN-001.c5; RAG-27 POL-PAIN-001.c4; RAG-29 POL-PAIN-002.c4; RAG-34 POL-SURG-002.c1; RAG-35 POL-SURG-002.c2; RAG-38 POL-SURG-004.c2 POL-SURG-004.c3; RAG-39 POL-SURG-004.c4; RAG-42 POL-REHAB-001.c2; RAG-45 POL-WOUND-001.c3
- RAG queries on a policy that gains a criterion: RAG-15, RAG-16, RAG-17, RAG-18, RAG-19, RAG-24, RAG-25, RAG-26, RAG-27, RAG-31, RAG-32, RAG-33, RAG-34, RAG-35, RAG-40, RAG-41
- Other test files naming a replaced criterion (tests/golden/blind_review not opened): none

## Nerve-conduction labels that contradict L34594 cov-037 (D-RULE-6)

R17-flagged lines (a nerve conduction code, no needle EMG code on the claim) without a carpal tunnel diagnosis (G56.00-G56.03), labelled APPROVE or PEND. For the generator v2 task; the v1 dataset is not changed. Expected v2: the status of POL-DX-002.c4 (Q9: another cause in the notes NOT_MET, silent NOT_DOCUMENTED) and the line decision it gives; a judgment of the notes, with its reason.

| Record | Split | Line | Code | Diagnoses | v1 label | Scenario | v1 DX-002 statuses | Expected v2 c4 -> decision | Why |
|---|---|---|---|---|---|---|---|---|---|
| DEC-TE-00001 | test | 1 | 95910 | E1142 | APPROVE | approve_single | c1 MET, c2 NOT_APPLICABLE, c3 MET | NOT_MET -> DENY | hand numbness and weak grip, but the notes and the line's diagnosis give diabetic polyneuropathy (E11.42), another cause; carpal tunnel not mentioned (judgment: hand symptoms) |
| DEC-TE-00010 | test | 1 | 95910 | E1142 | APPROVE | approve_single | c1 MET, c2 NOT_APPLICABLE, c3 MET | NOT_MET -> DENY | leg symptoms; the line's diagnosis is diabetic polyneuropathy (E11.42), another cause |
| DEC-TE-00020 | test | 1 | 95910 | R202 | APPROVE | approve_single | c1 MET, c2 MET, c3 NOT_APPLICABLE | NOT_DOCUMENTED -> PEND | hand numbness and weak grip, a nerve lesion suspected; no other cause, no carpal tunnel |
| DEC-TE-00040 | test | 1 | 95907 | E1142 | PEND | pend_missing | c1 MET, c2 NOT_APPLICABLE, c3 NOT_DOCUMENTED | NOT_MET -> DENY | leg symptoms; the line's diagnosis is diabetic polyneuropathy (E11.42), another cause |
| DEC-TE-00041 | test | 1 | 95910 | E1142 | APPROVE | approve_single | c1 MET, c2 NOT_APPLICABLE, c3 MET | NOT_MET -> DENY | hand numbness and weak grip, but the notes and the line's diagnosis give diabetic polyneuropathy (E11.42), another cause; carpal tunnel not mentioned (judgment: hand symptoms) |
| DEC-TE-00046 | test | 1 | 95910 | M5412 | APPROVE | rule_denied_line | c1 MET, c2 MET, c3 NOT_APPLICABLE | NOT_MET -> DENY | leg symptoms; the line's diagnosis is radiculopathy (M54.12) |
| DEC-TE-00070 | test | 1 | 95910 | E1142 | PEND | pend_missing | c1 MET, c2 NOT_APPLICABLE, c3 NOT_DOCUMENTED | NOT_MET -> DENY | hand numbness and weak grip, but the notes and the line's diagnosis give diabetic polyneuropathy (E11.42), another cause; carpal tunnel not mentioned (judgment: hand symptoms) |
| DEC-TE-00080 | test | 2 | 95910 | R202 | APPROVE | office_plus_procedure | c1 MET, c2 MET, c3 NOT_APPLICABLE | NOT_DOCUMENTED -> PEND | hand numbness and weak grip, a nerve lesion suspected; no other cause, no carpal tunnel |
| DEC-TE-00089 | test | 1 | 95907 | E1142 | APPROVE | approve_single | c1 MET, c2 NOT_APPLICABLE, c3 MET | NOT_MET -> DENY | leg symptoms; the line's diagnosis is diabetic polyneuropathy (E11.42), another cause |
| DEC-TE-00096 | test | 2 | 95910 | E1142 | APPROVE | office_plus_procedure | c1 MET, c2 NOT_APPLICABLE, c3 MET | NOT_MET -> DENY | leg symptoms; the line's diagnosis is diabetic polyneuropathy (E11.42), another cause |

- Total: 10; expected v2: NOT_DOCUMENTED 2, NOT_MET 8.

## Foot care lines (11720, 11721): what Q4's new criteria touch

Lines billing 11720 or 11721: 207 in 196 records. Their v1 labels by split (source and decision):

| Split | v1 label | Lines |
|---|---|---|
| test | MODEL APPROVE | 5 |
| test | MODEL DENY | 7 |
| test | MODEL PEND | 1 |
| test | RULE DENY | 1 |
| train | MODEL APPROVE | 60 |
| train | MODEL DENY | 85 |
| train | MODEL PEND | 25 |
| train | RULE DENY | 9 |
| validation | MODEL APPROVE | 6 |
| validation | MODEL DENY | 7 |
| validation | RULE DENY | 1 |

- v1 FOOT-001 statuses on these lines: c1 MET 44, c1 NOT_APPLICABLE 57, c1 NOT_DOCUMENTED 13, c1 NOT_MET 82, c2 MET 38, c2 NOT_APPLICABLE 139, c2 NOT_DOCUMENTED 19, c3 MET 93, c3 NOT_DOCUMENTED 18, c3 NOT_MET 85
- Scenarios: deny_exclusion 68, approve_single 25, rule_denied_line 22, two_policy 21, pend_missing 17, office_same_day 17, office_plus_procedure 14, deny_dx 13, deny_criterion 10
- Lines with onychomycosis (B351, the mycotic-nail path of the new c5): 190
- Diagnoses on these lines (lines with each code): B351 190, Z7901 50, E1140 48, E1142 46, G609 45, G4733 6, M79671 2, J069 2, K5900 2, I10 2, M1711 1, L237 1, F419 1

## Lines billing 93241: v1 labels and v2 c5 (extended triage A4)

v2 POL-CAR-002.c5 is the only criterion on 93241 and covers continuous recording beyond 48 hours only to check the response to treatment (L34636 cov-019); the infrequent-symptoms path is for event monitors. The reading comes from the wording of the v1 c3 evidence; the v2 status follows D-POL-3 (another purpose: NOT_MET, DENY; silent: NOT_DOCUMENTED, PEND). For generator v2; the v1 dataset is not changed.

| Split | v1 label | v1 c3 | Reading of the v1 label | v2 c5 | v2 decision | Lines |
|---|---|---|---|---|---|---|
| test | MODEL APPROVE | MET | infrequent symptoms | NOT_MET | DENY | 2 |
| test | MODEL DENY | NOT_MET | another purpose | NOT_MET | DENY | 1 |
| test | MODEL PEND | MET | infrequent symptoms | NOT_MET | DENY | 2 |
| test | MODEL PEND | NOT_DOCUMENTED | silent | NOT_DOCUMENTED | PEND | 1 |
| train | MODEL APPROVE | MET | infrequent symptoms | NOT_MET | DENY | 22 |
| train | MODEL DENY | MET | infrequent symptoms | NOT_MET | DENY | 3 |
| train | MODEL DENY | NOT_MET | another purpose | NOT_MET | DENY | 14 |
| train | MODEL DENY | NOT_MET | frequent symptoms | NOT_MET | DENY | 12 |
| train | MODEL PEND | MET | infrequent symptoms | NOT_MET | DENY | 7 |
| train | MODEL PEND | NOT_DOCUMENTED | silent | NOT_DOCUMENTED | PEND | 15 |
| train | RULE DENY | - | decided by a rule | - | unchanged | 7 |
| validation | MODEL APPROVE | MET | infrequent symptoms | NOT_MET | DENY | 4 |
| validation | MODEL DENY | NOT_MET | another purpose | NOT_MET | DENY | 2 |
| validation | MODEL PEND | MET | infrequent symptoms | NOT_MET | DENY | 3 |
| validation | MODEL PEND | NOT_DOCUMENTED | silent | NOT_DOCUMENTED | PEND | 2 |

- Lines billing 93241: 97; v1 labels resting on the infrequent-symptoms reading: 43; labels whose decision changes under v2 c5: 40.

## v1 criteria whose text did not match the source (for the final report)

Lines whose v1 gold label used the criterion (status other than NOT_APPLICABLE).

| v1 criterion | Why | Train | Validation | Test | Records |
|---|---|---|---|---|---|
| POL-SURG-004.c2 | V1b WRONG CRITERION (SURG-004.F1) | 162 | 28 | 17 | 207 |
| POL-SURG-004.c3 | V1b WRONG CRITERION (SURG-004.F1) | 162 | 28 | 17 | 207 |
| POL-DX-003.c1 | V1b WRONG CRITERION (DX-003.F1) | 120 | 19 | 12 | 108 |
| POL-REHAB-001.c2 | V1b WRONG CRITERION (REHAB-001.F1) | 228 | 30 | 23 | 205 |
| POL-CAR-002.c2 | V1b WRONG CRITERION (CAR-002.F1) | 44 | 8 | 4 | 56 |
| POL-DX-001.c3 | B7: limit dropped or changed | 0 | 0 | 8 | 8 |
| POL-IMG-002.c2 | B20: limit dropped or changed | 0 | 0 | 8 | 8 |
| POL-BH-001.c1 | KB1: limit dropped or changed | 132 | 13 | 18 | 108 |
| POL-CAR-001.c2 | KB4: hedge or qualifier only | 54 | 7 | 7 | 68 |
| POL-CAR-001.c3 | KB5: limit dropped or changed | 68 | 7 | 10 | 85 |
| POL-DX-002.c1 | KB8: hedge or qualifier only | 0 | 0 | 38 | 33 |
| POL-DX-003.c2 | KB11: limit dropped or changed | 38 | 11 | 4 | 53 |
| POL-DX-003.c3 | KB12: hedge or qualifier only | 158 | 30 | 16 | 161 |
| POL-IMG-001.c3 | KB17: limit dropped or changed | 41 | 10 | 3 | 54 |
| POL-IMG-002.c1 | KB19: limit dropped or changed | 0 | 0 | 19 | 19 |
| POL-PAIN-001.c3 | KB24: hedge or qualifier only | 127 | 15 | 11 | 153 |
| POL-PAIN-002.c2 | KB26: hedge or qualifier only | 139 | 27 | 16 | 182 |
| POL-REHAB-001.c1 | KB28: limit dropped or changed | 228 | 30 | 23 | 205 |
| POL-REHAB-001.c3 | KB29: limit dropped or changed | 183 | 27 | 18 | 152 |

- V1b WRONG CRITERION (4 findings): 5 criteria; 695 lines in 576 records.
- kept texts with a limit dropped or changed: 9 criteria; 663 lines in 532 records.
- kept texts that only lost a hedge or qualifier: 5 criteria; 645 lines in 573 records.
- wrong or limit changed (hedge-only left out): 14 criteria; 1077 lines in 896 records.
- all of them: 19 criteria; 1518 lines in 1302 records.
- Lines shown any criteria, all splits: 3335.

## SURG-002.F3: which L34005 limitations R15 already catches

R15 for 45378 (A56456): A56456 v32, ICD-10-CM group 1, or a group 2A primary with a group 2B secondary diagnosis; R15 (D-RULE-4): the group 2A code must be the line's first diagnosis. A limitation is caught when a line whose diagnoses are only its codes fails R15; codes A56456 covers in group 1 pass R15 alone, so the policy needs the criterion.

| Limitation | ICD-10-CM codes matched | In group 1 (R15 passes alone) | In groups 2 or 3 | Not covered |
|---|---|---|---|---|
| cov-037 irritable bowel syndrome | 5 | K580 K581 K589 | - | 2 |
| cov-037 chronic abdominal pain | 11 | R1011 R1012 R1013 R1031 R1032 R1033 R1084 R109 | - | 3 |
| cov-038 diarrhea (acute is not coded) | 4 | K580 K591 R197 | - | 1 |
| cov-039 hemorrhoids | 12 | K640 K641 K642 K643 | - | 8 |
| cov-040 malignancy of unknown primary | 3 | - | - | 3 |
| cov-048 diverticulitis | 8 | K5720 K5721 K5732 K5733 K5740 K5741 K5752 K5753 | - | 0 |
| cov-049 diverticulosis | 4 | K5730 K5731 K5750 K5751 | - | 0 |
