"""Add macro_releases table

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-13
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "macro_releases",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("event_id", sa.String(), nullable=True),
        sa.Column("metric", sa.String(length=32), nullable=False),
        sa.Column("release_value", sa.Float(), nullable=True),
        sa.Column("previous_value", sa.Float(), nullable=True),
        sa.Column("expected_value", sa.Float(), nullable=True),
        sa.Column("unit", sa.String(length=16), nullable=True),
        sa.Column("period", sa.String(length=32), nullable=True),
        sa.Column("geography", sa.String(length=32), nullable=False, server_default="India"),
        sa.Column("importance", sa.String(length=16), nullable=True),
        sa.Column("affected_sectors", sa.JSON(), nullable=False),
        sa.Column("affected_companies", sa.JSON(), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("headline", sa.Text(), nullable=False),
        sa.Column("raw_summary", sa.Text(), nullable=True),
        sa.Column("release_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("macro_releases") as batch_op:
        batch_op.create_index("ix_macro_releases_event_id", ["event_id"])
        batch_op.create_index("ix_macro_releases_metric", ["metric"])
        batch_op.create_index("ix_macro_releases_created_at", ["created_at"])


def downgrade() -> None:
    with op.batch_alter_table("macro_releases") as batch_op:
        batch_op.drop_index("ix_macro_releases_created_at")
        batch_op.drop_index("ix_macro_releases_metric")
        batch_op.drop_index("ix_macro_releases_event_id")
    op.drop_table("macro_releases")
