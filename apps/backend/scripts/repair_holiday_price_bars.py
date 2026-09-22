"""
Guarded, idempotent repair for the 49 contaminated 2026-09-14 (Ganesh
Chaturthi) PriceBar rows (2026-09-22 read-only audit finding).

Provenance: the price-bar ingestion job (app/services/quant/backfill.py,
via quant/refresh.py's daily scheduled refresh) stored a flat, zero-
volume "bar" for all 49 tracked symbols on 2026-09-14 — a verified NSE
holiday, confirmed live via app.services.market_calendar.
is_nse_trading_holiday — because nothing checked bar_date against the
trading calendar before writing it. Ingested 2026-09-20 11:00 UTC (a
backfill/catch-up run swept it in 6 days after the fact). The ingestion
guard (is_valid_nse_trading_session, deployed separately — see
scripts/repair_leaked_seed_events.py's own precedent for why code and
data changes are kept in separate, sequenced steps) now rejects this
class of row outright; this script only removes the 49 rows that
predate that guard.

Only ever matches rows satisfying ALL of:
  - bar_date = 2026-09-14
  - volume = 0
  - open = high = low = close
  - close = the same symbol's 2026-09-11 close (the prior real session)
  - 2026-09-14 fails is_valid_nse_trading_session (defense in depth —
    this script re-derives the same verdict the deployed guard uses,
    rather than trusting the date alone)

Usage — no argv (piped to `python3 -` over `railway ssh`), mode via the
REPAIR_MODE environment variable:

  REPAIR_MODE=dry_run   (default, safe) — runs every check, prints the
                          full manifest and what WOULD happen, makes
                          zero writes.
  REPAIR_MODE=apply     — after every check passes, deletes the exact
                          rows in one transaction; requires exactly 49
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
from datetime import date, datetime, timezone

_CONTAMINATED_DATE = date(2026, 9, 14)
_PRIOR_SESSION_DATE = date(2026, 9, 11)


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

    sys.path.insert(0, "/app")
    from app.services.market_calendar import is_valid_nse_trading_session

    if is_valid_nse_trading_session(_CONTAMINATED_DATE):
        # Defense in depth: if the calendar ever disagrees with this
        # script's hardcoded target date (e.g. the holiday list is
        # edited later), refuse outright rather than deleting real data.
        print(f"{_CONTAMINATED_DATE.isoformat()} is a valid trading session per the current calendar — aborting")
        return 1

    db_path = _db_path()
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    cur.execute("""
        SELECT id, symbol, timeframe, bar_date, open, high, low, close, volume,
               source, data_quality, ingested_at
        FROM price_bars WHERE bar_date = ?
    """, (_CONTAMINATED_DATE.isoformat(),))
    candidates = [dict(r) for r in cur.fetchall()]

    if not candidates:
        print(json.dumps({
            "status": "nothing_to_do", "mode": mode,
            "reason": f"no price_bars rows for {_CONTAMINATED_DATE.isoformat()} — already repaired",
            "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        }, indent=2))
        return 0

    manifest = {
        "description": "Holiday-contaminated PriceBar repair — see this script's own module docstring.",
        "mode": mode,
        "exported_at_utc": datetime.now(timezone.utc).isoformat(),
        "contaminated_date": _CONTAMINATED_DATE.isoformat(),
        "candidate_count": len(candidates),
        "rows_before_delete": candidates,
    }

    # ── Reconfirm every candidate satisfies ALL required conditions —
    #    never trust yesterday's read; every row is re-verified fresh
    #    against its own symbol's prior-session close. ──────────────────
    qualifying_ids: list[str] = []
    disqualified: list[dict] = []
    for row in candidates:
        cur.execute(
            "SELECT close FROM price_bars WHERE symbol = ? AND bar_date = ?",
            (row["symbol"], _PRIOR_SESSION_DATE.isoformat()),
        )
        prior = cur.fetchone()
        prior_close = prior["close"] if prior else None

        conditions = {
            "bar_date_is_contaminated_date": row["bar_date"] == _CONTAMINATED_DATE.isoformat(),
            "volume_is_zero": row["volume"] == 0,
            "ohlc_flat": row["open"] == row["high"] == row["low"] == row["close"],
            "matches_prior_session_close": prior_close is not None and row["close"] == prior_close,
            "non_trading_date": not is_valid_nse_trading_session(_CONTAMINATED_DATE),
        }
        if all(conditions.values()):
            qualifying_ids.append(row["id"])
        else:
            disqualified.append({"id": row["id"], "symbol": row["symbol"], "conditions": conditions})

    manifest["qualifying_count"] = len(qualifying_ids)
    manifest["disqualified"] = disqualified

    if disqualified:
        manifest["status"] = "aborted_disqualified_rows_found"
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
        cur.execute(f"DELETE FROM price_bars WHERE id IN ({placeholders})", qualifying_ids)
        affected = cur.rowcount
        if affected != len(qualifying_ids):
            con.rollback()
            manifest["status"] = "rolled_back_rowcount_mismatch"
            manifest["expected_affected"] = len(qualifying_ids)
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
