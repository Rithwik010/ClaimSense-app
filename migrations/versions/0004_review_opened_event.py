"""audit event type REVIEW_OPENED (P5.3)

A reviewer opening a claim awaiting review is audited as REVIEW_OPENED, so the review time can run
from the acting reviewer's latest opening to the action (D-REV-6).

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-09 12:00:00

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: str | Sequence[str] | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CONSTRAINT = "ck_audit_events_event_type_allowed"
BEFORE = (
    "INTAKE_COMPLETED",
    "RULES_EVALUATED",
    "CONTEXT_ASSEMBLED",
    "SLM_RECOMMENDED",
    "OUTPUT_INVALID",
    "CALCULATED",
    "CALCULATION_FAILED",
    "EXPLANATION_BUILT",
    "REVIEW_ACCEPTED",
    "REVIEW_OVERRIDDEN",
    "FINALIZED",
    "AUTO_OUTCOME",
)
AFTER = (*BEFORE[:8], "REVIEW_OPENED", *BEFORE[8:])


def _check(types: Sequence[str]) -> str:
    return "event_type IN (" + ", ".join(f"'{t}'" for t in types) + ")"


def upgrade() -> None:
    op.drop_constraint(op.f(CONSTRAINT), "audit_events", type_="check")
    op.create_check_constraint(op.f(CONSTRAINT), "audit_events", _check(AFTER))


def downgrade() -> None:
    # audit_events is append-only (0001), so REVIEW_OPENED rows already written stay; the old check
    # applies to new rows only (NOT VALID skips the existing ones).
    op.drop_constraint(op.f(CONSTRAINT), "audit_events", type_="check")
    op.execute(
        f"ALTER TABLE audit_events ADD CONSTRAINT {CONSTRAINT} CHECK ({_check(BEFORE)}) NOT VALID"
    )
