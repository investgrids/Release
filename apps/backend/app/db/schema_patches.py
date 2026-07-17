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


async def relax_events_score_columns(engine) -> None:
    """
    One-time SQLite migration: `events.impact_score`/`confidence` were
    created NOT NULL by the original (pre-Scoring-Engine) schema — the
    Event model has declared them nullable=True for a while, but
    create_all() never alters an existing table, so the physical column
    stayed NOT NULL. That was harmless while every write path always
    supplied some number (even a fabricated fallback). It stopped being
    harmless the moment event_pipeline.py started honestly persisting
    `None` for insufficient_data events — the Scoring Engine's whole
    point — which now crashes with a NOT NULL constraint violation
    instead of storing the honest answer.

    SQLite has no ALTER COLUMN for constraints; relaxing NOT NULL requires
    the documented rebuild procedure (recreate the table, copy rows, swap
    names) — https://www.sqlite.org/lang_altertable.html#otheralter. Runs
    in its own connections deliberately separate from main.py's create_all
    transaction: `PRAGMA foreign_keys` is a no-op mid-transaction in
    SQLite, so toggling it needs an autocommit-mode connection, not the
    one already inside `engine.begin()`.

    Idempotent — checks PRAGMA table_info first and no-ops once already
    fixed (or if the table doesn't exist yet, or the engine isn't SQLite).
    """
    if engine.dialect.name != "sqlite":
        return

    check_conn = await engine.connect()
    check_conn = await check_conn.execution_options(isolation_level="AUTOCOMMIT")
    try:
        result = await check_conn.execute(text("PRAGMA table_info(events)"))
        cols = {row[1]: row for row in result.fetchall()}
        if not cols or cols["impact_score"][3] == 0:
            return  # table doesn't exist yet, or already fixed
        log.warning("schema_patch.events_notnull_rebuild.start")
        await check_conn.execute(text("PRAGMA foreign_keys=OFF"))
    finally:
        await check_conn.close()

    try:
        async with engine.begin() as conn:
            await conn.execute(text("ALTER TABLE events RENAME TO events_notnull_fix_tmp"))
            await conn.execute(text("""
                CREATE TABLE events (
                    id VARCHAR NOT NULL,
                    title VARCHAR(256) NOT NULL,
                    summary TEXT NOT NULL,
                    impact_score FLOAT,
                    confidence FLOAT,
                    sectors JSON NOT NULL,
                    companies JSON NOT NULL,
                    category VARCHAR(64),
                    published_at DATETIME,
                    slug VARCHAR(256),
                    description TEXT,
                    source VARCHAR(128),
                    event_type VARCHAR(64),
                    event_date DATETIME,
                    ai_summary JSON,
                    enrichment_status VARCHAR(32) DEFAULT 'pending' NOT NULL,
                    created_at DATETIME,
                    updated_at DATETIME,
                    PRIMARY KEY (id)
                )
            """))
            await conn.execute(text("""
                INSERT INTO events
                SELECT id, title, summary, impact_score, confidence, sectors,
                       companies, category, published_at, slug, description,
                       source, event_type, event_date, ai_summary,
                       enrichment_status, created_at, updated_at
                FROM events_notnull_fix_tmp
            """))
            await conn.execute(text("DROP TABLE events_notnull_fix_tmp"))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_events_id ON events (id)"))
    finally:
        restore_conn = await engine.connect()
        restore_conn = await restore_conn.execution_options(isolation_level="AUTOCOMMIT")
        try:
            await restore_conn.execute(text("PRAGMA foreign_keys=ON"))
        finally:
            await restore_conn.close()

    log.warning("schema_patch.events_notnull_rebuild.done")
