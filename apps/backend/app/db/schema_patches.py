"""
Idempotent runtime schema patches.

This backend has no automated migration runner wired into its deploy path
(alembic exists but isn't invoked from the Dockerfile/Procfile/startup
sequence) — `Base.metadata.create_all()` only creates missing tables, it
never alters existing ones. New columns added to already-deployed tables
need an explicit, safe ADD COLUMN patch that runs on every boot and is a
no-op once applied. Keep this list small; anything structurally bigger
than "add a nullable-with-default column" belongs in a real migration.
"""
from __future__ import annotations

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

log = structlog.get_logger(__name__)

# (table, column, column_ddl_type_and_default)
_COLUMN_PATCHES: list[tuple[str, str, str]] = [
    ("ripple_graphs", "source", "VARCHAR(20) NOT NULL DEFAULT 'ai_generated'"),
    ("opportunities", "source", "VARCHAR(20) NOT NULL DEFAULT 'pipeline'"),
]


async def apply_schema_patches(conn: AsyncConnection) -> None:
    for table, column, ddl in _COLUMN_PATCHES:
        try:
            result = await conn.execute(text(f"PRAGMA table_info({table})"))
            existing_cols = {row[1] for row in result.fetchall()}
            if column in existing_cols:
                continue
            await conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))
            log.info("schema_patch.applied", table=table, column=column)
        except Exception as exc:
            # Table may not exist yet on a brand-new DB (create_all handles
            # that case with the column already in the model) — don't crash
            # startup over a patch that either doesn't apply yet or already landed.
            log.warning("schema_patch.skipped", table=table, column=column, error=str(exc)[:200])
