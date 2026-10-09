# ClaimSense — Public data sources

Files live in `data/raw/<source>/<version>/` (gitignored, never committed). They were downloaded
by the team and received into the repo on 2026-09-21. Downloads are done by people, never by code
(INSTRUCTIONS.md §9.1). Never copy AMA CPT descriptor text into the repository (H10).

## In `data/raw/`

| Source | Version | Folder | Files | Page | License / terms |
|---|---|---|---|---|---|
| NUCC 1500 Claim Form Reference Instruction Manual | v13.0, 07/2025 | `nucc/v13/` | `1500_claim_form_instruction_manual_2025_07-v13.pdf` | [nucc.org](https://www.nucc.org/index.php/1500-claim-form-mainmenu-35/1500-instructions-mainmenu-42) | NUCC publication; see nucc.org terms |
| Blank CMS-1500 claim form | 02/12 | `nucc/v13/` | `1500_claim_form_2012_02.pdf` | [nucc.org](https://www.nucc.org/index.php/1500-claim-form-mainmenu-35) | NUCC publication; see nucc.org terms |
| Medicare Claims Processing Manual, Ch. 26 (CMS-1500 data set) | as downloaded | `cms-manual/ch26/` | `clm104c26.pdf` | [cms.gov](https://www.cms.gov/regulations-and-guidance/guidance/manuals/downloads/clm104c26pdf.pdf) | CMS (US government work) |
| ICD-10-CM Official Guidelines for Coding and Reporting | FY2027 (effective 2026-10-01) | `icd10cm/FY2027/` | `icd_10_cm_october_1_2026_fy27_guidelines.pdf` | [cms.gov](https://www.cms.gov/medicare/coding-billing/icd-10-codes) | CMS/NCHS (US government work) |
| ICD-10-CM code descriptions in tabular order (74,879 codes) | FY2027 (effective 2026-10-01) | `icd10cm/FY2027/` | `2027-code-descriptions-tabular-order.zip` | [cms.gov](https://www.cms.gov/medicare/coding-billing/icd-10-codes) | CMS/NCHS (US government work) |
| ICD-10-CM code tables, tabular and index (XML and PDF; used for the tabular's categories and inclusion terms, D-RULE-3) | FY2027 (effective 2026-10-01) | `icd10cm/FY2027/` | `Table and Index.zip` (added 2026-10-09; re-zipped on a Mac, so it holds `__MACOSX` entries and its SHA-256 is not that of the CMS download) | [cms.gov](https://www.cms.gov/files/zip/2027-code-tables-tabular-index.zip) | CMS/NCHS (US government work) |
| HCPCS Level II alpha-numeric file | October 2026, v2 | `hcpcs/2026-10/` | `HCPC2026_OCT_ANWEB_v2.txt` / `.xlsx`, record layout, transaction report, corrections, NOC codes, procedure notes | [cms.gov](https://www.cms.gov/medicare/coding-billing/healthcare-common-procedure-system/quarterly-update) | CMS (US government work) |
| Place of Service code set | 2024-05-02 | `pos/2024-05-02/` | `Website_POS_database__5_2_24 (kmk).pdf` | [cms.gov](https://www.cms.gov/medicare/coding-billing/place-of-service-codes/code-sets) | CMS (US government work) |
| NCCI PTP edits, practitioner: full edit tables (2,637,645 pairs; row counts match CMS) | v323r0, effective 2026-10-01 | `ncci-ptp/ccipra-v323r0-f1/` … `-f4/` | `ccipra-v323r0-f1.TXT` … `-f4.txt` (+ `.xlsx`; f1 restored 2026-10-03, see the note below) | [cms.gov](https://www.cms.gov/medicare/coding-billing/national-correct-coding-initiative-ncci-edits/medicare-ncci-procedure-procedure-ptp-edits) | Contains CPT® (© AMA); AMA license accepted at download by the team |
| NCCI PTP edits, practitioner: quarterly changes only | effective 2026-10-01 | `ncci-ptp/2026-10-changes-only/` | additions, deletions, modifier-indicator changes | [cms.gov](https://www.cms.gov/medicare/coding-billing/national-correct-coding-initiative-ncci-edits/medicare-ncci-procedure-procedure-ptp-edits) | Contains CPT® (© AMA); AMA license accepted at download |
| MUE table, practitioner services | effective 2026-10-01 (used: DECISIONS.md R1) | `mue/2026-10/` | `MCR_MUE_PractitionerServices_Eff_10-01-2026.csv` / `.xlsx` | [cms.gov](https://www.cms.gov/medicare/coding-billing/national-correct-coding-initiative-ncci-edits/medicare-ncci-medically-unlikely-edits) | Contains CPT® (© AMA); AMA license accepted by the team |
| MUE table, practitioner services | effective 2026-07-01 | `mue/2026-07/` | `MCR_MUE_PractitionerServices_Eff_07-01-2026.csv` / `.xlsx` | [cms.gov](https://www.cms.gov/medicare/coding-billing/national-correct-coding-initiative-ncci-edits/medicare-ncci-medically-unlikely-edits) | Contains CPT® (© AMA); AMA license accepted at download |
| Physician Fee Schedule relative value files | RVU26A (January 2026) | `pfs/rvu26a/` | `PPRRVU2026_Jan_*`, `GPCI2026`, `26LOCCO`, `ANES2026`, `OPPSCAP_Jan`, `RVU26AR.pdf` | [cms.gov](https://www.cms.gov/medicare/payment/fee-schedules/physician/pfs-relative-value-files) | Contains CPT® (© AMA); AMA license accepted at download |
| Medicare Coverage Database | as downloaded | `mcd/2026-09-21/` | `ncd.zip`, `current_lcd.zip`, `current_article.zip`, `all_lcd.zip`, `all_article.zip` | [cms.gov](https://www.cms.gov/medicare-coverage-database/downloads/downloads.aspx) | CMS; see MCD page terms (LCDs and Articles may contain CPT®) |
| Claim Adjustment Reason Codes (CARC) | page saved 2026-09-21 | `carc-rarc/2026-09-21/` | `Claim Adjustment Reason Codes _ X12.html` | [x12.org](https://x12.org/codes/claim-adjustment-reason-codes) | © X12; X12 terms of use. Commit code numbers only, not descriptions |
| Remittance Advice Remark Codes (RARC) | page saved 2026-09-21 | `carc-rarc/2026-09-21/` | `Remittance Advice Remark Codes _ X12.html` | [x12.org](https://x12.org/codes/remittance-advice-remark-codes) | © X12; X12 terms of use. Commit code numbers only, not descriptions |
| Uniform Glossary (English) | 2023-06-07 | `sbc/2023-06-07/` | `Uniform-Glossary English-060723.pdf` | [cms.gov](https://www.cms.gov/marketplace/resources/forms-reports-other#Summary_of_Benefits_and_Coverage_and_Uniform_Glossary) | CMS/DOL (US government work) |
| SBC template (English) | 2024-11-04 | `sbc/template-2024-11-04/` | `english-sbc-template-accessible-format-110424.pdf`, `english-sbc-template-standard-format-110424.docx` | [cms.gov](https://www.cms.gov/marketplace/resources/forms-reports-other#Summary_of_Benefits_and_Coverage_and_Uniform_Glossary) | CMS/DOL (US government work) |
| Sample completed SBC (English) | 2025-01-28 | `sbc/sample-2025-01-28/` | `english-sample-completed-sbc-accessible-format-012825.pdf`, `english-sample-completed-sbc-standard-format-012825.doc` | [cms.gov](https://www.cms.gov/marketplace/resources/forms-reports-other#Summary_of_Benefits_and_Coverage_and_Uniform_Glossary) | CMS/DOL (US government work) |
| Cigna Companion Guide: 837 Professional (Evernorth is part of The Cigna Group) | v1.18 | `payer-guides/2026-09-21/` | `5010-837P-companion-guide.pdf` | [cigna.com](https://www.cigna.com/static/www-cigna-com/docs/5010-837P-companion-guide.pdf) | © Cigna; public download, reference only |
| Evernorth e-course: medical and behavioral claim submission by EDI | © 2021 | `payer-guides/2026-09-21/` | `medBehaviorClaimSubmit.pdf` | [evernorth.com](https://static.evernorth.com/assets/evernorth/provider/pdf/resourceLibrary/eCourses/medical/ediOptions/medBehaviorClaimSubmit.pdf) | © Evernorth; public download, reference only |

**NCCI part f1 restored (2026-10-03).** The f1 `.txt` (`ccipra-v323r0-f1.TXT`) was lost from
`data/raw/` (missing since 2026-09-22), and the CMS download was blocked (access denied) on
2026-10-03, so G2 read f1 from `ccipra-v323r0-f1.xlsx`, the official file from the same CMS
release. Later on 2026-10-03 (P2.3a) the team supplied the original f1 download: its `.xlsx` is
byte-identical (SHA-256) to the one in `data/raw/`, and its `.TXT` parses to exactly the same
675,157 edit records, including (11042, 97597). The `.TXT` was put back and listed in
`data/raw_manifest.csv` (D-DATA-1), so f1 is read from its `.txt` again. `app/db/raw.py` still
falls back to a part's `.xlsx` when its `.txt` is missing. For every part f1–f4 the `.xlsx` gives
the same edit records as the `.txt`; f1–f4 total 2,637,645 (`tests/unit/test_raw_sources.py`).

## Still to download

Nothing outstanding.

## Open question: AMA CPT license

CMS's NCCI, MUE and PFS downloads sit behind an AMA license that authorizes CPT use "internally
within your organization within the United States" and limits use "to use in Medicare, Medicaid
or other programs administered by CMS". The team downloaded these files and is confirming with its guide / Evernorth that a private,
non-commercial academic prototype is acceptable; record the outcome in `DECISIONS.md`. Until then:
never commit or publish CPT-containing files, datasets or models.
