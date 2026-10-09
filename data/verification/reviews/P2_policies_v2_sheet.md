# Policies v2: source review sheet (checkpoint 1)

Two passes: pass 1 in a separate Claude chat (paste the whole sheet and ask for the three verdict tables at the end, filled); pass 2 by the reviewer, for every row whose pass 1 verdict is not MATCHES, AGREE or COMPLETE, plus 5 random MATCHES rows.

- **Who wrote what.** The v2 texts, the choice of excerpts, the types, the code lists and the notes were written by the same model (Claude, in the repository session); the two passes are the check.
- **Excerpts are copied word for word from data/raw by `scripts/verify/policies_v2_sources.py`, never typed.** LCD text: the CMS Medicare Coverage Database download (data/raw/mcd/2026-09-21/current_lcd.zip, lcd.csv, latest version of each LCD), with tags removed, entities decoded and whitespace collapsed, as in V1b. Block IDs are the V1b IDs: L<LCD>-cov-NNN is block NNN of the LCD's coverage field, L<LCD>-doc-NNN of its Associated Information field; headings and background blocks are marked. Manual text: Medicare Benefit Policy Manual, chapter 15, Rev. 13889 (data/raw/cms-manual/bp102c15/bp102c15.pdf), line breaks joined.
- **No AMA CPT text.** Codes are shown with the team's plain-language descriptions (data/curated/procedure_descriptions.csv), not CPT descriptors; the sheet was checked against the CPT descriptor texts of our codes before writing (0 found).
- In the excerpts, a backslash before `*` is Markdown escaping, not source text. 'under:' names the headings above an LCD block, as the V1b parser reads them.
- **Decisions** cited as `decision D-...` are team decisions recorded in DECISIONS.md, not sources: do not mark a row NOT IN SOURCE for what such a decision adds.
- Part A: 30 new criteria (each replaces a v1 criterion or is new); Part B: 38 criteria kept from v1 with their v1 ID and text; v1 criteria retired: 19. v2 total: 68. Part C: 3 indication groups, each with every covered indication its sources give.
- Automatic checks: every cited block and section found, every excerpt word for word in its source; rows with a number, duration or threshold that no excerpt contains: 0 (none).
- Estimated time: Part A about 3 minutes a row (90 minutes), Part B about 19 minutes, Part C about 12 minutes.

## How to judge

**Part A** (MATCHES, DIFFERENT MEANING, NOT IN SOURCE or UNSURE): does the v2 text say what its excerpts say, no more and no less, for its type and codes? A plain-language paraphrase is fine.

- MATCHES: the same meaning.
- DIFFERENT MEANING: the text adds, drops or changes a condition, number, list item or scope. Say which in the notes.
- NOT IN SOURCE: something in the text has no support in the excerpts (apart from cited decisions).
- UNSURE: say why.

**Part B** (AGREE, DISAGREE or UNSURE): is the type right for the text, and the code list and group?

**Part C** (COMPLETE, GAPS or UNSURE): for each indication group, is every covered indication its sources give for the policy's codes held by the criterion named, and is each reason to leave one out right?

**Types** (decisions D-ESI-6 and D-GEN-3) fix what the notes' silence means:

- requirement: must be satisfied; silent notes give NOT_DOCUMENTED.
- exclusion: describes a situation that is not covered; present gives NOT_MET, absent or silent gives NOT_APPLICABLE; never MET.
- conditional: applies only in the situation named with it; otherwise NOT_APPLICABLE; when it applies, it works as a requirement.
- Group: indication: alternative indications of one policy, which count only as a group (D-POL-3). Counting only the criteria that apply to the line's code, the group is satisfied when any member is MET; a member's NOT_MET or NOT_DOCUMENTED never decides the line on its own. Any NOT_MET outside the group gives DENY; otherwise an unsatisfied group gives PEND with 'no covered indication documented'; otherwise any NOT_DOCUMENTED outside the group gives PEND; otherwise APPROVE. Explicit non-coverage is in exclusion criteria, outside the group.
- Applies to: the criterion is shown only on lines billing these codes; without it, on every code of the policy.

## Codes of the policies

