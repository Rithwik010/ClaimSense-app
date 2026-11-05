# Sample training records for review

## DEC-VA-00266 (validation, approve_single)

```text
CLAIM
Claim ID: CLM-VA-00265
Patient: 43-year-old, sex M
Plan: PLN-PPO-GOLD (PPO); provider network: IN_NETWORK
Diagnoses:
  A. L23.7 Allergic contact dermatitis due to plants, except food
Service lines:
  1. 2026-10-17 | POS 11 | 95044 Skin patch allergy tests, per patch | modifiers: none | units 26 | diagnoses: A
Clinical notes:
  The patient has a recurring rash. An itchy rash appears wherever the skin touches nickel jewelry, suggesting allergic contact dermatitis. The 26 allergens tested were chosen from the patient's exposures at home and work. Past medical history was reviewed without changes. Plan: skin patch allergy tests, per patch.

RULES_RESULT
Claim outcome: PASS
Line 1: PASS

PLAN_BENEFITS
Excluded procedure codes: none
Line 1 (95044) candidate categories:
  - DIAGNOSTIC_TESTS: covered; prior authorization not required; no visit limit; cost share DEDUCTIBLE_COINSURANCE

COVERAGE_CRITERIA
Line 1 (95044):
  Policy POL-DX-003 Allergy testing (covers 95004, 95024, 95044):
    [POL-DX-003.c2] Patch testing is covered for suspected allergic contact dermatitis, or other dermatitis where a contact allergen is the likely cause. (LCD L33261 v40, Covered indications, section A.)
    [POL-DX-003.c3] The tests chosen must match the patient's history and physical findings, and the number of tests must be justified. Guideline limits for an initial evaluation are about 70 prick and 40 intradermal tests for airborne allergens, or up to 80 patch tests. (LCD L33261 v40, Covered indications, number of tests.)
    [POL-DX-003.c1] Skin prick and intradermal tests are covered to evaluate IgE-mediated allergy to airborne allergens, foods, stinging-insect venom, certain drugs or chemicals, when the tests are correlated with the patient's history and examination. (LCD L33261 v40, Covered indications, section A.)

LINES TO DECIDE: 1
```

Target answer:

```json
{
  "lines": [
    {
      "line_no": 1,
      "decision": "APPROVE",
      "benefit_category": "DIAGNOSTIC_TESTS",
      "criteria": [
        {
          "criterion_id": "POL-DX-003.c2",
          "status": "MET",
          "evidence": "An itchy rash appears wherever the skin touches nickel jewelry, suggesting allergic contact dermatitis."
        },
        {
          "criterion_id": "POL-DX-003.c3",
          "status": "MET",
          "evidence": "The 26 allergens tested were chosen from the patient's exposures at home and work."
        },
        {
          "criterion_id": "POL-DX-003.c1",
          "status": "NOT_APPLICABLE",
          "evidence": "Does not apply to this service."
        }
      ],
      "reasons": [],
      "missing_information": []
    }
  ],
  "complexity": "LOW"
}
```

## DEC-TR-01047 (train, deny_criterion)

```text
CLAIM
Claim ID: CLM-TR-01046
Patient: 19-year-old, sex F
Plan: PLN-PPO-SILVER (PPO); provider network: IN_NETWORK
Diagnoses:
  A. E11.621 Type 2 diabetes mellitus with foot ulcer
Service lines:
  1. 2026-10-02 | POS 11 | 11042 Removal of dead tissue from a wound down to the fat layer, first 20 square cm or less | modifiers: none | units 1 | diagnoses: A
Clinical notes:
  The patient is seen in the wound clinic for a foot ulcer. Only a dressing change was done; no dead tissue was removed. Past medical history was reviewed without changes. The care plan covers off-loading, infection control and blood-sugar management to help the wound close. Plan: removal of dead tissue from a wound down to the fat layer, first 20 square cm or less. Allergies: none known.

RULES_RESULT
Claim outcome: PASS
Line 1: PASS

PLAN_BENEFITS
Excluded procedure codes: 64635
Line 1 (11042) candidate categories:
  - MINOR_PROCEDURES: covered; prior authorization not required; no visit limit; cost share DEDUCTIBLE_COINSURANCE

COVERAGE_CRITERIA
Line 1 (11042):
  Policy POL-WOUND-001 Wound and ulcer care (covers 11042, 97597, 29581):
    [POL-WOUND-001.c1] Active wound care (debridement) is covered to remove dead tissue and promote healing, performed with direct one-on-one patient contact, following accepted standards of wound treatment. (LCD L38902 v12, Indications.)
    [POL-WOUND-001.c2] Care must be part of a plan that addresses complicating factors (pressure off-loading, infection, poor circulation, metabolic or nutritional problems), aiming at wound closure or, when healing is not possible, preventing the wound from getting worse. (LCD L38902 v12, Indications.)
    [POL-WOUND-001.c3] How often debridement is done depends on the wound. Frequent repeated debridement requires a documented reassessment of the treatment plan. (LCD L38902 v12, Indications, frequency.)

LINES TO DECIDE: 1
```

Target answer:

```json
{
  "lines": [
    {
      "line_no": 1,
      "decision": "DENY",
      "benefit_category": "MINOR_PROCEDURES",
      "criteria": [
        {
          "criterion_id": "POL-WOUND-001.c1",
          "status": "NOT_MET",
          "evidence": "Only a dressing change was done; no dead tissue was removed."
        },
        {
          "criterion_id": "POL-WOUND-001.c2",
          "status": "MET",
          "evidence": "The care plan covers off-loading, infection control and blood-sugar management to help the wound close."
        },
        {
          "criterion_id": "POL-WOUND-001.c3",
          "status": "NOT_APPLICABLE",
          "evidence": "Does not apply to this service."
        }
      ],
      "reasons": [
        "DN_NOT_MEDICALLY_NECESSARY"
      ],
      "missing_information": []
    }
  ],
  "complexity": "MEDIUM"
}
```

## DEC-TR-01208 (train, deny_dx)

```text
CLAIM
Claim ID: CLM-TR-01207
Patient: 78-year-old, sex F
Plan: PLN-HDHP (PPO); provider network: IN_NETWORK
Diagnoses:
  A. H25.13 Age-related nuclear cataract, bilateral
Service lines:
  1. 2026-10-14 | POS 24 | 45378 Colonoscopy to look inside the colon, with no tissue removed | modifiers: none | units 1 | diagnoses: A
Clinical notes:
  Vision in both eyes has slowly clouded over the past year. The patient understands the plan and wants to go ahead. Plan: colonoscopy to look inside the colon, with no tissue removed.

RULES_RESULT
Claim outcome: PASS
Line 1: PASS

PLAN_BENEFITS
Excluded procedure codes: none
Line 1 (45378) candidate categories:
  - ENDOSCOPY: covered; prior authorization not required; no visit limit; cost share DEDUCTIBLE_COINSURANCE
  - PREVENTIVE_CARE: covered; prior authorization not required; no visit limit; cost share COPAY

COVERAGE_CRITERIA
Line 1 (45378):
  Policy POL-SURG-002 Colonoscopy (covers 45378, 45380, 45385):
    [POL-SURG-002.c1] Colonoscopy to investigate symptoms is covered for an imaging abnormality likely to be significant; unexplained bleeding (blood in the stool not from a rectal source, black tarry stool, or a positive stool blood test); unexplained iron-deficiency anemia; or significant unexplained diarrhea with other findings such as weight loss. (LCD L34005 v34, Indications.)
    [POL-SURG-002.c3] Patients identified as high risk for colon cancer are eligible for continued screening every 24 months. (LCD L34005 v34, Indications.)
    [POL-SURG-002.c2] Surveillance is covered for a history of colorectal cancer or polyps, follow-up one year after colorectal cancer surgery, follow-up after removal of a large polyp, and inflammatory bowel disease surveillance (pancolitis for more than 7 years, or left-sided colitis for more than 15 years). (LCD L34005 v34, Indications.)

LINES TO DECIDE: 1
```

Target answer:

```json
{
  "lines": [
    {
      "line_no": 1,
      "decision": "DENY",
      "benefit_category": "ENDOSCOPY",
      "criteria": [
        {
          "criterion_id": "POL-SURG-002.c1",
          "status": "NOT_APPLICABLE",
          "evidence": "Does not apply to this service."
        },
        {
          "criterion_id": "POL-SURG-002.c3",
          "status": "NOT_APPLICABLE",
          "evidence": "Does not apply to this service."
        },
        {
          "criterion_id": "POL-SURG-002.c2",
          "status": "NOT_MET",
          "evidence": "Vision in both eyes has slowly clouded over the past year."
        }
      ],
      "reasons": [
        "DN_NOT_MEDICALLY_NECESSARY"
      ],
      "missing_information": []
    }
  ],
  "complexity": "MEDIUM"
}
```

