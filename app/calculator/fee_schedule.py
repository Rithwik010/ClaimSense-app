"""Allowed amounts from the Physician Fee Schedule (DECISIONS.md D6, `fee_schedule.yaml`).

National amount = total non-facility RVU x conversion factor, rounded half-up to whole cents.
In-network allowed = national amount x in-network bps; out-of-network allowed = national amount x
out-of-network bps; each rounded half-up to whole cents.
"""

from decimal import Decimal

from app.calculator.money import apply_bps, round_half_up


def national_amount_cents(total_rvu: Decimal, conversion_factor: Decimal) -> int:
    if total_rvu < 0 or conversion_factor < 0:
        raise ValueError("RVU and conversion factor must not be negative")
    return round_half_up(total_rvu * conversion_factor * 100)


def allowed_amounts(
    total_rvu: Decimal, conversion_factor: Decimal, in_network_bps: int, out_of_network_bps: int
) -> tuple[int, int]:
    """(in-network allowed cents, out-of-network allowed cents)."""
    national = national_amount_cents(total_rvu, conversion_factor)
    return apply_bps(national, in_network_bps), apply_bps(national, out_of_network_bps)
