# Policies v2 review sheet: author triage of the pass 2 rows

Author triage (2026-10-09): Claude Code, the author of the criteria, triaged the 22 pass 2 rows in P2_policies_v2_triage.md; not an independent check. The pass 2 columns hold the reviewer's decisions, recorded as 'author triage by Claude Code, decided by Manideep'.

The 22 rows: the 17 that pass 1 flagged, plus the 5 random MATCHES rows (A2, A6, A10, A11, A24). Categories: LIMITING CHANGE 4, ADDED 4, MISSING LIMIT 3, REWORDING 2, TYPE 5, OK 4. Proposed fixes change draft text of new v2 criteria in place (no v2 data uses them yet) or only the code list of kept criteria (their ID and text stay); one new criterion (SURG-003.c4) needs its own approval. Every excerpt below is checked word for word against data/raw by scripts/verify/policies_v2_triage.py.

| Row | Criterion | Category | Action | Reason |
|---|---|---|---|---|
| A1 | POL-CAR-001.c4 | ADDED | fix | The lead-in 'signs or symptoms of, or is being evaluated for' and 'lung disease affecting the heart' had no cited item; cov-108 and cov-043 support the reworded lead-in and the pulmonary item. Left out: cov-009's expert-examiner condition, a provider qualification that claims do not carry (as for DX-001's accreditation, D-V2-1). |
| A2 | POL-CAR-001.c5 | OK | keep | 'not covered' and 'without signs or symptoms' are cov-012's words; no number. |
| A3 | POL-CAR-002.c4 | ADDED | fix | 'known' in 'a known arrhythmia' is in no cited item (cov-007 is 'Arrhythmias') and narrows it; removed. 'fainting' for 'Syncope (lightheadedness)' is a rewording. |
| A6 | POL-DX-001.c4 | OK | keep | 'moderate to severe' and the three examples are cov-110's; 'such as' keeps its open list; 'not covered' rests on cov-109's 'no comorbidities' criterion. |
| A10 | POL-DX-003.c5 | OK | keep | 'not covered' matches the list heading above cov-080 (cov-063), which the sheet's 'under' path did not show; cov-058's 'not recommended' is the reason given. |
| A11 | POL-FOOT-001.c4 | OK | keep | Class counts (two B; one B and two C; three trophic changes) and the asterisk rule match 290.D and 290.F; 'for example' keeps the presumption non-exhaustive, as 290.F does ('may be applied'). |
| A15 | POL-PAIN-001.c7 | LIMITING CHANGE | fix | 'only when a contrast allergy or pregnancy' closes a list the LCD gives as examples of a contraindication (cov-020, cov-025), and leaves out cov-015's ultrasound fallback. D-ESI-7 names allergy or pregnancy; the fix reads them as the LCD's examples. |
| A17 | POL-PAIN-001.c9 | ADDED | fix | The gloss '(pain that does not radiate from a nerve root)' is in no coverage item; the only LCD text for it is in the summary of evidence, which D-ESI-1 does not apply. Removed; D-ESI-4's reading stays with the cited decision. |
| A19 | POL-REHAB-001.c4 | MISSING LIMIT | fix | cov-020 limits coverage to a plan that sets type, frequency and duration; added. The evaluation sentence (and its missing proviso from cov-112) concerns codes c4 does not apply to, so it is removed; the code list carries REHAB-001.F1. |
| A20 | POL-REHAB-001.c5 | ADDED | fix | 'who certifies and recertifies' had no cited item; cov-005 and doc-016 say a physician or NPP certifies the plan and that it need not be the same one, so the text names no single physician. |
| A22 | POL-SURG-002.c4 | MISSING LIMIT | fix | cov-009 excludes a perianal source too and says 'not thought to be'; cov-010 limits black stool to 'unknown origin'. The examples in cov-007 and cov-023 stay out (examples only). |
| A24 | POL-SURG-002.c6 | LIMITING CHANGE | fix | Not OK: 'unless the record documents why it is needed' is cov-036's clause but was applied to cov-045's list, which has none; and cov-037's 'unusual exceptions' became 'it may be done'. The fix keeps the two lists apart. |
| A26 | POL-SURG-004.c5 | MISSING LIMIT | fix | cov-039 limits lid retraction or lag to three causes, and cov-040 limits dermatitis to symptomatic dermatitis of the pretarsal skin; added. Blepharospasm stays as is: cov-042 names it plainly and 'Primary essential (idiopathic)' describes it. |
| A27 | POL-SURG-004.c6 | LIMITING CHANGE | fix | cov-024's list is open ('include (but are not limited to)'); the text closed it. 'such as' reopens it. |
| A30 | POL-WOUND-001.c4 | LIMITING CHANGE | fix | cov-082 limits the no-continued-care rule to care aimed at healing ('However, if ... the goal of care is not wound healing ... palliative care standards'), and cov-118 says 'should' and 'expected healing'; restored. |
| B4 | POL-CAR-001.c2 | TYPE | fix | The yearly limit is the LCD's rule for TTE (sections A and F); shown on 93350 it could deny a repeat stress echo by the TTE rule. Code list: the TTE codes. |
| B17 | POL-IMG-001.c3 | REWORDING | keep | Type question; pass 1 too strict: as a requirement, silent notes give NOT_DOCUMENTED, right for 'need a documented reason', and the repeat-scan clause only bites when the notes show a second contrast scan, which then gives NOT_MET either way. |
| B18 | POL-IMG-001.c4 | TYPE | fix | An exclusion about brain imaging shown on the cervical spine MRI (72141) invites a wrong NOT_MET when the notes mention cancer staging; silent notes are unaffected. Code list: the head and brain codes. |
| B27 | POL-PAIN-002.c3 | REWORDING | keep | Type question; pass 1 too strict: the LCD makes the absence one of the criteria that ALL must be met (cov-015, cov-018, cov-019), so the record must show it; requirement (silent notes give NOT_DOCUMENTED) is right. |
| B29 | POL-REHAB-001.c3 | TYPE | fix | A requirement of restorative potential on the evaluation codes gives NOT_DOCUMENTED (PEND) on an evaluation with silent notes, though an evaluation can be covered when therapy is not needed (cov-112). Code list: the treatment codes. |
| B34 | POL-SURG-003.c1 | TYPE | fix | c1 is the LCD's ablation limitation (cov-022), so it belongs on the ablation codes. That leaves stab phlebectomy (37765) with no requirement, so a new c4 holds the LCD's section A indications, which cov-017 also applies to ablation and cov-028 to same-day phlebectomy. c4 is a new criterion: approve it separately. |
| B37 | POL-WOUND-001.c1 | TYPE | fix | A debridement requirement shown on the compression code (29581) gives NOT_DOCUMENTED (PEND) on a compression line with silent notes. Code list: the debridement codes; c2 and c4 still apply to 29581. |

