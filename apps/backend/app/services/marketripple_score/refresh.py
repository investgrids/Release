"""
Production MarketRipple Score refresh (owner decision 2026-09-28: compute
and publish). Computes and persists a fresh snapshot for every company the
methodology supports — each NONBANK_INDUSTRIAL_SECTORS sector with the same
shared-fetch pattern as scripts/s11_shared_fetch_sector_backfill.py (the
sector's peer/benchmark data fetched once, not once per company), then every
eligible NSE bank one by one (Banking's pillars take no shared cache).

Runs ONLY in its own OS process (scripts/run_marketripple_score_refresh.py),
started by start_refresh_process(). The first production run executed inside
the web worker: hundreds of yfinance downloads + pandas parsing starved the
worker for >120s, gunicorn killed it (SIGABRT), the site stalled and the run
died after 23 companies with empty scores. A separate, lower-priority process
has its own interpreter and event loop, so the web workers stay responsive.

Writes only new MarketRippleScoreSnapshot rows (insert-only, history kept);
publishable is decided per row by engine.py + snapshot.py, never here.
Per-company failures are recorded and never abort the run. A lock file keeps
it to one run at a time; progress and the final summary are files on the
persistent volume, so status survives worker restarts.
"""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import structlog

log = structlog.get_logger(__name__)

PAUSE_BETWEEN_COMPANIES_S = 0.5
_BACKEND_ROOT = Path(__file__).resolve().parents[3]


def _report_dir() -> Path:
    # /data is the persistent Railway volume; fall back to a local folder.
    base = Path("/data") if Path("/data").is_dir() else _BACKEND_ROOT / "artifacts"
    d = base / "marketripple_score_refresh"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _lock_path() -> Path:
    return _report_dir() / "running.lock"


_proc: subprocess.Popen | None = None  # the child this worker started, reaped via poll()


def _pid_alive(pid: int) -> bool:
    if _proc is not None and _proc.pid == pid:
        code = _proc.poll()  # also reaps a finished child (no zombie)
        if code is not None:
            _write_json("last_exit.json", {"pid": pid, "exit_code": code, "at": datetime.now(timezone.utc).isoformat()})
        return code is None
    if os.name == "nt":
        return True  # os.kill(pid, 0) terminates on Windows; trust the lock file
    try:
        os.kill(pid, 0)
    except (OSError, SystemError):
        return False
    return True


def _running_pid() -> int | None:
    try:
        pid = int(_lock_path().read_text().strip())
    except (OSError, ValueError):
        return None
    return pid if _pid_alive(pid) else None


def _write_json(name: str, data: dict) -> None:
    try:
        (_report_dir() / name).write_text(json.dumps(data, indent=2), encoding="utf-8")
    except OSError as exc:
        log.warning("marketripple_score.refresh.write_failed", file=name, error=str(exc))


