"""Add failure_reason to event_coverage

Revision ID: 0003
Revises: d6f90d12c6ca
Create Date: 2026-08-12
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "d6f90d12c6ca"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("event_coverage") as batch_op:
        batch_op.add_column(sa.Column("failure_reason", sa.String(256), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("event_coverage") as batch_op:
        batch_op.drop_column("failure_reason")
