# Rules v2 golden cases: independent check (Task G4)

The answers were worked out by a separate Claude Code session with repository access, told to use only the sheet, which reports it did not open new_golden/ or DECISIONS.md. Like G3, this is a Claude recomputation, not a blind human check, and not independent of the cases' author (also Claude). The sheet (G4_rules_v2_sheet.md) showed the inputs, the facts the rules read and the rule text with every team decision (D-RULE-2 to D-RULE-4, D-RULE-7); no titles, worked steps or expected values.

- Cases: 31 rules cases and 3 end-to-end cases (E2E-17, E2E-23, E2E-32); cells compared: 218; agree: 218; disagree: 0.
- 5 status cells were UNDECIDABLE because the sheet named no statuses (a sheet gap): the checker's descriptions, mapped through the status table of INSTRUCTIONS.md section 5, agree with the drafts and are counted as agreeing. Future G sheets include the status table.
- Case R14-05: the checker denies both lines by R12 (2 units of 64483 on one date, MUE 1) with no DN_MULTIPLE_BLOCKS, as the draft does (A-R4); the case stays, showing R14 adds nothing for the same code on two lines.
- Case R18-03: the checker read each 64484 unit as one level and noted the rule text said only "levels"; D-RULE-3 and INSTRUCTIONS.md section 8.3 now say each unit of an add-on level code is one level.

## Status cells mapped through section 5

| Case | Cell | Checker's description | Mapped | Draft |
|---|---|---|---|---|
| E2E-17 | status after processing | the sheet names no statuses (by its text, the claim is rule-denied and closes without the model or review) | DENIED_BY_RULE | DENIED_BY_RULE |
| E2E-23 | status after processing | the sheet names no statuses (by its text, the claim waits for FULL review) | AWAITING_REVIEW | AWAITING_REVIEW |
| E2E-23 | final status after ACCEPT | the sheet names no statuses (the accepted decision is PARTIAL) | FINAL_PARTIAL | FINAL_PARTIAL |
| E2E-32 | status after processing | the sheet names no statuses (by its text, the claim waits for FULL review) | AWAITING_REVIEW | AWAITING_REVIEW |
| E2E-32 | final status after ACCEPT | the sheet names no statuses (the accepted decision is PARTIAL) | FINAL_PARTIAL | FINAL_PARTIAL |

## Not compared

