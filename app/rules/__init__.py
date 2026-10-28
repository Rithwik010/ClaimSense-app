"""Rules engine (INSTRUCTIONS.md §8.3). Bump RULES_VERSION on every change to a rule.

RULES_VERSION 2.1.0 (P2.3c) is the v1 rule set (R01–R13, duplicates, H5; P2.3a), the rules the
model v1 dataset was generated with, plus rules v2 R14–R20 from the LCDs and billing articles
(D-RULE-2 to D-RULE-7, P2.3b), with R11 bypassing NCCI edits by the manual's NCCI PTP-associated
modifiers (D-RULE-8). Versions: major when a rule is added or removed, minor when an existing
rule's behaviour changes, patch when no outcome can change (D-RULE-9). The pipeline runs it since
P2.5.

RULES_VERSION 2.2.0 adds R21, the yearly visit limit (D-RULE-10); the minor bump for an added
rule is the team's choice of 17 Oct, an exception to D-RULE-9.
"""

RULES_VERSION = "2.2.0"
