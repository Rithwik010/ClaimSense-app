"""Rules engine (INSTRUCTIONS.md §8.3). Bump RULES_VERSION on every change to a rule.

RULES_VERSION is the v1 rule set (R01–R13, duplicates, H5; P2.3a), the rules the model v1 dataset
was generated with. The pipeline runs it since P2.5 (the walking skeleton's R05-only path, version
0.1.0, is gone).
"""

RULES_VERSION = "1.0.0"
