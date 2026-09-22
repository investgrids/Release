"""
Guarded, idempotent repair for 3 leaked seed-fixture Event rows
(2026-09-22 read-only audit finding).

Provenance: app/db/seed.py's hardcoded EVENTS list ran unconditionally
against what is now the production database on 2026-07-22 (created_at
timestamps confirm this), THREE DAYS before commit 5449e897
(2026-07-25) added the `if settings.is_production: skip seeding` guard
in main.py's lifespan. The guard fixed the entry point going forward
but included no cleanup migration, so these 3 rows have sat in
production for two months. Confirmed publicly reachable: both
`GET /api/events/{id}` and the public `/events/{slug}` page return 200
with the fabricated content for at least one of the three (spot-checked
live). Zero dependent rows exist in any of the 9 real-FK event_* child
tables or the 2 soft-referencing tables (event_id column, no enforced
FK) — see DEPENDENT_TABLES below, which mirrors app/db/models/event.py's
own ForeignKey("events.id") declarations plus the two known soft refs.

Affected IDs (exactly these 3, never a broader match):
  evt-rbi-june-2026, evt-defence-budget-2026, evt-solar-capacity-2026

Usage — this script has no argv (it is piped to `python3 -` over
`railway ssh`, which has no stdin-based arg passing), so its mode is
controlled by the REPAIR_MODE environment variable:

  REPAIR_MODE=dry_run   (default, safe) — runs every check, prints the
                          full manifest and what WOULD happen, makes
                          zero writes to `events` or any other table.
  REPAIR_MODE=apply     — after every check passes, deletes the 3 rows
                          in one transaction; requires exactly 3
                          affected rows or rolls back and raises.

Idempotent: re-running with REPAIR_MODE=apply after the rows are
already gone finds 0 matching rows and exits cleanly ("nothing to
do"), rather than erroring on a rowcount mismatch.

This script never triggers the backup itself — see
scripts/repair_leaked_seed_events_trigger_backup.py, run and verified
separately, once, immediately before the first REPAIR_MODE=apply run.
Keeping the two concerns in separate files means a backup failure can
never be silently bypassed by re-running this file alone.

Dependent-row handling (found by this script's own first dry-run,
2026-09-22 — not assumed, not part of the original 4-table read-only
audit): `opportunities` has no event-related column in production at
all (its model file's comment is stale; checked directly via
PRAGMA table_info, not assumed innocent). Two real, exact-ID
dependents DO exist and are purely derivative of the 3 fixtures — never
independently valuable once their source event is gone:
  - event_similar: 7 rows where `similar_event_id` is one of the 3
    fixtures (7 real, unrelated NSE events lose one "similar event"
    cross-reference each; their own rows are untouched).
  - ripple_graphs: exactly 3 rows, one per fixture, `event_id` = the
    fixture id, built directly from the fixture's own fabricated title.
Both are deleted, by the same exact 3 IDs only, in the SAME transaction
as the events themselves, before the events delete — never a broader
match, never touching any row that isn't provably tied to one of these
3 IDs.
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
from datetime import datetime, timezone

FIXTURE_IDS = ("evt-rbi-june-2026", "evt-defence-budget-2026", "evt-solar-capacity-2026")

# Mirrors app/db/models/event.py's own ForeignKey("events.id") columns
# exactly, plus the known soft (non-FK, comment-only) reference —
# discovered via `grep -rn "events.id" app/db/models/*.py`, not assumed.
# `opportunities` is NOT here: its model file's own comment claims an
# `event_id` FK, but PRAGMA table_info(opportunities) against the real
# production schema (checked directly, 2026-09-22) shows no such column
# exists at all — a stale comment, not a real dependency to guard.
DEPENDENT_TABLES: tuple[tuple[str, str], ...] = (
    ("event_companies", "event_id"),
    ("event_sectors", "event_id"),
    ("event_timeline", "event_id"),
    ("event_news", "event_id"),
    ("event_graph_nodes", "event_id"),
    ("event_graph_edges", "event_id"),
    ("event_similar", "event_id"),
    ("event_policies", "event_id"),
)

# Discovered by this script's own first dry-run run (2026-09-22) — real,
# exact-ID dependents that ARE expected and are purely derivative of the
# 3 fixtures (never independently valuable once their source event is
# gone). Deleted by these exact IDs only, in the same transaction, right
# before the events themselves — never blocking, unlike DEPENDENT_TABLES
# above, but never silently ignored either: every row deleted here is
# recorded in the manifest.
CLEANUP_BEFORE_DELETE: tuple[tuple[str, str], ...] = (
    ("event_similar", "similar_event_id"),
    ("ripple_graphs", "event_id"),
)


def _db_path() -> str:
    sys.path.insert(0, "/app")
    from sqlalchemy.engine import make_url
    from app.core.config import settings
    url = make_url(settings.database_url)
    if not url.drivername.startswith("sqlite") or not url.database:
        raise RuntimeError(f"expected a sqlite database_url, got drivername={url.drivername!r}")
    return url.database


def main() -> int:
    mode = os.environ.get("REPAIR_MODE", "dry_run")
    if mode not in ("dry_run", "apply"):
        print(f"invalid REPAIR_MODE={mode!r}, must be dry_run or apply")
        return 2

    db_path = _db_path()
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    placeholders = ",".join("?" for _ in FIXTURE_IDS)

    # ── Export the complete rows (the repair record) before touching anything ──
    rows = []
    for fid in FIXTURE_IDS:
        cur.execute("SELECT * FROM events WHERE id = ?", (fid,))
        r = cur.fetchone()
        rows.append(dict(r) if r else None)

    present_ids = [fid for fid, r in zip(FIXTURE_IDS, rows) if r is not None]
    if not present_ids:
        print(json.dumps({
            "status": "nothing_to_do", "mode": mode,
            "reason": "none of the 3 fixture IDs are present — already repaired",
            "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        }, indent=2))
        return 0

    manifest = {
        "description": "Leaked seed-fixture Event repair — see this script's own module docstring for full provenance.",
        "mode": mode,
        "exported_at_utc": datetime.now(timezone.utc).isoformat(),
        "fixture_ids": list(FIXTURE_IDS),
        "present_ids": present_ids,
        "rows_before_delete": rows,
    }

    # ── Reconfirm zero dependent rows, every table discovered via schema
    #    inspection — never assume yesterday's check still holds. ──────────
    dependent_results = {}
    all_clear = True
    for table, col in DEPENDENT_TABLES:
        try:
            cur.execute(f"SELECT COUNT(*) FROM {table} WHERE {col} IN ({placeholders})", present_ids)
            n = cur.fetchone()[0]
        except sqlite3.OperationalError as exc:
            n = f"error: {exc}"
        dependent_results[f"{table}.{col}"] = n
        if n != 0:
            all_clear = False
    manifest["dependent_row_check"] = dependent_results
    manifest["dependent_rows_all_clear"] = all_clear

    # raw_evidence has no real FK (title-text only) — checked for
    # completeness, never treated as a blocking dependency either way.
    titles = [r["title"] for r in rows if r]
    raw_evidence_titles = {}
    for t in titles:
        cur.execute("SELECT COUNT(*) FROM raw_evidence WHERE title = ?", (t,))
        raw_evidence_titles[t] = cur.fetchone()[0]
    manifest["raw_evidence_title_matches"] = raw_evidence_titles

    # Expected, non-blocking dependents — recorded exactly, deleted (in
    # apply mode) by these same exact IDs, before the events themselves.
    cleanup_counts = {}
    for table, col in CLEANUP_BEFORE_DELETE:
        cur.execute(f"SELECT COUNT(*) FROM {table} WHERE {col} IN ({placeholders})", present_ids)
        cleanup_counts[f"{table}.{col}"] = cur.fetchone()[0]
    manifest["cleanup_before_delete_counts"] = cleanup_counts

    if not all_clear:
        manifest["status"] = "aborted_dependent_rows_found"
        print(json.dumps(manifest, indent=2, default=str))
        con.close()
        return 1

    if mode == "dry_run":
        manifest["status"] = "dry_run_ok_would_delete"
        print(json.dumps(manifest, indent=2, default=str))
        con.close()
        return 0

    # ── mode == "apply" ──────────────────────────────────────────────────
    try:
        cur.execute("BEGIN")

        cleanup_affected = {}
        for table, col in CLEANUP_BEFORE_DELETE:
            cur.execute(f"DELETE FROM {table} WHERE {col} IN ({placeholders})", present_ids)
            cleanup_affected[f"{table}.{col}"] = cur.rowcount
        manifest["cleanup_affected_rows"] = cleanup_affected
        for key, expected in cleanup_counts.items():
            if cleanup_affected.get(key) != expected:
                con.rollback()
                manifest["status"] = "rolled_back_cleanup_rowcount_mismatch"
                manifest["mismatch_key"] = key
                print(json.dumps(manifest, indent=2, default=str))
                con.close()
                return 1

        cur.execute(f"DELETE FROM events WHERE id IN ({placeholders})", present_ids)
        affected = cur.rowcount
        if affected != len(present_ids):
            con.rollback()
            manifest["status"] = "rolled_back_rowcount_mismatch"
            manifest["expected_affected"] = len(present_ids)
            manifest["actual_affected"] = affected
            print(json.dumps(manifest, indent=2, default=str))
            con.close()
            return 1
        con.commit()
        manifest["status"] = "applied"
        manifest["affected_rows"] = affected
    except Exception as exc:
        con.rollback()
        manifest["status"] = "rolled_back_exception"
        manifest["error"] = str(exc)
        print(json.dumps(manifest, indent=2, default=str))
        con.close()
        return 1

    print(json.dumps(manifest, indent=2, default=str))
    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
