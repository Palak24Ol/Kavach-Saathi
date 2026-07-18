"""widen returns.refund_status

Revision ID: f7c4d8a1e6b2
Revises: e2a9c1f5b8d3
Create Date: 2026-07-18 21:15:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f7c4d8a1e6b2"
down_revision: str | Sequence[str] | None = "e2a9c1f5b8d3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # "awaiting_cod_refund_details" (28 chars) was already truncating against the
    # old String(24) column -- widened to match the schema's standard short-string
    # width rather than trimming the value.
    op.alter_column("returns", "refund_status", type_=sa.String(32), existing_type=sa.String(24))


def downgrade() -> None:
    op.alter_column("returns", "refund_status", type_=sa.String(24), existing_type=sa.String(32))
