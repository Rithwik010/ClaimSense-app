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

Claim outcome (PASS / DENY / REJECT): ____

| Line | Outcome (PASS / DENY) | Reason codes in order | Flags |
|---|---|---|---|
| 1 |  |  |  |
| 2 |  |  |  |

### Case 2 (R14-02)

Diagnoses: A M5416, B M47816

| Line | Date | Code | Units | Modifiers | Pointers |
|---|---|---|---|---|---|
| 1 | 2026-10-06 | 64483 | 1 | - | A |
| 2 | 2026-10-13 | 64493 | 1 | - | B |

Facts: MUE 64483: 1; MUE 64493: 1; R15 for 64483 (A56651): group 1; 64483 -> A56651: M5416 in groups [1]; 64483 -> A56651: M47816 in groups none; R15 for 64493 (A57787): group 1; 64493 -> A57787: M5416 in groups none; 64493 -> A57787: M47816 in groups [1].

Claim outcome (PASS / DENY / REJECT): ____

| Line | Outcome (PASS / DENY) | Reason codes in order | Flags |
|---|---|---|---|
| 1 |  |  |  |
| 2 |  |  |  |

### Case 3 (R14-03)

Diagnoses: A M5416, B M7138

| Line | Date | Code | Units | Modifiers | Pointers |
|---|---|---|---|---|---|
| 1 | 2026-10-06 | 64483 | 1 | - | A |
| 2 | 2026-10-06 | 64493 | 1 | - | B |

Facts: MUE 64483: 1; MUE 64493: 1; R15 for 64483 (A56651): group 1; 64483 -> A56651: M5416 in groups [1]; 64483 -> A56651: M7138 in groups none; R15 for 64493 (A57787): group 1; 64493 -> A57787: M5416 in groups none; 64493 -> A57787: M7138 in groups [1].

Claim outcome (PASS / DENY / REJECT): ____

| Line | Outcome (PASS / DENY) | Reason codes in order | Flags |
|---|---|---|---|
| 1 |  |  |  |
| 2 |  |  |  |

### Case 4 (R14-04)

Diagnoses: A M5416

| Line | Date | Code | Units | Modifiers | Pointers |
|---|---|---|---|---|---|
| 1 | 2026-10-06 | 64483 | 1 | - | A |
| 2 | 2026-10-06 | 64484 | 1 | - | A |

Facts: MUE 64483: 1; MUE 64484: 4; R15 for 64483 (A56651): group 1; 64483 -> A56651: M5416 in groups [1]; 64484: no billing article (R15 does not check it).

Claim outcome (PASS / DENY / REJECT): ____

| Line | Outcome (PASS / DENY) | Reason codes in order | Flags |
|---|---|---|---|
| 1 |  |  |  |
| 2 |  |  |  |

### Case 5 (R14-05)

Diagnoses: A M5416

| Line | Date | Code | Units | Modifiers | Pointers |
|---|---|---|---|---|---|
| 1 | 2026-10-06 | 64483 | 1 | RT | A |
| 2 | 2026-10-06 | 64483 | 1 | LT | A |

Facts: MUE 64483: 1; R15 for 64483 (A56651): group 1; 64483 -> A56651: M5416 in groups [1].

Claim outcome (PASS / DENY / REJECT): ____

| Line | Outcome (PASS / DENY) | Reason codes in order | Flags |
|---|---|---|---|
| 1 |  |  |  |
| 2 |  |  |  |

### Case 6 (R14-06)

Diagnoses: A M5416, B M47816

| Line | Date | Code | Units | Modifiers | Pointers |
|---|---|---|---|---|---|
| 1 | 2026-10-06 | 64483 | 1 | - | A |
| 2 | 2026-10-06 | 64484 | 1 | - | A |
| 3 | 2026-10-06 | 64493 | 1 | - | B |

Facts: MUE 64483: 1; MUE 64484: 4; MUE 64493: 1; R15 for 64483 (A56651): group 1; 64483 -> A56651: M5416 in groups [1]; 64483 -> A56651: M47816 in groups none; 64484: no billing article (R15 does not check it); R15 for 64493 (A57787): group 1; 64493 -> A57787: M5416 in groups none; 64493 -> A57787: M47816 in groups [1].