## Drafts and excerpts

### A1. POL-CAR-001.c4: ADDED, fix

- Reason: The lead-in 'signs or symptoms of, or is being evaluated for' and 'lung disease affecting the heart' had no cited item; cov-108 and cov-043 support the reworded lead-in and the pulmonary item. Left out: cov-009's expert-examiner condition, a provider qualification that claims do not carry (as for DX-001's accreditation, D-V2-1).
- Old text: A transthoracic echocardiogram is covered when the patient has signs or symptoms of, or is being evaluated for, one of these: weakened heart muscle or cardiomyopathy; hypertensive heart disease with clinical evidence of heart disease; heart attack or coronary insufficiency; exposure to drugs or treatments toxic to the heart; heart transplant or rejection monitoring; native heart valve disease; prosthetic heart valves; acute endocarditis; pericardial disease; aortic disease; congenital heart disease; suspected clots or embolic sources in the heart; heart tumors or masses; critical illness or trauma; arrhythmias or palpitations; fainting (syncope); or lung disease affecting the heart.
- **New text:** A transthoracic echocardiogram is covered when the patient has symptoms of, or an existing condition in, one of these: weakened heart muscle or cardiomyopathy; hypertensive heart disease with clinical evidence of heart disease; heart attack or coronary insufficiency; exposure to drugs or treatments toxic to the heart; heart transplant or rejection monitoring; native heart valve disease; prosthetic heart valves; acute endocarditis; pericardial disease; aortic disease; congenital heart disease; suspected clots or embolic sources in the heart; heart tumors or masses; critical illness or trauma; arrhythmias or palpitations; fainting (syncope); or pulmonary heart disease, such as unexplained pulmonary hypertension or a pulmonary embolism with suspected clots in the right heart.
- Old source line: LCD L37379 v42 cov-006, cov-007, cov-009, cov-011, cov-012, cov-013, cov-016, cov-018, cov-020, cov-022, cov-024, cov-026, cov-028, cov-030, cov-032, cov-034, cov-036, cov-038, cov-040, cov-042.
- **New source line:** LCD L37379 v42 cov-006, cov-007, cov-009, cov-011, cov-012, cov-013, cov-016, cov-018, cov-020, cov-022, cov-024, cov-026, cov-028, cov-030, cov-032, cov-034, cov-036, cov-038, cov-040, cov-042, cov-043, cov-108.
- Excerpt words (word for word):
  - **L37379-cov-108**: "Symptoms or an existing condition must be present to meet medical necessity."
  - **L37379-cov-108**: "ECHO performed for screening purposes is not covered."
  - **L37379-cov-043**: "Pulmonary heart disease may result from acute changes in the pulmonary circulation"
  - **L37379-cov-043**: "Indications include unexplained pulmonary HTN and PE with suspected clots in the right atrium or ventricle."

