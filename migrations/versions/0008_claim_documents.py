"""claim documents (D-DOC-1)

The original file each claim was filed from (JSON, PDF, PNG or JPEG), so every role can see the
claim as it was sent: its sanitized file name, content type, size, SHA-256 and bytes. It reverses
the earlier note that uploaded files are never stored (D-RAG-3); a file refused at upload creates
no claim and is not kept.

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-13 12:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0008"
down_revision: str | Sequence[str] | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "claim_documents",
        sa.Column("claim_id", sa.String(length=48), nullable=False),
        sa.Column("file_name", sa.String(length=128), nullable=False),
        sa.Column("content_type", sa.String(length=32), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("content", sa.LargeBinary(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "content_type IN ('application/json', 'application/pdf', 'image/png', 'image/jpeg')",
            name=op.f("ck_claim_documents_content_type_allowed"),
        ),
        sa.CheckConstraint("sha256 ~ '^[0-9a-f]{64}$'", name=op.f("ck_claim_documents_sha256_hex")),
        sa.CheckConstraint("size_bytes > 0", name=op.f("ck_claim_documents_size_bytes_positive")),
        sa.ForeignKeyConstraint(
            ["claim_id"],
            ["claims.claim_id"],
            name=op.f("fk_claim_documents_claim_id_claims"),
        ),
        sa.PrimaryKeyConstraint("claim_id", name=op.f("pk_claim_documents")),
    )


def downgrade() -> None:
    op.drop_table("claim_documents")