def _read_json(name: str) -> dict | None:
    try:
        return json.loads((_report_dir() / name).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def refresh_status() -> dict[str, Any]:
    pid = _running_pid()
    return {
        "running": pid is not None,
        "pid": pid,
        "progress": _read_json("progress.json") if pid else None,
        "last_run": _read_json("last_run.json"),
        "last_exit": _read_json("last_exit.json"),
    }


def start_refresh_process(include_banks: bool = True) -> dict[str, Any]:
    """Start one refresh in a separate, low-priority process. Returns at once."""
    pid = _running_pid()
    if pid:
        return {"started": False, "reason": "a refresh is already running", "pid": pid}
    cmd = [sys.executable, "-u", "scripts/run_marketripple_score_refresh.py"]
    if not include_banks:
        cmd.append("--no-banks")
    log_file = open(_report_dir() / "last_run.log", "w", encoding="utf-8")  # noqa: SIM115 — owned by the child
    # Own session: signals aimed at the web worker's process group never reach
    # it. (Priority is lowered inside the script; preexec_fn is unsafe in a
    # threaded parent like a uvicorn worker.)
    kwargs: dict[str, Any] = {"cwd": str(_BACKEND_ROOT), "stdout": log_file, "stderr": subprocess.STDOUT,
                              "stdin": subprocess.DEVNULL}
    if os.name != "nt":
        kwargs["start_new_session"] = True
    global _proc
    proc = _proc = subprocess.Popen(cmd, **kwargs)
    log_file.close()
    _lock_path().write_text(str(proc.pid))
    log.info("marketripple_score.refresh.process_started", pid=proc.pid)
    return {"started": True, "pid": proc.pid}


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
    for reason in snap.publication_block_reasons or []:
        tally["block_reasons"][reason] = tally["block_reasons"].get(reason, 0) + 1
    missing = [p for p in ("financial_strength", "valuation", "market_behaviour") if getattr(snap, p) is None]
    for p in missing:
        tally["missing_pillars"][p] = tally["missing_pillars"].get(p, 0) + 1
    if snap.publishable:
        tally["published"] += 1
        tally["ratings"][snap.rating or "?"] = tally["ratings"].get(snap.rating or "?", 0) + 1


def _progress(sector: str, symbol: str, tally: dict) -> None:
    _write_json("progress.json", {
        "sector": sector, "symbol": symbol, "done": tally["attempted"],
        "published": tally["published"], "errors": len(tally["errors"]),
        "at": datetime.now(timezone.utc).isoformat(),
    })


async def _refresh_sector(sector: str, tally: dict, market_cutoff_date: date | None = None) -> None:
    from app.services.marketripple_score.financial_strength_industrial import prefetch_industrial_inputs
    from app.services.marketripple_score.market_behaviour import (
        _NIFTY_TICKER, _SECTOR_ETFS, _SECTOR_LABEL_TO_ETF_KEY, _fetch_daily_close_observations_sync,
        completed_session_cutoff_date,
    )
    from app.services.marketripple_score.sector_universe import sector_peer_universe
    from app.services.marketripple_score.valuation import prefetch_valuation_snapshots

    universe = sector_peer_universe(sector)
    if not universe:
        return
    _progress(sector, "(prefetching sector data)", tally)
    loop = asyncio.get_running_loop()
    sector_ticker = _SECTOR_ETFS.get(_SECTOR_LABEL_TO_ETF_KEY.get(sector, sector))
    tickers = [_NIFTY_TICKER] + ([sector_ticker] if sector_ticker else [])
    # One cutoff and one benchmark retrieval time for the whole sector: every company in it
    # is scored against the same completed sessions (today's candle is excluded until 16:00 IST).
    market_cutoff_date = market_cutoff_date or completed_session_cutoff_date()
    observations = await asyncio.gather(*[
        loop.run_in_executor(None, _fetch_daily_close_observations_sync, t) for t in tickers
    ])
    benchmarks_fetched_at = datetime.now(timezone.utc).isoformat()
    cache = {
        "financial_inputs": await prefetch_industrial_inputs(universe),
        "valuation_snapshots": await prefetch_valuation_snapshots(universe),
        "benchmarks": dict(zip(tickers, observations)),
        "market_cutoff_date": market_cutoff_date.isoformat(),
        "benchmarks_fetched_at": benchmarks_fetched_at,
    }
    for symbol in universe:
        _progress(sector, symbol, tally)
        tally["attempted"] += 1
        await _persist(symbol, cache, tally)
        await asyncio.sleep(PAUSE_BETWEEN_COMPANIES_S)


async def refresh_all_scores(include_banks: bool = True) -> dict[str, Any]:
    """Run one full refresh in the CURRENT process. Call only from
    scripts/run_marketripple_score_refresh.py (never from a web worker)."""
    from app.services.marketripple_score.banking_universe import ALL_ELIGIBLE_NSE_BANKS
    from app.services.marketripple_score.sector_universe import NONBANK_INDUSTRIAL_SECTORS

    started = datetime.now(timezone.utc)
    from app.services.marketripple_score.market_behaviour import completed_session_cutoff_date

    market_cutoff_date = completed_session_cutoff_date(started)  # one cutoff for the whole run
    t0 = time.perf_counter()
    tally: dict[str, Any] = {
        "attempted": 0, "numeric": 0, "partial": 0, "unusable": 0, "published": 0,
        "ratings": {}, "block_reasons": {}, "missing_pillars": {}, "errors": [], "sector_failures": [],
        "market_cutoff_date": market_cutoff_date.isoformat(),
    }
    log.info("marketripple_score.refresh.start", sectors=len(NONBANK_INDUSTRIAL_SECTORS),
             banks=len(ALL_ELIGIBLE_NSE_BANKS) if include_banks else 0)
    try:
        for sector in NONBANK_INDUSTRIAL_SECTORS:
            try:
                await _refresh_sector(sector, tally, market_cutoff_date)
            except Exception as exc:
                tally["sector_failures"].append({"sector": sector, "error": f"{type(exc).__name__}: {exc}"[:300]})
        if include_banks:
            for symbol in ALL_ELIGIBLE_NSE_BANKS:
                _progress("Banking", symbol, tally)
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
        _write_json("last_run.json", summary)
        _write_json(f"refresh_{started.strftime('%Y%m%dT%H%M%SZ')}.json", summary)
        log.info(
            "marketripple_score.refresh.done",
            attempted=summary["attempted"], numeric=summary["numeric"], published=summary["published"],
            partial=summary["partial"], unusable=summary["unusable"], errors=summary["error_count"],
            elapsed_s=summary["elapsed_s"],
        )
    return summary