### A2. POL-CAR-001.c5: OK, keep

- Reason: 'not covered' and 'without signs or symptoms' are cov-012's words; no number.
- Excerpt words (word for word):
  - **L37379-cov-012**: "When there are no signs or symptoms of heart disease, the use of TTE is not covered for hypertension (HTN)."

### A3. POL-CAR-002.c4: ADDED, fix

- Reason: 'known' in 'a known arrhythmia' is in no cited item (cov-007 is 'Arrhythmias') and narrows it; removed. 'fainting' for 'Syncope (lightheadedness)' is a rewording.
- Old text: Recording for up to 48 hours is covered for one or more of: palpitations, fainting or near fainting, dizziness, chest pain, transient ischemic episodes, shortness of breath, or a known arrhythmia; checking the response to antiarrhythmic drugs; heart attack survivors with an ejection fraction of 40% or less; coronary artery disease with active symptoms, to correlate chest pain with ST-segment changes; other acute and subacute forms of ischemic heart disease; or detecting arrhythmias after an ablation procedure.
- **New text:** Recording for up to 48 hours is covered for one or more of: palpitations, fainting or near fainting, dizziness, chest pain, transient ischemic episodes, shortness of breath, or arrhythmias; checking the response to antiarrhythmic drugs; heart attack survivors with an ejection fraction of 40% or less; coronary artery disease with active symptoms, to correlate chest pain with ST-segment changes; other acute and subacute forms of ischemic heart disease; or detecting arrhythmias after an ablation procedure.
- Excerpt words (word for word):
  - **L34636-cov-007**: "Arrhythmias"

### A6. POL-DX-001.c4: OK, keep

- Reason: 'moderate to severe' and the three examples are cov-110's; 'such as' keeps its open list; 'not covered' rests on cov-109's 'no comorbidities' criterion.
- Excerpt words (word for word):
  - **L35050-cov-110**: "including, but not limited to, moderate to severe pulmonary disease, neuromuscular disease, or congestive heart failure"
  - **L35050-cov-109**: "That no comorbidities exist that are contraindications to OCST testing"

### A10. POL-DX-003.c5: OK, keep

- Reason: 'not covered' matches the list heading above cov-080 (cov-063), which the sheet's 'under' path did not show; cov-058's 'not recommended' is the reason given.
- Excerpt words (word for word):
  - **L33261-cov-063**: "The following tests are considered not medically reasonable and necessary:"
  - **L33261-cov-080**: "Intradermal testing to diagnose food allergy"

### A11. POL-FOOT-001.c4: OK, keep

- Reason: Class counts (two B; one B and two C; three trophic changes) and the asterisk rule match 290.D and 290.F; 'for example' keeps the presumption non-exhaustive, as 290.F does ('may be applied').
- Excerpt words (word for word):
  - **§290.F**: "Two of the Class B findings; or"
  - **§290.F**: "One Class B and two Class C findings."
  - **§290.F**: "(Three required)"
  - **§290.D**: "routine procedures are covered only if the patient is under the active care of a doctor of medicine or osteopathy who documents the condition."

### A15. POL-PAIN-001.c7: LIMITING CHANGE, fix

