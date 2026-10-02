# Model disagreements (Task V1c): review sheet

Read the criterion and notes and decide the status yourself BEFORE looking at the gold and model columns. Then write LABEL RIGHT, MODEL RIGHT, BOTH WRONG or UNSURE.

Estimated review time: 36 minutes (12 rows, 3 minutes per row).

Source: claimsense-decision:v1 on the 300 test records (`data/generated/eval/finetuned-v1.jsonl`): 282 valid answers; 1,036 criterion statuses and 386 line decisions compared, as the evaluator does (statuses on valid answers only; an invalid answer is PEND). 319 disagreements (203 statuses, 116 line decisions), all in `C_disagreements_full.csv`.

## Disagreements per error type (gold -> model)

| Kind | Gold -> model | All | In a known-problem group | Not explained | From invalid answers |
|---|---|---|---|---|---|
| criterion status | MET -> NOT_DOCUMENTED | 47 | 4 | 43 | - |
| criterion status | MET -> NOT_APPLICABLE | 31 | 0 | 31 | - |
| criterion status | NOT_DOCUMENTED -> NOT_APPLICABLE | 29 | 17 | 12 | - |
| criterion status | NOT_APPLICABLE -> NOT_DOCUMENTED | 19 | 11 | 8 | - |
| criterion status | NOT_MET -> NOT_DOCUMENTED | 19 | 11 | 8 | - |
| criterion status | NOT_DOCUMENTED -> MET | 14 | 3 | 11 | - |
| criterion status | NOT_MET -> MET | 14 | 3 | 11 | - |
| criterion status | MET -> NOT_MET | 13 | 5 | 8 | - |
| criterion status | NOT_MET -> NOT_APPLICABLE | 8 | 6 | 2 | - |
| criterion status | NOT_DOCUMENTED -> NOT_MET | 3 | 3 | 0 | - |
| criterion status | NOT_APPLICABLE -> NOT_MET | 3 | 2 | 1 | - |
| criterion status | NOT_APPLICABLE -> MET | 3 | 1 | 2 | - |
| line decision | APPROVE -> PEND | 51 | 6 | 45 | 12 |
| line decision | DENY -> PEND | 44 | 22 | 22 | 15 |
| line decision | PEND -> APPROVE | 14 | 0 | 14 | 0 |
| line decision | DENY -> APPROVE | 7 | 1 | 6 | 0 |

## Known-problem groups (already explained)

| Group | Why | Test records | Lines | Status disagreements | Decision disagreements |
|---|---|---|---|---|---|
| diagnosis mismatch | V1a check 1: diagnoses do not satisfy the billing article (R15 in v2, D-DX-1) | 53 | 59 | 51 | 20 |
| two_policy contradictory notes | D-ESI-5: radicular statement and 'no pain down the limbs' in one record | 1 | 2 | 3 | 1 |
| ESI line | 62321, 62323, 64483: ESI labels conflict with LCD L33906 (D-ESI-1 to D-ESI-7) | 22 | 22 | 9 | 7 |
| POL-REHAB-001 evaluation line | 97161, 97162: plan-of-care criterion on evaluations (V1b, POL-REHAB-001.F1) | 5 | 5 | 9 | 2 |
| Any group | A line can be in more than one group | 76 | 84 | 66 | 29 |
| No group | Not explained | - | - | 137 | 87 |

Of the 224 unexplained disagreements, 6 sit in a record with a known problem on another line, so they are left out of the sample too.

## Status definitions (prompt decision_v2, word for word)

- NOT_APPLICABLE: the criterion's policy does not cover the line's procedure code, or the criterion is about a situation this claim is not in. Evidence: "Does not apply to this service."
- MET: the notes show the criterion is satisfied. Evidence: copy the sentence from the clinical notes that shows it.
- NOT_MET: the notes show the criterion is not satisfied. Evidence: copy the sentence from the clinical notes that shows it.
- NOT_DOCUMENTED: the criterion applies, but the notes say nothing about it. Evidence: "Not documented in the clinical notes."

## Sample: 8 disagreements (seed 42, records in no known-problem group)

Drawn: 3 from MET -> NOT_DOCUMENTED, 3 from NOT_MET -> NOT_DOCUMENTED, 2 from NOT_APPLICABLE / NOT_DOCUMENTED boundary; the rows are shuffled, so their order says nothing about the error type.

