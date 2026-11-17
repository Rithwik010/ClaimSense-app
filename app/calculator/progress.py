"""How far a member is through a yearly limit (D-MEM-5): what is left of a deductible, an
out-of-pocket maximum or a visit limit, and the share used in basis points; and the sums the lists
and the Overview report (D-UI-12, D-QLT-1). The calculator's, because only the calculator produces
amounts (H1); the pages show these as they are. A new module: the claim calculation is untouched.

Integers only: cents, visits and basis points. Nothing is ever below zero or above the limit: a
stored total over its limit (a plan whose limit changed mid-year) shows as nothing left, 100%."""

from collections.abc import Iterable

from app.calculator.money import BPS_DENOMINATOR


def remaining(limit: int, used: int) -> int:
    """What is left of a limit: limit - used, never below zero."""
    if limit < 0 or used < 0:
        raise ValueError("a limit and what is used of it must not be negative")
    return max(limit - used, 0)


def used_bps(limit: int, used: int) -> int:
    """The share of a limit used, in basis points (0 to 10000), rounded down so a limit shows
    100% only once it is fully used. A limit of zero is fully used."""
    if limit < 0 or used < 0:
        raise ValueError("a limit and what is used of it must not be negative")
    if limit == 0:
        return BPS_DENOMINATOR
    return min(used * BPS_DENOMINATOR // limit, BPS_DENOMINATOR)


def total_cents(amounts: Iterable[int]) -> int:
    """The sum of whole-cent amounts: a claim's billed charges as filed (the lists' Billed column)
    and the Overview's sums of stored totals. Every amount is cents, never negative."""
    total = 0
    for amount in amounts:
        if isinstance(amount, bool) or not isinstance(amount, int) or amount < 0:
            raise ValueError("amounts are whole, non-negative cents")
        total += amount
    return total
