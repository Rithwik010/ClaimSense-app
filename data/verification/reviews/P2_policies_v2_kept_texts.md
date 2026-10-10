# Policies v2: kept-text check

Kept-text check (2026-10-10): Claude Code, the author of the criteria, compared every v1 criterion that keeps its ID and text with its v1 source excerpt for numbers, limiting words and left-out coverage limits, in P2_policies_v2_kept_texts.md; not an independent check. Nothing in it is applied until the reviewer approves it.

The 36 v1 criteria that keep their ID and text (rows are KB plus their Part B row). Compared with the v1 source excerpt (data/curated/policy_sources.csv, checked word for word in V1b) for numbers, limiting words ('only', 'and'/'or', 'except', 'unless', 'usually' and the like, 'not covered') and coverage limits the text leaves out. Categories: LIMITING CHANGE 8, ADDED 1, MISSING LIMIT 4, OK 23. A text that must change is replaced under a new ID, which keeps the replaced criterion's type and code list; a citation-only fix keeps the ID and text. Every excerpt below is checked word for word against data/raw by scripts/verify/policies_v2_triage.py.

| Row | Criterion | Category | Action | Reason |
|---|---|---|---|---|
| KB1 | POL-BH-001.c1 | LIMITING CHANGE | fix | The LCD joins its two indications with 'or' (known or suspected involvement, or testing that will affect management); c1 requires both ('and'). c2 still excludes testing when no problem is suspected. |
| KB2 | POL-BH-001.c2 | OK | keep | 'consists only of' restates 'used for' self-scored tools; the other two situations match. |
| KB3 | POL-BH-001.c3 | OK | keep | Same words. |
| KB4 | POL-CAR-001.c2 | LIMITING CHANGE | fix | The LCD says 'not generally medically necessary' and 'imminent valvular surgery'; c2 dropped 'generally' and softened 'imminent' to 'planned'. |
| KB5 | POL-CAR-001.c3 | LIMITING CHANGE | fix | cov-049 has two alternatives joined by 'or' (the evaluation could contribute significant information to the patient's condition or treatment plan, or adds information after a non-diagnostic treadmill test with suspected CAD); c3 kept only the second. |
| KB6 | POL-DX-001.c1 | OK | keep | Subsection B lists only narcolepsy and sleep apnea (cov-027, cov-039); the physician's prior evaluation matches. |
| KB8 | POL-DX-002.c1 | LIMITING CHANGE | fix | The LCD says a rule-out diagnosis is 'typically' not acceptable; c1 made it absolute ('not sufficient'). |
| KB9 | POL-DX-002.c2 | OK | keep | 'first-line' and 'recent injury' restate 'first order' and 'immediate antecedent trauma'. |
| KB10 | POL-DX-002.c3 | OK | keep | 'not covered' and 'only to monitor' match 'sole purpose'. |
| KB11 | POL-DX-003.c2 | MISSING LIMIT | fix | cov-012 limits patch testing to a 'clear-cut clinical suspicion of contact allergy' and to 'the chemicals relevant to the problem'; c2 says only 'suspected'. |
| KB12 | POL-DX-003.c3 | LIMITING CHANGE | fix | The guideline number is '< 70' (fewer than 70) prick tests; c3 says 'about 70'. |
| KB13 | POL-FOOT-001.c1 | OK | keep | 2 of 5 sites and the 5.07 monofilament match. |
| KB14 | POL-FOOT-001.c2 | OK | keep | Matches. |
| KB15 | POL-IMG-001.c1 | ADDED | fix | The second sentence ('Symptoms recorded on the claim and in the notes must support the scan') is not in the v1 excerpt (cov-005); cov-017 and cov-029 support it. Citation only; the ID and text stay. |
| KB16 | POL-IMG-001.c2 | OK | keep | 'only' restates 'should be reserved for'; the three headache situations and two weeks match. |
| KB17 | POL-IMG-001.c3 | MISSING LIMIT | fix | c3 leaves out cov-029 (contrast generally adds nothing after head trauma unless symptoms suggest a bleed) and widens cov-028's staging of lung cancer, breast cancer and lymphoma to any 'cancer staging'; it also lacks cov-027 (neovascularity) and the MRI section's seizure case (cov-015). The contrast rules are in the CT section, applied to 70553 as in v1. |
| KB18 | POL-IMG-001.c4 | OK | keep | The four cancers match; 'rarely spread to the brain' is cov-041's own 'almost never metastasize to the brain'. |
| KB19 | POL-IMG-002.c1 | MISSING LIMIT | fix | cov-006 covers 'intermetatarsal neuroma'; c1 says any 'neuromas'. It also leaves out cov-005 (telling solid tumors from cysts), an indication. |
| KB21 | POL-IMG-002.c3 | OK | keep | 'one', 'only when still uncertain' and the two exclusions match. |
| KB22 | POL-IMG-002.c4 | OK | keep | 'only if' pathology of both limbs and the 'control' exclusion match. |
| KB23 | POL-PAIN-001.c1 | OK | keep | The three alternatives and their causes match. |
| KB24 | POL-PAIN-001.c3 | LIMITING CHANGE | fix | The LCD pairs 4 weeks only with failure to respond ('inability to tolerate noninvasive conservative care or ... failure to respond to four (4) weeks'); c3 also ties the inability to tolerate to 4 weeks of care. |
| KB25 | POL-PAIN-002.c1 | OK | keep | 'predominantly axial', the scale and 'moderate to severe' match. |
| KB26 | POL-PAIN-002.c2 | LIMITING CHANGE | fix | The LCD qualifies the failed conservative care with '(as tolerated)'; c2 dropped it. |
| KB27 | POL-PAIN-002.c3 | OK | keep | The 'except' for a facet cyst, 'and' and the example causes match. |
| KB28 | POL-REHAB-001.c1 | LIMITING CHANGE | fix | The LCD's 'or' joins complexity and the patient's condition, both requiring that only a physical therapist (or someone under supervision) can do the service; c1 makes 'given under a physical therapist's supervision' enough on its own and drops the patient's condition. |
| KB29 | POL-REHAB-001.c3 | MISSING LIMIT | fix | cov-019 requires a condition 'expected to improve significantly within a reasonable and generally predictable period of time' (or a safe and effective maintenance program); c3 says only 'a reasonable potential for improvement'. This is the LCD's own wording. |
| KB30 | POL-SURG-001.c1 | OK | keep | Symptomatic, not correctable, activity limits and other diseases ruled out match. |
| KB31 | POL-SURG-001.c2 | OK | keep | 'only' restates 'purely'. |
| KB32 | POL-SURG-001.c3 | OK | keep | The four alternatives match (cov-008 is c4). |
| KB33 | POL-SURG-002.c3 | OK | keep | Same words; 24 months matches. |
| KB34 | POL-SURG-003.c1 | OK | keep | 'only', 3 months and the saphenous veins match. |
| KB35 | POL-SURG-003.c2 | OK | keep | 'or', 3 months, 'by any technique' and 'not covered' match. |
| KB36 | POL-SURG-003.c3 | OK | keep | Matches. |
| KB37 | POL-WOUND-001.c1 | OK | keep | Debridement, healing and one-on-one contact match. |
| KB38 | POL-WOUND-001.c2 | OK | keep | Complicating factors, closure and the palliative goal match. |

## Drafts and excerpts

### KB1. POL-BH-001.c1: LIMITING CHANGE, fix

- Reason: The LCD joins its two indications with 'or' (known or suspected involvement, or testing that will affect management); c1 requires both ('and'). c2 still excludes testing when no problem is suspected.
- **New criterion POL-BH-001.c4** (requirement; applies to every code of the policy; replaces POL-BH-001.c1): Testing is covered when brain or psychological involvement is known or suspected, or when the results will affect the patient's management by confirming or delineating a diagnosis or otherwise informing diagnosis, treatment planning, prognosis or quality of life. An example is telling dementia or brain injury apart from depression when the diagnosis is still uncertain after examination.
  Source line: LCD L34520 v32 cov-003.
- Excerpt words (word for word):
  - **L34520-cov-003**: "whether there is known or suspected neurocognitive involvement or effects, or where neuropsychological testing will impact the management of the patient"

### KB2. POL-BH-001.c2: OK, keep

- Reason: 'consists only of' restates 'used for' self-scored tools; the other two situations match.
- Excerpt words (word for word):
  - **v1:POL-BH-001.c2**: "used for self-administered or self-scored inventories or screening tests"

### KB3. POL-BH-001.c3: OK, keep

- Reason: Same words.
- Excerpt words (word for word):
  - **v1:POL-BH-001.c3**: "is not medically necessary."

### KB4. POL-CAR-001.c2: LIMITING CHANGE, fix

- Reason: The LCD says 'not generally medically necessary' and 'imminent valvular surgery'; c2 dropped 'generally' and softened 'imminent' to 'planned'.
- **New criterion POL-CAR-001.c6** (conditional; applies to 93306, 93308; replaces POL-CAR-001.c2): Repeating the study more often than once a year is generally not medically necessary unless the notes document a discrete episode of deterioration (an abrupt change in signs or symptoms), a check of the response to treatment, or imminent valve surgery.
  Source line: LCD L37379 v42 cov-008, cov-021.
- Excerpt words (word for word):
  - **L37379-cov-008**: "it is not generally medically necessary to repeat TTE assessments more frequently than annually"
  - **L37379-cov-021**: "plan of care includes imminent valvular surgery, more frequent exams may be necessary"

### KB5. POL-CAR-001.c3: LIMITING CHANGE, fix

- Reason: cov-049 has two alternatives joined by 'or' (the evaluation could contribute significant information to the patient's condition or treatment plan, or adds information after a non-diagnostic treadmill test with suspected CAD); c3 kept only the second.
- **New criterion POL-CAR-001.c7** (requirement; applies to 93350; replaces POL-CAR-001.c3): Stress echocardiography is covered when the evaluation could contribute significant information about the patient's condition or treatment plan, or to add diagnostic information after a treadmill stress test that did not give a diagnosis in a patient with signs or symptoms of suspected coronary artery disease.
  Source line: LCD L37379 v42 cov-049.
- Excerpt words (word for word):
  - **L37379-cov-049**: "Stress ECHO may be necessary when the evaluation could contribute significant information to the patient"
  - **L37379-cov-049**: "or to provide additional diagnostic information in patients with a previous non-diagnostic treadmill stress test who have signs or symptoms of suspected CAD"

### KB6. POL-DX-001.c1: OK, keep

- Reason: Subsection B lists only narcolepsy and sleep apnea (cov-027, cov-039); the physician's prior evaluation matches.
- Excerpt words (word for word):
  - **v1:POL-DX-001.c1**: "The patient is to be evaluated by a physician prior to ordering of test."

### KB8. POL-DX-002.c1: LIMITING CHANGE, fix

- Reason: The LCD says a rule-out diagnosis is 'typically' not acceptable; c1 made it absolute ('not sufficient').
- **New criterion POL-DX-002.c5** (requirement; applies to every code of the policy; replaces POL-DX-002.c1): Testing is covered when the history and examination before the test clearly document the need for it, for example limb pain, numbness or tingling, or weakness that suggests a nerve or muscle disorder. A rule-out diagnosis alone is typically not acceptable.
  Source line: LCD L34594 v42 cov-025.
- Excerpt words (word for word):
  - **L34594-cov-025**: "diagnosis is typically not acceptable"

### KB9. POL-DX-002.c2: OK, keep

- Reason: 'first-line' and 'recent injury' restate 'first order' and 'immediate antecedent trauma'.
- Excerpt words (word for word):
  - **v1:POL-DX-002.c2**: "irrelevant as a first order diagnostic test"

### KB10. POL-DX-002.c3: OK, keep

- Reason: 'not covered' and 'only to monitor' match 'sole purpose'.
- Excerpt words (word for word):
  - **v1:POL-DX-002.c3**: "Testing for the sole purpose of monitoring disease intensity or treatment efficacy"

### KB11. POL-DX-003.c2: MISSING LIMIT, fix

- Reason: cov-012 limits patch testing to a 'clear-cut clinical suspicion of contact allergy' and to 'the chemicals relevant to the problem'; c2 says only 'suspected'.
- **New criterion POL-DX-003.c6** (requirement; applies to 95044; replaces POL-DX-003.c2): Patch testing is covered to diagnose allergic contact dermatitis, or other dermatitis or skin eruptions where a contact allergen is the likely cause, when there is a clear-cut clinical suspicion of contact allergy and the chemicals tested are relevant to the problem.
  Source line: LCD L33261 v40 cov-010, cov-012.
- Excerpt words (word for word):
  - **L33261-cov-012**: "for patients with a clear-cut clinical suspicion of contact allergy, and they are tested with the chemicals relevant to the problem"
  - **L33261-cov-010**: "reserved for patients with skin eruptions for which a contact allergy source is likely"

### KB12. POL-DX-003.c3: LIMITING CHANGE, fix

- Reason: The guideline number is '< 70' (fewer than 70) prick tests; c3 says 'about 70'.
- **New criterion POL-DX-003.c7** (requirement; applies to every code of the policy; replaces POL-DX-003.c3): The tests chosen must match the patient's history and physical findings, and the number of tests must be justified. For an initial evaluation of airborne allergens, guidelines justify fewer than 70 prick and 40 intradermal tests; up to 80 patch tests may be needed to diagnose allergic contact dermatitis.
  Source line: LCD L33261 v40 cov-055, cov-056.
- Excerpt words (word for word):
  - **L33261-cov-056**: "< 70 prick/puncture and 40 intracutaneous tests"
  - **L33261-cov-056**: "up to 80 patch tests may be required for ACD diagnosis"

### KB13. POL-FOOT-001.c1: OK, keep

- Reason: 2 of 5 sites and the 5.07 monofilament match.
- Excerpt words (word for word):
  - **v1:POL-FOOT-001.c1**: "absence of sensation at two or more sites out of five tested on either foot"

### KB14. POL-FOOT-001.c2: OK, keep

- Reason: Matches.
- Excerpt words (word for word):
  - **v1:POL-FOOT-001.c2**: "the significant risk and danger posed by the non-professional"

### KB15. POL-IMG-001.c1: ADDED, fix

- Reason: The second sentence ('Symptoms recorded on the claim and in the notes must support the scan') is not in the v1 excerpt (cov-005); cov-017 and cov-029 support it. Citation only; the ID and text stay.
- Old source line: LCD L37373 v41, CT section, general indications.
- **New source line:** LCD L37373 v41 cov-005, cov-017, cov-029.
- Excerpt words (word for word):
  - **L37373-cov-017**: "not supported by the patient"
  - **L37373-cov-029**: "These symptoms should be documented in the medical record, and if appropriate, included in the diagnostic codes listed on the claim."

### KB16. POL-IMG-001.c2: OK, keep

- Reason: 'only' restates 'should be reserved for'; the three headache situations and two weeks match.
- Excerpt words (word for word):
  - **v1:POL-IMG-001.c2**: "should be reserved for the patient whose presentation indicates a focal problem"

### KB17. POL-IMG-001.c3: MISSING LIMIT, fix

- Reason: c3 leaves out cov-029 (contrast generally adds nothing after head trauma unless symptoms suggest a bleed) and widens cov-028's staging of lung cancer, breast cancer and lymphoma to any 'cancer staging'; it also lacks cov-027 (neovascularity) and the MRI section's seizure case (cov-015). The contrast rules are in the CT section, applied to 70553 as in v1.
- **New criterion POL-IMG-001.c5** (requirement; applies to 70553; replaces POL-IMG-001.c3): A scan with contrast needs a documented reason: assessing perfusion (such as a stroke), characterizing a specific lesion, detecting a blood-brain barrier defect (such as infarct, tumor, infection or vasculitis) or new blood vessels in a tumor, new-onset seizures (particularly with a focal component), or staging a known lung cancer, breast cancer or lymphoma likely to spread early to the brain. After head trauma, contrast generally adds nothing unless symptoms suggest a possible bleed inside the skull. More than one contrast scan per episode of illness is not covered except for stroke, TIA, non-traumatic bleeding, a post-operative scan for residual tumor or a complication, or a known brain tumor or metastases with a change in mental status or other sign of central nervous system change.
  Source line: LCD L37373 v41 cov-015, cov-023 to cov-035.
- Excerpt words (word for word):
  - **L37373-cov-029**: "Intravenous contrast generally adds no information to CT scans done secondary to head trauma."
  - **L37373-cov-028**: "For staging of known lung cancer, breast cancer, and lymphomas likely to metastasize early to the brain"
  - **L37373-cov-027**: "Detect neovascularity (tumor), and"
  - **L37373-cov-015**: "New onset seizures, particularly if a focal component is present (contrast agent is appropriate for these patients)"

### KB18. POL-IMG-001.c4: OK, keep

- Reason: The four cancers match; 'rarely spread to the brain' is cov-041's own 'almost never metastasize to the brain'.
- Excerpt words (word for word):
  - **L37373-cov-041**: "Certain tumors almost never metastasize to the brain parenchyma."

### KB19. POL-IMG-002.c1: MISSING LIMIT, fix

- Reason: cov-006 covers 'intermetatarsal neuroma'; c1 says any 'neuromas'. It also leaves out cov-005 (telling solid tumors from cysts), an indication.
- **New criterion POL-IMG-002.c6** (requirement; applies to every code of the policy; replaces POL-IMG-002.c1): Extremity ultrasound is covered to detect cysts, abscesses, tumors (including their size) or effusions, or to tell solid tumors from fluid-filled cysts; to evaluate tendons, joints, plantar fascia, ligaments, soft-tissue masses, ganglion cysts, intermetatarsal neuromas or metatarsal stress fractures; or to help diagnose and remove foreign bodies.
  Source line: LCD L33619 v25 cov-003 to cov-007.
- Excerpt words (word for word):
  - **L33619-cov-006**: "ganglion cysts, intermetatarsal neuroma and stress fractures of the metatarsals"
  - **L33619-cov-005**: "To distinguish solid tumors from fluid-filled cysts;"

### KB21. POL-IMG-002.c3: OK, keep

- Reason: 'one', 'only when still uncertain' and the two exclusions match.
- Excerpt words (word for word):
  - **v1:POL-IMG-002.c3**: "A single diagnostic extremity ultrasound may be medically necessary for plantar fasciitis"

### KB22. POL-IMG-002.c4: OK, keep

- Reason: 'only if' pathology of both limbs and the 'control' exclusion match.
- Excerpt words (word for word):
  - **v1:POL-IMG-002.c4**: "Bilateral studies are allowed only if there is pathology of both extremities"

### KB23. POL-PAIN-001.c1: OK, keep

- Reason: The three alternatives and their causes match.
- Excerpt words (word for word):
  - **v1:POL-PAIN-001.c1**: "OR Post-laminectomy syndrome, OR Acute herpes zoster associated pain"

### KB24. POL-PAIN-001.c3: LIMITING CHANGE, fix

- Reason: The LCD pairs 4 weeks only with failure to respond ('inability to tolerate noninvasive conservative care or ... failure to respond to four (4) weeks'); c3 also ties the inability to tolerate to 4 weeks of care.
- **New criterion POL-PAIN-001.c10** (requirement; applies to every code of the policy; replaces POL-PAIN-001.c3): The pain must have lasted at least 4 weeks, with an inability to tolerate non-invasive conservative care or documented failure to respond to 4 weeks of it. Acute shingles pain that does not respond to conservative care is exempt from the 4-week wait.
  Source line: LCD L33906 v75 cov-014.
- Excerpt words (word for word):
  - **L33906-cov-014**: "the inability to tolerate noninvasive conservative care or medical documentation of failure to respond to four (4) weeks of noninvasive conservative care"

### KB25. POL-PAIN-002.c1: OK, keep

- Reason: 'predominantly axial', the scale and 'moderate to severe' match.
- Excerpt words (word for word):
  - **v1:POL-PAIN-002.c1**: "predominantly axial, that causes functional deficit"

### KB26. POL-PAIN-002.c2: LIMITING CHANGE, fix

- Reason: The LCD qualifies the failed conservative care with '(as tolerated)'; c2 dropped it.
- **New criterion POL-PAIN-002.c6** (requirement; applies to every code of the policy; replaces POL-PAIN-002.c2): The pain must have lasted at least 3 months, with documented failure to respond to non-invasive conservative care, as tolerated.
  Source line: LCD L33930 v49 cov-017.
- Excerpt words (word for word):
  - **L33930-cov-017**: "documented failure to respond to noninvasive conservative care management (as tolerated)"

### KB27. POL-PAIN-002.c3: OK, keep

- Reason: The 'except' for a facet cyst, 'and' and the example causes match.
- Excerpt words (word for word):
  - **v1:POL-PAIN-002.c3**: "except for radiculopathy caused by facet joint synovial cyst"

### KB28. POL-REHAB-001.c1: LIMITING CHANGE, fix

- Reason: The LCD's 'or' joins complexity and the patient's condition, both requiring that only a physical therapist (or someone under supervision) can do the service; c1 makes 'given under a physical therapist's supervision' enough on its own and drops the patient's condition.
- **New criterion POL-REHAB-001.c6** (requirement; applies to every code of the policy; replaces POL-REHAB-001.c1): Services must need the skills of a licensed physical therapist: because of their complexity or the patient's condition, they can be performed safely and effectively only by a physical therapist or under a physical therapist's supervision.
  Source line: LCD L34428 v93 cov-017.
- Excerpt words (word for word):
  - **L34428-cov-017**: "can be safely and effectively performed only by a licensed physical therapist or under his/her supervision"

### KB29. POL-REHAB-001.c3: MISSING LIMIT, fix

- Reason: cov-019 requires a condition 'expected to improve significantly within a reasonable and generally predictable period of time' (or a safe and effective maintenance program); c3 says only 'a reasonable potential for improvement'. This is the LCD's own wording.
- **New criterion POL-REHAB-001.c7** (requirement; applies to 97110, 97140, 97530; replaces POL-REHAB-001.c3): Restorative therapy must be for a condition expected to improve significantly within a reasonable and generally predictable period of time; otherwise the plan must establish a safe and effective maintenance program that meets the Medicare Benefit Policy Manual, Chapter 15, Section 220 criteria.
  Source line: LCD L34428 v93 cov-013, cov-015, cov-019.
- Excerpt words (word for word):
  - **L34428-cov-019**: "expected to improve significantly within a reasonable and generally predictable period of time"
  - **L34428-cov-015**: "maintain or to slow deterioration"

### KB30. POL-SURG-001.c1: OK, keep

- Reason: Symptomatic, not correctable, activity limits and other diseases ruled out match.
- Excerpt words (word for word):
  - **v1:POL-SURG-001.c1**: "have been ruled out as the primary cause of decreased visual function"

### KB31. POL-SURG-001.c2: OK, keep

- Reason: 'only' restates 'purely'.
- Excerpt words (word for word):
  - **v1:POL-SURG-001.c2**: "purely on the basis of lens opacity in the absence of symptoms"

### KB32. POL-SURG-001.c3: OK, keep

- Reason: The four alternatives match (cov-008 is c4).
- Excerpt words (word for word):
  - **v1:POL-SURG-001.c3**: "Intolerable anisometropia or aniseikonia"

### KB33. POL-SURG-002.c3: OK, keep

- Reason: Same words; 24 months matches.
- Excerpt words (word for word):
  - **v1:POL-SURG-002.c3**: "is eligible for continued screening at 24-month intervals"

### KB34. POL-SURG-003.c1: OK, keep

- Reason: 'only', 3 months and the saphenous veins match.
- Excerpt words (word for word):
  - **v1:POL-SURG-003.c1**: "are covered only for the treatment of symptomatic varicosities"

### KB35. POL-SURG-003.c2: OK, keep

- Reason: 'or', 3 months, 'by any technique' and 'not covered' match.
- Excerpt words (word for word):
  - **v1:POL-SURG-003.c2**: "or symptomatic varicose veins without a 3-month trial of conservative measures"

### KB36. POL-SURG-003.c3: OK, keep

- Reason: Matches.
- Excerpt words (word for word):
  - **v1:POL-SURG-003.c3**: "by any technique is considered cosmetic"

### KB37. POL-WOUND-001.c1: OK, keep

- Reason: Debridement, healing and one-on-one contact match.
- Excerpt words (word for word):
  - **v1:POL-WOUND-001.c1**: "The provider is required to have direct (one-on-one) patient contact"

### KB38. POL-WOUND-001.c2: OK, keep

- Reason: Complicating factors, closure and the palliative goal match.
- Excerpt words (word for word):
  - **v1:POL-WOUND-001.c2**: "may be only to prevent progression of the wound"

