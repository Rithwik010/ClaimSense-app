"""Deterministic money calculations in integer cents. Must not import ML, RAG or model code.

CALCULATOR_VERSION is recorded with every calculation (the CALCULATED or CALCULATION_FAILED audit
event); bump it on every change to the calculation. 1.0.0 is the full calculator of §8.6 with
assumptions A1-A9 (P2.4).
"""

CALCULATOR_VERSION = "1.0.0"
