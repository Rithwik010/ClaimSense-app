---
policy_id: POL-CAR-001
title: Echocardiography (heart ultrasound)
procedure_codes: ["93306", "93308", "93350"]
plan_ids: ["ALL"]
effective_date: 2026-01-01
sources: ["LCD L37379 version 42 (revision effective 2025-10-23); billing article A56625; CMS Medicare Coverage Database download, retrieved 2026-09-21"]
billing_article: A56625
split: TRAIN
policy_set: v2
replaces: {"POL-CAR-001.c1": ["POL-CAR-001.c4", "POL-CAR-001.c5"], "POL-CAR-001.c2": ["POL-CAR-001.c6"], "POL-CAR-001.c3": ["POL-CAR-001.c7"]}
---

## POL-CAR-001.c4
A transthoracic echocardiogram is covered when the patient has symptoms of, or an existing condition in, one of these: weakened heart muscle or cardiomyopathy; hypertensive heart disease with clinical evidence of heart disease; heart attack or coronary insufficiency; exposure to drugs or treatments toxic to the heart; heart transplant or rejection monitoring; native heart valve disease; prosthetic heart valves; acute endocarditis; pericardial disease; aortic disease; congenital heart disease; suspected clots or embolic sources in the heart; heart tumors or masses; critical illness or trauma; arrhythmias or palpitations; fainting (syncope); or pulmonary heart disease, such as unexplained pulmonary hypertension or a pulmonary embolism with suspected clots in the right heart.

Type: requirement
Applies to: 93306, 93308
Source: LCD L37379 v42 cov-006, cov-007, cov-009, cov-011, cov-012, cov-013, cov-016, cov-018, cov-020, cov-022, cov-024, cov-026, cov-028, cov-030, cov-032, cov-034, cov-036, cov-038, cov-040, cov-042, cov-043, cov-108.

## POL-CAR-001.c5
High blood pressure alone, without signs or symptoms of heart disease, is not a covered reason.

Type: exclusion
Applies to: 93306, 93308
Source: LCD L37379 v42 cov-012.

## POL-CAR-001.c6
Repeating the study more often than once a year is generally not medically necessary unless the notes document a discrete episode of deterioration (an abrupt change in signs or symptoms), a check of the response to treatment, or imminent valve surgery.

Type: conditional
Applies to: 93306, 93308
Source: LCD L37379 v42 cov-008, cov-021.

## POL-CAR-001.c7
Stress echocardiography is covered when the evaluation could contribute significant information about the patient's condition or treatment plan, or to add diagnostic information after a treadmill stress test that did not give a diagnosis in a patient with signs or symptoms of suspected coronary artery disease.

Type: requirement
Applies to: 93350
Source: LCD L37379 v42 cov-049.
