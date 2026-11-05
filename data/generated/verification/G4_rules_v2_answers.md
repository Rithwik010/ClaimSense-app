# Rules v2 golden cases: independent check (Task G4)

For one reviewer, or a separate Claude chat that sees only this sheet (D-GOLD-2). Work out each case from the inputs, the facts and the rule text below, then fill in the blank cells. **Do not open data/generated/verification/new_golden/ until every cell is filled.**

Every claim below passes Groups A and B (eligibility, provider, filing, network, referral and authorization are in order); only Group C decides.

## Rule text (D-RULE-2 to D-RULE-4, D-RULE-7)

Group C runs on every line of a claim that passed Groups A and B. Every rule is evaluated on every
line; a line's reason codes and flags are listed in rule order (R11, R12, R13, then R14 to R20) and
the first reason code is the primary one. A line with any reason code is denied; a line with only
flags passes. When every line is denied, the claim is DENY; otherwise PASS. A flag never denies.
D-RULE-2: a rule denies only when the LCD or article is explicit and the check needs nothing beyond
the claim; limits worded "usually"/"rarely" or with a documented exception give a flag.

- R11 (A-R3): for two lines on the same date, the first NCCI edit active that day with line A's
  code in column 1 and line B's in column 2 applies (indicator 9: none). Indicator 1 with a bypass
  modifier (XE, XP, XS, XU) on either line: line B passes with the flag NCCI_BYPASS; otherwise
  line B is denied, DN_NCCI_BUNDLED.
- R12 (A-R4): the units of one code on one date, added over the lines, above the MUE limit deny
  every line of that code and date, DN_MUE_EXCEEDED.
- R13: a code on the plan's exclusion list is denied, DN_EXCLUDED.
- R14 (L33906): an ESI line (62321, 62323, 64479, 64483) is denied, DN_MULTIPLE_BLOCKS, when another
  block is billed on the same date: a different ESI code, or a facet joint injection (64490,
  64493). Not other blocks: add-on level codes (64480, 64484, 64491, 64494), radiofrequency
  denervation (64633-64636), the same code on another line. Exception: a facet injection whose own
  diagnoses include a facet synovial cyst code (M71.30, M71.38) is not a block. Only ESI lines are
  denied; when two ESI codes meet, both are. Every billed line counts, even one another rule denies.
  A denied ESI's own add-on lines on the same date (64480 with 64479, 64484 with 64483) are denied
  with it, DN_MULTIPLE_BLOCKS (D-RULE-7).
- R15 (billing articles): a line's own diagnoses (its pointers) must meet one of its code's
  alternatives; codes with no article are not checked. A group is met when one of the line's
  diagnoses is in it. 66982: group 1 only. Colonoscopy (45378, 45380, 45385): group 1, or the line's
  first diagnosis in group 2A with a group 2B code among the others. Foot care (11720, 11721):
  groups 1, 3 or 4, or group 2 when modifier Q7, Q8 or Q9 is billed. Fails: DN_DX_NOT_SUPPORTED.
- R16 (L35050): a home sleep test line (95800, 95801, 95806, G0398-G0400) with a parasomnia
  diagnosis (G47.50-G47.59) among its own is denied, DN_HOME_TEST_PARASOMNIA.
- R17 (L34594, "usually"): every nerve conduction line (95907-95913) with no needle EMG line
  (95860-95870, 95872, 95885-95887) anywhere on the claim gets the flag NCS_WITHOUT_EMG; carpal
  tunnel included; never a denial.
- R18 (L33906): transforaminal levels per date and region (64483 + add-on 64484; 64479 + 64480),
  counted per side: an RT or LT line counts on its side; modifier 50 or no side modifier on both
  sides. If either side has more than 2 levels, the add-on lines counting on that side are denied,
  DN_ESI_LEVELS. An interlaminar or caudal ESI (62321, 62323) with modifier 50 is denied,
  DN_ESI_LEVELS.
- R19 (L33930, A57787): a third-level facet code (64492, 64495) is denied, DN_FACET_LEVELS. Facet
  codes of both regions on one date (cervical/thoracic 64490-64492, 64633-64634; lumbar/sacral
  64493-64495, 64635-64636) give every facet line that date the flag FACET_TWO_REGIONS.
- R20 (L34520): testing minutes on the claim from 96130 (60 per unit), 96131 (60) and 96136 (30);
  above 480, every testing line gets the flag EXTENDED_TESTING.
- H5: a failing rule whose fields include a field read below 0.85 becomes REJECT
  RJ_LOW_CONFIDENCE_FIELD, never DENY; the claim is then REJECT with no line outcomes. R15 reads
  the line's code, pointers and pointed diagnoses.

Article groups: A56456 group 2 is 2A and group 3 is 2B.

## Rules cases

### Case 1 (R14-01)

Diagnoses: A M5416, B M47816

