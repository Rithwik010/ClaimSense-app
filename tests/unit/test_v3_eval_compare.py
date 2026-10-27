"""The paired v3 - v2 comparison of scripts/verify/v3_eval_report.py: the same claims resampled for
both models in every bootstrap draw."""

import pytest

from scripts.verify.v3_eval_report import paired


def rows(predicted: list[str], gold: list[str]) -> list[dict]:
    return [
        {"record_id": f"R{i:03d}", "valid": True, "lines": [{"gold": g, "predicted": p}]}
        for i, (p, g) in enumerate(zip(predicted, gold, strict=True))
    ]


GOLD = ["APPROVE", "PEND", "DENY"] * 20


def test_the_same_answers_differ_by_zero() -> None:
    found = paired(rows(GOLD, GOLD), rows(GOLD, GOLD))
    assert found["claims"] == 60
    assert found["macro_f1"]["v3_minus_v2"] == 0.0
    assert found["macro_f1"]["ci95"] == [0.0, 0.0]


def test_a_better_model_has_a_positive_interval() -> None:
    worse = ["APPROVE"] * 60  # approves everything
    found = paired(rows(GOLD, GOLD), rows(worse, GOLD))
    assert found["line_accuracy"]["v3_minus_v2"] == pytest.approx(1 - 1 / 3, abs=1e-4)
    low, high = found["line_accuracy"]["ci95"]
    assert 0 < low <= found["line_accuracy"]["v3_minus_v2"] <= high
    assert found["deny_precision"]["v2"] is None  # v2 denies nothing


def test_different_claims_are_refused() -> None:
    with pytest.raises(SystemExit):
        paired(rows(GOLD, GOLD), rows(GOLD[:-1], GOLD[:-1]))