| # | Record ID | Criterion ID | Criterion text | Full clinical notes | My status | Who is right? | Notes | Gold status | Model status |
|---|---|---|---|---|---|---|---|---|---|
| 1 | DEC-TE-00043, line 1 (76882) | POL-IMG-002.c3 | For plantar fasciitis, one ultrasound is covered only when the diagnosis is still uncertain after a failed course of conservative treatment. It is not covered for the initial diagnosis or for repeat studies. | CC: heel pain. VS WNL. US to eval 1 cm soft-tissue mass near heel. Plan -> limited ultrasound of an arm or leg joint or soft tissue area. | NOT_APPLICABLE | MODEL RIGHT | ultrasound is for a soft-tissue mass, not plantar fasciitis | NOT_DOCUMENTED | NOT_APPLICABLE |
| 2 | DEC-TE-00015, line 1 (76881) | POL-IMG-002.c1 | Extremity ultrasound is covered to evaluate cysts, abscesses, tumors or joint effusions; tendons, joints, plantar fascia, ligaments, soft-tissue masses, ganglion cysts, neuromas or metatarsal stress fractures; or foreign bodies. | CC: lump/swelling. US for suspected ankle effusion vs cyst. NKDA. Dx unclear on exam; firm lump, cause uncertain. Plan -> complete ultrasound of one arm or leg joint. Pt agrees w/ plan. | MET | LABEL RIGHT | effusion vs cyst is a listed indication | MET | NOT_DOCUMENTED |
| 3 | DEC-TE-00196, line 1 (95044) | POL-DX-003.c3 | The tests chosen must match the patient's history and physical findings, and the number of tests must be justified. Guideline limits for an initial evaluation are about 70 prick and 40 intradermal tests for airborne allergens, or up to 80 patch tests. | CC: recurrent dermatitis. NKDA. Pt agrees w/ plan. Rash at sites of contact w/ rubber gloves; ?ACD. Std panel run, not tied to hx. Plan -> skin patch allergy tests, per patch. | NOT_MET | LABEL RIGHT | "Std panel run, not tied to hx" | NOT_MET | NOT_DOCUMENTED |
| 4 | DEC-TE-00044, line 1 (76882) | POL-IMG-002.c3 | For plantar fasciitis, one ultrasound is covered only when the diagnosis is still uncertain after a failed course of conservative treatment. It is not covered for the initial diagnosis or for repeat studies. | CC: heel pain. PMH reviewed, no change. Plan -> limited ultrasound of an arm or leg joint or soft tissue area. | NOT_DOCUMENTED | UNSURE | depends on the line's diagnosis, which the sheet does not show | NOT_DOCUMENTED | NOT_APPLICABLE |
| 5 | DEC-TE-00275, line 1 (95044) | POL-DX-003.c3 | The tests chosen must match the patient's history and physical findings, and the number of tests must be justified. Guideline limits for an initial evaluation are about 70 prick and 40 intradermal tests for airborne allergens, or up to 80 patch tests. | CC: recurrent dermatitis. NKDA. Rash at sites of contact w/ a new skin cream; ?ACD. 43 allergens selected per exposure hx. VS WNL. Plan -> skin patch allergy tests, per patch. | MET | LABEL RIGHT | "43 allergens selected per exposure hx", within the 80 patch-test limit | MET | NOT_DOCUMENTED |
| 6 | DEC-TE-00177, line 2 (93350) | POL-CAR-001.c3 | Stress echocardiography is covered to evaluate suspected coronary artery disease in patients with signs or symptoms, for example after a treadmill stress test that did not give a diagnosis. | CC: chest discomfort. exertional chest tightness; exam: an abnormal resting ECG; ?cardiomyopathy/valve dz. No CP/SOB; stress echo as routine screen. Visit: eval + counseling done. Plan -> heart ultrasound during an exercise or drug stress test. PMH reviewed, no change. | UNSURE | UNSURE | notes contradict: "exertional chest tightness" vs "No CP/SOB; stress echo as routine screen" | NOT_MET | NOT_DOCUMENTED |
| 7 | DEC-TE-00107, line 1 (64490) | POL-PAIN-002.c2 | The pain must have lasted at least 3 months, with documented failure of non-invasive conservative care. | CC: chronic axial neck pain. NKDA. Axial neck pain 9/10, worse w/ extension/rotation; disability 38%. Onset 3wk ago; no PT tried. No radicular sx; imaging neg for fx/tumor/infection. PMH reviewed, no change. Plan -> facet joint nerve block injection, neck or upper back, first level. | NOT_MET | LABEL RIGHT | "Onset 3wk ago; no PT tried" | NOT_MET | NOT_DOCUMENTED |
| 8 | DEC-TE-00060, line 1 (76882) | POL-IMG-002.c1 | Extremity ultrasound is covered to evaluate cysts, abscesses, tumors or joint effusions; tendons, joints, plantar fascia, ligaments, soft-tissue masses, ganglion cysts, neuromas or metatarsal stress fractures; or foreign bodies. | CC: heel pain. US for suspected heel effusion vs cyst. Heel pain persists after 13wk stretching, orthotics, NSAIDs; dx still uncertain. Plan -> limited ultrasound of an arm or leg joint or soft tissue area. PMH reviewed, no change. | MET | LABEL RIGHT | effusion vs cyst is a listed indication | MET | NOT_DOCUMENTED |

