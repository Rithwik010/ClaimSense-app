# SME claim example → ClaimSense design

Source: `docs/sme-claim-example.json` (generic schema shared by the SMEs, transcribed 2026-09-21).
Target: the contracts in INSTRUCTIONS.md §8.1, frozen in task P1.4.

The SME example is a *decision-ready* view: it mixes what the provider submits with facts the
payer looks up (eligibility, network, authorization) and with plan terms. ClaimSense keeps those
apart: the claim carries only what is on a CMS-1500, and the rules engine looks everything else up
in the database, so a claim can never assert its own eligibility or coverage.

## Field mapping

| SME field | ClaimSense location | Notes |
|---|---|---|
| `claim.id` | `IntakeClaim.claim_id` | |
| `claim.member.id` | `IntakeClaim.member_id` | Box 1a |
| `claim.member.name` | `IntakeClaim.patient.name` | Box 2 |
| `claim.member.active` | `members` table (coverage start/end) → rule R05 | Looked up, not submitted |
| `claim.member.plan_type` | `members.plan_id` → `plans.plan_type` | Looked up |
| `claim.member.effective` | `members.coverage_start` | Looked up |
| `claim.provider.npi` | `IntakeClaim.billing_npi`, `ServiceLine.rendering_npi` | Boxes 33a, 24J; check digit validated by R03. The example's `1234567890` fails the check digit |
| `claim.provider.name` | `providers` table | Looked up |
| `claim.provider.network_status` | `provider_networks` table → rule R08 | Looked up per plan |
| `claim.provider.enrolled` | `providers.enrollment_status` → rule R06 | Looked up |
| `claim.date_of_service` | `ServiceLine.date_of_service` | Box 24A is per line on a CMS-1500 |
| `claim.submitted_at` | `IntakeClaim.received_date` | Date only |
| `claim.covered_service` | Derived: exclusions (R13), benefits and the SLM decision | Never submitted |
| `claim.referral_obtained` | `IntakeClaim.referring_npi` (Box 17b) → rule R09 | |
| `claim.authorization_obtained` | `IntakeClaim.prior_auth_number` (Box 23) + `authorizations` table → rule R10 | |
| `service_lines[].cpt_code` | `ServiceLine.procedure_code` | Box 24D; also HCPCS Level II |
| `service_lines[].icd10_code` | `IntakeClaim.diagnoses` (Box 21 A–L) + `ServiceLine.diagnosis_pointers` (Box 24E) | Diagnoses are claim-level on a CMS-1500 |
| `service_lines[].description` | `data/curated/procedure_descriptions.csv` | Not on the claim; never AMA CPT text (H10) |
| `service_lines[].charge_cents` | `ServiceLine.charge_cents` | Box 24F |
| `plan.*` | `plans`, `benefits`, `fee_schedule` tables (H16) | Plan facts come from the database |
| `plan.timely_filing_days` | `plans.filing_window_inn_days` / `filing_window_oon_days` | R07 uses separate in/out-of-network windows |
| `plan.in_network_copay_cents` | `benefits.copay_cents` | Per benefit category |
| `plan.in_network_allowed_cents` | `fee_schedule.inn_allowed_cents` | Per procedure code |
| `plan.out_of_network_allowed_pct` | `fee_schedule.oon_allowed_cents` | Stored as cents, not a float (H2) |
| `plan.out_of_network_coinsurance_pct` | `plans.oon_coinsurance_bps` | Basis points: 40% = 4000 (H2) |
| `plan.covers_out_of_network` | `plans.oon_covered` → rule R08 | |
| `plan.requires_referral` | `plan_referral_rules` | R09, per provider type |
| `plan.usual_customary_cents` | `fee_schedule.oon_allowed_cents` | |

## CMS-1500 fields the SME example does not have

Patient date of birth, sex and address (Boxes 3, 5); subscriber relationship (Box 6); billing TIN
(Box 25); place of service (24B); modifiers (24D); units (24G); up to 12 diagnoses (Box 21);
frequency code (Box 22); clinical notes (attachment); other coverage (Boxes 9, 11d).

## Recommendation for P1.4

Keep `IntakeClaim` as in §8.1 (it matches the form that intake and OCR read). Use the SME example
as a reference for field naming and as an optional export view built from a finished decision
record.
