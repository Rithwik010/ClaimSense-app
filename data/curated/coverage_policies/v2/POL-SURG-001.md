---
policy_id: POL-SURG-001
title: Cataract surgery
procedure_codes: ["66982", "66984"]
plan_ids: ["ALL"]
effective_date: 2026-01-01
sources: ["LCD L33558 version 33 (revision effective 2026-04-01); billing article A56544; CMS Medicare Coverage Database download, retrieved 2026-09-21"]
billing_article: A56544
split: TRAIN
policy_set: v2
replaces: {}
---

## POL-SURG-001.c1
Surgery is covered when the cataract causes symptoms of impaired vision that cannot be corrected with a tolerable change in glasses or contact lenses, and that limits activities such as reading, watching television, driving, or work and hobbies. Other eye diseases must be ruled out as the main cause.

Type: conditional
Group: indication
Source: LCD L33558 v33, Indications and limitations.

## POL-SURG-001.c2
Surgery is not medically necessary based only on clouding of the lens without symptoms.

Type: exclusion
Source: LCD L33558 v33, Indications and limitations.

## POL-SURG-001.c3
It is also covered when the cataract prevents monitoring or treatment of another eye disease (such as diabetic retinopathy), interferes with retinal surgery, causes lens-induced disease threatening vision, or leaves an intolerable difference between the eyes after surgery on the other eye.

Type: conditional
Group: indication
Source: LCD L33558 v33, Indications and limitations.