## DEC-TR-00548 (train, deny_exclusion)

```text
CLAIM
Claim ID: CLM-TR-00547
Patient: 52-year-old, sex F
Plan: PLN-HDHP (PPO); provider network: IN_NETWORK
Diagnoses:
  A. E11.42 Type 2 diabetes mellitus with diabetic polyneuropathy
  B. B35.1 Tinea unguium
Service lines:
  1. 2026-11-29 | POS 11 | 11721 Trimming and cleaning of thickened toenails, 6 or more nails | modifiers: none | units 1 | diagnoses: AB
Clinical notes:
  The patient is seen for thick, painful toenails. Monofilament testing shows normal feeling at every site on both feet. The patient has no condition that makes home nail care risky; the visit is for routine trimming. Plan: trimming and cleaning of thickened toenails, 6 or more nails. Allergies: none known. Current medications were reviewed and updated.

RULES_RESULT
Claim outcome: PASS
Line 1: PASS

PLAN_BENEFITS
Excluded procedure codes: none
Line 1 (11721) candidate categories:
  - MINOR_PROCEDURES: covered; prior authorization not required; no visit limit; cost share DEDUCTIBLE_COINSURANCE

COVERAGE_CRITERIA
Line 1 (11721):
  Policy POL-FOOT-001 Routine foot care (nail debridement) (covers 11720, 11721):
    [POL-FOOT-001.c1] Routine foot care is covered for nerve damage in the feet (without blood-vessel impairment) severe enough that care by a non-professional would put the patient at risk. The record must document loss of protective sensation: no feeling at 2 or more of 5 sites on either foot with the 5.07 Semmes-Weinstein monofilament. (LCD L33941 v23, Covered indications.)
    [POL-FOOT-001.c3] Outside these conditions, routine foot care such as nail trimming is not covered (Medicare Benefit Policy Manual, Chapter 15, Section 290, referenced by the LCD). (LCD L33941 v23, Covered indications, reference to benefit policy.)
    [POL-FOOT-001.c2] It is covered for patients on blood thinners when the record documents the significant risk of non-professional foot care. (LCD L33941 v23, Covered indications.)

LINES TO DECIDE: 1
```

Target answer:

```json
{
  "lines": [
    {
      "line_no": 1,
      "decision": "DENY",
      "benefit_category": "MINOR_PROCEDURES",
      "criteria": [
        {
          "criterion_id": "POL-FOOT-001.c1",
          "status": "NOT_MET",
          "evidence": "Monofilament testing shows normal feeling at every site on both feet."
        },
        {
          "criterion_id": "POL-FOOT-001.c3",
          "status": "NOT_MET",
          "evidence": "The patient has no condition that makes home nail care risky; the visit is for routine trimming."
        },
        {
          "criterion_id": "POL-FOOT-001.c2",
          "status": "NOT_APPLICABLE",
          "evidence": "Does not apply to this service."
        }
      ],
      "reasons": [
        "DN_CONDITIONAL_EXCLUSION"
      ],
      "missing_information": []
    }
  ],
  "complexity": "HIGH"
}
```

## DEC-TR-01290 (train, ncci_bypass)

```text
CLAIM
Claim ID: CLM-TR-01289
Patient: 25-year-old, sex F
Plan: PLN-EPO (EPO); provider network: IN_NETWORK
Diagnoses:
  A. L97.312 Non-pressure chronic ulcer of right ankle with fat layer exposed
Service lines:
  1. 2026-10-27 | POS 11 | 11042 Removal of dead tissue from a wound down to the fat layer, first 20 square cm or less | modifiers: none | units 1 | diagnoses: A
  2. 2026-10-27 | POS 11 | 97597 Selective removal of dead tissue from an open wound, first 20 square cm or less | modifiers: XS | units 1 | diagnoses: A
Clinical notes:
  The patient returns to the wound clinic. Dead tissue was cut away from a 2 cm ulcer on the right ankle down to the fat layer, with the patient seen one on one. This is the fourth debridement, and the treatment plan was reassessed last week. Current medications were reviewed and updated. Plan: removal of dead tissue from a wound down to the fat layer, first 20 square cm or less; selective removal of dead tissue from an open wound, first 20 square cm or less.

RULES_RESULT
Claim outcome: PASS
Line 1: PASS
Line 2: PASS, flag NCCI_BYPASS (a bypass modifier was used; check that the notes show a separate, distinct service)

PLAN_BENEFITS
Excluded procedure codes: 97140
Line 1 (11042) candidate categories:
  - MINOR_PROCEDURES: covered; prior authorization not required; no visit limit; cost share DEDUCTIBLE_COINSURANCE
Line 2 (97597) candidate categories:
  - MINOR_PROCEDURES: covered; prior authorization not required; no visit limit; cost share DEDUCTIBLE_COINSURANCE

COVERAGE_CRITERIA
Line 1 (11042):
  Policy POL-WOUND-001 Wound and ulcer care (covers 11042, 97597, 29581):
    [POL-WOUND-001.c1] Active wound care (debridement) is covered to remove dead tissue and promote healing, performed with direct one-on-one patient contact, following accepted standards of wound treatment. (LCD L38902 v12, Indications.)
    [POL-WOUND-001.c3] How often debridement is done depends on the wound. Frequent repeated debridement requires a documented reassessment of the treatment plan. (LCD L38902 v12, Indications, frequency.)
    [POL-WOUND-001.c2] Care must be part of a plan that addresses complicating factors (pressure off-loading, infection, poor circulation, metabolic or nutritional problems), aiming at wound closure or, when healing is not possible, preventing the wound from getting worse. (LCD L38902 v12, Indications.)
Line 2 (97597):
  Policy POL-WOUND-001 Wound and ulcer care (covers 11042, 97597, 29581):
    [POL-WOUND-001.c1] Active wound care (debridement) is covered to remove dead tissue and promote healing, performed with direct one-on-one patient contact, following accepted standards of wound treatment. (LCD L38902 v12, Indications.)
    [POL-WOUND-001.c3] How often debridement is done depends on the wound. Frequent repeated debridement requires a documented reassessment of the treatment plan. (LCD L38902 v12, Indications, frequency.)
    [POL-WOUND-001.c2] Care must be part of a plan that addresses complicating factors (pressure off-loading, infection, poor circulation, metabolic or nutritional problems), aiming at wound closure or, when healing is not possible, preventing the wound from getting worse. (LCD L38902 v12, Indications.)

LINES TO DECIDE: 1, 2
```

Target answer:

```json
{
  "lines": [
    {
      "line_no": 1,
      "decision": "APPROVE",
      "benefit_category": "MINOR_PROCEDURES",
      "criteria": [
        {
          "criterion_id": "POL-WOUND-001.c1",
          "status": "MET",
          "evidence": "Dead tissue was cut away from a 2 cm ulcer on the right ankle down to the fat layer, with the patient seen one on one."
        },
        {
          "criterion_id": "POL-WOUND-001.c3",
          "status": "MET",
          "evidence": "This is the fourth debridement, and the treatment plan was reassessed last week."
        },
        {
          "criterion_id": "POL-WOUND-001.c2",
          "status": "NOT_APPLICABLE",
          "evidence": "Does not apply to this service."
        }
      ],
      "reasons": [],
      "missing_information": []
    },
    {
      "line_no": 2,
      "decision": "PEND",
      "benefit_category": "MINOR_PROCEDURES",
      "criteria": [
        {
          "criterion_id": "POL-WOUND-001.c1",
          "status": "MET",
          "evidence": "Dead tissue was cut away from a 2 cm ulcer on the right ankle down to the fat layer, with the patient seen one on one."
        },
        {
          "criterion_id": "POL-WOUND-001.c3",
          "status": "MET",
          "evidence": "This is the fourth debridement, and the treatment plan was reassessed last week."
        },
        {
          "criterion_id": "POL-WOUND-001.c2",
          "status": "NOT_APPLICABLE",
          "evidence": "Does not apply to this service."
        }
      ],
      "reasons": [
        "PD_MISSING_DOCUMENTATION"
      ],
      "missing_information": [
        "Documentation that the second debridement was on a separate wound or site"
      ]
    }
  ],
  "complexity": "HIGH"
}
```

## DEC-TE-00259 (test, office_plus_procedure)

