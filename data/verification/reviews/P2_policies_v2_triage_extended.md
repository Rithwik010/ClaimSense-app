# Policies v2 review sheet: extended author triage

Extended author triage (2026-10-10): Claude Code, the author of the criteria, triaged the other 15 Part A MATCHES rows, row A31 and the 31 Part B AGREE rows in P2_policies_v2_triage_extended.md; not an independent check. Nothing in it is applied until the reviewer approves it.

The 47 rows: the other 15 Part A MATCHES rows, row A31 and the 31 Part B AGREE rows. Categories: LIMITING CHANGE 3, ADDED 1, TYPE 2, OK 41. Fixes to new v2 criteria change their draft text in place; a kept v1 criterion whose text must change is replaced under a new ID (B7, B20); code-list fixes keep the ID and text. Every excerpt below is checked word for word against data/raw by scripts/verify/policies_v2_triage.py.

| Row | Criterion | Category | Action | Reason |
|---|---|---|---|---|
| A4 | POL-CAR-002.c5 | LIMITING CHANGE | fix | Its only code, 93241, is continuous recording; cov-019 covers continuous recording beyond 48 hours only for treatment response, and the infrequent-symptom path is for event monitors, which no in-scope code bills. D-V2-1 named this criterion 'event monitoring up to 15 days', so this narrows the decided wording: please confirm. |
| A5 | POL-CAR-002.c6 | OK | keep | Every item of the 30-day list (cov-022 to cov-032) is present; '30-day' matches; no ejection fraction condition. |
| A7 | POL-DX-001.c5 | OK | keep | 'high likelihood of moderate to severe' and 'documented in the note' are cov-107 and cov-108's. |
| A8 | POL-DX-002.c4 | ADDED | fix | 'which the notes must document' is not in cov-037; it is Q9's documentation rule, recorded in D-POL-4. Cite the decision on the source line; the text stays. |
| A9 | POL-DX-003.c4 | OK | keep | Prick and intradermal lists match cov-008 and cov-009; foods only for prick; correlation with history and examination is cov-007's. |
| A12 | POL-FOOT-001.c5 | LIMITING CHANGE | fix | The manual says 'covered only when'; the text dropped 'only'. c6 and the group rule carry it today, but the word belongs in the criterion. |
| A13 | POL-FOOT-001.c6 | OK | keep | 'not covered' and the examples match 290.B.2; 'except in the situations this policy covers' was approved under Q4. |
| A14 | POL-PAIN-001.c6 | OK | keep | Severity and a baseline scale before treatment are cov-013's; the scale form is D-ESI-2's. |
| A16 | POL-PAIN-001.c8 | OK | keep | 50%, 3 months, 14 days and the different approach, level or medication match cov-019 and cov-039. |
| A18 | POL-PAIN-002.c5 | OK | keep | 'a minimum of 2 weeks' and the documented exception match cov-024; the intent to proceed to RFA is cov-023's. |
| A21 | POL-SURG-001.c4 | OK | keep | Matches cov-008, including its examples. |
| A23 | POL-SURG-002.c5 | OK | keep | 2 cm, 7 and 15 years and the rectosigmoid exclusion match; the intervals are left out by D-RULE-1. |
| A25 | POL-SURG-002.c7 | OK | keep | All six therapeutic items of cov-027 to cov-031 and cov-034 are present. |
| A28 | POL-SURG-004.c7 | OK | keep | 12 degrees or 30 percent and the potential correction match cov-028; the taping is how the correction is shown, not a further limit. |
| A29 | POL-SURG-004.c8 | OK | keep | 'considered cosmetic' without functional signs or symptoms is cov-004's; scoped to group 1 by cov-016. |
| A31 | POL-SURG-003.c4 | OK | keep | 3 months, 'AND' and 'one, or more' match section A. Stab phlebectomy rests on cov-028 and section A's open 'For example' list of surgical treatments. Not yet reviewed by pass 1. |
| B1 | POL-BH-001.c1 | OK | keep | Requirement on every testing code fits. |
| B2 | POL-BH-001.c2 | OK | keep | Not-covered situations: exclusion. |
| B3 | POL-BH-001.c3 | OK | keep | Not-necessary situation: exclusion. |
| B5 | POL-CAR-001.c3 | OK | keep | Stress echo requirement on 93350. |
| B6 | POL-DX-001.c1 | OK | keep | Requirement on every sleep test code fits. |
| B7 | POL-DX-001.c3 | TYPE | fix | The LCD's repeat rule is for 'polysomnography or sleep testing', home tests included, but c3 says 'facility' and applies to 95810 and 95811 only, so a repeat home test has no limit; c3 also dropped cov-059's 'due to equipment failure'. The text must change, so a new ID: c6 replaces c3 (on every code), with cov-121's in-laboratory follow-up after a failed home test. |
| B8 | POL-DX-002.c1 | OK | keep | Requirement on every code, EMG included. |
| B9 | POL-DX-002.c2 | OK | keep | A situation where testing is not appropriate: exclusion. |
| B10 | POL-DX-002.c3 | OK | keep | Not-covered situations: exclusion. |
| B11 | POL-DX-003.c2 | OK | keep | Patch test requirement on 95044. |
| B12 | POL-DX-003.c3 | OK | keep | Requirement on every allergy test code. |
| B13 | POL-FOOT-001.c1 | OK | keep | Conditional, in the indication group (C1). |
| B14 | POL-FOOT-001.c2 | OK | keep | Conditional, in the indication group (C1). |
| B15 | POL-IMG-001.c1 | OK | keep | Requirement on every head and neck code. |
| B16 | POL-IMG-001.c2 | TYPE | fix | The headache rule is for head imaging; shown on the cervical spine MRI (72141) it invites a wrong NOT_MET when the notes mention a headache, as B18 found for c4. Code list: the head and brain codes. |
| B19 | POL-IMG-002.c1 | OK | keep | Requirement on both ultrasound codes. |
| B20 | POL-IMG-002.c2 | LIMITING CHANGE | fix | Type and codes fit, but the kept v1 text applies 'unless the notes show that the clinical picture is unclear' to every condition; the LCD gives that exception only to neuromas, superficial ganglia, bursae and abscesses (cov-019), and the text leaves out ganglia and bursae. The text must change, so a new ID: c5 replaces c2. |
| B21 | POL-IMG-002.c3 | OK | keep | Conditional on plantar fasciitis. |
| B22 | POL-IMG-002.c4 | OK | keep | Conditional on both limbs being scanned. |
| B23 | POL-PAIN-001.c1 | OK | keep | Requirement on every ESI code (D-ESI-1). |
| B24 | POL-PAIN-001.c3 | OK | keep | Requirement on every ESI code (D-ESI-1). |
| B25 | POL-PAIN-002.c1 | OK | keep | Requirement on every facet code, RFA included (cov-015's 'ALL of the following'). |
| B26 | POL-PAIN-002.c2 | OK | keep | Requirement on every facet code. |
| B28 | POL-REHAB-001.c1 | OK | keep | Skilled-service requirement fits evaluations and treatment. |
| B30 | POL-SURG-001.c1 | OK | keep | Conditional, in the indication group (C2). |
| B31 | POL-SURG-001.c2 | OK | keep | Not-necessary situation: exclusion, outside the group. |
| B32 | POL-SURG-001.c3 | OK | keep | Conditional, in the indication group (C2). |
| B33 | POL-SURG-002.c3 | OK | keep | Conditional, in the indication group (C3); the 24 months are the LCD's own indication, not an interval rule. |
| B35 | POL-SURG-003.c2 | OK | keep | Exclusion 'by any technique': every code. |
| B36 | POL-SURG-003.c3 | OK | keep | Exclusion 'by any technique': every code. |
| B38 | POL-WOUND-001.c2 | OK | keep | Plan requirement on every wound code; its palliative goal agrees with the fixed c4. |

## Drafts and excerpts

### A4. POL-CAR-002.c5: LIMITING CHANGE, fix

- Reason: Its only code, 93241, is continuous recording; cov-019 covers continuous recording beyond 48 hours only for treatment response, and the infrequent-symptom path is for event monitors, which no in-scope code bills. D-V2-1 named this criterion 'event monitoring up to 15 days', so this narrows the decided wording: please confirm.
- Old text: Recording for more than 48 hours, up to 15 days, is covered to look for symptom-free episodes when checking the response to treatment in a patient treated for a listed condition, or, with an event monitor, as an alternative to 48-hour monitoring when symptoms suggesting an arrhythmia (palpitations, dizziness, near fainting or fainting) occur less often than every 48 hours.
- **New text:** Continuous recording for more than 48 hours, up to 15 days, is covered to look for symptom-free episodes when checking the response to treatment in a patient treated for a listed condition.
- Excerpt words (word for word):
  - **L34636-cov-019**: "by continuous rhythm recording and storage, may be considered medically necessary in patients treated for reasons listed in the diagnosis list to monitor for asymptomatic episodes in order to evaluate treatment response"
  - **L34636-cov-019**: "The use of external electrocardiographic event monitors for greater than 48 hours"

### A5. POL-CAR-002.c6: OK, keep

- Reason: Every item of the 30-day list (cov-022 to cov-032) is present; '30-day' matches; no ejection fraction condition.
- Excerpt words (word for word):
  - **L34636-cov-030**: "Evaluation of myocardial infarction (MI) survivors."
  - **L34636-cov-029**: "To initiate, revise or discontinue arrhythmia drug therapy."

### A7. POL-DX-001.c5: OK, keep

- Reason: 'high likelihood of moderate to severe' and 'documented in the note' are cov-107 and cov-108's.
- Excerpt words (word for word):
  - **L35050-cov-107**: "high likelihood of having moderate to severe sleep apnea"
  - **L35050-cov-108**: "evidenced by symptoms and physical examination documented in the note"

### A8. POL-DX-002.c4: ADDED, fix

- Reason: 'which the notes must document' is not in cov-037; it is Q9's documentation rule, recorded in D-POL-4. Cite the decision on the source line; the text stays.
- Old source line: LCD L34594 v42 cov-037.
- **New source line:** LCD L34594 v42 cov-037; decision D-POL-4.
- Excerpt words (word for word):
  - **L34594-cov-037**: "The only exception to this is a situation where a provider may consider it appropriate to perform an NCS without doing an EMG for the diagnosis of carpal tunnel syndrome with a high pre-test probability."

### A9. POL-DX-003.c4: OK, keep

- Reason: Prick and intradermal lists match cov-008 and cov-009; foods only for prick; correlation with history and examination is cov-007's.
- Excerpt words (word for word):
  - **L33261-cov-008**: "inhalants, foods, Hymenoptera (stinging insects), chemicals, and specific drugs"
  - **L33261-cov-009**: "inhalants, Hymenoptera venoms (e.g., bee venom), drugs (e.g., penicillin, insulin, heparin, muscle relaxants) and/or chemicals"

### A12. POL-FOOT-001.c5: LIMITING CHANGE, fix

- Reason: The manual says 'covered only when'; the text dropped 'only'. c6 and the group rule carry it today, but the word belongs in the criterion.
- Old text: Without a systemic condition, treatment of mycotic (fungal) toenails is covered when the physician attending the mycotic condition documents clinical evidence of mycosis of the toenail and, for a patient who can walk, marked limitation of walking, pain, or secondary infection caused by the thickened, dystrophic nail plate; for a patient who cannot walk, pain or secondary infection caused by it.
- **New text:** Without a systemic condition, treatment of mycotic (fungal) toenails is covered only when the physician attending the mycotic condition documents clinical evidence of mycosis of the toenail and, for a patient who can walk, marked limitation of walking, pain, or secondary infection caused by the thickened, dystrophic nail plate; for a patient who cannot walk, pain or secondary infection caused by it.
- Excerpt words (word for word):
  - **§290.C.4**: "covered only when the physician attending the"

### A13. POL-FOOT-001.c6: OK, keep

- Reason: 'not covered' and the examples match 290.B.2; 'except in the situations this policy covers' was approved under Q4.
- Excerpt words (word for word):
  - **§290.B.2**: "Except as provided above, routine foot care is excluded from coverage."

### A14. POL-PAIN-001.c6: OK, keep

- Reason: Severity and a baseline scale before treatment are cov-013's; the scale form is D-ESI-2's.
- Excerpt words (word for word):
  - **L33906-cov-013**: "An objective pain scale or functional assessment must be performed at baseline (prior to interventions)."

### A16. POL-PAIN-001.c8: OK, keep

- Reason: 50%, 3 months, 14 days and the different approach, level or medication match cov-019 and cov-039.
- Excerpt words (word for word):
  - **L33906-cov-019**: "a repeat ESI after 14 days can be performed using a different approach, level and/or medication"

### A18. POL-PAIN-002.c5: OK, keep

- Reason: 'a minimum of 2 weeks' and the documented exception match cov-024; the intent to proceed to RFA is cov-023's.
- Excerpt words (word for word):
  - **L33930-cov-024**: "The second diagnostic procedure may only be performed a minimum of 2 weeks after the initial diagnostic procedure."

### A21. POL-SURG-001.c4: OK, keep

- Reason: Matches cov-008, including its examples.
- Excerpt words (word for word):
  - **L33558-cov-008**: "High probability of accelerating cataract development"

### A23. POL-SURG-002.c5: OK, keep

- Reason: 2 cm, 7 and 15 years and the rectosigmoid exclusion match; the intervals are left out by D-RULE-1.
- Excerpt words (word for word):
  - **L34005-cov-020**: "Pancolitis of greater than seven years duration; or,"
  - **L34005-cov-021**: "Left-sided colitis of over 15 years duration"

### A25. POL-SURG-002.c7: OK, keep

- Reason: All six therapeutic items of cov-027 to cov-031 and cov-034 are present.
- Excerpt words (word for word):
  - **L34005-cov-029**: "Excision of colonic polyps;"

### A28. POL-SURG-004.c7: OK, keep

- Reason: 12 degrees or 30 percent and the potential correction match cov-028; the taping is how the correction is shown, not a further limit.
- Excerpt words (word for word):
  - **L33944-cov-028**: "A minimum 12 degree or 30 percent loss of upper field of vision"

### A29. POL-SURG-004.c8: OK, keep

- Reason: 'considered cosmetic' without functional signs or symptoms is cov-004's; scoped to group 1 by cov-016.
- Excerpt words (word for word):
  - **L33944-cov-004**: "in the absence of any signs or symptoms of functional abnormalities, the procedure is considered cosmetic."

### A31. POL-SURG-003.c4: OK, keep

- Reason: 3 months, 'AND' and 'one, or more' match section A. Stab phlebectomy rests on cov-028 and section A's open 'For example' list of surgical treatments. Not yet reviewed by pass 1.
- Excerpt words (word for word):
  - **L34209-cov-008**: "A 3-month trial of conservative therapy"
  - **L34209-cov-009**: "The patient is symptomatic and has one, or more, of the following:"
  - **L34209-cov-007**: "A. Indications for surgical treatment: For example venous ligation, vein stripping and/or sclerotherapy:"

### B1. POL-BH-001.c1: OK, keep

- Reason: Requirement on every testing code fits.
- Excerpt words (word for word):
  - **v1:POL-BH-001.c1**: "known or suspected neurocognitive involvement or effects"

### B2. POL-BH-001.c2: OK, keep

- Reason: Not-covered situations: exclusion.
- Excerpt words (word for word):
  - **v1:POL-BH-001.c2**: "performed when abnormalities of brain or emotional function are not suspected"

### B3. POL-BH-001.c3: OK, keep

- Reason: Not-necessary situation: exclusion.
- Excerpt words (word for word):
  - **v1:POL-BH-001.c3**: "is not medically necessary."

### B5. POL-CAR-001.c3: OK, keep

- Reason: Stress echo requirement on 93350.
- Excerpt words (word for word):
  - **v1:POL-CAR-001.c3**: "who have signs or symptoms of suspected CAD"

### B6. POL-DX-001.c1: OK, keep

- Reason: Requirement on every sleep test code fits.
- Excerpt words (word for word):
  - **v1:POL-DX-001.c1**: "The patient is to be evaluated by a physician prior to ordering of test."

### B7. POL-DX-001.c3: TYPE, fix

- Reason: The LCD's repeat rule is for 'polysomnography or sleep testing', home tests included, but c3 says 'facility' and applies to 95810 and 95811 only, so a repeat home test has no limit; c3 also dropped cov-059's 'due to equipment failure'. The text must change, so a new ID: c6 replaces c3 (on every code), with cov-121's in-laboratory follow-up after a failed home test.
- **New criterion POL-DX-001.c6** (conditional; applies to every code of the policy; replaces POL-DX-001.c3): A repeat sleep study, in a facility or at home, is covered when the record justifies it: the first study was technically inadequate because of equipment failure, the patient could not sleep or slept too little for a diagnosis, the results were inconclusive or ambiguous, or starting therapy or confirming that the prescribed therapy works requires it. After a negative or technically inadequate home test in a patient with a high likelihood of moderate to severe obstructive sleep apnea, the repeat should be an in-laboratory study.
  Source line: LCD L35050 v55 cov-058 to cov-062, cov-121.
- Excerpt words (word for word):
  - **L35050-cov-058**: "Repeat polysomnography or sleep testing for diagnosing sleep apnea requires documentation justifying the medical necessity for the repeated test."
  - **L35050-cov-059**: "if the first study is technically inadequate due to equipment failure;"
  - **L35050-cov-121**: "Negative or technically inadequate OCST in patients with a high pretest probability of moderate to severe OSA should have prompt in-laboratory"

### B8. POL-DX-002.c1: OK, keep

- Reason: Requirement on every code, EMG included.
- Excerpt words (word for word):
  - **v1:POL-DX-002.c1**: "must always describe and document clearly and comprehensibly the need for the planned test"

### B9. POL-DX-002.c2: OK, keep

- Reason: A situation where testing is not appropriate: exclusion.
- Excerpt words (word for word):
  - **v1:POL-DX-002.c2**: "irrelevant as a first order diagnostic test for limb pain resulting from immediate antecedent trauma or acute bone injury"

### B10. POL-DX-002.c3: OK, keep

- Reason: Not-covered situations: exclusion.
- Excerpt words (word for word):
  - **v1:POL-DX-002.c3**: "is not considered medically necessary and is not covered."

### B11. POL-DX-003.c2: OK, keep

- Reason: Patch test requirement on 95044.
- Excerpt words (word for word):
  - **v1:POL-DX-003.c2**: "Allergy patch testing will be considered medically reasonable and necessary when used to diagnose allergic contact dermatitis"

### B12. POL-DX-003.c3: OK, keep

- Reason: Requirement on every allergy test code.
- Excerpt words (word for word):
  - **v1:POL-DX-003.c3**: "The number of allergy tests performed should be judicious"

### B13. POL-FOOT-001.c1: OK, keep

- Reason: Conditional, in the indication group (C1).
- Excerpt words (word for word):
  - **v1:POL-FOOT-001.c1**: "absence of sensation at two or more sites out of five tested on either foot"

### B14. POL-FOOT-001.c2: OK, keep

- Reason: Conditional, in the indication group (C1).
- Excerpt words (word for word):
  - **v1:POL-FOOT-001.c2**: "For patients requiring anticoagulation therapy"

### B15. POL-IMG-001.c1: OK, keep

- Reason: Requirement on every head and neck code.
- Excerpt words (word for word):
  - **v1:POL-IMG-001.c1**: "preliminary (or provisional) diagnosis"

### B16. POL-IMG-001.c2: TYPE, fix

- Reason: The headache rule is for head imaging; shown on the cervical spine MRI (72141) it invites a wrong NOT_MET when the notes mention a headache, as B18 found for c4. Code list: the head and brain codes.
- Old Applies to: every code of the policy
- **New Applies to:** 70450, 70551, 70553 (text and ID unchanged)
- Excerpt words (word for word):
  - **v1:POL-IMG-001.c2**: "CT imaging has not been useful in general for the evaluation of headache or dizziness"

### B19. POL-IMG-002.c1: OK, keep

- Reason: Requirement on both ultrasound codes.
- Excerpt words (word for word):
  - **v1:POL-IMG-002.c1**: "Extremity ultrasound is indicated for the following conditions"

### B20. POL-IMG-002.c2: LIMITING CHANGE, fix

- Reason: Type and codes fit, but the kept v1 text applies 'unless the notes show that the clinical picture is unclear' to every condition; the LCD gives that exception only to neuromas, superficial ganglia, bursae and abscesses (cov-019), and the text leaves out ganglia and bursae. The text must change, so a new ID: c5 replaces c2.
- **New criterion POL-IMG-002.c5** (exclusion; applies to every code of the policy; replaces POL-IMG-002.c2): Extremity ultrasound is not medically necessary for the routine diagnosis or management of bunions, cellulitis, nail-fold infections (paronychia), plantar warts, superficial abscesses, or neuromas whose clinical impression is obvious. For neuromas, superficial ganglia, bursae and abscesses it is not medically necessary unless the notes document a clinical presentation that obscures these simple diagnoses.
  Source line: LCD L33619 v25 cov-011 to cov-017, cov-019.
- Excerpt words (word for word):
  - **L33619-cov-011**: "Extremity ultrasound is considered not medically necessary for the routine diagnosis or management of the following conditions:"
  - **L33619-cov-014**: "neuromas (where the clinical impression is obvious and ultrasound is not likely to add further information)"
  - **L33619-cov-019**: "neuromas, superficial ganglia, bursae and abscesses unless there is documented evidence of some clinical presentation"

### B21. POL-IMG-002.c3: OK, keep

- Reason: Conditional on plantar fasciitis.
- Excerpt words (word for word):
  - **v1:POL-IMG-002.c3**: "A single diagnostic extremity ultrasound may be medically necessary for plantar fasciitis"

### B22. POL-IMG-002.c4: OK, keep

- Reason: Conditional on both limbs being scanned.
- Excerpt words (word for word):
  - **v1:POL-IMG-002.c4**: "Bilateral studies are allowed only if there is pathology of both extremities"

### B23. POL-PAIN-001.c1: OK, keep

- Reason: Requirement on every ESI code (D-ESI-1).
- Excerpt words (word for word):
  - **v1:POL-PAIN-001.c1**: "concordant radiological image-based diagnostic testing that supports one of the following"

### B24. POL-PAIN-001.c3: OK, keep

- Reason: Requirement on every ESI code (D-ESI-1).
- Excerpt words (word for word):
  - **v1:POL-PAIN-001.c3**: "Pain duration of at least four (4) weeks"

### B25. POL-PAIN-002.c1: OK, keep

- Reason: Requirement on every facet code, RFA included (cov-015's 'ALL of the following').
- Excerpt words (word for word):
  - **v1:POL-PAIN-002.c1**: "Moderate to severe chronic neck or low back pain, predominantly axial"

### B26. POL-PAIN-002.c2: OK, keep

- Reason: Requirement on every facet code.
- Excerpt words (word for word):
  - **v1:POL-PAIN-002.c2**: "Pain that has been present for a minimum of 3 months"

### B28. POL-REHAB-001.c1: OK, keep

- Reason: Skilled-service requirement fits evaluations and treatment.
- Excerpt words (word for word):
  - **v1:POL-REHAB-001.c1**: "can be safely and effectively performed only by a licensed physical therapist or under his/her supervision"

### B30. POL-SURG-001.c1: OK, keep

- Reason: Conditional, in the indication group (C2).
- Excerpt words (word for word):
  - **v1:POL-SURG-001.c1**: "when one (or more) of the following conditions or circumstances exists"

### B31. POL-SURG-001.c2: OK, keep

- Reason: Not-necessary situation: exclusion, outside the group.
- Excerpt words (word for word):
  - **v1:POL-SURG-001.c2**: "purely on the basis of lens opacity in the absence of symptoms"

### B32. POL-SURG-001.c3: OK, keep

- Reason: Conditional, in the indication group (C2).
- Excerpt words (word for word):
  - **v1:POL-SURG-001.c3**: "Cataract interfering with the performance of vitreoretinal surgery"

### B33. POL-SURG-002.c3: OK, keep

- Reason: Conditional, in the indication group (C3); the 24 months are the LCD's own indication, not an interval rule.
- Excerpt words (word for word):
  - **v1:POL-SURG-002.c3**: "is eligible for continued screening at 24-month intervals"

### B35. POL-SURG-003.c2: OK, keep

- Reason: Exclusion 'by any technique': every code.
- Excerpt words (word for word):
  - **v1:POL-SURG-003.c2**: "by any technique will be considered cosmetic and therefore not covered"

### B36. POL-SURG-003.c3: OK, keep

- Reason: Exclusion 'by any technique': every code.
- Excerpt words (word for word):
  - **v1:POL-SURG-003.c3**: "by any technique is considered cosmetic"

### B38. POL-WOUND-001.c2: OK, keep

- Reason: Plan requirement on every wound code; its palliative goal agrees with the fixed c4.
- Excerpt words (word for word):
  - **v1:POL-WOUND-001.c2**: "the goal of wound care provided in outpatient settings may be only to prevent progression of the wound"

