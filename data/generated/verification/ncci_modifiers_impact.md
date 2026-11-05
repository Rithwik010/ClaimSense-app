# P2.3c planning: NCCI modifiers and the reference tables

## Modifiers billed

- dataset test: XS x 16
- dataset train: XS x 141
- dataset validation: XS x 17
- golden e2e: XS x 1
- golden rules: 5 x 1
- golden rules: 50 x 4
- golden rules: LT x 3
- golden rules: Q8 x 1
- golden rules: RT x 6
- golden rules: XS x 3

## R11 changes against v1 (every changed line)

### Option A (v1 + 59): 0 changed lines; office visits with 25 among them: 0


### Option B (full list, manual placement; approved, D-RULE-8): 0 changed lines; office visits with 25 among them: 0


### Option B on either line (no placement): 1 changed lines; office visits with 25 among them: 0

| Source | Case | Line | Code | Modifiers | R11 | Scenario | Label |
|---|---|---|---|---|---|---|---|
| golden rules | R11-06 | 2 | 45380 | LT | DENY -> BYPASS | - | - |

- golden rules: 1

## File-backed against database-backed tables (R11, R12)

Lines billing a code outside the 60-code scope: golden rules 11

Lines whose R11 or R12 result differs (file / database): 0