Claim outcome (PASS / DENY / REJECT): ____

| Line | Outcome (PASS / DENY) | Reason codes in order | Flags |
|---|---|---|---|
| 1 |  |  |  |
| 2 |  |  |  |
| 3 |  |  |  |

### Case 7 (R15-01)

Diagnoses: A I10

| Line | Date | Code | Units | Modifiers | Pointers |
|---|---|---|---|---|---|
| 1 | 2026-10-06 | 93350 | 1 | - | A |

Facts: MUE 93350: 1; R15 for 93350 (A56625): group 4; 93350 -> A56625: I10 in groups [2, 3].

Claim outcome (PASS / DENY / REJECT): ____

| Line | Outcome (PASS / DENY) | Reason codes in order | Flags |
|---|---|---|---|
| 1 |  |  |  |

### Case 8 (R15-02)

Diagnoses: A I2510

| Line | Date | Code | Units | Modifiers | Pointers |
|---|---|---|---|---|---|
| 1 | 2026-10-06 | 93350 | 1 | - | A |

Facts: MUE 93350: 1; R15 for 93350 (A56625): group 4; 93350 -> A56625: I2510 in groups [2, 3, 4].

Claim outcome (PASS / DENY / REJECT): ____

| Line | Outcome (PASS / DENY) | Reason codes in order | Flags |
|---|---|---|---|
| 1 |  |  |  |

### Case 9 (R15-03)

Diagnoses: A H2513

| Line | Date | Code | Units | Modifiers | Pointers |
|---|---|---|---|---|---|
| 1 | 2026-10-06 | 66982 | 1 | - | A |

Facts: MUE 66982: 1; R15 for 66982 (A56544): group 1; 66982 -> A56544: H2513 in groups [1].

Claim outcome (PASS / DENY / REJECT): ____

| Line | Outcome (PASS / DENY) | Reason codes in order | Flags |
|---|---|---|---|
| 1 |  |  |  |

### Case 10 (R15-04)

Diagnoses: A S36500A, B S31609A

| Line | Date | Code | Units | Modifiers | Pointers |
|---|---|---|---|---|---|
| 1 | 2026-10-06 | 45385 | 1 | - | AB |

Facts: MUE 45385: 1; R15 for 45385 (A56456): group 1 or group 2 + group 3; 45385 -> A56456: S36500A in groups [3]; 45385 -> A56456: S31609A in groups [2].

Claim outcome (PASS / DENY / REJECT): ____

| Line | Outcome (PASS / DENY) | Reason codes in order | Flags |
|---|---|---|---|
| 1 |  |  |  |

### Case 11 (R15-05)

Diagnoses: A S31609A, B S36500A

| Line | Date | Code | Units | Modifiers | Pointers |
|---|---|---|---|---|---|
| 1 | 2026-10-06 | 45385 | 1 | - | AB |

Facts: MUE 45385: 1; R15 for 45385 (A56456): group 1 or group 2 + group 3; 45385 -> A56456: S31609A in groups [2]; 45385 -> A56456: S36500A in groups [3].

Claim outcome (PASS / DENY / REJECT): ____

| Line | Outcome (PASS / DENY) | Reason codes in order | Flags |
|---|---|---|---|
| 1 |  |  |  |

### Case 12 (R15-06)

Diagnoses: A E1151

| Line | Date | Code | Units | Modifiers | Pointers |
|---|---|---|---|---|---|
| 1 | 2026-10-06 | 11720 | 1 | Q8 | A |

Facts: MUE 11720: 1; R15 for 11720 (A57188): group 1 or group 2 or group 3 or group 4; 11720 -> A57188: E1151 in groups [2].

Claim outcome (PASS / DENY / REJECT): ____

| Line | Outcome (PASS / DENY) | Reason codes in order | Flags |
|---|---|---|---|
| 1 |  |  |  |

### Case 13 (R15-07)

Diagnoses: A E1151

| Line | Date | Code | Units | Modifiers | Pointers |
|---|---|---|---|---|---|
| 1 | 2026-10-06 | 11720 | 1 | - | A |

Facts: MUE 11720: 1; R15 for 11720 (A57188): group 1 or group 2 or group 3 or group 4; 11720 -> A57188: E1151 in groups [2].