```text
CLAIM
Claim ID: CLM-TE-00258
Patient: 78-year-old, sex F
Plan: PLN-HMO (HMO); provider network: IN_NETWORK
Diagnoses:
  A. M51.16 Intervertebral disc disorders with radiculopathy, lumbar region
Service lines:
  1. 2026-10-28 | POS 11 | 99203 Office visit for a new patient, low-complexity problem | modifiers: none | units 1 | diagnoses: A
  2. 2026-11-06 | POS 22 | 62323 Epidural steroid injection between the vertebrae, lower back, with imaging guidance | modifiers: none | units 1 | diagnoses: A
Clinical notes:
  Returns for repeat ESI. MRI: L4-L5 HNP compressing right L5 root; concordant w/ exam. NKDA. Prior ESI 3 mo ago: 63% relief x3 mo. Fluoro-guided w/ contrast, single level. Visit: eval + counseling done. VS WNL. Plan -> epidural steroid injection between the vertebrae, lower back, with imaging guidance.

RULES_RESULT
Claim outcome: PASS
Line 1: PASS
Line 2: PASS

PLAN_BENEFITS
Excluded procedure codes: 95044
Line 1 (99203) candidate categories:
  - OFFICE_VISIT_SPECIALIST: covered; prior authorization not required; no visit limit; cost share COPAY
Line 2 (62323) candidate categories:
  - PAIN_MANAGEMENT: covered; prior authorization required; no visit limit; cost share DEDUCTIBLE_COINSURANCE

COVERAGE_CRITERIA
Line 1 (99203):
  No criteria retrieved.
Line 2 (62323):
  Policy POL-PAIN-001 Epidural steroid injections (covers 62321, 62323, 64483):
    [POL-PAIN-001.c4] Injections must be done under CT or fluoroscopic guidance with contrast, unless there is a documented contrast allergy or pregnancy. Interlaminar injections are limited to one level, and transforaminal injections to two levels in one spinal region. (LCD L33906 v75, Covered indications, technique and levels.)
    [POL-PAIN-001.c1] History, examination and matching imaging must support nerve-root pain (radiculopathy) or neurogenic claudication from a disc herniation, bone spurs or severe disc degeneration narrowing the spinal canal or nerve openings; or pain after spinal surgery (post-laminectomy syndrome); or acute shingles pain. (LCD L33906 v75, Covered indications.)
    [POL-PAIN-001.c5] A repeat injection requires documented improvement of at least 50% in pain lasting at least 3 months, or at least 50% improvement in function, compared with the baseline scale. (LCD L33906 v75, Covered indications, repeat injections.)
    [POL-PAIN-001.c2] The pain must be severe enough to greatly affect quality of life or function, measured with an objective pain or function scale before treatment. (LCD L33906 v75, Covered indications.)
    [POL-PAIN-001.c3] The pain must have lasted at least 4 weeks, with failure of, or inability to tolerate, 4 weeks of non-invasive conservative care. Acute shingles pain that does not respond to conservative care is exempt from the 4-week wait. (LCD L33906 v75, Covered indications.)

LINES TO DECIDE: 1, 2
```

Target answer:

```json
{
  "lines": [
    {
      "line_no": 1,
      "decision": "APPROVE",
      "benefit_category": "OFFICE_VISIT_SPECIALIST",
      "criteria": [],
      "reasons": [],
      "missing_information": []
    },
    {
      "line_no": 2,
      "decision": "APPROVE",
      "benefit_category": "PAIN_MANAGEMENT",
      "criteria": [
        {
          "criterion_id": "POL-PAIN-001.c4",
          "status": "MET",
          "evidence": "Fluoro-guided w/ contrast, single level."
        },
        {
          "criterion_id": "POL-PAIN-001.c1",
          "status": "MET",
          "evidence": "MRI: L4-L5 HNP compressing right L5 root; concordant w/ exam."
        },
        {
          "criterion_id": "POL-PAIN-001.c5",
          "status": "MET",
          "evidence": "Prior ESI 3 mo ago: 63% relief x3 mo."
        },
        {
          "criterion_id": "POL-PAIN-001.c2",
          "status": "NOT_APPLICABLE",
          "evidence": "Does not apply to this service."
        },
        {
          "criterion_id": "POL-PAIN-001.c3",
          "status": "NOT_APPLICABLE",
          "evidence": "Does not apply to this service."
        }
      ],
      "reasons": [],
      "missing_information": []
    }
  ],
  "complexity": "LOW"
}
```

## DEC-TR-00098 (train, office_same_day)

```text
CLAIM
Claim ID: CLM-TR-00097
Patient: 78-year-old, sex M
Plan: PLN-PPO-SILVER (PPO); provider network: IN_NETWORK
Diagnoses:
  A. H25.12 Age-related nuclear cataract, left eye
Service lines:
  1. 2026-10-10 | POS 11 | 99212 Office visit for an existing patient, simple problem | modifiers: none | units 1 | diagnoses: A
  2. 2026-10-10 | POS 24 | 66984 Cataract removal with lens implant, routine case | modifiers: none | units 1 | diagnoses: A
Clinical notes:
  The patient is seen for cataract surgery planning. Glare and blurred vision in the right eye make night driving and reading hard, and vision is 20/50 even with new glasses; other eye diseases were ruled out. The patient describes daily problems caused by the cataract, not only a finding on exam. The visit included a history, a focused exam and a discussion of treatment options. Plan: cataract removal with lens implant, routine case. The patient understands the plan and wants to go ahead.

RULES_RESULT
Claim outcome: PASS
Line 1: DENIED by rule (DN_NCCI_BUNDLED); do not decide this line
Line 2: PASS

PLAN_BENEFITS
Excluded procedure codes: 64635
Line 2 (66984) candidate categories:
  - OUTPATIENT_SURGERY: covered; prior authorization required; no visit limit; cost share DEDUCTIBLE_COINSURANCE

COVERAGE_CRITERIA
Line 2 (66984):
  Policy POL-SURG-001 Cataract surgery (covers 66982, 66984):
    [POL-SURG-001.c1] Surgery is covered when the cataract causes symptoms of impaired vision that cannot be corrected with a tolerable change in glasses or contact lenses, and that limits activities such as reading, watching television, driving, or work and hobbies. Other eye diseases must be ruled out as the main cause. (LCD L33558 v33, Indications and limitations.)
    [POL-SURG-001.c3] It is also covered when the cataract prevents monitoring or treatment of another eye disease (such as diabetic retinopathy), interferes with retinal surgery, causes lens-induced disease threatening vision, or leaves an intolerable difference between the eyes after surgery on the other eye. (LCD L33558 v33, Indications and limitations.)
    [POL-SURG-001.c2] Surgery is not medically necessary based only on clouding of the lens without symptoms. (LCD L33558 v33, Indications and limitations.)

LINES TO DECIDE: 2
```

Target answer:

```json
{
  "lines": [
    {
      "line_no": 2,
      "decision": "APPROVE",
      "benefit_category": "OUTPATIENT_SURGERY",
      "criteria": [
        {
          "criterion_id": "POL-SURG-001.c1",
          "status": "MET",
          "evidence": "Glare and blurred vision in the right eye make night driving and reading hard, and vision is 20/50 even with new glasses; other eye diseases were ruled out."
        },
        {
          "criterion_id": "POL-SURG-001.c3",
          "status": "NOT_APPLICABLE",
          "evidence": "Does not apply to this service."
        },
        {
          "criterion_id": "POL-SURG-001.c2",
          "status": "MET",
          "evidence": "The patient describes daily problems caused by the cataract, not only a finding on exam."
        }
      ],
      "reasons": [],
      "missing_information": []
    }
  ],
  "complexity": "HIGH"
}
```

## DEC-TR-01166 (train, office_visit)

```text
CLAIM
Claim ID: CLM-TR-01165
Patient: 28-year-old, sex M
Plan: PLN-PPO-GOLD (PPO); provider network: IN_NETWORK
Diagnoses:
  A. J30.1 Allergic rhinitis due to pollen
Service lines:
  1. 2026-10-12 | POS 11 | 99203 Office visit for a new patient, low-complexity problem | modifiers: none | units 1 | diagnoses: A
Clinical notes:
  Sneezing and itchy eyes return every spring when trees are in bloom. Allergies: none known. The visit included a history, a focused exam and a discussion of treatment options.

RULES_RESULT
Claim outcome: PASS
Line 1: PASS

PLAN_BENEFITS
Excluded procedure codes: none
Line 1 (99203) candidate categories:
  - OFFICE_VISIT_PCP: covered; prior authorization not required; no visit limit; cost share COPAY

COVERAGE_CRITERIA
Line 1 (99203):
  No criteria retrieved.

LINES TO DECIDE: 1
```

Target answer:

```json
{
  "lines": [
    {
      "line_no": 1,
      "decision": "APPROVE",
      "benefit_category": "OFFICE_VISIT_PCP",
      "criteria": [],
      "reasons": [],
      "missing_information": []
    }
  ],
  "complexity": "LOW"
}
```

