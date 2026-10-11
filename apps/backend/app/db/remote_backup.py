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

import gzip
import hashlib
import os
import shutil
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

# ── Retention ──────────────────────────────────────────────────────────────────────────────────────────────────────
# Objects were immutable and NEVER deleted, and a "boot" backup is written on every process start. Crawler traffic recycled the web worker every 1-3 hours,
# so the bucket grew by ~11 GB a day and reached 413 objects / 222 GB (about 735 MB each). The rule below keeps recovery points without keeping every restart:
#   automated/boot/   newest 5
#   automated/daily/  all from the last 30 days, then the first of each ISO week up to 84 days, then the first of each month
#   anything else     never touched (pre-repair snapshots, manual preservation copies)
# It runs only after a new backup is remote-verified, never deletes the object just uploaded, deletes at most _RETENTION_MAX_DELETES per run, and can never
# fail or slow the backup (everything is caught). Set BACKUP_REMOTE_RETENTION_ENABLED=false to turn it off.
_BOOT_KEEP = 5
_DAILY_KEEP_DAYS = 30
_WEEKLY_KEEP_DAYS = 84
_RETENTION_MAX_DELETES = 100
_PRUNABLE_PREFIXES = (f"{_OBJECT_PREFIX}/boot/", f"{_OBJECT_PREFIX}/daily/")


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
        config=Config(s3={"addressing_style": getattr(settings, "backup_bucket_addressing_style", "virtual") or "virtual"}),
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


def _cleanup_sqlite_file(path: Path) -> None:
    """Removes the main file plus whatever -shm/-wal/-journal sidecars
    SQLite created alongside it while a connection had it open (even a
    read-only quick_check connection creates -shm/-wal in WAL-mode
    databases) — confirmed live (2026-09-10): a bare path.unlink() alone
    left orphaned -shm/-wal files behind on every real run, the same
    class of leak app/db/backup.py's own _prune_old_backups() had to fix
    for *.tmp-journal siblings. Harmless on ephemeral /tmp (ample space,
    resets on restart) but incomplete cleanup either way."""
    path.unlink(missing_ok=True)
    for suffix in ("-shm", "-wal", "-journal"):
        sidecar = path.with_name(path.name + suffix)
        sidecar.unlink(missing_ok=True)


def plan_retention(objects: list, now: datetime, protect: set | None = None, max_bytes: int = 0) -> tuple[list, list]:
    """Pure function. `objects` are S3 listing dicts ({Key, LastModified, Size}). Returns (keep_keys, delete_keys). Only boot/ and daily/ objects can ever be
    in delete_keys; every other object, and everything in `protect`, is always kept."""
    protect = set(protect or ())
    boots = sorted((o for o in objects if o["Key"].startswith(f"{_OBJECT_PREFIX}/boot/")), key=lambda o: o["LastModified"])
    dailies = sorted((o for o in objects if o["Key"].startswith(f"{_OBJECT_PREFIX}/daily/")), key=lambda o: o["LastModified"])
    keep = {o["Key"] for o in objects if not o["Key"].startswith(_PRUNABLE_PREFIXES)} | protect
    keep |= {o["Key"] for o in boots[-_BOOT_KEEP:]}
    weeks: dict = {}
    months: dict = {}
    for o in dailies:
        age_days = (now - o["LastModified"]).days
        if age_days <= _DAILY_KEEP_DAYS:
            keep.add(o["Key"])
        elif age_days <= _WEEKLY_KEEP_DAYS:
            weeks.setdefault(tuple(o["LastModified"].isocalendar()[:2]), o["Key"])
        else:
            months.setdefault((o["LastModified"].year, o["LastModified"].month), o["Key"])
    keep |= set(weeks.values()) | set(months.values())

    # Optional hard ceiling (e.g. a free-tier bucket). Drop the least valuable kept backups until the total fits, in this order: weekly/monthly samples (oldest first), then dailies older
    # than 7 days (oldest first), then boot backups beyond the newest 2. Never dropped: the protected keys, the newest 2 boot backups, the newest 3 dailies, and anything that is not
    # a boot/daily backup. If those alone exceed the ceiling nothing more is dropped (it never deletes data it was told to keep).
    if max_bytes and max_bytes > 0:
        size = {o["Key"]: o["Size"] for o in objects}
        total = sum(size[k] for k in keep)
        floor = protect | {o["Key"] for o in boots[-2:]} | {o["Key"] for o in dailies[-3:]}
        order = {o["Key"]: i for i, o in enumerate(sorted(objects, key=lambda o: o["LastModified"]))}
        sampled = set(weeks.values()) | set(months.values())
        weekly = sorted((k for k in keep if k in sampled and k not in floor), key=order.get)
        old_daily = sorted((o["Key"] for o in dailies if o["Key"] in keep and o["Key"] not in floor and o["Key"] not in sampled and (now - o["LastModified"]).days > 7), key=order.get)
        old_boot = sorted((o["Key"] for o in boots if o["Key"] in keep and o["Key"] not in floor), key=order.get)
        for k in weekly + old_daily + old_boot:
            if total <= max_bytes:
                break
            keep.discard(k)
            total -= size[k]
    delete = sorted(o["Key"] for o in objects if o["Key"] not in keep)
    return sorted(keep), delete


