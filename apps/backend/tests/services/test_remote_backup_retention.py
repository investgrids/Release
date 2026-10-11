"""Retention for the off-box backup bucket: bounded, safe, and unable to fail a backup. Pure planner tests plus a fake S3 client; no network."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.core.config import settings
from app.db import remote_backup as rb

NOW = datetime(2026, 10, 11, 7, 30, tzinfo=timezone.utc)


def obj(key, days_ago, hours=0, size=735_000_000):
    return {"Key": key, "LastModified": NOW - timedelta(days=days_ago, hours=hours), "Size": size}


def realistic_bucket():
    """The bucket as it was before cleanup: 378 boot backups over 21 days, 30 dailies, three pre-repair snapshots, two preserved copies."""
    objs = [obj(f"automated/boot/ig-{i}.db", 21 - i * 21 / 378) for i in range(378)]
    objs += [obj(f"automated/daily/ig-d{i}.db", 30 - i) for i in range(30)]
    objs += [obj(f"automated/pre_{n}/ig.db", 19) for n in ("holiday_price_bar_repair", "sector_data_fabrication_repair", "seed_fixture_repair")]
    objs += [obj(f"manual-preservation/ig-{n}.db", 31) for n in ("a", "b")]
    return objs


def test_planner_matches_the_reviewed_plan_on_a_realistic_bucket():
    keep, delete = rb.plan_retention(realistic_bucket(), NOW)
    assert len(delete) == 373 and len(keep) == 40
    assert all(k.startswith("automated/boot/") for k in delete)            # only boot backups were removed
    assert sum(k.startswith("automated/daily/") for k in keep) == 30        # every recent daily stays
    assert sum(k.startswith("automated/boot/") for k in keep) == 5


def test_only_the_newest_five_boot_backups_survive_and_they_are_the_newest():
    objs = [obj(f"automated/boot/ig-{i}.db", 10 - i) for i in range(10)]    # i=9 is newest
    keep, delete = rb.plan_retention(objs, NOW)
    assert keep == sorted(f"automated/boot/ig-{i}.db" for i in range(5, 10))
    assert sorted(delete) == sorted(f"automated/boot/ig-{i}.db" for i in range(0, 5))


def test_never_touches_objects_outside_boot_and_daily_even_when_very_old():
    objs = [obj("automated/pre_seed_fixture_repair/ig.db", 400), obj("manual-preservation/ig.db", 500), obj("something/else.db", 900)]
    keep, delete = rb.plan_retention(objs, NOW)
    assert delete == [] and len(keep) == 3


def test_a_protected_key_is_kept_even_if_it_would_be_deleted():
    objs = [obj(f"automated/boot/ig-{i}.db", 10 - i) for i in range(10)]
    keep, delete = rb.plan_retention(objs, NOW, protect={"automated/boot/ig-0.db"})
    assert "automated/boot/ig-0.db" in keep and "automated/boot/ig-0.db" not in delete


def test_old_dailies_are_thinned_to_one_per_week_then_one_per_month():
    recent = [obj(f"automated/daily/recent-{i}.db", i) for i in range(0, 31)]                 # all kept
    weekly_zone = [obj(f"automated/daily/w-{i}.db", 40 + i) for i in range(0, 28)]            # 40..67 days old: 4 weeks of dailies
    monthly_zone = [obj(f"automated/daily/m-{i}.db", 100 + i) for i in range(0, 60)]          # 100..159 days old: about 2 months
    keep, delete = rb.plan_retention(recent + weekly_zone + monthly_zone, NOW)
    kept_weekly = [k for k in keep if "/w-" in k]
    kept_monthly = [k for k in keep if "/m-" in k]
    assert 4 <= len(kept_weekly) <= 5                                                         # one per ISO week
    assert 2 <= len(kept_monthly) <= 3                                                        # one per month
    assert all(f"automated/daily/recent-{i}.db" in keep for i in range(0, 31))
    assert len(delete) == len(weekly_zone) + len(monthly_zone) - len(kept_weekly) - len(kept_monthly)


def test_planner_is_idempotent():
    objs = realistic_bucket()
    keep, delete = rb.plan_retention(objs, NOW)
    remaining = [o for o in objs if o["Key"] in set(keep)]
    keep2, delete2 = rb.plan_retention(remaining, NOW)
    assert delete2 == [] and keep2 == keep


# ── pruner with a fake S3 client ──────────────────────────────────────────────────────────────────────────────────

class FakeS3:
    def __init__(self, objects, fail_list=False, errors=None):
        self.objects, self.deleted_calls, self.fail_list, self.errors = list(objects), [], fail_list, errors or []

    def get_paginator(self, name):
        assert name == "list_objects_v2"
        outer = self

        class P:
            def paginate(self, Bucket, Prefix):
                if outer.fail_list:
                    raise RuntimeError("list failed")
                yield {"Contents": [o for o in outer.objects if o["Key"].startswith(Prefix)]}
        return P()

    def delete_objects(self, Bucket, Delete):
        keys = [d["Key"] for d in Delete["Objects"]]
        self.deleted_calls.append(keys)
        gone = [k for k in keys if k not in self.errors]
        self.objects = [o for o in self.objects if o["Key"] not in gone]
        return {"Deleted": [{"Key": k} for k in gone], "Errors": [{"Key": k, "Code": "AccessDenied"} for k in keys if k in self.errors]}


def test_prune_deletes_old_boots_but_never_the_object_just_uploaded():
    objs = [obj(f"automated/boot/ig-{i}.db", 10 - i) for i in range(12)]
    just = "automated/boot/ig-0.db"                                    # pretend the oldest was just uploaded (extreme case)
    c = FakeS3(objs)
    r = rb.prune_remote_backups(c, "b", just, now=NOW)
    assert r["status"] == "ok" and r["deleted"] == 6                 # 12 boots - newest 5 - the protected one
    assert all(just not in call for call in c.deleted_calls)


def test_prune_caps_deletions_per_run_and_converges_over_runs():
    objs = [obj(f"automated/boot/ig-{i:04d}.db", 20 - i * 0.01) for i in range(300)]
    c = FakeS3(objs)
    r1 = rb.prune_remote_backups(c, "b", "automated/boot/ig-0299.db", now=NOW)
    assert r1["deleted"] == rb._RETENTION_MAX_DELETES
    for _ in range(5):
        rb.prune_remote_backups(c, "b", "automated/boot/ig-0299.db", now=NOW)
    assert sum(o["Key"].startswith("automated/boot/") for o in c.objects) == 5


def test_prune_never_raises_when_the_bucket_misbehaves():
    assert rb.prune_remote_backups(FakeS3([], fail_list=True), "b", "k", now=NOW)["status"] == "error"
    objs = [obj(f"automated/boot/ig-{i}.db", 10 - i) for i in range(8)]
    r = rb.prune_remote_backups(FakeS3(objs, errors=["automated/boot/ig-0.db"]), "b", "automated/boot/ig-7.db", now=NOW)
    assert r["status"] == "partial" and r["errors"] == 1


def test_prune_does_nothing_when_nothing_is_old(monkeypatch):
    objs = [obj(f"automated/boot/ig-{i}.db", i) for i in range(3)]
    c = FakeS3(objs)
    assert rb.prune_remote_backups(c, "b", "automated/boot/ig-0.db", now=NOW)["deleted"] == 0 and c.deleted_calls == []


def test_prune_can_be_switched_off(monkeypatch):
    monkeypatch.setattr(settings, "backup_remote_retention_enabled", False)
    c = FakeS3([obj(f"automated/boot/ig-{i}.db", 10 - i) for i in range(12)])
    assert rb.prune_remote_backups(c, "b", "k", now=NOW) == {"status": "disabled"} and c.deleted_calls == []