| Line | Date | Code | Units | Modifiers | Pointers |
|---|---|---|---|---|---|
| 1 | 2026-10-06 | 64483 | 1 | - | A |
| 2 | 2026-10-06 | 64493 | 1 | - | B |

Facts: MUE 64483: 1; MUE 64493: 1; R15 for 64483 (A56651): group 1; 64483 -> A56651: M5416 in groups [1]; 64483 -> A56651: M47816 in groups none; R15 for 64493 (A57787): group 1; 64493 -> A57787: M5416 in groups none; 64493 -> A57787: M47816 in groups [1].

Claim outcome (PASS / DENY / REJECT): PASS

| Line | Outcome (PASS / DENY) | Reason codes in order | Flags |
|---|---|---|---|
| 1 | DENY | DN_MULTIPLE_BLOCKS | — |
| 2 | PASS | — | — |

Why: R14 fails line 1. ESI 64483 is billed the same day as facet 64493, and the facet's own diagnosis M47816 is not a cyst code, so the facet is a block. R14 denies only the ESI line. R15 passes both lines (M5416 is in group 1 for 64483, M47816 in group 1 for 64493), as do R12 and R18 (1 level a side). One line passes, so the claim is PASS.

### Case 2 (R14-02)

Diagnoses: A M5416, B M47816

| Line | Date | Code | Units | Modifiers | Pointers |
|---|---|---|---|---|---|
| 1 | 2026-10-06 | 64483 | 1 | - | A |
| 2 | 2026-10-13 | 64493 | 1 | - | B |

Facts: MUE 64483: 1; MUE 64493: 1; R15 for 64483 (A56651): group 1; 64483 -> A56651: M5416 in groups [1]; 64483 -> A56651: M47816 in groups none; R15 for 64493 (A57787): group 1; 64493 -> A57787: M5416 in groups none; 64493 -> A57787: M47816 in groups [1].

Claim outcome (PASS / DENY / REJECT): PASS

| Line | Outcome (PASS / DENY) | Reason codes in order | Flags |
|---|---|---|---|
| 1 | PASS | — | — |
| 2 | PASS | — | — |

Why: R14 passes because the ESI and the facet are on different dates. R15 passes both lines (M5416 in group 1 for 64483, M47816 in group 1 for 64493). R12, R18 (1 level a side) and R19 also pass.

### Case 3 (R14-03)

Diagnoses: A M5416, B M7138

| Line | Date | Code | Units | Modifiers | Pointers |
|---|---|---|---|---|---|
| 1 | 2026-10-06 | 64483 | 1 | - | A |
| 2 | 2026-10-06 | 64493 | 1 | - | B |

Facts: MUE 64483: 1; MUE 64493: 1; R15 for 64483 (A56651): group 1; 64483 -> A56651: M5416 in groups [1]; 64483 -> A56651: M7138 in groups none; R15 for 64493 (A57787): group 1; 64493 -> A57787: M5416 in groups none; 64493 -> A57787: M7138 in groups [1].

Claim outcome (PASS / DENY / REJECT): PASS

| Line | Outcome (PASS / DENY) | Reason codes in order | Flags |
|---|---|---|---|
| 1 | PASS | — | — |
| 2 | PASS | — | — |

Why: R14 passes. The facet line's own diagnosis M7138 (M71.38) is a facet synovial cyst code, so 64493 is not a block. R15 passes both lines (M5416 in group 1, M7138 in group 1). R12 and R18 (1 level a side) pass.

### Case 4 (R14-04)

Diagnoses: A M5416

| Line | Date | Code | Units | Modifiers | Pointers |
|---|---|---|---|---|---|
| 1 | 2026-10-06 | 64483 | 1 | - | A |
| 2 | 2026-10-06 | 64484 | 1 | - | A |

Facts: MUE 64483: 1; MUE 64484: 4; R15 for 64483 (A56651): group 1; 64483 -> A56651: M5416 in groups [1]; 64484: no billing article (R15 does not check it).

Claim outcome (PASS / DENY / REJECT): PASS

| Line | Outcome (PASS / DENY) | Reason codes in order | Flags |
|---|---|---|---|
| 1 | PASS | — | — |
| 2 | PASS | — | — |

Why: R14 passes because 64484 is an add-on level code, not another block. R15 passes 64483 (M5416 in group 1) and does not check 64484. Neither line has a side modifier, so R18 counts 2 levels on each side, which is not above 2. R12 is within MUE.

### Case 5 (R14-05)

Diagnoses: A M5416

| Line | Date | Code | Units | Modifiers | Pointers |
|---|---|---|---|---|---|
| 1 | 2026-10-06 | 64483 | 1 | RT | A |
| 2 | 2026-10-06 | 64483 | 1 | LT | A |

Facts: MUE 64483: 1; R15 for 64483 (A56651): group 1; 64483 -> A56651: M5416 in groups [1].

Claim outcome (PASS / DENY / REJECT): DENY

| Line | Outcome (PASS / DENY) | Reason codes in order | Flags |
|---|---|---|---|
| 1 | DENY | DN_MUE_EXCEEDED | — |
| 2 | DENY | DN_MUE_EXCEEDED | — |

