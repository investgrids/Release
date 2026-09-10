"""app/db/backup.py — atomic writes, always-runs pruning, split daily/boot
retention, and disk-usage logging. Covers the 2026-08-19 volume-full
incident's root causes directly: an unhandled copy failure used to skip
`_prune_old_backups()` entirely, and restart-triggered ("boot") backups
shared the same 14-file retention as the dated daily backups, so restarts
during active development accumulated far faster than "14 days" implied.

Pure file/sqlite3 I/O, no live app DB needed — isolates `_BACKUP_DIR` and
`_sqlite_path()` to a pytest tmp_path per test.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

import app.db.backup as backup_module
from app.db.backup import backup_database, last_backup_info


@pytest.fixture
def isolated_backup_env(tmp_path, monkeypatch):
    src_db = tmp_path / "ig.db"
    conn = sqlite3.connect(str(src_db))
    conn.execute("CREATE TABLE t (id INTEGER)")
    conn.commit()
    conn.close()

    backup_dir = tmp_path / "backups"
    monkeypatch.setattr(backup_module, "_BACKUP_DIR", backup_dir)
    monkeypatch.setattr(backup_module, "_sqlite_path", lambda: src_db)
    return {"src_db": src_db, "backup_dir": backup_dir}


def test_backup_daily_creates_dated_file(isolated_backup_env):
    result = backup_database(kind="daily")
    assert result["status"] == "ok"
    assert result["kind"] == "daily"
    dest = Path(result["path"])
    assert dest.exists()
    assert dest.name.startswith("ig-daily-")
    assert dest.stat().st_size > 0


def test_backup_boot_creates_timestamped_file(isolated_backup_env):
    result = backup_database(kind="boot")
    assert result["status"] == "ok"
    assert result["kind"] == "boot"
    dest = Path(result["path"])
    assert dest.exists()
    assert not dest.name.startswith("ig-daily-")


class _ExplodingConn:
    """Stands in for the destination connection so `.backup()` fails like a
    real disk-full mid-copy would — `sqlite3.Connection` is a C type and
    can't be monkeypatched directly, so this intercepts at `sqlite3.connect`
    instead, only for the `.tmp` destination path."""

    def backup(self, other):
        raise sqlite3.OperationalError("database or disk is full")

    def close(self):
        pass


def _connect_with_exploding_dest(monkeypatch):
    real_connect = sqlite3.connect

    def _fake_connect(path, *args, **kwargs):
        if str(path).endswith(".tmp"):
            return _ExplodingConn()
        return real_connect(path, *args, **kwargs)

    monkeypatch.setattr(backup_module.sqlite3, "connect", _fake_connect)


def test_failed_copy_leaves_no_partial_file(isolated_backup_env, monkeypatch):
    _connect_with_exploding_dest(monkeypatch)

    result = backup_database(kind="boot")
    assert result["status"] == "error"

    backup_dir = isolated_backup_env["backup_dir"]
    leftovers = list(backup_dir.glob("*"))
    assert leftovers == [], f"expected no files after a failed backup, found: {leftovers}"


def test_pruning_still_runs_after_a_failed_copy(isolated_backup_env, monkeypatch):
    """The exact incident bug: an unhandled copy failure must not skip
    pruning for that call — otherwise a retention bug and a disk-full
    failure compound each other. Retention itself is computed dynamically
    (see _max_backup_slots) from the real DB size — pinned here to a known
    value so this test verifies pruning-after-failure, not the sizing math
    (that's covered separately below).

    CR-0 (2026-09-10) note: under the pre-copy capacity guard, pruning now
    happens BEFORE the copy is attempted (reserving room for it), not only
    in the post-copy safety net — so on a real test machine with abundant
    free disk (the guard trivially passes), this scenario now prunes all
    the way down to retention-1 (0 boot backups, reserving the one slot
    for the incoming copy) BEFORE the injected failure. The pre-existing
    excess is still correctly pruned down to the safety-net's retention
    (1) by the always-runs _prune_old_backups() in `finally` — but since
    the pre-copy step already removed everything down to 0, there is
    nothing left for that safety net to act on, so the end state is 0, not
    1. This is an accepted, deliberate trade-off given real production
    numbers (see the capacity-guard tests below for the case that matters
    in practice: when pruning would NOT yield enough room, nothing is
    deleted at all)."""
    monkeypatch.setattr(backup_module, "_max_backup_slots", lambda: (4, 1))
    backup_dir = isolated_backup_env["backup_dir"]
    backup_dir.mkdir(parents=True)
    # Simulate stale excess boot backups already on disk, over retention.
    for i in range(6):
        (backup_dir / f"ig-2026010{i}T000000Z.db").write_bytes(b"x")

    _connect_with_exploding_dest(monkeypatch)
    backup_database(kind="boot")

    remaining = sorted(backup_dir.glob("ig-*.db"))
    assert len(remaining) == 0


def test_daily_and_boot_retention_are_independent(isolated_backup_env, monkeypatch):
    monkeypatch.setattr(backup_module, "_max_backup_slots", lambda: (4, 1))
    backup_dir = isolated_backup_env["backup_dir"]
    backup_dir.mkdir(parents=True)
    for i in range(20):
        (backup_dir / f"ig-daily-202601{i:02d}.db").write_bytes(b"x")
    for i in range(10):
        (backup_dir / f"ig-202601{i:02d}T000000Z.db").write_bytes(b"x")

    backup_module._prune_old_backups()

    daily_left = list(backup_dir.glob("ig-daily-*.db"))
    boot_left = [p for p in backup_dir.glob("ig-*.db") if not p.name.startswith("ig-daily-")]
    assert len(daily_left) == 4
    assert len(boot_left) == 1


def test_retention_shrinks_as_real_db_size_grows(isolated_backup_env, monkeypatch):
    """The actual 2026-08-26 incident: fixed retention counts went stale as
    the real DB grew, silently letting backups outgrow the volume. Retention
    must now shrink (never grow unboundedly) as the live DB gets bigger,
    without ever dropping below the real minimum (1 daily + 1 boot)."""
    src_db = isolated_backup_env["src_db"]

    monkeypatch.setattr(backup_module, "_VOLUME_TOTAL_BYTES", 500 * 1024 * 1024)
    src_db.write_bytes(b"x" * (10 * 1024 * 1024))  # small DB -> many slots fit
    daily_small, boot_small = backup_module._max_backup_slots()

    src_db.write_bytes(b"x" * (200 * 1024 * 1024))  # DB now most of the volume
    daily_large, boot_large = backup_module._max_backup_slots()

    assert daily_large < daily_small
    assert daily_large >= backup_module._MIN_DAILY_RETENTION
    assert boot_large >= backup_module._MIN_BOOT_RETENTION


def test_zero_byte_files_are_dropped_regardless_of_retention(isolated_backup_env):
    backup_dir = isolated_backup_env["backup_dir"]
    backup_dir.mkdir(parents=True)
    (backup_dir / "ig-20260101T000000Z.db").write_bytes(b"")
    (backup_dir / "ig-20260102T000000Z.db").write_bytes(b"real data")

    backup_module._prune_old_backups()

    remaining = list(backup_dir.glob("ig-*.db"))
    assert len(remaining) == 1
    assert remaining[0].name == "ig-20260102T000000Z.db"


def test_orphaned_tmp_files_are_cleaned_up(isolated_backup_env):
    backup_dir = isolated_backup_env["backup_dir"]
    backup_dir.mkdir(parents=True)
    (backup_dir / "ig-20260101T000000Z.db.tmp").write_bytes(b"partial")

    backup_module._prune_old_backups()

    assert list(backup_dir.glob("*.tmp")) == []


def test_orphaned_tmp_journal_siblings_are_cleaned_up(isolated_backup_env):
    """2026-08-31 production disk-recovery finding: sqlite3's own backup
    API leaves a *.tmp-journal sibling behind on an interrupted copy --
    production had ~80 of these accumulated since 2026-08-18 because the
    old glob ("*.tmp") never matched "*.tmp-journal"."""
    backup_dir = isolated_backup_env["backup_dir"]
    backup_dir.mkdir(parents=True)
    (backup_dir / "ig-20260101T000000Z.db.tmp-journal").write_bytes(b"stray journal")

    backup_module._prune_old_backups()

    assert list(backup_dir.glob("*.tmp-journal")) == []


def test_last_backup_info_finds_true_latest_across_kinds(isolated_backup_env):
    import os
    import time

    backup_dir = isolated_backup_env["backup_dir"]
    backup_dir.mkdir(parents=True)
    older = backup_dir / "ig-daily-20260101.db"
    newer = backup_dir / "ig-20260102T120000Z.db"
    older.write_bytes(b"x")
    time.sleep(0.01)
    newer.write_bytes(b"x")
    now = time.time()
    os.utime(older, (now - 100, now - 100))
    os.utime(newer, (now, now))

    info = last_backup_info()
    assert info["path"] == str(newer)
    assert info["kind"] == "boot"


def test_repeated_daily_backup_same_day_overwrites_not_accumulates(isolated_backup_env):
    backup_database(kind="daily")
    backup_database(kind="daily")

    backup_dir = isolated_backup_env["backup_dir"]
    daily_files = list(backup_dir.glob("ig-daily-*.db"))
    assert len(daily_files) == 1


def test_disk_usage_warning_does_not_fire_below_threshold(isolated_backup_env, monkeypatch):
    calls = []

    class _FakeUsage:
        total = 1000
        used = 500  # 50% — below the 75% warn threshold
        free = 500

    monkeypatch.setattr(backup_module.shutil, "disk_usage", lambda path: _FakeUsage())
    monkeypatch.setattr(backup_module.log, "warning", lambda *a, **kw: calls.append((a, kw)))

    backup_module._log_backup_disk_usage()

    assert calls == []


def test_disk_usage_warning_fires_above_threshold(isolated_backup_env, monkeypatch):
    calls = []

    class _FakeUsage:
        total = 1000
        used = 800  # 80% — above the 75% warn threshold
        free = 200

    monkeypatch.setattr(backup_module.shutil, "disk_usage", lambda path: _FakeUsage())
    monkeypatch.setattr(backup_module.log, "warning", lambda *a, **kw: calls.append((a, kw)))

    backup_module._log_backup_disk_usage()

    assert len(calls) == 1
    args, kwargs = calls[0]
    assert args[0] == "backup.disk_usage_high"
    assert kwargs["volume_used_pct"] == 80.0


# ── CR-0 (2026-09-10): pre-copy capacity guard + integrity check ───────────────
# Real incident: backup_database() used to prune old backups only AFTER
# attempting a new copy, so a copy needed live-DB + every existing same-kind
# backup + the new file simultaneously — stopped fitting once the live DB
# grew past ~280MB on the real 879MB production volume. These tests cover
# the fix: prune-before-copy (only when pruning would actually help), a hard
# fail-closed guard when it wouldn't, and a post-copy integrity check that
# refuses to ever report/keep a corrupt backup as successful.

def _fake_disk_usage(total, used):
    class _U:
        pass
    _U.total = total
    _U.used = used
    _U.free = total - used
    return _U()


def test_capacity_guard_skips_without_deleting_when_pruning_would_not_help(isolated_backup_env, monkeypatch):
    """The scenario that matters in practice: even after pruning this
    kind's excess down to reserve one slot, there still isn't comfortably
    enough room for the incoming copy. Nothing must be deleted in this
    case — the existing (possibly the only) backup of this kind must
    survive untouched, and the call must fail closed rather than attempt
    a copy likely to fail mid-write."""
    monkeypatch.setattr(backup_module, "_max_backup_slots", lambda: (1, 1))
    backup_dir = isolated_backup_env["backup_dir"]
    backup_dir.mkdir(parents=True)
    existing = backup_dir / "ig-20260101T000000Z.db"
    existing.write_bytes(b"x" * 1000)  # the one existing boot backup

    # The fixture's real src_db (a valid tiny SQLite file, ~8KB minimum
    # page size) is left untouched — required = its real size * 1.15,
    # comfortably larger than free(1 byte) + prunable(1000 bytes) below.
    src_db = isolated_backup_env["src_db"]
    required = int(src_db.stat().st_size * backup_module._REQUIRED_HEADROOM_FACTOR)
    assert required > 1001, "test setup assumption: real fixture DB is bigger than 1000-ish bytes"

    monkeypatch.setattr(backup_module.shutil, "disk_usage", lambda path: _fake_disk_usage(total=2000, used=1999))

    result = backup_database(kind="boot")

    assert result["status"] == "skipped"
    assert result["reason"] == "insufficient_disk_headroom"
    assert existing.exists(), "the existing backup must survive untouched when pruning wouldn't help"
    assert existing.stat().st_size == 1000


def test_capacity_guard_prunes_and_proceeds_when_pruning_would_be_enough(isolated_backup_env, monkeypatch):
    """When freeing this kind's excess WOULD create comfortable room, the
    guard must actually let the backup proceed — proves the guard isn't
    just conservative-to-the-point-of-useless."""
    monkeypatch.setattr(backup_module, "_max_backup_slots", lambda: (1, 1))
    backup_dir = isolated_backup_env["backup_dir"]
    backup_dir.mkdir(parents=True)
    existing = backup_dir / "ig-20260101T000000Z.db"
    existing.write_bytes(b"x" * 1000)

    result = backup_database(kind="boot")  # real disk_usage — plenty of real free space in tmp_path

    assert result["status"] == "ok"
    assert not existing.exists(), "the old same-kind backup should have been pruned to make room"
    dest = Path(result["path"])
    assert dest.exists()


def test_successful_backup_records_duration_and_free_space(isolated_backup_env):
    result = backup_database(kind="boot")
    assert result["status"] == "ok"
    assert result["quick_check"] == "ok"
    assert isinstance(result["duration_sec"], float)
    assert result["duration_sec"] >= 0
    assert isinstance(result["free_before_bytes"], int)
    assert isinstance(result["free_after_bytes"], int)


def test_corrupt_backup_fails_closed_never_renamed_into_place(isolated_backup_env, monkeypatch):
    """A backup nobody could restore from is worse than no backup at all —
    it looks fine sitting in the directory listing. If the freshly-written
    copy fails PRAGMA quick_check, it must be deleted, never renamed into
    place, and reported as an error, not a success."""
    real_connect = sqlite3.connect

    class _FakeCheckCursor:
        def execute(self, sql):
            return self

        def fetchone(self):
            return ("corruption detected",)

    class _FakeCheckConn:
        def cursor(self):
            return self

        def execute(self, sql):
            return _FakeCheckCursor()

        def close(self):
            pass

    def _fake_connect(path, *args, **kwargs):
        if isinstance(path, str) and path.startswith("file:") and "mode=ro" in path:
            return _FakeCheckConn()
        return real_connect(path, *args, **kwargs)

    monkeypatch.setattr(backup_module.sqlite3, "connect", _fake_connect)

    result = backup_database(kind="boot")

    assert result["status"] == "error"
    assert "quick_check failed" in result["error"]
    backup_dir = isolated_backup_env["backup_dir"]
    assert list(backup_dir.glob("ig-*.db")) == [], "a failed integrity check must never leave a renamed backup file"
    assert list(backup_dir.glob("*.tmp")) == [], "the failed tmp file must be cleaned up, not left behind"
