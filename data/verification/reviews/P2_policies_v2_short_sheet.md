# Policies v2: short review sheet (rows added after pass 1)

One pass, in a separate Claude chat: paste the whole sheet and ask for the verdict table at the end, filled. These criteria were added or rewritten after the main sheet's pass 1; this pass gives every v2 criterion one independent check.

- **Who wrote what.** The texts, excerpt choices, types and code lists were written by the same model (Claude, in the repository session); this pass is the check.
- **Excerpts are copied word for word from data/raw** by `scripts/verify/policies_v2_sources.py`, never typed (LCD text from the CMS Medicare Coverage Database download, tags removed and whitespace collapsed; block IDs L<LCD>-cov-NNN for the coverage field, -doc-NNN for Associated Information; headings and background blocks marked). A backslash before `*` is Markdown escaping.
- **No AMA CPT text.** Codes are shown with the team's plain-language descriptions, not CPT descriptors; checked before writing (0 found).
- `decision D-...` in a source line is a team decision, not a source to check.

## How to judge

For each row: does the criterion text say what its excerpts say, no more and no less, for its type and code list? A plain-language paraphrase is fine. Pay attention to numbers and to words such as 'only', 'and'/'or', 'except', 'unless', 'usually' and 'not covered'.

- MATCHES: the same meaning.
- DIFFERENT MEANING: the text adds, drops or changes a condition, number, list item or scope. Say which.
- NOT IN SOURCE: something in the text has no support in the excerpts (apart from cited decisions).
- UNSURE: say why.

Types: requirement (must be satisfied; silent notes give NOT_DOCUMENTED); exclusion (a situation that is not covered; present gives NOT_MET, absent or silent NOT_APPLICABLE; never MET); conditional (applies only in the situation named with it, then works as a requirement). Applies to: the codes the criterion is shown on; without it, every code of the policy.

## Codes of these policies

