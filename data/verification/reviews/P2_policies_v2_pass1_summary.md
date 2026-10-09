# Policies v2 review sheet: pass 1 summary and the pass 2 rows

Pass 1 (2026-10-09): a normal Claude chat with no repository access, which saw only the pasted sheet and the pass 1 prompt (answers as returned: P2_policies_v2_pass1_answers.md). A Claude recomputation, not a human check; independent of the repository by construction, not of the author model (the criteria were also written by Claude). Pass 2 is the reviewer's: the rows listed in P2_policies_v2_pass1_summary.md.

Pass 1 verdicts: Part A: MATCHES 20, DIFFERENT MEANING 8, NOT IN SOURCE 2; Part B: AGREE 31, DISAGREE 4, UNSURE 3; Part C: COMPLETE 3.

## Pass 2: rows whose pass 1 verdict is not MATCHES, AGREE or COMPLETE (17)

| Row | Criterion | Pass 1 verdict | Pass 1 notes |
|---|---|---|---|
| A1 | POL-CAR-001.c4 | DIFFERENT MEANING | The lead-in "signs or symptoms of, or is being evaluated for" is applied to all 17 items, but only A (cov-009) and B (cov-012) state a signs/symptoms condition and C to Q are bare headings. "lung disease affecting the heart" adds "affecting the heart" to heading "Q. Pulmonary". cov-009's "expected to be performed by examiners recognized as experts" (diastolic dysfunction) is not reflected. |
| A3 | POL-CAR-002.c4 | DIFFERENT MEANING | "a known arrhythmia" narrows source item "Arrhythmias" (cov-007), which has no "known"; A5 uses plain "arrhythmias" for the matching 30-day list. The 40% ejection fraction, ST-segment and ablation items match. Minor: "Syncope (lightheadedness)" becomes "fainting". |
| A15 | POL-PAIN-001.c7 | DIFFERENT MEANING | "without contrast only when a contrast allergy or pregnancy is documented" is narrower than cov-020 ("unless the patient has a contraindication to contrast") and cov-025 ("documented contraindication to contrast media (e.g., allergy, pregnancy)"). cov-015's fallback is "ultrasound guidance without contrast", which the text does not mention. Level limits match cov-016 and cov-017. |
| A17 | POL-PAIN-001.c9 | NOT IN SOURCE | The gloss "(pain that does not radiate from a nerve root)" is not in cov-029, which says only "axial spine pain". The six listed conditions otherwise match. |
| A19 | POL-REHAB-001.c4 | DIFFERENT MEANING | Drops the proviso "if the patient's condition showed a need for an evaluation" (cov-112), so "An evaluation can be covered even when it finds that therapy is not needed" is unconditional (and it concerns evaluation codes this criterion does not apply to). It also drops the plan content in cov-020, "planned out specifically in terms of type, frequency and duration"; the text says only "specific goals". |
| A20 | POL-REHAB-001.c5 | NOT IN SOURCE | "who certifies and recertifies the plan of care": doc-007 only lists "Certifications and recertifications" as required documentation, with no who or what, and cov-018 lets the physical therapist establish the plan. "under the care of a physician or NPP" is supported by doc-019. |
| A22 | POL-SURG-002.c4 | DIFFERENT MEANING | "blood in the stool not from a rectal source" drops "or perianal" and "thought to be" from cov-009 ("not thought to be from rectum or perianal source"), which broadens it. Minor: examples "negative stool cultures persisting for more than 3 weeks" (cov-023) and "an inadequate examination" (cov-007) are left out. Other items match. |
| A26 | POL-SURG-004.c5 | DIFFERENT MEANING | Drops qualifiers. "lid retraction or lag" omits cov-039's "due to horizontal lower eyelid laxity ... due to horizontal upper eyelid laxity ... or due to orbital thyroid disease". "chronic dermatitis" omits "symptomatic" and "of pretarsal skin" (cov-040). Blepharospasm omits "Primary essential (idiopathic)" (cov-042). |
| A27 | POL-SURG-004.c6 | DIFFERENT MEANING | Closes an open list. cov-024 says the documentation must address the signs and symptoms commonly found, and "These include (but are not limited to)" three items; the text lists only those three complaints. |
| A30 | POL-WOUND-001.c4 | DIFFERENT MEANING | Drops the palliative exception in cov-082 ("However, if it is determined that the goal of care is not wound healing ... palliative care standards"), which also conflicts with kept c2 (B38: "preventing the wound from getting worse"). "must be revised" hardens cov-118's "should necessitate a revision", and "expected healing" becomes "healing". The 30 days and the frequency sentence match. |
| B4 | POL-CAR-001.c2 | UNSURE | Conditional fits the repeat trigger, but "all" includes 93350 (stress echo) while the TTE criteria A1 and A2 apply to 93306, 93308 only. The text says "Repeating the study more often than once a year" and "planned valve surgery", so the sheet does not show the rule covers stress echo. |
| B17 | POL-IMG-001.c3 | UNSURE | 70553 is the only contrast code, so the code list fits. The type mixes a requirement ("need a documented reason") with a repeat-scan rule ("More than one contrast scan per episode of illness is not covered except ...") that applies only to a second contrast scan; the sheet splits mixed criteria elsewhere (A1 and A2). |
| B18 | POL-IMG-001.c4 | DISAGREE | Text says "Brain imaging", but "all" includes 72141 (MRI of the neck (cervical) spine). Applies to should be 70450, 70551, 70553. |
| B27 | POL-PAIN-002.c3 | UNSURE | Negative wording ("There must be no untreated nerve-root pain ... and no other cause of the pain") behaves like an exclusion (silent notes give NOT_APPLICABLE) but is typed requirement (silent notes give NOT_DOCUMENTED, so PEND). Confirm that is intended. |
| B29 | POL-REHAB-001.c3 | DISAGREE | "Restorative therapy requires a reasonable potential for improvement" should not apply to evaluation codes 97161 and 97162 (A19: an evaluation can be covered even when therapy is not needed). Applies to should be 97110, 97140, 97530. |
| B34 | POL-SURG-003.c1 | DISAGREE | Text is limited to "Radiofrequency or laser vein ablation", but "all" includes 37765 (removal through small punctures, not ablation). Applies to should be 36475, 36478, or the text should be widened. |
| B37 | POL-WOUND-001.c1 | DISAGREE | Text is about "Active wound care (debridement) ... to remove dead tissue", but "all" includes 29581 (multi-layer compression wrap), which is not debridement. Applies to should be 11042, 97597. |