Why: R12 fails. 64483 is billed 1 + 1 = 2 units on 2026-10-06, above MUE 1, and the rule text adds units over lines with no exception for RT/LT, so both lines are denied. R14 passes (the same code on another line is not another block), as do R15 (M5416 in group 1) and R18 (1 level RT, 1 level LT).

### Case 6 (R14-06)

Diagnoses: A M5416, B M47816

| Line | Date | Code | Units | Modifiers | Pointers |
|---|---|---|---|---|---|
| 1 | 2026-10-06 | 64483 | 1 | - | A |
| 2 | 2026-10-06 | 64484 | 1 | - | A |
| 3 | 2026-10-06 | 64493 | 1 | - | B |

Facts: MUE 64483: 1; MUE 64484: 4; MUE 64493: 1; R15 for 64483 (A56651): group 1; 64483 -> A56651: M5416 in groups [1]; 64483 -> A56651: M47816 in groups none; 64484: no billing article (R15 does not check it); R15 for 64493 (A57787): group 1; 64493 -> A57787: M5416 in groups none; 64493 -> A57787: M47816 in groups [1].

Claim outcome (PASS / DENY / REJECT): PASS

| Line | Outcome (PASS / DENY) | Reason codes in order | Flags |
|---|---|---|---|
| 1 | DENY | DN_MULTIPLE_BLOCKS | — |
| 2 | DENY | DN_MULTIPLE_BLOCKS | — |
| 3 | PASS | — | — |

Why: R14 fails line 1 (ESI 64483 with facet 64493 the same day, and M47816 is not a cyst code). It also fails line 2, the denied ESI's own add-on 64484 on that date. The facet line 3 is not an ESI, so it passes. R15 passes (M5416 in group 1, M47816 in group 1, 64484 not checked). R18 (2 levels a side), R12 and R19 also pass.

### Case 7 (R15-01)

Diagnoses: A I10

| Line | Date | Code | Units | Modifiers | Pointers |
|---|---|---|---|---|---|
| 1 | 2026-10-06 | 93350 | 1 | - | A |

Facts: MUE 93350: 1; R15 for 93350 (A56625): group 4; 93350 -> A56625: I10 in groups [2, 3].

Claim outcome (PASS / DENY / REJECT): DENY

| Line | Outcome (PASS / DENY) | Reason codes in order | Flags |
|---|---|---|---|
| 1 | DENY | DN_DX_NOT_SUPPORTED | — |

Why: R15 fails because 93350 needs group 4 and I10 is only in groups 2 and 3. The only line is denied, so the claim is DENY.

### Case 8 (R15-02)

Diagnoses: A I2510

| Line | Date | Code | Units | Modifiers | Pointers |
|---|---|---|---|---|---|
| 1 | 2026-10-06 | 93350 | 1 | - | A |

Facts: MUE 93350: 1; R15 for 93350 (A56625): group 4; 93350 -> A56625: I2510 in groups [2, 3, 4].

Claim outcome (PASS / DENY / REJECT): PASS

| Line | Outcome (PASS / DENY) | Reason codes in order | Flags |
|---|---|---|---|
| 1 | PASS | — | — |

Why: R15 passes because I2510 is in group 4. R12 is within MUE, and no other rule covers 93350.

### Case 9 (R15-03)

Diagnoses: A H2513

| Line | Date | Code | Units | Modifiers | Pointers |
|---|---|---|---|---|---|
| 1 | 2026-10-06 | 66982 | 1 | - | A |

Facts: MUE 66982: 1; R15 for 66982 (A56544): group 1; 66982 -> A56544: H2513 in groups [1].

Claim outcome (PASS / DENY / REJECT): PASS

| Line | Outcome (PASS / DENY) | Reason codes in order | Flags |
|---|---|---|---|
| 1 | PASS | — | — |

Why: R15 passes because H2513 is in group 1, the only group for 66982. R12 is within MUE.

### Case 10 (R15-04)

Diagnoses: A S36500A, B S31609A

| Line | Date | Code | Units | Modifiers | Pointers |
|---|---|---|---|---|---|
| 1 | 2026-10-06 | 45385 | 1 | - | AB |

Facts: MUE 45385: 1; R15 for 45385 (A56456): group 1 or group 2 + group 3; 45385 -> A56456: S36500A in groups [3]; 45385 -> A56456: S31609A in groups [2].

Claim outcome (PASS / DENY / REJECT): DENY

| Line | Outcome (PASS / DENY) | Reason codes in order | Flags |
|---|---|---|---|
| 1 | DENY | DN_DX_NOT_SUPPORTED | — |

Why: R15 fails. Neither diagnosis is in group 1, and the line's first diagnosis (A, S36500A) is in group 3 = 2B, not 2A. The only line is denied, so the claim is DENY.

### Case 11 (R15-05)

Diagnoses: A S31609A, B S36500A

