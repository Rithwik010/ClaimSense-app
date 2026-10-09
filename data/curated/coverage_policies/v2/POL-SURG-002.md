---
policy_id: POL-SURG-002
title: Colonoscopy
procedure_codes: ["45378", "45380", "45385"]
plan_ids: ["ALL"]
effective_date: 2026-01-01
sources: ["LCD L34005 version 34 (revision effective 2026-01-22); billing article A56456; CMS Medicare Coverage Database download, retrieved 2026-09-21"]
billing_article: A56456
split: TRAIN
policy_set: v2
replaces: {"POL-SURG-002.c1": ["POL-SURG-002.c4"], "POL-SURG-002.c2": ["POL-SURG-002.c5"]}
---

## POL-SURG-002.c3
Patients identified as high risk for colon cancer are eligible for continued screening every 24 months.

Type: conditional
Group: indication
Source: LCD L34005 v34, Indications.

## POL-SURG-002.c4
Colonoscopy to investigate symptoms or findings is covered for: an imaging abnormality likely to be significant; unexplained bleeding (blood in the stool not from a rectal source, black tarry stool, or a positive stool blood test); unexplained iron-deficiency anemia; significant unexplained diarrhea with other findings such as weight loss; examining the whole colon for synchronous cancer or polyps in a patient with a treatable cancer or polyp; chronic inflammatory bowel disease when a more precise diagnosis or the extent of activity will change immediate management; locating during surgery a lesion that cannot be found by touch or sight; acute colonic ischemia; Streptococcus bovis endocarditis; unexplained new-onset constipation that does not respond to medical treatment; an anorectal adenomatous polyp; or infectious colitis.

Type: conditional
Group: indication
Source: LCD L34005 v34 cov-007, cov-009 to cov-012, cov-014, cov-022 to cov-026, cov-032, cov-033, doc-001.

## POL-SURG-002.c5
Surveillance is covered for a history of colorectal cancer or polyps, follow-up one year after colorectal cancer surgery, follow-up after removal of a large sessile adenoma (more than 2 cm in its greatest dimension), and inflammatory bowel disease surveillance (pancolitis for more than 7 years, or left-sided colitis for more than 15 years; not for disease limited to the rectosigmoid).

Type: conditional
Group: indication
Source: LCD L34005 v34 cov-013, cov-015, cov-017, cov-019 to cov-021.

## POL-SURG-002.c6
Colonoscopy is generally not covered, unless the record documents why it is needed, for: chronic, stable irritable bowel syndrome or chronic abdominal pain (it may be done to rule out organic disease, especially when symptoms do not respond to therapy); acute diarrhea; hemorrhoids; routine follow-up of inflammatory bowel disease (cancer surveillance in Crohn's disease or chronic ulcerative colitis excepted); routine examination before elective abdominal surgery for a non-colonic disease; upper GI bleeding or black tarry stool with a demonstrated upper GI source; fulminant colitis; possible perforation; acute severe diverticulitis; or diverticulosis as the reason for the test (it may still be reported when it is the final diagnosis).

Type: exclusion
Source: LCD L34005 v34 cov-036 to cov-039, cov-041 to cov-043, cov-045 to cov-049.
