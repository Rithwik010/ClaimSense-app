"""The calculator's steps on hand-worked values (INSTRUCTIONS.md §8.6, assumptions A1 to A9). The
golden cases are in test_calculator_golden.py; the invariants on random claims in
test_calculator_properties.py."""

from decimal import Decimal

import pytest

from app.calculator.engine import (
    CalcLine,
    CalculationError,
    CostShare,
    CostShareTerms,
    FeeEntry,
    NetworkTerms,
    adjustments,
    allowed_amount,
    cost_share,
)
from app.calculator.money import apply_bps, round_half_up
from app.domain.contracts import CostShareRule, LineDecision, Network

FEE = FeeEntry(inn_allowed_cents=11899, oon_allowed_cents=9519)
TERMS = NetworkTerms(deductible_cents=50000, coinsurance_bps=2000, oop_max_cents=300000)
COPAY = CostShareTerms(CostShareRule.COPAY, 2500)
DEDUCTIBLE = CostShareTerms(CostShareRule.DEDUCTIBLE_COINSURANCE, None)


def line(units: int = 1, billed: int = 19000) -> CalcLine:
    return CalcLine(1, "99213", units, billed, LineDecision.APPROVE, "OFFICE_VISIT_PCP")


# --- Steps 1 and 2: allowed amount (A1), contractual adjustment and balance-bill exposure (A9) ---


def test_allowed_is_the_fee_for_the_network_times_units_capped_by_billed() -> None:
    assert allowed_amount(line(), Network.IN_NETWORK, FEE) == 11899
    assert allowed_amount(line(), Network.OUT_OF_NETWORK, FEE) == 9519
    three_units = allowed_amount(line(units=3, billed=40000), Network.IN_NETWORK, FEE)
    assert three_units == 35697  # 3 x 11899
    assert allowed_amount(line(units=3, billed=30000), Network.IN_NETWORK, FEE) == 30000  # billed


def test_contractual_adjustment_in_network_and_balance_bill_out_of_network() -> None:
    assert adjustments(19000, 11899, Network.IN_NETWORK) == (7101, 0)
    assert adjustments(19000, 9519, Network.OUT_OF_NETWORK) == (0, 9481)
    assert adjustments(9000, 9000, Network.IN_NETWORK) == (0, 0)


# --- Rounding (§8.6: Decimal for percentage math, ROUND_HALF_UP to whole cents) ---------------


@pytest.mark.parametrize(
    ("value", "cents"),
    [
        ("0.5", 1),
        ("2.5", 3),  # banker's rounding would give 2
        ("3.5", 4),
        ("1234.5", 1235),
        ("2663.8", 2664),
        ("2.4999", 2),
        ("5424.4", 5424),
        ("0", 0),
    ],
)
def test_round_half_up_by_hand(value: str, cents: int) -> None:
    assert round_half_up(Decimal(value)) == cents


@pytest.mark.parametrize(
    ("amount", "bps", "cents"),
    [
        (15, 5000, 8),  # 7.5 -> 8
        (25, 5000, 13),  # 12.5 -> 13 (banker's rounding would give 12)
        (10005, 5000, 5003),  # 5002.5 -> 5003
        (13319, 2000, 2664),  # 2663.8 -> 2664
        (4591, 1000, 459),  # 459.1 -> 459
        (19621, 2500, 4905),  # 4905.25 -> 4905
        (14425, 2000, 2885),  # exact
    ],
)
def test_apply_bps_rounds_half_up_by_hand(amount: int, bps: int, cents: int) -> None:
    assert apply_bps(amount, bps) == cents


# --- Step 3: member cost share by the benefit's rule; out of network (A3) ----------------------


def test_copay_is_the_copay_capped_by_allowed_and_skips_the_deductible() -> None:
    assert cost_share(11899, Network.IN_NETWORK, COPAY, TERMS, 50000) == CostShare(0, 2500, 0)
    assert cost_share(2000, Network.IN_NETWORK, COPAY, TERMS, 50000) == CostShare(0, 2000, 0)


def test_deductible_then_coinsurance_on_the_rest() -> None:
    # remaining 10000 of 24425: deductible 10000; coinsurance 14425 x 20% = 2885
    assert cost_share(24425, Network.IN_NETWORK, DEDUCTIBLE, TERMS, 10000) == CostShare(
        10000, 0, 2885
    )
    # deductible larger than allowed: all deductible, no coinsurance
    assert cost_share(24425, Network.IN_NETWORK, DEDUCTIBLE, TERMS, 30000) == CostShare(24425, 0, 0)


def test_coinsurance_rounds_half_up() -> None:
    terms = NetworkTerms(deductible_cents=0, coinsurance_bps=5000, oop_max_cents=300000)

    assert cost_share(10005, Network.IN_NETWORK, DEDUCTIBLE, terms, 0) == CostShare(0, 0, 5003)


def test_out_of_network_uses_deductible_and_coinsurance_even_for_a_copay_category() -> None:
    oon = NetworkTerms(deductible_cents=100000, coinsurance_bps=4000, oop_max_cents=600000)

    # A3: remaining deductible 0; coinsurance 13561 x 40% = 5424.4 -> 5424
    assert cost_share(13561, Network.OUT_OF_NETWORK, COPAY, oon, 0) == CostShare(0, 0, 5424)


def test_a_copay_category_without_a_copay_amount_is_an_error() -> None:
    with pytest.raises(CalculationError, match="copay"):
        cost_share(11899, Network.IN_NETWORK, CostShareTerms(CostShareRule.COPAY, None), TERMS, 0)