## DEC-TR-00504 (train, pend_missing)

```text
CLAIM
Claim ID: CLM-TR-00503
Patient: 34-year-old, sex M
Plan: PLN-PPO-GOLD (PPO); provider network: IN_NETWORK
Diagnoses:
  A. M54.12 Radiculopathy, cervical region
Service lines:
  1. 2026-11-28 | POS 11 | 72141 MRI of the neck (cervical) spine without contrast | modifiers: none | units 1 | diagnoses: A
Clinical notes:
  The patient has neck and arm symptoms. Vital signs are stable. Plan: mRI of the neck (cervical) spine without contrast. Current medications were reviewed and updated.

RULES_RESULT
Claim outcome: PASS
Line 1: PASS

PLAN_BENEFITS
Excluded procedure codes: none
Line 1 (72141) candidate categories:
  - ADVANCED_IMAGING: covered; prior authorization required; no visit limit; cost share DEDUCTIBLE_COINSURANCE

COVERAGE_CRITERIA
Line 1 (72141):
  Policy POL-IMG-001 CT and MRI of the head and neck (covers 70450, 70551, 70553, 72141):
    [POL-IMG-001.c2] For headache or dizziness, imaging is covered only with a focal neurological finding, a significant change in symptoms, a head injury where bleeding must be ruled out, a headache lasting more than two weeks that has not responded to treatment, or a sudden, severe headache. (LCD L37373 v41, CT section, headache indications.)
    [POL-IMG-001.c3] Scans with contrast need a documented reason, such as characterizing a specific lesion, suspected stroke, tumor or infection, or cancer staging. More than one contrast scan per episode of illness is not covered except for stroke, TIA, non-traumatic bleeding, post-operative checks, or a known brain tumor with new neurological change. (LCD L37373 v41, CT section, contrast indications.)
    [POL-IMG-001.c1] CT or MRI of the head or neck is covered when the scan is medically appropriate for the patient's documented symptoms and provisional diagnosis. Symptoms recorded on the claim and in the notes must support the scan as ordered. (LCD L37373 v41, CT section, general indications.)
    [POL-IMG-001.c4] Brain imaging to stage a cancer without neurological symptoms is not covered for cancers that rarely spread to the brain: esophagus, oropharynx, prostate and non-melanoma skin cancer. (LCD L37373 v41, MRI section, cancer staging.)

LINES TO DECIDE: 1
```

Target answer:

```json
{
  "lines": [
    {
      "line_no": 1,
      "decision": "PEND",
      "benefit_category": "ADVANCED_IMAGING",
      "criteria": [
        {
          "criterion_id": "POL-IMG-001.c2",
          "status": "NOT_APPLICABLE",
          "evidence": "Does not apply to this service."
        },
        {
          "criterion_id": "POL-IMG-001.c3",
          "status": "NOT_APPLICABLE",
          "evidence": "Does not apply to this service."
        },
        {
          "criterion_id": "POL-IMG-001.c1",
          "status": "NOT_DOCUMENTED",
          "evidence": "Not documented in the clinical notes."
        },
        {
          "criterion_id": "POL-IMG-001.c4",
          "status": "NOT_APPLICABLE",
          "evidence": "Does not apply to this service."
        }
      ],
      "reasons": [
        "PD_MISSING_DOCUMENTATION"
      ],
      "missing_information": [
        "Symptoms and provisional diagnosis that support the scan as ordered"
      ]
    }
  ],
  "complexity": "MEDIUM"
}
```

## DEC-TR-01115 (train, rule_denied_line)

```text
CLAIM
Claim ID: CLM-TR-01114
Patient: 76-year-old, sex M
Plan: PLN-PPO-GOLD (PPO); provider network: IN_NETWORK
Diagnoses:
  A. M54.16 Radiculopathy, lumbar region
Service lines:
  1. 2026-10-16 | POS 11 | 97530 Functional movement activities to improve daily tasks, each 15 minutes | modifiers: none | units 3 | diagnoses: A
  2. 2026-10-16 | POS 11 | 97110 Therapeutic exercise to build strength, flexibility or endurance, each 15 minutes | modifiers: none | units 9 | diagnoses: A
Clinical notes:
  The patient continues outpatient physical therapy. Current medications were reviewed and updated. Past medical history was reviewed without changes. A written plan of care from the evaluation sets goals: climb stairs without pain. Function improved from 44 to 66 on the patient-specific function scale over 5 weeks, and more gains are expected. Plan: functional movement activities to improve daily tasks, each 15 minutes.

RULES_RESULT
Claim outcome: PASS
Line 1: PASS
Line 2: DENIED by rule (DN_MUE_EXCEEDED); do not decide this line

PLAN_BENEFITS
Excluded procedure codes: none
Line 1 (97530) candidate categories:
  - REHAB_THERAPY: covered; prior authorization not required; visit limit 30 per year, 3 used; cost share COPAY

COVERAGE_CRITERIA
Line 1 (97530):
  Policy POL-REHAB-001 Outpatient physical therapy (covers 97110, 97140, 97161, 97162, 97530):
    [POL-REHAB-001.c2] Treatment must follow a plan of care with specific goals, developed from an examination and evaluation. (LCD L34428 v93, Plan of care.)
    [POL-REHAB-001.c3] Restorative therapy requires a reasonable potential for improvement from the services. Maintenance programs must meet the Medicare Benefit Policy Manual, Chapter 15, Section 220 criteria. (LCD L34428 v93, Restorative and maintenance therapy.)
    [POL-REHAB-001.c1] Services must be complex enough to need the skills of a qualified physical therapist, or be given under a physical therapist's supervision. (LCD L34428 v93, General physical therapy guidelines.)

LINES TO DECIDE: 1
```

Target answer:

```json
{
  "lines": [
    {
      "line_no": 1,
      "decision": "PEND",
      "benefit_category": "REHAB_THERAPY",
      "criteria": [
        {
          "criterion_id": "POL-REHAB-001.c2",
          "status": "MET",
          "evidence": "A written plan of care from the evaluation sets goals: climb stairs without pain."
        },
        {
          "criterion_id": "POL-REHAB-001.c3",
          "status": "MET",
          "evidence": "Function improved from 44 to 66 on the patient-specific function scale over 5 weeks, and more gains are expected."
        },
        {
          "criterion_id": "POL-REHAB-001.c1",
          "status": "NOT_DOCUMENTED",
          "evidence": "Not documented in the clinical notes."
        }
      ],
      "reasons": [
        "PD_MISSING_DOCUMENTATION"
      ],
      "missing_information": [
        "Why the services need a physical therapist's skills"
      ]
    }
  ],
  "complexity": "HIGH"
}
```

## DEC-TR-00964 (train, same_profile_multi)

```text
CLAIM
Claim ID: CLM-TR-00963
Patient: 33-year-old, sex M
Plan: PLN-HMO (HMO); provider network: IN_NETWORK
Diagnoses:
  A. J45.30 Mild persistent asthma, uncomplicated
Service lines:
  1. 2026-11-12 | POS 11 | 95004 Skin prick allergy tests, per allergen | modifiers: none | units 23 | diagnoses: A
  2. 2026-11-12 | POS 11 | 95024 Allergy tests injected just under the skin, per allergen | modifiers: none | units 15 | diagnoses: A
Clinical notes:
  The patient is seen in the allergy clinic. The 23 allergens tested were chosen from the patient's exposures at home and work. Plan: skin prick allergy tests, per allergen; allergy tests injected just under the skin, per allergen. Vital signs are stable. Current medications were reviewed and updated.

RULES_RESULT
Claim outcome: PASS
Line 1: PASS
Line 2: PASS

PLAN_BENEFITS
Excluded procedure codes: 95044
Line 1 (95004) candidate categories:
  - DIAGNOSTIC_TESTS: covered; prior authorization required; no visit limit; cost share DEDUCTIBLE_COINSURANCE
Line 2 (95024) candidate categories:
  - DIAGNOSTIC_TESTS: covered; prior authorization required; no visit limit; cost share DEDUCTIBLE_COINSURANCE

COVERAGE_CRITERIA
Line 1 (95004):
  Policy POL-DX-003 Allergy testing (covers 95004, 95024, 95044):
    [POL-DX-003.c3] The tests chosen must match the patient's history and physical findings, and the number of tests must be justified. Guideline limits for an initial evaluation are about 70 prick and 40 intradermal tests for airborne allergens, or up to 80 patch tests. (LCD L33261 v40, Covered indications, number of tests.)
    [POL-DX-003.c1] Skin prick and intradermal tests are covered to evaluate IgE-mediated allergy to airborne allergens, foods, stinging-insect venom, certain drugs or chemicals, when the tests are correlated with the patient's history and examination. (LCD L33261 v40, Covered indications, section A.)
    [POL-DX-003.c2] Patch testing is covered for suspected allergic contact dermatitis, or other dermatitis where a contact allergen is the likely cause. (LCD L33261 v40, Covered indications, section A.)
Line 2 (95024):
  Policy POL-DX-003 Allergy testing (covers 95004, 95024, 95044):
    [POL-DX-003.c3] The tests chosen must match the patient's history and physical findings, and the number of tests must be justified. Guideline limits for an initial evaluation are about 70 prick and 40 intradermal tests for airborne allergens, or up to 80 patch tests. (LCD L33261 v40, Covered indications, number of tests.)
    [POL-DX-003.c1] Skin prick and intradermal tests are covered to evaluate IgE-mediated allergy to airborne allergens, foods, stinging-insect venom, certain drugs or chemicals, when the tests are correlated with the patient's history and examination. (LCD L33261 v40, Covered indications, section A.)
    [POL-DX-003.c2] Patch testing is covered for suspected allergic contact dermatitis, or other dermatitis where a contact allergen is the likely cause. (LCD L33261 v40, Covered indications, section A.)

LINES TO DECIDE: 1, 2
```

