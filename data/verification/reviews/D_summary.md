# V1 review verdicts: summary (Task V1d)

Verdicts by Manideep3183, entered 2026-10-02. The filled sheets are in `data/verification/reviews/`; this summary is read back from them by `scripts/verify/review_verdicts.py`. How each review was done:

- A_labels_review.md: verdicts decided with Claude's help during V1a.
- B_policy_sources_review.md: verdicts suggested by Claude and accepted by the reviewer.
- C_disagreements_review.md: statuses are Claude's reading, accepted by the reviewer (not a blind review).

## Verdict counts

| Sheet | Table | Rows | Verdicts |
|---|---|---|---|
| A_labels_review.md | Label verification (Task V1a) | 5 | REAL ERROR 5 |
| B_policy_sources_review.md | Sitting 1: source check (Part 1) | 14 | MATCHES 8, DIFFERENT MEANING 4, NOT IN SOURCE 1, UNSURE 1 |
| B_policy_sources_review.md | Sitting 2: completeness findings | 12 | ADD IN V2 8, NOT NEEDED 4 |
| C_disagreements_review.md | Sample: 8 disagreements (seed 42, records in no known-problem group) | 8 | LABEL RIGHT 5, UNSURE 2, MODEL RIGHT 1 |
| C_disagreements_review.md | Extra sample: MET -> NOT_APPLICABLE | 4 | MODEL RIGHT 3, UNSURE 1 |

C_disagreements_review.md by error type (gold -> model):

| Error type | Rows | LABEL RIGHT | MODEL RIGHT | BOTH WRONG | UNSURE |
|---|---|---|---|---|---|
| NOT_DOCUMENTED -> NOT_APPLICABLE | 2 | 0 | 1 | 0 | 1 |
| MET -> NOT_DOCUMENTED | 3 | 3 | 0 | 0 | 0 |
| NOT_MET -> NOT_DOCUMENTED | 3 | 2 | 0 | 0 | 1 |
| MET -> NOT_APPLICABLE | 4 | 0 | 3 | 0 | 1 |

## Rows that are not MATCHES or LABEL RIGHT

A_labels_review.md (verdicts other than FALSE ALARM):

- Row 1, DEC-TR-01140 (line 1), POL-PAIN-001.c2: REAL ERROR. c2 applies to repeats (LCD L33906, D-ESI-1); no baseline score; no prior relief stated, so c5 not documented
- Row 2, DEC-TR-00431 (line 1), POL-PAIN-001.c2: REAL ERROR. c2 applies to repeats (D-ESI-1); no baseline score; line should be PEND
- Row 3, DEC-VA-00208 (line 2), POL-PAIN-001.c2: REAL ERROR. same as row 2
- Row 4, DEC-TE-00243 (line 1), POL-PAIN-001.c2: REAL ERROR. same as row 2
- Row 5, DEC-TE-00110 (line 1), POL-PAIN-001.c2: REAL ERROR. c2 applies to repeats (D-ESI-1); no baseline score and no prior relief stated

B_policy_sources_review.md, sitting 1 (verdicts other than MATCHES):

- Row 2, POL-CAR-002.c1: DIFFERENT MEANING. LCD list is for 48-hour recording only; criterion has no duration scope
- Row 3, POL-CAR-002.c3: DIFFERENT MEANING. infrequent-symptom condition is for event monitors up to 15 days, not 30-day monitoring; rule candidate: no other ECG monitoring code billed at the same time
- Row 4, POL-PAIN-002.c4: DIFFERENT MEANING. drops the LCD's documented-exception clause to the 2-week wait
- Row 6, POL-SURG-002.c2: DIFFERENT MEANING. drops the >2 cm sessile adenoma threshold, the 3-6 month and 1-2 year intervals (D-RULE-1) and the rectosigmoid exclusion
- Row 7, POL-FOOT-001.c3: NOT IN SOURCE. LCD only points to Benefit Policy Manual Ch. 15 §290, which is not in our sources
- Row 12, POL-CAR-001.c1: UNSURE. high-blood-pressure exclusion matches; the coverage part needs L37379's indication list

B_policy_sources_review.md, sitting 2 (every entry; its verdicts are decisions, not matches):

