"""rule tables: NCCI rows keyed by a surrogate id and source order; reference provenance (P2.1)

The full NCCI PTP table repeats a (column 1, column 2, effective date) key in 261 rows, so
ncci_ptp_edits gets a surrogate id and keeps each row's position in the published files
(source_order), which decides the first edit active on a date. reference_sources records each
loaded table's source files and their SHA-256. ncci_ptp_edits was never loaded before this
revision, so it is recreated.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-05 12:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

INDICATOR_CHECK = "modifier_indicator IN ('0', '1', '9')"


def upgrade() -> None:
    op.drop_table("ncci_ptp_edits")
    op.create_table(
        "ncci_ptp_edits",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("column1_code", sa.String(length=5), nullable=False),
        sa.Column("column2_code", sa.String(length=5), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("deletion_date", sa.Date(), nullable=True),
        sa.Column("modifier_indicator", sa.String(length=1), nullable=False),
        sa.Column("source_order", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            INDICATOR_CHECK, name=op.f("ck_ncci_ptp_edits_modifier_indicator_allowed")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ncci_ptp_edits")),
    )
    op.create_index(
        op.f("ix_ncci_ptp_edits_pair"),
        "ncci_ptp_edits",
        ["column1_code", "column2_code"],
        unique=False,
    )
    op.create_table(
        "reference_sources",
        sa.Column("table_name", sa.String(length=64), nullable=False),
        sa.Column("source_path", sa.Text(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column(
            "loaded_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.PrimaryKeyConstraint("table_name", "source_path", name=op.f("pk_reference_sources")),
    )


def downgrade() -> None:
    op.drop_table("reference_sources")
    op.drop_index(op.f("ix_ncci_ptp_edits_pair"), table_name="ncci_ptp_edits")
    op.drop_table("ncci_ptp_edits")
    op.create_table(
        "ncci_ptp_edits",
        sa.Column("column1_code", sa.String(length=5), nullable=False),
        sa.Column("column2_code", sa.String(length=5), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("deletion_date", sa.Date(), nullable=True),
        sa.Column("modifier_indicator", sa.String(length=1), nullable=False),
        sa.CheckConstraint(
            INDICATOR_CHECK, name=op.f("ck_ncci_ptp_edits_modifier_indicator_allowed")
        ),
        sa.PrimaryKeyConstraint(
            "column1_code", "column2_code", "effective_date", name=op.f("pk_ncci_ptp_edits")
        ),
    )
