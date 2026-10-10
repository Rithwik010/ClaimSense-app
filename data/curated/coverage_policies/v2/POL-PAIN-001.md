---
policy_id: POL-PAIN-001
title: Epidural steroid injections
procedure_codes: ["62321", "62323", "64483"]
plan_ids: ["ALL"]
effective_date: 2026-01-01
sources: ["LCD L33906 version 75 (revision effective 2026-04-09); billing article A56651; CMS Medicare Coverage Database download, retrieved 2026-09-21"]
billing_article: A56651
split: TRAIN
policy_set: v2
replaces: {"POL-PAIN-001.c2": ["POL-PAIN-001.c6"], "POL-PAIN-001.c4": ["POL-PAIN-001.c7"], "POL-PAIN-001.c5": ["POL-PAIN-001.c8"], "POL-PAIN-001.c3": ["POL-PAIN-001.c10"]}
---

## POL-PAIN-001.c1
History, examination and matching imaging must support nerve-root pain (radiculopathy) or neurogenic claudication from a disc herniation, bone spurs or severe disc degeneration narrowing the spinal canal or nerve openings; or pain after spinal surgery (post-laminectomy syndrome); or acute shingles pain.

Type: requirement
Source: LCD L33906 v75, Covered indications.

## POL-PAIN-001.c6
The pain must be severe enough to greatly affect quality of life or function, and a baseline pain or function score, a numeric score or a named scale, must be documented before treatment.

Type: requirement
Source: LCD L33906 v75 cov-013, cov-023; decision D-ESI-2.

## POL-PAIN-001.c7
Injections must be done under CT or fluoroscopic guidance with contrast. Without contrast, for example under ultrasound guidance, they are covered only when a contraindication to contrast, such as an allergy or pregnancy, is documented. A procedure code that includes imaging guidance counts as evidence of guidance, but contrast use, or the documented contraindication, must be in the notes. Interlaminar and caudal injections are limited to one level, and transforaminal injections to two levels in one spinal region.

Type: requirement
Source: LCD L33906 v75 cov-015, cov-016, cov-017, cov-020, cov-025; decision D-ESI-7.

## POL-PAIN-001.c8
A repeat injection is covered when the first one gave at least 50% improvement in pain lasting at least 3 months, or at least 50% improvement in function, on the same scale as the baseline. If the first injection did not work well, a repeat after at least 14 days is covered with a different approach, level or medication, when the reason for it is documented.

Type: conditional
Source: LCD L33906 v75 cov-019, cov-039; decision D-ESI-2.

## POL-PAIN-001.c9
Injections given to treat non-specific low back pain, axial spine pain, complex regional pain syndrome, widespread diffuse pain, pain from neuropathy of other causes, or cervicogenic headaches are not covered.

Type: exclusion
Source: LCD L33906 v75 cov-029; decision D-ESI-4.

## POL-PAIN-001.c10
The pain must have lasted at least 4 weeks, with an inability to tolerate non-invasive conservative care or documented failure to respond to 4 weeks of it. Acute shingles pain that does not respond to conservative care is exempt from the 4-week wait.

Type: requirement
Source: LCD L33906 v75 cov-014.