| Code | Plain-language description (team's, not the CPT descriptor) |
|---|---|
| 36475 | Closing a leg vein from the inside with radiofrequency heat, first vein |
| 36478 | Closing a leg vein from the inside with laser heat, first vein |
| 37765 | Removing leg varicose veins through small punctures, 10 to 20 incisions |
| 62321 | Epidural steroid injection between the vertebrae, neck or upper back, with imaging guidance |
| 62323 | Epidural steroid injection between the vertebrae, lower back, with imaging guidance |
| 64483 | Epidural steroid injection beside the nerve root, lower back, first level |
| 64490 | Facet joint nerve block injection, neck or upper back, first level |
| 64493 | Facet joint nerve block injection, lower back, first level |
| 64635 | Radiofrequency destruction of facet joint nerves, lower back, first joint |
| 70450 | CT scan of the head without contrast |
| 70551 | MRI of the brain without contrast |
| 70553 | MRI of the brain before and after contrast |
| 72141 | MRI of the neck (cervical) spine without contrast |
| 76881 | Complete ultrasound of one arm or leg joint |
| 76882 | Limited ultrasound of an arm or leg joint or soft tissue area |
| 93306 | Complete heart ultrasound through the chest wall, including blood-flow imaging |
| 93308 | Limited or follow-up heart ultrasound through the chest wall |
| 93350 | Heart ultrasound during an exercise or drug stress test |
| 95004 | Skin prick allergy tests, per allergen |
| 95024 | Allergy tests injected just under the skin, per allergen |
| 95044 | Skin patch allergy tests, per patch |
| 95806 | Home sleep test measuring breathing effort and oxygen, unattended |
| 95810 | Overnight lab sleep study with brain-wave monitoring, patient 6 or older |
| 95811 | Overnight lab sleep study with CPAP titration, patient 6 or older |
| 95886 | Needle muscle electrical testing of one limb, done with nerve conduction testing |
| 95907 | Nerve conduction testing, 1 to 2 nerves |
| 95910 | Nerve conduction testing, 7 to 8 nerves |
| 96130 | Psychological test evaluation by a psychologist or physician, first hour |
| 96131 | Psychological test evaluation by a psychologist or physician, each additional hour |
| 96136 | Psychological or neuropsychological test administration by a professional, first 30 minutes |
| 97110 | Therapeutic exercise to build strength, flexibility or endurance, each 15 minutes |
| 97140 | Hands-on manual therapy such as joint mobilization, each 15 minutes |
| 97161 | Physical therapy evaluation, low complexity |
| 97162 | Physical therapy evaluation, moderate complexity |
| 97530 | Functional movement activities to improve daily tasks, each 15 minutes |

## Rows (15)

### A31. POL-SURG-003.c4

- **Text:** Treatment of varicose veins, including stab phlebectomy, is covered when a 3-month trial of conservative therapy, such as exercise, periodic leg elevation, weight loss, compression or avoiding long immobility, has failed, and the patient is symptomatic with one or more of: pain or burning in the leg severe enough to impair mobility; recurrent superficial phlebitis; a non-healing skin ulcer; bleeding from a varicosity; stasis dermatitis; or refractory dependent edema.
- Type: requirement. Applies to: every code of the policy. Group: -.
- Source line: LCD L34209 v43 cov-007 to cov-015, cov-017, cov-028.

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

### A32. POL-DX-001.c6

- **Text:** A repeat sleep study, in a facility or at home, is covered when the record justifies it: the first study was technically inadequate because of equipment failure, the patient could not sleep or slept too little for a diagnosis, the results were inconclusive or ambiguous, or starting therapy or confirming that the prescribed therapy works requires it. After a negative or technically inadequate home test in a patient with a high likelihood of moderate to severe obstructive sleep apnea, the repeat should be an in-laboratory study.
- Type: conditional (applies when: a repeat sleep study, in a facility or at home). Applies to: every code of the policy. Group: -.
- Source line: LCD L35050 v55 cov-058 to cov-062, cov-121.

Excerpts, word for word:

> **L35050-cov-058** (item; under: Covered Indications > Diagnosis of obstructive sleep apnea requires documentation of:): Repeat polysomnography or sleep testing for diagnosing sleep apnea requires documentation justifying the medical necessity for the repeated test. Repeat polysomnography/sleep testing may be indicated:

> **L35050-cov-059** (item; under: Covered Indications > Diagnosis of obstructive sleep apnea requires documentation of:): if the first study is technically inadequate due to equipment failure;

> **L35050-cov-060** (item; under: Covered Indications > Diagnosis of obstructive sleep apnea requires documentation of:): if the subject could not sleep or slept for an insufficient amount of time to allow a clinical diagnosis;

> **L35050-cov-061** (item; under: Covered Indications > Diagnosis of obstructive sleep apnea requires documentation of:): if the results were inconclusive or ambiguous; or

> **L35050-cov-062** (item; under: Covered Indications > Diagnosis of obstructive sleep apnea requires documentation of:): if initiation of therapy or confirmation of the efficacy of prescribed therapy is needed.

> **L35050-cov-121** (item; under: Limitations > Types of Monitors:): A follow-up visit to review test results should be performed for all patients undergoing OCST in the sleep facility authorized to order such testing or oversee OCST testing. Negative or technically inadequate OCST in patients with a high pretest probability of moderate to severe OSA should have prompt in-laboratory polysomnography.

### A33. POL-IMG-002.c5

- **Text:** Extremity ultrasound is not medically necessary for the routine diagnosis or management of bunions, cellulitis, nail-fold infections (paronychia), plantar warts, superficial abscesses, or neuromas whose clinical impression is obvious. For neuromas, superficial ganglia, bursae and abscesses it is not medically necessary unless the notes document a clinical presentation that obscures these simple diagnoses.
- Type: exclusion. Applies to: every code of the policy. Group: -.
- Source line: LCD L33619 v25 cov-011 to cov-017, cov-019.

Excerpts, word for word:

> **L33619-cov-011** (item; under: Limitations:): Extremity ultrasound is considered not medically necessary for the routine diagnosis or management of the following conditions:

> **L33619-cov-012** (item; under: Limitations:): - bunions;

> **L33619-cov-013** (item; under: Limitations:): - cellulitis;

> **L33619-cov-014** (item; under: Limitations:): - neuromas (where the clinical impression is obvious and ultrasound is not likely to add further information);

> **L33619-cov-015** (item; under: Limitations:): - paronychia;

> **L33619-cov-016** (item; under: Limitations:): - plantar warts; or

> **L33619-cov-017** (item; under: Limitations:): - superficial abscesses.

> **L33619-cov-019** (item; under: Limitations:): Extremity ultrasound is considered not medically necessary for diagnosis or management of neuromas, superficial ganglia, bursae and abscesses unless there is documented evidence of some clinical presentation that obscures the clinician's ability to establish these simple clinical diagnoses.

### A34. POL-BH-001.c4

- **Text:** Testing is covered when brain or psychological involvement is known or suspected, or when the results will affect the patient's management by confirming or delineating a diagnosis or otherwise informing diagnosis, treatment planning, prognosis or quality of life. An example is telling dementia or brain injury apart from depression when the diagnosis is still uncertain after examination.
- Type: requirement. Applies to: every code of the policy. Group: -.
- Source line: LCD L34520 v32 cov-003.

Excerpts, word for word:

> **L34520-cov-003** (background block; under: History/Background and/or General Information): Neuropsychological testing is not supported or excluded from medical necessity based on diagnosis alone. Rather, indications for testing are based on whether there is known or suspected neurocognitive involvement or effects, or where neuropsychological testing will impact the management of the patient by confirmation or delineation of diagnosis, or otherwise providing substantive information regarding diagnosis, treatment planning, prognosis, or quality of life.

### A35. POL-CAR-001.c6

- **Text:** Repeating the study more often than once a year is generally not medically necessary unless the notes document a discrete episode of deterioration (an abrupt change in signs or symptoms), a check of the response to treatment, or imminent valve surgery.
- Type: conditional (applies when: the study repeats one done within the past year). Applies to: 93306, 93308. Group: -.
- Source line: LCD L37379 v42 cov-008, cov-021.

Excerpts, word for word:

> **L37379-cov-008** (item; under: The clinical use of contrast echocardiography (ECHO) is appropriate in selected patients to: > A. Ventricular Function and Cardiomyopathies): Changes in myocardial thickness (hypertrophy and thinning) in derived parameters of contractility, and in chamber volume and morphology, can be quantitated and charted over time by TTE. Cardiac responses to volume perturbations, chronic pressure excess and therapeutic interventions can be monitored. Recognition of the relative contributions of myocardial and valvular functional perturbations to a clinical presentation is facilitated. TTE aids in the recognition of myopathies and their classification into hypertrophic, dilated and restrictive types. Without clinically documented, discrete (abrupt change in signs and symptoms) episodes of deterioration, it is not generally medically necessary to repeat TTE assessments more frequently than annually, unless done to evaluate the response to therapeutic intervention.

> **L37379-cov-021** (item; under: The clinical use of contrast echocardiography (ECHO) is appropriate in selected patients to: > F. Native Valvular Heart Disease): Detection of mitral stenosis was among the first practical clinical applications of TTE. TTE is well established as the technique of choice for the evaluation of valvular pathology and its effect upon global myocardial function. The relative severity of multi-valve pathologies can be quantified. Visualization of the valve and valvular apparatus facilitates therapeutic decisions when competing therapeutic options exist, especially interventions for mitral stenosis. Absent acute intervention, or a discrete change in otherwise stable clinical signs and symptoms, TTE is used annually in follow-up of chronic valvular disease to document the course over time. Generally, it is not medically necessary to repeat these examinations more frequently than annually. When the patient’s plan of care includes imminent valvular surgery, more frequent exams may be necessary.

### A36. POL-CAR-001.c7

- **Text:** Stress echocardiography is covered when the evaluation could contribute significant information about the patient's condition or treatment plan, or to add diagnostic information after a treadmill stress test that did not give a diagnosis in a patient with signs or symptoms of suspected coronary artery disease.
- Type: requirement. Applies to: 93350. Group: -.
- Source line: LCD L37379 v42 cov-049.

Excerpts, word for word:

> **L37379-cov-049** (item; under: The clinical use of contrast echocardiography (ECHO) is appropriate in selected patients to: > T. Stress ECHO): Stress ECHO may be necessary when the evaluation could contribute significant information to the patient’s condition or treatment plan or to provide additional diagnostic information in patients with a previous non-diagnostic treadmill stress test who have signs or symptoms of suspected CAD.

### A37. POL-DX-002.c5

- **Text:** Testing is covered when the history and examination before the test clearly document the need for it, for example limb pain, numbness or tingling, or weakness that suggests a nerve or muscle disorder. A rule-out diagnosis alone is typically not acceptable.
- Type: requirement. Applies to: every code of the policy. Group: -.
- Source line: LCD L34594 v42 cov-025.

Excerpts, word for word:

> **L34594-cov-025** (item; under: Results of the NCS reflect on the integrity and function of: > Nerve Conduction Studies): The broad diagnostic scope of NCS is recognizable by the foregoing description. There may be instances where questions about an indication, or need for a study, will arise. The clinical history and examination, carried out before the study, must always describe and document clearly and comprehensibly the need for the planned test. A "rule-out" diagnosis is typically not acceptable. The Contractor is cognizant of the fact that patients are not always referred with a definite diagnosis in mind. Often, pain, paresthesia, or weakness in an extremity is the reason for an NCS or EMG. These common symptoms result not only from axonal and myelin dysfunction but also from systemic, non-neurological illnesses. EMG and NCS may help in making this distinction. Therefore, symptom-based diagnoses such as "pain in limb" weakness, disturbance in skin sensation, or "paresthesia" are acceptable provided the clinical assessment unequivocally supports the need for a study. To cite but 1 example of many, an EMG or NCS is irrelevant as a first order diagnostic test for limb pain resulting from immediate antecedent trauma or acute bone injury.

### A38. POL-DX-003.c6

- **Text:** Patch testing is covered to diagnose allergic contact dermatitis, or other dermatitis or skin eruptions where a contact allergen is the likely cause, when there is a clear-cut clinical suspicion of contact allergy and the chemicals tested are relevant to the problem.
- Type: requirement. Applies to: 95044. Group: -.
- Source line: LCD L33261 v40 cov-010, cov-012.

Excerpts, word for word:

> **L33261-cov-010** (item; under: Covered Indications > A. In Vivo Testing (skin tests):): Patch testing is used to differentiate allergic contact dermatitis (ACD) and irritant contact dermatitis (ICD). Patch testing is the gold standard method of identifying the cause of allergic contact dermatitis. This testing is indicated to evaluate a nonspecific dermatitis, allergic contact dermatitis, pruritus, and other dermatitis to determine the causative antigen. It is a diagnostic test reserved for patients with skin eruptions for which a contact allergy source is likely. 1,2

> **L33261-cov-012** (item; under: Covered Indications > A. In Vivo Testing (skin tests):): Allergy patch testing will be considered medically reasonable and necessary when used to diagnose allergic contact dermatitis for patients with a clear-cut clinical suspicion of contact allergy, and they are tested with the chemicals relevant to the problem, which may include the following:

### A39. POL-DX-003.c7

- **Text:** The tests chosen must match the patient's history and physical findings, and the number of tests must be justified. For an initial evaluation of airborne allergens, guidelines justify fewer than 70 prick and 40 intradermal tests; up to 80 patch tests may be needed to diagnose allergic contact dermatitis.
- Type: requirement. Applies to: every code of the policy. Group: -.
- Source line: LCD L33261 v40 cov-055, cov-056.

Excerpts, word for word:

> **L33261-cov-055** (item; under: Limitations): The number of allergy tests performed should be judicious and dependent upon the patient’s history, physical findings and provider’s clinical judgment. All patients should not necessarily receive the same tests or the same number of sensitivity tests. Rather, testing should be patient specific based on the history and physical examination.

> **L33261-cov-056** (item; under: Limitations): Per evidence-based guidelines, the number of skin tests (e.g., < 70 prick/puncture and 40 intracutaneous tests) for inhalant allergens is justified as an initial diagnostic evaluation. Also, up to 80 patch tests may be required for ACD diagnosis.

### A40. POL-IMG-001.c5

- **Text:** A scan with contrast needs a documented reason: assessing perfusion (such as a stroke), characterizing a specific lesion, detecting a blood-brain barrier defect (such as infarct, tumor, infection or vasculitis) or new blood vessels in a tumor, new-onset seizures (particularly with a focal component), or staging a known lung cancer, breast cancer or lymphoma likely to spread early to the brain. After head trauma, contrast generally adds nothing unless symptoms suggest a possible bleed inside the skull. More than one contrast scan per episode of illness is not covered except for stroke, TIA, non-traumatic bleeding, a post-operative scan for residual tumor or a complication, or a known brain tumor or metastases with a change in mental status or other sign of central nervous system change.
- Type: requirement. Applies to: 70553. Group: -.
- Source line: LCD L37373 v41 cov-015, cov-023 to cov-035.

Excerpts, word for word:

> **L37373-cov-015** (item; under: Computerized Tomography (CT) > Patients who are not suitable candidates for MRI evaluation:): New onset seizures, particularly if a focal component is present (contrast agent is appropriate for these patients)

> **L37373-cov-023** (item; under: Computerized Tomography (CT) > A CT scan for the diagnosis of headache can be allowed for the following:): A CT Scan may be ordered without contrast, with contrast, or without contrast followed by contrast. Contrast administration is not without risk to the patient, and for some conditions, adds little or no benefit to the patient. The general indications for use of contrast CT scanning (as opposed to non-contrast scanning) are to:

> **L37373-cov-024** (item; under: Computerized Tomography (CT) > A CT scan for the diagnosis of headache can be allowed for the following:): Assess perfusion (e.g. CVA)

> **L37373-cov-025** (item; under: Computerized Tomography (CT) > A CT scan for the diagnosis of headache can be allowed for the following:): Characterize a specific lesion

> **L37373-cov-026** (item; under: Computerized Tomography (CT) > A CT scan for the diagnosis of headache can be allowed for the following:): Detect defects in blood/brain barrier (e.g. infarct, tumor, infection, vasculitis)

> **L37373-cov-027** (item; under: Computerized Tomography (CT) > A CT scan for the diagnosis of headache can be allowed for the following:): Detect neovascularity (tumor), and

> **L37373-cov-028** (item; under: Computerized Tomography (CT) > A CT scan for the diagnosis of headache can be allowed for the following:): For staging of known lung cancer, breast cancer, and lymphomas likely to metastasize early to the brain

> **L37373-cov-029** (item; under: Computerized Tomography (CT) > A CT scan for the diagnosis of headache can be allowed for the following:): Intravenous contrast generally adds no information to CT scans done secondary to head trauma. Additional symptoms suggesting a possible intracranial bleed may justify the use of contrast. These symptoms should be documented in the medical record, and if appropriate, included in the diagnostic codes listed on the claim.

> **L37373-cov-030** (item; under: Computerized Tomography (CT) > A CT scan for the diagnosis of headache can be allowed for the following:): More than one contrast CT scan per episode of illness adds no information with the following exceptions:

> **L37373-cov-031** (item; under: Computerized Tomography (CT) > A CT scan for the diagnosis of headache can be allowed for the following:): CVA

> **L37373-cov-032** (item; under: Computerized Tomography (CT) > A CT scan for the diagnosis of headache can be allowed for the following:): Non-traumatic hemorrhage

> **L37373-cov-033** (item; under: Computerized Tomography (CT) > A CT scan for the diagnosis of headache can be allowed for the following:): TIA

> **L37373-cov-034** (item; under: Computerized Tomography (CT) > A CT scan for the diagnosis of headache can be allowed for the following:): Post-operative scan for residual tumor or post operative complication

> **L37373-cov-035** (item; under: Computerized Tomography (CT) > A CT scan for the diagnosis of headache can be allowed for the following:): Known brain tumor/metastases with a change in mental status or other evidence of CNS change

### A41. POL-IMG-002.c6

- **Text:** Extremity ultrasound is covered to detect cysts, abscesses, tumors (including their size) or effusions, or to tell solid tumors from fluid-filled cysts; to evaluate tendons, joints, plantar fascia, ligaments, soft-tissue masses, ganglion cysts, intermetatarsal neuromas or metatarsal stress fractures; or to help diagnose and remove foreign bodies.
- Type: requirement. Applies to: every code of the policy. Group: -.
- Source line: LCD L33619 v25 cov-003 to cov-007.

Excerpts, word for word:

> **L33619-cov-003** (heading): Extremity ultrasound is indicated for the following conditions:

> **L33619-cov-004** (item; under: Indications: > Extremity ultrasound is indicated for the following conditions:): To detect cysts, abscesses, tumors (including evaluation of size of tumors) and effusion;

> **L33619-cov-005** (item; under: Indications: > Extremity ultrasound is indicated for the following conditions:): To distinguish solid tumors from fluid-filled cysts;

> **L33619-cov-006** (item; under: Indications: > Extremity ultrasound is indicated for the following conditions:): To evaluate tendons (including tears, tendonitis and tenosynovitis), joints, plantar fascia, ligaments, soft tissue masses, ganglion cysts, intermetatarsal neuroma and stress fractures of the metatarsals;

> **L33619-cov-007** (item; under: Indications: > Extremity ultrasound is indicated for the following conditions:): To aid in the diagnosis of and surgical removal of foreign bodies.

### A42. POL-PAIN-001.c10

- **Text:** The pain must have lasted at least 4 weeks, with an inability to tolerate non-invasive conservative care or documented failure to respond to 4 weeks of it. Acute shingles pain that does not respond to conservative care is exempt from the 4-week wait.
- Type: requirement. Applies to: every code of the policy. Group: -.
- Source line: LCD L33906 v75 cov-014.

Excerpts, word for word:

> **L33906-cov-014** (item; under: Covered Indications): Pain duration of at least four (4) weeks, and the inability to tolerate noninvasive conservative care or medical documentation of failure to respond to four (4) weeks of noninvasive conservative care or acute herpes zoster refractory to conservative management where a four (4) week wait is not required. 6,9

### A43. POL-PAIN-002.c6

- **Text:** The pain must have lasted at least 3 months, with documented failure to respond to non-invasive conservative care, as tolerated.
- Type: requirement. Applies to: every code of the policy. Group: -.
- Source line: LCD L33930 v49 cov-017.

Excerpts, word for word:

> **L33930-cov-017** (item; under: Covered Indications > Facet Joint Interventions:): Pain that has been present for a minimum of 3 months with documented failure to respond to noninvasive conservative care management (as tolerated), AND

### A44. POL-REHAB-001.c6

- **Text:** Services must need the skills of a licensed physical therapist: because of their complexity or the patient's condition, they can be performed safely and effectively only by a physical therapist or under a physical therapist's supervision.
- Type: requirement. Applies to: every code of the policy. Group: -.
- Source line: LCD L34428 v93 cov-017.

Excerpts, word for word:

> **L34428-cov-017** (item; under: Restorative/Rehabilitative therapy: > GENERAL PT GUIDELINES): 1. PT services are covered services provided the services are of a level of complexity and sophistication, or the patient's condition is such that the services can be safely and effectively performed only by a licensed physical therapist or under his/her supervision. Services normally considered a routine part of nursing care are not covered as PT (i.e., turning patients to prevent pressure injuries, walking a patient in the hallway postoperatively or ambulation without gait training).

### A45. POL-REHAB-001.c7

- **Text:** Restorative therapy must be for a condition expected to improve significantly within a reasonable and generally predictable period of time; otherwise the plan must establish a safe and effective maintenance program that meets the Medicare Benefit Policy Manual, Chapter 15, Section 220 criteria.
- Type: requirement. Applies to: 97110, 97140, 97530. Group: -.
- Source line: LCD L34428 v93 cov-013, cov-015, cov-019.

Excerpts, word for word:

> **L34428-cov-013** (item; under: Restorative/Rehabilitative therapy:): In evaluating a claim for skilled therapy that is restorative/rehabilitative (i.e., whose goal and/or purpose is to reverse, in whole or in part, a previous loss of function), it would be entirely appropriate to consider the beneficiary’s potential for improvement from the services.

> **L34428-cov-015** (item; under: Restorative/Rehabilitative therapy: > Maintenance therapy:): A maintenance program is a program designed to maintain or to slow deterioration as described in the CMS Internet-Only Manual Pub. 100-02, Medicare Benefit Policy Manual, Chapter 15, §220 and §220.2 and must meet these criteria to be considered reasonable and necessary.

> **L34428-cov-019** (item; under: Restorative/Rehabilitative therapy: > GENERAL PT GUIDELINES): 3. In order for the plan of treatment to be covered, it must address a condition for which PT is an accepted method of treatment as defined by standards of medical practice. Also, the plan of treatment must be for a condition that is expected to improve significantly within a reasonable and generally predictable period of time or establishes a safe and effective maintenance program. If at any point in the treatment of an illness it is determined that the treatment is not rehabilitative or does not legitimately require the services of a qualified professional for management of a maintenance program, the services will no longer be considered reasonable and necessary and are excluded from coverage.

## Verdicts (MATCHES, DIFFERENT MEANING, NOT IN SOURCE or UNSURE)

| Row | Criterion | Pass 1 verdict (Claude chat) | Pass 1 notes |
|---|---|---|---|
| A31 | POL-SURG-003.c4 |  |  |
| A32 | POL-DX-001.c6 |  |  |
| A33 | POL-IMG-002.c5 |  |  |
| A34 | POL-BH-001.c4 |  |  |
| A35 | POL-CAR-001.c6 |  |  |
| A36 | POL-CAR-001.c7 |  |  |
| A37 | POL-DX-002.c5 |  |  |
| A38 | POL-DX-003.c6 |  |  |
| A39 | POL-DX-003.c7 |  |  |
| A40 | POL-IMG-001.c5 |  |  |
| A41 | POL-IMG-002.c6 |  |  |
| A42 | POL-PAIN-001.c10 |  |  |
| A43 | POL-PAIN-002.c6 |  |  |
| A44 | POL-REHAB-001.c6 |  |  |
| A45 | POL-REHAB-001.c7 |  |  |
