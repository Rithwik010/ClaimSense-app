# Policy source and completeness check (Task V1b): review sheet

For one reviewer, in two sittings of about 35 minutes each. Sitting 1 verdicts: MATCHES, DIFFERENT MEANING, NOT IN SOURCE or UNSURE. Sitting 2 verdicts: ADD IN V2, NOT NEEDED or UNSURE.

- **The excerpts were selected, and the items classified and grouped, by the same model that wrote the criteria, so the human review of the flagged rows, the findings and the controls is the independent check.**
- **Only in the full CSVs.** Part 1: 43 of 57 criteria are only in B_policy_sources_full.csv (15 composite-only flags not sampled, 23 unflagged criteria, and the 5 POL-PAIN-001 criteria, whose 3 flags were decided in V1a). Part 2: 63 of 72 findings (195 LCD items) are only in B_findings_full.csv, and the 829 items that are in no finding (mapped, covered, already decided or out of scope), apart from the 3 controls, are only in B_completeness_full.csv.
- Criteria: 57; flagged: 30 (composite 26, differing values 7, low meaning similarity 5, outside the coverage field 1); composite-only: 17; POL-PAIN-001 flags already decided (D-ESI-1 to D-ESI-7), not reviewed again: 3.
- Meaning similarity (criterion vs its excerpt, BAAI/bge-small-en-v1.5 cosine, triage only): min 0.716, 10th percentile 0.754, median 0.853, max 0.999; flagged below 0.754 (the 10th percentile).
- Checker self-test: 8/8 planted cases behaved as expected (an exact excerpt passes; a made-up source sentence is flagged; NOT FOUND is flagged; a different duration is flagged; an excerpt from the evidence summary is flagged; a composite excerpt is flagged; background blocks are skipped; footnote superscripts are removed).
- LCD items: 1060 (161 background, definition and abstract blocks skipped); mapped to a criterion by its excerpt: 127; covered by a criterion (paraphrase): 161; already decided (POL-PAIN-001): 8.
- NOT IN POLICY items per classification: affects decisions 207, rule candidate 24, out of scope 533.
- Classified by keyword rules: 16; by section: 426; by item-level judgment: 491, of which 7 replace a keyword rule that misfired. Unmapped items at least 0.628 similar to a criterion (5th percentile of mapped items) were judged by hand before any rule.
- Findings: 72 (WRONG CRITERION 4, MISSING CRITERION 52, RULE CANDIDATE 16), holding all 231 items classified as affecting decisions or rule candidates, each in exactly one finding. Impact = dataset lines (all splits) of the finding's codes.
- AMA CPT descriptor text: excerpts containing it 0; displayed items with it replaced by [AMA CPT descriptor omitted]: 0.
- Estimated time: sitting 1 28 minutes (14 rows, 2 minutes each); sitting 2 34 minutes (2 minutes per finding plus 1 per 4 LCD items after the first; 2 per control).

## Sitting 1: source check (Part 1), about 28 minutes

Does the source text say what our criterion says? Write MATCHES, DIFFERENT MEANING, NOT IN SOURCE or UNSURE. POL-PAIN-001 is left out (decided in V1a).

