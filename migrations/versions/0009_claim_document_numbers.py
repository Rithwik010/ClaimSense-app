"""claim documents numbered (D-DOC-2)

A claim filed from its form's pages in several files keeps every file: `file_no` (1, 2, ... in
page order) joins the claim ID in the key of `claim_documents`. Files kept before have number 1.

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-15 10:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0009"
down_revision: str | Sequence[str] | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "claim_documents",
        sa.Column("file_no", sa.Integer(), server_default="1", nullable=False),
    )
    op.alter_column("claim_documents", "file_no", server_default=None)
    op.drop_constraint(op.f("pk_claim_documents"), "claim_documents", type_="primary")
    op.create_primary_key(op.f("pk_claim_documents"), "claim_documents", ["claim_id", "file_no"])
    op.create_check_constraint(
        op.f("ck_claim_documents_file_no_positive"), "claim_documents", "file_no >= 1"
    )


def downgrade() -> None:
    op.execute("DELETE FROM claim_documents WHERE file_no > 1")
    op.drop_constraint(
        op.f("ck_claim_documents_file_no_positive"), "claim_documents", type_="check"
    )
    op.drop_constraint(op.f("pk_claim_documents"), "claim_documents", type_="primary")
    op.create_primary_key(op.f("pk_claim_documents"), "claim_documents", ["claim_id"])
    op.drop_column("claim_documents", "file_no")