- Reason: 'only when a contrast allergy or pregnancy' closes a list the LCD gives as examples of a contraindication (cov-020, cov-025), and leaves out cov-015's ultrasound fallback. D-ESI-7 names allergy or pregnancy; the fix reads them as the LCD's examples.
- Old text: Injections must be done under CT or fluoroscopic guidance with contrast; without contrast only when a contrast allergy or pregnancy is documented. A procedure code that includes imaging guidance counts as evidence of guidance, but contrast use, or the documented allergy or pregnancy, must be in the notes. Interlaminar and caudal injections are limited to one level, and transforaminal injections to two levels in one spinal region.
- **New text:** Injections must be done under CT or fluoroscopic guidance with contrast. Without contrast, for example under ultrasound guidance, they are covered only when a contraindication to contrast, such as an allergy or pregnancy, is documented. A procedure code that includes imaging guidance counts as evidence of guidance, but contrast use, or the documented contraindication, must be in the notes. Interlaminar and caudal injections are limited to one level, and transforaminal injections to two levels in one spinal region.
- Excerpt words (word for word):
  - **L33906-cov-020**: "unless the patient has a contraindication to contrast"
  - **L33906-cov-025**: "except in cases of documented contraindication to contrast media (e.g., allergy, pregnancy)"
  - **L33906-cov-015**: "ultrasound guidance without contrast may be considered"

### A17. POL-PAIN-001.c9: ADDED, fix

- Reason: The gloss '(pain that does not radiate from a nerve root)' is in no coverage item; the only LCD text for it is in the summary of evidence, which D-ESI-1 does not apply. Removed; D-ESI-4's reading stays with the cited decision.
- Old text: Injections are not covered to treat non-specific low back pain, axial spine pain (pain that does not radiate from a nerve root), complex regional pain syndrome, widespread diffuse pain, pain from neuropathy of other causes, or cervicogenic headaches.
- **New text:** Injections are not covered to treat non-specific low back pain, axial spine pain, complex regional pain syndrome, widespread diffuse pain, pain from neuropathy of other causes, or cervicogenic headaches.
- Excerpt words (word for word):
  - **L33906-cov-029**: "axial spine pain"

### A19. POL-REHAB-001.c4: MISSING LIMIT, fix

- Reason: cov-020 limits coverage to a plan that sets type, frequency and duration; added. The evaluation sentence (and its missing proviso from cov-112) concerns codes c4 does not apply to, so it is removed; the code list carries REHAB-001.F1.
- Old text: Treatment, as opposed to an initial evaluation or re-evaluation, must follow a written plan of care with specific goals, developed from an examination and evaluation. An evaluation can be covered even when it finds that therapy is not needed.
- **New text:** Treatment must follow a written plan of care, developed from an examination and evaluation, that sets specific goals and plans the procedures by type, frequency and duration.
- Excerpt words (word for word):
  - **L34428-cov-020**: "PT is only covered when it is rendered under a written plan of treatment"
  - **L34428-cov-020**: "planned out specifically in terms of type, frequency and duration"
  - **L34428-cov-112**: "if the patient's condition showed a need for an evaluation"

### A20. POL-REHAB-001.c5: ADDED, fix

- Reason: 'who certifies and recertifies' had no cited item; cov-005 and doc-016 say a physician or NPP certifies the plan and that it need not be the same one, so the text names no single physician.
- Old text: The patient must be under the care of a physician or NPP, who certifies and recertifies the plan of care.
- **New text:** The patient must be under the care of a physician or NPP, and a physician or NPP must certify the plan of care and recertify it.
- Old source line: LCD L34428 v93 cov-018, doc-007, doc-019.
- **New source line:** LCD L34428 v93 cov-005, cov-018, doc-007, doc-016, doc-019.
- Excerpt words (word for word):
  - **L34428-cov-005**: "Such NPPs may certify, order and establish the POC"
  - **L34428-doc-016**: "It is not required that the same physician/NPP who participated initially in recommending or planning the patient's care certify and/or recertify the plans."
  - **L34428-doc-019**: "the individual is under the care of a physician or NPP"

### A22. POL-SURG-002.c4: MISSING LIMIT, fix

