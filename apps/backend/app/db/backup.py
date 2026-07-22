"""Database backup — one call site (`backup_database`) meant to survive the
planned SQLite -> PostgreSQL migration. Today it snapshots the SQLite file;
once the app moves to Postgres, backups are the managed provider's job (or a
scheduled pg_dump added here), so that branch is a documented no-op rather
than SQLite-only tooling that gets thrown away.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import structlog
from sqlalchemy.engine import make_url

from app.core.config import settings

log = structlog.get_logger(__name__)

_BACKUP_DIR = Path("/data/backups")
_RETENTION = 14  # keep the last N daily backups


def _sqlite_path() -> Optional[Path]:
    url = make_url(settings.database_url)
    if not url.drivername.startswith("sqlite") or not url.database:
        return None
    return Path(url.database)


def backup_database() -> dict:
    """Snapshot the database. Synchronous (file/sqlite3 I/O) — call via
    asyncio.to_thread from async contexts (e.g. the scheduler job)."""
    db_path = _sqlite_path()
    if db_path is None:
        log.info("backup.skipped", reason="non-sqlite engine — use provider-managed backups")
        return {"status": "skipped", "reason": "non-sqlite engine"}

    if not db_path.exists():
        log.warning("backup.skipped", reason="db file not found", path=str(db_path))
        return {"status": "skipped", "reason": "db file not found"}

    _BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest = _BACKUP_DIR / f"ig-{stamp}.db"

    # sqlite3's own backup API checkpoints WAL and copies consistently,
    # unlike a raw file copy racing a concurrent writer.
    src_conn = sqlite3.connect(str(db_path))
    dest_conn = sqlite3.connect(str(dest))
    try:
        src_conn.backup(dest_conn)
    finally:
        dest_conn.close()
        src_conn.close()

    _prune_old_backups()
    size = dest.stat().st_size
    log.info("backup.completed", path=str(dest), size_bytes=size)
    return {"status": "ok", "path": str(dest), "size_bytes": size, "timestamp": stamp}


def _prune_old_backups() -> None:
    backups = sorted(_BACKUP_DIR.glob("ig-*.db"))
    excess = len(backups) - _RETENTION
    for old in backups[:excess]:
        old.unlink(missing_ok=True)


def last_backup_info() -> Optional[dict]:
    if not _BACKUP_DIR.exists():
        return None
    backups = sorted(_BACKUP_DIR.glob("ig-*.db"))
    if not backups:
        return None
    latest = backups[-1]
    stat = latest.stat()
    return {
        "path": str(latest),
        "size_bytes": stat.st_size,
        "modified_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
        "count": len(backups),
    }
