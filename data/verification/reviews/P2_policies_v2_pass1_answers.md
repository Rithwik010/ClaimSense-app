# Policies v2 review sheet: pass 1 answers

Returned on 2026-10-09 by a normal Claude chat with no repository access, which saw only the pasted
sheet (P2_policies_v2_sheet.md, commit 0f1b92a) and the pass 1 prompt. A Claude recomputation, not
a human check; independent of the repository by construction, not of the author model (the criteria
were also written by Claude). The tables below are as returned; scripts/verify/policies_v2_review.py
merges them into the sheet.

### Part A (MATCHES, DIFFERENT MEANING, NOT IN SOURCE or UNSURE)

| Row | Criterion | Pass 1 verdict (Claude chat) | Pass 1 notes | Pass 2 verdict (reviewer) | Pass 2 notes |
|---|---|---|---|---|---|
| A1 | POL-CAR-001.c4 | DIFFERENT MEANING | The lead-in "signs or symptoms of, or is being evaluated for" is applied to all 17 items, but only A (cov-009) and B (cov-012) state a signs/symptoms condition and C to Q are bare headings. "lung disease affecting the heart" adds "affecting the heart" to heading "Q. Pulmonary". cov-009's "expected to be performed by examiners recognized as experts" (diastolic dysfunction) is not reflected. |  |  |
| A2 | POL-CAR-001.c5 | MATCHES | Same as the first sentence of cov-012 ("When there are no signs or symptoms of heart disease, the use of TTE is not covered for hypertension"); exclusion type fits. |  |  |
| A3 | POL-CAR-002.c4 | DIFFERENT MEANING | "a known arrhythmia" narrows source item "Arrhythmias" (cov-007), which has no "known"; A5 uses plain "arrhythmias" for the matching 30-day list. The 40% ejection fraction, ST-segment and ablation items match. Minor: "Syncope (lightheadedness)" becomes "fainting". |  |  |
| A4 | POL-CAR-002.c5 | MATCHES | Matches cov-019 (more than 48 h up to 15 days; asymptomatic episodes for treatment response; infrequent symptoms, less often than every 48 hours). Minor: source says "alternative to Holter monitoring", text says "alternative to 48-hour monitoring". |  |  |
| A5 | POL-CAR-002.c6 | MATCHES | All items of cov-022 to cov-032 are present and no ejection fraction is added for heart attack survivors. cov-020's billing rule is left to R11, as the sheet states. |  |  |
| A6 | POL-DX-001.c4 | MATCHES | Matches cov-110 (significant comorbid conditions or sleep disorders; moderate to severe pulmonary disease, neuromuscular disease, congestive heart failure). "not covered" is supported by the parent heading "...are not covered in the following situations". |  |  |
| A7 | POL-DX-001.c5 | MATCHES | Matches cov-107 and cov-108 (high likelihood of moderate to severe sleep apnea, shown by symptoms and physical examination in the note). |  |  |
| A8 | POL-DX-002.c4 | MATCHES | Matches cov-037 ("usually considered not medically necessary"; "The only exception" is carpal tunnel syndrome with a high pre-test probability). "which the notes must document" comes from the cited decision and the conditional type, not the source. |  |  |
| A9 | POL-DX-003.c4 | MATCHES | Prick list matches cov-008. Intradermal list matches cov-009 without foods, consistent with cov-058. Correlation with history and examination matches cov-007. |  |  |
| A10 | POL-DX-003.c5 | MATCHES | cov-058 and cov-080 sit under Limitations, so "not covered" is a fair reading, though cov-058 itself uses the weaker "not recommended". |  |  |
| A11 | POL-FOOT-001.c4 | MATCHES | Systemic conditions and asterisk/active-care rule (290.D), Class B/C counts including "three required" (290.F), "diagnosis alone" (290.G) and the 290.C.3 hazard wording all match; "for example" keeps the findings non-exhaustive. |  |  |
| A12 | POL-FOOT-001.c5 | MATCHES | Matches 290.C.4 for ambulatory and nonambulatory patients. "covered only when" becomes "is covered when", but c6 carries the "only". |  |  |
| A13 | POL-FOOT-001.c6 | MATCHES | Matches 290.B.2 (corns, calluses, nail trimming and debriding). "Except as provided above" becomes "Except in the situations this policy covers", in line with c4, c5 and Part C. |  |  |
| A14 | POL-PAIN-001.c6 | MATCHES | Severity and baseline scale match cov-013 and cov-023. "a numeric score or a named scale" is added by cited decision D-ESI-2. |  |  |
| A15 | POL-PAIN-001.c7 | DIFFERENT MEANING | "without contrast only when a contrast allergy or pregnancy is documented" is narrower than cov-020 ("unless the patient has a contraindication to contrast") and cov-025 ("documented contraindication to contrast media (e.g., allergy, pregnancy)"). cov-015's fallback is "ultrasound guidance without contrast", which the text does not mention. Level limits match cov-016 and cov-017. |  |  |
| A16 | POL-PAIN-001.c8 | MATCHES | Matches cov-019 and cov-039 (50% for 3 months or 50% function on the same scale; repeat after 14 days with a different approach, level or medication, rationale documented). |  |  |
| A17 | POL-PAIN-001.c9 | NOT IN SOURCE | The gloss "(pain that does not radiate from a nerve root)" is not in cov-029, which says only "axial spine pain". The six listed conditions otherwise match. |  |  |
| A18 | POL-PAIN-002.c5 | MATCHES | Matches cov-023 and cov-024 (RFA intent; second procedure a minimum of 2 weeks later; documented exception). |  |  |
| A19 | POL-REHAB-001.c4 | DIFFERENT MEANING | Drops the proviso "if the patient's condition showed a need for an evaluation" (cov-112), so "An evaluation can be covered even when it finds that therapy is not needed" is unconditional (and it concerns evaluation codes this criterion does not apply to). It also drops the plan content in cov-020, "planned out specifically in terms of type, frequency and duration"; the text says only "specific goals". |  |  |
| A20 | POL-REHAB-001.c5 | NOT IN SOURCE | "who certifies and recertifies the plan of care": doc-007 only lists "Certifications and recertifications" as required documentation, with no who or what, and cov-018 lets the physical therapist establish the plan. "under the care of a physician or NPP" is supported by doc-019. |  |  |
| A21 | POL-SURG-001.c4 | MATCHES | Matches cov-008 (high probability of accelerating cataract development after a concomitant or subsequent procedure; examples; external beam irradiation). |  |  |
| A22 | POL-SURG-002.c4 | DIFFERENT MEANING | "blood in the stool not from a rectal source" drops "or perianal" and "thought to be" from cov-009 ("not thought to be from rectum or perianal source"), which broadens it. Minor: examples "negative stool cultures persisting for more than 3 weeks" (cov-023) and "an inadequate examination" (cov-007) are left out. Other items match. |  |  |
| A23 | POL-SURG-002.c5 | MATCHES | Matches cov-013, 015, 017, 019 to 021 (2 cm, 7 years, 15 years, rectosigmoid). The 3 to 6 month and 1 to 2 year intervals are dropped by the sheet's D-RULE-1. |  |  |
| A24 | POL-SURG-002.c6 | MATCHES | All items of cov-037 to cov-049 are present (cov-040 left out on purpose per the sheet). Minor: "unusual exceptions" (cov-037) becomes "it may be done", and cov-036's documentation clause is also applied to the cov-045 list. |  |  |
| A25 | POL-SURG-002.c7 | MATCHES | Matches cov-027 to cov-031 and cov-034. Minor: "stenosing, bleeding neoplasms" becomes "narrowing or bleeding tumors". |  |  |
| A26 | POL-SURG-004.c5 | DIFFERENT MEANING | Drops qualifiers. "lid retraction or lag" omits cov-039's "due to horizontal lower eyelid laxity ... due to horizontal upper eyelid laxity ... or due to orbital thyroid disease". "chronic dermatitis" omits "symptomatic" and "of pretarsal skin" (cov-040). Blepharospasm omits "Primary essential (idiopathic)" (cov-042). |  |  |
| A27 | POL-SURG-004.c6 | DIFFERENT MEANING | Closes an open list. cov-024 says the documentation must address the signs and symptoms commonly found, and "These include (but are not limited to)" three items; the text lists only those three complaints. |  |  |
| A28 | POL-SURG-004.c7 | MATCHES | Matches cov-028 (minimum 12 degree or 30 percent loss of upper field, potential correction). The lid-taping method is not stated but not contradicted. |  |  |
| A29 | POL-SURG-004.c8 | MATCHES | Supported by cov-001, cov-004 and cov-006. Paraphrases "in the absence of any signs or symptoms of functional abnormalities" as "without documented functional impairment"; the "to improve a patient's appearance" purpose is implicit. |  |  |
| A30 | POL-WOUND-001.c4 | DIFFERENT MEANING | Drops the palliative exception in cov-082 ("However, if it is determined that the goal of care is not wound healing ... palliative care standards"), which also conflicts with kept c2 (B38: "preventing the wound from getting worse"). "must be revised" hardens cov-118's "should necessitate a revision", and "expected healing" becomes "healing". The 30 days and the frequency sentence match. |  |  |

