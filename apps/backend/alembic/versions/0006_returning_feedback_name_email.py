"""Add name/email to returning_user_feedback

Revision ID: 0006
Revises: 0005
Create Date: 2026-08-13
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("returning_user_feedback") as batch_op:
        batch_op.add_column(sa.Column("name", sa.String(128), nullable=True))
        batch_op.add_column(sa.Column("email", sa.String(320), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("returning_user_feedback") as batch_op:
        batch_op.drop_column("email")
        batch_op.drop_column("name")
