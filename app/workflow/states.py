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


# Follow-ups after a decision (D-FUP-1, D-APL-1): a decided claim that paid nothing goes back,
# to its provider (RECEIVED, to correct or add documentation and process again) or to review (an
# appeal). Kept apart from ALLOWED_TRANSITIONS: these claims are final, and stay final until a
# provider or member asks for a follow-up (app/workflow/followup.py checks what each one needs).
FOLLOW_UP_TRANSITIONS: dict[ClaimStatus, frozenset[ClaimStatus]] = {
    ClaimStatus.REJECTED: frozenset({ClaimStatus.RECEIVED}),
    ClaimStatus.DENIED_BY_RULE: frozenset({ClaimStatus.RECEIVED}),
    ClaimStatus.PENDED_BY_RULE: frozenset({ClaimStatus.RECEIVED}),
    ClaimStatus.FINAL_PENDED: frozenset({ClaimStatus.RECEIVED}),
    ClaimStatus.FINAL_DENIED: frozenset({ClaimStatus.AWAITING_REVIEW}),
}


class InvalidTransition(ValueError):
    pass


def check_follow_up(current: ClaimStatus, new: ClaimStatus) -> None:
    if new not in FOLLOW_UP_TRANSITIONS.get(current, frozenset()):
        raise InvalidTransition(
            f"claim status {current.value} -> {new.value} is not a follow-up the plan allows"
        )


def check_transition(current: ClaimStatus, new: ClaimStatus) -> None:
    if new not in ALLOWED_TRANSITIONS.get(current, frozenset()):
        raise InvalidTransition(f"claim status {current.value} -> {new.value} is not allowed")


def is_final(status: ClaimStatus) -> bool:
    return status not in ALLOWED_TRANSITIONS