| Policy | Code | Plain-language description (team's, not the CPT descriptor) |
|---|---|---|
| POL-BH-001 | 96130 | Psychological test evaluation by a psychologist or physician, first hour |
| POL-BH-001 | 96131 | Psychological test evaluation by a psychologist or physician, each additional hour |
| POL-BH-001 | 96136 | Psychological or neuropsychological test administration by a professional, first 30 minutes |
| POL-CAR-001 | 93306 | Complete heart ultrasound through the chest wall, including blood-flow imaging |
| POL-CAR-001 | 93308 | Limited or follow-up heart ultrasound through the chest wall |
| POL-CAR-001 | 93350 | Heart ultrasound during an exercise or drug stress test |
| POL-CAR-002 | 93224 | Wearable heart rhythm recording for up to 48 hours, with analysis and report |
| POL-CAR-002 | 93241 | Wearable heart rhythm recording for 2 to 7 days, with analysis and report |
| POL-CAR-002 | 93268 | Patient-activated heart rhythm event recording for up to 30 days |
| POL-DX-001 | 95806 | Home sleep test measuring breathing effort and oxygen, unattended |
| POL-DX-001 | 95810 | Overnight lab sleep study with brain-wave monitoring, patient 6 or older |
| POL-DX-001 | 95811 | Overnight lab sleep study with CPAP titration, patient 6 or older |
| POL-DX-002 | 95907 | Nerve conduction testing, 1 to 2 nerves |
| POL-DX-002 | 95910 | Nerve conduction testing, 7 to 8 nerves |
| POL-DX-002 | 95886 | Needle muscle electrical testing of one limb, done with nerve conduction testing |
| POL-DX-003 | 95004 | Skin prick allergy tests, per allergen |
| POL-DX-003 | 95024 | Allergy tests injected just under the skin, per allergen |
| POL-DX-003 | 95044 | Skin patch allergy tests, per patch |
| POL-FOOT-001 | 11720 | Trimming and cleaning of thickened toenails, 1 to 5 nails |
| POL-FOOT-001 | 11721 | Trimming and cleaning of thickened toenails, 6 or more nails |
| POL-IMG-001 | 70450 | CT scan of the head without contrast |
| POL-IMG-001 | 70551 | MRI of the brain without contrast |
| POL-IMG-001 | 70553 | MRI of the brain before and after contrast |
| POL-IMG-001 | 72141 | MRI of the neck (cervical) spine without contrast |
| POL-IMG-002 | 76881 | Complete ultrasound of one arm or leg joint |
| POL-IMG-002 | 76882 | Limited ultrasound of an arm or leg joint or soft tissue area |
| POL-PAIN-001 | 62321 | Epidural steroid injection between the vertebrae, neck or upper back, with imaging guidance |
| POL-PAIN-001 | 62323 | Epidural steroid injection between the vertebrae, lower back, with imaging guidance |
| POL-PAIN-001 | 64483 | Epidural steroid injection beside the nerve root, lower back, first level |
| POL-PAIN-002 | 64490 | Facet joint nerve block injection, neck or upper back, first level |
| POL-PAIN-002 | 64493 | Facet joint nerve block injection, lower back, first level |
| POL-PAIN-002 | 64635 | Radiofrequency destruction of facet joint nerves, lower back, first joint |
| POL-REHAB-001 | 97110 | Therapeutic exercise to build strength, flexibility or endurance, each 15 minutes |
| POL-REHAB-001 | 97140 | Hands-on manual therapy such as joint mobilization, each 15 minutes |
| POL-REHAB-001 | 97161 | Physical therapy evaluation, low complexity |
| POL-REHAB-001 | 97162 | Physical therapy evaluation, moderate complexity |
| POL-REHAB-001 | 97530 | Functional movement activities to improve daily tasks, each 15 minutes |
| POL-SURG-001 | 66982 | Cataract removal with lens implant, complex case |
| POL-SURG-001 | 66984 | Cataract removal with lens implant, routine case |
| POL-SURG-002 | 45378 | Colonoscopy to look inside the colon, with no tissue removed |
| POL-SURG-002 | 45380 | Colonoscopy with tissue sample (biopsy) |
| POL-SURG-002 | 45385 | Colonoscopy with polyp removal using a wire snare |
| POL-SURG-003 | 36475 | Closing a leg vein from the inside with radiofrequency heat, first vein |
| POL-SURG-003 | 36478 | Closing a leg vein from the inside with laser heat, first vein |
| POL-SURG-003 | 37765 | Removing leg varicose veins through small punctures, 10 to 20 incisions |
| POL-SURG-004 | 15822 | Upper eyelid surgery (blepharoplasty) |
| POL-SURG-004 | 15823 | Upper eyelid surgery removing excess skin that droops over the eye |
| POL-SURG-004 | 67904 | Repair of drooping upper eyelid by tightening the lifting muscle |
| POL-WOUND-001 | 11042 | Removal of dead tissue from a wound down to the fat layer, first 20 square cm or less |
| POL-WOUND-001 | 97597 | Selective removal of dead tissue from an open wound, first 20 square cm or less |
| POL-WOUND-001 | 29581 | Applying a multi-layer compression wrap to the leg |

## Part A: new criteria (30 rows)

### A1. POL-CAR-001.c4 (replaces POL-CAR-001.c1)

- Decision: D-V2-1
- What changed: Replaces the first sentence of v1 c1; re-sourced to L37379's covered-indication list (its section headings A to Q).
- v1 text (POL-CAR-001.c1): A transthoracic echocardiogram is covered when there are clinical signs or symptoms of heart disease or heart dysfunction, such as suspected weakening of the heart muscle, cardiomyopathy or valve disease. High blood pressure alone, without signs or symptoms of heart disease, is not a covered reason.
- **v2 text:** A transthoracic echocardiogram is covered when the patient has signs or symptoms of, or is being evaluated for, one of these: weakened heart muscle or cardiomyopathy; hypertensive heart disease with clinical evidence of heart disease; heart attack or coronary insufficiency; exposure to drugs or treatments toxic to the heart; heart transplant or rejection monitoring; native heart valve disease; prosthetic heart valves; acute endocarditis; pericardial disease; aortic disease; congenital heart disease; suspected clots or embolic sources in the heart; heart tumors or masses; critical illness or trauma; arrhythmias or palpitations; fainting (syncope); or lung disease affecting the heart.
- Type: requirement. Applies to: 93306, 93308. Group: -.
- Source line: LCD L37379 v42 cov-006, cov-007, cov-009, cov-011, cov-012, cov-013, cov-016, cov-018, cov-020, cov-022, cov-024, cov-026, cov-028, cov-030, cov-032, cov-034, cov-036, cov-038, cov-040, cov-042.
- Automatic check, numbers in the v2 text that no excerpt contains: none

Excerpts, word for word:

> **L37379-cov-006** (item; under: The clinical use of contrast echocardiography (ECHO) is appropriate in selected patients to:): The plethora of structural and functional information provided by transthoracic echocardiogram (TTE) is unique among diagnostic testing modalities. The rapid and noninvasive acquisition of this information has contributed to exponential application, and to potential overutilization. This policy addresses the medically necessary and appropriate application of TTE.

> **L37379-cov-007** (heading): A. Ventricular Function and Cardiomyopathies

> **L37379-cov-009** (item; under: The clinical use of contrast echocardiography (ECHO) is appropriate in selected patients to: > A. Ventricular Function and Cardiomyopathies): Although TTE is used in the assessment of ventricular diastolic function, reproducible pathognomonic findings are not well established. In individuals with signs and/or symptoms suggestive of ventricular dysfunction, the demonstration by TTE of normal systolic function and/or ventricular hypertrophy may suggest the presence of diastolic functional abnormalities. Because the TTE findings suggesting diastolic dysfunction are less well established, when this application of TTE is the primary indication for the test, it will be expected to be performed by examiners recognized as experts in assessment and treatment of ventricular diastolic dysfunction.

> **L37379-cov-011** (heading): B. Hypertensive Cardiovascular (CV) Disease

> **L37379-cov-012** (item; under: The clinical use of contrast echocardiography (ECHO) is appropriate in selected patients to: > B. Hypertensive Cardiovascular (CV) Disease): When there are no signs or symptoms of heart disease, the use of TTE is not covered for hypertension (HTN). HTN with clinical evidence of heart disease is a Medicare-covered indication for TTE evaluation. Left ventricular hypertrophy (LVH) correlates with prognosis in hypertensive CV disease. Certain anti-hypertensive medications have been reported to stabilize and possibly contribute to the regression of LVH. The decision to commit certain individuals with insidiously progressive borderline HTN to long-term anti-hypertensive therapy may be determined by the presence of LVH. TTE may assist in the decision to treat through the formulation and analysis of a treatment program. Baseline TTE and serial annual assessments may be medically appropriate. More frequent assessments should have explicit contemporaneous medical necessity documentation.

> **L37379-cov-013** (heading): C. AMI and Coronary Insufficiency

> **L37379-cov-016** (heading): D. Exposure to Cardiotoxic Agents (chemotherapeutic and external)

> **L37379-cov-018** (heading): E. Cardiac Transplant and Rejection Monitoring

> **L37379-cov-020** (heading): F. Native Valvular Heart Disease

> **L37379-cov-022** (heading): G. Prosthetic Heart Valves (Mechanical & Bio-prostheses)

> **L37379-cov-024** (heading): H. Acute Endocarditis

> **L37379-cov-026** (heading): I. Pericardial Disease

> **L37379-cov-028** (heading): J. Aortic Pathology

> **L37379-cov-030** (heading): K. Congenital Heart Disease (CHD)

> **L37379-cov-032** (heading): L. Suspected Cardiac Thrombi and Embolic Sources

> **L37379-cov-034** (heading): M. Cardiac Tumors and Masses

> **L37379-cov-036** (heading): N. Critically Ill and Trauma Patients

> **L37379-cov-038** (heading): O. Arrhythmias and Palpitations

> **L37379-cov-040** (heading): P. Syncope

> **L37379-cov-042** (heading): Q. Pulmonary

### A2. POL-CAR-001.c5 (replaces POL-CAR-001.c1)

- Decision: D-V2-1
- What changed: The second sentence of v1 c1, same words; split out because a criterion has one type.
- v1 text (POL-CAR-001.c1): A transthoracic echocardiogram is covered when there are clinical signs or symptoms of heart disease or heart dysfunction, such as suspected weakening of the heart muscle, cardiomyopathy or valve disease. High blood pressure alone, without signs or symptoms of heart disease, is not a covered reason.
- **v2 text:** High blood pressure alone, without signs or symptoms of heart disease, is not a covered reason.
- Type: exclusion. Applies to: 93306, 93308. Group: -.
- Source line: LCD L37379 v42 cov-012.
- Automatic check, numbers in the v2 text that no excerpt contains: none

Excerpts, word for word:

> **L37379-cov-012** (item; under: The clinical use of contrast echocardiography (ECHO) is appropriate in selected patients to: > B. Hypertensive Cardiovascular (CV) Disease): When there are no signs or symptoms of heart disease, the use of TTE is not covered for hypertension (HTN). HTN with clinical evidence of heart disease is a Medicare-covered indication for TTE evaluation. Left ventricular hypertrophy (LVH) correlates with prognosis in hypertensive CV disease. Certain anti-hypertensive medications have been reported to stabilize and possibly contribute to the regression of LVH. The decision to commit certain individuals with insidiously progressive borderline HTN to long-term anti-hypertensive therapy may be determined by the presence of LVH. TTE may assist in the decision to treat through the formulation and analysis of a treatment program. Baseline TTE and serial annual assessments may be medically appropriate. More frequent assessments should have explicit contemporaneous medical necessity documentation.

### A3. POL-CAR-002.c4 (replaces POL-CAR-002.c1, POL-CAR-002.c2)

- Decision: D-V2-1, D-V2-2 CAR-002.F1, Q2
- What changed: v1 c1 and c2 merged and limited to recording up to 48 hours (the LCD's one list, '1 or more of the following'); the ejection fraction condition stays with 48-hour recording; adds cov-017 (other acute and subacute forms of ischemic heart disease), which v1 left out.
- v1 text (POL-CAR-002.c1): Heart rhythm monitoring is covered for symptoms suggesting an arrhythmia: palpitations, fainting or near fainting, dizziness, chest pain, transient ischemic episodes, shortness of breath, or a known arrhythmia.
- v1 text (POL-CAR-002.c2): It is also covered to check the response to antiarrhythmic drugs, for heart attack survivors with an ejection fraction of 40% or less, for coronary artery disease with active symptoms, and to detect arrhythmias after an ablation procedure.
- **v2 text:** Recording for up to 48 hours is covered for one or more of: palpitations, fainting or near fainting, dizziness, chest pain, transient ischemic episodes, shortness of breath, or a known arrhythmia; checking the response to antiarrhythmic drugs; heart attack survivors with an ejection fraction of 40% or less; coronary artery disease with active symptoms, to correlate chest pain with ST-segment changes; other acute and subacute forms of ischemic heart disease; or detecting arrhythmias after an ablation procedure.
- Type: requirement. Applies to: 93224. Group: -.
- Source line: LCD L34636 v38 cov-004, cov-005 to cov-018.
- Automatic check, numbers in the v2 text that no excerpt contains: none

Excerpts, word for word:

> **L34636-cov-004** (item; under: Medical Necessity:): The medical necessity indications listed in this policy must be present in order for these tests to be covered.

> **L34636-cov-005** (heading): Indications for external 48-hour ECG recording include 1 or more of the following:

> **L34636-cov-006** (heading): Symptoms:

> **L34636-cov-007** (item; under: Indications for external 48-hour ECG recording include 1 or more of the following: > Symptoms:): Arrhythmias

> **L34636-cov-008** (item; under: Indications for external 48-hour ECG recording include 1 or more of the following: > Symptoms:): Chest pain

> **L34636-cov-009** (item; under: Indications for external 48-hour ECG recording include 1 or more of the following: > Symptoms:): Syncope (lightheadedness) or near syncope

> **L34636-cov-010** (item; under: Indications for external 48-hour ECG recording include 1 or more of the following: > Symptoms:): Vertigo (dizziness)

> **L34636-cov-011** (item; under: Indications for external 48-hour ECG recording include 1 or more of the following: > Symptoms:): Palpitations

> **L34636-cov-012** (item; under: Indications for external 48-hour ECG recording include 1 or more of the following: > Symptoms:): Transient ischemic episodes

> **L34636-cov-013** (item; under: Indications for external 48-hour ECG recording include 1 or more of the following: > Symptoms:): Dyspnea (shortness of breath)

> **L34636-cov-014** (item; under: Indications for external 48-hour ECG recording include 1 or more of the following: > Symptoms:): Evaluation of the response to antiarrhythmic drug therapy.

> **L34636-cov-015** (item; under: Indications for external 48-hour ECG recording include 1 or more of the following: > Symptoms:): Evaluation of myocardial infarction (MI) survivors with an ejection fraction of 40% or less.

> **L34636-cov-016** (item; under: Indications for external 48-hour ECG recording include 1 or more of the following: > Symptoms:): Assessment of patients with coronary artery disease with active symptoms, to correlate chest pain with ST-segment changes.

> **L34636-cov-017** (item; under: Indications for external 48-hour ECG recording include 1 or more of the following: > Symptoms:): Other acute and subacute forms of ischemic heart disease.

> **L34636-cov-018** (item; under: Indications for external 48-hour ECG recording include 1 or more of the following: > Symptoms:): To detect arrhythmias post ablation procedures.

### A4. POL-CAR-002.c5 (replaces POL-CAR-002.c3)

- Decision: D-V2-1
- What changed: Split from v1 c3: recording or event monitoring for more than 48 hours up to 15 days.
- v1 text (POL-CAR-002.c3): Recording for more than 48 hours (up to 15 days) or 30-day event monitoring is covered when symptoms occur less often than every 48 hours, or to monitor the response to treatment for the listed conditions.
- **v2 text:** Recording for more than 48 hours, up to 15 days, is covered to look for symptom-free episodes when checking the response to treatment in a patient treated for a listed condition, or, with an event monitor, as an alternative to 48-hour monitoring when symptoms suggesting an arrhythmia (palpitations, dizziness, near fainting or fainting) occur less often than every 48 hours.
- Type: requirement. Applies to: 93241. Group: -.
- Source line: LCD L34636 v38 cov-004, cov-019.
- Automatic check, numbers in the v2 text that no excerpt contains: none

Excerpts, word for word:

> **L34636-cov-004** (item; under: Medical Necessity:): The medical necessity indications listed in this policy must be present in order for these tests to be covered.

> **L34636-cov-019** (item; under: Indications for external 48-hour ECG recording include 1 or more of the following: > Symptoms:): The use of external electrocardiographic recording for greater than 48 hours and up to 7 days or for greater than 7 days up to 15 days by continuous rhythm recording and storage, may be considered medically necessary in patients treated for reasons listed in the diagnosis list to monitor for asymptomatic episodes in order to evaluate treatment response. The use of external electrocardiographic event monitors for greater than 48 hours and up to 7 days or for greater than 7 days up to 15 days that are either patient-activated or auto-activated may be considered medically necessary as a diagnostic alternative to Holter monitoring in patients who experience infrequent symptoms (less frequently than every 48 hours) suggestive of cardiac arrhythmias (i.e., palpitations, dizziness, presyncope, or syncope). (Refer to current CPT codebook)

### A5. POL-CAR-002.c6 (replaces POL-CAR-002.c3)

- Decision: D-V2-1, D-V2-2 CAR-002.F1
- What changed: Split from v1 c3: 30-day monitoring, with the LCD's own list; heart attack survivors without the ejection fraction condition. cov-020's 'no other EKG monitoring codes' is enforced by the NCCI edits (R11), not by a criterion.
- v1 text (POL-CAR-002.c3): Recording for more than 48 hours (up to 15 days) or 30-day event monitoring is covered when symptoms occur less often than every 48 hours, or to monitor the response to treatment for the listed conditions.
- **v2 text:** 30-day event monitoring is covered for arrhythmias, chest pain, fainting or near fainting, dizziness, palpitations, transient ischemic episodes or shortness of breath; to start, revise or stop antiarrhythmic drug therapy; for heart attack survivors; for acute and subacute forms of ischemic heart disease; or for coronary artery disease with active symptoms, to correlate chest pain with ST-segment changes.
- Type: requirement. Applies to: 93268. Group: -.
- Source line: LCD L34636 v38 cov-001, cov-004, cov-020 to cov-032.
- Automatic check, numbers in the v2 text that no excerpt contains: none

Excerpts, word for word:

> **L34636-cov-001** (item; under: the top of the field): Cardiac Event Detection (CED) is a 30-day service for the purpose of documentation and diagnosis of paroxysmal or suspected arrhythmias.

> **L34636-cov-004** (item; under: Medical Necessity:): The medical necessity indications listed in this policy must be present in order for these tests to be covered.

> **L34636-cov-020** (item; under: Indications for external 48-hour ECG recording include 1 or more of the following: > Symptoms:): Long term 30-day monitoring: Telephonic Transmission of ECG involves 24 hour attended monitoring per 30-day period of time; no other EKG monitoring codes can be billed simultaneously with these codes.

> **L34636-cov-021** (heading): Indications for performing a Telephonic Transmission:

> **L34636-cov-022** (item; under: Indications for performing a Telephonic Transmission:): Arrhythmias

> **L34636-cov-023** (item; under: Indications for performing a Telephonic Transmission:): Chest pain

> **L34636-cov-024** (item; under: Indications for performing a Telephonic Transmission:): Syncope (lightheadedness) or near syncope

> **L34636-cov-025** (item; under: Indications for performing a Telephonic Transmission:): Vertigo (dizziness)

> **L34636-cov-026** (item; under: Indications for performing a Telephonic Transmission:): Palpitations

> **L34636-cov-027** (item; under: Indications for performing a Telephonic Transmission:): Transient ischemic episodes

> **L34636-cov-028** (item; under: Indications for performing a Telephonic Transmission:): Dyspnea (shortness of breath)

> **L34636-cov-029** (item; under: Indications for performing a Telephonic Transmission:): To initiate, revise or discontinue arrhythmia drug therapy.

> **L34636-cov-030** (item; under: Indications for performing a Telephonic Transmission:): Evaluation of myocardial infarction (MI) survivors.

> **L34636-cov-031** (item; under: Indications for performing a Telephonic Transmission:): Evaluation of acute and subacute forms of ischemic heart disease.

> **L34636-cov-032** (item; under: Indications for performing a Telephonic Transmission:): Assessment of patients with coronary artery disease with active symptoms, to correlate chest pain with ST-segment changes.

### A6. POL-DX-001.c4 (replaces POL-DX-001.c2)

- Decision: D-V2-1, Q6
- What changed: v1 c2 without the accreditation requirement, with the home-testing conditions of cov-109 and cov-110 spelled out. Typed exclusion, so silent notes give NOT_APPLICABLE. The other home-testing conditions (cov-107 and cov-108) are c5.
- v1 text (POL-DX-001.c2): The study must be performed by a sleep program that meets the LCD's physician-direction and accreditation requirements. Home (out-of-center) testing is covered only under the LCD's out-of-center sleep testing conditions and supervision.
- **v2 text:** Home (out-of-center) sleep testing is not covered for diagnosing obstructive sleep apnea when the patient has a significant comorbid medical condition or sleep disorder that may make the test inaccurate, such as moderate to severe lung disease, neuromuscular disease or congestive heart failure.
- Type: exclusion. Applies to: 95806. Group: -.
- Source line: LCD L35050 v55 cov-106, cov-109, cov-110.
- Automatic check, numbers in the v2 text that no excerpt contains: none

Excerpts, word for word:

> **L35050-cov-106** (item; under: Limitations > Polysomnography or sleep studies, and MSLT are not covered in the following situations:): Hospital based sleep, as well as non-hospital based sleep clinics shall be credentialed with the qualification listed in the Documentation Requirements below and shall meet the following criteria for OCST:

> **L35050-cov-109** (item; under: Limitations > Polysomnography or sleep studies, and MSLT are not covered in the following situations:): That no comorbidities exist that are contraindications to OCST testing

> **L35050-cov-110** (item; under: Limitations > Polysomnography or sleep studies, and MSLT are not covered in the following situations:): OCST is not appropriate for the diagnosis of OSA in patients with significant comorbid medical conditions or comorbid sleep disorders that may degrade the accuracy of PM, including, but not limited to, moderate to severe pulmonary disease, neuromuscular disease, or congestive heart failure.

### A7. POL-DX-001.c5 (new, no v1 predecessor)

- Decision: D-POL-4 (checkpoint 1 review)
- What changed: New: the home-testing conditions of cov-107 and cov-108. A requirement on the home-test code: the code list carries the condition, as for CAR-002 c4 to c6.
- **v2 text:** Home (out-of-center) sleep testing requires a high likelihood of moderate to severe sleep apnea, shown by the symptoms and the physical examination documented in the notes.
- Type: requirement. Applies to: 95806. Group: -.
- Source line: LCD L35050 v55 cov-106, cov-107, cov-108.
- Automatic check, numbers in the v2 text that no excerpt contains: none

Excerpts, word for word:

> **L35050-cov-106** (item; under: Limitations > Polysomnography or sleep studies, and MSLT are not covered in the following situations:): Hospital based sleep, as well as non-hospital based sleep clinics shall be credentialed with the qualification listed in the Documentation Requirements below and shall meet the following criteria for OCST:

> **L35050-cov-107** (item; under: Limitations > Polysomnography or sleep studies, and MSLT are not covered in the following situations:): The medical record must clearly indicate the patient has a high likelihood of having moderate to severe sleep apnea

> **L35050-cov-108** (item; under: Limitations > Polysomnography or sleep studies, and MSLT are not covered in the following situations:): This increased likelihood is evidenced by symptoms and physical examination documented in the note

### A8. POL-DX-002.c4 (new, no v1 predecessor)

- Decision: D-RULE-6, Q9
- What changed: New. Applies when a nerve conduction study is done without needle EMG; then needs documented carpal tunnel syndrome with a high pre-test probability (notes showing another cause: NOT_MET; silent notes: NOT_DOCUMENTED).
- **v2 text:** A nerve conduction study done without needle EMG is usually not medically necessary. It is covered alone only for carpal tunnel syndrome with a high pre-test probability, which the notes must document.
- Type: conditional (applies when: a nerve conduction study with no needle EMG on the claim). Applies to: 95907, 95910. Group: -.
- Source line: LCD L34594 v42 cov-037.
- Automatic check, numbers in the v2 text that no excerpt contains: none

Excerpts, word for word:

> **L34594-cov-037** (item; under: Results of the NCS reflect on the integrity and function of: > Nerve Conduction Studies): In most instances, both NCS and EMG are necessary to perform diagnostic testing. While a provider may choose to perform just an NCS, when performed alone it is usually considered not medically necessary. The only exception to this is a situation where a provider may consider it appropriate to perform an NCS without doing an EMG for the diagnosis of carpal tunnel syndrome with a high pre-test probability.

### A9. POL-DX-003.c4 (replaces POL-DX-003.c1)

- Decision: D-V2-2 DX-003.F1
- What changed: v1 c1 with foods removed from intradermal testing (the LCD lists foods for prick tests only).
- v1 text (POL-DX-003.c1): Skin prick and intradermal tests are covered to evaluate IgE-mediated allergy to airborne allergens, foods, stinging-insect venom, certain drugs or chemicals, when the tests are correlated with the patient's history and examination.
- **v2 text:** Skin prick tests are covered to evaluate IgE-mediated allergy to airborne allergens, foods, stinging-insect venom, certain drugs or chemicals; intradermal tests are covered for the same allergies except foods. The tests must be correlated with the patient's history and examination.
- Type: requirement. Applies to: 95004, 95024. Group: -.
- Source line: LCD L33261 v40 cov-007, cov-008, cov-009, cov-058.
- Automatic check, numbers in the v2 text that no excerpt contains: none

Excerpts, word for word:

> **L33261-cov-007** (item; under: Covered Indications > A. In Vivo Testing (skin tests):): In vivo testing (skin tests) include the performance and evaluation of selective cutaneous and mucous membrane tests in correlation with history, physician examination, and other observations of the patient. The tests are performed to determine body sensitivity and reaction to the antigen for the purpose of diagnosing the presence of allergic reaction to antigenic stimuli. Prick/puncture tests or intracutaneous tests are the preferred techniques for immunoglobulin E (IgE)-mediated hypersensitivity. 1

> **L33261-cov-008** (item; under: Covered Indications > A. In Vivo Testing (skin tests):): Percutaneous testing (scratch, puncture, prick), immediate type reaction, will be considered medically reasonable and necessary when used to evaluate IgE mediated hypersensitivity to inhalants, foods, Hymenoptera (stinging insects), chemicals, and specific drugs (e.g., penicillins and macromolecular agents). 1

> **L33261-cov-009** (item; under: Covered Indications > A. In Vivo Testing (skin tests):): Intracutaneous (intradermal) testing, immediate type reaction, will be considered medically reasonable and necessary when used to evaluate IgE mediated hypersensitivity to inhalants, Hymenoptera venoms (e.g., bee venom), drugs (e.g., penicillin, insulin, heparin, muscle relaxants) and/or chemicals. 1,2

> **L33261-cov-058** (item; under: Limitations): Intracutaneous (intradermal) tests for food sensitivity are not recommended because of numerous false-positive test findings and possible risks.

### A10. POL-DX-003.c5 (replaces POL-DX-003.c1)

- Decision: D-V2-2 DX-003.F1
- What changed: New exclusion: intradermal testing for food allergy.
- v1 text (POL-DX-003.c1): Skin prick and intradermal tests are covered to evaluate IgE-mediated allergy to airborne allergens, foods, stinging-insect venom, certain drugs or chemicals, when the tests are correlated with the patient's history and examination.
- **v2 text:** Intradermal testing to diagnose food allergy is not covered.
- Type: exclusion. Applies to: 95024. Group: -.
- Source line: LCD L33261 v40 cov-058, cov-080.
- Automatic check, numbers in the v2 text that no excerpt contains: none

Excerpts, word for word:

> **L33261-cov-058** (item; under: Limitations): Intracutaneous (intradermal) tests for food sensitivity are not recommended because of numerous false-positive test findings and possible risks.

> **L33261-cov-080** (item; under: Limitations > Tests to diagnose Food Allergy:): Intradermal testing to diagnose food allergy

### A11. POL-FOOT-001.c4 (new, no v1 predecessor)

- Decision: Q4 (new finding)
- What changed: New: manual section 290.C.3 (systemic conditions), with 290.D's list and its asterisk rule, 290.F's class findings, and 290.G's 'the mere statement of a diagnosis ... does not of itself indicate the severity'.
- **v2 text:** Foot care that would otherwise be routine is covered when a systemic condition, such as diabetes, arteriosclerosis obliterans, Buerger's disease, chronic thrombophlebitis or a peripheral neuropathy involving the feet, causes severe circulatory problems or areas of reduced sensation in the legs or feet, so that care by a non-professional would be hazardous. A diagnosis alone does not show the severity: the record must show it, for example by a non-traumatic amputation of the foot or part of it; two Class B findings (absent posterior tibial pulse, absent dorsalis pedis pulse, or advanced trophic changes, three of which are needed); or one Class B and two Class C findings (claudication, temperature changes such as cold feet, edema, paresthesias, burning). For diabetes, chronic thrombophlebitis and the neuropathies marked in the manual, the patient must be under the active care of a doctor of medicine or osteopathy who documents the condition.
- Type: conditional (applies when: a systemic condition). Applies to: every code of the policy. Group: indication.
- Source line: Medicare Benefit Policy Manual Ch. 15 §290.C.3, §290.D, §290.F, §290.G; LCD L33941 v23 cov-000.
- Automatic check, numbers in the v2 text that no excerpt contains: none

Excerpts, word for word:

> **Manual Ch. 15 §290.C.3** (page 261): 3. Presence of Systemic Condition The presence of a systemic condition such as metabolic, neurologic, or peripheral vascular disease may require scrupulous foot care by a professional that in the absence of such condition(s) would be considered routine (and, therefore, excluded from coverage). Accordingly, foot care that would otherwise be considered routine may be covered when systemic condition(s) result in severe circulatory embarrassment or areas of diminished sensation in the individual’s legs or feet. (See subsection A.) In these instances, certain foot care procedures that otherwise are considered routine (e.g., cutting or removing corns and calluses, or trimming, cutting, clipping, or debriding nails) may pose a hazard when performed by a nonprofessional person on patients with such systemic conditions. (See §290.G for procedural instructions.)

> **Manual Ch. 15 §290.D** (page 262): D. Systemic Conditions That Might Justify Coverage Although not intended as a comprehensive list, the following metabolic, neurologic, and peripheral vascular diseases (with synonyms in parentheses) most commonly represent the underlying conditions that might justify coverage for routine foot care. Diabetes mellitus \* Arteriosclerosis obliterans (A.S.O., arteriosclerosis of the extremities, occlusive peripheral arteriosclerosis) Buerger’s disease (thromboangiitis obliterans) Chronic thrombophlebitis \* Peripheral neuropathies involving the feet - Associated with malnutrition and vitamin deficiency \* • Malnutrition (general, pellagra) • Alcoholism • Malabsorption (celiac disease, tropical sprue) • Pernicious anemia Associated with carcinoma \* Associated with diabetes mellitus \* Associated with drugs and toxins \* Associated with multiple sclerosis \* Associated with uremia (chronic renal disease) \* Associated with traumatic injury Associated with leprosy or neurosyphilis Associated with hereditary disorders • Hereditary sensory radicular neuropathy • Angiokeratoma corporis diffusum (Fabry’s) • Amyloid neuropathy When the patient’s condition is one of those designated by an asterisk (\*), routine procedures are covered only if the patient is under the active care of a doctor of medicine or osteopathy who documents the condition.

> **Manual Ch. 15 §290.F** (pages 262-264): F. Presumption of Coverage In evaluating whether the routine services can be reimbursed, a presumption of coverage may be made where the evidence available discloses certain physical and/or clinical findings consistent with the diagnosis and indicative of severe peripheral involvement. For purposes of applying this presumption the following findings are pertinent: Class A Findings Nontraumatic amputation of foot or integral skeletal portion thereof. Class B Findings Absent posterior tibial pulse; Advanced trophic changes as: hair growth (decrease or absence) nail changes (thickening) pigmentary changes (discoloration) skin texture (thin, shiny) skin color (rubor or redness) (Three required); and Absent dorsalis pedis pulse. Class C Findings Claudication; Temperature changes (e.g., cold feet); Edema; Paresthesias (abnormal spontaneous sensations in the feet); and Burning. The presumption of coverage may be applied when the physician rendering the routine foot care has identified: 1. A Class A finding; 2. Two of the Class B findings; or 3. One Class B and two Class C findings. Cases evidencing findings falling short of these alternatives may involve podiatric treatment that may constitute covered care and should be reviewed by the intermediary’s medical staff and developed as necessary. For purposes of applying the coverage presumption where the routine services have been rendered by a podiatrist, the A/B MAC (B) may deem the active care requirement met if the claim or other evidence available discloses that the patient has seen an M.D. or D.O. for treatment and/or evaluation of the complicating disease process during the 6-month period prior to the rendition of the routine-type services. The A/B MAC (A) may also accept the podiatrist’s statement that the diagnosing and treating M.D. or D.O. also concurs with the podiatrist’s findings as to the severity of the peripheral involvement indicated. Services ordinarily considered routine might also be covered if they are performed as a necessary and integral part of otherwise covered services, such as diagnosis and treatment of diabetic ulcers, wounds, and infections.

> **Manual Ch. 15 §290.G** (pages 264-265): G. Application of Foot Care Exclusions to Physician’s Services The exclusion of foot care is determined by the nature of the service. Thus, payment for an excluded service should be denied whether performed by a podiatrist, osteopath, or a doctor of medicine, and without regard to the difficulty or complexity of the procedure. When an itemized bill shows both covered services and noncovered services not integrally related to the covered service, the portion of charges attributable to the noncovered services should be denied. (For example, if an itemized bill shows surgery for an ingrown toenail and also removal of calluses not necessary for the performance of toe surgery, any additional charge attributable to removal of the calluses should be denied.) In reviewing claims involving foot care, the A/B MAC (B) should be alert to the following exceptional situations: 1. Payment may be made for incidental noncovered services performed as a necessary and integral part of, and secondary to, a covered procedure. For example, if trimming of toenails is required for application of a cast to a fractured foot, the A/B MAC (B) need not allocate and deny a portion of the charge for the trimming of the nails. However, a separately itemized charge for such excluded service should be disallowed. When the primary procedure is covered the administration of anesthesia necessary for the performance of such procedure is also covered. 2. Payment may be made for initial diagnostic services performed in connection with a specific symptom or complaint if it seems likely that its treatment would be covered even though the resulting diagnosis may be one requiring only noncovered care. The name of the M.D. or D.O. who diagnosed the complicating condition must be submitted with the claim. In those cases, where active care is required, the approximate date the beneficiary was last seen by such physician must also be indicated. NOTE: Section 939 of P.L. 96-499 removed “warts” from the routine foot care exclusion effective July 1, 1981. Relatively few claims for routine-type care are anticipated considering the severity of conditions contemplated as the basis for this exception. Claims for this type of foot care should not be paid in the absence of convincing evidence that nonprofessional performance of the service would have been hazardous for the beneficiary because of an underlying systemic disease. The mere statement of a diagnosis such as those mentioned in §D above does not of itself indicate the severity of the condition. Where development is indicated to verify diagnosis and/or severity the A/B MAC (B) should follow existing claims processing practices, which may include review of A/B MAC (B)’s history and medical consultation as well as physician contacts. The rules in §290.F concerning presumption of coverage also apply. Codes and policies for routine foot care and supportive devices for the feet are not exclusively for the use of podiatrists. These codes must be used to report foot care services regardless of the specialty of the physician who furnishes the services. A/B MACs (B) must instruct physicians to use the most appropriate code available when billing for routine foot care.

> **L33941-cov-000** (item; under: the top of the field): Please refer to CMS IOM Publication 100-02, Medicare Benefit Policy Manual , Chapter 15, Section 290 Foot Care for indications and limitations in coverage of routine foot care.

### A12. POL-FOOT-001.c5 (new, no v1 predecessor)

- Decision: Q4 (new finding)
- What changed: New: manual section 290.C.4 (mycotic nails).
- **v2 text:** Without a systemic condition, treatment of mycotic (fungal) toenails is covered when the physician attending the mycotic condition documents clinical evidence of mycosis of the toenail and, for a patient who can walk, marked limitation of walking, pain, or secondary infection caused by the thickened, dystrophic nail plate; for a patient who cannot walk, pain or secondary infection caused by it.
- Type: conditional (applies when: mycotic toenails without a systemic condition). Applies to: every code of the policy. Group: indication.
- Source line: Medicare Benefit Policy Manual Ch. 15 §290.C.4; LCD L33941 v23 cov-000.
- Automatic check, numbers in the v2 text that no excerpt contains: none

Excerpts, word for word:

> **Manual Ch. 15 §290.C.4** (page 261): 4. Mycotic Nails In the absence of a systemic condition, treatment of mycotic nails may be covered. The treatment of mycotic nails for an ambulatory patient is covered only when the physician attending the patient’s mycotic condition documents that (1) there is clinical evidence of mycosis of the toenail, and (2) the patient has marked limitation of ambulation, pain, or secondary infection resulting from the thickening and dystrophy of the infected toenail plate. The treatment of mycotic nails for a nonambulatory patient is covered only when the physician attending the patient’s mycotic condition documents that (1) there is clinical evidence of mycosis of the toenail, and (2) the patient suffers from pain or secondary infection resulting from the thickening and dystrophy of the infected toenail plate. For the purpose of these requirements, documentation means any written information that is required by the A/B MAC (B) in order for services to be covered. Thus, the information submitted with claims must be substantiated by information found in the patient’s medical record. Any information, including that contained in a form letter, used for documentation purposes is subject to A/B MAC (B) verification in order to ensure that the information adequately justifies coverage of the treatment of mycotic nails.

> **L33941-cov-000** (item; under: the top of the field): Please refer to CMS IOM Publication 100-02, Medicare Benefit Policy Manual , Chapter 15, Section 290 Foot Care for indications and limitations in coverage of routine foot care.

### A13. POL-FOOT-001.c6 (replaces POL-FOOT-001.c3)

- Decision: D-V2-1, Q4
- What changed: Replaces v1 c3: cites manual section 290.B.2 (now in data/raw) and says 'except in the situations this policy covers', since c4 and c5 add exceptions.
- v1 text (POL-FOOT-001.c3): Outside these conditions, routine foot care such as nail trimming is not covered (Medicare Benefit Policy Manual, Chapter 15, Section 290, referenced by the LCD).
- **v2 text:** Except in the situations this policy covers, routine foot care, such as cutting or removing corns and calluses or trimming, cutting, clipping or debriding nails, is not covered.
- Type: exclusion. Applies to: every code of the policy. Group: -.
- Source line: Medicare Benefit Policy Manual Ch. 15 §290.B.2; LCD L33941 v23 cov-000.
- Automatic check, numbers in the v2 text that no excerpt contains: none

Excerpts, word for word:

> **Manual Ch. 15 §290.B.2** (page 260): 2. Routine Foot Care Except as provided above, routine foot care is excluded from coverage. Services that normally are considered routine and not covered by Medicare include the following: • The cutting or removal of corns and calluses; • The trimming, cutting, clipping, or debriding of nails; and • Other hygienic and preventive maintenance care, such as cleaning and soaking the feet, the use of skin creams to maintain skin tone of either ambulatory or bedfast patients, and any other service performed in the absence of localized illness, injury, or symptoms involving the foot.

> **L33941-cov-000** (item; under: the top of the field): Please refer to CMS IOM Publication 100-02, Medicare Benefit Policy Manual , Chapter 15, Section 290 Foot Care for indications and limitations in coverage of routine foot care.

### A14. POL-PAIN-001.c6 (replaces POL-PAIN-001.c2)

- Decision: D-ESI-2
- What changed: v1 c2 plus: the baseline score is a numeric score or a named scale.
- v1 text (POL-PAIN-001.c2): The pain must be severe enough to greatly affect quality of life or function, measured with an objective pain or function scale before treatment.
- **v2 text:** The pain must be severe enough to greatly affect quality of life or function, and a baseline pain or function score, a numeric score or a named scale, must be documented before treatment.
- Type: requirement. Applies to: every code of the policy. Group: -.
- Source line: LCD L33906 v75 cov-013, cov-023; decision D-ESI-2.
- Automatic check, numbers in the v2 text that no excerpt contains: none

Excerpts, word for word:

> **L33906-cov-013** (item; under: Covered Indications): Radiculopathy, radicular pain and/or neurogenic claudication is severe enough to greatly impact quality of life or function. An objective pain scale or functional assessment must be performed at baseline (prior to interventions). The same scale\* must be used at each follow-up for assessment of response.

> **L33906-cov-023** (item; under: Covered Indications): \*Note: The scales used to measure pain or disability must be documented in the medical record. Acceptable scales include, but are not limited to: Verbal rating scales, Numerical Rating Scale (NRS) and Visual Analog Scale (VAS) for pain assessment, and Pain Disability Assessment Scale (PDAS), Oswestry Disability Index (ODI), Oswestry Low Back Pain Disability Questionnaire (OLBPDQ), Quebec Back Pain Disability Scale (QBPDS), Roland Morris Pain Scale, Back Pain Functional Scale (BPFS), and the Patient-Reported Outcomes Measurement Information System (PROMIS) profile domains to assess function.

### A15. POL-PAIN-001.c7 (replaces POL-PAIN-001.c4)

- Decision: D-ESI-7
- What changed: v1 c4 plus: a code that includes imaging guidance counts as evidence of guidance, and contrast use (or the documented allergy or pregnancy) must be in the notes; caudal injections added to the one-level limit (cov-017). The level limits are also enforced by R18.
- v1 text (POL-PAIN-001.c4): Injections must be done under CT or fluoroscopic guidance with contrast, unless there is a documented contrast allergy or pregnancy. Interlaminar injections are limited to one level, and transforaminal injections to two levels in one spinal region.
- **v2 text:** Injections must be done under CT or fluoroscopic guidance with contrast; without contrast only when a contrast allergy or pregnancy is documented. A procedure code that includes imaging guidance counts as evidence of guidance, but contrast use, or the documented allergy or pregnancy, must be in the notes. Interlaminar and caudal injections are limited to one level, and transforaminal injections to two levels in one spinal region.
- Type: requirement. Applies to: every code of the policy. Group: -.
- Source line: LCD L33906 v75 cov-015, cov-016, cov-017, cov-020, cov-025; decision D-ESI-7.
- Automatic check, numbers in the v2 text that no excerpt contains: none

Excerpts, word for word:

> **L33906-cov-015** (item; under: Covered Indications): The ESIs must be performed under computed tomography (CT) or fluoroscopy image guidance with contrastunless the patient has a documented contrast allergy or pregnancy where ultrasound guidance without contrast may be considered.

> **L33906-cov-016** (item; under: Covered Indications): Transforaminal ESIs (TFESIs) involving a maximum of two (2) levels in one spinal region are considered medically reasonable and necessary. It is important to recognize that most conditions would not ordinarily require ESI at two (2) levels in one spinal region.

> **L33906-cov-017** (item; under: Covered Indications): Caudal ESIs and interlaminar ESIs (ILESIs) involving a maximum of one level are considered medically reasonable and necessary.

> **L33906-cov-020** (item; under: Covered Indications): An initial injection of contrast is required to confirm epidural placement, unless the patient has a contraindication to contrast. The subsequent ESI should include corticosteroids and may be combined with anesthetics or saline.

> **L33906-cov-025** (item; under: Limitations): Injections performed without image guidance or by ultrasound are not considered medically reasonable and necessary except in cases of documented contraindication to contrast media (e.g., allergy, pregnancy).

### A16. POL-PAIN-001.c8 (replaces POL-PAIN-001.c5)

- Decision: D-ESI-2, V1a open item
- What changed: v1 c5 plus the repeat after a poor first response (after 14 days, with a different approach, level or medication, the reason documented).
- v1 text (POL-PAIN-001.c5): A repeat injection requires documented improvement of at least 50% in pain lasting at least 3 months, or at least 50% improvement in function, compared with the baseline scale.
- **v2 text:** A repeat injection is covered when the first one gave at least 50% improvement in pain lasting at least 3 months, or at least 50% improvement in function, on the same scale as the baseline. If the first injection did not work well, a repeat after at least 14 days is covered with a different approach, level or medication, when the reason for it is documented.
- Type: conditional (applies when: a repeat injection). Applies to: every code of the policy. Group: -.
- Source line: LCD L33906 v75 cov-019, cov-039; decision D-ESI-2.
- Automatic check, numbers in the v2 text that no excerpt contains: none

Excerpts, word for word:

> **L33906-cov-019** (item; under: Covered Indications): Repeat ESI when the first injection directly and significantly provided improvement of the condition being treated may be considered medically reasonable and necessary when the medical record documents a minimum of consistent 50% improvement in pain for at least three (3) months or at least 50% consistent improvement in the ability to perform previously painful movements and ADLs as compared to baseline measurement using the same scale. If a patient fails to respond well to the initial ESI, a repeat ESI after 14 days can be performed using a different approach, level and/or medication, if appropriate, with the rationale and medical necessity for the second ESI documented in the medical record.

> **L33906-cov-039** (item; under: Limitations): The ESI provides at least 50% sustained improvement of pain and/or 50% objective improvement in function (using same scale as baseline).

### A17. POL-PAIN-001.c9 (new, no v1 predecessor)

- Decision: D-ESI-4, Q5
- What changed: New exclusion with every condition cov-029 lists.
- **v2 text:** Injections are not covered to treat non-specific low back pain, axial spine pain (pain that does not radiate from a nerve root), complex regional pain syndrome, widespread diffuse pain, pain from neuropathy of other causes, or cervicogenic headaches.
- Type: exclusion. Applies to: every code of the policy. Group: -.
- Source line: LCD L33906 v75 cov-029; decision D-ESI-4.
- Automatic check, numbers in the v2 text that no excerpt contains: none

Excerpts, word for word:

> **L33906-cov-029** (item; under: Limitations): ESIs to treat non-specific low back pain (LBP), axial spine pain, complex regional pain syndrome, widespread diffuse pain, pain from neuropathy from other causes, or cervicogenic headaches are considered investigational and therefore are not considered medically reasonable and necessary.

### A18. POL-PAIN-002.c5 (replaces POL-PAIN-002.c4)

- Decision: D-V2-1
- What changed: v1 c4 plus the LCD's documented-exception clause; shown on the diagnostic injection codes only.
- v1 text (POL-PAIN-002.c4): Diagnostic facet procedures are done with the intent of proceeding to radiofrequency ablation at that level if they succeed. A second, confirming diagnostic procedure at the same level must be at least 2 weeks after the first.
- **v2 text:** Diagnostic facet procedures are done with the intent of proceeding to radiofrequency ablation at that level if they succeed. A second, confirming diagnostic procedure at the same level must be at least 2 weeks after the first, unless the record clearly documents the clinical circumstances that need an exception.
- Type: requirement. Applies to: 64490, 64493. Group: -.
- Source line: LCD L33930 v49 cov-023, cov-024.
- Automatic check, numbers in the v2 text that no excerpt contains: none

Excerpts, word for word:

> **L33930-cov-023** (item; under: Covered Indications > A. Diagnostic Facet Joint Injection Procedures (IA or MBB):): Diagnostic procedures should be performed with the intent that if successful, RFA procedure would be considered the primary treatment goal at the diagnosed level(s).

> **L33930-cov-024** (item; under: Covered Indications > A. Diagnostic Facet Joint Injection Procedures (IA or MBB):): A second diagnostic facet procedure is considered medically reasonable and necessary to confirm validity of the initial diagnostic facet procedure when administered at the same level. The second diagnostic procedure may only be performed a minimum of 2 weeks after the initial diagnostic procedure.Clinical circumstances that necessitate an exception to the 2 week duration may be considered on an individual basis and must be clearly documented in the medical record.

### A19. POL-REHAB-001.c4 (replaces POL-REHAB-001.c2)

- Decision: D-V2-2 REHAB-001.F1
- What changed: v1 c2, shown on treatment codes only: an evaluation needs no plan of care.
- v1 text (POL-REHAB-001.c2): Treatment must follow a plan of care with specific goals, developed from an examination and evaluation.
- **v2 text:** Treatment, as opposed to an initial evaluation or re-evaluation, must follow a written plan of care with specific goals, developed from an examination and evaluation. An evaluation can be covered even when it finds that therapy is not needed.
- Type: requirement. Applies to: 97110, 97140, 97530. Group: -.
- Source line: LCD L34428 v93 cov-001, cov-020, cov-112.
- Automatic check, numbers in the v2 text that no excerpt contains: none

Excerpts, word for word:

> **L34428-cov-001** (item; under: the top of the field): PT services are part of a constellation of rehabilitative services designed to improve or restore physical functioning, as well as, to prevent injury, impairments, activity limitations, participation restrictions and disability following disease, injury or loss of a body part. Impairments, activity limitations and disabilities are addressed by the examination, evaluation and development of a plan of care (POC) that may include implementation of therapeutic interventions tailored to the specific needs of the individual patient to achieve specific goals and outcomes. The specific interventions that may be utilized are therapeutic exercises to strengthen muscles, maintain or restore motion, integumentary repair and protection techniques, physical agents and mechanical modalities, such as heat, cold, electrotherapeutic modalities, ultrasound (US) and hydrotherapy, manual therapy and functional training or retraining an individual to perform the activities of daily living (ADLs).

> **L34428-cov-020** (item; under: Restorative/Rehabilitative therapy: > GENERAL PT GUIDELINES): 4. PT is only covered when it is rendered under a written plan of treatment established by the physician, NPP or the qualified physical therapist, to address specific therapeutic goals for which modalities and procedures are planned out specifically in terms of type, frequency and duration. The physician or NPP should periodically review the plan of treatment.

> **L34428-cov-112** (item; under: Restorative/Rehabilitative therapy: > 1. The initial examination has the following components:): 3. Initial evaluations or re-evaluations may be determined reasonable and necessary even when the evaluation determines that skilled rehabilitation is not required if the patient's condition showed a need for an evaluation, or even if the goals established by the plan of treatment are not realized.

### A20. POL-REHAB-001.c5 (replaces POL-REHAB-001.c2)

- Decision: D-V2-2 REHAB-001.F2
- What changed: New: physician or NPP care and plan certification, treatment codes only.
- v1 text (POL-REHAB-001.c2): Treatment must follow a plan of care with specific goals, developed from an examination and evaluation.
- **v2 text:** The patient must be under the care of a physician or NPP, who certifies and recertifies the plan of care.
- Type: requirement. Applies to: 97110, 97140, 97530. Group: -.
- Source line: LCD L34428 v93 cov-018, doc-007, doc-019.
- Automatic check, numbers in the v2 text that no excerpt contains: none

Excerpts, word for word:

> **L34428-cov-018** (item; under: Restorative/Rehabilitative therapy: > GENERAL PT GUIDELINES): 2. Covered PT must be furnished while the individual is or was under the care of a physician. Services must relate directly and specifically to a written plan of treatment regimen established by the physician or NPP after any necessary consultation with the qualified physical therapist, or by the physical therapist providing the services and must be reasonable and necessary to the treatment of the individual's illness or injury.

> **L34428-doc-007** (item; under: Documentation Requirements > 4. Required documentation:): Certifications and recertifications

> **L34428-doc-019** (item; under: Documentation Requirements > 5. Documentation should justify:): - the individual is under the care of a physician or NPP

### A21. POL-SURG-001.c4 (new, no v1 predecessor)

- Decision: D-POL-4 (checkpoint 1 review)
- What changed: New: L33558 cov-008, a covered indication no v1 criterion held (found while listing the indication group's sources). A separate criterion, so c3 keeps its ID.
- **v2 text:** It is also covered when another procedure or treatment, done now or planned (such as pars plana vitrectomy, iridocyclectomy, a procedure for eye trauma, or external beam radiation), makes faster cataract development highly probable.
- Type: conditional (applies when: another procedure or treatment likely to speed up the cataract). Applies to: every code of the policy. Group: indication.
- Source line: LCD L33558 v33 cov-003, cov-008.
- Automatic check, numbers in the v2 text that no excerpt contains: none

Excerpts, word for word:

> **L33558-cov-003** (item; under: Indications and Limitations:): Lens extraction is considered medically necessary and therefore covered by Medicare when one (or more) of the following conditions or circumstances exists:

> **L33558-cov-008** (item; under: Indications and Limitations:): High probability of accelerating cataract development as a result of a concomitant or subsequent procedure (e.g., pars plana vitrectomy, iridocyclectomy, procedure for ocular trauma) and treatments such as external beam irradiation

### A22. POL-SURG-002.c4 (replaces POL-SURG-002.c1)

- Decision: D-V2-2 SURG-002.F1
- What changed: v1 c1 plus the covered indications it missed (cov-014, cov-022, cov-024 to cov-026, cov-032, cov-033, doc-001). The LCD's therapeutic indications are c7.
- v1 text (POL-SURG-002.c1): Colonoscopy to investigate symptoms is covered for an imaging abnormality likely to be significant; unexplained bleeding (blood in the stool not from a rectal source, black tarry stool, or a positive stool blood test); unexplained iron-deficiency anemia; or significant unexplained diarrhea with other findings such as weight loss.
- **v2 text:** Colonoscopy to investigate symptoms or findings is covered for: an imaging abnormality likely to be significant; unexplained bleeding (blood in the stool not from a rectal source, black tarry stool, or a positive stool blood test); unexplained iron-deficiency anemia; significant unexplained diarrhea with other findings such as weight loss; examining the whole colon for synchronous cancer or polyps in a patient with a treatable cancer or polyp; chronic inflammatory bowel disease when a more precise diagnosis or the extent of activity will change immediate management; locating during surgery a lesion that cannot be found by touch or sight; acute colonic ischemia; Streptococcus bovis endocarditis; unexplained new-onset constipation that does not respond to medical treatment; an anorectal adenomatous polyp; or infectious colitis.
- Type: conditional (applies when: symptoms or findings to investigate). Applies to: every code of the policy. Group: indication.
- Source line: LCD L34005 v34 cov-007, cov-009 to cov-012, cov-014, cov-022 to cov-026, cov-032, cov-033, doc-001.
- Automatic check, numbers in the v2 text that no excerpt contains: none

Excerpts, word for word:

> **L34005-cov-007** (item; under: Indications: > The following are Medicare-covered indications:): Evaluation of an abnormality discovered on barium enema and/or other imaging technique that is likely to be clinically significant, such as a filling defect or stricture or an inadequate examination;

> **L34005-cov-009** (item; under: Indications: > Evaluation of unexplained gastrointestinal bleeding:): Hematochezia not thought to be from rectum or perianal source

> **L34005-cov-010** (item; under: Indications: > Evaluation of unexplained gastrointestinal bleeding:): Melena of unknown origin;

> **L34005-cov-011** (item; under: Indications: > Evaluation of unexplained gastrointestinal bleeding:): Presence of fecal occult blood

> **L34005-cov-012** (item; under: Indications: > Evaluation of unexplained gastrointestinal bleeding:): Unexplained iron deficiency anemia;

> **L34005-cov-014** (item; under: Indications: > Evaluation of unexplained gastrointestinal bleeding:): Examination to evaluate entire colon for synchronous cancer or polyps in a patient with treatable cancer or polyp;

> **L34005-cov-022** (item; under: Indications: > Evaluation of unexplained gastrointestinal bleeding:): Chronic inflammatory bowel disease of the colon if a more precise diagnosis or if a determination of the extent of activity of disease will influence immediate management;

> **L34005-cov-023** (item; under: Indications: > Evaluation of unexplained gastrointestinal bleeding:): Clinically significant diarrhea of unexplained origin with additional findings (e.g., with weight loss or negative stool cultures persisting for more than 3 weeks;

> **L34005-cov-024** (item; under: Indications: > Evaluation of unexplained gastrointestinal bleeding:): Intraoperative identification of the site of a lesion that can not be detected by palpation or gross inspection at surgery (e.g., polypectomy site or location of a bleeding source);

> **L34005-cov-025** (item; under: Indications: > Evaluation of unexplained gastrointestinal bleeding:): Evaluation of acute colonic ischemia/ischemic bowel disease;

> **L34005-cov-026** (item; under: Indications: > Evaluation of unexplained gastrointestinal bleeding:): Evaluation of patient with Streptococcus bovis endocarditis;

> **L34005-cov-032** (item; under: Indications: > Evaluation of unexplained gastrointestinal bleeding:): Evaluation of unexplained, new onset constipation, refractory to medical therapy;

> **L34005-cov-033** (item; under: Indications: > Evaluation of unexplained gastrointestinal bleeding:): Evaluation of anorectal polyp (adenomatous polyp only); or,

> **L34005-doc-001** (item; under: the top of the field): Infectious colitis is an acceptable indication in its general form. However, specificity in ICD-10-CM coding is not needed but should be maintained in the patient's chart. The medical record should support the medical necessity and frequency of this treatment.

### A23. POL-SURG-002.c5 (replaces POL-SURG-002.c2)

- Decision: D-V2-1
- What changed: v1 c2 plus the large sessile adenoma definition (more than 2 cm) and the rectosigmoid exclusion; no intervals (D-RULE-1).
- v1 text (POL-SURG-002.c2): Surveillance is covered for a history of colorectal cancer or polyps, follow-up one year after colorectal cancer surgery, follow-up after removal of a large polyp, and inflammatory bowel disease surveillance (pancolitis for more than 7 years, or left-sided colitis for more than 15 years).
- **v2 text:** Surveillance is covered for a history of colorectal cancer or polyps, follow-up one year after colorectal cancer surgery, follow-up after removal of a large sessile adenoma (more than 2 cm in its greatest dimension), and inflammatory bowel disease surveillance (pancolitis for more than 7 years, or left-sided colitis for more than 15 years; not for disease limited to the rectosigmoid).
- Type: conditional (applies when: surveillance). Applies to: every code of the policy. Group: indication.
- Source line: LCD L34005 v34 cov-013, cov-015, cov-017, cov-019 to cov-021.
- Automatic check, numbers in the v2 text that no excerpt contains: none

Excerpts, word for word:

> **L34005-cov-013** (item; under: Indications: > Evaluation of unexplained gastrointestinal bleeding:): Surveillance of colonic neoplasia. When the patient has a history of colorectal cancer or polyps and is being followed for this indication;

> **L34005-cov-015** (item; under: Indications: > Evaluation of unexplained gastrointestinal bleeding:): Follow-up in one year after surgery for treatment of colorectal cancer;

> **L34005-cov-017** (item; under: Indications: > Evaluation of unexplained gastrointestinal bleeding:): Follow-up for removal of neoplastic polyp (follow-up at least three to six months to verify removal of large sessile adenoma [i.e., greater than 2 cm in greatest dimension] after colonoscopic removal);

> **L34005-cov-019** (item; under: Indications: > Evaluation of unexplained gastrointestinal bleeding:): In patients with Crohn’s colitis and chronic ulcerative colitis: colonoscopy every one or two years with multiple biopsies for detection of cancer and dysplasia in patients with:

> **L34005-cov-020** (item; under: Indications: > Evaluation of unexplained gastrointestinal bleeding:): Pancolitis of greater than seven years duration; or,

> **L34005-cov-021** (item; under: Indications: > Evaluation of unexplained gastrointestinal bleeding:): Left-sided colitis of over 15 years duration (no surveillance needed for disease limited to rectosigmoid);

### A24. POL-SURG-002.c6 (new, no v1 predecessor)

- Decision: D-V2-2 SURG-002.F3
- What changed: New exclusion: the LCD limitations that R15 cannot catch, including cov-044 (bright red bleeding with an anorectal source; checkpoint 1 review). Left out: cov-040 (R15 denies it: billing article A56456 covers none of its diagnosis codes).
- **v2 text:** Colonoscopy is generally not covered, unless the record documents why it is needed, for: chronic, stable irritable bowel syndrome or chronic abdominal pain (it may be done to rule out organic disease, especially when symptoms do not respond to therapy); acute diarrhea; hemorrhoids; routine follow-up of inflammatory bowel disease (cancer surveillance in Crohn's disease or chronic ulcerative colitis excepted); routine examination before elective abdominal surgery for a non-colonic disease; upper GI bleeding or black tarry stool with a demonstrated upper GI source; bright red rectal bleeding with a convincing anorectal source on sigmoidoscopy and no other symptoms suggesting a source higher up; fulminant colitis; possible perforation; acute severe diverticulitis; or diverticulosis as the reason for the test (it may still be reported when it is the final diagnosis).
- Type: exclusion. Applies to: every code of the policy. Group: -.
- Source line: LCD L34005 v34 cov-036 to cov-039, cov-041 to cov-049.
- Automatic check, numbers in the v2 text that no excerpt contains: none

Excerpts, word for word:

> **L34005-cov-036** (item; under: Limitations:): Endoscopy is generally not covered for treating the following, and records must have additional documentation indicating the medical necessity of the procedure for review as needed:

> **L34005-cov-037** (item; under: Limitations:): Chronic, stable, irritable bowel syndrome, or chronic abdominal pain, There are unusual exceptions in which colonoscopy may be done to rule out organic disease, especially if symptoms are unresponsive to therapy;

> **L34005-cov-038** (item; under: Limitations:): Acute diarrhea;

> **L34005-cov-039** (item; under: Limitations:): Hemorrhoids;

> **L34005-cov-041** (item; under: Limitations:): Routine follow-up of inflammatory bowel disease (except for cancer surveillance in Crohn’s disease and chronic ulcerative colitis);

> **L34005-cov-042** (item; under: Limitations:): Routine examination of the colon in patients about to undergo elective abdominal surgery for non-colonic disease;

> **L34005-cov-043** (item; under: Limitations:): Upper gastrointestinal (GI) bleeding or melena with a demonstrated upper GI source; or,

> **L34005-cov-044** (item; under: Limitations:): Bright red rectal bleeding with a convincing anorectal source on sigmoidoscopy and no other symptoms suggestive of a more proximal bleeding source;

> **L34005-cov-045** (heading): Colonoscopy/Sigmoidoscopy/Proctosigmoidoscopy is generally not covered for:

> **L34005-cov-046** (item; under: Limitations: > Colonoscopy/Sigmoidoscopy/Proctosigmoidoscopy is generally not covered for:): Fulminant colitis;

> **L34005-cov-047** (item; under: Limitations: > Colonoscopy/Sigmoidoscopy/Proctosigmoidoscopy is generally not covered for:): Possible perforated viscus;

> **L34005-cov-048** (item; under: Limitations: > Colonoscopy/Sigmoidoscopy/Proctosigmoidoscopy is generally not covered for:): Acute severe diverticulitis; or,

> **L34005-cov-049** (item; under: Limitations: > Colonoscopy/Sigmoidoscopy/Proctosigmoidoscopy is generally not covered for:): Diverticulosis. This condition is not usually considered an indication for diagnostic or therapeutic colonoscopy, sigmoidoscopy or proctosigmoidoscopy, but may be reported on the claim when this condition is found to be the final diagnosis.

### A25. POL-SURG-002.c7 (new, no v1 predecessor)

- Decision: D-POL-4 (checkpoint 1 review)
- What changed: New: the LCD's therapeutic indications (cov-027 to cov-031, cov-034), in the indication group, on the biopsy and polyp-removal codes, so those lines are not pended for want of an indication.
- **v2 text:** Colonoscopy is also covered to treat: bleeding from lesions such as vascular anomalies, ulceration or tumors; a foreign body (removal); colonic polyps (excision); pseudo-obstruction of the colon (Ogilvie's syndrome, decompression); sigmoid volvulus or stricture; or narrowing or bleeding tumors, as palliative treatment (for example laser, electrocoagulation or stenting).
- Type: conditional (applies when: treatment during the colonoscopy). Applies to: 45380, 45385. Group: indication.
- Source line: LCD L34005 v34 cov-006, cov-027 to cov-031, cov-034.
- Automatic check, numbers in the v2 text that no excerpt contains: none

Excerpts, word for word:

> **L34005-cov-006** (heading): The following are Medicare-covered indications:

> **L34005-cov-027** (item; under: Indications: > Evaluation of unexplained gastrointestinal bleeding:): Treatment of bleeding from such lesions as vascular anomalies, ulceration and neoplasia;

> **L34005-cov-028** (item; under: Indications: > Evaluation of unexplained gastrointestinal bleeding:): Removal of foreign body;

> **L34005-cov-029** (item; under: Indications: > Evaluation of unexplained gastrointestinal bleeding:): Excision of colonic polyps;

> **L34005-cov-030** (item; under: Indications: > Evaluation of unexplained gastrointestinal bleeding:): Decompression of pseudo-obstruction of the colon (Olgilvie’s syndrome);

> **L34005-cov-031** (item; under: Indications: > Evaluation of unexplained gastrointestinal bleeding:): Treatment of sigmoid volvulus or stricture;

> **L34005-cov-034** (item; under: Indications: > Evaluation of unexplained gastrointestinal bleeding:): Palliative treatment of stenosing, bleeding neoplasms (e.g., laser, electrocoagulation, stenting).

### A26. POL-SURG-004.c5 (replaces POL-SURG-004.c1)

- Decision: D-V2-2 SURG-004.F1, Q3
- What changed: v1 c1 plus the reconstructive conditions: the LCD's group 2 (cov-030 to cov-041) and group 3 (blepharospasm, cov-042 and cov-043). The V1b finding cited only cov-030 and cov-038.
- v1 text (POL-SURG-004.c1): Eyelid surgery is reconstructive (covered) when it corrects visual impairment caused by excess eyelid skin weighing down the lashes (dermatochalasis), blepharochalasis, drooping of the eyelid (blepharoptosis) or drooping of the brow.
- **v2 text:** Eyelid surgery is covered when it corrects visual impairment caused by excess eyelid skin weighing down the lashes (dermatochalasis), blepharochalasis, drooping of the eyelid (blepharoptosis) or drooping of the brow. It is also covered as reconstruction: to repair defects caused by disease (including thyroid disease and cranial nerve palsies), trauma or tumor surgery; for ectropion or entropion, epiblepharon, lagophthalmos, congenital ectropion, entropion, lagophthalmos or ptosis, lid retraction or lag, or chronic dermatitis caused by redundant upper eyelid skin; or, when other treatments have failed or cannot be used, to relieve blepharospasm. For these reconstructive conditions, the record must document the patient's complaints and the examination findings.
- Type: requirement. Applies to: every code of the policy. Group: -.
- Source line: LCD L33944 v27 cov-016, cov-017, cov-019 to cov-022, cov-030 to cov-043.
- Automatic check, numbers in the v2 text that no excerpt contains: none

Excerpts, word for word:

> **L33944-cov-016** (item; under: Indications and Limitations:): The conditions listed under “2” and “3” below are generally considered reconstructive and not subject to the medical review of conditions listed under “1” which have the potential of being considered cosmetic

> **L33944-cov-017** (item; under: Indications and Limitations:): Blepharoplasty may be considered reconstructive when performed for one of the following conditions that may affect both upper and lower eyelids.

> **L33944-cov-019** (item; under: Indications and Limitations: > To correct visual impairment caused by:): Dermatochalasis, including symptomatic redundant skin weighing down on the upper eyelashes (i.e., pseudoptosis) and surgically induced dermatochalasis after ptosis repair.

> **L33944-cov-020** (item; under: Indications and Limitations: > To correct visual impairment caused by:): Blepharochalasis.

> **L33944-cov-021** (item; under: Indications and Limitations: > To correct visual impairment caused by:): Blepharoptosis, including dehiscence of the aponeurosis of the levator palpebrae superioris muscle after trauma or cataract extraction, causing ptosis that may obstruct the superior visual field as well as the visual axis in downgaze (reading position).

> **L33944-cov-022** (item; under: Indications and Limitations: > To correct visual impairment caused by:): Brow ptosis.

> **L33944-cov-030** (item; under: Indications and Limitations: > To correct visual impairment caused by:): Repair of anatomical or pathological defects, including those caused by disease (including thyroid dysfunction and cranial nerve palsies), trauma, or tumor-ablative surgery. Surgery is performed to reconstruct the normal structure of the eyelid, using local or distant tissue. Reconstruction may be necessary to protect the eye and/or improve visual function. Conditions that may require blepharoplasty, ptosis repair, ectropion repair, or entropion repair are:

> **L33944-cov-031** (item; under: Indications and Limitations: > To correct visual impairment caused by:): Ectropion and entropion

> **L33944-cov-032** (item; under: Indications and Limitations: > To correct visual impairment caused by:): Epiblepharon

> **L33944-cov-033** (item; under: Indications and Limitations: > To correct visual impairment caused by:): Post-traumatic defects of the eyelid

> **L33944-cov-034** (item; under: Indications and Limitations: > To correct visual impairment caused by:): Post-surgical defects after excision of neoplasm(s)

> **L33944-cov-035** (item; under: Indications and Limitations: > To correct visual impairment caused by:): Lagophthalmos

> **L33944-cov-036** (item; under: Indications and Limitations: > To correct visual impairment caused by:): Congenital lagophthalmos

> **L33944-cov-037** (item; under: Indications and Limitations: > To correct visual impairment caused by:): Congenital ectropion, entropion

> **L33944-cov-038** (item; under: Indications and Limitations: > To correct visual impairment caused by:): Congenital ptosis

> **L33944-cov-039** (item; under: Indications and Limitations: > To correct visual impairment caused by:): Lid retraction or lag (due to horizontal lower eyelid laxity without ectropion or entropion, causing exposure keratopathy and/or epiphora; due to horizontal upper eyelid laxity, causing floppy eyelid syndrome; or due to orbital thyroid disease).

> **L33944-cov-040** (item; under: Indications and Limitations: > To correct visual impairment caused by:): Chronic symptomatic dermatitis of pretarsal skin caused by redundant upper eyelid skin.

> **L33944-cov-041** (item; under: Indications and Limitations: > To correct visual impairment caused by:): The medical record must contain documented patient complaints and pertinent examination findings to justify the medical necessity for functional, restorative procedures(s) for the treatment of any of the above conditions. (Please see “Documentation Requirements.”) (Photography for purposes of documentation is not separately reportable or reimbursed.)

> **L33944-cov-042** (item; under: Indications and Limitations: > To correct visual impairment caused by:): Relief of eye symptoms associated with blepharospasm. Primary essential (idiopathic) blepharospasm is characterized by severe squinting, secondary to uncontrollable spasms the peri-ocular facial muscles. Occasionally, it can be debilitating. If other treatments have failed or are contraindicated, a blepharoplasty combined with limited myectomy may be necessary.

> **L33944-cov-043** (item; under: Indications and Limitations: > To correct visual impairment caused by:): Patient complaints and relevant medical history (e.g., failure to respond to botulinum toxin therapy, botulinum toxin therapy is contraindicated, etc.) must be documented and available upon request. Please see “Documentation Requirements.”

### A27. POL-SURG-004.c6 (replaces POL-SURG-004.c2)

- Decision: D-V2-2 SURG-004.F1
- What changed: v1 c2 limited to the four group 1 conditions; the reconstructive conditions are exempt (cov-016).
- v1 text (POL-SURG-004.c2): The record must document the patient's complaints of functional problems: vision blocked above or to the side, trouble reading because the upper field is lost, or looking through the eyelashes or seeing eyelid skin.
- **v2 text:** For dermatochalasis, blepharochalasis, blepharoptosis or brow ptosis, the record must document the patient's complaints of functional problems: vision blocked above or to the side, trouble reading because the upper field is lost, or looking through the eyelashes or seeing eyelid skin. The reconstructive conditions are exempt.
- Type: conditional (applies when: dermatochalasis, blepharochalasis, blepharoptosis or brow ptosis). Applies to: every code of the policy. Group: -.
- Source line: LCD L33944 v27 cov-016, cov-024 to cov-027.
- Automatic check, numbers in the v2 text that no excerpt contains: none

Excerpts, word for word:

> **L33944-cov-016** (item; under: Indications and Limitations:): The conditions listed under “2” and “3” below are generally considered reconstructive and not subject to the medical review of conditions listed under “1” which have the potential of being considered cosmetic

> **L33944-cov-024** (item; under: Indications and Limitations: > To correct visual impairment caused by:): Any procedure(s) involving blepharoplasty and billed to this contractor must be supported by documented patient complaints which justify functional surgery. This documentation must address the signs and symptoms commonly found in association with ptosis, pseudoptosis, blepharochalasis and/or dermatochalasis. These include (but are not limited to):

> **L33944-cov-025** (item; under: Indications and Limitations: > To correct visual impairment caused by:): Significant interference with vision or superior or lateral visual field, (e.g., difficulty seeing objects approaching from the periphery);

> **L33944-cov-026** (item; under: Indications and Limitations: > To correct visual impairment caused by:): Difficulty reading due to superior visual field loss; or,

> **L33944-cov-027** (item; under: Indications and Limitations: > To correct visual impairment caused by:): Looking through the eyelashes or seeing the upper eyelid skin.

### A28. POL-SURG-004.c7 (replaces POL-SURG-004.c3)

- Decision: D-V2-2 SURG-004.F1
- What changed: v1 c3 limited to the four group 1 conditions; the reconstructive conditions are exempt (cov-016).
- v1 text (POL-SURG-004.c3): Visual field testing must show a significant loss of upper vision (at least 12 degrees or 30 percent) that the surgery could correct.
- **v2 text:** For dermatochalasis, blepharochalasis, blepharoptosis or brow ptosis, visual field testing must show a significant loss of upper vision (at least 12 degrees or 30 percent) that the surgery could correct. The reconstructive conditions are exempt.
- Type: conditional (applies when: dermatochalasis, blepharochalasis, blepharoptosis or brow ptosis). Applies to: every code of the policy. Group: -.
- Source line: LCD L33944 v27 cov-016, cov-028.
- Automatic check, numbers in the v2 text that no excerpt contains: none

Excerpts, word for word:

> **L33944-cov-016** (item; under: Indications and Limitations:): The conditions listed under “2” and “3” below are generally considered reconstructive and not subject to the medical review of conditions listed under “1” which have the potential of being considered cosmetic

> **L33944-cov-028** (item; under: Indications and Limitations: > To correct visual impairment caused by:): The visual fields should demonstrate a significant loss of superior visual field and potential correction of the visual field by the proposed procedures(s). A minimum 12 degree or 30 percent loss of upper field of vision with upper lid skin and/or upper lid margin in repose and elevated (by taping of the lid) to demonstrate potential correction by the proposed procedure or procedures is required. Photographs may be used to demonstrate the eyelid abnormality(ies) necessitating the procedures(s), but are not required. (Photography for purposes of documentation is not seperately reportable or reimbursed.) (Please see “Documentation Requirements.”)

### A29. POL-SURG-004.c8 (replaces POL-SURG-004.c4)

- Decision: D-V2-2 SURG-004.F1, Q3
- What changed: v1 c4 limited to the four group 1 conditions; sourced to the LCD's cosmetic definitions (background blocks cov-001, cov-004 and cov-006) and cov-016.
- v1 text (POL-SURG-004.c4): Without documented functional impairment, eyelid surgery is considered cosmetic and is not covered.
- **v2 text:** For dermatochalasis, blepharochalasis, blepharoptosis or brow ptosis, eyelid surgery without documented functional impairment is considered cosmetic and is not covered.
- Type: exclusion. Applies to: every code of the policy. Group: -.
- Source line: LCD L33944 v27 cov-001, cov-004, cov-006, cov-016.
- Automatic check, numbers in the v2 text that no excerpt contains: none

Excerpts, word for word:

> **L33944-cov-001** (background block; under: Abstract:): Medicare does not cover cosmetic surgery or expenses incurred in connection with such surgery. Cosmetic surgery is defined by Medicare as: “any surgical procedure directed at improving appearance, except when required for the prompt [i.e., as soon as medically feasible] repair of accidental injury or for the improvement of the functioning of a malformed body member. For example, this exclusion does not apply to surgery in connection with treatment of severe burns or repair of the face following a serious automobile accident, or to surgery for therapeutic purposes which coincidentally also serves some cosmetic purpose” (CMS Publication 100-2; Medicare Benefit Policy Manual , Chapter 16, Section 120). This local coverage determination provides additional guidance on CGS covered indications and limitations of coverage for blepharoplasty surgery

> **L33944-cov-004** (background block; under: Abstract: > The American Society of Plastic and Reconstructive Surgeons has published the following definitions:): Cosmetic Blepharoplasty: When blepharoplasty is performed to improve a patient’s appearance in the absence of any signs or symptoms of functional abnormalities, the procedure is considered cosmetic.

> **L33944-cov-006** (background block; under: Abstract: > The American Society of Plastic and Reconstructive Surgeons has published the following definitions:): Based upon the above definitions, surgery of the upper eyelids is reconstructive when it provides functional vision and/or visual field benefits or improves the functioning of a malformed or degenerated body member, but cosmetic when done to enhance aesthetic appearance. The goal of functional restorative surgery is to restore significant function to a structure that has been altered by trauma, infection, inflammation, degeneration (e.g., from aging), neoplasia, or developmental errors.

> **L33944-cov-016** (item; under: Indications and Limitations:): The conditions listed under “2” and “3” below are generally considered reconstructive and not subject to the medical review of conditions listed under “1” which have the potential of being considered cosmetic

### A30. POL-WOUND-001.c4 (replaces POL-WOUND-001.c3)

- Decision: D-V2-2 WOUND-001.F3
- What changed: v1 c3's frequency sentence plus the firm rule only: no continued care without improvement, and a revised plan when healing is not documented after 30 days. v1's 'frequent repeated debridement requires a documented reassessment' is replaced by the 30-day revision. Left out: the expectations in cov-112, cov-113 and cov-117.
- v1 text (POL-WOUND-001.c3): How often debridement is done depends on the wound. Frequent repeated debridement requires a documented reassessment of the treatment plan.
- **v2 text:** How often debridement is done depends on the wound. A given type of wound care is not continued when the record does not show improvement leading to healing, and when healing is not documented after 30 days the plan of care must be revised.
- Type: conditional (applies when: continuing or repeated wound care). Applies to: every code of the policy. Group: -.
- Source line: LCD L38902 v12 cov-082, cov-118, doc-032.
- Automatic check, numbers in the v2 text that no excerpt contains: none

Excerpts, word for word:

> **L38902-cov-082** (item; under: Limitations): Wound care may be of a palliative nature. Optimally, the overall goal of care is healing, and it would be neither reasonable nor medically necessary to continue a given type of wound care if evidence of wound improvement leading to healing of the wound as outlined in this LCD cannot be shown. However, if it is determined that the goal of care is not wound healing, which would lead ultimately to wound closure, the patient should be managed following appropriate palliative care standards. Wounds of some Medicare beneficiaries residing in Skilled Nursing Facilities (SNFs) and Nursing Facilities (NFs) may not close, heal, or be amenable to self-care in spite of optimal therapy. In those patients where wound closure, healing, or self-care is not a likely outcome, the goals of wound care may include prevention of hospitalization and improvement in quality of life. As such, due to severe underlying debility or other factors, the goal of wound care provided in these settings may be only to prevent progression of the wound by stabilizing the wound by:

> **L38902-cov-118** (item; under: Limitations > Medicare expects that with appropriate care:): Failure to document expected healing after 30 days should necessitate a revision in the Plan of Care, to include the possibility of alternative treatment approaches, or transition to an alternative care setting, such as a multidisciplinary, and specialized, wound center. It is the expectation of Medicare that patients with chronic wounds may be demonstrating manifestations of underlying chronic illnesses, and that follow-up and coordination of care with other medical practitioners be fully reflected in the chart.

> **L38902-doc-032** (item; under: Utilization Guidelines:): Wound care must be performed in accordance with accepted standards for medical and surgical treatment of wounds. The appropriate interval and frequency of debridement depends on the individual clinical characteristics of the patient and the extent of the wound. The extent and number of services provided should be medically necessary and reasonable based on the documented medical evaluation of the patient's condition, diagnosis, and plan.

Rows added after pass 1 (POL-SURG-003.c4): from approved pass 2 fixes; not yet reviewed.

### A31. POL-SURG-003.c4 (new, no v1 predecessor)

- Decision: D-POL-4 (checkpoint 1 review, B34)
- What changed: New: the LCD's section A indications (cov-007 to cov-015), which cov-017 also applies to ablation and cov-028 to same-day stab phlebectomy; c1 now applies to the ablation codes only, so stab phlebectomy (37765) has a requirement. Added after pass 1.
- **v2 text:** Treatment of varicose veins, including stab phlebectomy, is covered when a 3-month trial of conservative therapy, such as exercise, periodic leg elevation, weight loss, compression or avoiding long immobility, has failed, and the patient is symptomatic with one or more of: pain or burning in the leg severe enough to impair mobility; recurrent superficial phlebitis; a non-healing skin ulcer; bleeding from a varicosity; stasis dermatitis; or refractory dependent edema.
- Type: requirement. Applies to: every code of the policy. Group: -.
- Source line: LCD L34209 v43 cov-007 to cov-015, cov-017, cov-028.
- Automatic check, numbers in the v2 text that no excerpt contains: none

Excerpts, word for word:

> **L34209-cov-007** (item; under: the top of the field): A. Indications for surgical treatment: For example venous ligation, vein stripping and/or sclerotherapy:

> **L34209-cov-008** (item; under: the top of the field): 1. A 3-month trial of conservative therapy such as exercise, periodic leg elevation, weight loss, compressive therapy, and avoidance of prolonged immobility where appropriate, has failed, AND

> **L34209-cov-009** (heading): 2. The patient is symptomatic and has one, or more, of the following:

> **L34209-cov-010** (item; under: 2. The patient is symptomatic and has one, or more, of the following:): a. Pain or burning in the extremity severe enough to impair mobility

> **L34209-cov-011** (item; under: 2. The patient is symptomatic and has one, or more, of the following:): b. Recurrent episodes of superficial phlebitis

> **L34209-cov-012** (item; under: 2. The patient is symptomatic and has one, or more, of the following:): c. Non-healing skin ulceration

> **L34209-cov-013** (item; under: 2. The patient is symptomatic and has one, or more, of the following:): d. Bleeding from a varicosity

> **L34209-cov-014** (item; under: 2. The patient is symptomatic and has one, or more, of the following:): e. Stasis dermatitis

> **L34209-cov-015** (item; under: 2. The patient is symptomatic and has one, or more, of the following:): f. Refractory dependent edema

> **L34209-cov-017** (item; under: 2. The patient is symptomatic and has one, or more, of the following: > B. Indications for ERFA or laser ablation :): In addition to the above (see A), the patient's anatomy and clinical condition are amenable to the proposed treatment including ALL of the following:

> **L34209-cov-028** (item; under: 2. The patient is symptomatic and has one, or more, of the following: > C. Limitations for ERFA and laser ablation:): Noridian notes that stab phlebectomy of the same vein performed on the same day as endovenous radiofrequency or laser ablation may be covered if the criteria for reasonable and necessary as described in this LCD are met.

## Part B: kept criteria (38 rows)

Text and ID unchanged from v1 (checked byte for byte); only the type, code list and group are new.

| Row | Criterion | Text | Type | Applies to | Group |
|---|---|---|---|---|---|
| B1 | POL-BH-001.c1 | Testing is covered when brain or psychological involvement is known or suspected and the results will affect diagnosis, treatment planning or management. An example is telling dementia or brain injury apart from depression when the diagnosis is still uncertain after examination. | requirement | all | - |
| B2 | POL-BH-001.c2 | Testing is not covered when no problem with brain or emotional function is suspected, when it consists only of self-administered or self-scored screening tools, or when it is repeated without being needed for a medical decision. | exclusion | all | - |
| B3 | POL-BH-001.c3 | Routine re-evaluation of chronically disabled patients that is not needed for diagnosis or continued treatment is not medically necessary. | exclusion | all | - |
| B4 | POL-CAR-001.c2 | Repeating the study more often than once a year is not medically necessary unless the notes document a clear change in signs or symptoms, a check of the response to treatment, or planned valve surgery. | conditional (applies when: the study repeats one done within the past year) | all | - |
| B5 | POL-CAR-001.c3 | Stress echocardiography is covered to evaluate suspected coronary artery disease in patients with signs or symptoms, for example after a treadmill stress test that did not give a diagnosis. | requirement | 93350 | - |
| B6 | POL-DX-001.c1 | Sleep testing is covered to evaluate suspected sleep apnea or narcolepsy when the physician's evaluation documents the symptoms and findings that led to the test. | requirement | all | - |
| B7 | POL-DX-001.c3 | A repeat facility study is covered when the first study was technically inadequate, the patient slept too little for a diagnosis, starting or confirming the effect of therapy requires it (such as CPAP titration), or the results were inconclusive. | conditional (applies when: a repeat facility study) | 95810, 95811 | - |
| B8 | POL-DX-002.c1 | Testing is covered when the history and examination before the test clearly document the need for it, for example limb pain, numbness or tingling, or weakness that suggests a nerve or muscle disorder. A bare rule-out diagnosis is not sufficient. | requirement | all | - |
| B9 | POL-DX-002.c2 | These tests are not a first-line test for limb pain caused by a recent injury or an acute bone injury. | exclusion | all | - |
| B10 | POL-DX-002.c3 | Routine testing for nerve damage from diabetes or end-stage kidney disease, or testing only to monitor how severe it is or how well treatment works, is not covered. | exclusion | all | - |
| B11 | POL-DX-003.c2 | Patch testing is covered for suspected allergic contact dermatitis, or other dermatitis where a contact allergen is the likely cause. | requirement | 95044 | - |
| B12 | POL-DX-003.c3 | The tests chosen must match the patient's history and physical findings, and the number of tests must be justified. Guideline limits for an initial evaluation are about 70 prick and 40 intradermal tests for airborne allergens, or up to 80 patch tests. | requirement | all | - |
| B13 | POL-FOOT-001.c1 | Routine foot care is covered for nerve damage in the feet (without blood-vessel impairment) severe enough that care by a non-professional would put the patient at risk. The record must document loss of protective sensation: no feeling at 2 or more of 5 sites on either foot with the 5.07 Semmes-Weinstein monofilament. | conditional (applies when: nerve damage in the feet without blood-vessel impairment) | all | indication |
| B14 | POL-FOOT-001.c2 | It is covered for patients on blood thinners when the record documents the significant risk of non-professional foot care. | conditional (applies when: the patient takes blood thinners) | all | indication |
| B15 | POL-IMG-001.c1 | CT or MRI of the head or neck is covered when the scan is medically appropriate for the patient's documented symptoms and provisional diagnosis. Symptoms recorded on the claim and in the notes must support the scan as ordered. | requirement | all | - |
| B16 | POL-IMG-001.c2 | For headache or dizziness, imaging is covered only with a focal neurological finding, a significant change in symptoms, a head injury where bleeding must be ruled out, a headache lasting more than two weeks that has not responded to treatment, or a sudden, severe headache. | conditional (applies when: headache or dizziness) | all | - |
| B17 | POL-IMG-001.c3 | Scans with contrast need a documented reason, such as characterizing a specific lesion, suspected stroke, tumor or infection, or cancer staging. More than one contrast scan per episode of illness is not covered except for stroke, TIA, non-traumatic bleeding, post-operative checks, or a known brain tumor with new neurological change. | requirement | 70553 | - |
| B18 | POL-IMG-001.c4 | Brain imaging to stage a cancer without neurological symptoms is not covered for cancers that rarely spread to the brain: esophagus, oropharynx, prostate and non-melanoma skin cancer. | exclusion | all | - |
| B19 | POL-IMG-002.c1 | Extremity ultrasound is covered to evaluate cysts, abscesses, tumors or joint effusions; tendons, joints, plantar fascia, ligaments, soft-tissue masses, ganglion cysts, neuromas or metatarsal stress fractures; or foreign bodies. | requirement | all | - |
| B20 | POL-IMG-002.c2 | It is not medically necessary for the routine diagnosis of bunions, cellulitis, obvious neuromas, nail-fold infections, plantar warts or superficial abscesses, unless the notes show that the clinical picture is unclear. | exclusion | all | - |
| B21 | POL-IMG-002.c3 | For plantar fasciitis, one ultrasound is covered only when the diagnosis is still uncertain after a failed course of conservative treatment. It is not covered for the initial diagnosis or for repeat studies. | conditional (applies when: plantar fasciitis) | all | - |
| B22 | POL-IMG-002.c4 | Scanning both limbs requires documented disease in both. Scanning the other limb only as a comparison is not covered. | conditional (applies when: both limbs are scanned) | all | - |
| B23 | POL-PAIN-001.c1 | History, examination and matching imaging must support nerve-root pain (radiculopathy) or neurogenic claudication from a disc herniation, bone spurs or severe disc degeneration narrowing the spinal canal or nerve openings; or pain after spinal surgery (post-laminectomy syndrome); or acute shingles pain. | requirement | all | - |
| B24 | POL-PAIN-001.c3 | The pain must have lasted at least 4 weeks, with failure of, or inability to tolerate, 4 weeks of non-invasive conservative care. Acute shingles pain that does not respond to conservative care is exempt from the 4-week wait. | requirement | all | - |
| B25 | POL-PAIN-002.c1 | The patient must have moderate to severe chronic neck or low back pain, mainly in the spine itself (axial), causing a functional deficit measured on a pain or disability scale. | requirement | all | - |
| B26 | POL-PAIN-002.c2 | The pain must have lasted at least 3 months, with documented failure of non-invasive conservative care. | requirement | all | - |
| B27 | POL-PAIN-002.c3 | There must be no untreated nerve-root pain or neurogenic claudication (except from a facet joint cyst), and no other cause of the pain such as fracture, tumor, infection or major deformity. | requirement | all | - |
| B28 | POL-REHAB-001.c1 | Services must be complex enough to need the skills of a qualified physical therapist, or be given under a physical therapist's supervision. | requirement | all | - |
| B29 | POL-REHAB-001.c3 | Restorative therapy requires a reasonable potential for improvement from the services. Maintenance programs must meet the Medicare Benefit Policy Manual, Chapter 15, Section 220 criteria. | requirement | all | - |
| B30 | POL-SURG-001.c1 | Surgery is covered when the cataract causes symptoms of impaired vision that cannot be corrected with a tolerable change in glasses or contact lenses, and that limits activities such as reading, watching television, driving, or work and hobbies. Other eye diseases must be ruled out as the main cause. | conditional (applies when: a cataract causing impaired vision) | all | indication |
| B31 | POL-SURG-001.c2 | Surgery is not medically necessary based only on clouding of the lens without symptoms. | exclusion | all | - |
| B32 | POL-SURG-001.c3 | It is also covered when the cataract prevents monitoring or treatment of another eye disease (such as diabetic retinopathy), interferes with retinal surgery, causes lens-induced disease threatening vision, or leaves an intolerable difference between the eyes after surgery on the other eye. | conditional (applies when: another eye disease, retinal surgery or a difference between the eyes) | all | indication |
| B33 | POL-SURG-002.c3 | Patients identified as high risk for colon cancer are eligible for continued screening every 24 months. | conditional (applies when: screening of a high-risk patient) | all | indication |
| B34 | POL-SURG-003.c1 | Radiofrequency or laser vein ablation is covered only for symptomatic varicose veins of the great or small saphenous veins and their branches that have failed 3 months of conservative therapy. | requirement | all | - |
| B35 | POL-SURG-003.c2 | Treating veins that cause no symptoms, or symptomatic veins without a 3-month trial of conservative measures (such as compression, exercise, leg elevation or weight loss), is considered cosmetic and not covered, by any technique. | exclusion | all | - |
| B36 | POL-SURG-003.c3 | Treating spider veins (telangiectasias) by any technique is cosmetic and not covered. | exclusion | all | - |
| B37 | POL-WOUND-001.c1 | Active wound care (debridement) is covered to remove dead tissue and promote healing, performed with direct one-on-one patient contact, following accepted standards of wound treatment. | requirement | all | - |
| B38 | POL-WOUND-001.c2 | Care must be part of a plan that addresses complicating factors (pressure off-loading, infection, poor circulation, metabolic or nutritional problems), aiming at wound closure or, when healing is not possible, preventing the wound from getting worse. | requirement | all | - |

## Part C: indication groups (3 rows)

Every covered indication the sources give for the policy's codes, word for word, and the criterion that holds it, or why it is left out. Checked automatically: every listed source exists; a new criterion that holds one cites it; every group criterion holds at least one; the LCD indication lists (SURG-001: L33558 cov-004 to cov-009; SURG-002: L34005 cov-007 to cov-034, plus doc-001) are listed block by block.

### C1. POL-FOOT-001 (group: c1, c2, c4, c5; codes 11720, 11721)

- **L33941-cov-002** (item; under: Covered Indications) -> **POL-FOOT-001.c1**.

  > Routine foot care may be available for patients with peripheral neuropathy involving the feet, but without vascular impairment. The neuropathy should be of such severity that care by a non- professional person would put the patient at risk. The medical record must document the patient has an absence of sensation at two or more sites out of five tested on either foot when tested with the 5.07 Semmes-Weinstein monofilament to support the diagnosis of peripheral neuropathy with loss of protective sensation. This testing may be performed by the attending physician, non-physician practitioner, or the podiatrist.

- **L33941-cov-003** (item; under: Covered Indications) -> **POL-FOOT-001.c2**.

  > For patients requiring anticoagulation therapy, the provider must document in the medical record the significant risk and danger posed by the non-professional rendering routine foot care services.

- **Manual Ch. 15 §290.A** (pages 259-260) -> left out: not an indication for the nail codes 11720 and 11721 (Q4); treatment of subluxation, billed with other codes.

  > A. Treatment of Subluxation of Foot Subluxations of the foot are defined as partial dislocations or displacements of joint surfaces, tendons ligaments, or muscles of the foot. Surgical or nonsurgical treatments undertaken for the sole purpose of correcting a subluxated structure in the foot as an isolated entity are not covered. However, medical or surgical treatment of subluxation of the ankle joint (talo-crural joint) is covered. In addition, reasonable and necessary medical or surgical services, diagnosis, or treatment for medical conditions that have resulted from or are associated with partial displacement of structures is covered. For example, if a patient has osteoarthritis that has resulted in a partial displacement of joints in the foot, and the primary treatment is for the osteoarthritis, coverage is provided.

- **Manual Ch. 15 §290.C.1** (page 261) -> left out: not an indication for the nail codes 11720 and 11721 (Q4); routine care done as a necessary and integral part of another covered service, such as ulcer, wound or infection treatment, goes with that service.

  > 1. Necessary and Integral Part of Otherwise Covered Services In certain circumstances, services ordinarily considered to be routine may be covered if they are performed as a necessary and integral part of otherwise covered services, such as diagnosis and treatment of ulcers, wounds, or infections.

- **Manual Ch. 15 §290.C.2** (page 261) -> left out: not an indication for the nail codes 11720 and 11721 (Q4); treatment of warts, billed with other codes.

  > 2. Treatment of Warts on Foot The treatment of warts (including plantar warts) on the foot is covered to the same extent as services provided for the treatment of warts located elsewhere on the body.

- **Manual Ch. 15 §290.C.3** (page 261) -> **POL-FOOT-001.c4**.

  > 3. Presence of Systemic Condition The presence of a systemic condition such as metabolic, neurologic, or peripheral vascular disease may require scrupulous foot care by a professional that in the absence of such condition(s) would be considered routine (and, therefore, excluded from coverage). Accordingly, foot care that would otherwise be considered routine may be covered when systemic condition(s) result in severe circulatory embarrassment or areas of diminished sensation in the individual’s legs or feet. (See subsection A.) In these instances, certain foot care procedures that otherwise are considered routine (e.g., cutting or removing corns and calluses, or trimming, cutting, clipping, or debriding nails) may pose a hazard when performed by a nonprofessional person on patients with such systemic conditions. (See §290.G for procedural instructions.)

- **Manual Ch. 15 §290.C.4** (page 261) -> **POL-FOOT-001.c5**.

  > 4. Mycotic Nails In the absence of a systemic condition, treatment of mycotic nails may be covered. The treatment of mycotic nails for an ambulatory patient is covered only when the physician attending the patient’s mycotic condition documents that (1) there is clinical evidence of mycosis of the toenail, and (2) the patient has marked limitation of ambulation, pain, or secondary infection resulting from the thickening and dystrophy of the infected toenail plate. The treatment of mycotic nails for a nonambulatory patient is covered only when the physician attending the patient’s mycotic condition documents that (1) there is clinical evidence of mycosis of the toenail, and (2) the patient suffers from pain or secondary infection resulting from the thickening and dystrophy of the infected toenail plate. For the purpose of these requirements, documentation means any written information that is required by the A/B MAC (B) in order for services to be covered. Thus, the information submitted with claims must be substantiated by information found in the patient’s medical record. Any information, including that contained in a form letter, used for documentation purposes is subject to A/B MAC (B) verification in order to ensure that the information adequately justifies coverage of the treatment of mycotic nails.

- **Manual Ch. 15 §290.D** (page 262) -> **POL-FOOT-001.c4** (the systemic conditions and the asterisk rule).

  > D. Systemic Conditions That Might Justify Coverage Although not intended as a comprehensive list, the following metabolic, neurologic, and peripheral vascular diseases (with synonyms in parentheses) most commonly represent the underlying conditions that might justify coverage for routine foot care. Diabetes mellitus \* Arteriosclerosis obliterans (A.S.O., arteriosclerosis of the extremities, occlusive peripheral arteriosclerosis) Buerger’s disease (thromboangiitis obliterans) Chronic thrombophlebitis \* Peripheral neuropathies involving the feet - Associated with malnutrition and vitamin deficiency \* • Malnutrition (general, pellagra) • Alcoholism • Malabsorption (celiac disease, tropical sprue) • Pernicious anemia Associated with carcinoma \* Associated with diabetes mellitus \* Associated with drugs and toxins \* Associated with multiple sclerosis \* Associated with uremia (chronic renal disease) \* Associated with traumatic injury Associated with leprosy or neurosyphilis Associated with hereditary disorders • Hereditary sensory radicular neuropathy • Angiokeratoma corporis diffusum (Fabry’s) • Amyloid neuropathy When the patient’s condition is one of those designated by an asterisk (\*), routine procedures are covered only if the patient is under the active care of a doctor of medicine or osteopathy who documents the condition.

- **Manual Ch. 15 §290.E** (page 262) -> left out: not an indication for the nail codes 11720 and 11721 (Q4); supportive devices and therapeutic shoes.

  > E. Supportive Devices for Feet Orthopedic shoes and other supportive devices for the feet generally are not covered. However, this exclusion does not apply to such a shoe if it is an integral part of a leg brace, and its expense is included as part of the cost of the brace. Also, this exclusion does not apply to therapeutic shoes furnished to diabetics.

- **Manual Ch. 15 §290.F** (pages 262-264) -> **POL-FOOT-001.c4** (the class findings that show the severity).

  > F. Presumption of Coverage In evaluating whether the routine services can be reimbursed, a presumption of coverage may be made where the evidence available discloses certain physical and/or clinical findings consistent with the diagnosis and indicative of severe peripheral involvement. For purposes of applying this presumption the following findings are pertinent: Class A Findings Nontraumatic amputation of foot or integral skeletal portion thereof. Class B Findings Absent posterior tibial pulse; Advanced trophic changes as: hair growth (decrease or absence) nail changes (thickening) pigmentary changes (discoloration) skin texture (thin, shiny) skin color (rubor or redness) (Three required); and Absent dorsalis pedis pulse. Class C Findings Claudication; Temperature changes (e.g., cold feet); Edema; Paresthesias (abnormal spontaneous sensations in the feet); and Burning. The presumption of coverage may be applied when the physician rendering the routine foot care has identified: 1. A Class A finding; 2. Two of the Class B findings; or 3. One Class B and two Class C findings. Cases evidencing findings falling short of these alternatives may involve podiatric treatment that may constitute covered care and should be reviewed by the intermediary’s medical staff and developed as necessary. For purposes of applying the coverage presumption where the routine services have been rendered by a podiatrist, the A/B MAC (B) may deem the active care requirement met if the claim or other evidence available discloses that the patient has seen an M.D. or D.O. for treatment and/or evaluation of the complicating disease process during the 6-month period prior to the rendition of the routine-type services. The A/B MAC (A) may also accept the podiatrist’s statement that the diagnosing and treating M.D. or D.O. also concurs with the podiatrist’s findings as to the severity of the peripheral involvement indicated. Services ordinarily considered routine might also be covered if they are performed as a necessary and integral part of otherwise covered services, such as diagnosis and treatment of diabetic ulcers, wounds, and infections.

- **Manual Ch. 15 §290.G** (pages 264-265) -> **POL-FOOT-001.c4** (the sentence that a diagnosis alone does not show the severity; its items 1 and 2 are payment rules for other services (a covered procedure, initial diagnostic services)).

  > G. Application of Foot Care Exclusions to Physician’s Services The exclusion of foot care is determined by the nature of the service. Thus, payment for an excluded service should be denied whether performed by a podiatrist, osteopath, or a doctor of medicine, and without regard to the difficulty or complexity of the procedure. When an itemized bill shows both covered services and noncovered services not integrally related to the covered service, the portion of charges attributable to the noncovered services should be denied. (For example, if an itemized bill shows surgery for an ingrown toenail and also removal of calluses not necessary for the performance of toe surgery, any additional charge attributable to removal of the calluses should be denied.) In reviewing claims involving foot care, the A/B MAC (B) should be alert to the following exceptional situations: 1. Payment may be made for incidental noncovered services performed as a necessary and integral part of, and secondary to, a covered procedure. For example, if trimming of toenails is required for application of a cast to a fractured foot, the A/B MAC (B) need not allocate and deny a portion of the charge for the trimming of the nails. However, a separately itemized charge for such excluded service should be disallowed. When the primary procedure is covered the administration of anesthesia necessary for the performance of such procedure is also covered. 2. Payment may be made for initial diagnostic services performed in connection with a specific symptom or complaint if it seems likely that its treatment would be covered even though the resulting diagnosis may be one requiring only noncovered care. The name of the M.D. or D.O. who diagnosed the complicating condition must be submitted with the claim. In those cases, where active care is required, the approximate date the beneficiary was last seen by such physician must also be indicated. NOTE: Section 939 of P.L. 96-499 removed “warts” from the routine foot care exclusion effective July 1, 1981. Relatively few claims for routine-type care are anticipated considering the severity of conditions contemplated as the basis for this exception. Claims for this type of foot care should not be paid in the absence of convincing evidence that nonprofessional performance of the service would have been hazardous for the beneficiary because of an underlying systemic disease. The mere statement of a diagnosis such as those mentioned in §D above does not of itself indicate the severity of the condition. Where development is indicated to verify diagnosis and/or severity the A/B MAC (B) should follow existing claims processing practices, which may include review of A/B MAC (B)’s history and medical consultation as well as physician contacts. The rules in §290.F concerning presumption of coverage also apply. Codes and policies for routine foot care and supportive devices for the feet are not exclusively for the use of podiatrists. These codes must be used to report foot care services regardless of the specialty of the physician who furnishes the services. A/B MACs (B) must instruct physicians to use the most appropriate code available when billing for routine foot care.

### C2. POL-SURG-001 (group: c1, c3, c4; codes 66982, 66984)

- **L33558-cov-004** (item; under: Indications and Limitations:) -> **POL-SURG-001.c1**.

  > Cataract causing symptomatic (i.e., causing the patient to seek medical attention) impairment of visual function not correctable with a tolerable change in glasses or contact lenses resulting in specific activity limitations and/or participation restrictions including, but not limited to reading, viewing television, driving, or meeting vocational or recreational needs. Surgery is not deemed to be medically necessary purely on the basis of lens opacity in the absence of symptoms. Also other eye disease(s) including, but not limited to macular degeneration or diabetic retinopathy, have been ruled out as the primary cause of decreased visual function.

- **L33558-cov-005** (item; under: Indications and Limitations:) -> **POL-SURG-001.c3**.

  > Concomitant intraocular disease (e.g., diabetic retinopathy or intraocular tumor) requiring monitoring or treatment that is prevented by the presence of cataract.

- **L33558-cov-006** (item; under: Indications and Limitations:) -> **POL-SURG-001.c3**.

  > Cataract interfering with the performance of vitreoretinal surgery (e.g., performance of surgery for far peripheral vitreoretinal dissection and excision of the vitreous base, as in cases of proliferative vitreoretinopathy, complicated retinal detachments, and severe proliferative diabetic retinopathy).

- **L33558-cov-007** (item; under: Indications and Limitations:) -> **POL-SURG-001.c3**.

  > Lens-induced disease threatening vision or ocular health (including, but not limited to, phacomorphic or phacolytic glaucoma)

- **L33558-cov-008** (item; under: Indications and Limitations:) -> **POL-SURG-001.c4**.

  > High probability of accelerating cataract development as a result of a concomitant or subsequent procedure (e.g., pars plana vitrectomy, iridocyclectomy, procedure for ocular trauma) and treatments such as external beam irradiation

- **L33558-cov-009** (item; under: Indications and Limitations:) -> **POL-SURG-001.c3**.

  > Intolerable anisometropia or aniseikonia uncorrectable with glasses or contact lenses that exists as a result of lens extraction in the first eye (despite satisfactorily corrected monocular visual acuity).

### C3. POL-SURG-002 (group: c3, c4, c5, c7 (45380, 45385); codes 45378, 45380, 45385)

- **L34005-cov-007** (item; under: Indications: > The following are Medicare-covered indications:) -> **POL-SURG-002.c4**.

  > Evaluation of an abnormality discovered on barium enema and/or other imaging technique that is likely to be clinically significant, such as a filling defect or stricture or an inadequate examination;

- **L34005-cov-009** (item; under: Indications: > Evaluation of unexplained gastrointestinal bleeding:) -> **POL-SURG-002.c4**.

  > Hematochezia not thought to be from rectum or perianal source

- **L34005-cov-010** (item; under: Indications: > Evaluation of unexplained gastrointestinal bleeding:) -> **POL-SURG-002.c4**.

  > Melena of unknown origin;

- **L34005-cov-011** (item; under: Indications: > Evaluation of unexplained gastrointestinal bleeding:) -> **POL-SURG-002.c4**.

  > Presence of fecal occult blood

- **L34005-cov-012** (item; under: Indications: > Evaluation of unexplained gastrointestinal bleeding:) -> **POL-SURG-002.c4**.

  > Unexplained iron deficiency anemia;

- **L34005-cov-014** (item; under: Indications: > Evaluation of unexplained gastrointestinal bleeding:) -> **POL-SURG-002.c4**.

  > Examination to evaluate entire colon for synchronous cancer or polyps in a patient with treatable cancer or polyp;

- **L34005-cov-013** (item; under: Indications: > Evaluation of unexplained gastrointestinal bleeding:) -> **POL-SURG-002.c5**.

  > Surveillance of colonic neoplasia. When the patient has a history of colorectal cancer or polyps and is being followed for this indication;

- **L34005-cov-015** (item; under: Indications: > Evaluation of unexplained gastrointestinal bleeding:) -> **POL-SURG-002.c5**.

  > Follow-up in one year after surgery for treatment of colorectal cancer;

- **L34005-cov-016** (item; under: Indications: > Evaluation of unexplained gastrointestinal bleeding:) -> **POL-SURG-002.c3**.

  > This patient is identified as being at high-risk for colon cancer and is eligible for continued screening at 24-month intervals.

- **L34005-cov-017** (item; under: Indications: > Evaluation of unexplained gastrointestinal bleeding:) -> **POL-SURG-002.c5**.

  > Follow-up for removal of neoplastic polyp (follow-up at least three to six months to verify removal of large sessile adenoma [i.e., greater than 2 cm in greatest dimension] after colonoscopic removal);

- **L34005-cov-018** (item; under: Indications: > Evaluation of unexplained gastrointestinal bleeding:) -> **POL-SURG-002.c3** (the LCD repeats cov-016).

  > This patient is identified as being at high-risk for colon cancer and is eligible for continued screening at 24-month intervals.

- **L34005-cov-019** (item; under: Indications: > Evaluation of unexplained gastrointestinal bleeding:) -> **POL-SURG-002.c5**.

  > In patients with Crohn’s colitis and chronic ulcerative colitis: colonoscopy every one or two years with multiple biopsies for detection of cancer and dysplasia in patients with:

- **L34005-cov-020** (item; under: Indications: > Evaluation of unexplained gastrointestinal bleeding:) -> **POL-SURG-002.c5**.

  > Pancolitis of greater than seven years duration; or,

- **L34005-cov-021** (item; under: Indications: > Evaluation of unexplained gastrointestinal bleeding:) -> **POL-SURG-002.c5**.

  > Left-sided colitis of over 15 years duration (no surveillance needed for disease limited to rectosigmoid);

- **L34005-cov-022** (item; under: Indications: > Evaluation of unexplained gastrointestinal bleeding:) -> **POL-SURG-002.c4**.

  > Chronic inflammatory bowel disease of the colon if a more precise diagnosis or if a determination of the extent of activity of disease will influence immediate management;

- **L34005-cov-023** (item; under: Indications: > Evaluation of unexplained gastrointestinal bleeding:) -> **POL-SURG-002.c4**.

  > Clinically significant diarrhea of unexplained origin with additional findings (e.g., with weight loss or negative stool cultures persisting for more than 3 weeks;

- **L34005-cov-024** (item; under: Indications: > Evaluation of unexplained gastrointestinal bleeding:) -> **POL-SURG-002.c4**.

  > Intraoperative identification of the site of a lesion that can not be detected by palpation or gross inspection at surgery (e.g., polypectomy site or location of a bleeding source);

- **L34005-cov-025** (item; under: Indications: > Evaluation of unexplained gastrointestinal bleeding:) -> **POL-SURG-002.c4**.

  > Evaluation of acute colonic ischemia/ischemic bowel disease;

- **L34005-cov-026** (item; under: Indications: > Evaluation of unexplained gastrointestinal bleeding:) -> **POL-SURG-002.c4**.

  > Evaluation of patient with Streptococcus bovis endocarditis;

- **L34005-cov-027** (item; under: Indications: > Evaluation of unexplained gastrointestinal bleeding:) -> **POL-SURG-002.c7**.

  > Treatment of bleeding from such lesions as vascular anomalies, ulceration and neoplasia;

- **L34005-cov-028** (item; under: Indications: > Evaluation of unexplained gastrointestinal bleeding:) -> **POL-SURG-002.c7**.

  > Removal of foreign body;

- **L34005-cov-029** (item; under: Indications: > Evaluation of unexplained gastrointestinal bleeding:) -> **POL-SURG-002.c7**.

  > Excision of colonic polyps;

- **L34005-cov-030** (item; under: Indications: > Evaluation of unexplained gastrointestinal bleeding:) -> **POL-SURG-002.c7**.

  > Decompression of pseudo-obstruction of the colon (Olgilvie’s syndrome);

- **L34005-cov-031** (item; under: Indications: > Evaluation of unexplained gastrointestinal bleeding:) -> **POL-SURG-002.c7**.

  > Treatment of sigmoid volvulus or stricture;

- **L34005-cov-032** (item; under: Indications: > Evaluation of unexplained gastrointestinal bleeding:) -> **POL-SURG-002.c4**.

  > Evaluation of unexplained, new onset constipation, refractory to medical therapy;

- **L34005-cov-033** (item; under: Indications: > Evaluation of unexplained gastrointestinal bleeding:) -> **POL-SURG-002.c4**.

  > Evaluation of anorectal polyp (adenomatous polyp only); or,

- **L34005-cov-034** (item; under: Indications: > Evaluation of unexplained gastrointestinal bleeding:) -> **POL-SURG-002.c7**.

  > Palliative treatment of stenosing, bleeding neoplasms (e.g., laser, electrocoagulation, stenting).

- **L34005-doc-001** (item; under: the top of the field) -> **POL-SURG-002.c4**.

  > Infectious colitis is an acceptable indication in its general form. However, specificity in ICD-10-CM coding is not needed but should be maintained in the patient's chart. The medical record should support the medical necessity and frequency of this treatment.

## Verdicts

Pass 1 (2026-10-09): a normal Claude chat with no repository access, which saw only the pasted sheet and the pass 1 prompt (answers as returned: P2_policies_v2_pass1_answers.md). A Claude recomputation, not a human check; independent of the repository by construction, not of the author model (the criteria were also written by Claude). Pass 2 is the reviewer's: the rows listed in P2_policies_v2_pass1_summary.md.

Author triage (2026-10-09): Claude Code, the author of the criteria, triaged the 22 pass 2 rows in P2_policies_v2_triage.md; not an independent check. The pass 2 columns hold the reviewer's decisions, recorded as 'author triage by Claude Code, decided by Manideep'.

Pass 2 (2026-10-09): the 22 triaged rows hold the reviewer's decisions on the author triage (author triage by Claude Code, decided by Manideep with recommendations from the planning chat). Approved fixes are applied to the v2 files; the texts above are the ones reviewed, and the triage file shows old and new.

### Part A (MATCHES, DIFFERENT MEANING, NOT IN SOURCE or UNSURE)

| Row | Criterion | Pass 1 verdict (Claude chat) | Pass 1 notes | Pass 2 verdict (reviewer) | Pass 2 notes |
|---|---|---|---|---|---|
| A1 | POL-CAR-001.c4 | DIFFERENT MEANING | The lead-in "signs or symptoms of, or is being evaluated for" is applied to all 17 items, but only A (cov-009) and B (cov-012) state a signs/symptoms condition and C to Q are bare headings. "lung disease affecting the heart" adds "affecting the heart" to heading "Q. Pulmonary". cov-009's "expected to be performed by examiners recognized as experts" (diastolic dysfunction) is not reflected. | NOT IN SOURCE | ADDED; fix approved (old and new text in P2_policies_v2_triage.md). Author triage by Claude Code, decided by Manideep with recommendations from the planning chat. |
| A2 | POL-CAR-001.c5 | MATCHES | Same as the first sentence of cov-012 ("When there are no signs or symptoms of heart disease, the use of TTE is not covered for hypertension"); exclusion type fits. | MATCHES | OK; kept. Author triage by Claude Code, decided by Manideep with recommendations from the planning chat. |
| A3 | POL-CAR-002.c4 | DIFFERENT MEANING | "a known arrhythmia" narrows source item "Arrhythmias" (cov-007), which has no "known"; A5 uses plain "arrhythmias" for the matching 30-day list. The 40% ejection fraction, ST-segment and ablation items match. Minor: "Syncope (lightheadedness)" becomes "fainting". | NOT IN SOURCE | ADDED; fix approved (old and new text in P2_policies_v2_triage.md). Author triage by Claude Code, decided by Manideep with recommendations from the planning chat. |
| A4 | POL-CAR-002.c5 | MATCHES | Matches cov-019 (more than 48 h up to 15 days; asymptomatic episodes for treatment response; infrequent symptoms, less often than every 48 hours). Minor: source says "alternative to Holter monitoring", text says "alternative to 48-hour monitoring". |  |  |
| A5 | POL-CAR-002.c6 | MATCHES | All items of cov-022 to cov-032 are present and no ejection fraction is added for heart attack survivors. cov-020's billing rule is left to R11, as the sheet states. |  |  |
| A6 | POL-DX-001.c4 | MATCHES | Matches cov-110 (significant comorbid conditions or sleep disorders; moderate to severe pulmonary disease, neuromuscular disease, congestive heart failure). "not covered" is supported by the parent heading "...are not covered in the following situations". | MATCHES | OK; kept. Author triage by Claude Code, decided by Manideep with recommendations from the planning chat. |
| A7 | POL-DX-001.c5 | MATCHES | Matches cov-107 and cov-108 (high likelihood of moderate to severe sleep apnea, shown by symptoms and physical examination in the note). |  |  |
| A8 | POL-DX-002.c4 | MATCHES | Matches cov-037 ("usually considered not medically necessary"; "The only exception" is carpal tunnel syndrome with a high pre-test probability). "which the notes must document" comes from the cited decision and the conditional type, not the source. |  |  |
| A9 | POL-DX-003.c4 | MATCHES | Prick list matches cov-008. Intradermal list matches cov-009 without foods, consistent with cov-058. Correlation with history and examination matches cov-007. |  |  |
| A10 | POL-DX-003.c5 | MATCHES | cov-058 and cov-080 sit under Limitations, so "not covered" is a fair reading, though cov-058 itself uses the weaker "not recommended". | MATCHES | OK; kept. Author triage by Claude Code, decided by Manideep with recommendations from the planning chat. |
| A11 | POL-FOOT-001.c4 | MATCHES | Systemic conditions and asterisk/active-care rule (290.D), Class B/C counts including "three required" (290.F), "diagnosis alone" (290.G) and the 290.C.3 hazard wording all match; "for example" keeps the findings non-exhaustive. | MATCHES | OK; kept. Author triage by Claude Code, decided by Manideep with recommendations from the planning chat. |
| A12 | POL-FOOT-001.c5 | MATCHES | Matches 290.C.4 for ambulatory and nonambulatory patients. "covered only when" becomes "is covered when", but c6 carries the "only". |  |  |
| A13 | POL-FOOT-001.c6 | MATCHES | Matches 290.B.2 (corns, calluses, nail trimming and debriding). "Except as provided above" becomes "Except in the situations this policy covers", in line with c4, c5 and Part C. |  |  |
| A14 | POL-PAIN-001.c6 | MATCHES | Severity and baseline scale match cov-013 and cov-023. "a numeric score or a named scale" is added by cited decision D-ESI-2. |  |  |
| A15 | POL-PAIN-001.c7 | DIFFERENT MEANING | "without contrast only when a contrast allergy or pregnancy is documented" is narrower than cov-020 ("unless the patient has a contraindication to contrast") and cov-025 ("documented contraindication to contrast media (e.g., allergy, pregnancy)"). cov-015's fallback is "ultrasound guidance without contrast", which the text does not mention. Level limits match cov-016 and cov-017. | DIFFERENT MEANING | LIMITING CHANGE; fix approved (old and new text in P2_policies_v2_triage.md). Author triage by Claude Code, decided by Manideep with recommendations from the planning chat. |
| A16 | POL-PAIN-001.c8 | MATCHES | Matches cov-019 and cov-039 (50% for 3 months or 50% function on the same scale; repeat after 14 days with a different approach, level or medication, rationale documented). |  |  |
| A17 | POL-PAIN-001.c9 | NOT IN SOURCE | The gloss "(pain that does not radiate from a nerve root)" is not in cov-029, which says only "axial spine pain". The six listed conditions otherwise match. | NOT IN SOURCE | ADDED; fix approved with a condition: remove the gloss but keep the LCD's 'to treat' wording, so the exclusion is about what the injection treats; a patient with radicular pain who also has axial pain is not excluded. Author triage by Claude Code, decided by Manideep with recommendations from the planning chat. |
| A18 | POL-PAIN-002.c5 | MATCHES | Matches cov-023 and cov-024 (RFA intent; second procedure a minimum of 2 weeks later; documented exception). |  |  |
| A19 | POL-REHAB-001.c4 | DIFFERENT MEANING | Drops the proviso "if the patient's condition showed a need for an evaluation" (cov-112), so "An evaluation can be covered even when it finds that therapy is not needed" is unconditional (and it concerns evaluation codes this criterion does not apply to). It also drops the plan content in cov-020, "planned out specifically in terms of type, frequency and duration"; the text says only "specific goals". | DIFFERENT MEANING | MISSING LIMIT; fix approved (old and new text in P2_policies_v2_triage.md). Author triage by Claude Code, decided by Manideep with recommendations from the planning chat. |
| A20 | POL-REHAB-001.c5 | NOT IN SOURCE | "who certifies and recertifies the plan of care": doc-007 only lists "Certifications and recertifications" as required documentation, with no who or what, and cov-018 lets the physical therapist establish the plan. "under the care of a physician or NPP" is supported by doc-019. | NOT IN SOURCE | ADDED; fix approved (old and new text in P2_policies_v2_triage.md). Author triage by Claude Code, decided by Manideep with recommendations from the planning chat. |
| A21 | POL-SURG-001.c4 | MATCHES | Matches cov-008 (high probability of accelerating cataract development after a concomitant or subsequent procedure; examples; external beam irradiation). |  |  |
| A22 | POL-SURG-002.c4 | DIFFERENT MEANING | "blood in the stool not from a rectal source" drops "or perianal" and "thought to be" from cov-009 ("not thought to be from rectum or perianal source"), which broadens it. Minor: examples "negative stool cultures persisting for more than 3 weeks" (cov-023) and "an inadequate examination" (cov-007) are left out. Other items match. | DIFFERENT MEANING | MISSING LIMIT; fix approved (old and new text in P2_policies_v2_triage.md). Author triage by Claude Code, decided by Manideep with recommendations from the planning chat. |
| A23 | POL-SURG-002.c5 | MATCHES | Matches cov-013, 015, 017, 019 to 021 (2 cm, 7 years, 15 years, rectosigmoid). The 3 to 6 month and 1 to 2 year intervals are dropped by the sheet's D-RULE-1. |  |  |
| A24 | POL-SURG-002.c6 | MATCHES | All items of cov-037 to cov-049 are present (cov-040 left out on purpose per the sheet). Minor: "unusual exceptions" (cov-037) becomes "it may be done", and cov-036's documentation clause is also applied to the cov-045 list. | DIFFERENT MEANING | LIMITING CHANGE; fix approved (old and new text in P2_policies_v2_triage.md). Author triage by Claude Code, decided by Manideep with recommendations from the planning chat. |
| A25 | POL-SURG-002.c7 | MATCHES | Matches cov-027 to cov-031 and cov-034. Minor: "stenosing, bleeding neoplasms" becomes "narrowing or bleeding tumors". |  |  |
| A26 | POL-SURG-004.c5 | DIFFERENT MEANING | Drops qualifiers. "lid retraction or lag" omits cov-039's "due to horizontal lower eyelid laxity ... due to horizontal upper eyelid laxity ... or due to orbital thyroid disease". "chronic dermatitis" omits "symptomatic" and "of pretarsal skin" (cov-040). Blepharospasm omits "Primary essential (idiopathic)" (cov-042). | DIFFERENT MEANING | MISSING LIMIT; fix approved (old and new text in P2_policies_v2_triage.md). Author triage by Claude Code, decided by Manideep with recommendations from the planning chat. |
| A27 | POL-SURG-004.c6 | DIFFERENT MEANING | Closes an open list. cov-024 says the documentation must address the signs and symptoms commonly found, and "These include (but are not limited to)" three items; the text lists only those three complaints. | DIFFERENT MEANING | LIMITING CHANGE; fix approved (old and new text in P2_policies_v2_triage.md). Author triage by Claude Code, decided by Manideep with recommendations from the planning chat. |
| A28 | POL-SURG-004.c7 | MATCHES | Matches cov-028 (minimum 12 degree or 30 percent loss of upper field, potential correction). The lid-taping method is not stated but not contradicted. |  |  |
| A29 | POL-SURG-004.c8 | MATCHES | Supported by cov-001, cov-004 and cov-006. Paraphrases "in the absence of any signs or symptoms of functional abnormalities" as "without documented functional impairment"; the "to improve a patient's appearance" purpose is implicit. |  |  |
| A30 | POL-WOUND-001.c4 | DIFFERENT MEANING | Drops the palliative exception in cov-082 ("However, if it is determined that the goal of care is not wound healing ... palliative care standards"), which also conflicts with kept c2 (B38: "preventing the wound from getting worse"). "must be revised" hardens cov-118's "should necessitate a revision", and "expected healing" becomes "healing". The 30 days and the frequency sentence match. | DIFFERENT MEANING | LIMITING CHANGE; fix approved (old and new text in P2_policies_v2_triage.md). Author triage by Claude Code, decided by Manideep with recommendations from the planning chat. |
| A31 | POL-SURG-003.c4 |  |  |  |  |

### Part B (AGREE, DISAGREE or UNSURE)

| Row | Criterion | Pass 1 verdict (Claude chat) | Pass 1 notes | Pass 2 verdict (reviewer) | Pass 2 notes |
|---|---|---|---|---|---|
| B1 | POL-BH-001.c1 | AGREE | Positive coverage condition, so requirement fits; all three codes. |  |  |
| B2 | POL-BH-001.c2 | AGREE | Lists situations not covered, so exclusion fits; all codes. |  |  |
| B3 | POL-BH-001.c3 | AGREE | Not-necessary situation, so exclusion fits; all codes. |  |  |
| B4 | POL-CAR-001.c2 | UNSURE | Conditional fits the repeat trigger, but "all" includes 93350 (stress echo) while the TTE criteria A1 and A2 apply to 93306, 93308 only. The text says "Repeating the study more often than once a year" and "planned valve surgery", so the sheet does not show the rule covers stress echo. | DISAGREE | TYPE; fix approved (old and new text in P2_policies_v2_triage.md). Author triage by Claude Code, decided by Manideep with recommendations from the planning chat. |
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
| B17 | POL-IMG-001.c3 | UNSURE | 70553 is the only contrast code, so the code list fits. The type mixes a requirement ("need a documented reason") with a repeat-scan rule ("More than one contrast scan per episode of illness is not covered except ...") that applies only to a second contrast scan; the sheet splits mixed criteria elsewhere (A1 and A2). | AGREE | REWORDING; kept. Author triage by Claude Code, decided by Manideep with recommendations from the planning chat. |
| B18 | POL-IMG-001.c4 | DISAGREE | Text says "Brain imaging", but "all" includes 72141 (MRI of the neck (cervical) spine). Applies to should be 70450, 70551, 70553. | DISAGREE | TYPE; fix approved (old and new text in P2_policies_v2_triage.md). Author triage by Claude Code, decided by Manideep with recommendations from the planning chat. |
| B19 | POL-IMG-002.c1 | AGREE | Requirement listing the covered indications; both ultrasound codes. |  |  |
| B20 | POL-IMG-002.c2 | AGREE | Not-necessary situations, so exclusion fits; both codes. |  |  |
| B21 | POL-IMG-002.c3 | AGREE | Conditional on plantar fasciitis; both codes. |  |  |
| B22 | POL-IMG-002.c4 | AGREE | Conditional on both limbs scanned; both codes. |  |  |
| B23 | POL-PAIN-001.c1 | AGREE | Requirement; all three ESI codes. |  |  |
| B24 | POL-PAIN-001.c3 | AGREE | Requirement with an exemption for acute shingles pain; all codes. |  |  |
| B25 | POL-PAIN-002.c1 | AGREE | Requirement; all three facet codes. |  |  |
| B26 | POL-PAIN-002.c2 | AGREE | Requirement; all codes. |  |  |
| B27 | POL-PAIN-002.c3 | UNSURE | Negative wording ("There must be no untreated nerve-root pain ... and no other cause of the pain") behaves like an exclusion (silent notes give NOT_APPLICABLE) but is typed requirement (silent notes give NOT_DOCUMENTED, so PEND). Confirm that is intended. | AGREE | REWORDING; kept. Author triage by Claude Code, decided by Manideep with recommendations from the planning chat. |
| B28 | POL-REHAB-001.c1 | AGREE | Requirement; all five codes, including evaluations, is fine. |  |  |
| B29 | POL-REHAB-001.c3 | DISAGREE | "Restorative therapy requires a reasonable potential for improvement" should not apply to evaluation codes 97161 and 97162 (A19: an evaluation can be covered even when therapy is not needed). Applies to should be 97110, 97140, 97530. | DISAGREE | TYPE; fix approved (old and new text in P2_policies_v2_triage.md). Author triage by Claude Code, decided by Manideep with recommendations from the planning chat. |
| B30 | POL-SURG-001.c1 | AGREE | Conditional on a symptomatic cataract; both codes; indication group matches C2. |  |  |
| B31 | POL-SURG-001.c2 | AGREE | Not-necessary situation, so exclusion fits, outside the group; both codes. |  |  |
| B32 | POL-SURG-001.c3 | AGREE | Conditional; indication group matches C2; both codes. |  |  |
| B33 | POL-SURG-002.c3 | AGREE | Conditional on high-risk screening; indication group matches C3; all three codes. Note: keeps "every 24 months" while A23 drops intervals by D-RULE-1. |  |  |
| B34 | POL-SURG-003.c1 | DISAGREE | Text is limited to "Radiofrequency or laser vein ablation", but "all" includes 37765 (removal through small punctures, not ablation). Applies to should be 36475, 36478, or the text should be widened. | DISAGREE | TYPE; fix approved (old and new text in P2_policies_v2_triage.md); adds POL-SURG-003.c4. Author triage by Claude Code, decided by Manideep with recommendations from the planning chat. |
| B35 | POL-SURG-003.c2 | AGREE | Exclusion "by any technique", so all three codes. |  |  |
| B36 | POL-SURG-003.c3 | AGREE | Exclusion "by any technique", so all three codes. |  |  |
| B37 | POL-WOUND-001.c1 | DISAGREE | Text is about "Active wound care (debridement) ... to remove dead tissue", but "all" includes 29581 (multi-layer compression wrap), which is not debridement. Applies to should be 11042, 97597. | DISAGREE | TYPE; fix approved (old and new text in P2_policies_v2_triage.md). Author triage by Claude Code, decided by Manideep with recommendations from the planning chat. |
| B38 | POL-WOUND-001.c2 | AGREE | Plan-of-care requirement fits every wound code, including the compression wrap. |  |  |

### Part C (COMPLETE, GAPS or UNSURE)

| Row | Criterion | Pass 1 verdict (Claude chat) | Pass 1 notes | Pass 2 verdict (reviewer) | Pass 2 notes |
|---|---|---|---|---|---|
| C1 | POL-FOOT-001 | COMPLETE | cov-002 maps to c1, cov-003 to c2, manual C.3, D, F, G to c4, and C.4 to c5. The left-out items are right for nail codes 11720 and 11721. A (subluxation), C.2 (warts) and E (supportive devices) are billed with other codes. C.1 (integral care) is not separately payable: G.1 says "a separately itemized charge for such excluded service should be disallowed". |  |  |
| C2 | POL-SURG-001 | COMPLETE | All six items of cov-004 to cov-009 are held: cov-004 maps to c1, cov-005, 006, 007, 009 to c3, and cov-008 to c4. cov-004's "not deemed to be medically necessary purely on the basis of lens opacity" sits in c2, outside the group. |  |  |
| C3 | POL-SURG-002 | COMPLETE | Every block of cov-007 to cov-034 and doc-001 maps to c3, c4, c5 or c7, and the mappings agree with the criterion texts (A22, A23, A25, B33). cov-008 is not listed; it appears to be the "Evaluation of unexplained gastrointestinal bleeding:" heading named in cov-009's "under" path, but worth a glance. |  |  |
