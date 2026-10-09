---
policy_id: POL-DX-001
title: Outpatient sleep studies
procedure_codes: ["95806", "95810", "95811"]
plan_ids: ["ALL"]
effective_date: 2026-01-01
sources: ["LCD L35050 version 55 (revision effective 2021-01-01); billing article A56923; CMS Medicare Coverage Database download, retrieved 2026-09-21"]
billing_article: A56923
split: TEST_ONLY
policy_set: v2
replaces: {"POL-DX-001.c2": ["POL-DX-001.c4"], "POL-DX-001.c3": ["POL-DX-001.c6"]}
---

## POL-DX-001.c1
Sleep testing is covered to evaluate suspected sleep apnea or narcolepsy when the physician's evaluation documents the symptoms and findings that led to the test.

Type: requirement
Source: LCD L35050 v55, Covered indications, section B.

## POL-DX-001.c4
Home (out-of-center) sleep testing is not covered for diagnosing obstructive sleep apnea when the patient has a significant comorbid medical condition or sleep disorder that may make the test inaccurate, such as moderate to severe lung disease, neuromuscular disease or congestive heart failure.

Type: exclusion
Applies to: 95806
Source: LCD L35050 v55 cov-106, cov-109, cov-110.

## POL-DX-001.c5
Home (out-of-center) sleep testing requires a high likelihood of moderate to severe sleep apnea, shown by the symptoms and the physical examination documented in the notes.

Type: requirement
Applies to: 95806
Source: LCD L35050 v55 cov-106, cov-107, cov-108.

## POL-DX-001.c6
A repeat sleep study, in a facility or at home, is covered when the record justifies it: the first study was technically inadequate because of equipment failure, the patient could not sleep or slept too little for a diagnosis, the results were inconclusive or ambiguous, or starting therapy or confirming that the prescribed therapy works requires it. After a negative or technically inadequate home test in a patient with a high likelihood of moderate to severe obstructive sleep apnea, the repeat should be an in-laboratory study.

Type: conditional
Source: LCD L35050 v55 cov-058 to cov-062, cov-121.
