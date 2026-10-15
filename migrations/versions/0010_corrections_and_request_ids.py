"""audit event type FIELD_CORRECTED and the request ID of each audit event (D-FIX-1, D-OBS-1)

A provider's correction of a box read from the form, before the claim is processed, is audited as
FIELD_CORRECTED. Each audit event keeps the ID of the API request that wrote it (the X-Request-ID
of the request's log lines and response), so an event, its log lines and the response that
answered it can be found from one another.

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-15 18:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0010"
down_revision: str | Sequence[str] | None = "0009"
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
    "REVIEW_OPENED",
    "REVIEW_ACCEPTED",
    "REVIEW_OVERRIDDEN",
    "FINALIZED",
    "AUTO_OUTCOME",
)
AFTER = (*BEFORE, "FIELD_CORRECTED")


def _check(types: Sequence[str]) -> str:
    return "event_type IN (" + ", ".join(f"'{t}'" for t in types) + ")"


def upgrade() -> None:
    op.drop_constraint(op.f(CONSTRAINT), "audit_events", type_="check")
    op.create_check_constraint(op.f(CONSTRAINT), "audit_events", _check(AFTER))
    op.add_column("audit_events", sa.Column("request_id", sa.String(length=64), nullable=True))
    op.create_index(
        op.f("ix_audit_events_request_id"), "audit_events", ["request_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_audit_events_request_id"), table_name="audit_events")
    op.drop_column("audit_events", "request_id")
    # audit_events is append-only (0001), so FIELD_CORRECTED rows already written stay; the old
    # check applies to new rows only (NOT VALID skips the existing ones).
    op.drop_constraint(op.f(CONSTRAINT), "audit_events", type_="check")
    op.execute(
        f"ALTER TABLE audit_events ADD CONSTRAINT {CONSTRAINT} CHECK ({_check(BEFORE)}) NOT VALID"
    )
