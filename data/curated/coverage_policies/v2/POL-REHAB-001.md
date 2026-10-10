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
replaces: {"POL-REHAB-001.c2": ["POL-REHAB-001.c4", "POL-REHAB-001.c5"], "POL-REHAB-001.c1": ["POL-REHAB-001.c6"], "POL-REHAB-001.c3": ["POL-REHAB-001.c7"]}
---

## POL-REHAB-001.c4
Treatment must follow a written plan of care, developed from an examination and evaluation, that sets specific goals and plans the procedures by type, frequency and duration.

Type: requirement
Applies to: 97110, 97140, 97530
Source: LCD L34428 v93 cov-001, cov-020, cov-112.

## POL-REHAB-001.c5
The patient must be under the care of a physician or NPP, and a physician or NPP must certify the plan of care and recertify it.

Type: requirement
Applies to: 97110, 97140, 97530
Source: LCD L34428 v93 cov-005, cov-018, doc-007, doc-016, doc-019.

## POL-REHAB-001.c6
Services must need the skills of a licensed physical therapist: because of their complexity or the patient's condition, they can be performed safely and effectively only by a physical therapist or under a physical therapist's supervision.

Type: requirement
Source: LCD L34428 v93 cov-017.

## POL-REHAB-001.c7
Restorative therapy must be for a condition expected to improve significantly within a reasonable and generally predictable period of time; otherwise the plan must establish a safe and effective maintenance program that meets the Medicare Benefit Policy Manual, Chapter 15, Section 220 criteria.

Type: requirement
Applies to: 97110, 97140, 97530
Source: LCD L34428 v93 cov-013, cov-015, cov-019.
