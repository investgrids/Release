"""
Alembic migration regression tests (Phase 1 gap, 2026-08 audit: "Add
migration tests where appropriate" was verified manually in-session via a
one-off round-trip against a throwaway DB copy, but never turned into a
repeatable, automated check — this file closes that gap).

Every test here operates on an isolated COPY of the real dev DB, in a
pytest tmp_path, addressed via a DATABASE_URL environment override passed
to a fresh `alembic` subprocess. Two things make this the correct pattern
for this specific codebase, confirmed by hitting the wrong assumption
first:

1. `app.core.config.settings` is a module-level singleton that reads
   DATABASE_URL once at import time, and alembic/env.py unconditionally
   overwrites whatever URL a Config object was given with
   `settings.database_url` — so in-process monkeypatching or
   `Config.set_main_option` alone does NOT redirect alembic away from the
   real dev DB. A real environment variable, read by a fresh subprocess,
   does.

2. A truly empty/fresh SQLite file does NOT work as a migration-test
   starting point in this codebase: `alembic upgrade head` against an
   empty DB fails partway through migration 0001 (confirmed live —
   `OperationalError: no such table: main.intelligence_articles`, while
   creating an index on a table 0001 never creates). This is because
   `app/main.py`'s startup lifespan runs `Base.metadata.create_all()`
   BEFORE Alembic ever runs — migration 0001 was written as a delta
   against an already-`create_all()`'d database, not a from-scratch
   schema initializer. Production's real /data/ig.db has always gone
   through that same create_all()-then-migrate sequence, so this isn't a
   deployment blocker for THIS codebase — but it does mean the only
   representative migration-test starting point is a copy of a real,
   already-`create_all()`'d database, not an empty file. See
   test_fresh_empty_db_requires_create_all_before_alembic below, which
   pins this down explicitly rather than leaving it as tribal knowledge.
"""
from __future__ import annotations

import os
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
_PYTHON = _BACKEND_ROOT / ".venv" / "Scripts" / "python.exe"
_REAL_DEV_DB = _BACKEND_ROOT / "ig_dev.db"

# The revision immediately before this task's two migrations — production's
# real starting point per the task brief ("0003/0004 applied locally but
# NOT production").
_PRE_TASK_REVISION = "d6f90d12c6ca"


def _run_alembic(*args: str, db_path: Path, timeout: int = 60) -> subprocess.CompletedProcess:
    env = {**os.environ, "DATABASE_URL": f"sqlite+aiosqlite:///{db_path.as_posix()}"}
    return subprocess.run(
        [str(_PYTHON), "-m", "alembic", *args],
        cwd=str(_BACKEND_ROOT), env=env, capture_output=True, text=True, timeout=timeout,
    )


def _table_columns(db_path: Path, table: str) -> set[str]:
    conn = sqlite3.connect(db_path)
    try:
        return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
    finally:
        conn.close()


def _schema_snapshot(db_path: Path, tables: tuple[str, ...]) -> dict[str, list[tuple]]:
    conn = sqlite3.connect(db_path)
    try:
        return {
            t: sorted((r[1], r[2], r[3]) for r in conn.execute(f"PRAGMA table_info({t})"))
            for t in tables
        }
    finally:
        conn.close()


@pytest.fixture()
def real_db_copy(tmp_path: Path) -> Path:
    """A private copy of the real dev DB (already at head) — never the
    real file itself, so nothing here can disturb the live dev DB or the
    dev server that may be running against it."""
    if not _REAL_DEV_DB.exists():
        pytest.skip("ig_dev.db not present — nothing to copy for a migration test")
    dest = tmp_path / "migration_test.db"
    shutil.copy2(_REAL_DEV_DB, dest)
    return dest


