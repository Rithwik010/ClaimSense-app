# Task V1a follow-up: POL-PAIN-001 extra records

Report only. Nothing in the dataset, policies or generators was changed.

## 1. POL-PAIN-001 criteria

Quoted exactly from `data/curated/coverage_policies/POL-PAIN-001.md`.

### POL-PAIN-001.c1

> History, examination and matching imaging must support nerve-root pain (radiculopathy) or neurogenic claudication from a disc herniation, bone spurs or severe disc degeneration narrowing the spinal canal or nerve openings; or pain after spinal surgery (post-laminectomy syndrome); or acute shingles pain.
> Source: LCD L33906 v75, Covered indications.

### POL-PAIN-001.c2

> The pain must be severe enough to greatly affect quality of life or function, measured with an objective pain or function scale before treatment.
> Source: LCD L33906 v75, Covered indications.

### POL-PAIN-001.c3

> The pain must have lasted at least 4 weeks, with failure of, or inability to tolerate, 4 weeks of non-invasive conservative care. Acute shingles pain that does not respond to conservative care is exempt from the 4-week wait.
> Source: LCD L33906 v75, Covered indications.

### POL-PAIN-001.c4

> Injections must be done under CT or fluoroscopic guidance with contrast, unless there is a documented contrast allergy or pregnancy. Interlaminar injections are limited to one level, and transforaminal injections to two levels in one spinal region.
> Source: LCD L33906 v75, Covered indications, technique and levels.

### POL-PAIN-001.c5

> A repeat injection requires documented improvement of at least 50% in pain lasting at least 3 months, or at least 50% improvement in function, compared with the baseline scale.
> Source: LCD L33906 v75, Covered indications, repeat injections.

### Text on which criteria apply to initial versus repeat injections

**In `POL-PAIN-001.md`: no such text.** No passage says which criteria apply to initial versus repeat injections. The only text about repeat injections is criterion c5 itself (quoted above), whose source line reads "Covered indications, repeat injections."

**In the source LCD it cites (L33906 v75, `indication` field of `lcd.csv` in `data/raw/mcd/2026-09-21/current_lcd.zip`)**: these passages bear on it. Quoted exactly, with HTML tags removed; footnote reference numbers, which sit on their own lines in the source, are not repeated.

> Covered Indications
> Epidural steroid injection (ESI) will be considered medically reasonable and necessary when the following requirements are met:
> Radiculopathy, radicular pain and/or neurogenic claudication is severe enough to greatly impact quality of life or function. An objective pain scale or functional assessment must be performed at baseline (prior to interventions). The same scale* must be used at each follow-up for assessment of response.
> Repeat ESI when the first injection directly and significantly provided improvement of the condition being treated may be considered medically reasonable and necessary when the medical record documents a minimum of consistent 50% improvement in pain for at least three (3) months or at least 50% consistent improvement in the ability to perform previously painful movements and ADLs as compared to baseline measurement using the same scale.
> If a patient fails to respond well to the initial ESI, a repeat ESI after 14 days can be performed using a different approach, level and/or medication, if appropriate, with the rationale and medical necessity for the second ESI documented in the medical record.
> An initial injection of contrast is required to confirm epidural placement, unless the patient has a contraindication to contrast. The subsequent ESI should include corticosteroids and may be combined with anesthetics or saline.
> The ESI provides at least 50% sustained improvement of pain and/or 50% objective improvement in function (using same scale as baseline).

Passages were found by searching the field (case-insensitive) for "repeat ESI", "initial ESI", "initial injection", "follow-up" and "baseline"; they are listed in source order after the Covered Indications heading and its introduction. The Covered Indications list (the source of c1 to c4) is introduced for ESI in general; it does not say it applies only to an initial injection, and no passage says c2 or c3 is waived for a repeat injection.

## 2. Records

### DEC-TR-00037

