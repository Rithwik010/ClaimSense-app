"""billing articles' covered ICD-10-CM codes by group (P2.3b, R15)

R15 (D-DX-1, D-RULE-4) denies a line whose own diagnoses meet none of its code's billing-article
group combinations. The articles of the in-scope codes are loaded from the MCD current-article
download, with their source in reference_sources.

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-09 18:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0005"
down_revision: str | Sequence[str] | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "article_icd10_covered",
        sa.Column("article_id", sa.String(length=8), nullable=False),
        sa.Column("covered_group", sa.Integer(), nullable=False),
        sa.Column("icd10_code", sa.String(length=7), nullable=False),
        sa.Column("article_version", sa.String(length=8), nullable=False),
        sa.PrimaryKeyConstraint(
            "article_id", "covered_group", "icd10_code", name=op.f("pk_article_icd10_covered")
        ),
    )


def downgrade() -> None:
    op.drop_table("article_icd10_covered")
