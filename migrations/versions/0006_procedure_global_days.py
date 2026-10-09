"""procedure codes: PFS global days (P2.3c, R11 modifiers 25 and 57)

R11 lets modifier 25 bypass an NCCI edit only when the paired code's global period is 000, 010 or
XXX, and modifier 57 only when it is 090 (D-RULE-8; 2026 NCCI Policy Manual, pages I-13 and I-16).
The seed fills the column from the PFS RVU file.

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-09 19:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0006"
down_revision: str | Sequence[str] | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("procedure_codes", sa.Column("global_days", sa.String(length=3), nullable=True))


def downgrade() -> None:
    op.drop_column("procedure_codes", "global_days")