### Part B (AGREE, DISAGREE or UNSURE)

| Row | Criterion | Pass 1 verdict (Claude chat) | Pass 1 notes | Pass 2 verdict (reviewer) | Pass 2 notes |
|---|---|---|---|---|---|
| B1 | POL-BH-001.c1 | AGREE | Positive coverage condition, so requirement fits; all three codes. |  |  |
| B2 | POL-BH-001.c2 | AGREE | Lists situations not covered, so exclusion fits; all codes. |  |  |
| B3 | POL-BH-001.c3 | AGREE | Not-necessary situation, so exclusion fits; all codes. |  |  |
| B4 | POL-CAR-001.c2 | UNSURE | Conditional fits the repeat trigger, but "all" includes 93350 (stress echo) while the TTE criteria A1 and A2 apply to 93306, 93308 only. The text says "Repeating the study more often than once a year" and "planned valve surgery", so the sheet does not show the rule covers stress echo. |  |  |
| B5 | POL-CAR-001.c3 | AGREE | Stress-echo requirement; 93350 only is right. |  |  |
| B6 | POL-DX-001.c1 | AGREE | Requirement for sleep testing; all three codes. |  |  |
| B7 | POL-DX-001.c3 | AGREE | Conditional on a repeat facility study; 95810 and 95811 are the facility codes (95806 is home). |  |  |
| B8 | POL-DX-002.c1 | AGREE | Requirement; all three codes. |  |  |
| B9 | POL-DX-002.c2 | AGREE | Situation where the test is not appropriate, so exclusion fits. "first-line" is softer than "not covered" but acceptable; all codes. |  |  |
| B10 | POL-DX-002.c3 | AGREE | Not-covered situations, so exclusion fits; all codes. |  |  |
| B11 | POL-DX-003.c2 | AGREE | Patch-test requirement; 95044 only is right. |  |  |
| B12 | POL-DX-003.c3 | AGREE | Requirement across prick, intradermal and patch tests; all three codes. |  |  |
| B13 | POL-FOOT-001.c1 | AGREE | Conditional on neuropathy without vascular impairment; both nail codes; indication group matches C1. |  |  |
| B14 | POL-FOOT-001.c2 | AGREE | Conditional on anticoagulation; both codes; indication group matches C1. |  |  |
| B15 | POL-IMG-001.c1 | AGREE | General requirement for head or neck CT/MRI; all four codes. |  |  |
| B16 | POL-IMG-001.c2 | AGREE | Conditional on headache or dizziness; "all" is workable because the trigger gates it. |  |  |
| B17 | POL-IMG-001.c3 | UNSURE | 70553 is the only contrast code, so the code list fits. The type mixes a requirement ("need a documented reason") with a repeat-scan rule ("More than one contrast scan per episode of illness is not covered except ...") that applies only to a second contrast scan; the sheet splits mixed criteria elsewhere (A1 and A2). |  |  |
| B18 | POL-IMG-001.c4 | DISAGREE | Text says "Brain imaging", but "all" includes 72141 (MRI of the neck (cervical) spine). Applies to should be 70450, 70551, 70553. |  |  |
| B19 | POL-IMG-002.c1 | AGREE | Requirement listing the covered indications; both ultrasound codes. |  |  |
| B20 | POL-IMG-002.c2 | AGREE | Not-necessary situations, so exclusion fits; both codes. |  |  |
| B21 | POL-IMG-002.c3 | AGREE | Conditional on plantar fasciitis; both codes. |  |  |
| B22 | POL-IMG-002.c4 | AGREE | Conditional on both limbs scanned; both codes. |  |  |
| B23 | POL-PAIN-001.c1 | AGREE | Requirement; all three ESI codes. |  |  |
| B24 | POL-PAIN-001.c3 | AGREE | Requirement with an exemption for acute shingles pain; all codes. |  |  |
| B25 | POL-PAIN-002.c1 | AGREE | Requirement; all three facet codes. |  |  |
| B26 | POL-PAIN-002.c2 | AGREE | Requirement; all codes. |  |  |
| B27 | POL-PAIN-002.c3 | UNSURE | Negative wording ("There must be no untreated nerve-root pain ... and no other cause of the pain") behaves like an exclusion (silent notes give NOT_APPLICABLE) but is typed requirement (silent notes give NOT_DOCUMENTED, so PEND). Confirm that is intended. |  |  |
| B28 | POL-REHAB-001.c1 | AGREE | Requirement; all five codes, including evaluations, is fine. |  |  |
| B29 | POL-REHAB-001.c3 | DISAGREE | "Restorative therapy requires a reasonable potential for improvement" should not apply to evaluation codes 97161 and 97162 (A19: an evaluation can be covered even when therapy is not needed). Applies to should be 97110, 97140, 97530. |  |  |
| B30 | POL-SURG-001.c1 | AGREE | Conditional on a symptomatic cataract; both codes; indication group matches C2. |  |  |
| B31 | POL-SURG-001.c2 | AGREE | Not-necessary situation, so exclusion fits, outside the group; both codes. |  |  |
| B32 | POL-SURG-001.c3 | AGREE | Conditional; indication group matches C2; both codes. |  |  |
| B33 | POL-SURG-002.c3 | AGREE | Conditional on high-risk screening; indication group matches C3; all three codes. Note: keeps "every 24 months" while A23 drops intervals by D-RULE-1. |  |  |
| B34 | POL-SURG-003.c1 | DISAGREE | Text is limited to "Radiofrequency or laser vein ablation", but "all" includes 37765 (removal through small punctures, not ablation). Applies to should be 36475, 36478, or the text should be widened. |  |  |
| B35 | POL-SURG-003.c2 | AGREE | Exclusion "by any technique", so all three codes. |  |  |
| B36 | POL-SURG-003.c3 | AGREE | Exclusion "by any technique", so all three codes. |  |  |
| B37 | POL-WOUND-001.c1 | DISAGREE | Text is about "Active wound care (debridement) ... to remove dead tissue", but "all" includes 29581 (multi-layer compression wrap), which is not debridement. Applies to should be 11042, 97597. |  |  |
| B38 | POL-WOUND-001.c2 | AGREE | Plan-of-care requirement fits every wound code, including the compression wrap. |  |  |

