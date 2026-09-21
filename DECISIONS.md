# ClaimSense — Decision log

Decisions made after `INSTRUCTIONS.md` was written. Where they differ, this file wins.
Add rows only for decisions the team has made.

| Date | Decision | Reason |
|---|---|---|
| 2026-09-21 | Rule failures are automatic: REJECT (return to provider), DENY (reason code) or PEND; no human edit review. A failure on a low-confidence field becomes REJECT, never DENY. | Rules are factual checks; avoids wrong denials from OCR errors |
| 2026-09-21 | Every SLM recommendation is human-reviewed; review tier set by code from decision, complexity and amount | Compliance; task differentiation |
| 2026-09-21 | Claim-level decision derived by code from line decisions (APPROVE / PEND / DENY / PARTIAL) | Fewer model errors |
| 2026-09-21 | Pipeline is synchronous; Redis/RQ deferred to stretch | Simplicity for the prototype |
| 2026-09-21 | COB default: traditional (secondary pays the lesser of its normal payment and the remaining balance) | Needs a defined rule for the calculator |
| 2026-09-21 | INSTRUCTIONS.md v1.0 adopted as the implementation specification | Single source of truth |
| 2026-09-21 | No pull requests. Each task is built on a local `p<phase>.<task>` branch, merged into `main` locally, and pushed only when a team member says so. Overrides H13 and the pull-request steps in §11, §12 and §14. | Team reviews changes together before pushing |
| 2026-09-21 | Laptop (Manideep3183): Apple M5, 16 GB RAM, macOS, no NVIDIA GPU. Training and server machines to be decided. | Hardware record (SETUP Part G) |
| 2026-09-21 | Curated data (`data/curated/`) and golden test cases (`tests/golden/`) are synthesized by Claude instead of hand-written. Insurance values are fictional; codes come only from `data/raw/`; every coverage criterion and CARC/RARC mapping cites its source in `data/raw/`; every golden expected value shows its worked steps; golden cases are written before the code they test. The team spot-checks a sample before use (about 10 rules cases, 10 calculator cases, 3 policies). Overrides H6/H12 and the "written by the team" wording in §9.2 and §9.5. | Team chose not to hand-write this data (2026-09-21) |
| 2026-09-21 | Procedure scope (C1): office visits 99202–99205 and 99211–99215, plus 17 coverage policies built from these LCDs: L37373 MRI/CT head and neck, L33619 extremity ultrasound, L37379 echocardiography, L34636 ECG monitoring, L35050 sleep studies, L34594 nerve conduction, L33261 allergy testing, L34520 psychological testing, L33906 epidural steroid injections, L33930 facet joint, L33558 cataract, L34005 colonoscopy, L34209 varicose veins, L33944 blepharoplasty, L33941 routine foot care, L34428 outpatient physical therapy, L38902 wound care. Lab tests and drugs excluded (not priced by the PFS). Test-only policies (never in training): L34594, L34209, L35050, L33619. | Every code has a PFS price, an LCD and covered ICD-10 lists in `data/raw/mcd/` |
| 2026-09-21 | Dates of service (R1): 2026-10-01 to 2026-12-31. Code sets: ICD-10-CM FY2027, HCPCS October 2026, NCCI PTP v323r0 and MUE effective 2026-10-01, PFS RVU26A. | All files in `data/raw/` cover this window |
| 2026-09-21 | Allowed amounts (D6): PFS national non-facility amount (total non-facility RVU × conversion factor 33.4009), rounded half-up to cents; in-network allowed = 125%, out-of-network allowed = 100% of that amount. | Defined, reproducible fee schedule for the calculator |
| 2026-09-21 | Accumulators (D7): deductibles and out-of-pocket totals reset every 1 January (calendar year); copays count toward the out-of-pocket maximum. | Needed by the calculator |
| 2026-09-21 | Rule order (D8): Group A = R01–R04 and the duplicate check (any failure → REJECT, stop). Group B = R05–R10, all evaluated, precedence REJECT > DENY > PEND. Group C = R11–R13 (line-level). | Resolves the §8.3 gaps |
| 2026-09-21 | Contracts (D2, D3): add `ContextPackage` to `app/domain/contracts.py`; output validation rejects a line whose benefit category is not one of that line's candidate categories (→ PEND, `MODEL_OUTPUT_INVALID`). | Context is stored in every decision record; the benefit category drives cost share |
| 2026-09-21 | SME claim example (`docs/sme-claim-example.json`) is a reference view; `IntakeClaim` follows §8.1. Mapping in `docs/claim-schema-mapping.md`. | The claim carries only CMS-1500 data; eligibility, network and coverage are looked up |
