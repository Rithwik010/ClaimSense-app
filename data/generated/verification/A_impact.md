# Task V1a follow-up 2: impact of the ESI decisions (D-ESI-1 to D-ESI-6)

**Scope: ESI lines only (22 of 386 test lines). This does not estimate NOT_APPLICABLE label quality for other policies; check 5 showed most of those cannot be verified automatically.**

Every number below is an **estimate** from the text patterns listed in section 2, applied to the existing records without modifying them. It does not replace `docs/results.md`.

## Summary

| Measure | Value |
|---|---|
| ESI lines (decided), all splits | 222 (headline 176; excluded 46: D-ESI-5 contradictory notes 21, diagnosis mismatch 25, conflicting duration 3; a line can be in more than one) |
| POL-PAIN-001 status labels changed (c2 to c5), headline | 234 |
| Line decisions changed, headline | 95 |
| Test: model decision errors that become correct | 3 of 11 changed test decisions |
| Test macro-F1, gold labels, all 386 lines (docs/results.md) | 0.6720 |
| Test macro-F1, gold labels, headline line set (384 lines) | 0.6732 |
| **Estimated test macro-F1, corrected labels (D-ESI-1, D-ESI-2, c4), headline set** | **0.6677** (accuracy 0.6875) |
| Estimated test macro-F1, also D-ESI-4 and D-ESI-3 (383 lines; R14 lines leave model scoring) | 0.6692 (accuracy 0.6893) |

## 1. Pattern validation

Agreement of each pattern with the existing gold labels where the decisions do not change the rule. The agreed basis excludes diagnosis-mismatch lines (section 4), whose gold statuses are placed by retrieval rank. Stop rule: below 95% on the agreed basis.

| Pattern | Reference (gold) | Lines (basis) | Agreement (basis) | All lines | Example disagreements (basis) |
|---|---|---|---|---|---|
| previous injection | found exactly when gold assesses POL-PAIN-001.c5 | 197 | 100.0% | 97.7% (n=222) | none |
| c2 re-derivation | equals gold where gold assesses c2 | 133 | 100.0% | 98.0% (n=153) | none |
| c2 re-derivation, mechanical | equals gold where gold assesses c2 | 133 | 97.0% | 92.8% (n=153) | DEC-TR-00361 line 1 (62321, two_policy): mechanical NOT_MET, gold NOT_DOCUMENTED<br>DEC-TR-00922 line 1 (62321, two_policy): mechanical NOT_MET, gold NOT_DOCUMENTED<br>DEC-TR-01275 line 1 (62323, two_policy): mechanical MET, gold NOT_MET |
| c3 re-derivation | equals gold where gold assesses c3 | 133 | 98.5% | 96.7% (n=153) | DEC-TR-00924 line 1 (64483, two_policy): re-derived MET, gold NOT_MET<br>DEC-TR-01261 line 1 (62321, two_policy): re-derived MET, gold NOT_MET |
| 4-weeks-or-more statement | found where gold POL-PAIN-001.c3 is MET | 111 | 100.0% | 100.0% (n=111) | none |
| radicular statement | found where gold POL-PAIN-001.c1 is MET | 169 | 100.0% | 100.0% (n=169) | none |
| facet sentence | found where gold POL-PAIN-002.c1 or c2 is MET or NOT_MET | 260 | 100.0% | 90.0% (n=289) | none |
| no pain down the limbs | found exactly when gold POL-PAIN-002.c3 is MET | 133 | 100.0% | 100.0% (n=138) | none |
| c4 re-derivation | equals gold where gold assesses c4 | 64 | 100.0% | 94.2% (n=69) | none |
| c5 re-derivation | equals gold where gold assesses c5 | 64 | 100.0% | 92.8% (n=69) | none |
| axial or back-only (ESI c2 exclusion) | found where gold POL-PAIN-002.c1 is MET or NOT_MET (axial pain described) | 129 | 100.0% | 83.2% (n=155) | none |
| radicular statement (facet reference) | found where gold POL-PAIN-002.c3 is NOT_MET | 11 | 100.0% | 68.8% (n=16) | none |
| under-4-week statement | found where gold POL-PAIN-001.c3 is NOT_MET | 11 | 100.0% | 100.0% (n=11) | none |

