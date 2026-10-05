"""P2.1/P2.5 decision 2: the count of claims with a date of service before 2026-10-01
(scripts/verify/early_dates.py)."""

from scripts.verify.early_dates import claim_sets, summary


def test_dates_before_the_first_loaded_day_are_counted_per_claim() -> None:
    rows = summary({"set": [["2026-09-30", "2026-10-02"], ["2026-10-01"], []]})

    assert rows == [("set", 3, 1, "2026-09-30", "2026-10-02")]


def test_no_committed_claim_has_a_date_before_fy2027() -> None:
    """Golden rules, golden end-to-end, blind-review and the sample claim: none (dates only)."""
    for name, _, early, _, _ in summary(claim_sets()):
        assert early == 0, name