| Line | Date | Code | Units | Modifiers | Pointers |
|---|---|---|---|---|---|
| 1 | 2026-10-06 | 45385 | 1 | - | AB |

Facts: MUE 45385: 1; R15 for 45385 (A56456): group 1 or group 2 + group 3; 45385 -> A56456: S31609A in groups [2]; 45385 -> A56456: S36500A in groups [3].

Claim outcome (PASS / DENY / REJECT): PASS

| Line | Outcome (PASS / DENY) | Reason codes in order | Flags |
|---|---|---|---|
| 1 | PASS | — | — |

Why: R15 passes. The first diagnosis, S31609A, is in group 2 = 2A, and S36500A, among the others, is in group 3 = 2B. R12 is within MUE.

### Case 12 (R15-06)

Diagnoses: A E1151

| Line | Date | Code | Units | Modifiers | Pointers |
|---|---|---|---|---|---|
| 1 | 2026-10-06 | 11720 | 1 | Q8 | A |

Facts: MUE 11720: 1; R15 for 11720 (A57188): group 1 or group 2 or group 3 or group 4; 11720 -> A57188: E1151 in groups [2].

Claim outcome (PASS / DENY / REJECT): PASS

| Line | Outcome (PASS / DENY) | Reason codes in order | Flags |
|---|---|---|---|
| 1 | PASS | — | — |

Why: R15 passes because E1151 is in group 2 and modifier Q8 is billed. R12 is within MUE.

### Case 13 (R15-07)

Diagnoses: A E1151

| Line | Date | Code | Units | Modifiers | Pointers |
|---|---|---|---|---|---|
| 1 | 2026-10-06 | 11720 | 1 | - | A |

Facts: MUE 11720: 1; R15 for 11720 (A57188): group 1 or group 2 or group 3 or group 4; 11720 -> A57188: E1151 in groups [2].

Claim outcome (PASS / DENY / REJECT): DENY

| Line | Outcome (PASS / DENY) | Reason codes in order | Flags |
|---|---|---|---|
| 1 | DENY | DN_DX_NOT_SUPPORTED | — |

Why: R15 fails because E1151 is only in group 2 and no Q7, Q8 or Q9 is billed. The only line is denied, so the claim is DENY.

### Case 14 (R16-01)

Diagnoses: A G4750

| Line | Date | Code | Units | Modifiers | Pointers |
|---|---|---|---|---|---|
| 1 | 2026-10-06 | 95806 | 1 | - | A |

Facts: MUE 95806: 1; R15 for 95806 (A56923): group 2; 95806 -> A56923: G4750 in groups [2].

Claim outcome (PASS / DENY / REJECT): DENY

| Line | Outcome (PASS / DENY) | Reason codes in order | Flags |
|---|---|---|---|
| 1 | DENY | DN_HOME_TEST_PARASOMNIA | — |

Why: R16 fails because 95806 is a home sleep test and the line's own diagnosis G4750 (G47.50) is a parasomnia code. R15 passes (G4750 is in group 2). The only line is denied, so the claim is DENY.

### Case 15 (R16-02)

Diagnoses: A G4750

| Line | Date | Code | Units | Modifiers | Pointers |
|---|---|---|---|---|---|
| 1 | 2026-10-06 | 95810 | 1 | - | A |

Facts: MUE 95810: 1; R15 for 95810 (A56923): group 2; 95810 -> A56923: G4750 in groups [2].

Claim outcome (PASS / DENY / REJECT): PASS

| Line | Outcome (PASS / DENY) | Reason codes in order | Flags |
|---|---|---|---|
| 1 | PASS | — | — |

Why: R16 does not apply because 95810 is not on the home sleep test list. R15 passes (G4750 is in group 2), and R12 is within MUE.

### Case 16 (R17-01)

Diagnoses: A G5601

| Line | Date | Code | Units | Modifiers | Pointers |
|---|---|---|---|---|---|
| 1 | 2026-10-06 | 95910 | 1 | - | A |

Facts: MUE 95910: 1; R15 for 95910 (A57478): group 1; 95910 -> A57478: G5601 in groups [1].

Claim outcome (PASS / DENY / REJECT): PASS

| Line | Outcome (PASS / DENY) | Reason codes in order | Flags |
|---|---|---|---|
| 1 | PASS | — | NCS_WITHOUT_EMG |

Why: R17 flags the line because 95910 is a nerve conduction code and the claim has no needle EMG line. A flag never denies. R15 passes (G5601 is in group 1).

### Case 17 (R17-02)

Diagnoses: A G5601

| Line | Date | Code | Units | Modifiers | Pointers |
|---|---|---|---|---|---|
| 1 | 2026-10-06 | 95910 | 1 | - | A |
| 2 | 2026-10-08 | 95886 | 1 | - | A |

Facts: MUE 95886: 4; MUE 95910: 1; R15 for 95886 (A57478): group 1; 95886 -> A57478: G5601 in groups [1]; R15 for 95910 (A57478): group 1; 95910 -> A57478: G5601 in groups [1].