## 2. Patterns

All case-insensitive. Notes are split into sentences at `.`, `!` or `?` followed by a space.

| Name | Regular expression |
|---|---|
| previous injection | `\b(?:repeat\|prior\|previous\|earlier\|last\|first\|second)\s+(?:injection\|esi)s?\b` |
| radicular statement | `\btravels down the (?:left\|right) (?:leg\|arm)\b\|\bradiating to (?:left\|right) (?:leg\|arm)\b\|\bshoots down the (?:left\|right) leg\b\|\bradicular pain to\b\|\b(?:pressing on\|pressure on\|compressing)\s+(?:the\s+)?(?:(?:left\|right)\s+)?[CLST]\d\s+(?:nerve\s+)?root\b\|\bfor (?:leg\|arm) pain\b` |
| no pain down the limbs | `\bno pain or numbness down the limbs\b\|\bno radicular sx\b` |
| axial or back-only (ESI c2 exclusion) | `\bmainly in the [a-z ]+ itself\b\|\baxial\b\|\bno pain or numbness down the limbs\b\|\bno radicular sx\b\|\b(?:low back\|neck) pain is\b\|\bmild (?:low back\|neck) pain\b` |
| back-pain statement (D-ESI-4, with the c2 exclusion markers) | `\bchronic (?:axial )?(?:low back\|neck) pain\b\|\bchronic axial LBP\b` |
| score | `\b\d{1,2}/10\b\|\b(?:Oswestry\|Neck Disability Index\|disability score\|ODI\|NDI)\b\|\bdisability \d{1,3}%` |
| mild or no limits | `\bmild\b\|\bno limits\b\|\bADLs unaffected\b\|\bdoes not limit\b\|\bno functional limits\b` |
| duration | `(\d+)\s*(days?\|d\|weeks?\|wks?\|months?\|mos?)\b` |
| conservative care failed | `\bdespite\b\|\bhave not helped\b\|\bfailed\b` |
| no conservative care tried | `\bno (?:other )?(?:treatment\|therapy\|conservative tx\|PT)\b[^.;]*\btried\b` |
| symptom onset | `\b(?:started\|began\|onset)\b` |
| symptom duration | `\b(?:lasted\|despite\|have not helped\|failed)\b\|\bSx\s*x\d` |
| injection result (never a symptom duration) | `\brelief\b\|\binjection\b\|\bESI\b` |
| shingles | `\bshingles\b\|\bzoster\b` |
| guidance with contrast | `\bfluoroscopy with contrast\b\|\bfluoro-guided w/ contrast\b\|\bCT (?:guidance )?with contrast\b` |
| too many levels | `\bfour levels\b\|\b4-level\b` |
| relief | `(\d{1,3})%\s*(?:pain\s+)?relief` |
| relief duration | `(?:lasted about\|x)\s*(\d+)\s*(?:months\|mo)\b` |
| function improvement | `(\d{1,3})%\s*(?:improvement in function\|functional improvement)` |
| facet sentence | `\bmainly in the (?:low back\|neck) itself\b\|\bAxial (?:low back\|neck) pain \d+/10\b\|\b(?:Low back\|Neck) pain is mild\b\|\bMild (?:low back\|neck) pain \d+/10\b\|\bPain has lasted \d+ months despite physical therapy and medication\b\|\bSx x\d+ mo, failed PT \+ meds\b\|\bPain began \d+ weeks ago, and no therapy has been tried\b\|\bOnset \d+wk ago; no PT tried\b` |
| synovial cyst | `\bsynovial cyst\b\|\bfacet (?:joint )?cyst\b` |

Rules built on them:

