"""
Guarded, idempotent repair for the 12 fabricated `sector_data` rows
(2026-09-22 sector_theme feasibility audit finding).

Provenance: db/seed.py's SECTORS list hand-types a percentage `value`
for each of these 12 rows (e.g. id="banking", value="+1.2%") — never
computed, never sourced from any real index feed. Confirmed live before
this repair: every row's `updated_at` is exactly the same timestamp
(2026-07-22 08:24:06), matching db/seed.py's own bulk-insert call and
the same day the 3 leaked seed Events (repaired 2026-09-22, see
scripts/repair_leaked_seed_events.py) were also inserted — no other
write path to this table exists anywhere in the codebase (confirmed by
absence: grep found no other `SectorData(` construction or `UPDATE
sector_data` anywhere), so these percentages have been frozen and
presented as live sector momentum for two months.

The code-side correction (api/sectors.py's list_sectors()/
sector_intelligence(), same commit as this script) already stops
reading this table's `value`/`positive` columns at all, regardless of
whether these rows still exist — this script is pure database cleanup
of now-fully-inert rows, run only AFTER that code is deployed and
verified live (see this repair's own deployment sequence). No
replacement momentum source is substituted (ThemeScoringWorker measures
a different taxonomy — theme momentum, not sector performance).

Only ever matches rows satisfying ALL of:
  - id/name/value/positive exactly matches db/seed.py's own SECTORS list
  - updated_at == 2026-07-22 08:24:06 (the seed insertion timestamp,
    re-verified per-row rather than assumed)
  - no dependent table has any row referencing sector_data.id (checked
    fresh — no FK exists in the schema today, but this is verified
    against the live schema rather than trusted from a prior read)

Usage — no argv (piped to `python3 -` over `railway ssh`), mode via the
REPAIR_MODE environment variable:

  REPAIR_MODE=dry_run   (default, safe) — runs every check, prints the
                          full manifest and what WOULD happen, makes
                          zero writes.
  REPAIR_MODE=apply     — after every check passes, deletes the exact
                          rows in one transaction; requires exactly 12
                          affected rows or rolls back and raises.

Idempotent: re-running with REPAIR_MODE=apply after the rows are
already gone finds 0 matching rows and exits cleanly ("nothing to
do").
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
from datetime import datetime, timezone

_SEEDED_AT = "2026-07-22 08:24:06"  # matched by prefix below (microseconds vary per row)

# The exact 12 rows db/seed.py's SECTORS list inserts — re-declared here
# (never imported from seed.py) so this script's own expectations are
# frozen and independently reviewable, not silently coupled to whatever
# seed.py happens to contain when this script runs.
_EXPECTED_ROWS: dict[str, tuple[str, str, bool]] = {
    "it":       ("IT", "-0.9%", False),
    "banking":  ("Banking", "+1.2%", True),
    "pharma":   ("Pharma", "+0.6%", True),
    "auto":     ("Auto", "+1.8%", True),
    "energy":   ("Energy", "+2.4%", True),
    "fmcg":     ("FMCG", "-0.3%", False),
    "infra":    ("Infra", "+3.1%", True),
    "metal":    ("Metal", "+0.7%", True),
    "realty":   ("Realty", "+1.5%", True),
    "psu-bank": ("PSU Bank", "+0.4%", True),
    "pvt-bank": ("Pvt Bank", "+1.1%", True),
    "media":    ("Media", "-1.2%", False),
}

# Every table in this schema — re-verified live against sqlite_master
# rather than a hardcoded assumption, since "no FK exists today" is
# exactly the kind of fact that silently rots.
_ALL_TABLES_CHECKED_FOR_DEPENDENTS = True


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

    cur.execute("SELECT id, name, value, positive, updated_at FROM sector_data")
    candidates = [dict(r) for r in cur.fetchall()]

    if not candidates:
        print(json.dumps({
            "status": "nothing_to_do", "mode": mode,
            "reason": "no sector_data rows — already repaired",
            "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        }, indent=2))
        con.close()
        return 0

    manifest = {
        "description": "Fabricated sector_data repair — see this script's own module docstring.",
        "mode": mode,
        "exported_at_utc": datetime.now(timezone.utc).isoformat(),
        "candidate_count": len(candidates),
        "rows_before_delete": candidates,
    }

    # ── Dependent-table check — every table in the live schema, not a
    #    hardcoded guess. Same pattern as scripts/repair_leaked_seed_
    #    events.py's own dependent-table discovery. ──────────────────────
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name != 'sector_data'")
    other_tables = [r["name"] for r in cur.fetchall()]
    dependent_rows_found: dict[str, int] = {}
    for table in other_tables:
        cur.execute(f"PRAGMA table_info({table})")
        cols = [r["name"] for r in cur.fetchall()]
        fk_like_cols = [c for c in cols if c.lower() in ("sector_id", "sector_data_id")]
        for col in fk_like_cols:
            cur.execute(
                f"SELECT COUNT(*) c FROM {table} WHERE {col} IN "
                f"({','.join('?' for _ in candidates)})",
                [row["id"] for row in candidates],
            )
            count = cur.fetchone()["c"]
            if count:
                dependent_rows_found[f"{table}.{col}"] = count

    manifest["dependent_tables_checked"] = len(other_tables)
    manifest["dependent_rows_found"] = dependent_rows_found

    if dependent_rows_found:
        manifest["status"] = "aborted_dependent_rows_found"
        print(json.dumps(manifest, indent=2, default=str))
        con.close()
        return 1

    # ── Reconfirm every candidate satisfies ALL required conditions —
    #    never trust yesterday's read. ──────────────────────────────────
    qualifying_ids: list[str] = []
    disqualified: list[dict] = []
    for row in candidates:
        expected = _EXPECTED_ROWS.get(row["id"])
        conditions = {
            "id_is_a_known_seed_row": expected is not None,
            "name_matches_seed": expected is not None and row["name"] == expected[0],
            "value_matches_seed": expected is not None and row["value"] == expected[1],
            "positive_matches_seed": expected is not None and bool(row["positive"]) == expected[2],
            "updated_at_is_seed_insertion_timestamp": (row["updated_at"] or "").startswith(_SEEDED_AT),
        }
        if all(conditions.values()):
            qualifying_ids.append(row["id"])
        else:
            disqualified.append({"id": row["id"], "conditions": conditions})

    manifest["qualifying_count"] = len(qualifying_ids)
    manifest["disqualified"] = disqualified

    if disqualified:
        manifest["status"] = "aborted_disqualified_rows_found"
        print(json.dumps(manifest, indent=2, default=str))
        con.close()
        return 1

    if len(qualifying_ids) != 12:
        manifest["status"] = "aborted_unexpected_row_count"
        print(json.dumps(manifest, indent=2, default=str))
        con.close()
        return 1

    if mode == "dry_run":
        manifest["status"] = "dry_run_ok_would_delete"
        print(json.dumps(manifest, indent=2, default=str))
        con.close()
        return 0

    # ── mode == "apply" ──────────────────────────────────────────────────
    placeholders = ",".join("?" for _ in qualifying_ids)
    try:
        cur.execute("BEGIN")
        cur.execute(f"DELETE FROM sector_data WHERE id IN ({placeholders})", qualifying_ids)
        affected = cur.rowcount
        if affected != 12:
            con.rollback()
            manifest["status"] = "rolled_back_rowcount_mismatch"
            manifest["expected_affected"] = 12
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