## Extra sample: MET -> NOT_APPLICABLE

Drawn: 4 from MET -> NOT_APPLICABLE (seed 43, records in no known-problem group); the rows are shuffled.

| # | Record ID | Criterion ID | Criterion text | Full clinical notes | My status | Who is right? | Notes | Gold status | Model status |
|---|---|---|---|---|---|---|---|---|---|
| 9 | DEC-TE-00007, line 2 (36475) | POL-SURG-003.c3 | Treating spider veins (telangiectasias) by any technique is cosmetic and not covered. | Vein clinic eval. Meds reconciled. R GSV varicosities w/ aching, swelling, heaviness; duplex: reflux. Sx persist after 3 mo compression, elevation, exercise. Treating GSV trunk, not spider veins. Visit: eval + counseling done. Plan -> closing a leg vein from the inside with radiofrequency heat, first vein. | NOT_APPLICABLE | MODEL RIGHT | exclusion criterion: the written NOT_APPLICABLE definition fits; gold MET follows a different convention | MET | NOT_APPLICABLE |
| 10 | DEC-TE-00094, line 2 (95910) | POL-DX-002.c2 | These tests are not a first-line test for limb pain caused by a recent injury or an acute bone injury. | CC: hand numbness. No recent trauma to limb. Pt agrees w/ plan. Visit: eval + counseling done. Plan -> nerve conduction testing, 7 to 8 nerves. | NOT_APPLICABLE | MODEL RIGHT | same as row 9 | MET | NOT_APPLICABLE |
| 11 | DEC-TE-00138, line 2 (15823) | POL-SURG-004.c4 | Without documented functional impairment, eyelid surgery is considered cosmetic and is not covered. | Pre-op cataract eval. PMH reviewed, no change. right eye glare/blur limits driving + reading; BCVA 20/70 w/ new Rx; other pathology excluded. Symptomatic cataract, not incidental finding. CC: droopy upper lids. Pt reports superior VF obstruction, trouble reading/driving. NKDA. VF full; 5 deg superior loss only. Goal: restore superior VF (functional). Plan -> cataract removal with lens implant, routine case; upper eyelid surgery removing excess skin that droops over the eye. | UNSURE | UNSURE | exclusion criterion: complaints documented, but visual-field loss only 5 degrees (<12) | MET | NOT_APPLICABLE |
| 12 | DEC-TE-00042, line 2 (36475) | POL-SURG-003.c3 | Treating spider veins (telangiectasias) by any technique is cosmetic and not covered. | Vein clinic eval. L GSV varicosities w/ aching, swelling, heaviness; duplex: reflux. Sx persist after 3 mo compression, elevation, exercise. PMH reviewed, no change. Meds reconciled. Treating GSV trunk, not spider veins. Plan -> removing leg varicose veins through small punctures, 10 to 20 incisions; closing a leg vein from the inside with radiofrequency heat, first vein. | NOT_APPLICABLE | MODEL RIGHT | same as row 9 | MET | NOT_APPLICABLE |