def test_single_head_revision():
    # Read-only against migration script files, not any database — safe to
    # run with default settings, no isolation needed.
    result = subprocess.run(
        [str(_PYTHON), "-m", "alembic", "heads"],
        cwd=str(_BACKEND_ROOT), capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stderr
    heads = [line.split()[0] for line in result.stdout.strip().splitlines() if line.strip()]
    assert len(heads) == 1, f"Migration chain has diverged into multiple heads: {heads}"
    assert heads[0] == "0006"


def test_0003_adds_failure_reason_reversibly(real_db_copy: Path):
    assert "failure_reason" in _table_columns(real_db_copy, "event_coverage")

    result = _run_alembic("downgrade", _PRE_TASK_REVISION, db_path=real_db_copy)
    assert result.returncode == 0, result.stderr
    assert "failure_reason" not in _table_columns(real_db_copy, "event_coverage")

    result = _run_alembic("upgrade", "head", db_path=real_db_copy)
    assert result.returncode == 0, result.stderr
    assert "failure_reason" in _table_columns(real_db_copy, "event_coverage")


def test_0004_adds_retry_backoff_columns_reversibly(real_db_copy: Path):
    expected = {"retry_count", "last_attempt_at", "next_retry_at", "last_failure_reason"}
    assert expected <= _table_columns(real_db_copy, "events")

    result = _run_alembic("downgrade", "0003", db_path=real_db_copy)
    assert result.returncode == 0, result.stderr
    remaining = expected & _table_columns(real_db_copy, "events")
    assert not remaining, f"downgrade left columns behind: {remaining}"

    result = _run_alembic("upgrade", "head", db_path=real_db_copy)
    assert result.returncode == 0, result.stderr
    assert expected <= _table_columns(real_db_copy, "events")


def _table_exists(db_path: Path, table: str) -> bool:
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()
        return row is not None
    finally:
        conn.close()


def test_0005_adds_macro_releases_table_reversibly(real_db_copy: Path):
    assert _table_exists(real_db_copy, "macro_releases")
    expected_columns = {
        "id", "event_id", "metric", "release_value", "previous_value", "expected_value",
        "unit", "period", "geography", "importance", "affected_sectors", "affected_companies",
        "source", "source_url", "headline", "raw_summary", "release_date", "created_at",
    }
    assert expected_columns <= _table_columns(real_db_copy, "macro_releases")

    result = _run_alembic("downgrade", "0004", db_path=real_db_copy)
    assert result.returncode == 0, result.stderr
    assert not _table_exists(real_db_copy, "macro_releases")

    result = _run_alembic("upgrade", "head", db_path=real_db_copy)
    assert result.returncode == 0, result.stderr
    assert _table_exists(real_db_copy, "macro_releases")
    assert expected_columns <= _table_columns(real_db_copy, "macro_releases")


def test_full_roundtrip_preserves_schema_and_data(real_db_copy: Path):
    tables = ("events", "event_coverage")
    schema_before = _schema_snapshot(real_db_copy, tables)
    conn = sqlite3.connect(real_db_copy)
    try:
        events_before = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        coverage_before = conn.execute("SELECT COUNT(*) FROM event_coverage").fetchone()[0]
        oldest_event = conn.execute(
            "SELECT id, title, created_at FROM events ORDER BY created_at ASC LIMIT 1"
        ).fetchone()
    finally:
        conn.close()

    result = _run_alembic("downgrade", _PRE_TASK_REVISION, db_path=real_db_copy)
    assert result.returncode == 0, result.stderr
    result = _run_alembic("upgrade", "head", db_path=real_db_copy)
    assert result.returncode == 0, result.stderr

    schema_after = _schema_snapshot(real_db_copy, tables)
    assert schema_before == schema_after, "downgrade/upgrade round-trip changed table schema"

    conn = sqlite3.connect(real_db_copy)
    try:
        events_after = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        coverage_after = conn.execute("SELECT COUNT(*) FROM event_coverage").fetchone()[0]
        oldest_event_after = conn.execute(
            "SELECT id, title, created_at FROM events WHERE id = ?", (oldest_event[0],)
        ).fetchone()
    finally:
        conn.close()

    # SQLite batch-mode ALTER recreates the whole table under the hood on
    # every downgrade/upgrade — the real risk this test guards against is
    # silent row loss or corruption during that recreation, not (just) the
    # column list.
    assert events_after == events_before, "row count changed across round-trip"
    assert coverage_after == coverage_before, "row count changed across round-trip"
    assert oldest_event_after == oldest_event, "existing row data changed across round-trip"


def test_migrated_tables_columns_match_orm_models(real_db_copy: Path):
    """Scoped schema-drift check (Phase 1: 'verify no model/schema
    mismatch') — deliberately limited to the tables THIS task's migrations
    own (events/event_coverage via 0003/0004, macro_releases via 0005). A
    full-repo `alembic check` also flags pre-existing, unrelated drift
    (returning_user_feedback / ai_company_signals tables created only via
    app.main's startup create_all(), never migrated; a nullable mismatch
    on 4 intelligence_articles JSON columns) that belongs to other
    features and is explicitly out of scope to fix here — asserting
    against that would make this test permanently red for reasons this
    task didn't cause and shouldn't silently paper over by skipping the
    check entirely either."""
    from sqlalchemy import inspect as sa_inspect
    from sqlalchemy import create_engine

    sys.path.insert(0, str(_BACKEND_ROOT))
    from app.db.models.event import Event
    from app.db.models.event_coverage import EventCoverage
    from app.db.models.macro_release import MacroRelease

    engine = create_engine(f"sqlite:///{real_db_copy}")
    inspector = sa_inspect(engine)
    try:
        for model, table in (
            (Event, "events"), (EventCoverage, "event_coverage"), (MacroRelease, "macro_releases"),
        ):
            db_columns = {c["name"] for c in inspector.get_columns(table)}
            model_columns = {c.name for c in model.__table__.columns}
            missing_in_db = model_columns - db_columns
            extra_in_db = db_columns - model_columns
            assert not missing_in_db, f"{table}: model declares columns the DB doesn't have: {missing_in_db}"
            assert not extra_in_db, f"{table}: DB has columns the model doesn't declare: {extra_in_db}"
    finally:
        engine.dispose()


def test_fresh_empty_db_requires_create_all_before_alembic(tmp_path: Path):
    """Pins down the finding in this file's module docstring: migration
    0001 is a delta against an already-create_all()'d database, not a
    from-scratch initializer. Not a bug to fix (production's real
    /data/ig.db has always gone through create_all-then-migrate, matching
    every dev DB) — but worth an explicit, named regression guard so this
    stays a known, understood constraint rather than being silently
    "fixed" by a future migration-0001 rewrite that could desync from
    what's already been applied to the real production DB."""
    empty_db = tmp_path / "empty.db"
    result = _run_alembic("upgrade", "head", db_path=empty_db, timeout=30)
    assert result.returncode != 0
    assert "intelligence_articles" in result.stderr
