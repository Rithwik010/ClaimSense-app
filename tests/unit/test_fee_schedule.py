"""Fee schedule amounts (DECISIONS.md D6; data/curated/fee_schedule.yaml).

Expected values worked by hand, PFS RVU26A national non-facility total RVUs, CF 33.4009:
  99213: 2.85 x 33.4009 = 95.192565 -> 9519 cents; x 1.25 = 11898.75 -> 11899
  64483: 7.93 x 33.4009 = 264.869137 -> 26487 cents; x 1.25 = 33108.75 -> 33109
  97110: 0.87 x 33.4009 = 29.058783 -> 2906 cents; x 1.25 = 3632.50 -> 3633 (half-up)
"""

from decimal import Decimal

import pytest

from app.calculator.fee_schedule import allowed_amounts, national_amount_cents
from app.calculator.money import apply_bps, round_half_up

CF = Decimal("33.4009")


@pytest.mark.parametrize(
    ("value", "expected"),
    [("0.5", 1), ("1.49", 1), ("1.5", 2), ("2.5", 3), ("11898.75", 11899), ("3632.50", 3633)],
)
def test_round_half_up(value: str, expected: int) -> None:
    assert round_half_up(Decimal(value)) == expected


def test_apply_bps() -> None:
    assert apply_bps(9519, 12500) == 11899
    assert apply_bps(2906, 12500) == 3633
    assert apply_bps(10000, 2000) == 2000
    assert apply_bps(0, 3000) == 0


@pytest.mark.parametrize(
    ("rvu", "national", "inn", "oon"),
    [("2.85", 9519, 11899, 9519), ("7.93", 26487, 33109, 26487), ("0.87", 2906, 3633, 2906)],
)
def test_allowed_amounts(rvu: str, national: int, inn: int, oon: int) -> None:
    assert national_amount_cents(Decimal(rvu), CF) == national
    assert allowed_amounts(Decimal(rvu), CF, 12500, 10000) == (inn, oon)


def test_results_are_int_cents() -> None:
    inn, oon = allowed_amounts(Decimal("2.85"), CF, 12500, 10000)
    assert type(inn) is int and type(oon) is int


def test_negative_inputs_are_rejected() -> None:
    with pytest.raises(ValueError):
        apply_bps(-1, 10000)
    with pytest.raises(ValueError):
        apply_bps(100, -1)
    with pytest.raises(ValueError):
        national_amount_cents(Decimal("-1"), CF)
