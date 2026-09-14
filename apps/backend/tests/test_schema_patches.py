"""
Runtime schema patches (`app/db/schema_patches.py`) — regression tests
against an EXISTING, already-populated database shape, not merely a
fresh `create_all()` database.

`create_all()` only ever creates MISSING tables; it never alters an
existing one (see schema_patches.py's own module docstring). Every
column added to an already-deployed table therefore depends entirely on
`apply_schema_patches()` actually running the right `ALTER TABLE ADD
COLUMN` against a real, pre-existing table that predates that column --
a scenario this test file did not previously exercise for any entry in
`_COLUMN_PATCHES`, for any table, ever (a real, general test gap, not
specific to any one column). This file closes that gap using
`key_facts` (Article V2-F1 Data Contract Completion, 2026-09-14) as the
concrete case, simulating a genuinely pre-migration table via SQLite's
own `ALTER TABLE ... DROP COLUMN` (supported since SQLite 3.35) rather
than hand-writing a parallel CREATE TABLE DDL that could silently drift
from the real model.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.db.base import Base
from app.db.schema_patches import apply_schema_patches


@pytest.mark.asyncio
async def test_key_facts_column_is_added_to_an_existing_pre_migration_table():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "pre_migration.db"
        engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
        try:
            async with engine.begin() as conn:
                # A real, fully-current schema (create_all() creates
                # key_facts too, since the model already declares it) --
                # then simulate a genuinely pre-migration table by
                # dropping exactly the one column under test, rather than
                # hand-writing a parallel DDL that could drift from the
                # real model.
                await conn.run_sync(Base.metadata.create_all)
                await conn.execute(text("ALTER TABLE intelligence_articles DROP COLUMN key_facts"))

            async with engine.begin() as conn:
                result = await conn.execute(text("PRAGMA table_info(intelligence_articles)"))
                cols_before = {row[1] for row in result.fetchall()}
                assert "key_facts" not in cols_before, "test setup failed to simulate a pre-migration table"

            async with engine.begin() as conn:
                await apply_schema_patches(conn)

            async with engine.begin() as conn:
                result = await conn.execute(text("PRAGMA table_info(intelligence_articles)"))
                cols_after = {row[1]: row for row in result.fetchall()}
                assert "key_facts" in cols_after, "apply_schema_patches() must add key_facts to an existing table"

            # A raw SQL insert (deliberately NOT through the ORM, which
            # would supply its own Python-side default=list for
            # key_facts regardless of whether the migration's DB-level
            # DEFAULT clause works at all) omitting key_facts entirely --
            # every OTHER NOT NULL column gets a type-appropriate dummy
            # value, discovered from the real schema rather than
            # hand-maintained, so this doesn't silently drift as the
            # model gains new required columns over time.
            async with engine.begin() as conn:
                result = await conn.execute(text("PRAGMA table_info(intelligence_articles)"))
                dummy_by_type = {"VARCHAR": "'x'", "TEXT": "'x'", "INTEGER": "0", "BOOLEAN": "0", "FLOAT": "0.0", "JSON": "'[]'"}
                cols, vals = ["id", "headline"], ["'test-row-1'", "'Test Headline'"]
                for _, name, col_type, notnull, dflt, _pk in result.fetchall():
                    if name in cols or name == "key_facts" or not notnull or dflt is not None:
                        continue
                    base_type = next((t for t in dummy_by_type if col_type.upper().startswith(t)), None)
                    assert base_type is not None, f"no dummy value mapped for column {name} ({col_type})"
                    cols.append(name)
                    vals.append(dummy_by_type[base_type])
                await conn.execute(text(f"INSERT INTO intelligence_articles ({', '.join(cols)}) VALUES ({', '.join(vals)})"))

            async with engine.begin() as conn:
                row = (await conn.execute(text(
                    "SELECT key_facts FROM intelligence_articles WHERE id = 'test-row-1'"
                ))).first()
                assert row[0] == "[]", "the migration's own DEFAULT '[]' clause must backfill a raw insert that omits the column"

            async with engine.begin() as conn:
                # Idempotent re-run — must not error on a column that
                # already exists (the real production boot path calls
                # this on every single startup, not just once).
                await apply_schema_patches(conn)
        finally:
            await engine.dispose()


@pytest.mark.asyncio
async def test_apply_schema_patches_is_a_no_op_on_a_fresh_database():
    """The complementary case: a brand-new database where create_all()
    already produced every column apply_schema_patches() would otherwise
    add -- must not error, must not duplicate anything."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "fresh.db"
        engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            async with engine.begin() as conn:
                await apply_schema_patches(conn)  # must not raise
            async with engine.begin() as conn:
                result = await conn.execute(text("PRAGMA table_info(intelligence_articles)"))
                cols = {row[1] for row in result.fetchall()}
                assert "key_facts" in cols
        finally:
            await engine.dispose()
