# R11 modifier golden cases: independent check (Task G5)

For one reviewer, or a separate Claude chat that sees only this sheet (D-GOLD-2). Work out each case from the inputs, the facts and the rule text, then fill in the blank cells. **Do not open data/generated/verification/new_golden/ until every cell is filled.**

## Rule text

R11 (A-R3 as amended by D-RULE-8; RULES_VERSION 2.1.0). For two lines on the same date of service,
the first NCCI edit active that day with line A's code in column 1 and line B's in column 2 applies
(indicator 9: none). Indicator 0: line B is denied, DN_NCCI_BUNDLED. Indicator 1: line B passes
with the flag NCCI_BYPASS when an NCCI PTP-associated modifier is reported where the manual places
it, and is denied DN_NCCI_BUNDLED otherwise. The modifiers and their places:

- 59, XE, XP, XS, XU: on either line, but not on an E&M line.
- 24, 25, 57: on an E&M line paired with a non-E&M code; 25 only when that code's PFS global period
  is 000, 010 or XXX; 57 only when it is 090.
- 58, 78, 79: on a non-E&M line (either column).
- 27, 91: on either line.
- Anatomic (E1-E4, FA, F1-F9, TA, T1-T9, LT, RT, LC, LD, RC, LM, RI): only when both lines carry an
  anatomic modifier and they share none (different sites).

E&M lines are the office visit codes 99202-99205 and 99211-99215. A line with no reason code
passes; when every line is denied the claim is DENY, otherwise PASS. Every claim below passes
Groups A and B and rules R12 to R20; only R11 decides.

Claim statuses (INSTRUCTIONS.md section 5; a PASS claim stays RECEIVED, a DENY claim is DENIED_BY_RULE):

| Status | Meaning |
|---|---|
| `RECEIVED` | Intake complete |
| `REJECTED` | Rule failure: data problem; returned to provider (final) |
| `DENIED_BY_RULE` | Rule failure: hard requirement not met (final) |
| `PENDED_BY_RULE` | Rule failure: information not yet available (e.g. provider enrollment pending) |
| `AWAITING_REVIEW` | SLM recommendation and calculation ready for a human |
| `FINAL_APPROVED` | Reviewer confirmed; all lines approved |
| `FINAL_PARTIAL` | Reviewer confirmed; some lines approved, some denied |
| `FINAL_DENIED` | Reviewer confirmed; all lines denied |
| `FINAL_PENDED` | Reviewer confirmed that information is missing |

## Cases

### Case 1 (R11-10)

| Line | Date | Code | Units | Modifiers |
|---|---|---|---|---|
| 1 | 2026-10-06 | 45385 | 1 | - |
| 2 | 2026-10-06 | 45380 | 1 | 59 |

Facts: NCCI 45385/45380 (column 1/column 2): modifier indicator 1; 45385: not E&M, PFS global 000; 45380: not E&M, PFS global 000.

Claim outcome (PASS / DENY): ____ | Status: ____

| Line | Outcome (PASS / DENY) | Reason codes | Flags |
|---|---|---|---|
| 1 |  |  |  |
| 2 |  |  |  |

### Case 2 (R11-11)

| Line | Date | Code | Units | Modifiers |
|---|---|---|---|---|
| 1 | 2026-10-06 | 11720 | 1 | - |
| 2 | 2026-10-06 | 99213 | 1 | 59 |

Facts: NCCI 11720/99213 (column 1/column 2): modifier indicator 1; 11720: not E&M, PFS global 000; 99213: E&M, PFS global XXX.

Claim outcome (PASS / DENY): ____ | Status: ____

| Line | Outcome (PASS / DENY) | Reason codes | Flags |
|---|---|---|---|
| 1 |  |  |  |
| 2 |  |  |  |

### Case 3 (R11-12)

| Line | Date | Code | Units | Modifiers |
|---|---|---|---|---|
| 1 | 2026-10-06 | 11720 | 1 | - |
| 2 | 2026-10-06 | 99213 | 1 | XU |

Facts: NCCI 11720/99213 (column 1/column 2): modifier indicator 1; 11720: not E&M, PFS global 000; 99213: E&M, PFS global XXX.

Claim outcome (PASS / DENY): ____ | Status: ____

| Line | Outcome (PASS / DENY) | Reason codes | Flags |
|---|---|---|---|
| 1 |  |  |  |
| 2 |  |  |  |

### Case 4 (R11-13)

| Line | Date | Code | Units | Modifiers |
|---|---|---|---|---|
| 1 | 2026-10-06 | 11720 | 1 | - |
| 2 | 2026-10-06 | 99213 | 1 | 25 |

Facts: NCCI 11720/99213 (column 1/column 2): modifier indicator 1; 11720: not E&M, PFS global 000; 99213: E&M, PFS global XXX.

Claim outcome (PASS / DENY): ____ | Status: ____

| Line | Outcome (PASS / DENY) | Reason codes | Flags |
|---|---|---|---|
| 1 |  |  |  |
| 2 |  |  |  |

### Case 5 (R11-14)

| Line | Date | Code | Units | Modifiers |
|---|---|---|---|---|
| 1 | 2026-10-06 | 11720 | 1 | 25 |
| 2 | 2026-10-06 | 99213 | 1 | - |

Facts: NCCI 11720/99213 (column 1/column 2): modifier indicator 1; 11720: not E&M, PFS global 000; 99213: E&M, PFS global XXX.

