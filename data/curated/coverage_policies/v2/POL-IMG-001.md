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
replaces: {}
---

## POL-IMG-001.c1
CT or MRI of the head or neck is covered when the scan is medically appropriate for the patient's documented symptoms and provisional diagnosis. Symptoms recorded on the claim and in the notes must support the scan as ordered.

Type: requirement
Source: LCD L37373 v41, CT section, general indications.

## POL-IMG-001.c2
For headache or dizziness, imaging is covered only with a focal neurological finding, a significant change in symptoms, a head injury where bleeding must be ruled out, a headache lasting more than two weeks that has not responded to treatment, or a sudden, severe headache.

Type: conditional
Source: LCD L37373 v41, CT section, headache indications.

## POL-IMG-001.c3
Scans with contrast need a documented reason, such as characterizing a specific lesion, suspected stroke, tumor or infection, or cancer staging. More than one contrast scan per episode of illness is not covered except for stroke, TIA, non-traumatic bleeding, post-operative checks, or a known brain tumor with new neurological change.

Type: requirement
Applies to: 70553
Source: LCD L37373 v41, CT section, contrast indications.

## POL-IMG-001.c4
Brain imaging to stage a cancer without neurological symptoms is not covered for cancers that rarely spread to the brain: esophagus, oropharynx, prostate and non-melanoma skin cancer.

Type: exclusion
Source: LCD L37373 v41, MRI section, cancer staging.
