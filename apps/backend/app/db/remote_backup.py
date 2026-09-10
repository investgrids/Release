"""Off-volume backup (CR-0b, 2026-09-10) — uploads a verified SQLite
snapshot to a Railway Bucket (S3-compatible), staged entirely on the
container's ephemeral filesystem (confirmed 1.7TB free on the root
overlay, vs. /data's persistent volume at 87% used) so this never
competes with the tight persistent-volume capacity app/db/backup.py's
same-volume path has become unable to reliably satisfy (see backup.py's
own CR-0 comment — the same-volume repair, deployed the same day, proved
correct but is now routinely skipping with status=insufficient_disk_headroom
because the live DB has outgrown what same-volume pruning alone can free).

Fully independent of app/db/backup.py — never reads, writes, or deletes
anything under /data/backups. A remote-backup failure here must never
affect the local backup path or the live database either way.

Real production sequence (owner-locked, 2026-09-10):
  1. SQLite online-backup API -> snapshot on ephemeral disk (/tmp)
  2. close both backup connections cleanly
  3. PRAGMA quick_check on the local snapshot
  4. SHA-256 of the local snapshot
  5. upload as an immutable object (never overwrites an existing key)
  6. HEAD the uploaded object, verify remote size matches
  7. download to a SECOND disposable temp path
  8. SHA-256 of the downloaded copy, must match step 4
  9. PRAGMA quick_check on the downloaded copy
  10. only once 6/8/9 all pass -> remote_verified
  11. delete the local ephemeral snapshot from step 1 (never before
      remote_verified)
  12. on ANY failure in 5-10: keep the local snapshot (ephemeral disk has
      ample room), log one consistent hard "backup_remote.degraded"
      alert regardless of which step failed, never touch the live DB or
      the same-volume backup path.

Telemetry states recorded in every real result (never inferred from "the
function returned without raising"): snapshot_created, local_integrity_ok,
upload_complete, remote_verified, cleanup_complete. A caller must check
`remote_verified` explicitly — `status == "ok"` implies it, but the
states dict is there so a partial failure never quietly reads as a full
success.
"""
from __future__ import annotations

import hashlib
import os
import sqlite3
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import structlog
from sqlalchemy.engine import make_url

from app.core.config import settings

log = structlog.get_logger(__name__)

_OBJECT_PREFIX = "automated"


def _sqlite_path() -> Optional[Path]:
    url = make_url(settings.database_url)
    if not url.drivername.startswith("sqlite") or not url.database:
        return None
    return Path(url.database)


def _bucket_configured() -> bool:
    return bool(settings.backup_bucket_access_key_id and settings.backup_bucket_name)


def _s3_client():
    import boto3
    from botocore.config import Config

    return boto3.client(
        "s3",
        endpoint_url=settings.backup_bucket_endpoint,
        region_name=settings.backup_bucket_region,
        aws_access_key_id=settings.backup_bucket_access_key_id,
        aws_secret_access_key=settings.backup_bucket_secret_access_key,
        config=Config(s3={"addressing_style": "virtual"}),
    )


def _sha256_of_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _sqlite_quick_check(path: Path) -> str:
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        return con.execute("PRAGMA quick_check").fetchone()[0]
    finally:
        con.close()


def _object_exists(client, bucket: str, key: str) -> bool:
    try:
        client.head_object(Bucket=bucket, Key=key)
        return True
    except client.exceptions.ClientError as exc:
        status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
        code = exc.response.get("Error", {}).get("Code")
        if status == 404 or code in ("404", "NoSuchKey", "NotFound"):
            return False
        raise  # any other ClientError (auth, permissions, etc.) must propagate, not be treated as "safe to proceed"


