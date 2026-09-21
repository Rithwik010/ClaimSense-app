"""Money primitives (H2): integer cents, integer basis points, Decimal only for intermediate math,
rounded half-up to whole cents (INSTRUCTIONS.md §8.6)."""

from decimal import ROUND_HALF_UP, Decimal

BPS_DENOMINATOR = 10000


def round_half_up(value: Decimal) -> int:
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def apply_bps(amount_cents: int, bps: int) -> int:
    """amount x bps / 10000, rounded half-up to whole cents."""
    if amount_cents < 0 or bps < 0:
        raise ValueError("amount and basis points must not be negative")
    return round_half_up(Decimal(amount_cents) * bps / BPS_DENOMINATOR)
