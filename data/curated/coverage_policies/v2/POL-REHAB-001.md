---
policy_id: POL-REHAB-001
title: Outpatient physical therapy
procedure_codes: ["97110", "97140", "97161", "97162", "97530"]
plan_ids: ["ALL"]
effective_date: 2026-01-01
sources: ["LCD L34428 version 93 (revision effective 2023-05-18); billing article A53065; CMS Medicare Coverage Database download, retrieved 2026-09-21"]
billing_article: A53065
split: TRAIN
policy_set: v2
replaces: {"POL-REHAB-001.c2": ["POL-REHAB-001.c4", "POL-REHAB-001.c5"]}
---

## POL-REHAB-001.c1
Services must be complex enough to need the skills of a qualified physical therapist, or be given under a physical therapist's supervision.

Type: requirement
Source: LCD L34428 v93, General physical therapy guidelines.

## POL-REHAB-001.c3
Restorative therapy requires a reasonable potential for improvement from the services. Maintenance programs must meet the Medicare Benefit Policy Manual, Chapter 15, Section 220 criteria.

Type: requirement
Source: LCD L34428 v93, Restorative and maintenance therapy.

## POL-REHAB-001.c4
Treatment, as opposed to an initial evaluation or re-evaluation, must follow a written plan of care with specific goals, developed from an examination and evaluation. An evaluation can be covered even when it finds that therapy is not needed.

Type: requirement
Applies to: 97110, 97140, 97530
Source: LCD L34428 v93 cov-001, cov-020, cov-112.

## POL-REHAB-001.c5
The patient must be under the care of a physician or NPP, who certifies and recertifies the plan of care.

Type: requirement
Applies to: 97110, 97140, 97530
Source: LCD L34428 v93 cov-018, doc-007, doc-019.
