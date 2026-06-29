"""Add event detail tables and extend events table

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-29
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Extend existing events table ─────────────────────────────────────────
    with op.batch_alter_table("events") as batch_op:
        batch_op.add_column(sa.Column("slug", sa.String(256), nullable=True))
        batch_op.add_column(sa.Column("description", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("source", sa.String(128), nullable=True))
        batch_op.add_column(sa.Column("event_type", sa.String(64), nullable=True))
        batch_op.add_column(sa.Column("event_date", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("ai_summary", sa.JSON(), nullable=True))
        batch_op.add_column(
            sa.Column(
                "enrichment_status",
                sa.String(32),
                nullable=False,
                server_default="pending",
            )
        )
        batch_op.add_column(sa.Column("created_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True))

    # ── event_companies ───────────────────────────────────────────────────────
    op.create_table(
        "event_companies",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "event_id",
            sa.String(),
            sa.ForeignKey("events.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("name", sa.String(256), nullable=True),
        sa.Column("impact_type", sa.String(32), nullable=False, server_default="neutral"),
        sa.Column("impact_score", sa.Float(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
    )
    op.create_index("ix_event_companies_event_id", "event_companies", ["event_id"])

    # ── event_sectors ─────────────────────────────────────────────────────────
    op.create_table(
        "event_sectors",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "event_id",
            sa.String(),
            sa.ForeignKey("events.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sector", sa.String(128), nullable=False),
        sa.Column("impact", sa.String(32), nullable=False, server_default="neutral"),
        sa.Column("impact_score", sa.Float(), nullable=True),
    )
    op.create_index("ix_event_sectors_event_id", "event_sectors", ["event_id"])

    # ── event_timeline ────────────────────────────────────────────────────────
    op.create_table(
        "event_timeline",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "event_id",
            sa.String(),
            sa.ForeignKey("events.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("date", sa.String(64), nullable=True),
        sa.Column("title", sa.String(256), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("order", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_event_timeline_event_id", "event_timeline", ["event_id"])

    # ── event_news ────────────────────────────────────────────────────────────
    op.create_table(
        "event_news",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "event_id",
            sa.String(),
            sa.ForeignKey("events.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "news_id",
            sa.String(),
            sa.ForeignKey("news_articles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("relevance_score", sa.Float(), nullable=True, server_default="1.0"),
        sa.UniqueConstraint("event_id", "news_id", name="uq_event_news"),
    )
    op.create_index("ix_event_news_event_id", "event_news", ["event_id"])

    # ── event_graph_nodes ─────────────────────────────────────────────────────
    op.create_table(
        "event_graph_nodes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "event_id",
            sa.String(),
            sa.ForeignKey("events.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("node_id", sa.String(64), nullable=False),
        sa.Column("label", sa.String(256), nullable=False),
        sa.Column("node_type", sa.String(64), nullable=False, server_default="entity"),
        sa.Column("node_metadata", sa.JSON(), nullable=True),
    )
    op.create_index("ix_event_graph_nodes_event_id", "event_graph_nodes", ["event_id"])

    # ── event_graph_edges ─────────────────────────────────────────────────────
    op.create_table(
        "event_graph_edges",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "event_id",
            sa.String(),
            sa.ForeignKey("events.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("target", sa.String(64), nullable=False),
        sa.Column("edge_relationship", sa.String(128), nullable=False, server_default="impacts"),
    )
    op.create_index("ix_event_graph_edges_event_id", "event_graph_edges", ["event_id"])

    # ── event_similar ─────────────────────────────────────────────────────────
    op.create_table(
        "event_similar",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "event_id",
            sa.String(),
            sa.ForeignKey("events.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "similar_event_id",
            sa.String(),
            sa.ForeignKey("events.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("similarity_score", sa.Float(), nullable=True, server_default="0.0"),
        sa.Column("reason", sa.Text(), nullable=True),
    )
    op.create_index("ix_event_similar_event_id", "event_similar", ["event_id"])

    # ── government_policies ───────────────────────────────────────────────────
    op.create_table(
        "government_policies",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("external_id", sa.String(128), nullable=False, unique=True),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("ministry", sa.String(256), nullable=True),
        sa.Column("announcement_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("url", sa.String(512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_government_policies_external_id", "government_policies", ["external_id"], unique=True)

    # ── event_policies ────────────────────────────────────────────────────────
    op.create_table(
        "event_policies",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "event_id",
            sa.String(),
            sa.ForeignKey("events.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "policy_id",
            sa.Integer(),
            sa.ForeignKey("government_policies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("relevance", sa.String(128), nullable=True, server_default="relevant"),
        sa.UniqueConstraint("event_id", "policy_id", name="uq_event_policy"),
    )
    op.create_index("ix_event_policies_event_id", "event_policies", ["event_id"])


def downgrade() -> None:
    op.drop_table("event_policies")
    op.drop_table("government_policies")
    op.drop_table("event_similar")
    op.drop_table("event_graph_edges")
    op.drop_table("event_graph_nodes")
    op.drop_table("event_news")
    op.drop_table("event_timeline")
    op.drop_table("event_sectors")
    op.drop_table("event_companies")

    with op.batch_alter_table("events") as batch_op:
        batch_op.drop_column("updated_at")
        batch_op.drop_column("created_at")
        batch_op.drop_column("enrichment_status")
        batch_op.drop_column("ai_summary")
        batch_op.drop_column("event_date")
        batch_op.drop_column("event_type")
        batch_op.drop_column("source")
        batch_op.drop_column("description")
        batch_op.drop_column("slug")
