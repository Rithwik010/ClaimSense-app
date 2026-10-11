"""users and claim owners (D-AUTH-1)

Logins replace the prototype role header: a users table (Argon2 password hash, role, the provider
ID of a provider user, an active flag), and on each claim the provider ID and username of the
provider account that filed it, which decide whose claims a provider sees.

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-11 17:15:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0007"
down_revision: str | Sequence[str] | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("provider_id", sa.String(length=10), nullable=True),
        sa.Column("active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(role = 'provider') = (provider_id IS NOT NULL)",
            name=op.f("ck_users_provider_id_for_providers"),
        ),
        sa.CheckConstraint(
            "provider_id ~ '^[0-9]{10}$'", name=op.f("ck_users_provider_id_ten_digits")
        ),
        sa.CheckConstraint(
            "role IN ('provider', 'reviewer', 'admin')", name=op.f("ck_users_role_allowed")
        ),
        sa.PrimaryKeyConstraint("username", name=op.f("pk_users")),
    )
    op.add_column("claims", sa.Column("provider_id", sa.String(length=10), nullable=True))
    op.add_column("claims", sa.Column("filed_by", sa.String(length=64), nullable=True))
    op.create_index(op.f("ix_claims_provider_id"), "claims", ["provider_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_claims_provider_id"), table_name="claims")
    op.drop_column("claims", "filed_by")
    op.drop_column("claims", "provider_id")
    op.drop_table("users")