Claim outcome (PASS / DENY / REJECT): ____

| Line | Outcome (PASS / DENY) | Reason codes in order | Flags |
|---|---|---|---|
| 1 |  |  |  |

### Case 14 (R16-01)

Diagnoses: A G4750

| Line | Date | Code | Units | Modifiers | Pointers |
|---|---|---|---|---|---|
| 1 | 2026-10-06 | 95806 | 1 | - | A |

Facts: MUE 95806: 1; R15 for 95806 (A56923): group 2; 95806 -> A56923: G4750 in groups [2].

Claim outcome (PASS / DENY / REJECT): ____

| Line | Outcome (PASS / DENY) | Reason codes in order | Flags |
|---|---|---|---|
| 1 |  |  |  |

### Case 15 (R16-02)

Diagnoses: A G4750

| Line | Date | Code | Units | Modifiers | Pointers |
|---|---|---|---|---|---|
| 1 | 2026-10-06 | 95810 | 1 | - | A |

Facts: MUE 95810: 1; R15 for 95810 (A56923): group 2; 95810 -> A56923: G4750 in groups [2].

Claim outcome (PASS / DENY / REJECT): ____

| Line | Outcome (PASS / DENY) | Reason codes in order | Flags |
|---|---|---|---|
| 1 |  |  |  |

### Case 16 (R17-01)

Diagnoses: A G5601

| Line | Date | Code | Units | Modifiers | Pointers |
|---|---|---|---|---|---|
| 1 | 2026-10-06 | 95910 | 1 | - | A |

Facts: MUE 95910: 1; R15 for 95910 (A57478): group 1; 95910 -> A57478: G5601 in groups [1].

Claim outcome (PASS / DENY / REJECT): ____

| Line | Outcome (PASS / DENY) | Reason codes in order | Flags |
|---|---|---|---|
| 1 |  |  |  |

### Case 17 (R17-02)

Diagnoses: A G5601

| Line | Date | Code | Units | Modifiers | Pointers |
|---|---|---|---|---|---|
| 1 | 2026-10-06 | 95910 | 1 | - | A |
| 2 | 2026-10-08 | 95886 | 1 | - | A |

Facts: MUE 95886: 4; MUE 95910: 1; R15 for 95886 (A57478): group 1; 95886 -> A57478: G5601 in groups [1]; R15 for 95910 (A57478): group 1; 95910 -> A57478: G5601 in groups [1].

Claim outcome (PASS / DENY / REJECT): ____

| Line | Outcome (PASS / DENY) | Reason codes in order | Flags |
|---|---|---|---|
| 1 |  |  |  |
| 2 |  |  |  |

### Case 18 (R18-01)

Diagnoses: A M5416

| Line | Date | Code | Units | Modifiers | Pointers |
|---|---|---|---|---|---|
| 1 | 2026-10-06 | 62323 | 1 | 50 | A |

Facts: MUE 62323: 1; R15 for 62323 (A56651): group 1; 62323 -> A56651: M5416 in groups [1].

Claim outcome (PASS / DENY / REJECT): ____

| Line | Outcome (PASS / DENY) | Reason codes in order | Flags |
|---|---|---|---|
| 1 |  |  |  |

### Case 19 (R18-02)

Diagnoses: A M5416

| Line | Date | Code | Units | Modifiers | Pointers |
|---|---|---|---|---|---|
| 1 | 2026-10-06 | 62323 | 1 | - | A |

Facts: MUE 62323: 1; R15 for 62323 (A56651): group 1; 62323 -> A56651: M5416 in groups [1].

Claim outcome (PASS / DENY / REJECT): ____

| Line | Outcome (PASS / DENY) | Reason codes in order | Flags |
|---|---|---|---|
| 1 |  |  |  |

### Case 20 (R18-03)

Diagnoses: A M5416

| Line | Date | Code | Units | Modifiers | Pointers |
|---|---|---|---|---|---|
| 1 | 2026-10-06 | 64483 | 1 | RT | A |
| 2 | 2026-10-06 | 64484 | 2 | RT | A |

