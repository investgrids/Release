"""Database backup — one call site (`backup_database`) meant to survive the
planned SQLite -> PostgreSQL migration. Today it snapshots the SQLite file;
once the app moves to Postgres, backups are the managed provider's job (or a
scheduled pg_dump added here), so that branch is a documented no-op rather
than SQLite-only tooling that gets thrown away.

Two backup "kinds" are tracked separately, because they answer different
questions and were getting conflated (the 2026-08-19 volume-full incident):
"daily" is the 2 AM cron, one file per calendar date, meant to answer "what
did the DB look like N days ago"; "boot" fires on every process restart
(deploys, crashes, local dev restarts) and only exists as a just-in-case
snapshot immediately before/after a restart — it has no reason to accumulate
like a dated history and gets a much smaller retention.
"""
from __future__ import annotations

import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import structlog
from sqlalchemy.engine import make_url

from app.core.config import settings

log = structlog.get_logger(__name__)

_BACKUP_DIR = Path("/data/backups")
# The Railway volume backing /data is 434MB real (not the 500MB shown in the
# dashboard), and each backup is a full ~49MB copy of the live DB — so
# retention has a hard ceiling here, not just a "how much history do we
# want" choice. 4 daily + 1 boot = 5 files (~245MB) keeps steady-state usage
# around 70%, under the 75% warn threshold below with the DB at its current
# size. Revisit these numbers if the DB grows materially or the volume is
# resized (Railway dashboard only — not exposed via the CLI).
_DAILY_RETENTION = 4  # one file per calendar date
_BOOT_RETENTION = 1  # restart-triggered snapshot; not a dated history

# Backup volume usage at/above this fraction gets a log.warning on every
# backup, so a slow refill (e.g. a retention bug) surfaces long before the
# disk actually fills — instead of only being visible once writes start
# failing.
_DISK_WARN_THRESHOLD = 0.75

_DAILY_PREFIX = "ig-daily-"


def _sqlite_path() -> Optional[Path]:
    url = make_url(settings.database_url)
    if not url.drivername.startswith("sqlite") or not url.database:
        return None
    return Path(url.database)


def backup_database(kind: str = "boot") -> dict:
    """Snapshot the database. Synchronous (file/sqlite3 I/O) — call via
    asyncio.to_thread from async contexts (e.g. the scheduler job).

    `kind` is "daily" (2 AM cron, dated retention) or "boot" (restart
    snapshot, short retention) — see module docstring.
    """
    db_path = _sqlite_path()
    if db_path is None:
        log.info("backup.skipped", reason="non-sqlite engine — use provider-managed backups")
        return {"status": "skipped", "reason": "non-sqlite engine"}

    if not db_path.exists():
        log.warning("backup.skipped", reason="db file not found", path=str(db_path))
        return {"status": "skipped", "reason": "db file not found"}

    _BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    if kind == "daily":
        stamp = now.strftime("%Y%m%d")
        dest = _BACKUP_DIR / f"{_DAILY_PREFIX}{stamp}.db"
    else:
        stamp = now.strftime("%Y%m%dT%H%M%SZ")
        dest = _BACKUP_DIR / f"ig-{stamp}.db"
    # Written under a .tmp name and only renamed onto the real name once the
    # copy fully succeeds — rename is atomic on the same filesystem, so a
    # partial/failed copy (e.g. disk full mid-write) can never leave a
    # zero-byte or truncated file at the real backup path.
    tmp_dest = dest.with_name(dest.name + ".tmp")

    try:
        # sqlite3's own backup API checkpoints WAL and copies consistently,
        # unlike a raw file copy racing a concurrent writer.
        src_conn = sqlite3.connect(str(db_path))
        dest_conn = sqlite3.connect(str(tmp_dest))
        try:
            src_conn.backup(dest_conn)
        finally:
            dest_conn.close()
            src_conn.close()
        tmp_dest.rename(dest)
        size = dest.stat().st_size
        log.info("backup.completed", path=str(dest), size_bytes=size, kind=kind)
        result = {"status": "ok", "path": str(dest), "size_bytes": size, "timestamp": stamp, "kind": kind}
    except Exception as exc:
        tmp_dest.unlink(missing_ok=True)
        log.error("backup.failed", error=str(exc), kind=kind)
        result = {"status": "error", "error": str(exc), "kind": kind}
    finally:
        # Always — a failed copy above must not skip pruning, or a retention
        # bug and a disk-full incident compound each other (this is exactly
        # how the 2026-08-19 volume-full incident happened: an unhandled
        # copy failure was silently skipping this call every time).
        _prune_old_backups()
        _log_backup_disk_usage()

    return result


def _prune_old_backups() -> None:
    # Orphaned .tmp files (process killed mid-copy, before the except
    # handler ran) are never valid backups regardless of age.
    for tmp in _BACKUP_DIR.glob("*.tmp"):
        tmp.unlink(missing_ok=True)

    all_backups = list(_BACKUP_DIR.glob("ig-*.db"))
    daily = sorted(p for p in all_backups if p.name.startswith(_DAILY_PREFIX))
    boot = sorted(p for p in all_backups if not p.name.startswith(_DAILY_PREFIX))
    _prune_category(daily, _DAILY_RETENTION)
    _prune_category(boot, _BOOT_RETENTION)


def _prune_category(backups: list[Path], retention: int) -> None:
    # Zero-byte files have no recovery value under any retention count —
    # drop them outright rather than letting them occupy a retention slot
    # that pushes out a real backup.
    kept = []
    for p in backups:
        try:
            if p.stat().st_size == 0:
                p.unlink(missing_ok=True)
                continue
        except FileNotFoundError:
            continue
        kept.append(p)

    excess = len(kept) - retention
    for old in kept[: max(excess, 0)]:
        old.unlink(missing_ok=True)


def _log_backup_disk_usage() -> None:
    total_backup_bytes = sum(p.stat().st_size for p in _BACKUP_DIR.glob("ig-*.db") if p.exists())
    try:
        usage = shutil.disk_usage(_BACKUP_DIR)
    except OSError:
        return
    used_pct = (usage.used / usage.total) if usage.total else 0.0
    log.info(
        "backup.disk_usage",
        total_backup_bytes=total_backup_bytes,
        volume_total_bytes=usage.total,
        volume_used_bytes=usage.used,
        volume_free_bytes=usage.free,
        volume_used_pct=round(used_pct * 100, 1),
    )
    if used_pct >= _DISK_WARN_THRESHOLD:
        log.warning(
            "backup.disk_usage_high",
            volume_used_pct=round(used_pct * 100, 1),
            volume_free_bytes=usage.free,
        )


def last_backup_info() -> Optional[dict]:
    if not _BACKUP_DIR.exists():
        return None
    backups = [p for p in _BACKUP_DIR.glob("ig-*.db")]
    if not backups:
        return None
    # Sorted by mtime, not filename — "ig-daily-" and "ig-<timestamp>" don't
    # share a lexical ordering, so filename sort doesn't reliably find the
    # most recent backup across both kinds.
    latest = max(backups, key=lambda p: p.stat().st_mtime)
    stat = latest.stat()
    return {
        "path": str(latest),
        "size_bytes": stat.st_size,
        "modified_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
        "count": len(backups),
        "kind": "daily" if latest.name.startswith(_DAILY_PREFIX) else "boot",
    }