- Reason: cov-009 excludes a perianal source too and says 'not thought to be'; cov-010 limits black stool to 'unknown origin'. The examples in cov-007 and cov-023 stay out (examples only).
- Old text: Colonoscopy to investigate symptoms or findings is covered for: an imaging abnormality likely to be significant; unexplained bleeding (blood in the stool not from a rectal source, black tarry stool, or a positive stool blood test); unexplained iron-deficiency anemia; significant unexplained diarrhea with other findings such as weight loss; examining the whole colon for synchronous cancer or polyps in a patient with a treatable cancer or polyp; chronic inflammatory bowel disease when a more precise diagnosis or the extent of activity will change immediate management; locating during surgery a lesion that cannot be found by touch or sight; acute colonic ischemia; Streptococcus bovis endocarditis; unexplained new-onset constipation that does not respond to medical treatment; an anorectal adenomatous polyp; or infectious colitis.
- **New text:** Colonoscopy to investigate symptoms or findings is covered for: an imaging abnormality likely to be significant; unexplained bleeding (blood in the stool not thought to be from a rectal or perianal source, black tarry stool of unknown origin, or a positive stool blood test); unexplained iron-deficiency anemia; significant unexplained diarrhea with other findings such as weight loss; examining the whole colon for synchronous cancer or polyps in a patient with a treatable cancer or polyp; chronic inflammatory bowel disease when a more precise diagnosis or the extent of activity will change immediate management; locating during surgery a lesion that cannot be found by touch or sight; acute colonic ischemia; Streptococcus bovis endocarditis; unexplained new-onset constipation that does not respond to medical treatment; an anorectal adenomatous polyp; or infectious colitis.
- Excerpt words (word for word):
  - **L34005-cov-009**: "Hematochezia not thought to be from rectum or perianal source"
  - **L34005-cov-010**: "Melena of unknown origin;"

### A24. POL-SURG-002.c6: LIMITING CHANGE, fix