Target answer:

```json
{
  "lines": [
    {
      "line_no": 1,
      "decision": "PEND",
      "benefit_category": "DIAGNOSTIC_TESTS",
      "criteria": [
        {
          "criterion_id": "POL-DX-003.c3",
          "status": "MET",
          "evidence": "The 23 allergens tested were chosen from the patient's exposures at home and work."
        },
        {
          "criterion_id": "POL-DX-003.c1",
          "status": "NOT_DOCUMENTED",
          "evidence": "Not documented in the clinical notes."
        },
        {
          "criterion_id": "POL-DX-003.c2",
          "status": "NOT_APPLICABLE",
          "evidence": "Does not apply to this service."
        }
      ],
      "reasons": [
        "PD_MISSING_DOCUMENTATION"
      ],
      "missing_information": [
        "History that links the symptoms to allergen exposure"
      ]
    },
    {
      "line_no": 2,
      "decision": "PEND",
      "benefit_category": "DIAGNOSTIC_TESTS",
      "criteria": [
        {
          "criterion_id": "POL-DX-003.c3",
          "status": "MET",
          "evidence": "The 23 allergens tested were chosen from the patient's exposures at home and work."
        },
        {
          "criterion_id": "POL-DX-003.c1",
          "status": "NOT_DOCUMENTED",
          "evidence": "Not documented in the clinical notes."
        },
        {
          "criterion_id": "POL-DX-003.c2",
          "status": "NOT_APPLICABLE",
          "evidence": "Does not apply to this service."
        }
      ],
      "reasons": [
        "PD_MISSING_DOCUMENTATION"
      ],
      "missing_information": [
        "History that links the symptoms to allergen exposure"
      ]
    }
  ],
  "complexity": "MEDIUM"
}
```

## DEC-TR-01407 (train, two_policy)

```text
CLAIM
Claim ID: CLM-TR-01406
Patient: 79-year-old, sex F
Plan: PLN-PPO-GOLD (PPO); provider network: IN_NETWORK
Diagnoses:
  A. M54.16 Radiculopathy, lumbar region
  B. M47.896 Other spondylosis, lumbar region
Service lines:
  1. 2026-11-17 | POS 22 | 62323 Epidural steroid injection between the vertebrae, lower back, with imaging guidance | modifiers: none | units 1 | diagnoses: A
  2. 2026-11-27 | POS 11 | 64635 Radiofrequency destruction of facet joint nerves, lower back, first joint | modifiers: none | units 1 | diagnoses: B
Clinical notes:
  The patient has low back pain that travels down the left leg. Imaging shows narrowing at L5-S1 with pressure on the S1 nerve root, which fits the pain pattern on exam. The patient rates pain 7/10 and cannot work a full day; Oswestry score 41%. 11 weeks of physical therapy and medication have not helped. The patient has chronic low back pain. Pain is mainly in the low back itself, 9/10, worse with bending back and twisting, with a disability score of 47%. Current medications were reviewed and updated. Vital signs are stable. Pain has lasted 4 months despite physical therapy and medication. There is no pain or numbness down the limbs, and imaging shows no fracture, tumor or infection. Plan: epidural steroid injection between the vertebrae, lower back, with imaging guidance; radiofrequency destruction of facet joint nerves, lower back, first joint.

RULES_RESULT
Claim outcome: PASS
Line 1: PASS
Line 2: PASS

PLAN_BENEFITS
Excluded procedure codes: none
Line 1 (62323) candidate categories:
  - PAIN_MANAGEMENT: covered; prior authorization required; no visit limit; cost share DEDUCTIBLE_COINSURANCE
Line 2 (64635) candidate categories:
  - PAIN_MANAGEMENT: covered; prior authorization required; no visit limit; cost share DEDUCTIBLE_COINSURANCE

COVERAGE_CRITERIA
Line 1 (62323):
  Policy POL-PAIN-001 Epidural steroid injections (covers 62321, 62323, 64483):
    [POL-PAIN-001.c1] History, examination and matching imaging must support nerve-root pain (radiculopathy) or neurogenic claudication from a disc herniation, bone spurs or severe disc degeneration narrowing the spinal canal or nerve openings; or pain after spinal surgery (post-laminectomy syndrome); or acute shingles pain. (LCD L33906 v75, Covered indications.)
    [POL-PAIN-001.c2] The pain must be severe enough to greatly affect quality of life or function, measured with an objective pain or function scale before treatment. (LCD L33906 v75, Covered indications.)
    [POL-PAIN-001.c5] A repeat injection requires documented improvement of at least 50% in pain lasting at least 3 months, or at least 50% improvement in function, compared with the baseline scale. (LCD L33906 v75, Covered indications, repeat injections.)
    [POL-PAIN-001.c4] Injections must be done under CT or fluoroscopic guidance with contrast, unless there is a documented contrast allergy or pregnancy. Interlaminar injections are limited to one level, and transforaminal injections to two levels in one spinal region. (LCD L33906 v75, Covered indications, technique and levels.)
    [POL-PAIN-001.c3] The pain must have lasted at least 4 weeks, with failure of, or inability to tolerate, 4 weeks of non-invasive conservative care. Acute shingles pain that does not respond to conservative care is exempt from the 4-week wait. (LCD L33906 v75, Covered indications.)
Line 2 (64635):
  Policy POL-PAIN-002 Facet joint injections and nerve ablation (covers 64490, 64493, 64635):
    [POL-PAIN-002.c1] The patient must have moderate to severe chronic neck or low back pain, mainly in the spine itself (axial), causing a functional deficit measured on a pain or disability scale. (LCD L33930 v49, Covered indications.)
    [POL-PAIN-002.c3] There must be no untreated nerve-root pain or neurogenic claudication (except from a facet joint cyst), and no other cause of the pain such as fracture, tumor, infection or major deformity. (LCD L33930 v49, Covered indications.)
    [POL-PAIN-002.c2] The pain must have lasted at least 3 months, with documented failure of non-invasive conservative care. (LCD L33930 v49, Covered indications.)
    [POL-PAIN-002.c4] Diagnostic facet procedures are done with the intent of proceeding to radiofrequency ablation at that level if they succeed. A second, confirming diagnostic procedure at the same level must be at least 2 weeks after the first. (LCD L33930 v49, Section A, diagnostic procedures.)

LINES TO DECIDE: 1, 2
```

Target answer:

```json
{
  "lines": [
    {
      "line_no": 1,
      "decision": "APPROVE",
      "benefit_category": "PAIN_MANAGEMENT",
      "criteria": [
        {
          "criterion_id": "POL-PAIN-001.c1",
          "status": "MET",
          "evidence": "Imaging shows narrowing at L5-S1 with pressure on the S1 nerve root, which fits the pain pattern on exam."
        },
        {
          "criterion_id": "POL-PAIN-001.c2",
          "status": "MET",
          "evidence": "The patient rates pain 7/10 and cannot work a full day; Oswestry score 41%."
        },
        {
          "criterion_id": "POL-PAIN-001.c5",
          "status": "NOT_APPLICABLE",
          "evidence": "Does not apply to this service."
        },
        {
          "criterion_id": "POL-PAIN-001.c4",
          "status": "NOT_APPLICABLE",
          "evidence": "Does not apply to this service."
        },
        {
          "criterion_id": "POL-PAIN-001.c3",
          "status": "MET",
          "evidence": "11 weeks of physical therapy and medication have not helped."
        }
      ],
      "reasons": [],
      "missing_information": []
    },
    {
      "line_no": 2,
      "decision": "APPROVE",
      "benefit_category": "PAIN_MANAGEMENT",
      "criteria": [
        {
          "criterion_id": "POL-PAIN-002.c1",
          "status": "MET",
          "evidence": "Pain is mainly in the low back itself, 9/10, worse with bending back and twisting, with a disability score of 47%."
        },
        {
          "criterion_id": "POL-PAIN-002.c3",
          "status": "MET",
          "evidence": "There is no pain or numbness down the limbs, and imaging shows no fracture, tumor or infection."
        },
        {
          "criterion_id": "POL-PAIN-002.c2",
          "status": "MET",
          "evidence": "Pain has lasted 4 months despite physical therapy and medication."
        },
        {
          "criterion_id": "POL-PAIN-002.c4",
          "status": "NOT_APPLICABLE",
          "evidence": "Does not apply to this service."
        }
      ],
      "reasons": [],
      "missing_information": []
    }
  ],
  "complexity": "MEDIUM"
}
```