- Split: train
- Scenario type: two_policy
- Clinical notes: The patient returns to discuss a repeat injection for leg pain. Imaging shows narrowing at L4-L5 with pressure on the L5 nerve root, which fits the pain pattern on exam. The first injection 5 months ago gave 73% pain relief that lasted about 5 months. The injection is planned under fluoroscopy with contrast at a single level. The patient has chronic low back pain. Pain is mainly in the low back itself, 8/10, worse with bending back and twisting, with a disability score of 58%. Pain has lasted 7 months despite physical therapy and medication. There is no pain or numbness down the limbs, and imaging shows no fracture, tumor or infection. Plan: epidural steroid injection between the vertebrae, lower back, with imaging guidance; facet joint nerve block injection, lower back, first level. The patient understands the plan and wants to go ahead.

Line 1, procedure code 62323, gold decision APPROVE:

| Criterion | Gold status | Gold evidence |
|---|---|---|
| POL-PAIN-001.c5 | MET | The first injection 5 months ago gave 73% pain relief that lasted about 5 months. |
| POL-PAIN-001.c1 | MET | Imaging shows narrowing at L4-L5 with pressure on the L5 nerve root, which fits the pain pattern on exam. |
| POL-PAIN-001.c4 | MET | The injection is planned under fluoroscopy with contrast at a single level. |
| POL-PAIN-001.c2 | NOT_APPLICABLE | Does not apply to this service. |
| POL-PAIN-001.c3 | NOT_APPLICABLE | Does not apply to this service. |

### DEC-TR-00038

- Split: train
- Scenario type: two_policy
- Clinical notes: The patient reports hard stools and infrequent bowel movements. Past medical history was reviewed without changes. The patient has chronic low back pain. Pain is mainly in the low back itself, 8/10, worse with bending back and twisting, with a disability score of 46%. Pain has lasted 5 months despite physical therapy and medication. Pain shoots down the right leg below the knee with numbness, and the nerve-root pressure has not been treated. Plan: epidural steroid injection between the vertebrae, lower back, with imaging guidance; radiofrequency destruction of facet joint nerves, lower back, first joint. Vital signs are stable.

Line 1, procedure code 62323, gold decision DENY:

| Criterion | Gold status | Gold evidence |
|---|---|---|
| POL-PAIN-001.c1 | NOT_MET | The patient reports hard stools and infrequent bowel movements. |
| POL-PAIN-001.c2 | NOT_APPLICABLE | Does not apply to this service. |
| POL-PAIN-001.c5 | NOT_DOCUMENTED | Not documented in the clinical notes. |
| POL-PAIN-001.c4 | NOT_DOCUMENTED | Not documented in the clinical notes. |
| POL-PAIN-001.c3 | NOT_APPLICABLE | Does not apply to this service. |

### DEC-TR-00450

- Split: train
- Scenario type: two_policy
- Clinical notes: The patient returns to discuss a repeat injection for leg pain. The patient understands the plan and wants to go ahead. MRI shows a disc herniation at L5-S1 pressing on the left S1 nerve root, matching the exam. The first injection 5 months ago gave 62% pain relief that lasted about 5 months. The injection is planned under fluoroscopy with contrast at a single level. The patient has chronic low back pain. Pain is mainly in the low back itself, 7/10, worse with bending back and twisting, with a disability score of 32%. Pain has lasted 6 months despite physical therapy and medication. There is no pain or numbness down the limbs, and imaging shows no fracture, tumor or infection. Plan: epidural steroid injection between the vertebrae, lower back, with imaging guidance; radiofrequency destruction of facet joint nerves, lower back, first joint.

Line 1, procedure code 62323, gold decision APPROVE:

| Criterion | Gold status | Gold evidence |
|---|---|---|
| POL-PAIN-001.c1 | MET | MRI shows a disc herniation at L5-S1 pressing on the left S1 nerve root, matching the exam. |
| POL-PAIN-001.c5 | MET | The first injection 5 months ago gave 62% pain relief that lasted about 5 months. |
| POL-PAIN-001.c4 | MET | The injection is planned under fluoroscopy with contrast at a single level. |
| POL-PAIN-001.c2 | NOT_APPLICABLE | Does not apply to this service. |
| POL-PAIN-001.c3 | NOT_APPLICABLE | Does not apply to this service. |

### DEC-TR-01569