### Part C (COMPLETE, GAPS or UNSURE)

| Row | Criterion | Pass 1 verdict (Claude chat) | Pass 1 notes | Pass 2 verdict (reviewer) | Pass 2 notes |
|---|---|---|---|---|---|
| C1 | POL-FOOT-001 | COMPLETE | cov-002 maps to c1, cov-003 to c2, manual C.3, D, F, G to c4, and C.4 to c5. The left-out items are right for nail codes 11720 and 11721. A (subluxation), C.2 (warts) and E (supportive devices) are billed with other codes. C.1 (integral care) is not separately payable: G.1 says "a separately itemized charge for such excluded service should be disallowed". |  |  |
| C2 | POL-SURG-001 | COMPLETE | All six items of cov-004 to cov-009 are held: cov-004 maps to c1, cov-005, 006, 007, 009 to c3, and cov-008 to c4. cov-004's "not deemed to be medically necessary purely on the basis of lens opacity" sits in c2, outside the group. |  |  |
| C3 | POL-SURG-002 | COMPLETE | Every block of cov-007 to cov-034 and doc-001 maps to c3, c4, c5 or c7, and the mappings agree with the criterion texts (A22, A23, A25, B33). cov-008 is not listed; it appears to be the "Evaluation of unexplained gastrointestinal bleeding:" heading named in cov-009's "under" path, but worth a glance. |  |  |
