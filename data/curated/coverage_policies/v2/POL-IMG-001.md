---
policy_id: POL-IMG-001
title: CT and MRI of the head and neck
procedure_codes: ["70450", "70551", "70553", "72141"]
plan_ids: ["ALL"]
effective_date: 2026-01-01
sources: ["LCD L37373 version 41 (revision effective 2025-10-23); billing article A57204; CMS Medicare Coverage Database download, retrieved 2026-09-21"]
billing_article: A57204
split: TRAIN
policy_set: v2
replaces: {"POL-IMG-001.c3": ["POL-IMG-001.c5"]}
---

## POL-IMG-001.c1
CT or MRI of the head or neck is covered when the scan is medically appropriate for the patient's documented symptoms and provisional diagnosis. Symptoms recorded on the claim and in the notes must support the scan as ordered.

Type: requirement
Source: LCD L37373 v41 cov-005, cov-017, cov-029.

## POL-IMG-001.c2
For headache or dizziness, imaging is covered only with a focal neurological finding, a significant change in symptoms, a head injury where bleeding must be ruled out, a headache lasting more than two weeks that has not responded to treatment, or a sudden, severe headache.

Type: conditional
Applies to: 70450, 70551, 70553
Source: LCD L37373 v41, CT section, headache indications.

## POL-IMG-001.c4
Brain imaging to stage a cancer without neurological symptoms is not covered for cancers that rarely spread to the brain: esophagus, oropharynx, prostate and non-melanoma skin cancer.

Type: exclusion
Applies to: 70450, 70551, 70553
Source: LCD L37373 v41, MRI section, cancer staging.

## POL-IMG-001.c5
A scan with contrast needs a documented reason: assessing perfusion (such as a stroke), characterizing a specific lesion, detecting a blood-brain barrier defect (such as infarct, tumor, infection or vasculitis) or new blood vessels in a tumor, new-onset seizures (particularly with a focal component), or staging a known lung cancer, breast cancer or lymphoma likely to spread early to the brain. After head trauma, contrast generally adds nothing unless symptoms suggest a possible bleed inside the skull. More than one contrast scan per episode of illness is not covered except for stroke, TIA, non-traumatic bleeding, a post-operative scan for residual tumor or a complication, or a known brain tumor or metastases with a change in mental status or other sign of central nervous system change.

Type: requirement
Applies to: 70553
Source: LCD L37373 v41 cov-015, cov-023 to cov-035.
