"""Claim status transitions (INSTRUCTIONS.md §5): an explicit table; anything else raises."""

from app.domain.contracts import ClaimStatus

FINAL_REVIEW_STATUSES = frozenset(
    {
        ClaimStatus.FINAL_APPROVED,
        ClaimStatus.FINAL_PARTIAL,
        ClaimStatus.FINAL_DENIED,
        ClaimStatus.FINAL_PENDED,
    }
)

ALLOWED_TRANSITIONS: dict[ClaimStatus, frozenset[ClaimStatus]] = {
    ClaimStatus.RECEIVED: frozenset(
        {
            ClaimStatus.REJECTED,
            ClaimStatus.DENIED_BY_RULE,
            ClaimStatus.PENDED_BY_RULE,
            ClaimStatus.AWAITING_REVIEW,
        }
    ),
    ClaimStatus.AWAITING_REVIEW: FINAL_REVIEW_STATUSES,
}


class InvalidTransition(ValueError):
    pass


def check_transition(current: ClaimStatus, new: ClaimStatus) -> None:
    if new not in ALLOWED_TRANSITIONS.get(current, frozenset()):
        raise InvalidTransition(f"claim status {current.value} -> {new.value} is not allowed")


def is_final(status: ClaimStatus) -> bool:
    return status not in ALLOWED_TRANSITIONS