Facts: MUE 64483: 1; MUE 64484: 4; R15 for 64483 (A56651): group 1; 64483 -> A56651: M5416 in groups [1]; 64484: no billing article (R15 does not check it).

Claim outcome (PASS / DENY / REJECT): ____

| Line | Outcome (PASS / DENY) | Reason codes in order | Flags |
|---|---|---|---|
| 1 |  |  |  |
| 2 |  |  |  |

### Case 21 (R18-04)

Diagnoses: A M5416

| Line | Date | Code | Units | Modifiers | Pointers |
|---|---|---|---|---|---|
| 1 | 2026-10-06 | 64483 | 1 | 50 | A |
| 2 | 2026-10-06 | 64484 | 1 | RT | A |
| 3 | 2026-10-06 | 64484 | 1 | LT | A |

Facts: MUE 64483: 1; MUE 64484: 4; R15 for 64483 (A56651): group 1; 64483 -> A56651: M5416 in groups [1]; 64484: no billing article (R15 does not check it).

Claim outcome (PASS / DENY / REJECT): ____

| Line | Outcome (PASS / DENY) | Reason codes in order | Flags |
|---|---|---|---|
| 1 |  |  |  |
| 2 |  |  |  |
| 3 |  |  |  |

### Case 22 (R18-05)

Diagnoses: A M5416

| Line | Date | Code | Units | Modifiers | Pointers |
|---|---|---|---|---|---|
| 1 | 2026-10-06 | 64483 | 1 | 50 | A |
| 2 | 2026-10-06 | 64484 | 1 | 50 | A |

Facts: MUE 64483: 1; MUE 64484: 4; R15 for 64483 (A56651): group 1; 64483 -> A56651: M5416 in groups [1]; 64484: no billing article (R15 does not check it).

Claim outcome (PASS / DENY / REJECT): ____

| Line | Outcome (PASS / DENY) | Reason codes in order | Flags |
|---|---|---|---|
| 1 |  |  |  |
| 2 |  |  |  |

### Case 23 (R19-01)

Diagnoses: A M47816

| Line | Date | Code | Units | Modifiers | Pointers |
|---|---|---|---|---|---|
| 1 | 2026-10-06 | 64493 | 1 | - | A |
| 2 | 2026-10-06 | 64494 | 1 | - | A |
| 3 | 2026-10-06 | 64495 | 1 | - | A |

Facts: MUE 64493: 1; MUE 64494: 1; MUE 64495: 1; R15 for 64493 (A57787): group 1; 64493 -> A57787: M47816 in groups [1]; 64494: no billing article (R15 does not check it); 64495: no billing article (R15 does not check it).

Claim outcome (PASS / DENY / REJECT): ____

| Line | Outcome (PASS / DENY) | Reason codes in order | Flags |
|---|---|---|---|
| 1 |  |  |  |
| 2 |  |  |  |
| 3 |  |  |  |

### Case 24 (R19-02)

Diagnoses: A M47816

| Line | Date | Code | Units | Modifiers | Pointers |
|---|---|---|---|---|---|
| 1 | 2026-10-06 | 64493 | 1 | - | A |
| 2 | 2026-10-06 | 64494 | 1 | - | A |

Facts: MUE 64493: 1; MUE 64494: 1; R15 for 64493 (A57787): group 1; 64493 -> A57787: M47816 in groups [1]; 64494: no billing article (R15 does not check it).

Claim outcome (PASS / DENY / REJECT): ____

| Line | Outcome (PASS / DENY) | Reason codes in order | Flags |
|---|---|---|---|
| 1 |  |  |  |
| 2 |  |  |  |

### Case 25 (R19-03)

Diagnoses: A M47812, B M47816

| Line | Date | Code | Units | Modifiers | Pointers |
|---|---|---|---|---|---|
| 1 | 2026-10-06 | 64490 | 1 | - | A |
| 2 | 2026-10-06 | 64493 | 1 | - | B |

Facts: MUE 64490: 1; MUE 64493: 1; R15 for 64490 (A57787): group 1; 64490 -> A57787: M47812 in groups [1]; 64490 -> A57787: M47816 in groups [1]; R15 for 64493 (A57787): group 1; 64493 -> A57787: M47812 in groups [1]; 64493 -> A57787: M47816 in groups [1].

