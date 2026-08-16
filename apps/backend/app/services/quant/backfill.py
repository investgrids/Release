"""
Historical OHLCV backfill — Phase 2B §3/§6.

Fetches daily history per symbol via yfinance (the only provider this
app has ever validated for multi-year daily history — Phase 2A §1) and
upserts into PriceBar. `auto_adjust=True` throughout, matching every
other yfinance call site in this app (Phase 2A §5's grounded
conclusion: this app has only ever validated adjusted OHLCV, so that's
what Kronos should receive too).

Idempotent: re-running a backfill for a symbol/date range that's
already stored updates existing rows in place (a data-quality flag can
change on rerun) rather than duplicating them — enforced by PriceBar's
own (symbol, timeframe, bar_date) unique constraint, but this module
does an explicit select-then-branch upsert rather than relying on a
database-level ON CONFLICT clause, so it behaves identically regardless
of which backend (SQLite locally, Postgres in prod) is underneath.
"""
from __future__ import annotations

import asyncio
import math
from datetime import date, datetime, timezone
from uuid import uuid4

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.price_bar import PriceBar
from app.services.quant.symbols import to_yfinance

log = structlog.get_logger(__name__)

# Data-quality thresholds — deliberately conservative flags, not filters.
# A flagged bar is still stored (Phase 2A §28: "a prediction should not
# exist if input is unusable" applies to the *prediction* step, not to
# warehouse storage — we keep every real bar, just label the doubtful
# ones so a consumer can decide).
_GAP_DAYS_THRESHOLD = 7      # >1 week between consecutive bars -> gap_detected
_SINGLE_DAY_MOVE_THRESHOLD = 0.20   # >20% single-day move on auto_adjust=True data -> corporate_action_uncertain (adjustment may have misfired)


def _fetch_symbol_history_sync(symbol: str, period: str) -> list[dict]:
    """One symbol's daily OHLCV via yfinance. Runs in executor. Empty list on any failure — same graceful-degradation convention as every other yfinance call site in this app (Phase 2A §1's reliability notes)."""
    try:
        import yfinance as yf

        ticker = to_yfinance(symbol)
        hist = yf.download(ticker, period=period, interval="1d", progress=False, auto_adjust=True, timeout=15)
        if hist is None or hist.empty:
            return []

        rows: list[dict] = []
        for ts, row in hist.iterrows():
            try:
                o, h, l, c = (float(row[col].iloc[0] if hasattr(row[col], "iloc") else row[col])
                              for col in ("Open", "High", "Low", "Close"))
                vol = row.get("Volume")
                v = int(vol.iloc[0] if hasattr(vol, "iloc") else vol) if vol is not None and not (isinstance(vol, float) and math.isnan(vol)) else None
            except Exception:
                continue
            if any(math.isnan(x) for x in (o, h, l, c)) or c <= 0:
                continue
            bar_date = ts.date() if hasattr(ts, "date") else ts
            rows.append({"bar_date": bar_date, "open": round(o, 2), "high": round(h, 2),
                          "low": round(l, 2), "close": round(c, 2), "volume": v})
        return rows
    except Exception as exc:
        log.warning("backfill.symbol_fetch_failed", symbol=symbol, error=str(exc)[:160])
        return []


async def _fetch_symbol_history(symbol: str, period: str) -> list[dict]:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _fetch_symbol_history_sync, symbol, period)


def _classify_quality(rows: list[dict]) -> list[dict]:
    """Adds a `data_quality` field to each row in place-order — gap
    detection compares each bar to the PREVIOUS row in the already-
    chronological yfinance result, single-day-move detection compares
    close-to-close, both real signals over the actual fetched series,
    never guessed."""
    out = []
    prev: dict | None = None
    for r in rows:
        quality = "good"
        if prev is not None:
            gap = (r["bar_date"] - prev["bar_date"]).days
            if gap > _GAP_DAYS_THRESHOLD:
                quality = "gap_detected"
            elif prev["close"] > 0:
                move = abs(r["close"] / prev["close"] - 1)
                if move > _SINGLE_DAY_MOVE_THRESHOLD:
                    quality = "corporate_action_uncertain"
        if r.get("volume") in (None, 0):
            quality = "thin_volume" if quality == "good" else quality
        out.append({**r, "data_quality": quality})
        prev = r
    return out


async def upsert_price_bars(db: AsyncSession, symbol: str, rows: list[dict], source: str = "yfinance") -> tuple[int, int]:
    """Idempotent bulk upsert for one symbol's rows. Returns (inserted, updated)."""
    if not rows:
        return (0, 0)

    dates = [r["bar_date"] for r in rows]
    existing = {
        row.bar_date: row
        for row in (await db.execute(
            select(PriceBar).where(PriceBar.symbol == symbol, PriceBar.timeframe == "1d", PriceBar.bar_date.in_(dates))
        )).scalars().all()
    }

    inserted = updated = 0
    now = datetime.now(timezone.utc)
    for r in rows:
        existing_row = existing.get(r["bar_date"])
        if existing_row is None:
            db.add(PriceBar(
                id=str(uuid4()), symbol=symbol, timeframe="1d", bar_date=r["bar_date"],
                open=r["open"], high=r["high"], low=r["low"], close=r["close"], volume=r.get("volume"),
                is_adjusted=True, source=source, data_quality=r["data_quality"], ingested_at=now,
            ))
            inserted += 1
        else:
            existing_row.open = r["open"]
            existing_row.high = r["high"]
            existing_row.low = r["low"]
            existing_row.close = r["close"]
            existing_row.volume = r.get("volume")
            existing_row.data_quality = r["data_quality"]
            existing_row.ingested_at = now
            updated += 1
    return (inserted, updated)


async def backfill_symbol(db: AsyncSession, symbol: str, period: str = "5y") -> dict:
    """Fetch + classify + upsert one symbol. Commits internally so one
    symbol's failure never rolls back another's already-stored history
    (same per-item isolation convention as evidence_window.py's
    collect_evidence_since, Phase 1E)."""
    raw = await _fetch_symbol_history(symbol, period)
    if not raw:
        return {"symbol": symbol, "fetched": 0, "inserted": 0, "updated": 0, "ok": False}
    rows = _classify_quality(raw)
    try:
        inserted, updated = await upsert_price_bars(db, symbol, rows)
        await db.commit()
        return {"symbol": symbol, "fetched": len(rows), "inserted": inserted, "updated": updated, "ok": True}
    except Exception as exc:
        await db.rollback()
        log.error("backfill.symbol_upsert_failed", symbol=symbol, error=str(exc)[:160])
        return {"symbol": symbol, "fetched": len(rows), "inserted": 0, "updated": 0, "ok": False}


async def backfill_universe(db: AsyncSession, symbols: list[str], period: str = "5y", delay_sec: float = 0.5) -> dict:
    """Sequential backfill over a symbol list — deliberately not
    parallel: Phase 2A §1 documents yfinance throttling hard above ~6
    concurrent requests elsewhere in this app (graph.py's own
    semaphore-guarded fetcher); a one-time backfill isn't latency-
    sensitive enough to risk that."""
    results = []
    for sym in symbols:
        results.append(await backfill_symbol(db, sym, period))
        await asyncio.sleep(delay_sec)
    ok = [r for r in results if r["ok"]]
    return {
        "total_symbols": len(symbols),
        "succeeded": len(ok),
        "failed": len(symbols) - len(ok),
        "total_bars_inserted": sum(r["inserted"] for r in results),
        "total_bars_updated": sum(r["updated"] for r in results),
        "per_symbol": results,
    }