- **First vs repeat:** repeat when `previous injection` matches the notes.
- **c2 (D-ESI-2):** sentences matching `score`; headline drops those matching the `axial or back-only` markers. MET if one counted sentence lacks `mild or no limits`; NOT_MET if all counted sentences have it; NOT_DOCUMENTED if none. Mechanical variant: no sentence dropped.
- **c3 (D-ESI-1):** MET if a sentence has `conservative care failed` and a `duration` of at least 4 weeks; else MET on `shingles` (the LCD's zoster exemption; no NASS exemption); else NOT_MET on `no conservative care tried`; else NOT_DOCUMENTED.
- **Conflicting duration:** the notes have both a `symptom onset` sentence under 4 weeks and a `symptom duration` sentence of 4 weeks or more (sentences matching `injection result` never count).
- **c4 (D-ESI-1):** NOT_MET on `too many levels`; MET on `guidance with contrast`; otherwise NOT_DOCUMENTED.
- **c5 (D-ESI-2):** NOT_APPLICABLE on a first injection; otherwise MET when a `relief` of at least 50% has a `relief duration` of at least 3 months, or a `function improvement` of at least 50%; NOT_MET when every result falls short; NOT_DOCUMENTED when none.
- **Decision:** the prompt's rule on gold c1 and re-derived c2 to c5; the NCCI_BYPASS branch is kept where gold shows it fired.
- **D-ESI-5 contradiction:** `radicular statement` and `no pain down the limbs` in the same notes.
- **D-ESI-4:** no `radicular statement`, and an axial or back-pain statement (`axial or back-only` or `back-pain statement`). Silence is not an exclusion (D-ESI-6).
- **D-ESI-3 (R14):** another line on the claim with the same date of service and a code in 62321, 62323, 64483, 64490, 64493 (ESIs and facet joint nerve blocks from `data/curated/procedure_scope.csv`; 64635 radiofrequency destruction excluded; no sympathetic block or trigger point code is in scope), unless `synovial cyst` matches.

## 3. Status and decision changes on ESI lines (headline)

All three ESI codes, every split, with 62323 broken out. Excluded lines are in section 4.

### POL-PAIN-001.c2

| Change | train | validation | test | all | of which 62323 |
|---|---|---|---|---|---|
| NOT_APPLICABLE → NOT_DOCUMENTED | 45 | 4 | 9 | 58 | 58 |

### POL-PAIN-001.c3

| Change | train | validation | test | all | of which 62323 |
|---|---|---|---|---|---|
| NOT_APPLICABLE → NOT_DOCUMENTED | 45 | 4 | 9 | 58 | 58 |

### POL-PAIN-001.c4

| Change | train | validation | test | all | of which 62323 |
|---|---|---|---|---|---|
| NOT_APPLICABLE → NOT_DOCUMENTED | 95 | 13 | 10 | 118 | 28 |

Initial-injection notes never document guidance with contrast. For 62321 and 62323 the plan line repeats the project's procedure description, "with imaging guidance", which does not document contrast, so c4 stays NOT_DOCUMENTED.

### POL-PAIN-001.c5

No changes.

### POL-PAIN-001.c2, mechanical variant (every score counts)

| Change | train | validation | test | all | of which 62323 |
|---|---|---|---|---|---|
| NOT_APPLICABLE → NOT_DOCUMENTED | 45 | 4 | 9 | 58 | 58 |

### Line decision

| Change | train | validation | test | all | of which 62323 |
|---|---|---|---|---|---|
| APPROVE → PEND | 72 | 12 | 11 | 95 | 47 |

**Headline lines whose c2 or c3 still depends on a facet sentence:** 0 of 176.

## 4. Lines excluded from the headline

### D-ESI-5: records with contradictory notes (21 records, all scenario types)

Their notes will be regenerated in v2. Current gold decisions of all their lines:

| Record | Split | Scenario | Line decisions (gold, source) |
|---|---|---|---|
| DEC-TR-00037 | train | two_policy | line 1 62323 APPROVE (MODEL); line 2 64493 APPROVE (MODEL) |
| DEC-TR-00172 | train | two_policy | line 1 64483 APPROVE (MODEL); line 2 64493 APPROVE (MODEL) |
| DEC-TR-00361 | train | two_policy | line 1 62321 PEND (MODEL); line 2 64490 DENY (MODEL) |
| DEC-TR-00450 | train | two_policy | line 1 62323 APPROVE (MODEL); line 2 64635 APPROVE (MODEL) |
| DEC-TR-00470 | train | two_policy | line 1 62323 APPROVE (MODEL); line 2 64493 APPROVE (MODEL) |
| DEC-TR-00717 | train | two_policy | line 1 62321 APPROVE (MODEL); line 2 64635 APPROVE (MODEL) |
| DEC-TR-00785 | train | two_policy | line 1 64483 APPROVE (MODEL); line 2 64490 APPROVE (MODEL) |
| DEC-TR-00922 | train | two_policy | line 1 62321 PEND (MODEL); line 2 64490 DENY (MODEL) |
| DEC-TR-00924 | train | two_policy | line 1 64483 DENY (MODEL); line 2 64490 APPROVE (MODEL) |
| DEC-TR-01144 | train | two_policy | line 1 62321 DENY (MODEL); line 2 64493 APPROVE (MODEL) |
| DEC-TR-01261 | train | two_policy | line 1 62321 DENY (MODEL); line 2 64635 PEND (MODEL) |
| DEC-TR-01275 | train | two_policy | line 1 62323 DENY (MODEL); line 2 64635 APPROVE (MODEL) |
| DEC-TR-01330 | train | two_policy | line 1 62321 APPROVE (MODEL); line 2 64635 DENY (MODEL) |
| DEC-TR-01407 | train | two_policy | line 1 62323 APPROVE (MODEL); line 2 64635 APPROVE (MODEL) |
| DEC-TR-01552 | train | two_policy | line 1 62323 APPROVE (MODEL); line 2 64493 PEND (MODEL) |
| DEC-TR-01569 | train | two_policy | line 1 62323 APPROVE (MODEL); line 2 64493 APPROVE (MODEL) |
| DEC-TR-01722 | train | two_policy | line 1 62321 APPROVE (MODEL); line 2 64490 PEND (MODEL) |
| DEC-VA-00092 | validation | two_policy | line 1 62323 APPROVE (MODEL); line 2 64490 APPROVE (MODEL) |
| DEC-VA-00143 | validation | two_policy | line 1 62323 APPROVE (MODEL); line 2 64493 APPROVE (MODEL) |
| DEC-VA-00168 | validation | two_policy | line 1 64483 PEND (MODEL); line 2 64490 PEND (MODEL) |
| DEC-TE-00185 | test | two_policy | line 1 62323 APPROVE (MODEL); line 2 64635 APPROVE (MODEL) |

### Conflicting duration (3 ESI lines)

DEC-TR-00924 line 1 (train, gold DENY, also D-ESI-5); DEC-TR-01261 line 1 (train, gold DENY, also D-ESI-5); DEC-TR-01330 line 1 (train, gold APPROVE, also D-ESI-5)

### Diagnosis-mismatch lines, all policies

Detected with check 1's rule: the line's pointed diagnoses do not satisfy the billing article's covered rule for its procedure. **Caveat:** this uses `app/db/raw.read_article_diagnoses`, the same reader the generator uses, so it is not an independent check of that reader. Gold is kept; these lines are out of the headline. "Indication criterion" means the policy's c1: in every curated policy c1 states the covered indication (POL-REHAB-001.c1, skilled-service need, is the closest to an exception); some policies also have alternative indications (for example POL-CAR-001.c3, POL-DX-003.c2), which this count treats as not c1.

| Policy | Lines | Gold decisions | NOT_MET criterion (count) | Position of the NOT_MET in the retrieved order | NOT_MET is the first applicable | NOT_MET not on c1 |
|---|---|---|---|---|---|---|
| POL-BH-001 | 27 | DENY 27 | POL-BH-001.c1 21, POL-BH-001.c3 3, POL-BH-001.c2 3 | 1: 24, 2: 3 | 27 of 27 | 6 of 27 |
| POL-CAR-001 | 42 | DENY 42 | POL-CAR-001.c1 28, POL-CAR-001.c3 13, POL-CAR-001.c2 1 | 1: 32, 2: 10 | 32 of 42 | 14 of 42 |
| POL-CAR-002 | 39 | DENY 39 | POL-CAR-002.c3 25, POL-CAR-002.c1 14 | 1: 25, 2: 14 | 39 of 39 | 25 of 39 |
| POL-DX-001 | 3 | DENY 3 | POL-DX-001.c3 2, POL-DX-001.c1 1 | 1: 3 | 3 of 3 | 2 of 3 |
| POL-DX-002 | 6 | DENY 6 | POL-DX-002.c1 4, POL-DX-002.c3 1, POL-DX-002.c2 1 | 1: 5, 2: 1 | 6 of 6 | 2 of 6 |
| POL-DX-003 | 25 | DENY 25 | POL-DX-003.c1 17, POL-DX-003.c2 7, POL-DX-003.c3 1 | 1: 25 | 25 of 25 | 8 of 25 |
| POL-FOOT-001 | 18 | DENY 18 | POL-FOOT-001.c3 17, POL-FOOT-001.c1 1 | 1: 16, 2: 2 | 18 of 18 | 17 of 18 |
| POL-IMG-001 | 29 | DENY 29 | POL-IMG-001.c2 16, POL-IMG-001.c1 7, POL-IMG-001.c3 6 | 1: 8, 2: 12, 3: 7, 4: 2 | 29 of 29 | 22 of 29 |
| POL-IMG-002 | 4 | DENY 4 | POL-IMG-002.c1 4 | 1: 2, 2: 1, 3: 1 | 4 of 4 | 0 of 4 |
| POL-PAIN-001 | 25 | DENY 25 | POL-PAIN-001.c1 18, POL-PAIN-001.c4 4, POL-PAIN-001.c2 3 | 1: 13, 2: 12 | 25 of 25 | 7 of 25 |
| POL-PAIN-002 | 34 | DENY 34 | POL-PAIN-002.c1 26, POL-PAIN-002.c3 5, POL-PAIN-002.c2 3 | 1: 33, 2: 1 | 34 of 34 | 8 of 34 |
| POL-REHAB-001 | 40 | DENY 40 | POL-REHAB-001.c2 36, POL-REHAB-001.c1 2, POL-REHAB-001.c3 2 | 1: 40 | 40 of 40 | 38 of 40 |
| POL-SURG-001 | 16 | DENY 16 | POL-SURG-001.c1 13, POL-SURG-001.c2 3 | 1: 16 | 16 of 16 | 3 of 16 |
| POL-SURG-002 | 19 | DENY 19 | POL-SURG-002.c1 10, POL-SURG-002.c2 9 | 1: 11, 2: 7, 3: 1 | 19 of 19 | 9 of 19 |
| POL-SURG-003 | 9 | DENY 9 | POL-SURG-003.c1 9, POL-SURG-003.c3 2 | 1: 9, 3: 2 | 9 of 11 | 2 of 11 |
| POL-SURG-004 | 24 | DENY 24 | POL-SURG-004.c1 15, POL-SURG-004.c2 6, POL-SURG-004.c3 3 | 1: 19, 2: 5 | 24 of 24 | 9 of 24 |
| POL-WOUND-001 | 31 | DENY 31 | POL-WOUND-001.c1 20, POL-WOUND-001.c2 11 | 1: 26, 2: 5 | 31 of 31 | 11 of 31 |

Totals: 391 lines; gold decisions DENY 391; NOT_MET criteria per line: 1: 389, 2: 2; NOT_MET not on c1: 183 of 393.

## 5. two_policy claims

two_policy records: 134; with an ESI line: 35.

**(a) Contradictory notes (D-ESI-5 pattern):** 21 two_policy records (train 17, validation 3, test 1); 0 other records match. Listed in section 4.

**(b) An ESI line and another block on the same date of service** (codes 62321, 62323, 64483, 64490, 64493; 64635 excluded):

| Record | Split | Scenario | ESI line (gold decision) | Other block lines |
|---|---|---|---|---|
| DEC-TE-00243 | test | two_policy | line 1 62323: APPROVE (MODEL) | line 2 64493 |
| DEC-TR-00037 | train | two_policy | line 1 62323: APPROVE (MODEL) | line 2 64493 |
| DEC-TR-00172 | train | two_policy | line 1 64483: APPROVE (MODEL) | line 2 64493 |
| DEC-TR-00336 | train | two_policy | line 1 62321: DENY (MODEL) | line 2 64493 |
| DEC-TR-00361 | train | two_policy | line 1 62321: PEND (MODEL) | line 2 64490 |
| DEC-TR-00470 | train | two_policy | line 1 62323: APPROVE (MODEL) | line 2 64493 |
| DEC-TR-00785 | train | two_policy | line 1 64483: APPROVE (MODEL) | line 2 64490 |
| DEC-TR-00922 | train | two_policy | line 1 62321: PEND (MODEL) | line 2 64490 |
| DEC-TR-00924 | train | two_policy | line 1 64483: DENY (MODEL) | line 2 64490 |
| DEC-TR-01085 | train | two_policy | line 1 62321: DENY (MODEL) | line 2 64490 |
| DEC-TR-01140 | train | two_policy | line 1 62323: PEND (MODEL) | line 2 64490 |
| DEC-TR-01144 | train | two_policy | line 1 62321: DENY (MODEL) | line 2 64493 |
| DEC-TR-01283 | train | two_policy | line 1 62321: DENY (MODEL) | line 2 64490 |
| DEC-TR-01460 | train | two_policy | line 1 62323: PEND (MODEL) | line 2 64490 |
| DEC-TR-01552 | train | two_policy | line 1 62323: APPROVE (MODEL) | line 2 64493 |
| DEC-TR-01569 | train | two_policy | line 1 62323: APPROVE (MODEL) | line 2 64493 |
| DEC-TR-01591 | train | two_policy | line 1 64483: DENY (MODEL) | line 2 64493 |
| DEC-TR-01722 | train | two_policy | line 1 62321: APPROVE (MODEL) | line 2 64490 |
| DEC-TR-01756 | train | two_policy | line 1 64483: DENY (MODEL) | line 2 64490 |
| DEC-TR-01944 | train | two_policy | line 1 62321: APPROVE (MODEL) | line 2 64493 |
| DEC-VA-00021 | validation | two_policy | line 1 62323: APPROVE (MODEL) | line 2 64493 |
| DEC-VA-00092 | validation | two_policy | line 1 62323: APPROVE (MODEL) | line 2 64490 |
| DEC-VA-00143 | validation | two_policy | line 1 62323: APPROVE (MODEL) | line 2 64493 |
| DEC-VA-00168 | validation | two_policy | line 1 64483: PEND (MODEL) | line 2 64490 |

Across all scenarios: 32 ESI lines; 24 in two_policy. Same code on both lines (bilateral use; see follow-ups): 0. Synovial-cyst exceptions: 0.

**(c) ESI lines that would become DENY:**

| Rule | two_policy: becomes DENY | two_policy: already DENY | all scenarios: becomes DENY | all scenarios: already DENY |
|---|---|---|---|---|
| D-ESI-3 (R14) | 17 | 7 | 20 | 12 |
| D-ESI-4 (limitation 5) | 0 | 4 | 0 | 4 |
| either | 17 | 8 | 20 | 13 |

## 6. Test split: model predictions against gold and re-derived labels

Every headline test line whose re-derived status or decision differs from gold. Statuses come from the model's saved answer (`data/generated/eval/finetuned-v1.jsonl`); decisions are its effective decisions (an invalid answer is PEND).

| Record | Line | Code | Field | Gold | Re-derived | Model | Result |
|---|---|---|---|---|---|---|---|
| DEC-TE-00103 | 1 | 62321 | c4 | NOT_APPLICABLE | NOT_DOCUMENTED | NOT_APPLICABLE | model matched gold, differs from re-derived |
| DEC-TE-00110 | 1 | 62323 | c2 | NOT_APPLICABLE | NOT_DOCUMENTED | NOT_APPLICABLE | model matched gold, differs from re-derived |
| DEC-TE-00110 | 1 | 62323 | c3 | NOT_APPLICABLE | NOT_DOCUMENTED | NOT_APPLICABLE | model matched gold, differs from re-derived |
| DEC-TE-00114 | 1 | 62323 | c4 | NOT_APPLICABLE | NOT_DOCUMENTED | (invalid answer) | neither |
| DEC-TE-00133 | 1 | 62323 | c2 | NOT_APPLICABLE | NOT_DOCUMENTED | NOT_APPLICABLE | model matched gold, differs from re-derived |
| DEC-TE-00133 | 1 | 62323 | c3 | NOT_APPLICABLE | NOT_DOCUMENTED | NOT_APPLICABLE | model matched gold, differs from re-derived |
| DEC-TE-00133 | 1 | 62323 | decision | APPROVE | PEND | APPROVE | model matched gold, differs from re-derived |
| DEC-TE-00174 | 1 | 64483 | c4 | NOT_APPLICABLE | NOT_DOCUMENTED | NOT_APPLICABLE | model matched gold, differs from re-derived |
| DEC-TE-00174 | 1 | 64483 | decision | APPROVE | PEND | APPROVE | model matched gold, differs from re-derived |
| DEC-TE-00179 | 1 | 62323 | c4 | NOT_APPLICABLE | NOT_DOCUMENTED | NOT_APPLICABLE | model matched gold, differs from re-derived |
| DEC-TE-00179 | 1 | 62323 | decision | APPROVE | PEND | APPROVE | model matched gold, differs from re-derived |
| DEC-TE-00209 | 1 | 62321 | c4 | NOT_APPLICABLE | NOT_DOCUMENTED | NOT_APPLICABLE | model matched gold, differs from re-derived |
| DEC-TE-00223 | 1 | 64483 | c4 | NOT_APPLICABLE | NOT_DOCUMENTED | NOT_APPLICABLE | model matched gold, differs from re-derived |
| DEC-TE-00231 | 1 | 64483 | c4 | NOT_APPLICABLE | NOT_DOCUMENTED | NOT_APPLICABLE | model matched gold, differs from re-derived |
| DEC-TE-00231 | 1 | 64483 | decision | APPROVE | PEND | APPROVE | model matched gold, differs from re-derived |
| DEC-TE-00232 | 2 | 64483 | c4 | NOT_APPLICABLE | NOT_DOCUMENTED | NOT_APPLICABLE | model matched gold, differs from re-derived |
| DEC-TE-00232 | 2 | 64483 | decision | APPROVE | PEND | PEND | model error that matches re-derived |
| DEC-TE-00243 | 1 | 62323 | c2 | NOT_APPLICABLE | NOT_DOCUMENTED | NOT_APPLICABLE | model matched gold, differs from re-derived |
| DEC-TE-00243 | 1 | 62323 | c3 | NOT_APPLICABLE | NOT_DOCUMENTED | NOT_APPLICABLE | model matched gold, differs from re-derived |
| DEC-TE-00243 | 1 | 62323 | decision | APPROVE | PEND | APPROVE | model matched gold, differs from re-derived |
| DEC-TE-00259 | 2 | 62323 | c2 | NOT_APPLICABLE | NOT_DOCUMENTED | NOT_APPLICABLE | model matched gold, differs from re-derived |
| DEC-TE-00259 | 2 | 62323 | c3 | NOT_APPLICABLE | NOT_DOCUMENTED | NOT_APPLICABLE | model matched gold, differs from re-derived |
| DEC-TE-00259 | 2 | 62323 | decision | APPROVE | PEND | APPROVE | model matched gold, differs from re-derived |
| DEC-TE-00262 | 2 | 62323 | c4 | NOT_APPLICABLE | NOT_DOCUMENTED | NOT_APPLICABLE | model matched gold, differs from re-derived |
| DEC-TE-00262 | 2 | 62323 | decision | APPROVE | PEND | PEND | model error that matches re-derived |
| DEC-TE-00273 | 1 | 62323 | c2 | NOT_APPLICABLE | NOT_DOCUMENTED | (invalid answer) | neither |
| DEC-TE-00273 | 1 | 62323 | c3 | NOT_APPLICABLE | NOT_DOCUMENTED | (invalid answer) | neither |
| DEC-TE-00278 | 1 | 62323 | c2 | NOT_APPLICABLE | NOT_DOCUMENTED | NOT_APPLICABLE | model matched gold, differs from re-derived |
| DEC-TE-00278 | 1 | 62323 | c3 | NOT_APPLICABLE | NOT_DOCUMENTED | NOT_APPLICABLE | model matched gold, differs from re-derived |
| DEC-TE-00278 | 1 | 62323 | decision | APPROVE | PEND | APPROVE | model matched gold, differs from re-derived |
| DEC-TE-00279 | 2 | 62323 | c2 | NOT_APPLICABLE | NOT_DOCUMENTED | NOT_DOCUMENTED | model error that matches re-derived |
| DEC-TE-00279 | 2 | 62323 | c3 | NOT_APPLICABLE | NOT_DOCUMENTED | NOT_APPLICABLE | model matched gold, differs from re-derived |
| DEC-TE-00291 | 2 | 62321 | c4 | NOT_APPLICABLE | NOT_DOCUMENTED | NOT_APPLICABLE | model matched gold, differs from re-derived |
| DEC-TE-00291 | 2 | 62321 | decision | APPROVE | PEND | PEND | model error that matches re-derived |
| DEC-TE-00298 | 2 | 62323 | c2 | NOT_APPLICABLE | NOT_DOCUMENTED | NOT_APPLICABLE | model matched gold, differs from re-derived |
| DEC-TE-00298 | 2 | 62323 | c3 | NOT_APPLICABLE | NOT_DOCUMENTED | NOT_APPLICABLE | model matched gold, differs from re-derived |
| DEC-TE-00298 | 2 | 62323 | decision | APPROVE | PEND | APPROVE | model matched gold, differs from re-derived |
| DEC-TE-00300 | 2 | 62323 | c2 | NOT_APPLICABLE | NOT_DOCUMENTED | NOT_APPLICABLE | model matched gold, differs from re-derived |
| DEC-TE-00300 | 2 | 62323 | c3 | NOT_APPLICABLE | NOT_DOCUMENTED | NOT_APPLICABLE | model matched gold, differs from re-derived |

Status changes: model matched gold, differs from re-derived 24, neither 3, model error that matches re-derived 1. Decision changes: model matched gold, differs from re-derived 8, model error that matches re-derived 3.

**Estimate, not a result** (does not replace `docs/results.md`):

| Line set and labels | Lines | Line accuracy | Macro-F1 |
|---|---|---|---|
| All test lines, gold (docs/results.md) | 386 | 0.6995 | 0.6720 |
| Headline set, gold | 384 | 0.7005 | 0.6732 |
| Headline set, corrected (D-ESI-1, D-ESI-2, c4) | 384 | 0.6875 | 0.6677 |
| Headline set, corrected + D-ESI-4, R14 lines removed | 383 | 0.6893 | 0.6692 |

The headline set drops the test lines of D-ESI-5 records and conflicting-duration lines (their correct labels are unknown). Diagnosis-mismatch lines stay in the metric with their gold label, which no D-ESI decision changes.