Claim outcome (PASS / DENY): ____ | Status: ____

| Line | Outcome (PASS / DENY) | Reason codes | Flags |
|---|---|---|---|
| 1 |  |  |  |
| 2 |  |  |  |

### Case 6 (R11-15)

| Line | Date | Code | Units | Modifiers |
|---|---|---|---|---|
| 1 | 2026-10-06 | 66982 | 1 | - |
| 2 | 2026-10-06 | 99213 | 1 | 25 |

Facts: NCCI 66982/99213 (column 1/column 2): modifier indicator 1; 66982: not E&M, PFS global 090; 99213: E&M, PFS global XXX.

Claim outcome (PASS / DENY): ____ | Status: ____

| Line | Outcome (PASS / DENY) | Reason codes | Flags |
|---|---|---|---|
| 1 |  |  |  |
| 2 |  |  |  |

### Case 7 (R11-16)

| Line | Date | Code | Units | Modifiers |
|---|---|---|---|---|
| 1 | 2026-10-06 | 66982 | 1 | - |
| 2 | 2026-10-06 | 99213 | 1 | 57 |

Facts: NCCI 66982/99213 (column 1/column 2): modifier indicator 1; 66982: not E&M, PFS global 090; 99213: E&M, PFS global XXX.

Claim outcome (PASS / DENY): ____ | Status: ____

| Line | Outcome (PASS / DENY) | Reason codes | Flags |
|---|---|---|---|
| 1 |  |  |  |
| 2 |  |  |  |

### Case 8 (R11-17)

| Line | Date | Code | Units | Modifiers |
|---|---|---|---|---|
| 1 | 2026-10-06 | 11720 | 1 | - |
| 2 | 2026-10-06 | 99213 | 1 | 57 |

Facts: NCCI 11720/99213 (column 1/column 2): modifier indicator 1; 11720: not E&M, PFS global 000; 99213: E&M, PFS global XXX.

Claim outcome (PASS / DENY): ____ | Status: ____

| Line | Outcome (PASS / DENY) | Reason codes | Flags |
|---|---|---|---|
| 1 |  |  |  |
| 2 |  |  |  |

### Case 9 (R11-18)

| Line | Date | Code | Units | Modifiers |
|---|---|---|---|---|
| 1 | 2026-10-06 | 99213 | 1 | - |
| 2 | 2026-10-06 | 99212 | 1 | 25 |

Facts: NCCI 99213/99212 (column 1/column 2): modifier indicator 1; 99213: E&M, PFS global XXX; 99212: E&M, PFS global XXX.

Claim outcome (PASS / DENY): ____ | Status: ____

| Line | Outcome (PASS / DENY) | Reason codes | Flags |
|---|---|---|---|
| 1 |  |  |  |
| 2 |  |  |  |

### Case 10 (R11-19)

| Line | Date | Code | Units | Modifiers |
|---|---|---|---|---|
| 1 | 2026-10-06 | 45385 | 1 | - |
| 2 | 2026-10-06 | 45380 | 1 | 58 |

Facts: NCCI 45385/45380 (column 1/column 2): modifier indicator 1; 45385: not E&M, PFS global 000; 45380: not E&M, PFS global 000.

Claim outcome (PASS / DENY): ____ | Status: ____

| Line | Outcome (PASS / DENY) | Reason codes | Flags |
|---|---|---|---|
| 1 |  |  |  |
| 2 |  |  |  |

### Case 11 (R11-20)

| Line | Date | Code | Units | Modifiers |
|---|---|---|---|---|
| 1 | 2026-10-06 | 11720 | 1 | - |
| 2 | 2026-10-06 | 99213 | 1 | 58 |

Facts: NCCI 11720/99213 (column 1/column 2): modifier indicator 1; 11720: not E&M, PFS global 000; 99213: E&M, PFS global XXX.

Claim outcome (PASS / DENY): ____ | Status: ____

| Line | Outcome (PASS / DENY) | Reason codes | Flags |
|---|---|---|---|
| 1 |  |  |  |
| 2 |  |  |  |

### Case 12 (R11-21)

| Line | Date | Code | Units | Modifiers |
|---|---|---|---|---|
| 1 | 2026-10-06 | 76881 | 1 | RT |
| 2 | 2026-10-06 | 76882 | 1 | LT |

Facts: NCCI 76881/76882 (column 1/column 2): modifier indicator 1; 76881: not E&M, PFS global XXX; 76882: not E&M, PFS global XXX.

Claim outcome (PASS / DENY): ____ | Status: ____

| Line | Outcome (PASS / DENY) | Reason codes | Flags |
|---|---|---|---|
| 1 |  |  |  |
| 2 |  |  |  |

### Case 13 (R11-22)

| Line | Date | Code | Units | Modifiers |
|---|---|---|---|---|
| 1 | 2026-10-06 | 76881 | 1 | RT |
| 2 | 2026-10-06 | 76882 | 1 | RT |

Facts: NCCI 76881/76882 (column 1/column 2): modifier indicator 1; 76881: not E&M, PFS global XXX; 76882: not E&M, PFS global XXX.

Claim outcome (PASS / DENY): ____ | Status: ____

| Line | Outcome (PASS / DENY) | Reason codes | Flags |
|---|---|---|---|
| 1 |  |  |  |
| 2 |  |  |  |