def prune_remote_backups(client, bucket: str, just_uploaded_key: str, now: datetime | None = None) -> dict:
    """Apply plan_retention to the bucket. Best effort: never raises, deletes at most _RETENTION_MAX_DELETES per run, and always logs what it did."""
    if not getattr(settings, "backup_remote_retention_enabled", True):
        return {"status": "disabled"}
    try:
        now = now or datetime.now(timezone.utc)
        objects: list = []
        for page in client.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=f"{_OBJECT_PREFIX}/"):
            objects += page.get("Contents", [])
        _, delete = plan_retention(objects, now, protect={just_uploaded_key}, max_bytes=int(getattr(settings, "backup_remote_max_bytes", 0) or 0))
        delete = [k for k in delete if k.startswith(_PRUNABLE_PREFIXES) and k != just_uploaded_key][:_RETENTION_MAX_DELETES]
        if not delete:
            return {"status": "ok", "deleted": 0, "listed": len(objects)}
        sizes = {o["Key"]: o["Size"] for o in objects}
        r = client.delete_objects(Bucket=bucket, Delete={"Objects": [{"Key": k} for k in delete], "Quiet": False})
        deleted = [d["Key"] for d in r.get("Deleted", [])]
        errors = r.get("Errors", [])
        log.info("backup_remote.retention", deleted=len(deleted), errors=len(errors), listed=len(objects), freed_bytes=sum(sizes.get(k, 0) for k in deleted))
        return {"status": "ok" if not errors else "partial", "deleted": len(deleted), "errors": len(errors), "listed": len(objects)}
    except Exception as exc:  # noqa: BLE001 -- retention must never break a backup
        log.warning("backup_remote.retention_failed", error=str(exc))
        return {"status": "error", "error": str(exc)}


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
    compressed_upload: Optional[Path] = None
    decompressed_verify: Optional[Path] = None
    compress = bool(getattr(settings, "backup_remote_compress", False))
    if compress:
        object_key += ".gz"

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

        # Optional compression (about 4x smaller). source-sha256 and source-size-bytes ALWAYS describe the uncompressed database, so the same checks apply either way.
        upload_path, upload_size = local_snapshot, snapshot_size
        if compress:
            fdz, gz_name = tempfile.mkstemp(prefix=f"cr0b_{kind}_", suffix=".db.gz")
            os.close(fdz)
            compressed_upload = Path(gz_name)
            with open(local_snapshot, "rb") as fi, gzip.open(compressed_upload, "wb", compresslevel=3) as fo:
                shutil.copyfileobj(fi, fo, 1 << 20)
            upload_path, upload_size = compressed_upload, compressed_upload.stat().st_size

        # Step 5: upload.
        meta = {
            "source-size-bytes": str(snapshot_size),
            "source-sha256": local_sha256,
            "upload-timestamp-utc": now.isoformat(),
            "kind": kind,
            "source-environment": "railway-production-backend",
        }
        if compress:
            meta["compression"] = "gzip"
            meta["stored-size-bytes"] = str(upload_size)
        client.upload_file(str(upload_path), settings.backup_bucket_name, object_key, ExtraArgs={"Metadata": meta})
        states["upload_complete"] = True

        # Step 6: HEAD/metadata verify (the size of what was stored).
        head = client.head_object(Bucket=settings.backup_bucket_name, Key=object_key)
        remote_size = head["ContentLength"]
        if remote_size != upload_size:
            return _fail("remote_size_mismatch", local_size=upload_size, remote_size=remote_size, object_key=object_key)

        # Steps 7-9: download to a second disposable path, re-verify independently.
        fd2, verify_name = tempfile.mkstemp(prefix=f"cr0b_verify_{kind}_", suffix=".db")
        os.close(fd2)
        verify_download = Path(verify_name)
        client.download_file(settings.backup_bucket_name, object_key, str(verify_download))

        check_path = verify_download
        if compress:
            fd3, plain_name = tempfile.mkstemp(prefix=f"cr0b_verify_plain_{kind}_", suffix=".db")
            os.close(fd3)
            decompressed_verify = Path(plain_name)
            try:
                with gzip.open(verify_download, "rb") as fi, open(decompressed_verify, "wb") as fo:
                    shutil.copyfileobj(fi, fo, 1 << 20)
            except (OSError, EOFError):
                return _fail("downloaded_decompress_failed", object_key=object_key)
            check_path = decompressed_verify

        downloaded_sha256 = _sha256_of_file(check_path)
        if downloaded_sha256 != local_sha256:
            return _fail("downloaded_checksum_mismatch", object_key=object_key)

        downloaded_check = _sqlite_quick_check(check_path)
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

        # Retention: only after this backup is remote-verified, and it can never fail the backup.
        prune_remote_backups(client, settings.backup_bucket_name, object_key)

        # Step 11: only delete the local ephemeral snapshot after remote_verified.
        _cleanup_sqlite_file(local_snapshot)
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
            _cleanup_sqlite_file(verify_download)
        for extra in (compressed_upload, decompressed_verify):
            if extra is not None:
                _cleanup_sqlite_file(extra)
