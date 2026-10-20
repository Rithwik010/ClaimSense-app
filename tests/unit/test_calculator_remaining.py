"""What is left of a yearly limit (D-MEM-3): the remaining deductible and out-of-pocket amount in
integer cents, and the visits left of a visit-limited benefit. The member's benefits page shows
these, and the calculator uses the same function for a claim's working totals (§8.6 steps 3-4)."""

import random

import pytest

from app.calculator.engine import (
    Accumulators,
    CalcLine,
    CostShareTerms,
    FeeEntry,
    NetworkTerms,
    calculate,
)
from app.calculator.remaining import LimitUsage, limit_usage, remaining_cents, visits_left
from app.domain.contracts import CostShareRule, LineDecision, Network


@pytest.mark.parametrize(
    ("limit", "met", "left"),
    [
        (50000, 0, 50000),  # nothing met yet
        (50000, 46500, 3500),  # part met
        (50000, 49999, 1),  # a cent left
        (50000, 50000, 0),  # met exactly
        (50000, 50001, 0),  # met above the limit (a stored total can be): nothing left, never < 0
        (0, 0, 0),  # a plan with no deductible
        (0, 1200, 0),
    ],
)
def test_remaining_cents_is_the_limit_less_what_is_met_never_below_zero(
    limit: int, met: int, left: int
) -> None:
    assert remaining_cents(limit, met) == left


@pytest.mark.parametrize(
    ("limit", "used", "left"),
    [(20, 0, 20), (20, 12, 8), (20, 19, 1), (20, 20, 0), (20, 23, 0), (30, 7, 23)],
)
def test_visits_left_is_the_limit_less_the_visits_used_never_below_zero(
    limit: int, used: int, left: int
) -> None:
    assert visits_left(limit, used) == left


@pytest.mark.parametrize(("limit", "used"), [(-1, 0), (0, -1), (-5, -5)])
def test_negative_inputs_are_refused(limit: int, used: int) -> None:
    with pytest.raises(ValueError, match="must not be negative"):
        remaining_cents(limit, used)
    with pytest.raises(ValueError, match="must not be negative"):
        visits_left(limit, used)


@pytest.mark.parametrize("value", [1.5, "100", None, True])
def test_only_integers_are_accepted(value: object) -> None:
    """Money is integer cents (H2): a float, a string or a bool is refused, not rounded."""
    with pytest.raises(TypeError, match="integer"):
        remaining_cents(value, 0)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="integer"):
        remaining_cents(50000, value)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="integer"):
        visits_left(value, 0)  # type: ignore[arg-type]


def test_limit_usage_keeps_the_stored_amount_and_the_limit() -> None:
    assert limit_usage(300000, 47700) == LimitUsage(
        limit_cents=300000, met_cents=47700, remaining_cents=252300
    )
    assert limit_usage(400000, 400000) == LimitUsage(400000, 400000, 0)


def test_met_plus_remaining_is_the_limit_until_the_limit_is_reached() -> None:
    rng = random.Random(20261019)
    for _ in range(5000):
        limit = rng.choice([0, 25000, 50000, 300000, rng.randint(0, 2_000_000)])
        met = rng.choice([0, limit, limit + rng.randint(1, 900), rng.randint(0, max(limit, 1))])
        left = remaining_cents(limit, met)
        assert isinstance(left, int) and left >= 0
        assert left == (limit - met if met <= limit else 0)


def test_the_calculator_caps_a_claim_at_the_remaining_amounts() -> None:
    """The calculator's working totals start from the same remaining amounts the member sees: a
    claim's deductible is at most the remaining deductible, and its cost share at most the
    remaining out-of-pocket amount."""
    terms = NetworkTerms(deductible_cents=50000, coinsurance_bps=2000, oop_max_cents=300000)
    stored = Accumulators(deductible_met_cents=46500, oop_met_cents=296000)
    line = CalcLine(
        line_no=1,
        procedure_code="11721",
        units=1,
        billed_cents=20000,
        decision=LineDecision.APPROVE,
        benefit_category="MINOR_PROCEDURES",
    )
    result = calculate(
        [line],
        Network.IN_NETWORK,
        terms,
        {"MINOR_PROCEDURES": CostShareTerms(CostShareRule.DEDUCTIBLE_COINSURANCE, None)},
        {"11721": FeeEntry(inn_allowed_cents=10000, oon_allowed_cents=8000)},
        stored,
    )

    # Allowed 100.00: the deductible takes the 35.00 left of it; coinsurance would be 20% of the
    # other 65.00 (13.00), but only 40.00 of the out-of-pocket maximum is left, so it is 5.00.
    amounts = result.amounts.lines[0]
    assert amounts.deductible_cents == remaining_cents(50000, 46500) == 3500
    assert amounts.coinsurance_cents == 500
    share = amounts.deductible_cents + amounts.copay_cents + amounts.coinsurance_cents
    assert share == remaining_cents(300000, 296000) == 4000
