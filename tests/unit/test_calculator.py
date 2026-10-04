"""The calculator's steps on hand-worked values (INSTRUCTIONS.md §8.6, assumptions A1 to A9). The
golden cases are in test_calculator_golden.py; the invariants on random claims in
test_calculator_properties.py."""

from decimal import Decimal

import pytest

from app.calculator.engine import (
    Accumulators,
    CalcLine,
    CalculationError,
    CostShare,
    CostShareTerms,
    FeeEntry,
    NetworkTerms,
    adjustments,
    allowed_amount,
    calculate,
    cap_to_out_of_pocket,
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


# --- Step 4: the out-of-pocket cap, filled deductible, copay, coinsurance (A4, A5) --------------


@pytest.mark.parametrize(
    ("share", "remaining", "capped"),
    [
        (CostShare(10000, 0, 5924), 11000, CostShare(10000, 0, 1000)),  # coinsurance cut first
        (CostShare(20000, 0, 4905), 15000, CostShare(15000, 0, 0)),  # cap inside the deductible
        (CostShare(0, 5000, 0), 1000, CostShare(0, 1000, 0)),
        (CostShare(0, 3000, 0), 0, CostShare(0, 0, 0)),
        (CostShare(10000, 0, 2885), 12885, CostShare(10000, 0, 2885)),  # exactly the remainder
        (CostShare(10000, 0, 2885), 300000, CostShare(10000, 0, 2885)),
    ],
)
def test_the_cap_keeps_deductible_then_copay_then_coinsurance(
    share: CostShare, remaining: int, capped: CostShare
) -> None:
    assert cap_to_out_of_pocket(share, remaining) == capped


# --- Step 7: working accumulators across the lines of one claim --------------------------------

IMAGING = CostShareTerms(CostShareRule.DEDUCTIBLE_COINSURANCE, None)
FEES = {"70551": FeeEntry(24425, 19540), "70553": FeeEntry(39621, 31697), "99213": FEE}


def imaging(line_no: int, code: str, billed: int) -> CalcLine:
    return CalcLine(line_no, code, 1, billed, LineDecision.APPROVE, "ADVANCED_IMAGING")


def test_a_deductible_split_across_two_lines_carries_over() -> None:
    lines = [imaging(1, "70551", 39000), imaging(2, "70553", 60000)]
    before = Accumulators(deductible_met_cents=20000, oop_met_cents=20000)

    result = calculate(
        lines, Network.IN_NETWORK, TERMS, {"ADVANCED_IMAGING": IMAGING}, FEES, before
    )

    first, second = result.amounts.lines
    # remaining 30000: line 1 all deductible (24425); line 2 the last 5575, then 20% of 34046
    assert (first.deductible_cents, first.coinsurance_cents) == (24425, 0)
    assert (second.deductible_cents, second.coinsurance_cents) == (5575, 6809)  # 6809.2
    assert result.accumulators_after == Accumulators(50000, 20000 + 24425 + 5575 + 6809)
    assert before == Accumulators(20000, 20000)  # stored accumulators are never written


def test_the_cap_reached_on_one_line_leaves_nothing_for_the_next() -> None:
    lines = [
        imaging(1, "70553", 60000),
        CalcLine(2, "99213", 1, 19000, LineDecision.APPROVE, "OFFICE_VISIT_PCP"),
    ]
    before = Accumulators(deductible_met_cents=50000, oop_met_cents=295000)
    benefits = {"ADVANCED_IMAGING": IMAGING, "OFFICE_VISIT_PCP": COPAY}

    result = calculate(lines, Network.IN_NETWORK, TERMS, benefits, FEES, before)

    first, second = result.amounts.lines
    # remaining 5000: coinsurance 7924 (39621 x 20% = 7924.2) is cut to 5000; the copay to 0
    assert (first.coinsurance_cents, first.member_pays_cents, first.plan_pays_cents) == (
        5000,
        5000,
        34621,
    )
    assert (second.copay_cents, second.member_pays_cents, second.plan_pays_cents) == (0, 0, 11899)
    assert result.accumulators_after == Accumulators(50000, 300000)
