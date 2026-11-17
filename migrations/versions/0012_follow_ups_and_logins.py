"""follow-ups after a decision, reviewer feedback and login protection (D-FUP-1, D-APL-1, D-FBK-1,
D-AUTH-2)

- Audit event types for a claim reopened for its provider to correct or add documentation
  (CLAIM_REOPENED, DOCUMENTATION_ADDED), an appeal filed and decided (APPEAL_FILED,
  APPEAL_DECIDED), and a reviewer's correction of the model's criteria (REVIEWER_FEEDBACK).
- appeals: a provider's or member's request that another reviewer decide a denied claim again.
- users: consecutive failed logins, when the login is locked until, and when the password last
  changed.

Revision ID: 0012
Revises: 0011
Create Date: 2026-11-16 10:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0012"
down_revision: str | Sequence[str] | None = "0011"
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
    "FIELD_CORRECTED",
)
AFTER = (
    *BEFORE,
    "CLAIM_REOPENED",
    "DOCUMENTATION_ADDED",
    "APPEAL_FILED",
    "APPEAL_DECIDED",
    "REVIEWER_FEEDBACK",
)


def _check(types: Sequence[str]) -> str:
    return "event_type IN (" + ", ".join(f"'{t}'" for t in types) + ")"


def upgrade() -> None:
    op.drop_constraint(op.f(CONSTRAINT), "audit_events", type_="check")
    op.create_check_constraint(op.f(CONSTRAINT), "audit_events", _check(AFTER))

    op.create_table(
        "appeals",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("claim_id", sa.String(length=48), nullable=False),
        sa.Column("filed_by", sa.String(length=64), nullable=False),
        sa.Column("filed_role", sa.String(length=16), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column(
            "filed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("previous_status", sa.String(length=24), nullable=False),
        sa.Column("previous_reviewer", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=16), server_default="OPEN", nullable=False),
        sa.Column("outcome", sa.String(length=16), nullable=True),
        sa.Column("decided_by", sa.String(length=64), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["claim_id"], ["claims.claim_id"], name=op.f("fk_appeals_claim_id_claims")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_appeals")),
        sa.CheckConstraint(
            "filed_role IN ('provider', 'member')", name=op.f("ck_appeals_filed_role")
        ),
        sa.CheckConstraint("status IN ('OPEN', 'DECIDED')", name=op.f("ck_appeals_status")),
        sa.CheckConstraint(
            "(status = 'OPEN' AND outcome IS NULL AND decided_by IS NULL AND decided_at IS NULL)"
            " OR (status = 'DECIDED' AND outcome IN ('UPHELD', 'CHANGED')"
            " AND decided_by IS NOT NULL AND decided_at IS NOT NULL)",
            name=op.f("ck_appeals_decision"),
        ),
    )
    op.create_index(op.f("ix_appeals_claim_id"), "appeals", ["claim_id"], unique=False)
    # One open appeal per claim at a time.
    op.create_index(
        "uq_appeals_one_open_per_claim",
        "appeals",
        ["claim_id"],
        unique=True,
        postgresql_where=sa.text("status = 'OPEN'"),
    )

    op.add_column(
        "users", sa.Column("failed_logins", sa.Integer(), server_default="0", nullable=False)
    )
    op.add_column("users", sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "users", sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("users", "password_changed_at")
    op.drop_column("users", "locked_until")
    op.drop_column("users", "failed_logins")
    op.drop_index("uq_appeals_one_open_per_claim", table_name="appeals")
    op.drop_index(op.f("ix_appeals_claim_id"), table_name="appeals")
    op.drop_table("appeals")
    # audit_events is append-only (0001): rows of the new types already written stay; the old
    # check applies to new rows only (NOT VALID skips the existing ones).
    op.drop_constraint(op.f(CONSTRAINT), "audit_events", type_="check")
    op.execute(
        f"ALTER TABLE audit_events ADD CONSTRAINT {CONSTRAINT} CHECK ({_check(BEFORE)}) NOT VALID"
    )
