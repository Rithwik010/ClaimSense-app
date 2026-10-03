"""Rules engine (INSTRUCTIONS.md §8.3). Bump RULES_VERSION on every change to a rule.

RULES_VERSION is the v1 rule set (R01–R13, duplicates, H5; P2.3a), the rules the model v1 dataset
was generated with. SKELETON_RULES_VERSION is the walking skeleton's R05-only path, which the
pipeline records until it switches to the full engine (after P2.1 loads NCCI, MUE, place of service
and the full code table).
"""

RULES_VERSION = "1.0.0"
SKELETON_RULES_VERSION = "0.1.0"
