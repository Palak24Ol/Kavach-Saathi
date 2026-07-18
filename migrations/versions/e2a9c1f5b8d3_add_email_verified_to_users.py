"""add email_verified to users

Revision ID: e2a9c1f5b8d3
Revises: b72f184ad630
Create Date: 2026-07-18 21:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e2a9c1f5b8d3"
down_revision: str | Sequence[str] | None = "b72f184ad630"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.alter_column("users", "email_verified", server_default=None)


def downgrade() -> None:
    op.drop_column("users", "email_verified")
