"""What is left of a yearly limit (D-MEM-3): the remaining deductible and out-of-pocket amount, in
integer cents (H2), and the visits left of a visit-limited benefit.

One place for "remaining": the calculator starts a claim's working totals from it (§8.6 steps 3-4,
engine.calculate), and the member's benefits page shows it for the stored accumulators and visit
usage of the current benefit year, so both always agree. A stored total can be above its limit (the
generated reference data has such members); nothing is then left, never a negative amount.
"""

from dataclasses import dataclass


def _counts(limit: int, used: int) -> None:
    for value in (limit, used):
        if not isinstance(value, int) or isinstance(value, bool):
            raise TypeError(f"limits and amounts are integers (cents or visits), not {value!r}")
        if value < 0:
            raise ValueError("a limit and what is used of it must not be negative")


def remaining_cents(limit_cents: int, met_cents: int) -> int:
    """What is left of a yearly limit in cents: the limit less what is met, not below 0."""
    _counts(limit_cents, met_cents)
    return max(limit_cents - met_cents, 0)


def visits_left(visit_limit: int, visits_used: int) -> int:
    """The visits left of a visit-limited benefit this benefit year, not below 0."""
    _counts(visit_limit, visits_used)
    return max(visit_limit - visits_used, 0)


@dataclass(frozen=True)
class LimitUsage:
    """A yearly limit (a deductible or an out-of-pocket maximum), what is met of it as stored, and
    what is left, in cents."""

    limit_cents: int
    met_cents: int
    remaining_cents: int


def limit_usage(limit_cents: int, met_cents: int) -> LimitUsage:
    return LimitUsage(limit_cents, met_cents, remaining_cents(limit_cents, met_cents))