## Pass 2: 5 random Part A MATCHES rows

Drawn with random.Random(42).sample from the 20 Part A MATCHES rows in row order.

| Row | Criterion | Pass 1 notes |
|---|---|---|
| A2 | POL-CAR-001.c5 | Same as the first sentence of cov-012 ("When there are no signs or symptoms of heart disease, the use of TTE is not covered for hypertension"); exclusion type fits. |
| A6 | POL-DX-001.c4 | Matches cov-110 (significant comorbid conditions or sleep disorders; moderate to severe pulmonary disease, neuromuscular disease, congestive heart failure). "not covered" is supported by the parent heading "...are not covered in the following situations". |
| A10 | POL-DX-003.c5 | cov-058 and cov-080 sit under Limitations, so "not covered" is a fair reading, though cov-058 itself uses the weaker "not recommended". |
| A11 | POL-FOOT-001.c4 | Systemic conditions and asterisk/active-care rule (290.D), Class B/C counts including "three required" (290.F), "diagnosis alone" (290.G) and the 290.C.3 hazard wording all match; "for example" keeps the findings non-exhaustive. |
| A24 | POL-SURG-002.c6 | All items of cov-037 to cov-049 are present (cov-040 left out on purpose per the sheet). Minor: "unusual exceptions" (cov-037) becomes "it may be done", and cov-036's documentation clause is also applied to the cov-045 list. |