Claim outcome (PASS / DENY / REJECT): ____

| Line | Outcome (PASS / DENY) | Reason codes in order | Flags |
|---|---|---|---|
| 1 |  |  |  |
| 2 |  |  |  |

### Case 26 (R20-01)

Diagnoses: A G3184

| Line | Date | Code | Units | Modifiers | Pointers |
|---|---|---|---|---|---|
| 1 | 2026-10-06 | 96130 | 1 | - | A |
| 2 | 2026-10-06 | 96131 | 7 | - | A |
| 3 | 2026-10-06 | 96136 | 1 | - | A |

Facts: MUE 96130: 1; MUE 96131: 7; MUE 96136: 1; R15 for 96130 (A57780): group 1; 96130 -> A57780: G3184 in groups [1]; R15 for 96131 (A57780): group 1; 96131 -> A57780: G3184 in groups [1]; R15 for 96136 (A57780): group 1; 96136 -> A57780: G3184 in groups [1].

Claim outcome (PASS / DENY / REJECT): ____

| Line | Outcome (PASS / DENY) | Reason codes in order | Flags |
|---|---|---|---|
| 1 |  |  |  |
| 2 |  |  |  |
| 3 |  |  |  |

### Case 27 (R20-02)

Diagnoses: A G3184

| Line | Date | Code | Units | Modifiers | Pointers |
|---|---|---|---|---|---|
| 1 | 2026-10-06 | 96130 | 1 | - | A |
| 2 | 2026-10-06 | 96131 | 7 | - | A |

Facts: MUE 96130: 1; MUE 96131: 7; R15 for 96130 (A57780): group 1; 96130 -> A57780: G3184 in groups [1]; R15 for 96131 (A57780): group 1; 96131 -> A57780: G3184 in groups [1].

Claim outcome (PASS / DENY / REJECT): ____

| Line | Outcome (PASS / DENY) | Reason codes in order | Flags |
|---|---|---|---|
| 1 |  |  |  |
| 2 |  |  |  |

### Case 28 (X-03)

Diagnoses: A M5416

| Line | Date | Code | Units | Modifiers | Pointers |
|---|---|---|---|---|---|
| 1 | 2026-10-06 | 62323 | 1 | - | A |
| 2 | 2026-10-06 | 64483 | 1 | - | A |

Facts: NCCI 62323/64483: modifier indicator 1; MUE 62323: 1; MUE 64483: 1; R15 for 62323 (A56651): group 1; 62323 -> A56651: M5416 in groups [1]; R15 for 64483 (A56651): group 1; 64483 -> A56651: M5416 in groups [1].

Claim outcome (PASS / DENY / REJECT): ____

| Line | Outcome (PASS / DENY) | Reason codes in order | Flags |
|---|---|---|---|
| 1 |  |  |  |
| 2 |  |  |  |

### Case 29 (X-04)

Diagnoses: A R519, B M5412

| Line | Date | Code | Units | Modifiers | Pointers |
|---|---|---|---|---|---|
| 1 | 2026-10-06 | 70450 | 1 | - | A |
| 2 | 2026-10-06 | 72141 | 1 | - | B |

Facts: MUE 70450: 3; MUE 72141: 1; R15 for 70450 (A57204): group 1; 70450 -> A57204: R519 in groups [1]; 70450 -> A57204: M5412 in groups [1]; R15 for 72141 (A57204): group 1; 72141 -> A57204: R519 in groups [1]; 72141 -> A57204: M5412 in groups [1].

Claim outcome (PASS / DENY / REJECT): ____

| Line | Outcome (PASS / DENY) | Reason codes in order | Flags |
|---|---|---|---|
| 1 |  |  |  |
| 2 |  |  |  |

### Case 30 (X-05)

Diagnoses: A I83811

| Line | Date | Code | Units | Modifiers | Pointers |
|---|---|---|---|---|---|
| 1 | 2026-10-06 | 36478 | 1 | RT | A |
| 2 | 2026-10-06 | 37765 | 1 | RT | A |

Facts: MUE 36478: 1; MUE 37765: 1; R15 for 36478 (A57706): group 1; 36478 -> A57706: I83811 in groups [1]; R15 for 37765 (A57706): group 1; 37765 -> A57706: I83811 in groups [1].