Claim outcome (PASS / DENY / REJECT): PASS

| Line | Outcome (PASS / DENY) | Reason codes in order | Flags |
|---|---|---|---|
| 1 | PASS | — | — |
| 2 | PASS | — | — |

Why: R17 passes because 95886 is a needle EMG line on the claim. The rule says "anywhere on the claim", so the different date does not matter. R15 passes both lines (G5601 is in group 1), and R12 is within MUE.

### Case 18 (R18-01)

Diagnoses: A M5416

| Line | Date | Code | Units | Modifiers | Pointers |
|---|---|---|---|---|---|
| 1 | 2026-10-06 | 62323 | 1 | 50 | A |

Facts: MUE 62323: 1; R15 for 62323 (A56651): group 1; 62323 -> A56651: M5416 in groups [1].

Claim outcome (PASS / DENY / REJECT): DENY

| Line | Outcome (PASS / DENY) | Reason codes in order | Flags |
|---|---|---|---|
| 1 | DENY | DN_ESI_LEVELS | — |

Why: R18 fails because 62323 (interlaminar/caudal ESI) is billed with modifier 50. R15 passes (M5416 is in group 1), and R14 finds no other block. The only line is denied, so the claim is DENY.

### Case 19 (R18-02)

Diagnoses: A M5416

| Line | Date | Code | Units | Modifiers | Pointers |
|---|---|---|---|---|---|
| 1 | 2026-10-06 | 62323 | 1 | - | A |

Facts: MUE 62323: 1; R15 for 62323 (A56651): group 1; 62323 -> A56651: M5416 in groups [1].

Claim outcome (PASS / DENY / REJECT): PASS

| Line | Outcome (PASS / DENY) | Reason codes in order | Flags |
|---|---|---|---|
| 1 | PASS | — | — |

Why: R18 passes because 62323 is billed without modifier 50. R15 passes (M5416 is in group 1), R14 finds no other block, and R12 is within MUE.

### Case 20 (R18-03)

Diagnoses: A M5416

| Line | Date | Code | Units | Modifiers | Pointers |
|---|---|---|---|---|---|
| 1 | 2026-10-06 | 64483 | 1 | RT | A |
| 2 | 2026-10-06 | 64484 | 2 | RT | A |

Facts: MUE 64483: 1; MUE 64484: 4; R15 for 64483 (A56651): group 1; 64483 -> A56651: M5416 in groups [1]; 64484: no billing article (R15 does not check it).

Claim outcome (PASS / DENY / REJECT): PASS

| Line | Outcome (PASS / DENY) | Reason codes in order | Flags |
|---|---|---|---|
| 1 | PASS | — | — |
| 2 | DENY | DN_ESI_LEVELS | — |

Why: R18 fails line 2. On the RT side, 64483 (1 level) plus 64484 (2 units, read as 2 levels) makes 3 levels, above 2, so the RT add-on line is denied. R12 (2 ≤ 4), R14 (an add-on is not a block) and R15 (M5416 in group 1) pass. The rule text says "levels", not units; if each line counted as 1 level, both lines would pass.

### Case 21 (R18-04)

Diagnoses: A M5416

| Line | Date | Code | Units | Modifiers | Pointers |
|---|---|---|---|---|---|
| 1 | 2026-10-06 | 64483 | 1 | 50 | A |
| 2 | 2026-10-06 | 64484 | 1 | RT | A |
| 3 | 2026-10-06 | 64484 | 1 | LT | A |

Facts: MUE 64483: 1; MUE 64484: 4; R15 for 64483 (A56651): group 1; 64483 -> A56651: M5416 in groups [1]; 64484: no billing article (R15 does not check it).

Claim outcome (PASS / DENY / REJECT): PASS

| Line | Outcome (PASS / DENY) | Reason codes in order | Flags |
|---|---|---|---|
| 1 | PASS | — | — |
| 2 | PASS | — | — |
| 3 | PASS | — | — |

Why: R18 passes. 64483-50 counts on both sides and each 64484 on its own side, giving 2 levels RT and 2 LT. R12 passes (64484: 1 + 1 = 2 ≤ 4; 64483: 1 ≤ 1). R15 passes 64483 (M5416 in group 1), and R14 finds no other block.

### Case 22 (R18-05)

Diagnoses: A M5416

| Line | Date | Code | Units | Modifiers | Pointers |
|---|---|---|---|---|---|
| 1 | 2026-10-06 | 64483 | 1 | 50 | A |
| 2 | 2026-10-06 | 64484 | 1 | 50 | A |

Facts: MUE 64483: 1; MUE 64484: 4; R15 for 64483 (A56651): group 1; 64483 -> A56651: M5416 in groups [1]; 64484: no billing article (R15 does not check it).

Claim outcome (PASS / DENY / REJECT): PASS