def backup_to_bucket(kind: str = "boot") -> dict:
    """Synchronous (file/sqlite3/network I/O) — call via asyncio.to_thread
    from async contexts, same convention as app.db.backup.backup_database.
    `kind` is "daily" or "boot", purely for object-key namespacing and
    logging — no retention/kind-specific behavior beyond that (no
    same-volume capacity constraint applies here, so there's nothing to
    ration between kinds)."""
    states: dict = {}

    if not _bucket_configured():
        return {"status": "skipped", "reason": "bucket not configured", "kind": kind, **states}

    db_path = _sqlite_path()
    if db_path is None or not db_path.exists():
        return {"status": "skipped", "reason": "no sqlite db", "kind": kind, **states}

    now = datetime.now(timezone.utc)
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    object_key = f"{_OBJECT_PREFIX}/{kind}/ig-{stamp}.db"
    start = time.monotonic()

    local_snapshot: Optional[Path] = None
    verify_download: Optional[Path] = None

    def _fail(reason: str, **extra) -> dict:
        log.error("backup_remote.degraded", kind=kind, reason=reason,
                   local_snapshot_retained=str(local_snapshot) if local_snapshot else None,
                   **states, **extra)
        return {
            "status": "error", "error": reason, "kind": kind,
            "local_snapshot_retained": str(local_snapshot) if local_snapshot else None,
            **states,
        }

    try:
        # Steps 1-2: SQLite online backup API -> ephemeral disk (/tmp, NOT
        # /data), both connections closed cleanly before anything else runs.
        fd, tmp_name = tempfile.mkstemp(prefix=f"cr0b_{kind}_", suffix=".db")
        os.close(fd)
        local_snapshot = Path(tmp_name)
        local_snapshot.unlink()  # sqlite3's backup API must create the file itself

        src_conn = sqlite3.connect(str(db_path))
        dest_conn = sqlite3.connect(str(local_snapshot))
        try:
            src_conn.backup(dest_conn)
        finally:
            dest_conn.close()
            src_conn.close()
        states["snapshot_created"] = True
        snapshot_size = local_snapshot.stat().st_size

        # Step 3: local integrity check, before any network call.
        local_check = _sqlite_quick_check(local_snapshot)
        if local_check != "ok":
            return _fail("local_integrity_check_failed", quick_check_result=local_check)
        states["local_integrity_ok"] = True

        # Step 4: checksum before upload.
        local_sha256 = _sha256_of_file(local_snapshot)

        client = _s3_client()

        # Immutable object naming — refuse to silently overwrite.
        if _object_exists(client, settings.backup_bucket_name, object_key):
            return _fail("object_already_exists", object_key=object_key)

        # Step 5: upload.
        client.upload_file(
            str(local_snapshot), settings.backup_bucket_name, object_key,
            ExtraArgs={
                "Metadata": {
                    "source-size-bytes": str(snapshot_size),
                    "source-sha256": local_sha256,
                    "upload-timestamp-utc": now.isoformat(),
                    "kind": kind,
                    "source-environment": "railway-production-backend",
                }
            },
        )
        states["upload_complete"] = True

        # Step 6: HEAD/metadata verify.
        head = client.head_object(Bucket=settings.backup_bucket_name, Key=object_key)
        remote_size = head["ContentLength"]
        if remote_size != snapshot_size:
            return _fail("remote_size_mismatch", local_size=snapshot_size, remote_size=remote_size, object_key=object_key)

        # Steps 7-9: download to a second disposable path, re-verify independently.
        fd2, verify_name = tempfile.mkstemp(prefix=f"cr0b_verify_{kind}_", suffix=".db")
        os.close(fd2)
        verify_download = Path(verify_name)
        client.download_file(settings.backup_bucket_name, object_key, str(verify_download))

        downloaded_sha256 = _sha256_of_file(verify_download)
        if downloaded_sha256 != local_sha256:
            return _fail("downloaded_checksum_mismatch", object_key=object_key)

        downloaded_check = _sqlite_quick_check(verify_download)
        if downloaded_check != "ok":
            return _fail("remote_integrity_check_failed", quick_check_result=downloaded_check, object_key=object_key)

        # Step 10: only now is the remote copy considered verified.
        states["remote_verified"] = True

        duration_sec = round(time.monotonic() - start, 2)
        log.info(
            "backup_remote.completed", kind=kind, object_key=object_key,
            size_bytes=snapshot_size, duration_sec=duration_sec, sha256=local_sha256,
        )
        result = {
            "status": "ok", "kind": kind, "object_key": object_key,
            "size_bytes": snapshot_size, "sha256": local_sha256, "duration_sec": duration_sec,
            **states,
        }

        # Step 11: only delete the local ephemeral snapshot after remote_verified.
        local_snapshot.unlink(missing_ok=True)
        local_snapshot = None
        states["cleanup_complete"] = True
        result["cleanup_complete"] = True
        return result

    except Exception as exc:
        # Step 12: any unexpected exception (network failure mid-upload,
        # credential failure, process restart risk, etc.) — retain the
        # local snapshot, log the same consistent degraded alert as the
        # explicit failure branches above, never touch the live DB or the
        # same-volume backup path.
        return _fail("unexpected_exception", error=str(exc))
    finally:
        if verify_download is not None:
            verify_download.unlink(missing_ok=True)
