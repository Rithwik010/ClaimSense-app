# Contracts review (task P1.4)

**Status: approved by the team on 2026-09-22 and frozen** (`DECISIONS.md`). Later changes need a
proposal and a `DECISIONS.md` entry (H11). Changing the model output or the context shown to the
model means regenerating the decision dataset and retraining.

## What to check (about 15 minutes)

1. Open `app/domain/contracts.py` and `tests/unit/test_contracts.py`.
2. Compare the models with INSTRUCTIONS.md §8.1 and the differences below.
3. Reply "contracts approved" (or list changes). Approval is then recorded in `DECISIONS.md`.

## Differences from §8.1

| Model | Change | Why |
|---|---|---|
| `ContextPackage` (+ `LineContext`, `BenefitFact`, `RetrievedCriterion`) | Added | DECISIONS.md D2: the context is stored in every decision record. It has no money fields |
| `IntakeClaim.patient` | Structured: first and last name, date of birth, sex, address | Matches CMS-1500 Boxes 2, 3, 5 |
| `IntakeClaim.diagnoses` | Stored without dots, uppercase (`M54.16` → `M5416`) | Matches the ICD-10-CM code files |
| `IntakeClaim.frequency_code` | Only `"1"` accepted | Corrected and void claims are out of scope (§4) |
| `IntakeClaim.other_coverage` | Payer name + primary paid amount per line | Needed by the COB step of the calculator |
| `IntakeResult.field_confidences` | A dictionary (field path → 0–1) instead of a separate `FieldConfidence` model | Simpler; same content |
| `RuleResult` | Optional `line_no`; `rule_id` also allows `DUP` | Line-level rules R11–R13 and the duplicate check |
| `RulesOutcome.line_outcomes` | Typed `LineRuleOutcome` with reason codes and flags (e.g. `NCCI_BYPASS`) | Line flags reach the model and the explanation |
| `LineAmounts`, `CostBreakdown` | Every amount field ends in `_cents` | Makes the unit explicit (H2) |
| `DecisionRecord` | Added `output_errors`, `line_decisions` (who decided each line), `review` | Needed for explanations and review |
| `CriterionResult` | `status` (MET / NOT_MET / NOT_DOCUMENTED / NOT_APPLICABLE) instead of `met` true/false; added at approval | Retrieved criteria that do not apply to the claim, and "not documented" no longer depends on the evidence text |

## Validation built into the contracts

- NPI check digit (billing, rendering, referring); TIN 9 digits.
- Code formats: ICD-10-CM, procedure code (CPT/HCPCS), modifier, place of service, criterion ID.
- Money: non-negative integer cents only (floats and strings are rejected).
- Diagnosis pointers must point at a listed diagnosis; line numbers run 1, 2, 3, ...
- Unknown fields are rejected everywhere (so the SME example's `covered_service`, `network_status`
  and similar fields cannot be submitted on a claim; see `docs/claim-schema-mapping.md`).
- `SLMOutput` has no money fields and its JSON schema forbids extra properties.
- `ReviewAction`: ACCEPT has no overrides; OVERRIDE needs at least one line with a reason.

Whether a code actually exists, and every business rule, is checked by the rules engine (P2.3),
not by the contracts.
