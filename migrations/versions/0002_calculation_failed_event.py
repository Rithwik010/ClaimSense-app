"""audit event type CALCULATION_FAILED (P2.4)

A calculation that fails (for example an approved line whose code has no fee) is audited as
CALCULATION_FAILED and the claim goes to FULL review instead of stopping the pipeline.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-04 12:00:00

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
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
    "EXPLANATION_BUILT",
    "REVIEW_ACCEPTED",
    "REVIEW_OVERRIDDEN",
    "FINALIZED",
    "AUTO_OUTCOME",
)
AFTER = (*BEFORE[:6], "CALCULATION_FAILED", *BEFORE[6:])


def _check(types: Sequence[str]) -> str:
    return "event_type IN (" + ", ".join(f"'{t}'" for t in types) + ")"


def upgrade() -> None:
    op.drop_constraint(op.f(CONSTRAINT), "audit_events", type_="check")
    op.create_check_constraint(op.f(CONSTRAINT), "audit_events", _check(AFTER))


def downgrade() -> None:
    # audit_events is append-only (0001), so CALCULATION_FAILED rows already written stay; the old
    # check applies to new rows only (NOT VALID skips the existing ones).
    op.drop_constraint(op.f(CONSTRAINT), "audit_events", type_="check")
    op.execute(
        f"ALTER TABLE audit_events ADD CONSTRAINT {CONSTRAINT} CHECK ({_check(BEFORE)}) NOT VALID"
    )