- Split: train
- Scenario type: two_policy
- Clinical notes: The patient returns to discuss a repeat injection for leg pain. Imaging shows narrowing at L5-S1 with pressure on the S1 nerve root, which fits the pain pattern on exam. The patient understands the plan and wants to go ahead. The first injection 3 months ago gave 56% pain relief that lasted about 3 months. The injection is planned under fluoroscopy with contrast at a single level. The patient has chronic low back pain. Pain is mainly in the low back itself, 9/10, worse with bending back and twisting, with a disability score of 45%. Pain has lasted 10 months despite physical therapy and medication. There is no pain or numbness down the limbs, and imaging shows no fracture, tumor or infection. Plan: epidural steroid injection between the vertebrae, lower back, with imaging guidance; facet joint nerve block injection, lower back, first level.

Line 1, procedure code 62323, gold decision APPROVE:

| Criterion | Gold status | Gold evidence |
|---|---|---|
| POL-PAIN-001.c5 | MET | The first injection 3 months ago gave 56% pain relief that lasted about 3 months. |
| POL-PAIN-001.c1 | MET | Imaging shows narrowing at L5-S1 with pressure on the S1 nerve root, which fits the pain pattern on exam. |
| POL-PAIN-001.c4 | MET | The injection is planned under fluoroscopy with contrast at a single level. |
| POL-PAIN-001.c2 | NOT_APPLICABLE | Does not apply to this service. |
| POL-PAIN-001.c3 | NOT_APPLICABLE | Does not apply to this service. |

### DEC-VA-00143

- Split: validation
- Scenario type: two_policy
- Clinical notes: The patient returns to discuss a repeat injection for leg pain. MRI shows a disc herniation at L5-S1 pressing on the right S1 nerve root, matching the exam. The first injection 3 months ago gave 69% pain relief that lasted about 3 months. Vital signs are stable. The injection is planned under fluoroscopy with contrast at a single level. The patient has chronic low back pain. Pain is mainly in the low back itself, 9/10, worse with bending back and twisting, with a disability score of 33%. Pain has lasted 10 months despite physical therapy and medication. There is no pain or numbness down the limbs, and imaging shows no fracture, tumor or infection. Plan: epidural steroid injection between the vertebrae, lower back, with imaging guidance; facet joint nerve block injection, lower back, first level.

Line 1, procedure code 62323, gold decision APPROVE:

| Criterion | Gold status | Gold evidence |
|---|---|---|
| POL-PAIN-001.c1 | MET | MRI shows a disc herniation at L5-S1 pressing on the right S1 nerve root, matching the exam. |
| POL-PAIN-001.c5 | MET | The first injection 3 months ago gave 69% pain relief that lasted about 3 months. |
| POL-PAIN-001.c4 | MET | The injection is planned under fluoroscopy with contrast at a single level. |
| POL-PAIN-001.c2 | NOT_APPLICABLE | Does not apply to this service. |
| POL-PAIN-001.c3 | NOT_APPLICABLE | Does not apply to this service. |

## 3. NOT_APPLICABLE for POL-PAIN-001.c2 or c3, notes with no previous injection

**5 of 69 lines** labelled NOT_APPLICABLE for POL-PAIN-001.c2 or c3 (across train, validation and test) have notes that mention no previous injection.

- Lines: 69 (69 with both c2 and c3 NOT_APPLICABLE, 0 c2 only, 0 c3 only); procedure codes: 62323 69
- Lines whose notes mention no previous injection, by split: train 3, validation 1, test 1. They are: DEC-TR-00038 line 1 (train, two_policy); DEC-TR-00377 line 1 (train, deny_dx); DEC-TR-01583 line 1 (train, deny_dx); DEC-VA-00195 line 1 (validation, deny_dx); DEC-TE-00233 line 2 (test, office_plus_procedure)
- "Mentions a previous injection" means the clinical notes contain a match for `\b(?:repeat|prior|previous|earlier|last|first|second)\s+(?:injection|esi)s?\b` (case-insensitive). Phrases matched: "repeat injection" 54, "first injection" 44, "repeat esi" 10, "prior esi" 8
- The other reading, notes that explicitly say there was no previous injection (`\bno\s+(?:prior|previous|earlier)\s+(?:injection|esi)s?\b|\bnever had (?:an )?(?:injection|esi)`): 0 lines.
