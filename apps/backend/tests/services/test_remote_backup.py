"""app/db/remote_backup.py (CR-0b, 2026-09-10) — off-volume backup upload,
verify-download, and integrity-check lifecycle. Pure file/sqlite3 I/O plus
a fake in-memory S3 client (no real network/bucket dependency) — isolates
`_sqlite_path()` and settings to a pytest tmp_path per test, following the
same convention as test_backup.py.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

import app.db.remote_backup as remote_backup_module
from app.core.config import settings
from app.db.remote_backup import backup_to_bucket


class _FakeClientError(Exception):
    def __init__(self, status=404, code="NoSuchKey"):
        self.response = {"ResponseMetadata": {"HTTPStatusCode": status}, "Error": {"Code": code}}
        super().__init__(f"{code} ({status})")


class _FakeExceptions:
    ClientError = _FakeClientError


class FakeS3Client:
    """In-memory stand-in for boto3's S3 client, exposing exactly the
    methods/behavior remote_backup.py actually calls."""

    def __init__(self):
        self.objects: dict[str, bytes] = {}
        self.metadata: dict[str, dict] = {}
        self.exceptions = _FakeExceptions
        self.corrupt_on_download: set[str] = set()
        self.lie_about_size = False

    def head_object(self, Bucket, Key):
        if Key not in self.objects:
            raise _FakeClientError(status=404, code="NoSuchKey")
        size = len(self.objects[Key])
        if self.lie_about_size:
            size += 999
        return {"ContentLength": size}

    def upload_file(self, path, Bucket, Key, ExtraArgs=None):
        with open(path, "rb") as f:
            self.objects[Key] = f.read()
        self.metadata[Key] = (ExtraArgs or {}).get("Metadata", {})

    def download_file(self, Bucket, Key, dest_path):
        data = self.objects[Key]
        if Key in self.corrupt_on_download:
            data = data + b"CORRUPTED"
        with open(dest_path, "wb") as f:
            f.write(data)


@pytest.fixture
def isolated_remote_backup_env(tmp_path, monkeypatch):
    src_db = tmp_path / "ig.db"
    conn = sqlite3.connect(str(src_db))
    conn.execute("CREATE TABLE t (id INTEGER)")
    conn.execute("INSERT INTO t VALUES (1)")
    conn.commit()
    conn.close()

    monkeypatch.setattr(remote_backup_module, "_sqlite_path", lambda: src_db)
    monkeypatch.setattr(settings, "backup_bucket_access_key_id", "fake-key")
    monkeypatch.setattr(settings, "backup_bucket_name", "fake-bucket")
    monkeypatch.setattr(settings, "backup_bucket_endpoint", "https://fake.example.com")
    monkeypatch.setattr(settings, "backup_bucket_region", "auto")
    monkeypatch.setattr(settings, "backup_bucket_secret_access_key", "fake-secret")

    fake_client = FakeS3Client()
    monkeypatch.setattr(remote_backup_module, "_s3_client", lambda: fake_client)

    return {"src_db": src_db, "client": fake_client}


def test_skips_when_bucket_not_configured(isolated_remote_backup_env, monkeypatch):
    monkeypatch.setattr(settings, "backup_bucket_access_key_id", "")
    result = backup_to_bucket(kind="boot")
    assert result["status"] == "skipped"
    assert result["reason"] == "bucket not configured"


def test_skips_when_no_sqlite_db(isolated_remote_backup_env, monkeypatch):
    monkeypatch.setattr(remote_backup_module, "_sqlite_path", lambda: None)
    result = backup_to_bucket(kind="boot")
    assert result["status"] == "skipped"
    assert result["reason"] == "no sqlite db"


def test_successful_full_lifecycle_all_states_true(isolated_remote_backup_env):
    result = backup_to_bucket(kind="boot")

    assert result["status"] == "ok"
    assert result["snapshot_created"] is True
    assert result["local_integrity_ok"] is True
    assert result["upload_complete"] is True
    assert result["remote_verified"] is True
    assert result["cleanup_complete"] is True
    assert result["object_key"].startswith("automated/boot/")

    client = isolated_remote_backup_env["client"]
    assert result["object_key"] in client.objects
    assert client.metadata[result["object_key"]]["source-sha256"] == result["sha256"]


def test_success_deletes_local_ephemeral_snapshot(isolated_remote_backup_env, monkeypatch):
    created_paths = []
    real_mkstemp = remote_backup_module.tempfile.mkstemp

    def _tracking_mkstemp(*a, **kw):
        fd, name = real_mkstemp(*a, **kw)
        created_paths.append(name)
        return fd, name

    monkeypatch.setattr(remote_backup_module.tempfile, "mkstemp", _tracking_mkstemp)

    result = backup_to_bucket(kind="boot")
    assert result["status"] == "ok"

    # The snapshot path (first mkstemp call) must be gone; the verify-download
    # path (second) is always cleaned up in `finally` regardless of outcome.
    for p in created_paths:
        assert not Path(p).exists(), f"expected {p} to be cleaned up after a successful run"


def test_object_already_exists_refuses_overwrite_and_never_reuploads(isolated_remote_backup_env):
    """Regardless of what key gets generated, head_object reporting the
    object already exists must refuse to proceed with an upload."""
    client = isolated_remote_backup_env["client"]
    real_head_object = client.head_object
    client.head_object = lambda Bucket, Key: {"ContentLength": 12345}  # always "exists"

    result = backup_to_bucket(kind="boot")

    assert result["status"] == "error"
    assert result["error"] == "object_already_exists"
    assert client.objects == {}, "must never call upload_file once head_object reports an existing key"


def test_local_integrity_check_failure_never_uploads(isolated_remote_backup_env, monkeypatch):
    monkeypatch.setattr(remote_backup_module, "_sqlite_quick_check", lambda path: "corruption found")

    result = backup_to_bucket(kind="boot")

    assert result["status"] == "error"
    assert result["error"] == "local_integrity_check_failed"
    assert result.get("upload_complete") is not True
    client = isolated_remote_backup_env["client"]
    assert client.objects == {}, "must never upload a snapshot that failed its own local integrity check"
    assert result["local_snapshot_retained"] is not None
    assert Path(result["local_snapshot_retained"]).exists()


def test_remote_size_mismatch_fails_closed(isolated_remote_backup_env):
    client = isolated_remote_backup_env["client"]
    client.lie_about_size = True

    result = backup_to_bucket(kind="boot")

    assert result["status"] == "error"
    assert result["error"] == "remote_size_mismatch"
    assert result.get("remote_verified") is not True


def test_downloaded_checksum_mismatch_fails_closed(isolated_remote_backup_env):
    client = isolated_remote_backup_env["client"]
    real_upload = client.upload_file

    def _upload_then_mark_corrupt(path, Bucket, Key, ExtraArgs=None):
        real_upload(path, Bucket, Key, ExtraArgs=ExtraArgs)
        client.corrupt_on_download.add(Key)

    client.upload_file = _upload_then_mark_corrupt

    result = backup_to_bucket(kind="boot")

    assert result["status"] == "error"
    assert result["error"] == "downloaded_checksum_mismatch"
    assert result.get("remote_verified") is not True


def test_failed_run_retains_local_snapshot_never_deletes_it(isolated_remote_backup_env, monkeypatch):
    monkeypatch.setattr(remote_backup_module, "_sqlite_quick_check", lambda path: "bad")

    result = backup_to_bucket(kind="boot")

    assert result["status"] == "error"
    retained = result["local_snapshot_retained"]
    assert retained is not None
    assert Path(retained).exists(), "a failed run must retain the local ephemeral snapshot, not delete it"


def test_unexpected_exception_is_caught_and_reported_not_raised(isolated_remote_backup_env, monkeypatch):
    def _boom(*a, **kw):
        raise RuntimeError("simulated network failure mid-upload")

    isolated_remote_backup_env["client"].upload_file = _boom

    result = backup_to_bucket(kind="boot")  # must not raise

    assert result["status"] == "error"
    assert result["error"] == "unexpected_exception"


def test_sqlite_sidecar_files_are_cleaned_up_not_just_the_db_file(isolated_remote_backup_env, monkeypatch):
    """Real bug found live (2026-09-10): a bare path.unlink() on the .db
    file alone left orphaned -shm/-wal sidecars behind, because SQLite
    creates those for any WAL-mode connection opened against the path
    (even the read-only quick_check connections) -- confirmed on a real
    production run. Both the local snapshot's and the verify-download's
    sidecars must be gone after a successful run."""
    created_paths = []
    real_mkstemp = remote_backup_module.tempfile.mkstemp

    def _tracking_mkstemp(*a, **kw):
        fd, name = real_mkstemp(*a, **kw)
        created_paths.append(name)
        return fd, name

    monkeypatch.setattr(remote_backup_module.tempfile, "mkstemp", _tracking_mkstemp)

    result = backup_to_bucket(kind="boot")
    assert result["status"] == "ok"

    for p in created_paths:
        base = Path(p)
        assert not base.exists()
        for suffix in ("-shm", "-wal", "-journal"):
            assert not base.with_name(base.name + suffix).exists(), f"sidecar {base.name}{suffix} was not cleaned up"


def test_daily_and_boot_kinds_use_distinct_object_key_namespaces(isolated_remote_backup_env):
    daily = backup_to_bucket(kind="daily")
    boot = backup_to_bucket(kind="boot")

    assert daily["status"] == "ok"
    assert boot["status"] == "ok"
    assert daily["object_key"].startswith("automated/daily/")
    assert boot["object_key"].startswith("automated/boot/")
    assert daily["object_key"] != boot["object_key"]
