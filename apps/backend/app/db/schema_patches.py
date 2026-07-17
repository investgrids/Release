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


_EVENT_CHILD_TABLE_DDL: dict[str, str] = {
    "event_companies": """
        CREATE TABLE event_companies (
            id INTEGER NOT NULL,
            event_id VARCHAR NOT NULL,
            symbol VARCHAR(32) NOT NULL,
            name VARCHAR(256),
            impact_type VARCHAR(32) DEFAULT 'neutral' NOT NULL,
            impact_score FLOAT,
            reason TEXT,
            PRIMARY KEY (id),
            FOREIGN KEY(event_id) REFERENCES events (id) ON DELETE CASCADE
        )
    """,
    "event_sectors": """
        CREATE TABLE event_sectors (
            id INTEGER NOT NULL,
            event_id VARCHAR NOT NULL,
            sector VARCHAR(128) NOT NULL,
            impact VARCHAR(32) DEFAULT 'neutral' NOT NULL,
            impact_score FLOAT,
            PRIMARY KEY (id),
            FOREIGN KEY(event_id) REFERENCES events (id) ON DELETE CASCADE
        )
    """,
    "event_timeline": """
        CREATE TABLE event_timeline (
            id INTEGER NOT NULL,
            event_id VARCHAR NOT NULL,
            date VARCHAR(64),
            title VARCHAR(256) NOT NULL,
            description TEXT,
            "order" INTEGER DEFAULT 0 NOT NULL,
            PRIMARY KEY (id),
            FOREIGN KEY(event_id) REFERENCES events (id) ON DELETE CASCADE
        )
    """,
    "event_news": """
        CREATE TABLE event_news (
            id INTEGER NOT NULL,
            event_id VARCHAR NOT NULL,
            news_id VARCHAR NOT NULL,
            relevance_score FLOAT,
            PRIMARY KEY (id),
            FOREIGN KEY(event_id) REFERENCES events (id) ON DELETE CASCADE,
            FOREIGN KEY(news_id) REFERENCES news_articles (id) ON DELETE CASCADE,
            CONSTRAINT uq_event_news UNIQUE (event_id, news_id)
        )
    """,
    "event_graph_nodes": """
        CREATE TABLE event_graph_nodes (
            id INTEGER NOT NULL,
            event_id VARCHAR NOT NULL,
            node_id VARCHAR(64) NOT NULL,
            label VARCHAR(256) NOT NULL,
            node_type VARCHAR(64) DEFAULT 'entity' NOT NULL,
            node_metadata JSON,
            PRIMARY KEY (id),
            FOREIGN KEY(event_id) REFERENCES events (id) ON DELETE CASCADE
        )
    """,
    "event_graph_edges": """
        CREATE TABLE event_graph_edges (
            id INTEGER NOT NULL,
            event_id VARCHAR NOT NULL,
            source VARCHAR(64) NOT NULL,
            target VARCHAR(64) NOT NULL,
            edge_relationship VARCHAR(128) DEFAULT 'impacts' NOT NULL,
            PRIMARY KEY (id),
            FOREIGN KEY(event_id) REFERENCES events (id) ON DELETE CASCADE
        )
    """,
    "event_similar": """
        CREATE TABLE event_similar (
            id INTEGER NOT NULL,
            event_id VARCHAR NOT NULL,
            similar_event_id VARCHAR NOT NULL,
            similarity_score FLOAT,
            reason TEXT,
            PRIMARY KEY (id),
            FOREIGN KEY(event_id) REFERENCES events (id) ON DELETE CASCADE,
            FOREIGN KEY(similar_event_id) REFERENCES events (id) ON DELETE CASCADE
        )
    """,
    "event_policies": """
        CREATE TABLE event_policies (
            id INTEGER NOT NULL,
            event_id VARCHAR NOT NULL,
            policy_id INTEGER NOT NULL,
            relevance VARCHAR(128) DEFAULT 'relevant',
            PRIMARY KEY (id),
            FOREIGN KEY(event_id) REFERENCES events (id) ON DELETE CASCADE,
            FOREIGN KEY(policy_id) REFERENCES government_policies (id) ON DELETE CASCADE,
            CONSTRAINT uq_event_policy UNIQUE (event_id, policy_id)
        )
    """,
}


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
    names) — https://www.sqlite.org/lang_altertable.html#otheralter.

    IMPORTANT ordering gotcha this function works around: `ALTER TABLE
    events RENAME TO x` does NOT just rename `events` — SQLite also
    silently rewrites every OTHER table's stored FOREIGN KEY clause that
    referenced `events` to reference `x` instead. Renaming a table AWAY
    from a name while 8 child tables (event_companies, event_sectors, ...)
    still hold live FK references to that name poisons all 8 of them
    permanently, even after the real `events` table exists again under
    its original name. The safe order is the opposite: build the fixed
    table under a name nothing references yet, drop the original outright
    (a plain DROP does not rewrite anything), then rename the new table
    *into* the vacated name — a rename that nothing currently points at,
    so it rewrites nothing.

    This function also detects and repairs the specific corruption an
    earlier (buggy) version of this migration could have left behind, by
    checking each child table's stored SQL for a stale reference and, if
    found, rebuilding just that table (safe to rename-away-from directly,
    since nothing holds an FK *into* a leaf table like event_companies).

    Runs in its own connections deliberately separate from main.py's
    create_all transaction: `PRAGMA foreign_keys` is a no-op mid-transaction
    in SQLite, so toggling it needs an autocommit-mode connection.

    Idempotent — checks table state first and no-ops once everything is
    already correct (or if the table doesn't exist yet, or the engine
    isn't SQLite).
    """
    if engine.dialect.name != "sqlite":
        return

    _STALE_MARKER = "events_notnull_fix_tmp"

    check_conn = await engine.connect()
    check_conn = await check_conn.execution_options(isolation_level="AUTOCOMMIT")
    try:
        result = await check_conn.execute(text("PRAGMA table_info(events)"))
        cols = {row[1]: row for row in result.fetchall()}
        if not cols:
            return  # brand-new DB — create_all already made this table correctly
        needs_notnull_fix = cols["impact_score"][3] == 1

        corrupted_children = []
        for t in _EVENT_CHILD_TABLE_DDL:
            row = (await check_conn.execute(
                text("SELECT sql FROM sqlite_master WHERE type='table' AND name=:t"),
                {"t": t},
            )).fetchone()
            if row and row[0] and _STALE_MARKER in row[0]:
                corrupted_children.append(t)

        if not needs_notnull_fix and not corrupted_children:
            return

        log.warning(
            "schema_patch.events_notnull_rebuild.start",
            needs_notnull_fix=needs_notnull_fix, corrupted_children=corrupted_children,
        )
        await check_conn.execute(text("PRAGMA foreign_keys=OFF"))
    finally:
        await check_conn.close()

    try:
        async with engine.begin() as conn:
            if needs_notnull_fix:
                await conn.execute(text("""
                    CREATE TABLE events_rebuilt (
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
                    INSERT INTO events_rebuilt
                    SELECT id, title, summary, impact_score, confidence, sectors,
                           companies, category, published_at, slug, description,
                           source, event_type, event_date, ai_summary,
                           enrichment_status, created_at, updated_at
                    FROM events
                """))
                await conn.execute(text("DROP TABLE events"))
                await conn.execute(text("ALTER TABLE events_rebuilt RENAME TO events"))
                await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_events_id ON events (id)"))

            # event_companies etc. are leaf tables — nothing holds an FK into
            # them, so renaming one of *them* away is safe (unlike `events`).
            for t in corrupted_children:
                await conn.execute(text(f"ALTER TABLE {t} RENAME TO {t}_corrupted"))
                await conn.execute(text(_EVENT_CHILD_TABLE_DDL[t]))
                cols_row = await conn.execute(text(f"PRAGMA table_info({t}_corrupted)"))
                col_names = ", ".join(f'"{r[1]}"' if r[1] == "order" else r[1] for r in cols_row.fetchall())
                await conn.execute(text(f"INSERT INTO {t} SELECT {col_names} FROM {t}_corrupted"))
                await conn.execute(text(f"DROP TABLE {t}_corrupted"))
    finally:
        restore_conn = await engine.connect()
        restore_conn = await restore_conn.execution_options(isolation_level="AUTOCOMMIT")
        try:
            await restore_conn.execute(text("PRAGMA foreign_keys=ON"))
            violations = (await restore_conn.execute(text("PRAGMA foreign_key_check"))).fetchall()
            if violations:
                log.error("schema_patch.events_notnull_rebuild.fk_violations", violations=str(violations)[:500])
        finally:
            await restore_conn.close()

    log.warning("schema_patch.events_notnull_rebuild.done")