- 1. POL-SURG-004.F1: WRONG CRITERION: ADD IN V2. 0 v1 lines affected
- 2. POL-DX-003.F1: WRONG CRITERION: ADD IN V2. 0 v1 lines affected
- 3. POL-REHAB-001.F1: WRONG CRITERION: ADD IN V2. 6 v1 labels affected
- 4. POL-CAR-002.F1: WRONG CRITERION: ADD IN V2. also scope CAR-002.c1 by duration
- 5. POL-WOUND-001.F3: MISSING CRITERION: ADD IN V2. firm rule only: no continuing care without improvement; revise the plan if healing is not documented after 30 days
- 6. POL-WOUND-001.F5: MISSING CRITERION: NOT NEEDED. unrealistic in our claims; would mostly add NOT_APPLICABLE labels
- 7. POL-SURG-002.F1: MISSING CRITERION: ADD IN V2. criteria must not be narrower than the billing article's covered diagnoses
- 8. POL-SURG-002.F3: MISSING CRITERION: ADD IN V2. only the limitations diagnosis codes cannot catch; skip those R15 denies
- 9. POL-REHAB-001.F2: MISSING CRITERION: ADD IN V2. physician/NPP care and plan certification, for treatment lines only
- 10. Control: L33906-cov-028 (POL-PAIN-001): NOT NEEDED. control OK
- 11. Control: L38902-doc-018 (POL-WOUND-001): NOT NEEDED. control OK
- 12. Control: L33261-cov-090 (POL-DX-003): NOT NEEDED. control OK

C_disagreements_review.md (verdicts other than LABEL RIGHT):

- Row 1, DEC-TE-00043, line 1 (76882), POL-IMG-002.c3, gold NOT_DOCUMENTED, model NOT_APPLICABLE: MODEL RIGHT (reviewer's status NOT_APPLICABLE). ultrasound is for a soft-tissue mass, not plantar fasciitis
- Row 4, DEC-TE-00044, line 1 (76882), POL-IMG-002.c3, gold NOT_DOCUMENTED, model NOT_APPLICABLE: UNSURE (reviewer's status NOT_DOCUMENTED). depends on the line's diagnosis, which the sheet does not show
- Row 6, DEC-TE-00177, line 2 (93350), POL-CAR-001.c3, gold NOT_MET, model NOT_DOCUMENTED: UNSURE (reviewer's status UNSURE). notes contradict: "exertional chest tightness" vs "No CP/SOB; stress echo as routine screen"
- Row 9, DEC-TE-00007, line 2 (36475), POL-SURG-003.c3, gold MET, model NOT_APPLICABLE: MODEL RIGHT (reviewer's status NOT_APPLICABLE). exclusion criterion: the written NOT_APPLICABLE definition fits; gold MET follows a different convention
- Row 10, DEC-TE-00094, line 2 (95910), POL-DX-002.c2, gold MET, model NOT_APPLICABLE: MODEL RIGHT (reviewer's status NOT_APPLICABLE). same as row 9
- Row 11, DEC-TE-00138, line 2 (15823), POL-SURG-004.c4, gold MET, model NOT_APPLICABLE: UNSURE (reviewer's status UNSURE). exclusion criterion: complaints documented, but visual-field loss only 5 degrees (<12)
- Row 12, DEC-TE-00042, line 2 (36475), POL-SURG-003.c3, gold MET, model NOT_APPLICABLE: MODEL RIGHT (reviewer's status NOT_APPLICABLE). same as row 9

## Controls

- B_policy_sources_review.md, sitting 1, unflagged criteria (expected MATCHES): row 13 POL-SURG-004.c3 MATCHES; row 14 POL-FOOT-001.c2 MATCHES - as expected.
- B_policy_sources_review.md, sitting 2, items a keyword rule put out of scope (expected NOT NEEDED): entry 10 NOT NEEDED; entry 11 NOT NEEDED; entry 12 NOT NEEDED - as expected.
- A_labels_review.md and C_disagreements_review.md have no controls.

## Known limitations (UNSURE)

These keep their current labels (D-LIM-1):

- B_policy_sources_review.md, sitting 1 row 12, POL-CAR-001.c1: high-blood-pressure exclusion matches; the coverage part needs L37379's indication list
- C_disagreements_review.md row 4, DEC-TE-00044, line 1 (76882), POL-IMG-002.c3 (gold NOT_DOCUMENTED, model NOT_APPLICABLE): depends on the line's diagnosis, which the sheet does not show
- C_disagreements_review.md row 6, DEC-TE-00177, line 2 (93350), POL-CAR-001.c3 (gold NOT_MET, model NOT_DOCUMENTED): notes contradict: "exertional chest tightness" vs "No CP/SOB; stress echo as routine screen"
- C_disagreements_review.md row 11, DEC-TE-00138, line 2 (15823), POL-SURG-004.c4 (gold MET, model NOT_APPLICABLE): exclusion criterion: complaints documented, but visual-field loss only 5 degrees (<12)
