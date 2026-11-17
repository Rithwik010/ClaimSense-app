"""The calculator's limit progress (D-MEM-5): what is left and the share used. Expected
values worked by hand: 1500.00 deductible, 400.00 met -> 1100.00 left, 400/1500 = 26.66% -> 2666
basis points (rounded down)."""

import pytest

from app.calculator.progress import remaining, used_bps


@pytest.mark.parametrize(
    ("limit", "used", "left"),
    [
        (150_000, 40_000, 110_000),  # part met
        (150_000, 0, 150_000),  # nothing met
        (150_000, 150_000, 0),  # met exactly
        (150_000, 160_000, 0),  # over the limit: nothing left, never negative
        (0, 0, 0),  # no deductible
        (20, 7, 13),  # visits: 20 a year, 7 used
    ],
)
def test_remaining(limit: int, used: int, left: int) -> None:
    assert remaining(limit, used) == left


@pytest.mark.parametrize(
    ("limit", "used", "bps"),
    [
        (150_000, 40_000, 2666),  # 26.666...% rounded down
        (150_000, 0, 0),
        (150_000, 149_999, 9999),  # one cent short is not 100%
        (150_000, 150_000, 10_000),
        (150_000, 160_000, 10_000),  # capped
        (0, 0, 10_000),  # a zero limit is fully used
        (20, 7, 3500),
    ],
)
def test_used_bps(limit: int, used: int, bps: int) -> None:
    assert used_bps(limit, used) == bps


@pytest.mark.parametrize("args", [(-1, 0), (0, -1)])
def test_negative_refused(args: tuple[int, int]) -> None:
    with pytest.raises(ValueError):
        remaining(*args)
    with pytest.raises(ValueError):
        used_bps(*args)


def test_total_cents() -> None:
    from app.calculator.progress import total_cents

    assert total_cents([12_500, 0, 7_550]) == 20_050  # 125.00 + 0.00 + 75.50 = 200.50
    assert total_cents([]) == 0
    for bad in ([-1], [1.5], [True]):
        with pytest.raises(ValueError):
            total_cents(bad)  # type: ignore[arg-type]
