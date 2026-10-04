"""The calculator's steps on hand-worked values (INSTRUCTIONS.md §8.6, assumptions A1 to A9). The
golden cases are in test_calculator_golden.py; the invariants on random claims in
test_calculator_properties.py."""

from app.calculator.engine import CalcLine, FeeEntry, adjustments, allowed_amount
from app.domain.contracts import LineDecision, Network

FEE = FeeEntry(inn_allowed_cents=11899, oon_allowed_cents=9519)


def line(units: int = 1, billed: int = 19000) -> CalcLine:
    return CalcLine(1, "99213", units, billed, LineDecision.APPROVE, "OFFICE_VISIT_PCP")


# --- Steps 1 and 2: allowed amount (A1), contractual adjustment and balance-bill exposure (A9) ---


def test_allowed_is_the_fee_for_the_network_times_units_capped_by_billed() -> None:
    assert allowed_amount(line(), Network.IN_NETWORK, FEE) == 11899
    assert allowed_amount(line(), Network.OUT_OF_NETWORK, FEE) == 9519
    assert (
        allowed_amount(line(units=3, billed=40000), Network.IN_NETWORK, FEE) == 35697
    )  # 3 x 11899
    assert allowed_amount(line(units=3, billed=30000), Network.IN_NETWORK, FEE) == 30000  # billed


def test_contractual_adjustment_in_network_and_balance_bill_out_of_network() -> None:
    assert adjustments(19000, 11899, Network.IN_NETWORK) == (7101, 0)
    assert adjustments(19000, 9519, Network.OUT_OF_NETWORK) == (0, 9481)
    assert adjustments(9000, 9000, Network.IN_NETWORK) == (0, 0)