| Line | Outcome (PASS / DENY) | Reason codes in order | Flags |
|---|---|---|---|
| 1 | PASS | — | — |
| 2 | PASS | — | — |

Why: R18 passes. Both lines carry modifier 50, giving 2 levels on each side, and the modifier-50 denial applies only to 62321/62323. R15 passes 64483 (M5416 in group 1), and R12 is within MUE.

### Case 23 (R19-01)

Diagnoses: A M47816

| Line | Date | Code | Units | Modifiers | Pointers |
|---|---|---|---|---|---|
| 1 | 2026-10-06 | 64493 | 1 | - | A |
| 2 | 2026-10-06 | 64494 | 1 | - | A |
| 3 | 2026-10-06 | 64495 | 1 | - | A |

Facts: MUE 64493: 1; MUE 64494: 1; MUE 64495: 1; R15 for 64493 (A57787): group 1; 64493 -> A57787: M47816 in groups [1]; 64494: no billing article (R15 does not check it); 64495: no billing article (R15 does not check it).

Claim outcome (PASS / DENY / REJECT): PASS

| Line | Outcome (PASS / DENY) | Reason codes in order | Flags |
|---|---|---|---|
| 1 | PASS | — | — |
| 2 | PASS | — | — |
| 3 | DENY | DN_FACET_LEVELS | — |

Why: R19 fails line 3 because 64495 is a third-level facet code. All three lines are lumbar, so there is no FACET_TWO_REGIONS flag. R15 passes 64493 (M47816 in group 1), R14 does not apply (no ESI line), and R12 is within MUE.

### Case 24 (R19-02)

Diagnoses: A M47816

| Line | Date | Code | Units | Modifiers | Pointers |
|---|---|---|---|---|---|
| 1 | 2026-10-06 | 64493 | 1 | - | A |
| 2 | 2026-10-06 | 64494 | 1 | - | A |

Facts: MUE 64493: 1; MUE 64494: 1; R15 for 64493 (A57787): group 1; 64493 -> A57787: M47816 in groups [1]; 64494: no billing article (R15 does not check it).

Claim outcome (PASS / DENY / REJECT): PASS

| Line | Outcome (PASS / DENY) | Reason codes in order | Flags |
|---|---|---|---|
| 1 | PASS | — | — |
| 2 | PASS | — | — |

Why: R19 passes because there is no third-level code and only one region. R15 passes 64493 (M47816 in group 1), and R12 is within MUE.

### Case 25 (R19-03)

Diagnoses: A M47812, B M47816

| Line | Date | Code | Units | Modifiers | Pointers |
|---|---|---|---|---|---|
| 1 | 2026-10-06 | 64490 | 1 | - | A |
| 2 | 2026-10-06 | 64493 | 1 | - | B |

Facts: MUE 64490: 1; MUE 64493: 1; R15 for 64490 (A57787): group 1; 64490 -> A57787: M47812 in groups [1]; 64490 -> A57787: M47816 in groups [1]; R15 for 64493 (A57787): group 1; 64493 -> A57787: M47812 in groups [1]; 64493 -> A57787: M47816 in groups [1].

Claim outcome (PASS / DENY / REJECT): PASS

| Line | Outcome (PASS / DENY) | Reason codes in order | Flags |
|---|---|---|---|
| 1 | PASS | — | FACET_TWO_REGIONS |
| 2 | PASS | — | FACET_TWO_REGIONS |

Why: R19 flags both lines because 64490 (cervical/thoracic) and 64493 (lumbar) are billed on the same date; a flag never denies. R15 passes (M47812 and M47816 are in group 1), and R14 does not apply (no ESI line).

### Case 26 (R20-01)

Diagnoses: A G3184

| Line | Date | Code | Units | Modifiers | Pointers |
|---|---|---|---|---|---|
| 1 | 2026-10-06 | 96130 | 1 | - | A |
| 2 | 2026-10-06 | 96131 | 7 | - | A |
| 3 | 2026-10-06 | 96136 | 1 | - | A |

Facts: MUE 96130: 1; MUE 96131: 7; MUE 96136: 1; R15 for 96130 (A57780): group 1; 96130 -> A57780: G3184 in groups [1]; R15 for 96131 (A57780): group 1; 96131 -> A57780: G3184 in groups [1]; R15 for 96136 (A57780): group 1; 96136 -> A57780: G3184 in groups [1].

Claim outcome (PASS / DENY / REJECT): PASS

| Line | Outcome (PASS / DENY) | Reason codes in order | Flags |
|---|---|---|---|
| 1 | PASS | — | EXTENDED_TESTING |
| 2 | PASS | — | EXTENDED_TESTING |
| 3 | PASS | — | EXTENDED_TESTING |

Why: R20 flags all three lines: 60 + 7 × 60 + 30 = 510 testing minutes, above 480. R15 passes all lines (G3184 is in group 1), and R12 is within MUE (96131: 7 ≤ 7).

### Case 27 (R20-02)

Diagnoses: A G3184

