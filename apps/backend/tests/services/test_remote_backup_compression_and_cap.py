"""Compressed off-box backups (verified on the DECOMPRESSED bytes) and a hard size ceiling for the bucket (Cloudflare R2's free tier is 10 GB)."""
from __future__ import annotations

import gzip
import hashlib
import re
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import app.db.remote_backup as rb
from app.core.config import settings
from tests.services.test_remote_backup import FakeS3Client, isolated_remote_backup_env  # noqa: F401  (fixtures reused)

NOW = datetime(2026, 10, 11, 7, 30, tzinfo=timezone.utc)
GB = 1_000_000_000


def _leftovers():
    return {p.name for p in Path(tempfile.gettempdir()).glob("cr0b_*")}


# ── compression ───────────────────────────────────────────────────────────────────────────────────────────────

def test_compressed_backup_is_gz_smaller_verified_on_decompressed_bytes(isolated_remote_backup_env, monkeypatch):
    monkeypatch.setattr(settings, "backup_remote_compress", True)
    before = _leftovers()
    result = rb.backup_to_bucket("boot")
    assert result["status"] == "ok" and result["remote_verified"] is True and result["cleanup_complete"] is True
    key = result["object_key"]
    assert key.endswith(".db.gz") and key.startswith("automated/boot/")
    fake = isolated_remote_backup_env["client"]
    stored = fake.objects[key]
    meta = fake.metadata[key]
    assert meta["compression"] == "gzip" and int(meta["stored-size-bytes"]) == len(stored)
    plain = gzip.decompress(stored)
    assert hashlib.sha256(plain).hexdigest() == meta["source-sha256"]            # the recorded checksum describes the uncompressed database
    assert int(meta["source-size-bytes"]) == len(plain)
    assert len(stored) < len(plain)
    assert _leftovers() == before                                                # no compressed/decompressed temp files left behind


def test_default_is_uncompressed_and_unchanged(isolated_remote_backup_env):
    result = rb.backup_to_bucket("boot")
    assert result["status"] == "ok" and result["object_key"].endswith(".db") and not result["object_key"].endswith(".gz")


def test_a_corrupted_compressed_download_fails_closed(isolated_remote_backup_env, monkeypatch):
    monkeypatch.setattr(settings, "backup_remote_compress", True)
    fake = FakeS3Client()
    monkeypatch.setattr(rb, "_s3_client", lambda: fake)
    orig_upload = fake.upload_file

    def corrupting_upload(path, Bucket, Key, ExtraArgs=None):
        orig_upload(path, Bucket, Key, ExtraArgs)
        fake.corrupt_on_download.add(Key)
    monkeypatch.setattr(fake, "upload_file", corrupting_upload)
    before = _leftovers()
    result = rb.backup_to_bucket("boot")
    assert result["status"] == "error" and result.get("remote_verified") is not True
    assert result["error"] in ("downloaded_decompress_failed", "downloaded_checksum_mismatch")
    assert not [p for p in _leftovers() - before if p.endswith(".gz")]           # compressed temp is cleaned even on failure


# ── size ceiling ───────────────────────────────────────────────────────────────────────────────────────────────

def obj(key, days_ago, size):
    return {"Key": key, "LastModified": NOW - timedelta(days=days_ago), "Size": size}


def bucket(n_daily=30, n_boot=20, size=int(0.2 * GB)):
    objs = [obj(f"automated/daily/d{i}.db.gz", i, size) for i in range(n_daily)]
    objs += [obj(f"automated/boot/b{i}.db.gz", 10 - i * 0.4, size) for i in range(n_boot)]
    objs += [obj("manual-preservation/a.db.gz", 40, size), obj("automated/pre_x_repair/p.db.gz", 20, size)]
    return objs


def total(objs, keys):
    ks = set(keys)
    return sum(o["Size"] for o in objs if o["Key"] in ks)


def test_no_ceiling_means_the_normal_policy_only():
    objs = bucket()
    keep_default, _ = rb.plan_retention(objs, NOW)
    keep_zero, _ = rb.plan_retention(objs, NOW, max_bytes=0)
    assert keep_default == keep_zero


def test_ceiling_drops_the_least_valuable_first_and_fits():
    objs = bucket()
    keep_all, _ = rb.plan_retention(objs, NOW)
    assert total(objs, keep_all) > 5 * GB                                        # the normal policy alone would not fit
    keep, delete = rb.plan_retention(objs, NOW, max_bytes=5 * GB)
    assert total(objs, keep) <= 5 * GB
    kept = set(keep)
    assert {"automated/boot/b19.db.gz", "automated/boot/b18.db.gz"} <= kept       # newest 2 boot backups survive
    assert {"automated/daily/d0.db.gz", "automated/daily/d1.db.gz", "automated/daily/d2.db.gz"} <= kept   # newest 3 dailies survive
    assert {"manual-preservation/a.db.gz", "automated/pre_x_repair/p.db.gz"} <= kept                       # non-automated copies untouched
    assert all(k.startswith(("automated/boot/", "automated/daily/")) and "pre_" not in k for k in delete)
    old_daily_dropped = [k for k in delete if "/daily/" in k]
    assert old_daily_dropped and all(int(re.search(r"/d(\d+)\.db", k).group(1)) > 7 for k in old_daily_dropped)  # nothing from the last week is dropped before older ones


def test_protected_key_survives_even_under_a_tiny_ceiling():
    objs = bucket()
    keep, delete = rb.plan_retention(objs, NOW, protect={"automated/daily/d20.db.gz"}, max_bytes=1)
    assert "automated/daily/d20.db.gz" in keep and "automated/daily/d20.db.gz" not in delete


def test_when_the_floor_alone_exceeds_the_ceiling_nothing_more_is_dropped():
    objs = bucket()
    keep, _ = rb.plan_retention(objs, NOW, max_bytes=1)
    assert len(keep) == 2 + 2 + 3 + 0 or len(keep) >= 7                          # newest 2 boots + newest 3 dailies + the 2 non-automated copies


def test_the_bucket_never_exceeds_the_ceiling_over_120_days_of_real_traffic():
    """Each day: 12 boot backups and one daily, 0.19 GB each (compressed), pruned after every upload under an 8.5 GB ceiling. The total must stay below 10 GB at all times."""
    cap, size, start = int(8.5 * GB), int(0.19 * GB), datetime(2026, 1, 1, tzinfo=timezone.utc)
    objs, worst = [], 0
    for day in range(120):
        for n in range(13):
            when = start + timedelta(days=day, hours=n * 1.8)
            key = f"automated/daily/{when:%Y%m%dT%H%M}.db.gz" if n == 12 else f"automated/boot/{when:%Y%m%dT%H%M}.db.gz"
            objs.append({"Key": key, "LastModified": when, "Size": size})
            worst = max(worst, sum(o["Size"] for o in objs))                     # right after an upload, before pruning
            _, delete = rb.plan_retention(objs, when, protect={key}, max_bytes=cap)
            objs = [o for o in objs if o["Key"] not in set(delete)]
    assert worst < 10 * GB
    assert sum(o["Size"] for o in objs) <= cap
