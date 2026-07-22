"""Database health/status snapshot — backs both the startup log line and the
protected /api/admin/db-status endpoint. Branches on dialect rather than
assuming SQLite, so it stays meaningful across the planned SQLite ->
PostgreSQL migration instead of being thrown-away tooling.
"""
from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.config import settings
from app.db.backup import last_backup_info

# Counted directly, not via ORM, so this works the same across dialects.
_KEY_TABLES = ["intelligence_articles", "events", "opportunities"]


async def db_status(engine: AsyncEngine) -> dict:
    url = make_url(settings.database_url)
    is_sqlite = url.drivername.startswith("sqlite")

    status: dict = {"type": url.get_backend_name(), "driver": url.drivername}

    if is_sqlite and url.database:
        path = Path(url.database)
        status["path"] = str(path)
        status["persistent_volume"] = str(path).startswith("/data")
        status["file_size_bytes"] = path.stat().st_size if path.exists() else 0
        status["writable"] = os.access(path.parent, os.W_OK) if path.parent.exists() else False
    else:
        status["host"] = url.host
        status["database"] = url.database
        status["persistent_volume"] = True  # managed provider — provider-backed storage

    # Each check gets its own connection/transaction — a missing
    # alembic_version table (this app applies schema via create_all() +
    # patches, not `alembic upgrade`, so that table may not exist) must not
    # poison the connected/record-count checks that follow it.
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        status["connected"] = True
    except Exception as exc:
        status["connected"] = False
        status["connection_error"] = str(exc)

    status["migration_version"] = None
    if status["connected"]:
        try:
            async with engine.connect() as conn:
                rev = await conn.execute(text("SELECT version_num FROM alembic_version"))
                row = rev.first()
                status["migration_version"] = row[0] if row else None
        except Exception:
            pass  # no alembic_version table — schema isn't alembic-managed here

    counts: dict = {}
    if status["connected"]:
        for table in _KEY_TABLES:
            try:
                async with engine.connect() as conn:
                    r = await conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
                    counts[table] = r.scalar()
            except Exception:
                counts[table] = None
    status["record_counts"] = counts

    status["last_backup"] = last_backup_info()
    return status
