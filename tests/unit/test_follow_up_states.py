"""Follow-up transitions (D-FUP-1, D-APL-1): only a decided claim that paid nothing goes back, to
its provider or to review; those claims stay final otherwise, and nothing else moves."""

import pytest

from app.domain.contracts import ClaimStatus
from app.workflow.states import (
    FOLLOW_UP_TRANSITIONS,
    InvalidTransition,
    check_follow_up,
    is_final,
)

S = ClaimStatus


@pytest.mark.parametrize(
    ("current", "new"),
    [
        (S.REJECTED, S.RECEIVED),  # correct and resubmit
        (S.DENIED_BY_RULE, S.RECEIVED),
        (S.PENDED_BY_RULE, S.RECEIVED),  # correct, or send documentation
        (S.FINAL_PENDED, S.RECEIVED),  # send documentation
        (S.FINAL_DENIED, S.AWAITING_REVIEW),  # appeal
    ],
)
def test_the_follow_ups(current: ClaimStatus, new: ClaimStatus) -> None:
    check_follow_up(current, new)
    assert is_final(current)  # still final until someone asks


@pytest.mark.parametrize(
    ("current", "new"),
    [
        (S.FINAL_APPROVED, S.RECEIVED),  # paid: never reopened
        (S.FINAL_PARTIAL, S.AWAITING_REVIEW),
        (S.FINAL_DENIED, S.RECEIVED),  # a reviewer's denial is appealed, not resubmitted
        (S.REJECTED, S.AWAITING_REVIEW),
        (S.AWAITING_REVIEW, S.RECEIVED),
        (S.RECEIVED, S.RECEIVED),
    ],
)
def test_nothing_else(current: ClaimStatus, new: ClaimStatus) -> None:
    with pytest.raises(InvalidTransition):
        check_follow_up(current, new)


def test_the_table_is_what_the_decision_says() -> None:
    assert set(FOLLOW_UP_TRANSITIONS) == {
        S.REJECTED,
        S.DENIED_BY_RULE,
        S.PENDED_BY_RULE,
        S.FINAL_PENDED,
        S.FINAL_DENIED,
    }
