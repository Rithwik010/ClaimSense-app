"""member logins (D-MEM-1)

A member (a patient) logs in to see their own claims, explanations of benefits, benefits and
profile: the users table admits the role member, and a member user carries the member ID it is
linked to, a member on file (a foreign key to members); every other role has none, as only a
provider user has a provider ID.

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-19 23:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0011"
down_revision: str | Sequence[str] | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ROLES = "ck_users_role_allowed"
MEMBER_ID = "ck_users_member_id_for_members"
FOREIGN_KEY = "fk_users_member_id_members"


def _roles(roles: Sequence[str]) -> str:
    return "role IN (" + ", ".join(f"'{r}'" for r in roles) + ")"


def upgrade() -> None:
    op.add_column("users", sa.Column("member_id", sa.String(length=32), nullable=True))
    op.create_foreign_key(op.f(FOREIGN_KEY), "users", "members", ["member_id"], ["member_id"])
    op.drop_constraint(op.f(ROLES), "users", type_="check")
    op.create_check_constraint(
        op.f(ROLES), "users", _roles(("provider", "reviewer", "admin", "member"))
    )
    op.create_check_constraint(
        op.f(MEMBER_ID), "users", "(role = 'member') = (member_id IS NOT NULL)"
    )


def downgrade() -> None:
    # A member login cannot exist before 0011 (no role, no member ID): it goes with the column.
    op.execute("DELETE FROM users WHERE role = 'member'")
    op.drop_constraint(op.f(MEMBER_ID), "users", type_="check")
    op.drop_constraint(op.f(ROLES), "users", type_="check")
    op.create_check_constraint(op.f(ROLES), "users", _roles(("provider", "reviewer", "admin")))
    op.drop_constraint(op.f(FOREIGN_KEY), "users", type_="foreignkey")
    op.drop_column("users", "member_id")