| Line | Date | Code | Units | Modifiers | Pointers |
|---|---|---|---|---|---|
| 1 | 2026-10-06 | 96130 | 1 | - | A |
| 2 | 2026-10-06 | 96131 | 7 | - | A |

Facts: MUE 96130: 1; MUE 96131: 7; R15 for 96130 (A57780): group 1; 96130 -> A57780: G3184 in groups [1]; R15 for 96131 (A57780): group 1; 96131 -> A57780: G3184 in groups [1].

Claim outcome (PASS / DENY / REJECT): PASS

| Line | Outcome (PASS / DENY) | Reason codes in order | Flags |
|---|---|---|---|
| 1 | PASS | — | — |
| 2 | PASS | — | — |

Why: R20 passes: 60 + 7 × 60 = 480 minutes, which is not above 480. R15 passes both lines (G3184 is in group 1), and R12 is within MUE.

### Case 28 (X-03)

Diagnoses: A M5416

| Line | Date | Code | Units | Modifiers | Pointers |
|---|---|---|---|---|---|
| 1 | 2026-10-06 | 62323 | 1 | - | A |
| 2 | 2026-10-06 | 64483 | 1 | - | A |

Facts: NCCI 62323/64483: modifier indicator 1; MUE 62323: 1; MUE 64483: 1; R15 for 62323 (A56651): group 1; 62323 -> A56651: M5416 in groups [1]; R15 for 64483 (A56651): group 1; 64483 -> A56651: M5416 in groups [1].

Claim outcome (PASS / DENY / REJECT): DENY

| Line | Outcome (PASS / DENY) | Reason codes in order | Flags |
|---|---|---|---|
| 1 | DENY | DN_MULTIPLE_BLOCKS | — |
| 2 | DENY | DN_NCCI_BUNDLED, DN_MULTIPLE_BLOCKS | — |

Why: R11 fails line 2. The 62323/64483 edit (read as column 1/column 2) has indicator 1, and neither line has XE, XP, XS or XU. R14 fails both lines because two different ESI codes are billed on one date. R15 and R18 pass. Every line is denied, so the claim is DENY.

### Case 29 (X-04)

Diagnoses: A R519, B M5412

| Line | Date | Code | Units | Modifiers | Pointers |
|---|---|---|---|---|---|
| 1 | 2026-10-06 | 70450 | 1 | - | A |
| 2 | 2026-10-06 | 72141 | 1 | - | B |

Facts: MUE 70450: 3; MUE 72141: 1; R15 for 70450 (A57204): group 1; 70450 -> A57204: R519 in groups [1]; 70450 -> A57204: M5412 in groups [1]; R15 for 72141 (A57204): group 1; 72141 -> A57204: R519 in groups [1]; 72141 -> A57204: M5412 in groups [1].

Claim outcome (PASS / DENY / REJECT): PASS

| Line | Outcome (PASS / DENY) | Reason codes in order | Flags |
|---|---|---|---|
| 1 | PASS | — | — |
| 2 | PASS | — | — |

Why: R15 passes both lines (R519 is in group 1 for 70450, M5412 in group 1 for 72141). No NCCI edit is given, R12 is within MUE, and R14 and R16 to R20 do not cover these codes.

### Case 30 (X-05)

Diagnoses: A I83811

| Line | Date | Code | Units | Modifiers | Pointers |
|---|---|---|---|---|---|
| 1 | 2026-10-06 | 36478 | 1 | RT | A |
| 2 | 2026-10-06 | 37765 | 1 | RT | A |

Facts: MUE 36478: 1; MUE 37765: 1; R15 for 36478 (A57706): group 1; 36478 -> A57706: I83811 in groups [1]; R15 for 37765 (A57706): group 1; 37765 -> A57706: I83811 in groups [1].

Claim outcome (PASS / DENY / REJECT): PASS

| Line | Outcome (PASS / DENY) | Reason codes in order | Flags |
|---|---|---|---|
| 1 | PASS | — | — |
| 2 | PASS | — | — |

Why: R15 passes both lines (I83811 is in group 1 for 36478 and for 37765). No NCCI edit is given, R12 is within MUE, and R14 and R16 to R20 do not cover these codes.

### Case 31 (H5-08)

Read with confidence: diagnoses.0 0.60.

Diagnoses: A I10

| Line | Date | Code | Units | Modifiers | Pointers |
|---|---|---|---|---|---|
| 1 | 2026-10-06 | 93350 | 1 | - | A |

Facts: MUE 93350: 1; R15 for 93350 (A56625): group 4; 93350 -> A56625: I10 in groups [2, 3].

Claim outcome (PASS / DENY / REJECT): REJECT (RJ_LOW_CONFIDENCE_FIELD)

| Line | Outcome (PASS / DENY) | Reason codes in order | Flags |
|---|---|---|---|
| 1 | — (no line outcome: claim REJECT) | — | — |

