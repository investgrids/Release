"""app/tasks/daily_tasks.py::job_backup_database_boot — orchestration
between the same-volume local backup (app.db.backup) and the off-volume
remote backup (app.db.remote_backup). CR-1 (2026-09-20): a real incident
where a volume-resize dashboard session caused 3 restarts in under 5
minutes, each leaving a ~400MB local staging copy behind with no cleanup
path except the NEXT restart's pre-copy pruning.

These tests mock both backup_database and backup_to_bucket at the module
level (app.db.backup / app.db.remote_backup) so job_backup_database_boot's
own reconciliation logic — cleanup-on-verified, retain-on-failure, and the
rate-limit gate — is exercised in isolation from real file/network I/O,
which the two underlying modules' own test suites already cover directly.
"""
from __future__ import annotations

import pytest

import app.db.backup as backup_module
from app.tasks.daily_tasks import job_backup_database_boot


def _local_ok(path="/data/backups/ig-20260101T000000Z.db"):
    return {"status": "ok", "path": path, "size_bytes": 1000, "kind": "boot"}


def _remote_verified(object_key="automated/boot/ig-20260101T000000Z.db"):
    return {"status": "ok", "kind": "boot", "object_key": object_key, "remote_verified": True, "cleanup_complete": True}


@pytest.fixture
def no_rate_limit(monkeypatch):
    monkeypatch.setattr(backup_module, "boot_backup_recently_verified", lambda: False)


@pytest.mark.asyncio
async def test_success_cleans_up_local_copy_and_records_verification(monkeypatch, no_rate_limit):
    cleanup_calls = []
    record_calls = []
    monkeypatch.setattr(backup_module, "backup_database", lambda kind: _local_ok())
    monkeypatch.setattr(backup_module, "cleanup_local_copy", lambda path: (cleanup_calls.append(path), {"status": "ok", "path": path, "removed": [path]})[1])
    monkeypatch.setattr(backup_module, "record_boot_backup_verified", lambda: record_calls.append(True))

    import app.db.remote_backup as remote_backup_module
    monkeypatch.setattr(remote_backup_module, "backup_to_bucket", lambda kind: _remote_verified())

    await job_backup_database_boot()

    assert cleanup_calls == ["/data/backups/ig-20260101T000000Z.db"]
    assert record_calls == [True]


@pytest.mark.asyncio
async def test_upload_failure_retains_local_copy(monkeypatch, no_rate_limit):
    cleanup_calls = []
    record_calls = []
    monkeypatch.setattr(backup_module, "backup_database", lambda kind: _local_ok())
    monkeypatch.setattr(backup_module, "cleanup_local_copy", lambda path: cleanup_calls.append(path))
    monkeypatch.setattr(backup_module, "record_boot_backup_verified", lambda: record_calls.append(True))

    import app.db.remote_backup as remote_backup_module
    monkeypatch.setattr(
        remote_backup_module, "backup_to_bucket",
        lambda kind: {"status": "error", "error": "upload_complete_but_no_head", "kind": "boot"},
    )

    await job_backup_database_boot()

    assert cleanup_calls == [], "local copy must be retained when the remote upload fails"
    assert record_calls == []


@pytest.mark.asyncio
async def test_verification_failure_retains_local_copy(monkeypatch, no_rate_limit):
    """Distinct from a raw upload failure — the object reached the bucket
    but re-download/checksum/integrity verification failed (remote_backup's
    own _fail() path for e.g. downloaded_checksum_mismatch). Must be
    treated the same as any other non-verified outcome: retain local."""
    cleanup_calls = []
    monkeypatch.setattr(backup_module, "backup_database", lambda kind: _local_ok())
    monkeypatch.setattr(backup_module, "cleanup_local_copy", lambda path: cleanup_calls.append(path))
    monkeypatch.setattr(backup_module, "record_boot_backup_verified", lambda: None)

    import app.db.remote_backup as remote_backup_module
    monkeypatch.setattr(
        remote_backup_module, "backup_to_bucket",
        lambda kind: {
            "status": "error", "error": "downloaded_checksum_mismatch", "kind": "boot",
            "local_snapshot_retained": "/tmp/cr0b_boot_x.db", "snapshot_created": True,
            "local_integrity_ok": True, "upload_complete": True,
        },
    )

    await job_backup_database_boot()

    assert cleanup_calls == [], "local copy must be retained when remote verification fails, even if upload itself succeeded"


@pytest.mark.asyncio
async def test_interrupted_cleanup_does_not_record_verification(monkeypatch, no_rate_limit):
    """If cleanup_local_copy itself fails partway (e.g. a sidecar can't be
    removed), the boot-verified marker must NOT be written — otherwise a
    later restart's rate-limit check would wrongly skip a real backup
    attempt while a stale/partial local copy still sits on disk."""
    record_calls = []
    monkeypatch.setattr(backup_module, "backup_database", lambda kind: _local_ok())
    monkeypatch.setattr(backup_module, "cleanup_local_copy", lambda path: {"status": "error", "path": path, "error": "simulated: file busy"})
    monkeypatch.setattr(backup_module, "record_boot_backup_verified", lambda: record_calls.append(True))

    import app.db.remote_backup as remote_backup_module
    monkeypatch.setattr(remote_backup_module, "backup_to_bucket", lambda kind: _remote_verified())

    await job_backup_database_boot()

    assert record_calls == [], "an interrupted/failed cleanup must not be recorded as a verified, cleaned-up boot backup"


@pytest.mark.asyncio
async def test_rate_limit_skips_the_entire_cycle_when_recently_verified(monkeypatch):
    local_calls = []
    remote_calls = []
    monkeypatch.setattr(backup_module, "boot_backup_recently_verified", lambda: True)
    monkeypatch.setattr(backup_module, "backup_database", lambda kind: local_calls.append(kind))

    import app.db.remote_backup as remote_backup_module
    monkeypatch.setattr(remote_backup_module, "backup_to_bucket", lambda kind: remote_calls.append(kind))

    await job_backup_database_boot()

    assert local_calls == [], "a recently-verified boot backup must skip the local copy step entirely"
    assert remote_calls == [], "a recently-verified boot backup must skip the remote upload step entirely"


@pytest.mark.asyncio
async def test_no_local_copy_means_nothing_to_reconcile(monkeypatch, no_rate_limit):
    """local backup_database itself skipped/failed (no 'path' in its
    result) — there is no local file to clean up or retain; the job must
    not error out trying to reconcile a copy that never existed."""
    monkeypatch.setattr(backup_module, "backup_database", lambda kind: {"status": "skipped", "reason": "db file not found", "kind": "boot"})

    import app.db.remote_backup as remote_backup_module
    monkeypatch.setattr(remote_backup_module, "backup_to_bucket", lambda kind: _remote_verified())

    await job_backup_database_boot()  # must not raise