| # | Criterion ID (why shown) | Our criterion text | Source file | Source text found (or NOT FOUND) | Similarity | Differing values | Your verdict | Notes |
|---|---|---|---|---|---|---|---|---|
| 1 | POL-DX-001.c1 (flagged: outside the coverage field (associated_info); composite (4 excerpts)) | Sleep testing is covered to evaluate suspected sleep apnea or narcolepsy when the physician's evaluation documents the symptoms and findings that led to the test. | data/raw/mcd/2026-09-21/current_lcd.zip:lcd.csv:L35050v55:indication [...] data/raw/mcd/2026-09-21/current_lcd.zip:lcd.csv:L35050v55:indication [...] data/raw/mcd/2026-09-21/current_lcd.zip:lcd.csv:L35050v55:indication [...] data/raw/mcd/2026-09-21/current_lcd.zip:lcd.csv:L35050v55:associated_info | All reasonable and necessary diagnostic tests given for the medical conditions listed in subsection B are covered when the following criteria are met: (Please refer to CMS Publication 100-02, Medicare Benefit Policy Manual , Chapter 15, Section 70 for complete information). [...] The diagnosis of narcolepsy is usually confirmed by an overnight sleep study (polysomnography) that is facility based followed by a MSLT that is likewise facility based. [...] Sleep Apnea - Testing by type III or IV devices can also be covered under special circumstances. [...] The patient is to be evaluated by a physician prior to ordering of test. | 1.0 | - | MATCHES | physician evaluation before ordering; fair reading |
| 2 | POL-CAR-002.c1 (flagged: composite (2 excerpts); differing values) | Heart rhythm monitoring is covered for symptoms suggesting an arrhythmia: palpitations, fainting or near fainting, dizziness, chest pain, transient ischemic episodes, shortness of breath, or a known arrhythmia. | data/raw/mcd/2026-09-21/current_lcd.zip:lcd.csv:L34636v38:indication | Indications for external 48-hour ECG recording include 1 or more of the following: [...] Arrhythmias Chest pain Syncope (lightheadedness) or near syncope Vertigo (dizziness) Palpitations Transient ischemic episodes Dyspnea (shortness of breath) | 1.0 | source: 48 hour | DIFFERENT MEANING | LCD list is for 48-hour recording only; criterion has no duration scope |
| 3 | POL-CAR-002.c3 (flagged: composite (2 excerpts); differing values) | Recording for more than 48 hours (up to 15 days) or 30-day event monitoring is covered when symptoms occur less often than every 48 hours, or to monitor the response to treatment for the listed conditions. | data/raw/mcd/2026-09-21/current_lcd.zip:lcd.csv:L34636v38:indication | The use of external electrocardiographic recording for greater than 48 hours and up to 7 days or for greater than 7 days up to 15 days by continuous rhythm recording and storage, may be considered medically necessary in patients treated for reasons listed in the diagnosis list to monitor for asymptomatic episodes in order to evaluate treatment response. The use of external electrocardiographic event monitors for greater than 48 hours and up to 7 days or for greater than 7 days up to 15 days that are either patient-activated or auto-activated may be considered medically necessary as a diagnostic alternative to Holter monitoring in patients who experience infrequent symptoms (less frequently than every 48 hours) suggestive of cardiac arrhythmias (i.e., palpitations, dizziness, presyncope, or syncope). [...] Long term 30-day monitoring: Telephonic Transmission of ECG involves 24 hour attended monitoring per 30-day period of time; no other EKG monitoring codes can be billed simultaneously with these codes. | 1.0 | source: 24 hour; source: at most 7 day; source: more than 7 day; source: per 30 day | DIFFERENT MEANING | infrequent-symptom condition is for event monitors up to 15 days, not 30-day monitoring; rule candidate: no other ECG monitoring code billed at the same time |
| 4 | POL-PAIN-002.c4 (flagged: differing values) | Diagnostic facet procedures are done with the intent of proceeding to radiofrequency ablation at that level if they succeed. A second, confirming diagnostic procedure at the same level must be at least 2 weeks after the first. | data/raw/mcd/2026-09-21/current_lcd.zip:lcd.csv:L33930v49:indication | Diagnostic procedures should be performed with the intent that if successful, RFA procedure would be considered the primary treatment goal at the diagnosed level(s). A second diagnostic facet procedure is considered medically reasonable and necessary to confirm validity of the initial diagnostic facet procedure when administered at the same level. The second diagnostic procedure may only be performed a minimum of 2 weeks after the initial diagnostic procedure.Clinical circumstances that necessitate an exception to the 2 week duration may be considered on an individual basis and must be clearly documented in the medical record. | 1.0 | source: 2 week; condition word in source only: except | DIFFERENT MEANING | drops the LCD's documented-exception clause to the 2-week wait |
| 5 | POL-SURG-002.c1 (flagged: composite (2 excerpts); differing values) | Colonoscopy to investigate symptoms is covered for an imaging abnormality likely to be significant; unexplained bleeding (blood in the stool not from a rectal source, black tarry stool, or a positive stool blood test); unexplained iron-deficiency anemia; or significant unexplained diarrhea with other findings such as weight loss. | data/raw/mcd/2026-09-21/current_lcd.zip:lcd.csv:L34005v34:indication | Evaluation of an abnormality discovered on barium enema and/or other imaging technique that is likely to be clinically significant, such as a filling defect or stricture or an inadequate examination; Evaluation of unexplained gastrointestinal bleeding: Hematochezia not thought to be from rectum or perianal source Melena of unknown origin; Presence of fecal occult blood Unexplained iron deficiency anemia; [...] Clinically significant diarrhea of unexplained origin with additional findings (e.g., with weight loss or negative stool cultures persisting for more than 3 weeks; | 1.0 | source: more than 3 week | MATCHES | drops one example (negative stool cultures >3 weeks); missing indications are SURG-002.F1 |
| 6 | POL-SURG-002.c2 (flagged: composite (4 excerpts); differing values) | Surveillance is covered for a history of colorectal cancer or polyps, follow-up one year after colorectal cancer surgery, follow-up after removal of a large polyp, and inflammatory bowel disease surveillance (pancolitis for more than 7 years, or left-sided colitis for more than 15 years). | data/raw/mcd/2026-09-21/current_lcd.zip:lcd.csv:L34005v34:indication | Surveillance of colonic neoplasia. When the patient has a history of colorectal cancer or polyps and is being followed for this indication; [...] Follow-up in one year after surgery for treatment of colorectal cancer; [...] Follow-up for removal of neoplastic polyp (follow-up at least three to six months to verify removal of large sessile adenoma [i.e., greater than 2 cm in greatest dimension] after colonoscopic removal); [...] In patients with Crohn’s colitis and chronic ulcerative colitis: colonoscopy every one or two years with multiple biopsies for detection of cancer and dysplasia in patients with: Pancolitis of greater than seven years duration; or, Left-sided colitis of over 15 years duration (no surveillance needed for disease limited to rectosigmoid); | 1.0 | source: 2 year; source: 6 month | DIFFERENT MEANING | drops the >2 cm sessile adenoma threshold, the 3-6 month and 1-2 year intervals (D-RULE-1) and the rectosigmoid exclusion |
| 7 | POL-FOOT-001.c3 (flagged: low meaning similarity 0.731 < 0.754) | Outside these conditions, routine foot care such as nail trimming is not covered (Medicare Benefit Policy Manual, Chapter 15, Section 290, referenced by the LCD). | data/raw/mcd/2026-09-21/current_lcd.zip:lcd.csv:L33941v23:indication | Please refer to CMS IOM Publication 100-02, Medicare Benefit Policy Manual , Chapter 15, Section 290 Foot Care for indications and limitations in coverage of routine foot care. | 1.0 | - | NOT IN SOURCE | LCD only points to Benefit Policy Manual Ch. 15 §290, which is not in our sources |
| 8 | POL-REHAB-001.c2 (flagged: composite (2 excerpts); low meaning similarity 0.716 < 0.754) | Treatment must follow a plan of care with specific goals, developed from an examination and evaluation. | data/raw/mcd/2026-09-21/current_lcd.zip:lcd.csv:L34428v93:indication | Impairments, activity limitations and disabilities are addressed by the examination, evaluation and development of a plan of care (POC) that may include implementation of therapeutic interventions tailored to the specific needs of the individual patient to achieve specific goals and outcomes. [...] PT is only covered when it is rendered under a written plan of treatment established by the physician, NPP or the qualified physical therapist, to address specific therapeutic goals for which modalities and procedures are planned out specifically in terms of type, frequency and duration. | 1.0 | - | MATCHES | less specific; evaluation exception is F1, certification is F2 |
| 9 | POL-SURG-004.c2 (flagged: composite (2 excerpts); low meaning similarity 0.716 < 0.754) | The record must document the patient's complaints of functional problems: vision blocked above or to the side, trouble reading because the upper field is lost, or looking through the eyelashes or seeing eyelid skin. | data/raw/mcd/2026-09-21/current_lcd.zip:lcd.csv:L33944v27:indication | Any procedure(s) involving blepharoplasty and billed to this contractor must be supported by documented patient complaints which justify functional surgery. This documentation must address the signs and symptoms commonly found in association with ptosis, pseudoptosis, blepharochalasis and/or dermatochalasis. [...] Significant interference with vision or superior or lateral visual field, (e.g., difficulty seeing objects approaching from the periphery); Difficulty reading due to superior visual field loss; or, Looking through the eyelashes or seeing the upper eyelid skin. | 1.0 | - | MATCHES | congenital/palsy exemption is F1 |
| 10 | POL-SURG-004.c4 (flagged: composite (2 excerpts); low meaning similarity 0.723 < 0.754) | Without documented functional impairment, eyelid surgery is considered cosmetic and is not covered. | data/raw/mcd/2026-09-21/current_lcd.zip:lcd.csv:L33944v27:indication | Medicare does not cover cosmetic surgery or expenses incurred in connection with such surgery. [...] Cosmetic Blepharoplasty: When blepharoplasty is performed to improve a patient’s appearance in the absence of any signs or symptoms of functional abnormalities, the procedure is considered cosmetic. | 1.0 | - | MATCHES | "eyelid surgery" is broader than "blepharoplasty"; reconstructive cases are F1 |
| 11 | POL-DX-001.c2 (sample of 17 composite-only flags: composite (2 excerpts)) | The study must be performed by a sleep program that meets the LCD's physician-direction and accreditation requirements. Home (out-of-center) testing is covered only under the LCD's out-of-center sleep testing conditions and supervision. | data/raw/mcd/2026-09-21/current_lcd.zip:lcd.csv:L35050v55:indication | All in facility sleep studies to be considered reasonable and necessary shall be performed in or under the direct supervision of a hospital sleep laboratory, a sleep clinic that is a direct extension of a physician’s office or by an Independent Diagnostic Testing Facility (IDTF). Each facility shall be supervised or under the directorship of a physician (MD/DO) trained in analyzing and interpreting the recordings who is Board Certified by the American Academy of Sleep Medicine (AASM), American Board of Medical Specialties in Sleep Medicine (ABMS) or board eligible for these credentials AND should be attended by an appropriately trained technologist. [...] In addition, the non-hospital based sleep clinic or IDTF shall be certified by the American Academy of Sleep Medicine, The Joint Commission (formerly known as JCAHO), or Accreditation Commission for Health Care, Inc. (ACHC). Sleep studies performed in the home shall only be covered under special circumstances listed below under "Out of Center Sleep Testing (OCST)." All home sleep studies, to be covered, must be under the supervision of the hospital based sleep lab, a sleep clinic that is a direct extension of the physician's office, an IDTF, or entity accredited by AASM as an OCST entity. | 1.0 | - | MATCHES | provider accreditation is not on claims; remove it from model criteria in v2 |
| 12 | POL-CAR-001.c1 (sample of 17 composite-only flags: composite (2 excerpts)) | A transthoracic echocardiogram is covered when there are clinical signs or symptoms of heart disease or heart dysfunction, such as suspected weakening of the heart muscle, cardiomyopathy or valve disease. High blood pressure alone, without signs or symptoms of heart disease, is not a covered reason. | data/raw/mcd/2026-09-21/current_lcd.zip:lcd.csv:L37379v42:indication | In individuals with signs and/or symptoms suggestive of ventricular dysfunction, the demonstration by TTE of normal systolic function and/or ventricular hypertrophy may suggest the presence of diastolic functional abnormalities. [...] When there are no signs or symptoms of heart disease, the use of TTE is not covered for hypertension (HTN). | 1.0 | - | UNSURE | high-blood-pressure exclusion matches; the coverage part needs L37379's indication list |
| 13 | POL-SURG-004.c3 (control (not flagged)) | Visual field testing must show a significant loss of upper vision (at least 12 degrees or 30 percent) that the surgery could correct. | data/raw/mcd/2026-09-21/current_lcd.zip:lcd.csv:L33944v27:indication | The visual fields should demonstrate a significant loss of superior visual field and potential correction of the visual field by the proposed procedures(s). A minimum 12 degree or 30 percent loss of upper field of vision with upper lid skin and/or upper lid margin in repose and elevated (by taping of the lid) to demonstrate potential correction by the proposed procedure or procedures is required. | 1.0 | - | MATCHES | control OK |
| 14 | POL-FOOT-001.c2 (control (not flagged)) | It is covered for patients on blood thinners when the record documents the significant risk of non-professional foot care. | data/raw/mcd/2026-09-21/current_lcd.zip:lcd.csv:L33941v23:indication | For patients requiring anticoagulation therapy, the provider must document in the medical record the significant risk and danger posed by the non-professional rendering routine foot care services. | 1.0 | - | MATCHES | control OK |

## Sitting 2: completeness findings (Part 2), about 34 minutes

Each finding is one proposed v2 change to one policy, with the LCD items behind it. Write ADD IN V2, NOT NEEDED or UNSURE. WRONG CRITERION findings come first, then the others by impact; the last 3 entries are controls (items a keyword rule classified as out of scope: write ADD IN V2 if one should change a policy).

Decision-dataset lines that use each WRONG CRITERION finding's criteria (status other than NOT_APPLICABLE in the gold target), report only:

| Finding | Criteria | Affected codes | Split | Lines using the criteria | On affected codes | Gold decisions (affected codes) | Criterion status (affected codes) |
|---|---|---|---|---|---|---|---|
| POL-CAR-002.F1 | POL-CAR-002.c2 | 93268 | train | 44 | 0 | - | - |
| POL-CAR-002.F1 | POL-CAR-002.c2 | 93268 | validation | 8 | 0 | - | - |
| POL-CAR-002.F1 | POL-CAR-002.c2 | 93268 | test | 4 | 0 | - | - |
| POL-DX-003.F1 | POL-DX-003.c1 | 95024 | train | 120 | 58 | APPROVE 32, DENY 13, PEND 13 | c1 MET 45, c1 NOT_DOCUMENTED 3, c1 NOT_MET 10 |
| POL-DX-003.F1 | POL-DX-003.c1 | 95024 | validation | 19 | 9 | APPROVE 5, DENY 2, PEND 2 | c1 MET 7, c1 NOT_MET 2 |
| POL-DX-003.F1 | POL-DX-003.c1 | 95024 | test | 12 | 6 | APPROVE 3, DENY 2, PEND 1 | c1 MET 3, c1 NOT_DOCUMENTED 1, c1 NOT_MET 2 |
| POL-REHAB-001.F1 | POL-REHAB-001.c2 | 97161 97162 | train | 228 | 45 | APPROVE 20, DENY 18, PEND 7 | c2 MET 32, c2 NOT_DOCUMENTED 7, c2 NOT_MET 6 |
| POL-REHAB-001.F1 | POL-REHAB-001.c2 | 97161 97162 | validation | 30 | 3 | APPROVE 1, DENY 1, PEND 1 | c2 MET 2, c2 NOT_DOCUMENTED 1 |
| POL-REHAB-001.F1 | POL-REHAB-001.c2 | 97161 97162 | test | 23 | 5 | APPROVE 2, DENY 3 | c2 MET 4, c2 NOT_MET 1 |
| POL-SURG-004.F1 | POL-SURG-004.c2 POL-SURG-004.c3 | 15822 15823 67904 | train | 162 | 162 | APPROVE 48, DENY 88, PEND 26 | c2 MET 76, c2 NOT_DOCUMENTED 21, c2 NOT_MET 65, c3 MET 77, c3 NOT_DOCUMENTED 23, c3 NOT_MET 62 |
| POL-SURG-004.F1 | POL-SURG-004.c2 POL-SURG-004.c3 | 15822 15823 67904 | validation | 28 | 28 | APPROVE 11, DENY 12, PEND 5 | c2 MET 18, c2 NOT_DOCUMENTED 4, c2 NOT_MET 6, c3 MET 16, c3 NOT_DOCUMENTED 5, c3 NOT_MET 7 |
| POL-SURG-004.F1 | POL-SURG-004.c2 POL-SURG-004.c3 | 15822 15823 67904 | test | 17 | 17 | APPROVE 3, DENY 14 | c2 MET 6, c2 NOT_DOCUMENTED 2, c2 NOT_MET 9, c3 MET 5, c3 NOT_DOCUMENTED 2, c3 NOT_MET 10 |

Refined: only the lines where the error could change the label, i.e. lines of the affected codes that use the criteria and also meet the condition below (gold decisions; report only). "R15 would not deny first" counts the lines whose diagnoses satisfy the billing article (the V1a check); the others are diagnosis mismatches that R15 (D-DX-1) denies before the SLM sees them. Example records show those lines first.

| Finding | Condition | Train | Validation | Test | R15 would not deny first (train / validation / test) | Scenario types | Example records |
|---|---|---|---|---|---|---|---|
| POL-CAR-002.F1 | none: every 30-day monitoring line that uses c2 counts | 0 | 0 | 0 | 0 / 0 / 0 | - | none |
| POL-DX-003.F1 | a food-allergy diagnosis on the intradermal test line (LCD L33261 items cov-058 and cov-080) | 0 | 0 | 0 | 0 / 0 / 0 | - | none |
| POL-REHAB-001.F1 | c2 (plan of care) NOT_MET or NOT_DOCUMENTED on the evaluation line | 13 (DENY 8, PEND 5) | 1 (PEND 1) | 1 (DENY 1) | 5 / 1 / 0 | deny_dx 8, pend_missing 6, rule_denied_line 1 | DEC-TR-00916, DEC-TR-00954 |
| POL-SURG-004.F1 | a congenital ptosis or palsy diagnosis (LCD L33944 items cov-030 and cov-038) | 0 | 0 | 0 | 0 / 0 / 0 | - | none |

Diagnosis codes used (ICD-10-CM, no dots):

- POL-DX-003.F1: J305 L272 T7801XA T7801XD T7801XS T7802XA T7802XD T7802XS T7805XA T7805XD T7805XS T7806XA T7806XD T7806XS T78070A T78070D T78070S T78071A T78071D T78071S T78080A T78080D T78080S T78081A T78081D T78081S T7809XA T7809XD T7809XS T78110A T78110D T78110S T78111A T78111D T78111S T78120A T78120D T78120S T78121A T78121D T78121S T7819XA T7819XD T7819XS Z91010 Z910111 Z910112 Z910121 Z910122 Z91013 Z91014 Z91018 (billing article A57531 v60 covered codes whose ICD-10-CM FY2027 description matches /\b(?:foods?|peanuts|milk|eggs?|shellfish|seafood|tree nuts|mammalian meats)\b/ but not /contact dermatitis|except food/)
- POL-SURG-004.F1: G510 H02151 H02152 H02154 H02155 H02156 H02159 H02231 H02232 H02234 H02235 H0223A H0223B H0223C H02431 H02432 H02433 Q100 (billing article A56439 v18 covered codes whose ICD-10-CM FY2027 description matches /congenital ptosis|palsy|paralytic/)

### 1. POL-SURG-004.F1: WRONG CRITERION (impact 208 lines; about 3 minutes)

**Proposed v2 change:** c2-c3: exempt the reconstructive conditions of the LCD's groups 2 and 3 (defects from disease, palsy, trauma or tumor surgery; congenital ptosis) from the functional-complaint and visual-field requirements.

**Our criterion now:** POL-SURG-004.c2: The record must document the patient's complaints of functional problems: vision blocked above or to the side, trouble reading because the upper field is lost, or looking through the eyelashes or seeing eyelid skin.

**Our criterion now:** POL-SURG-004.c3: Visual field testing must show a significant loss of upper vision (at least 12 degrees or 30 percent) that the surgery could correct.

Affected codes: 15822 15823 67904.

LCD L33944 items, word for word:

- `L33944-cov-016` (indication; Indications and Limitations:): The conditions listed under “2” and “3” below are generally considered reconstructive and not subject to the medical review of conditions listed under “1” which have the potential of being considered cosmetic
- `L33944-cov-030` (indication; Indications and Limitations: > To correct visual impairment caused by:): Repair of anatomical or pathological defects, including those caused by disease (including thyroid dysfunction and cranial nerve palsies), trauma, or tumor-ablative surgery. Surgery is performed to reconstruct the normal structure of the eyelid, using local or distant tissue. Reconstruction may be necessary to protect the eye and/or improve visual function. Conditions that may require blepharoplasty, ptosis repair, ectropion repair, or entropion repair are:
- `L33944-cov-038` (indication; Indications and Limitations: > To correct visual impairment caused by:): Congenital ptosis

Your verdict (ADD IN V2, NOT NEEDED or UNSURE): ADD IN V2

Notes: 0 v1 lines affected

### 2. POL-DX-003.F1: WRONG CRITERION (impact 73 lines; about 3 minutes)

**Proposed v2 change:** c1: remove foods from intradermal testing; the LCD covers foods by prick testing only and calls intradermal food testing not recommended.

**Our criterion now:** POL-DX-003.c1: Skin prick and intradermal tests are covered to evaluate IgE-mediated allergy to airborne allergens, foods, stinging-insect venom, certain drugs or chemicals, when the tests are correlated with the patient's history and examination.

Affected codes: 95024.

LCD L33261 items, word for word:

- `L33261-cov-058` (indication; Limitations): Intracutaneous (intradermal) tests for food sensitivity are not recommended because of numerous false-positive test findings and possible risks.
- `L33261-cov-080` (indication; Limitations > Tests to diagnose Food Allergy:): Intradermal testing to diagnose food allergy

Your verdict (ADD IN V2, NOT NEEDED or UNSURE): ADD IN V2

Notes: 0 v1 lines affected

### 3. POL-REHAB-001.F1: WRONG CRITERION (impact 60 lines; about 2 minutes)

**Proposed v2 change:** c2: an initial evaluation or re-evaluation can be covered even when it finds that therapy is not needed, so the plan-of-care requirement applies to treatment only.

**Our criterion now:** POL-REHAB-001.c2: Treatment must follow a plan of care with specific goals, developed from an examination and evaluation.

Affected codes: 97161 97162.

LCD L34428 items, word for word:

- `L34428-cov-112` (indication; Restorative/Rehabilitative therapy: > 1. The initial examination has the following components:): 3. Initial evaluations or re-evaluations may be determined reasonable and necessary even when the evaluation determines that skilled rehabilitation is not required if the patient's condition showed a need for an evaluation, or even if the goals established by the plan of treatment are not realized.

Your verdict (ADD IN V2, NOT NEEDED or UNSURE): ADD IN V2

Notes: 6 v1 labels affected

### 4. POL-CAR-002.F1: WRONG CRITERION (impact 42 lines; about 2 minutes)

**Proposed v2 change:** c2: limit the ejection fraction condition (40% or less) for heart attack survivors to 48-hour monitoring; the LCD's 30-day event monitoring list covers heart attack survivors without it.

**Our criterion now:** POL-CAR-002.c2: It is also covered to check the response to antiarrhythmic drugs, for heart attack survivors with an ejection fraction of 40% or less, for coronary artery disease with active symptoms, and to detect arrhythmias after an ablation procedure.

Affected codes: 93268.

LCD L34636 items, word for word:

- `L34636-cov-030` (indication; Indications for performing a Telephonic Transmission:): Evaluation of myocardial infarction (MI) survivors.

Your verdict (ADD IN V2, NOT NEEDED or UNSURE): ADD IN V2

Notes: also scope CAR-002.c1 by duration

### 5. POL-WOUND-001.F3: MISSING CRITERION (impact 358 lines; about 4 minutes)

**Proposed v2 change:** c3: expect measurable healing (smaller wound, granulation); allow 30 days to set up the plan; revise the plan when healing is not documented after 30 days; do not continue a type of care that shows no improvement.

LCD L38902 items, word for word:

- `L38902-cov-082` (indication; Limitations): Wound care may be of a palliative nature. Optimally, the overall goal of care is healing, and it would be neither reasonable nor medically necessary to continue a given type of wound care if evidence of wound improvement leading to healing of the wound as outlined in this LCD cannot be shown. However, if it is determined that the goal of care is not wound healing, which would lead ultimately to wound closure, the patient should be managed following appropriate palliative care standards. Wounds of some Medicare beneficiaries residing in Skilled Nursing Facilities (SNFs) and Nursing Facilities (NFs) may not close, heal, or be amenable to self-care in spite of optimal therapy. In those patients where wound closure, healing, or self-care is not a likely outcome, the goals of wound care may include prevention of hospitalization and improvement in quality of life. As such, due to severe underlying debility or other factors, the goal of wound care provided in these settings may be only to prevent progression of the wound by stabilizing the wound by:
- `L38902-cov-093` (indication; Limitations): A wound that has not progressed as expected after 30 days may require a new approach, which may include a physician reassessment of underlying infection, off-loading, biofilm, metabolic, nutritional, or vascular problems which may inhibit wound healing.
- `L38902-cov-112` (indication; Limitations > Medicare expects that with appropriate care:): Wound volume or surface dimension should decrease, or
- `L38902-cov-113` (indication; Limitations > Medicare expects that with appropriate care:): Wounds optimally will demonstrate granulation tissue.
- `L38902-cov-117` (indication; Limitations > Medicare expects that with appropriate care:): To acknowledge the difficulty in assembling this data in varied care settings, Medicare will allow 30 days from the initial patient encounter to organize and enter a comprehensive Plan of Care in the Medical Record. This should be maintained and updated as needed, and available upon request. Areas which are rural or underserved may benefit from evolving applications of telehealth to add expertise to the development of the Care Plan, or revision thereof, should the patient prove refractory.
- `L38902-cov-118` (indication; Limitations > Medicare expects that with appropriate care:): Failure to document expected healing after 30 days should necessitate a revision in the Plan of Care, to include the possibility of alternative treatment approaches, or transition to an alternative care setting, such as a multidisciplinary, and specialized, wound center. It is the expectation of Medicare that patients with chronic wounds may be demonstrating manifestations of underlying chronic illnesses, and that follow-up and coordination of care with other medical practitioners be fully reflected in the chart.

Your verdict (ADD IN V2, NOT NEEDED or UNSURE): ADD IN V2

Notes: firm rule only: no continuing care without improvement; revise the plan if healing is not documented after 30 days

### 6. POL-WOUND-001.F5: MISSING CRITERION (impact 358 lines; about 2 minutes)

**Proposed v2 change:** Add: care for cosmetic purposes is excluded.

LCD L38902 items, word for word:

- `L38902-cov-094` (indication; Limitations): Procedures performed for cosmetic reasons or to prepare tissues for cosmetic procedures are statutorily excluded from coverage by Medicare.

Your verdict (ADD IN V2, NOT NEEDED or UNSURE): NOT NEEDED

Notes: unrealistic in our claims; would mostly add NOT_APPLICABLE labels

### 7. POL-SURG-002.F1: MISSING CRITERION (impact 347 lines; about 4 minutes)

**Proposed v2 change:** c1: add the missing covered indications: synchronous cancer or polyps, inflammatory bowel disease when it changes management, intraoperative localization, colonic ischemia, Streptococcus bovis endocarditis, refractory new-onset constipation, anorectal adenomatous polyp, infectious colitis.

LCD L34005 items, word for word:

- `L34005-cov-014` (indication; Indications: > Evaluation of unexplained gastrointestinal bleeding:): Examination to evaluate entire colon for synchronous cancer or polyps in a patient with treatable cancer or polyp;
- `L34005-cov-022` (indication; Indications: > Evaluation of unexplained gastrointestinal bleeding:): Chronic inflammatory bowel disease of the colon if a more precise diagnosis or if a determination of the extent of activity of disease will influence immediate management;
- `L34005-cov-024` (indication; Indications: > Evaluation of unexplained gastrointestinal bleeding:): Intraoperative identification of the site of a lesion that can not be detected by palpation or gross inspection at surgery (e.g., polypectomy site or location of a bleeding source);
- `L34005-cov-025` (indication; Indications: > Evaluation of unexplained gastrointestinal bleeding:): Evaluation of acute colonic ischemia/ischemic bowel disease;
- `L34005-cov-026` (indication; Indications: > Evaluation of unexplained gastrointestinal bleeding:): Evaluation of patient with Streptococcus bovis endocarditis;
- `L34005-cov-032` (indication; Indications: > Evaluation of unexplained gastrointestinal bleeding:): Evaluation of unexplained, new onset constipation, refractory to medical therapy;
- `L34005-cov-033` (indication; Indications: > Evaluation of unexplained gastrointestinal bleeding:): Evaluation of anorectal polyp (adenomatous polyp only); or,
- `L34005-doc-001` (associated_info; (top)): Infectious colitis is an acceptable indication in its general form. However, specificity in ICD-10-CM coding is not needed but should be maintained in the patient's chart. The medical record should support the medical necessity and frequency of this treatment.

Your verdict (ADD IN V2, NOT NEEDED or UNSURE): ADD IN V2

Notes: criteria must not be narrower than the billing article's covered diagnoses

### 8. POL-SURG-002.F3: MISSING CRITERION (impact 347 lines; about 5 minutes)

**Proposed v2 change:** Add the LCD's limitations: chronic stable irritable bowel or abdominal pain, acute diarrhea, hemorrhoids, metastatic cancer of unknown primary without colonic symptoms, routine follow-up of inflammatory bowel disease, routine pre-operative examination, upper GI bleeding with an upper source, fulminant colitis, possible perforation, acute severe diverticulitis, diverticulosis.

LCD L34005 items, word for word:

- `L34005-cov-037` (indication; Limitations:): Chronic, stable, irritable bowel syndrome, or chronic abdominal pain, There are unusual exceptions in which colonoscopy may be done to rule out organic disease, especially if symptoms are unresponsive to therapy;
- `L34005-cov-038` (indication; Limitations:): Acute diarrhea;
- `L34005-cov-039` (indication; Limitations:): Hemorrhoids;
- `L34005-cov-040` (indication; Limitations:): Metastatic adenocarcinoma of unknown primary site in the absence of colonic symptoms when it will not influence management;
- `L34005-cov-041` (indication; Limitations:): Routine follow-up of inflammatory bowel disease (except for cancer surveillance in Crohn’s disease and chronic ulcerative colitis);
- `L34005-cov-042` (indication; Limitations:): Routine examination of the colon in patients about to undergo elective abdominal surgery for non-colonic disease;
- `L34005-cov-043` (indication; Limitations:): Upper gastrointestinal (GI) bleeding or melena with a demonstrated upper GI source; or,
- `L34005-cov-046` (indication; Limitations: > Colonoscopy/Sigmoidoscopy/Proctosigmoidoscopy is generally not covered for:): Fulminant colitis;
- `L34005-cov-047` (indication; Limitations: > Colonoscopy/Sigmoidoscopy/Proctosigmoidoscopy is generally not covered for:): Possible perforated viscus;
- `L34005-cov-048` (indication; Limitations: > Colonoscopy/Sigmoidoscopy/Proctosigmoidoscopy is generally not covered for:): Acute severe diverticulitis; or,
- `L34005-cov-049` (indication; Limitations: > Colonoscopy/Sigmoidoscopy/Proctosigmoidoscopy is generally not covered for:): Diverticulosis. This condition is not usually considered an indication for diagnostic or therapeutic colonoscopy, sigmoidoscopy or proctosigmoidoscopy, but may be reported on the claim when this condition is found to be the final diagnosis.

Your verdict (ADD IN V2, NOT NEEDED or UNSURE): ADD IN V2

Notes: only the limitations diagnosis codes cannot catch; skip those R15 denies

### 9. POL-REHAB-001.F2: MISSING CRITERION (impact 336 lines; about 3 minutes)

**Proposed v2 change:** c2: the patient is under the care of a physician or NPP, who certifies and recertifies the plan.

LCD L34428 items, word for word:

- `L34428-cov-018` (indication; Restorative/Rehabilitative therapy: > GENERAL PT GUIDELINES): 2. Covered PT must be furnished while the individual is or was under the care of a physician. Services must relate directly and specifically to a written plan of treatment regimen established by the physician or NPP after any necessary consultation with the qualified physical therapist, or by the physical therapist providing the services and must be reasonable and necessary to the treatment of the individual's illness or injury.
- `L34428-doc-007` (associated_info; Documentation Requirements > 4. Required documentation:): Certifications and recertifications
- `L34428-doc-019` (associated_info; Documentation Requirements > 5. Documentation should justify:): - the individual is under the care of a physician or NPP

Your verdict (ADD IN V2, NOT NEEDED or UNSURE): ADD IN V2

Notes: physician/NPP care and plan certification, for treatment lines only

### 10. Control: L33906-cov-028 (POL-PAIN-001)

Classified out of scope by a keyword rule: sedation or anesthesia; not a service in our scope.

- `L33906-cov-028` (indication; Limitations): Use of Moderate or Deep Sedation, General Anesthesia, or Monitored Anesthesia Care (MAC) is usually unnecessary or rarely indicated for these procedures and therefore, is not considered medically reasonable and necessary. Even in patients with a needle phobia and anxiety, typically oral anxiolytics suffice. In exceptional and unique cases, documentation must clearly establish the need for such sedation in the specific patient.

Your verdict (ADD IN V2, NOT NEEDED or UNSURE): NOT NEEDED

Notes: control OK

### 11. Control: L38902-doc-018 (POL-WOUND-001)

Classified out of scope by a keyword rule: sedation or anesthesia; not a service in our scope.

- `L38902-doc-018` (associated_info; Documentation Requirements): Type of anesthesia used, if and when used.

Your verdict (ADD IN V2, NOT NEEDED or UNSURE): NOT NEEDED

Notes: control OK

### 12. Control: L33261-cov-090 (POL-DX-003)

Classified out of scope by a keyword rule: provider qualification; claims do not carry it.

- `L33261-cov-090` (indication; Limitations > Tests to diagnose Food Allergy:): Services will be considered medically reasonable and necessary when all aspects of care are within the scope of practice of the provider’s professional licensure; and when all procedures are performed by appropriately trained providers in the appropriate setting.

Your verdict (ADD IN V2, NOT NEEDED or UNSURE): NOT NEEDED

Notes: control OK