Why: R15 fails as in Case 7 (I10 is not in group 4). R15 reads the pointed diagnosis A = diagnoses.0, which was read at 0.60, below 0.85, so H5 turns the failure into REJECT RJ_LOW_CONFIDENCE_FIELD with no line outcomes.

## End-to-end cases

For each: the rules result, then the line decisions (source RULE for a rule denial, MODEL for the model's), the claim decision (any PEND -> PEND; all DENY -> DENY; all APPROVE -> APPROVE; otherwise PARTIAL) and the review tier (FULL when the model output is invalid, any model line is DENY, or the complexity is HIGH; STANDARD for a PEND, MEDIUM complexity, a high-dollar or low-confidence claim; QUICK otherwise). Complexity is HIGH when the line decisions differ, rule-denied lines counting as DENY. A rule-denied claim never reaches the model or review.

### E2E-17

Diagnoses: A F419

| Line | Code | Pointers | The model's answer if the line reaches it |
|---|---|---|---|
| 1 | 15822 | A | no model answer for this line |

Facts: MUE 15822: 1; R15 for 15822 (A56439): group 1 or group 2; 15822 -> A56439: F419 in groups none.

Rules claim outcome: DENY | Status after processing: UNDECIDABLE: the sheet names no statuses (by its text, the claim is rule-denied and closes without the model or review)

| Line | Decision | Source | Reason codes |
|---|---|---|---|
| 1 | DENY | RULE | DN_DX_NOT_SUPPORTED |

Claim decision: DENY | Review tier: N/A (a rule-denied claim never reaches review) | Final status after ACCEPT (or N/A): N/A

Why: R15 fails because 15822 needs group 1 or group 2 and F419 is in neither. The only line is denied, so the claim is DENY and never reaches the model or review. Units are not shown and are read as 1, within MUE 1.

### E2E-23

Diagnoses: A I10, B I4891

| Line | Code | Pointers | The model's answer if the line reaches it |
|---|---|---|---|
| 1 | 93350 | A | no model answer for this line |
| 2 | 93241 | B | APPROVE (no reason) |

Model complexity: HIGH.

Facts: MUE 93241: 1; MUE 93350: 1; R15 for 93241 (A57476): group 3; 93241 -> A57476: I10 in groups none; 93241 -> A57476: I4891 in groups [1, 2, 3]; R15 for 93350 (A56625): group 4; 93350 -> A56625: I10 in groups [2, 3]; 93350 -> A56625: I4891 in groups [2, 3, 4, 5].

Rules claim outcome: PASS | Status after processing: UNDECIDABLE: the sheet names no statuses (by its text, the claim waits for FULL review)

| Line | Decision | Source | Reason codes |
|---|---|---|---|
| 1 | DENY | RULE | DN_DX_NOT_SUPPORTED |
| 2 | APPROVE | MODEL | — |

Claim decision: PARTIAL | Review tier: FULL | Final status after ACCEPT (or N/A): UNDECIDABLE: the sheet names no statuses (the accepted decision is PARTIAL)

Why: R15 fails line 1 (I10 is not in group 4 for 93350) and passes line 2 (I4891 is in group 3 for 93241). Line 2 passes, so the claim goes to the model, which approves line 2. DENY plus APPROVE gives PARTIAL. The decisions differ, so complexity is HIGH, as given, and the tier is FULL. Units are read as 1.

### E2E-32

Diagnoses: A I2510, B I4891

| Line | Code | Pointers | The model's answer if the line reaches it |
|---|---|---|---|
| 1 | 93350 | A | DENY (DN_NOT_MEDICALLY_NECESSARY) |
| 2 | 93241 | B | APPROVE (no reason) |

Model complexity: HIGH.

E2E-32 is a new case. Its amounts and accumulators equal E2E-23's already verified values (same plan, member, fees and approved line); only the rule outcome and the decisions are asked here.

Facts: MUE 93241: 1; MUE 93350: 1; R15 for 93241 (A57476): group 3; 93241 -> A57476: I2510 in groups none; 93241 -> A57476: I4891 in groups [1, 2, 3]; R15 for 93350 (A56625): group 4; 93350 -> A56625: I2510 in groups [2, 3, 4]; 93350 -> A56625: I4891 in groups [2, 3, 4, 5].

Rules claim outcome: PASS | Status after processing: UNDECIDABLE: the sheet names no statuses (by its text, the claim waits for FULL review)

| Line | Decision | Source | Reason codes |
|---|---|---|---|
| 1 | DENY | MODEL | DN_NOT_MEDICALLY_NECESSARY |
| 2 | APPROVE | MODEL | — |

Claim decision: PARTIAL | Review tier: FULL | Final status after ACCEPT (or N/A): UNDECIDABLE: the sheet names no statuses (the accepted decision is PARTIAL)

Why: R15 passes both lines (I2510 is in group 4 for 93350, I4891 in group 3 for 93241), so both go to the model, which denies line 1 and approves line 2. That gives PARTIAL. The tier is FULL because a model line is DENY, and complexity is also HIGH. Units are read as 1.