## DEC-TR-01236 (train, approve_single)

```text
CLAIM
Claim ID: CLM-TR-01235
Patient: 74-year-old, sex F
Plan: PLN-HDHP (PPO); provider network: IN_NETWORK
Diagnoses:
  A. L97.412 Non-pressure chronic ulcer of right heel and midfoot with fat layer exposed
Service lines:
  1. 2026-10-19 | POS 11 | 97597 Selective removal of dead tissue from an open wound, first 20 square cm or less | modifiers: none | units 1 | diagnoses: A
Clinical notes:
  The patient is seen in the wound clinic for a foot ulcer. Dead tissue was cut away from a 4 cm ulcer on the right heel down to the fat layer, with the patient seen one on one. Vital signs are stable. Current medications were reviewed and updated. The care plan covers off-loading, infection control and blood-sugar management to help the wound close. Plan: selective removal of dead tissue from an open wound, first 20 square cm or less.

RULES_RESULT
Claim outcome: PASS
Line 1: PASS

PLAN_BENEFITS
Excluded procedure codes: none
Line 1 (97597) candidate categories:
  - MINOR_PROCEDURES: covered; prior authorization not required; no visit limit; cost share DEDUCTIBLE_COINSURANCE

COVERAGE_CRITERIA
Line 1 (97597):
  Policy POL-WOUND-001 Wound and ulcer care (covers 11042, 97597, 29581):
    [POL-WOUND-001.c1] Active wound care (debridement) is covered to remove dead tissue and promote healing, performed with direct one-on-one patient contact, following accepted standards of wound treatment. (LCD L38902 v12, Indications.)
    [POL-WOUND-001.c2] Care must be part of a plan that addresses complicating factors (pressure off-loading, infection, poor circulation, metabolic or nutritional problems), aiming at wound closure or, when healing is not possible, preventing the wound from getting worse. (LCD L38902 v12, Indications.)
    [POL-WOUND-001.c3] How often debridement is done depends on the wound. Frequent repeated debridement requires a documented reassessment of the treatment plan. (LCD L38902 v12, Indications, frequency.)

LINES TO DECIDE: 1
```

Target answer:

```json
{
  "lines": [
    {
      "line_no": 1,
      "decision": "APPROVE",
      "benefit_category": "MINOR_PROCEDURES",
      "criteria": [
        {
          "criterion_id": "POL-WOUND-001.c1",
          "status": "MET",
          "evidence": "Dead tissue was cut away from a 4 cm ulcer on the right heel down to the fat layer, with the patient seen one on one."
        },
        {
          "criterion_id": "POL-WOUND-001.c2",
          "status": "MET",
          "evidence": "The care plan covers off-loading, infection control and blood-sugar management to help the wound close."
        },
        {
          "criterion_id": "POL-WOUND-001.c3",
          "status": "NOT_APPLICABLE",
          "evidence": "Does not apply to this service."
        }
      ],
      "reasons": [],
      "missing_information": []
    }
  ],
  "complexity": "LOW"
}
```

## DEC-TR-01076 (train, deny_criterion)

```text
CLAIM
Claim ID: CLM-TR-01075
Patient: 48-year-old, sex M
Plan: PLN-HDHP (PPO); provider network: IN_NETWORK
Diagnoses:
  A. R41.89 Other symptoms and signs involving cognitive functions and awareness
Service lines:
  1. 2026-10-22 | POS 11 | 96130 Psychological test evaluation by a psychologist or physician, first hour | modifiers: none | units 1 | diagnoses: A
Clinical notes:
  The patient is referred for psychological testing. The diagnosis is already clear, and the results would not change the treatment plan. Testing uses standardized tests given and scored by the psychologist. Plan: psychological test evaluation by a psychologist or physician, first hour. Current medications were reviewed and updated.

RULES_RESULT
Claim outcome: PASS
Line 1: PASS

PLAN_BENEFITS
Excluded procedure codes: none
Line 1 (96130) candidate categories:
  - MENTAL_HEALTH_OUTPATIENT: covered; prior authorization not required; no visit limit; cost share DEDUCTIBLE_COINSURANCE

COVERAGE_CRITERIA
Line 1 (96130):
  Policy POL-BH-001 Psychological and neuropsychological testing (covers 96130, 96131, 96136):
    [POL-BH-001.c1] Testing is covered when brain or psychological involvement is known or suspected and the results will affect diagnosis, treatment planning or management. An example is telling dementia or brain injury apart from depression when the diagnosis is still uncertain after examination. (LCD L34520 v32, Indications.)
    [POL-BH-001.c2] Testing is not covered when no problem with brain or emotional function is suspected, when it consists only of self-administered or self-scored screening tools, or when it is repeated without being needed for a medical decision. (LCD L34520 v32, Limitations.)
    [POL-BH-001.c3] Routine re-evaluation of chronically disabled patients that is not needed for diagnosis or continued treatment is not medically necessary. (LCD L34520 v32, Limitations.)

LINES TO DECIDE: 1
```

Target answer:

```json
{
  "lines": [
    {
      "line_no": 1,
      "decision": "DENY",
      "benefit_category": "MENTAL_HEALTH_OUTPATIENT",
      "criteria": [
        {
          "criterion_id": "POL-BH-001.c1",
          "status": "NOT_MET",
          "evidence": "The diagnosis is already clear, and the results would not change the treatment plan."
        },
        {
          "criterion_id": "POL-BH-001.c2",
          "status": "MET",
          "evidence": "Testing uses standardized tests given and scored by the psychologist."
        },
        {
          "criterion_id": "POL-BH-001.c3",
          "status": "NOT_APPLICABLE",
          "evidence": "Does not apply to this service."
        }
      ],
      "reasons": [
        "DN_NOT_MEDICALLY_NECESSARY"
      ],
      "missing_information": []
    }
  ],
  "complexity": "MEDIUM"
}
```

## DEC-TE-00249 (test, deny_dx)

```text
CLAIM
Claim ID: CLM-TE-00248
Patient: 75-year-old, sex F
Plan: PLN-HDHP (PPO); provider network: IN_NETWORK
Diagnoses:
  A. F41.9 Anxiety disorder, unspecified
Service lines:
  1. 2026-11-08 | POS 11 | 97530 Functional movement activities to improve daily tasks, each 15 minutes | modifiers: none | units 3 | diagnoses: A
Clinical notes:
  Anxiety sx x months, poor sleep. NKDA. Plan -> functional movement activities to improve daily tasks, each 15 minutes. Meds reconciled.

RULES_RESULT
Claim outcome: PASS
Line 1: PASS

PLAN_BENEFITS
Excluded procedure codes: none
Line 1 (97530) candidate categories:
  - REHAB_THERAPY: covered; prior authorization not required; visit limit 20 per year, 0 used; cost share DEDUCTIBLE_COINSURANCE

COVERAGE_CRITERIA
Line 1 (97530):
  Policy POL-REHAB-001 Outpatient physical therapy (covers 97110, 97140, 97161, 97162, 97530):
    [POL-REHAB-001.c2] Treatment must follow a plan of care with specific goals, developed from an examination and evaluation. (LCD L34428 v93, Plan of care.)
    [POL-REHAB-001.c3] Restorative therapy requires a reasonable potential for improvement from the services. Maintenance programs must meet the Medicare Benefit Policy Manual, Chapter 15, Section 220 criteria. (LCD L34428 v93, Restorative and maintenance therapy.)
    [POL-REHAB-001.c1] Services must be complex enough to need the skills of a qualified physical therapist, or be given under a physical therapist's supervision. (LCD L34428 v93, General physical therapy guidelines.)

LINES TO DECIDE: 1
```

Target answer:

