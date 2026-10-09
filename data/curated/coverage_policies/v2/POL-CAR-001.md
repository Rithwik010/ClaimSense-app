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
replaces: {"POL-CAR-001.c1": ["POL-CAR-001.c4", "POL-CAR-001.c5"]}
---

## POL-CAR-001.c2
Repeating the study more often than once a year is not medically necessary unless the notes document a clear change in signs or symptoms, a check of the response to treatment, or planned valve surgery.

Type: conditional
Source: LCD L37379 v42, Sections A and F, repeat studies.

## POL-CAR-001.c3
Stress echocardiography is covered to evaluate suspected coronary artery disease in patients with signs or symptoms, for example after a treadmill stress test that did not give a diagnosis.

Type: requirement
Applies to: 93350
Source: LCD L37379 v42, Stress echocardiography indications.

## POL-CAR-001.c4
A transthoracic echocardiogram is covered when the patient has signs or symptoms of, or is being evaluated for, one of these: weakened heart muscle or cardiomyopathy; hypertensive heart disease with clinical evidence of heart disease; heart attack or coronary insufficiency; exposure to drugs or treatments toxic to the heart; heart transplant or rejection monitoring; native heart valve disease; prosthetic heart valves; acute endocarditis; pericardial disease; aortic disease; congenital heart disease; suspected clots or embolic sources in the heart; heart tumors or masses; critical illness or trauma; arrhythmias or palpitations; fainting (syncope); or lung disease affecting the heart.

Type: requirement
Applies to: 93306, 93308
Source: LCD L37379 v42 cov-006, cov-007, cov-009, cov-011, cov-012, cov-013, cov-016, cov-018, cov-020, cov-022, cov-024, cov-026, cov-028, cov-030, cov-032, cov-034, cov-036, cov-038, cov-040, cov-042.

## POL-CAR-001.c5
High blood pressure alone, without signs or symptoms of heart disease, is not a covered reason.

Type: exclusion
Applies to: 93306, 93308
Source: LCD L37379 v42 cov-012.