- E2E-17 claim decision: answer DENY; the draft has none (a rule-denied claim's decision record leaves claim_decision empty; the rules claim outcome above is compared instead)

## Disagreements

None: every compared cell agrees.

## Every compared cell

| Case | Cell | Answer | Draft | Agree |
|---|---|---|---|---|
| R14-01 | claim outcome | PASS | PASS | yes |
| R14-01 | line 1 outcome | DENY | DENY | yes |
| R14-01 | line 1 reasons | DN_MULTIPLE_BLOCKS | DN_MULTIPLE_BLOCKS | yes |
| R14-01 | line 1 flags | - | - | yes |
| R14-01 | line 2 outcome | PASS | PASS | yes |
| R14-01 | line 2 reasons | - | - | yes |
| R14-01 | line 2 flags | - | - | yes |
| R14-02 | claim outcome | PASS | PASS | yes |
| R14-02 | line 1 outcome | PASS | PASS | yes |
| R14-02 | line 1 reasons | - | - | yes |
| R14-02 | line 1 flags | - | - | yes |
| R14-02 | line 2 outcome | PASS | PASS | yes |
| R14-02 | line 2 reasons | - | - | yes |
| R14-02 | line 2 flags | - | - | yes |
| R14-03 | claim outcome | PASS | PASS | yes |
| R14-03 | line 1 outcome | PASS | PASS | yes |
| R14-03 | line 1 reasons | - | - | yes |
| R14-03 | line 1 flags | - | - | yes |
| R14-03 | line 2 outcome | PASS | PASS | yes |
| R14-03 | line 2 reasons | - | - | yes |
| R14-03 | line 2 flags | - | - | yes |
| R14-04 | claim outcome | PASS | PASS | yes |
| R14-04 | line 1 outcome | PASS | PASS | yes |
| R14-04 | line 1 reasons | - | - | yes |
| R14-04 | line 1 flags | - | - | yes |
| R14-04 | line 2 outcome | PASS | PASS | yes |
| R14-04 | line 2 reasons | - | - | yes |
| R14-04 | line 2 flags | - | - | yes |
| R14-05 | claim outcome | DENY | DENY | yes |
| R14-05 | line 1 outcome | DENY | DENY | yes |
| R14-05 | line 1 reasons | DN_MUE_EXCEEDED | DN_MUE_EXCEEDED | yes |
| R14-05 | line 1 flags | - | - | yes |
| R14-05 | line 2 outcome | DENY | DENY | yes |
| R14-05 | line 2 reasons | DN_MUE_EXCEEDED | DN_MUE_EXCEEDED | yes |
| R14-05 | line 2 flags | - | - | yes |
| R14-06 | claim outcome | PASS | PASS | yes |
| R14-06 | line 1 outcome | DENY | DENY | yes |
| R14-06 | line 1 reasons | DN_MULTIPLE_BLOCKS | DN_MULTIPLE_BLOCKS | yes |
| R14-06 | line 1 flags | - | - | yes |
| R14-06 | line 2 outcome | DENY | DENY | yes |
| R14-06 | line 2 reasons | DN_MULTIPLE_BLOCKS | DN_MULTIPLE_BLOCKS | yes |
| R14-06 | line 2 flags | - | - | yes |
| R14-06 | line 3 outcome | PASS | PASS | yes |
| R14-06 | line 3 reasons | - | - | yes |
| R14-06 | line 3 flags | - | - | yes |
| R15-01 | claim outcome | DENY | DENY | yes |
| R15-01 | line 1 outcome | DENY | DENY | yes |
| R15-01 | line 1 reasons | DN_DX_NOT_SUPPORTED | DN_DX_NOT_SUPPORTED | yes |
| R15-01 | line 1 flags | - | - | yes |
| R15-02 | claim outcome | PASS | PASS | yes |
| R15-02 | line 1 outcome | PASS | PASS | yes |
| R15-02 | line 1 reasons | - | - | yes |
| R15-02 | line 1 flags | - | - | yes |
| R15-03 | claim outcome | PASS | PASS | yes |
| R15-03 | line 1 outcome | PASS | PASS | yes |
| R15-03 | line 1 reasons | - | - | yes |
| R15-03 | line 1 flags | - | - | yes |
| R15-04 | claim outcome | DENY | DENY | yes |
| R15-04 | line 1 outcome | DENY | DENY | yes |
| R15-04 | line 1 reasons | DN_DX_NOT_SUPPORTED | DN_DX_NOT_SUPPORTED | yes |
| R15-04 | line 1 flags | - | - | yes |
| R15-05 | claim outcome | PASS | PASS | yes |
| R15-05 | line 1 outcome | PASS | PASS | yes |
| R15-05 | line 1 reasons | - | - | yes |
| R15-05 | line 1 flags | - | - | yes |
| R15-06 | claim outcome | PASS | PASS | yes |
| R15-06 | line 1 outcome | PASS | PASS | yes |
| R15-06 | line 1 reasons | - | - | yes |
| R15-06 | line 1 flags | - | - | yes |
| R15-07 | claim outcome | DENY | DENY | yes |
| R15-07 | line 1 outcome | DENY | DENY | yes |
| R15-07 | line 1 reasons | DN_DX_NOT_SUPPORTED | DN_DX_NOT_SUPPORTED | yes |
| R15-07 | line 1 flags | - | - | yes |
| R16-01 | claim outcome | DENY | DENY | yes |
| R16-01 | line 1 outcome | DENY | DENY | yes |
| R16-01 | line 1 reasons | DN_HOME_TEST_PARASOMNIA | DN_HOME_TEST_PARASOMNIA | yes |
| R16-01 | line 1 flags | - | - | yes |
| R16-02 | claim outcome | PASS | PASS | yes |
| R16-02 | line 1 outcome | PASS | PASS | yes |
| R16-02 | line 1 reasons | - | - | yes |
| R16-02 | line 1 flags | - | - | yes |
| R17-01 | claim outcome | PASS | PASS | yes |
| R17-01 | line 1 outcome | PASS | PASS | yes |
| R17-01 | line 1 reasons | - | - | yes |
| R17-01 | line 1 flags | NCS_WITHOUT_EMG | NCS_WITHOUT_EMG | yes |
| R17-02 | claim outcome | PASS | PASS | yes |
| R17-02 | line 1 outcome | PASS | PASS | yes |
| R17-02 | line 1 reasons | - | - | yes |
| R17-02 | line 1 flags | - | - | yes |
| R17-02 | line 2 outcome | PASS | PASS | yes |
| R17-02 | line 2 reasons | - | - | yes |
| R17-02 | line 2 flags | - | - | yes |
| R18-01 | claim outcome | DENY | DENY | yes |
| R18-01 | line 1 outcome | DENY | DENY | yes |
| R18-01 | line 1 reasons | DN_ESI_LEVELS | DN_ESI_LEVELS | yes |
| R18-01 | line 1 flags | - | - | yes |
| R18-02 | claim outcome | PASS | PASS | yes |
| R18-02 | line 1 outcome | PASS | PASS | yes |
| R18-02 | line 1 reasons | - | - | yes |
| R18-02 | line 1 flags | - | - | yes |
| R18-03 | claim outcome | PASS | PASS | yes |
| R18-03 | line 1 outcome | PASS | PASS | yes |
| R18-03 | line 1 reasons | - | - | yes |
| R18-03 | line 1 flags | - | - | yes |
| R18-03 | line 2 outcome | DENY | DENY | yes |
| R18-03 | line 2 reasons | DN_ESI_LEVELS | DN_ESI_LEVELS | yes |
| R18-03 | line 2 flags | - | - | yes |
| R18-04 | claim outcome | PASS | PASS | yes |
| R18-04 | line 1 outcome | PASS | PASS | yes |
| R18-04 | line 1 reasons | - | - | yes |
| R18-04 | line 1 flags | - | - | yes |
| R18-04 | line 2 outcome | PASS | PASS | yes |
| R18-04 | line 2 reasons | - | - | yes |
| R18-04 | line 2 flags | - | - | yes |
| R18-04 | line 3 outcome | PASS | PASS | yes |
| R18-04 | line 3 reasons | - | - | yes |
| R18-04 | line 3 flags | - | - | yes |
| R18-05 | claim outcome | PASS | PASS | yes |
| R18-05 | line 1 outcome | PASS | PASS | yes |
| R18-05 | line 1 reasons | - | - | yes |
| R18-05 | line 1 flags | - | - | yes |
| R18-05 | line 2 outcome | PASS | PASS | yes |
| R18-05 | line 2 reasons | - | - | yes |
| R18-05 | line 2 flags | - | - | yes |
| R19-01 | claim outcome | PASS | PASS | yes |
| R19-01 | line 1 outcome | PASS | PASS | yes |
| R19-01 | line 1 reasons | - | - | yes |
| R19-01 | line 1 flags | - | - | yes |
| R19-01 | line 2 outcome | PASS | PASS | yes |
| R19-01 | line 2 reasons | - | - | yes |
| R19-01 | line 2 flags | - | - | yes |
| R19-01 | line 3 outcome | DENY | DENY | yes |
| R19-01 | line 3 reasons | DN_FACET_LEVELS | DN_FACET_LEVELS | yes |
| R19-01 | line 3 flags | - | - | yes |
| R19-02 | claim outcome | PASS | PASS | yes |
| R19-02 | line 1 outcome | PASS | PASS | yes |
| R19-02 | line 1 reasons | - | - | yes |
| R19-02 | line 1 flags | - | - | yes |
| R19-02 | line 2 outcome | PASS | PASS | yes |
| R19-02 | line 2 reasons | - | - | yes |
| R19-02 | line 2 flags | - | - | yes |
| R19-03 | claim outcome | PASS | PASS | yes |
| R19-03 | line 1 outcome | PASS | PASS | yes |
| R19-03 | line 1 reasons | - | - | yes |
| R19-03 | line 1 flags | FACET_TWO_REGIONS | FACET_TWO_REGIONS | yes |
| R19-03 | line 2 outcome | PASS | PASS | yes |
| R19-03 | line 2 reasons | - | - | yes |
| R19-03 | line 2 flags | FACET_TWO_REGIONS | FACET_TWO_REGIONS | yes |
| R20-01 | claim outcome | PASS | PASS | yes |
| R20-01 | line 1 outcome | PASS | PASS | yes |
| R20-01 | line 1 reasons | - | - | yes |
| R20-01 | line 1 flags | EXTENDED_TESTING | EXTENDED_TESTING | yes |
| R20-01 | line 2 outcome | PASS | PASS | yes |
| R20-01 | line 2 reasons | - | - | yes |
| R20-01 | line 2 flags | EXTENDED_TESTING | EXTENDED_TESTING | yes |
| R20-01 | line 3 outcome | PASS | PASS | yes |
| R20-01 | line 3 reasons | - | - | yes |
| R20-01 | line 3 flags | EXTENDED_TESTING | EXTENDED_TESTING | yes |
| R20-02 | claim outcome | PASS | PASS | yes |
| R20-02 | line 1 outcome | PASS | PASS | yes |
| R20-02 | line 1 reasons | - | - | yes |
| R20-02 | line 1 flags | - | - | yes |
| R20-02 | line 2 outcome | PASS | PASS | yes |
| R20-02 | line 2 reasons | - | - | yes |
| R20-02 | line 2 flags | - | - | yes |
| X-03 | claim outcome | DENY | DENY | yes |
| X-03 | line 1 outcome | DENY | DENY | yes |
| X-03 | line 1 reasons | DN_MULTIPLE_BLOCKS | DN_MULTIPLE_BLOCKS | yes |
| X-03 | line 1 flags | - | - | yes |
| X-03 | line 2 outcome | DENY | DENY | yes |
| X-03 | line 2 reasons | DN_NCCI_BUNDLED DN_MULTIPLE_BLOCKS | DN_NCCI_BUNDLED DN_MULTIPLE_BLOCKS | yes |
| X-03 | line 2 flags | - | - | yes |
| X-04 | claim outcome | PASS | PASS | yes |
| X-04 | line 1 outcome | PASS | PASS | yes |
| X-04 | line 1 reasons | - | - | yes |
| X-04 | line 1 flags | - | - | yes |
| X-04 | line 2 outcome | PASS | PASS | yes |
| X-04 | line 2 reasons | - | - | yes |
| X-04 | line 2 flags | - | - | yes |
| X-05 | claim outcome | PASS | PASS | yes |
| X-05 | line 1 outcome | PASS | PASS | yes |
| X-05 | line 1 reasons | - | - | yes |
| X-05 | line 1 flags | - | - | yes |
| X-05 | line 2 outcome | PASS | PASS | yes |
| X-05 | line 2 reasons | - | - | yes |
| X-05 | line 2 flags | - | - | yes |
| H5-08 | claim outcome | REJECT | REJECT | yes |
| H5-08 | REJECT reason | RJ_LOW_CONFIDENCE_FIELD | RJ_LOW_CONFIDENCE_FIELD | yes |
| H5-08 | line outcomes | none | none | yes |
| E2E-17 | rules claim outcome | DENY | DENY | yes |
| E2E-17 | status after processing | DENIED_BY_RULE | DENIED_BY_RULE | yes |
| E2E-17 | line 1 decision | DENY | DENY | yes |
| E2E-17 | line 1 source | RULE | RULE | yes |
| E2E-17 | line 1 reasons | DN_DX_NOT_SUPPORTED | DN_DX_NOT_SUPPORTED | yes |
| E2E-17 | review tier | N/A | N/A | yes |
| E2E-17 | final status after ACCEPT | N/A | N/A | yes |
| E2E-23 | rules claim outcome | PASS | PASS | yes |
| E2E-23 | status after processing | AWAITING_REVIEW | AWAITING_REVIEW | yes |
| E2E-23 | line 1 decision | DENY | DENY | yes |
| E2E-23 | line 1 source | RULE | RULE | yes |
| E2E-23 | line 1 reasons | DN_DX_NOT_SUPPORTED | DN_DX_NOT_SUPPORTED | yes |
| E2E-23 | line 2 decision | APPROVE | APPROVE | yes |
| E2E-23 | line 2 source | MODEL | MODEL | yes |
| E2E-23 | line 2 reasons | - | - | yes |
| E2E-23 | claim decision | PARTIAL | PARTIAL | yes |
| E2E-23 | review tier | FULL | FULL | yes |
| E2E-23 | final status after ACCEPT | FINAL_PARTIAL | FINAL_PARTIAL | yes |
| E2E-32 | rules claim outcome | PASS | PASS | yes |
| E2E-32 | status after processing | AWAITING_REVIEW | AWAITING_REVIEW | yes |
| E2E-32 | line 1 decision | DENY | DENY | yes |
| E2E-32 | line 1 source | MODEL | MODEL | yes |
| E2E-32 | line 1 reasons | DN_NOT_MEDICALLY_NECESSARY | DN_NOT_MEDICALLY_NECESSARY | yes |
| E2E-32 | line 2 decision | APPROVE | APPROVE | yes |
| E2E-32 | line 2 source | MODEL | MODEL | yes |
| E2E-32 | line 2 reasons | - | - | yes |
| E2E-32 | claim decision | PARTIAL | PARTIAL | yes |
| E2E-32 | review tier | FULL | FULL | yes |
| E2E-32 | final status after ACCEPT | FINAL_PARTIAL | FINAL_PARTIAL | yes |
