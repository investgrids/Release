"""
Production MarketRipple Score refresh (owner decision 2026-09-28: compute
and publish). Computes and persists a fresh snapshot for every company the
methodology supports — each NONBANK_INDUSTRIAL_SECTORS sector with the same
shared-fetch pattern as scripts/s11_shared_fetch_sector_backfill.py (the
sector's peer/benchmark data fetched once, not once per company), then every
eligible NSE bank one by one (Banking's pillars take no shared cache).

Writes only new MarketRippleScoreSnapshot rows (insert-only, history kept);
publishable is decided per row by engine.py + snapshot.py, never here.
Per-company failures are recorded and never abort the run. A short pause
between companies keeps this batch from starving the site's own live
yfinance requests. Only one refresh can run at a time per process.

Triggered weekly by the scheduler and on demand by the admin endpoint
POST /api/admin/marketripple-score/refresh; each run's summary is kept in
memory (GET .../refresh/status) and saved as a JSON report.
"""
from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import structlog

log = structlog.get_logger(__name__)

PAUSE_BETWEEN_COMPANIES_S = 0.5

_lock = asyncio.Lock()
_state: dict[str, Any] = {"running": False, "last_run": None, "progress": None}


def refresh_status() -> dict[str, Any]:
    return dict(_state)


def _report_dir() -> Path:
    # /data is the persistent Railway volume; fall back to a local folder.
    base = Path("/data") if Path("/data").is_dir() else Path("artifacts")
    return base / "marketripple_score_refresh"


def _bucket(snap) -> str:
    if snap.score is not None:
        return "numeric"
    if any(v is not None for v in (snap.financial_strength, snap.valuation, snap.market_behaviour, snap.current_intelligence)):
        return "partial"
    return "unusable"


async def _persist(symbol: str, industrial_cache: dict | None, tally: dict) -> None:
    from app.db.session import AsyncSessionLocal
    from app.services.marketripple_score.snapshot import compute_and_persist_snapshot

    try:
        async with AsyncSessionLocal() as db:
            snap = await compute_and_persist_snapshot(db, symbol, industrial_cache=industrial_cache)
    except Exception as exc:  # one company never aborts the run
        tally["errors"].append({"symbol": symbol, "error": f"{type(exc).__name__}: {exc}"[:300]})
        return
    tally[_bucket(snap)] += 1
    if snap.publishable:
        tally["published"] += 1
        tally["ratings"][snap.rating or "?"] = tally["ratings"].get(snap.rating or "?", 0) + 1


async def _refresh_sector(sector: str, tally: dict) -> None:
    from app.services.marketripple_score.financial_strength_industrial import prefetch_industrial_inputs
    from app.services.marketripple_score.market_behaviour import (
        _NIFTY_TICKER, _SECTOR_ETFS, _SECTOR_LABEL_TO_ETF_KEY, _fetch_daily_closes_sync,
    )
    from app.services.marketripple_score.sector_universe import sector_peer_universe
    from app.services.marketripple_score.valuation import prefetch_valuation_snapshots

    universe = sector_peer_universe(sector)
    if not universe:
        return
    loop = asyncio.get_running_loop()
    sector_ticker = _SECTOR_ETFS.get(_SECTOR_LABEL_TO_ETF_KEY.get(sector, sector))
    tickers = [_NIFTY_TICKER] + ([sector_ticker] if sector_ticker else [])
    closes = await asyncio.gather(*[loop.run_in_executor(None, _fetch_daily_closes_sync, t) for t in tickers])
    cache = {
        "financial_inputs": await prefetch_industrial_inputs(universe),
        "valuation_snapshots": await prefetch_valuation_snapshots(universe),
        "benchmarks": dict(zip(tickers, closes)),
    }
    for symbol in universe:
        _state["progress"] = {"sector": sector, "symbol": symbol, "done": tally["attempted"]}
        tally["attempted"] += 1
        await _persist(symbol, cache, tally)
        await asyncio.sleep(PAUSE_BETWEEN_COMPANIES_S)


async def refresh_all_scores(include_banks: bool = True) -> dict[str, Any]:
    """Run one full refresh. Returns its summary, or {"skipped": ...} if a
    refresh is already running in this process."""
    from app.services.marketripple_score.banking_universe import ALL_ELIGIBLE_NSE_BANKS
    from app.services.marketripple_score.sector_universe import NONBANK_INDUSTRIAL_SECTORS

    if _lock.locked():
        return {"skipped": "a refresh is already running", "progress": _state["progress"]}
    async with _lock:
        _state["running"] = True
        started = datetime.now(timezone.utc)
        t0 = time.perf_counter()
        tally: dict[str, Any] = {
            "attempted": 0, "numeric": 0, "partial": 0, "unusable": 0, "published": 0,
            "ratings": {}, "errors": [], "sector_failures": [],
        }
        log.info("marketripple_score.refresh.start", sectors=len(NONBANK_INDUSTRIAL_SECTORS), banks=len(ALL_ELIGIBLE_NSE_BANKS) if include_banks else 0)
        try:
            for sector in NONBANK_INDUSTRIAL_SECTORS:
                try:
                    await _refresh_sector(sector, tally)
                except Exception as exc:
                    tally["sector_failures"].append({"sector": sector, "error": f"{type(exc).__name__}: {exc}"[:300]})
            if include_banks:
                for symbol in ALL_ELIGIBLE_NSE_BANKS:
                    _state["progress"] = {"sector": "Banking", "symbol": symbol, "done": tally["attempted"]}
                    tally["attempted"] += 1
                    await _persist(symbol, None, tally)
                    await asyncio.sleep(PAUSE_BETWEEN_COMPANIES_S)
        finally:
            summary = {
                **tally,
                "error_count": len(tally["errors"]),
                "started_at": started.isoformat(),
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "elapsed_s": round(time.perf_counter() - t0, 1),
            }
            _state.update(running=False, progress=None, last_run=summary)
            try:
                d = _report_dir()
                d.mkdir(parents=True, exist_ok=True)
                (d / f"refresh_{started.strftime('%Y%m%dT%H%M%SZ')}.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
            except OSError as exc:
                log.warning("marketripple_score.refresh.report_write_failed", error=str(exc))
            log.info(
                "marketripple_score.refresh.done",
                attempted=summary["attempted"], numeric=summary["numeric"], published=summary["published"],
                partial=summary["partial"], unusable=summary["unusable"], errors=summary["error_count"],
                elapsed_s=summary["elapsed_s"],
            )
        return summary