- Reason: Not OK: 'unless the record documents why it is needed' is cov-036's clause but was applied to cov-045's list, which has none; and cov-037's 'unusual exceptions' became 'it may be done'. The fix keeps the two lists apart.
- Old text: Colonoscopy is generally not covered, unless the record documents why it is needed, for: chronic, stable irritable bowel syndrome or chronic abdominal pain (it may be done to rule out organic disease, especially when symptoms do not respond to therapy); acute diarrhea; hemorrhoids; routine follow-up of inflammatory bowel disease (cancer surveillance in Crohn's disease or chronic ulcerative colitis excepted); routine examination before elective abdominal surgery for a non-colonic disease; upper GI bleeding or black tarry stool with a demonstrated upper GI source; bright red rectal bleeding with a convincing anorectal source on sigmoidoscopy and no other symptoms suggesting a source higher up; fulminant colitis; possible perforation; acute severe diverticulitis; or diverticulosis as the reason for the test (it may still be reported when it is the final diagnosis).
- **New text:** Colonoscopy is generally not covered, unless the record documents why it is needed, for: chronic, stable irritable bowel syndrome or chronic abdominal pain (in unusual cases it may be done to rule out organic disease, especially when symptoms do not respond to therapy); acute diarrhea; hemorrhoids; routine follow-up of inflammatory bowel disease (cancer surveillance in Crohn's disease or chronic ulcerative colitis excepted); routine examination before elective abdominal surgery for a non-colonic disease; upper GI bleeding or black tarry stool with a demonstrated upper GI source; or bright red rectal bleeding with a convincing anorectal source on sigmoidoscopy and no other symptoms suggesting a source higher up. It is also generally not covered for fulminant colitis, possible perforation, acute severe diverticulitis, or diverticulosis as the reason for the test (it may still be reported when it is the final diagnosis).
- Excerpt words (word for word):
  - **L34005-cov-036**: "records must have additional documentation indicating the medical necessity of the procedure for review as needed"
  - **L34005-cov-037**: "There are unusual exceptions in which colonoscopy may be done to rule out organic disease"
  - **L34005-cov-045**: "Colonoscopy/Sigmoidoscopy/Proctosigmoidoscopy is generally not covered for:"

### A26. POL-SURG-004.c5: MISSING LIMIT, fix

- Reason: cov-039 limits lid retraction or lag to three causes, and cov-040 limits dermatitis to symptomatic dermatitis of the pretarsal skin; added. Blepharospasm stays as is: cov-042 names it plainly and 'Primary essential (idiopathic)' describes it.
- Old text: Eyelid surgery is covered when it corrects visual impairment caused by excess eyelid skin weighing down the lashes (dermatochalasis), blepharochalasis, drooping of the eyelid (blepharoptosis) or drooping of the brow. It is also covered as reconstruction: to repair defects caused by disease (including thyroid disease and cranial nerve palsies), trauma or tumor surgery; for ectropion or entropion, epiblepharon, lagophthalmos, congenital ectropion, entropion, lagophthalmos or ptosis, lid retraction or lag, or chronic dermatitis caused by redundant upper eyelid skin; or, when other treatments have failed or cannot be used, to relieve blepharospasm. For these reconstructive conditions, the record must document the patient's complaints and the examination findings.
- **New text:** Eyelid surgery is covered when it corrects visual impairment caused by excess eyelid skin weighing down the lashes (dermatochalasis), blepharochalasis, drooping of the eyelid (blepharoptosis) or drooping of the brow. It is also covered as reconstruction: to repair defects caused by disease (including thyroid disease and cranial nerve palsies), trauma or tumor surgery; for ectropion or entropion, epiblepharon, lagophthalmos, congenital ectropion, entropion, lagophthalmos or ptosis; for lid retraction or lag caused by horizontal laxity of the lower eyelid without ectropion or entropion (with exposure keratopathy or tearing), by horizontal laxity of the upper eyelid (with floppy eyelid syndrome), or by orbital thyroid disease; for chronic symptomatic dermatitis of the pretarsal skin caused by redundant upper eyelid skin; or, when other treatments have failed or cannot be used, to relieve blepharospasm. For these reconstructive conditions, the record must document the patient's complaints and the examination findings.
- Excerpt words (word for word):
  - **L33944-cov-039**: "Lid retraction or lag (due to horizontal lower eyelid laxity without ectropion or entropion, causing exposure keratopathy and/or epiphora; due to horizontal upper eyelid laxity, causing floppy eyelid syndrome; or due to orbital thyroid disease)."
  - **L33944-cov-040**: "Chronic symptomatic dermatitis of pretarsal skin caused by redundant upper eyelid skin."
  - **L33944-cov-042**: "Relief of eye symptoms associated with blepharospasm."

### A27. POL-SURG-004.c6: LIMITING CHANGE, fix

- Reason: cov-024's list is open ('include (but are not limited to)'); the text closed it. 'such as' reopens it.
- Old text: For dermatochalasis, blepharochalasis, blepharoptosis or brow ptosis, the record must document the patient's complaints of functional problems: vision blocked above or to the side, trouble reading because the upper field is lost, or looking through the eyelashes or seeing eyelid skin. The reconstructive conditions are exempt.
- **New text:** For dermatochalasis, blepharochalasis, blepharoptosis or brow ptosis, the record must document the patient's complaints of functional problems, such as vision blocked above or to the side, trouble reading because the upper field is lost, or looking through the eyelashes or seeing eyelid skin. The reconstructive conditions are exempt.
- Excerpt words (word for word):
  - **L33944-cov-024**: "These include (but are not limited to):"

### A30. POL-WOUND-001.c4: LIMITING CHANGE, fix

- Reason: cov-082 limits the no-continued-care rule to care aimed at healing ('However, if ... the goal of care is not wound healing ... palliative care standards'), and cov-118 says 'should' and 'expected healing'; restored.
- Old text: How often debridement is done depends on the wound. A given type of wound care is not continued when the record does not show improvement leading to healing, and when healing is not documented after 30 days the plan of care must be revised.
- **New text:** How often debridement is done depends on the wound. When the goal of care is healing, a given type of wound care is not continued if the record does not show improvement leading to healing, and when the expected healing is not documented after 30 days the plan of care should be revised. When the goal of care is not healing, the patient is managed under palliative care standards.
- Excerpt words (word for word):
  - **L38902-cov-082**: "Optimally, the overall goal of care is healing"
  - **L38902-cov-082**: "However, if it is determined that the goal of care is not wound healing"
  - **L38902-cov-082**: "the patient should be managed following appropriate palliative care standards"
  - **L38902-cov-118**: "Failure to document expected healing after 30 days should necessitate a revision in the Plan of Care"

### B4. POL-CAR-001.c2: TYPE, fix

- Reason: The yearly limit is the LCD's rule for TTE (sections A and F); shown on 93350 it could deny a repeat stress echo by the TTE rule. Code list: the TTE codes.
- Old Applies to: every code of the policy
- **New Applies to:** 93306, 93308 (text and ID unchanged)
- Excerpt words (word for word):
  - **L37379-cov-021**: "more frequently than annually"
  - **L37379-cov-021**: "imminent valvular surgery"

### B17. POL-IMG-001.c3: REWORDING, keep

- Reason: Type question; pass 1 too strict: as a requirement, silent notes give NOT_DOCUMENTED, right for 'need a documented reason', and the repeat-scan clause only bites when the notes show a second contrast scan, which then gives NOT_MET either way.
- Excerpt words (word for word):
  - **L37373-cov-030**: "More than one contrast CT scan per episode of illness adds no information with the following exceptions:"

### B18. POL-IMG-001.c4: TYPE, fix

- Reason: An exclusion about brain imaging shown on the cervical spine MRI (72141) invites a wrong NOT_MET when the notes mention cancer staging; silent notes are unaffected. Code list: the head and brain codes.
- Old Applies to: every code of the policy
- **New Applies to:** 70450, 70551, 70553 (text and ID unchanged)
- Excerpt words (word for word):
  - **L37373-cov-041**: "in the absence of symptoms of brain involvement"

### B27. POL-PAIN-002.c3: REWORDING, keep

- Reason: Type question; pass 1 too strict: the LCD makes the absence one of the criteria that ALL must be met (cov-015, cov-018, cov-019), so the record must show it; requirement (silent notes give NOT_DOCUMENTED) is right.
- Excerpt words (word for word):
  - **L33930-cov-015**: "in patients who meet ALL of the following criteria:"
  - **L33930-cov-018**: "Absence of untreated radiculopathy or neurogenic claudication"

### B29. POL-REHAB-001.c3: TYPE, fix

- Reason: A requirement of restorative potential on the evaluation codes gives NOT_DOCUMENTED (PEND) on an evaluation with silent notes, though an evaluation can be covered when therapy is not needed (cov-112). Code list: the treatment codes.
- Old Applies to: every code of the policy
- **New Applies to:** 97110, 97140, 97530 (text and ID unchanged)
- Excerpt words (word for word):
  - **L34428-cov-013**: "potential for improvement from the services"
  - **L34428-cov-112**: "Initial evaluations or re-evaluations may be determined reasonable and necessary even when the evaluation determines that skilled rehabilitation is not required"

### B34. POL-SURG-003.c1: TYPE, fix

- Reason: c1 is the LCD's ablation limitation (cov-022), so it belongs on the ablation codes. That leaves stab phlebectomy (37765) with no requirement, so a new c4 holds the LCD's section A indications, which cov-017 also applies to ablation and cov-028 to same-day phlebectomy. c4 is a new criterion: approve it separately.
- Old Applies to: every code of the policy
- **New Applies to:** 36475, 36478 (text and ID unchanged)
- **New criterion POL-SURG-003.c4** (requirement; applies to every code of the policy): Treatment of varicose veins, including stab phlebectomy, is covered when a 3-month trial of conservative therapy, such as exercise, periodic leg elevation, weight loss, compression or avoiding long immobility, has failed, and the patient is symptomatic with one or more of: pain or burning in the leg severe enough to impair mobility; recurrent superficial phlebitis; a non-healing skin ulcer; bleeding from a varicosity; stasis dermatitis; or refractory dependent edema.
  Source line: LCD L34209 v43 cov-007 to cov-015, cov-017, cov-028.
- Excerpt words (word for word):
  - **L34209-cov-022**: "ERFA and laser ablation are covered only for"
  - **L34209-cov-008**: "A 3-month trial of conservative therapy"
  - **L34209-cov-017**: "In addition to the above (see A)"
  - **L34209-cov-028**: "stab phlebectomy of the same vein performed on the same day as endovenous radiofrequency or laser ablation may be covered if the criteria for reasonable and necessary as described in this LCD are met."

### B37. POL-WOUND-001.c1: TYPE, fix

- Reason: A debridement requirement shown on the compression code (29581) gives NOT_DOCUMENTED (PEND) on a compression line with silent notes. Code list: the debridement codes; c2 and c4 still apply to 29581.
- Old Applies to: every code of the policy
- **New Applies to:** 11042, 97597 (text and ID unchanged)
- Excerpt words (word for word):
  - **L38902-cov-031**: "Active wound care procedures involve selective and non-selective debridement techniques and are performed to remove devitalized tissue"