Claim outcome (PASS / DENY / REJECT): ____

| Line | Outcome (PASS / DENY) | Reason codes in order | Flags |
|---|---|---|---|
| 1 |  |  |  |
| 2 |  |  |  |

### Case 31 (H5-08)

Read with confidence: diagnoses.0 0.60.

Diagnoses: A I10

| Line | Date | Code | Units | Modifiers | Pointers |
|---|---|---|---|---|---|
| 1 | 2026-10-06 | 93350 | 1 | - | A |

Facts: MUE 93350: 1; R15 for 93350 (A56625): group 4; 93350 -> A56625: I10 in groups [2, 3].

Claim outcome (PASS / DENY / REJECT): ____

| Line | Outcome (PASS / DENY) | Reason codes in order | Flags |
|---|---|---|---|
| 1 |  |  |  |

## End-to-end cases

For each: the rules result, then the line decisions (source RULE for a rule denial, MODEL for the model's), the claim decision (any PEND -> PEND; all DENY -> DENY; all APPROVE -> APPROVE; otherwise PARTIAL) and the review tier (FULL when the model output is invalid, any model line is DENY, or the complexity is HIGH; STANDARD for a PEND, MEDIUM complexity, a high-dollar or low-confidence claim; QUICK otherwise). Complexity is HIGH when the line decisions differ, rule-denied lines counting as DENY. A rule-denied claim never reaches the model or review.

### E2E-17

Diagnoses: A F419

| Line | Code | Pointers | The model's answer if the line reaches it |
|---|---|---|---|
| 1 | 15822 | A | no model answer for this line |

Facts: MUE 15822: 1; R15 for 15822 (A56439): group 1 or group 2; 15822 -> A56439: F419 in groups none.

Rules claim outcome: ____ | Status after processing: ____

| Line | Decision | Source | Reason codes |
|---|---|---|---|
| 1 |  |  |  |

Claim decision: ____ | Review tier: ____ | Final status after ACCEPT (or N/A): ____

### E2E-23

Diagnoses: A I10, B I4891

| Line | Code | Pointers | The model's answer if the line reaches it |
|---|---|---|---|
| 1 | 93350 | A | no model answer for this line |
| 2 | 93241 | B | APPROVE (no reason) |

Model complexity: HIGH.

Facts: MUE 93241: 1; MUE 93350: 1; R15 for 93241 (A57476): group 3; 93241 -> A57476: I10 in groups none; 93241 -> A57476: I4891 in groups [1, 2, 3]; R15 for 93350 (A56625): group 4; 93350 -> A56625: I10 in groups [2, 3]; 93350 -> A56625: I4891 in groups [2, 3, 4, 5].

Rules claim outcome: ____ | Status after processing: ____

| Line | Decision | Source | Reason codes |
|---|---|---|---|
| 1 |  |  |  |
| 2 |  |  |  |

Claim decision: ____ | Review tier: ____ | Final status after ACCEPT (or N/A): ____

### E2E-32

Diagnoses: A I2510, B I4891

| Line | Code | Pointers | The model's answer if the line reaches it |
|---|---|---|---|
| 1 | 93350 | A | DENY (DN_NOT_MEDICALLY_NECESSARY) |
| 2 | 93241 | B | APPROVE (no reason) |

Model complexity: HIGH.

E2E-32 is a new case. Its amounts and accumulators equal E2E-23's already verified values (same plan, member, fees and approved line); only the rule outcome and the decisions are asked here.

Facts: MUE 93241: 1; MUE 93350: 1; R15 for 93241 (A57476): group 3; 93241 -> A57476: I2510 in groups none; 93241 -> A57476: I4891 in groups [1, 2, 3]; R15 for 93350 (A56625): group 4; 93350 -> A56625: I2510 in groups [2, 3, 4]; 93350 -> A56625: I4891 in groups [2, 3, 4, 5].

Rules claim outcome: ____ | Status after processing: ____

| Line | Decision | Source | Reason codes |
|---|---|---|---|
| 1 |  |  |  |
| 2 |  |  |  |

Claim decision: ____ | Review tier: ____ | Final status after ACCEPT (or N/A): ____