```json
{
  "lines": [
    {
      "line_no": 1,
      "decision": "DENY",
      "benefit_category": "REHAB_THERAPY",
      "criteria": [
        {
          "criterion_id": "POL-REHAB-001.c2",
          "status": "NOT_MET",
          "evidence": "Anxiety sx x months, poor sleep."
        },
        {
          "criterion_id": "POL-REHAB-001.c3",
          "status": "NOT_DOCUMENTED",
          "evidence": "Not documented in the clinical notes."
        },
        {
          "criterion_id": "POL-REHAB-001.c1",
          "status": "NOT_DOCUMENTED",
          "evidence": "Not documented in the clinical notes."
        }
      ],
      "reasons": [
        "DN_NOT_MEDICALLY_NECESSARY"
      ],
      "missing_information": []
    }
  ],
  "complexity": "MEDIUM"
}
```

## DEC-TR-01976 (train, deny_exclusion)

```text
CLAIM
Claim ID: CLM-TR-01975
Patient: 73-year-old, sex F
Plan: PLN-HMO (HMO); provider network: IN_NETWORK
Diagnoses:
  A. H02.834 Dermatochalasis of left upper eyelid
Service lines:
  1. 2026-10-13 | POS 11 | 15822 Upper eyelid surgery (blepharoplasty) | modifiers: none | units 1 | diagnoses: A
Clinical notes:
  The patient is seen about drooping upper eyelids. The patient has no vision complaints. Allergies: none known. Visual fields are full, with only 2 degrees of upper loss. The patient wants surgery to look less tired. Plan: upper eyelid surgery (blepharoplasty).

RULES_RESULT
Claim outcome: PASS
Line 1: PASS

PLAN_BENEFITS
Excluded procedure codes: 95044
Line 1 (15822) candidate categories:
  - OUTPATIENT_SURGERY: covered; prior authorization required; no visit limit; cost share DEDUCTIBLE_COINSURANCE

COVERAGE_CRITERIA
Line 1 (15822):
  Policy POL-SURG-004 Eyelid surgery (blepharoplasty and ptosis repair) (covers 15822, 15823, 67904):
    [POL-SURG-004.c1] Eyelid surgery is reconstructive (covered) when it corrects visual impairment caused by excess eyelid skin weighing down the lashes (dermatochalasis), blepharochalasis, drooping of the eyelid (blepharoptosis) or drooping of the brow. (LCD L33944 v27, Indications and limitations.)
    [POL-SURG-004.c3] Visual field testing must show a significant loss of upper vision (at least 12 degrees or 30 percent) that the surgery could correct. (LCD L33944 v27, Indications and limitations, visual fields.)
    [POL-SURG-004.c2] The record must document the patient's complaints of functional problems: vision blocked above or to the side, trouble reading because the upper field is lost, or looking through the eyelashes or seeing eyelid skin. (LCD L33944 v27, Indications and limitations, documentation.)
    [POL-SURG-004.c4] Without documented functional impairment, eyelid surgery is considered cosmetic and is not covered. (LCD L33944 v27, Indications and limitations.)

LINES TO DECIDE: 1
```

Target answer:

```json
{
  "lines": [
    {
      "line_no": 1,
      "decision": "DENY",
      "benefit_category": "OUTPATIENT_SURGERY",
      "criteria": [
        {
          "criterion_id": "POL-SURG-004.c1",
          "status": "NOT_APPLICABLE",
          "evidence": "Does not apply to this service."
        },
        {
          "criterion_id": "POL-SURG-004.c3",
          "status": "NOT_MET",
          "evidence": "Visual fields are full, with only 2 degrees of upper loss."
        },
        {
          "criterion_id": "POL-SURG-004.c2",
          "status": "NOT_MET",
          "evidence": "The patient has no vision complaints."
        },
        {
          "criterion_id": "POL-SURG-004.c4",
          "status": "NOT_MET",
          "evidence": "The patient wants surgery to look less tired."
        }
      ],
      "reasons": [
        "DN_CONDITIONAL_EXCLUSION"
      ],
      "missing_information": []
    }
  ],
  "complexity": "HIGH"
}
```

## DEC-TR-01021 (train, ncci_bypass)

```text
CLAIM
Claim ID: CLM-TR-01020
Patient: 77-year-old, sex F
Plan: PLN-PPO-GOLD (PPO); provider network: IN_NETWORK
Diagnoses:
  A. R19.5 Other fecal abnormalities
Service lines:
  1. 2026-10-07 | POS 24 | 45385 Colonoscopy with polyp removal using a wire snare | modifiers: none | units 1 | diagnoses: A
  2. 2026-10-07 | POS 22 | 45380 Colonoscopy with tissue sample (biopsy) | modifiers: XS | units 1 | diagnoses: A
Clinical notes:
  The patient is seen for a colonoscopy. Allergies: none known. The patient understands the plan and wants to go ahead. Plan: colonoscopy with polyp removal using a wire snare; colonoscopy with tissue sample (biopsy).

RULES_RESULT
Claim outcome: PASS
Line 1: PASS
Line 2: PASS, flag NCCI_BYPASS (a bypass modifier was used; check that the notes show a separate, distinct service)

PLAN_BENEFITS
Excluded procedure codes: none
Line 1 (45385) candidate categories:
  - ENDOSCOPY: covered; prior authorization not required; no visit limit; cost share DEDUCTIBLE_COINSURANCE
  - PREVENTIVE_CARE: covered; prior authorization not required; no visit limit; cost share COPAY
Line 2 (45380) candidate categories:
  - ENDOSCOPY: covered; prior authorization not required; no visit limit; cost share DEDUCTIBLE_COINSURANCE
  - PREVENTIVE_CARE: covered; prior authorization not required; no visit limit; cost share COPAY

COVERAGE_CRITERIA
Line 1 (45385):
  Policy POL-SURG-002 Colonoscopy (covers 45378, 45380, 45385):
    [POL-SURG-002.c1] Colonoscopy to investigate symptoms is covered for an imaging abnormality likely to be significant; unexplained bleeding (blood in the stool not from a rectal source, black tarry stool, or a positive stool blood test); unexplained iron-deficiency anemia; or significant unexplained diarrhea with other findings such as weight loss. (LCD L34005 v34, Indications.)
    [POL-SURG-002.c2] Surveillance is covered for a history of colorectal cancer or polyps, follow-up one year after colorectal cancer surgery, follow-up after removal of a large polyp, and inflammatory bowel disease surveillance (pancolitis for more than 7 years, or left-sided colitis for more than 15 years). (LCD L34005 v34, Indications.)
    [POL-SURG-002.c3] Patients identified as high risk for colon cancer are eligible for continued screening every 24 months. (LCD L34005 v34, Indications.)
Line 2 (45380):
  Policy POL-SURG-002 Colonoscopy (covers 45378, 45380, 45385):
    [POL-SURG-002.c1] Colonoscopy to investigate symptoms is covered for an imaging abnormality likely to be significant; unexplained bleeding (blood in the stool not from a rectal source, black tarry stool, or a positive stool blood test); unexplained iron-deficiency anemia; or significant unexplained diarrhea with other findings such as weight loss. (LCD L34005 v34, Indications.)
    [POL-SURG-002.c2] Surveillance is covered for a history of colorectal cancer or polyps, follow-up one year after colorectal cancer surgery, follow-up after removal of a large polyp, and inflammatory bowel disease surveillance (pancolitis for more than 7 years, or left-sided colitis for more than 15 years). (LCD L34005 v34, Indications.)
    [POL-SURG-002.c3] Patients identified as high risk for colon cancer are eligible for continued screening every 24 months. (LCD L34005 v34, Indications.)

LINES TO DECIDE: 1, 2
```

Target answer:

```json
{
  "lines": [
    {
      "line_no": 1,
      "decision": "PEND",
      "benefit_category": "ENDOSCOPY",
      "criteria": [
        {
          "criterion_id": "POL-SURG-002.c1",
          "status": "NOT_DOCUMENTED",
          "evidence": "Not documented in the clinical notes."
        },
        {
          "criterion_id": "POL-SURG-002.c2",
          "status": "NOT_APPLICABLE",
          "evidence": "Does not apply to this service."
        },
        {
          "criterion_id": "POL-SURG-002.c3",
          "status": "NOT_APPLICABLE",
          "evidence": "Does not apply to this service."
        }
      ],
      "reasons": [
        "PD_MISSING_DOCUMENTATION"
      ],
      "missing_information": [
        "The symptom or finding the colonoscopy is meant to investigate"
      ]
    },
    {
      "line_no": 2,
      "decision": "PEND",
      "benefit_category": "ENDOSCOPY",
      "criteria": [
        {
          "criterion_id": "POL-SURG-002.c1",
          "status": "NOT_DOCUMENTED",
          "evidence": "Not documented in the clinical notes."
        },
        {
          "criterion_id": "POL-SURG-002.c2",
          "status": "NOT_APPLICABLE",
          "evidence": "Does not apply to this service."
        },
        {
          "criterion_id": "POL-SURG-002.c3",
          "status": "NOT_APPLICABLE",
          "evidence": "Does not apply to this service."
        }
      ],
      "reasons": [
        "PD_MISSING_DOCUMENTATION"
      ],
      "missing_information": [
        "The symptom or finding the colonoscopy is meant to investigate",
        "Documentation that the biopsy was taken from a lesion separate from the polyp removed with the snare"
      ]
    }
  ],
  "complexity": "HIGH"
}
```

