"""Initial schema

Revision ID: 0001
Revises:
Create Date: 2026-06-28

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "events",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("title", sa.String(256), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("impact_score", sa.Float(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("sectors", sa.JSON(), nullable=False),
        sa.Column("companies", sa.JSON(), nullable=False),
        sa.Column("category", sa.String(64), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_events_id", "events", ["id"])

    op.create_table(
        "news_articles",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("headline", sa.String(512), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("source", sa.String(128), nullable=False),
        sa.Column("published_at", sa.String(64), nullable=False),
        sa.Column("companies", sa.JSON(), nullable=False),
        sa.Column("impact_score", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "calendar_events",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("category", sa.String(64), nullable=False),
        sa.Column("title", sa.String(256), nullable=False),
        sa.Column("date", sa.String(64), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "radar_opportunities",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("theme", sa.String(256), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("beneficiaries", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "stories",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("title", sa.String(256), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("theme", sa.String(128), nullable=False),
        sa.Column("image", sa.String(512), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "sector_data",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("value", sa.String(16), nullable=False),
        sa.Column("positive", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("sector_data")
    op.drop_table("stories")
    op.drop_table("radar_opportunities")
    op.drop_table("calendar_events")
    op.drop_table("news_articles")
    op.drop_index("ix_events_id", "events")
    op.drop_table("events")