## DEC-TR-00825 (train, office_plus_procedure)

```text
CLAIM
Claim ID: CLM-TR-00824
Patient: 45-year-old, sex F
Plan: PLN-HDHP (PPO); provider network: IN_NETWORK
Diagnoses:
  A. R06.02 Shortness of breath
Service lines:
  1. 2026-11-23 | POS 11 | 99204 Office visit for a new patient, moderately complex problem | modifiers: none | units 1 | diagnoses: A
  2. 2026-12-03 | POS 11 | 93306 Complete heart ultrasound through the chest wall, including blood-flow imaging | modifiers: none | units 1 | diagnoses: A
Clinical notes:
  The patient is seen in the heart clinic. The patient has breathlessness when lying flat, and exam finds a new heart murmur, raising concern for heart muscle or valve disease. No echocardiogram has been done before. Office visit to review the problem, examine the patient and agree on next steps. Plan: complete heart ultrasound through the chest wall, including blood-flow imaging. Past medical history was reviewed without changes.

RULES_RESULT
Claim outcome: PASS
Line 1: PASS
Line 2: PASS

PLAN_BENEFITS
Excluded procedure codes: none
Line 1 (99204) candidate categories:
  - OFFICE_VISIT_SPECIALIST: covered; prior authorization not required; no visit limit; cost share DEDUCTIBLE_COINSURANCE
Line 2 (93306) candidate categories:
  - DIAGNOSTIC_TESTS: covered; prior authorization not required; no visit limit; cost share DEDUCTIBLE_COINSURANCE

COVERAGE_CRITERIA
Line 1 (99204):
  No criteria retrieved.
Line 2 (93306):
  Policy POL-CAR-001 Echocardiography (heart ultrasound) (covers 93306, 93308, 93350):
    [POL-CAR-001.c1] A transthoracic echocardiogram is covered when there are clinical signs or symptoms of heart disease or heart dysfunction, such as suspected weakening of the heart muscle, cardiomyopathy or valve disease. High blood pressure alone, without signs or symptoms of heart disease, is not a covered reason. (LCD L37379 v42, Sections A and B.)
    [POL-CAR-001.c3] Stress echocardiography is covered to evaluate suspected coronary artery disease in patients with signs or symptoms, for example after a treadmill stress test that did not give a diagnosis. (LCD L37379 v42, Stress echocardiography indications.)
    [POL-CAR-001.c2] Repeating the study more often than once a year is not medically necessary unless the notes document a clear change in signs or symptoms, a check of the response to treatment, or planned valve surgery. (LCD L37379 v42, Sections A and F, repeat studies.)

LINES TO DECIDE: 1, 2
```

Target answer:

```json
{
  "lines": [
    {
      "line_no": 1,
      "decision": "APPROVE",
      "benefit_category": "OFFICE_VISIT_SPECIALIST",
      "criteria": [],
      "reasons": [],
      "missing_information": []
    },
    {
      "line_no": 2,
      "decision": "APPROVE",
      "benefit_category": "DIAGNOSTIC_TESTS",
      "criteria": [
        {
          "criterion_id": "POL-CAR-001.c1",
          "status": "MET",
          "evidence": "The patient has breathlessness when lying flat, and exam finds a new heart murmur, raising concern for heart muscle or valve disease."
        },
        {
          "criterion_id": "POL-CAR-001.c3",
          "status": "NOT_APPLICABLE",
          "evidence": "Does not apply to this service."
        },
        {
          "criterion_id": "POL-CAR-001.c2",
          "status": "MET",
          "evidence": "No echocardiogram has been done before."
        }
      ],
      "reasons": [],
      "missing_information": []
    }
  ],
  "complexity": "LOW"
}
```

## DEC-TR-00191 (train, office_same_day)

```text
CLAIM
Claim ID: CLM-TR-00190
Patient: 63-year-old, sex M
Plan: PLN-HDHP (PPO); provider network: IN_NETWORK
Diagnoses:
  A. Z79.01 Long term (current) use of anticoagulants
  B. B35.1 Tinea unguium
Service lines:
  1. 2026-10-14 | POS 11 | 99204 Office visit for a new patient, moderately complex problem | modifiers: none | units 1 | diagnoses: A
  2. 2026-10-14 | POS 11 | 11721 Trimming and cleaning of thickened toenails, 6 or more nails | modifiers: none | units 1 | diagnoses: AB
Clinical notes:
  The patient is seen for thick toenails. Current medications were reviewed and updated. The patient takes apixaban, and a small cut during nail care could bleed heavily. Nail care by the patient or family would put the feet at risk. Office visit to review the problem, examine the patient and agree on next steps. Plan: trimming and cleaning of thickened toenails, 6 or more nails.

RULES_RESULT
Claim outcome: PASS
Line 1: DENIED by rule (DN_NCCI_BUNDLED); do not decide this line
Line 2: PASS

PLAN_BENEFITS
Excluded procedure codes: none
Line 2 (11721) candidate categories:
  - MINOR_PROCEDURES: covered; prior authorization not required; no visit limit; cost share DEDUCTIBLE_COINSURANCE

COVERAGE_CRITERIA
Line 2 (11721):
  Policy POL-FOOT-001 Routine foot care (nail debridement) (covers 11720, 11721):
    [POL-FOOT-001.c2] It is covered for patients on blood thinners when the record documents the significant risk of non-professional foot care. (LCD L33941 v23, Covered indications.)
    [POL-FOOT-001.c3] Outside these conditions, routine foot care such as nail trimming is not covered (Medicare Benefit Policy Manual, Chapter 15, Section 290, referenced by the LCD). (LCD L33941 v23, Covered indications, reference to benefit policy.)
    [POL-FOOT-001.c1] Routine foot care is covered for nerve damage in the feet (without blood-vessel impairment) severe enough that care by a non-professional would put the patient at risk. The record must document loss of protective sensation: no feeling at 2 or more of 5 sites on either foot with the 5.07 Semmes-Weinstein monofilament. (LCD L33941 v23, Covered indications.)

LINES TO DECIDE: 2
```

Target answer:

```json
{
  "lines": [
    {
      "line_no": 2,
      "decision": "APPROVE",
      "benefit_category": "MINOR_PROCEDURES",
      "criteria": [
        {
          "criterion_id": "POL-FOOT-001.c2",
          "status": "MET",
          "evidence": "The patient takes apixaban, and a small cut during nail care could bleed heavily."
        },
        {
          "criterion_id": "POL-FOOT-001.c3",
          "status": "MET",
          "evidence": "Nail care by the patient or family would put the feet at risk."
        },
        {
          "criterion_id": "POL-FOOT-001.c1",
          "status": "NOT_APPLICABLE",
          "evidence": "Does not apply to this service."
        }
      ],
      "reasons": [],
      "missing_information": []
    }
  ],
  "complexity": "HIGH"
}
```

## DEC-TR-01729 (train, office_visit)

```text
CLAIM
Claim ID: CLM-TR-01728
Patient: 19-year-old, sex F
Plan: PLN-EPO (EPO); provider network: IN_NETWORK
Diagnoses:
  A. J30.1 Allergic rhinitis due to pollen
Service lines:
  1. 2026-11-06 | POS 11 | 99212 Office visit for an existing patient, simple problem | modifiers: none | units 1 | diagnoses: A
Clinical notes:
  Sneezing and itchy eyes return every spring when trees are in bloom. Office visit to review the problem, examine the patient and agree on next steps. Allergies: none known.

RULES_RESULT
Claim outcome: PASS
Line 1: PASS

PLAN_BENEFITS
Excluded procedure codes: 97140
Line 1 (99212) candidate categories:
  - OFFICE_VISIT_PCP: covered; prior authorization not required; no visit limit; cost share COPAY

COVERAGE_CRITERIA
Line 1 (99212):
  No criteria retrieved.

LINES TO DECIDE: 1
```

Target answer:

```json
{
  "lines": [
    {
      "line_no": 1,
      "decision": "APPROVE",
      "benefit_category": "OFFICE_VISIT_PCP",
      "criteria": [],
      "reasons": [],
      "missing_information": []
    }
  ],
  "complexity": "LOW"
}
```
