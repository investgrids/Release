"""
Production MarketRipple Score refresh (owner decision 2026-09-28: compute
and publish). Candidates are every company in the real Companies directory
whose sector the method supports (coverage.sector_candidates), not just the
curated `_NSE_UNIVERSE` list. Each sector is computed with the shared-fetch
pattern (its peer/benchmark data fetched once), every candidate is scored
against the same full directory peer set, and the whole sector is committed
in ONE transaction — readers never see a sector with mixed old/new peer
sets, and a run that dies mid-sector writes nothing for it. Banks follow,
against their own universe (Banking's pillars take no shared cache).

Runs ONLY in its own OS process (scripts/run_marketripple_score_refresh.py),
started by start_refresh_process(). The first production run executed inside
the web worker: hundreds of yfinance downloads + pandas parsing starved the
worker for >120s, gunicorn killed it (SIGABRT), the site stalled and the run
died after 23 companies with empty scores. A separate, lower-priority process
has its own interpreter and event loop, so the web workers stay responsive.

Writes only new MarketRippleScoreSnapshot rows (insert-only, history kept);
publishable is decided per row by engine.py + snapshot.py, never here.
Per-company failures are recorded and never abort the run. A lock file keeps
it to one run at a time; progress and the final summary (with per-sector
runtime, coverage and score movement) are files on the persistent volume.
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


def start_refresh_process(include_banks: bool = True, sectors: list[str] | None = None) -> dict[str, Any]:
    """Start one refresh in a separate, low-priority process. Returns at once.
    `sectors` limits the run (e.g. a two-sector pilot); None = everything."""
    pid = _running_pid()
    if pid:
        return {"started": False, "reason": "a refresh is already running", "pid": pid}
    cmd = [sys.executable, "-u", "scripts/run_marketripple_score_refresh.py"]
    if not include_banks:
        cmd.append("--no-banks")
    if sectors:
        cmd += ["--sectors", ",".join(sectors)]
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
    log.info("marketripple_score.refresh.process_started", pid=proc.pid, sectors=sectors)
    return {"started": True, "pid": proc.pid, "sectors": sectors}


def _bucket(snap) -> str:
    if snap.score is not None:
        return "numeric"
    if any(v is not None for v in (snap.financial_strength, snap.valuation, snap.market_behaviour, snap.current_intelligence)):
        return "partial"
    return "unusable"


def _tally_snapshot(snap, tally: dict) -> None:
    tally[_bucket(snap)] += 1
    for reason in snap.publication_block_reasons or []:
        tally["block_reasons"][reason] = tally["block_reasons"].get(reason, 0) + 1
    for p in ("financial_strength", "valuation", "market_behaviour"):
        if getattr(snap, p) is None:
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


async def _previous_published(symbols: list[str]) -> dict[str, tuple[float, str | None]]:
    """symbol -> (score, rating) of each company's current public score,
    read before its sector is recomputed, to measure score movement."""
    from app.db.session import AsyncSessionLocal
    from app.services.marketripple_score.public_projection import is_publicly_published
    from app.services.marketripple_score.snapshot import get_latest_snapshot

    out: dict[str, tuple[float, str | None]] = {}
    async with AsyncSessionLocal() as db:
        for s in symbols:
            snap = await get_latest_snapshot(db, s)
            if snap is not None and is_publicly_published(snap) and snap.score is not None:
                out[s] = (snap.score, snap.rating)
    return out


def _movement(before: dict[str, tuple[float, str | None]], built: list) -> dict[str, Any]:
    """How previously-public scores moved: value, rating band, and position in
    the sector's ranking (adding peers shifts ranks even when a score barely moves)."""
    from app.services.marketripple_score.public_projection import is_publicly_published

    after = {s.symbol: s for s in built if is_publicly_published(s) and s.score is not None}
    order_before = sorted(before, key=lambda k: -before[k][0])
    order_after = sorted(after, key=lambda k: -after[k].score)
    rank_before = {k: i + 1 for i, k in enumerate(order_before)}
    rank_after = {k: i + 1 for i, k in enumerate(order_after)}
    deltas: list[float] = []
    pct_shift: list[float] = []
    rating_changes = 0
    lost = [k for k in before if k in {s.symbol for s in built} and k not in after]
    for sym, (score, rating) in before.items():
        snap = after.get(sym)
        if snap is None:
            continue
        deltas.append(abs(snap.score - score))
        rating_changes += int(snap.rating != rating)
        pct_shift.append(abs(rank_after[sym] / len(after) - rank_before[sym] / len(before)) * 100)
    deltas.sort()
    return {
        "previously_public": len(before), "public_after": len(after),
        "compared": len(deltas), "lost_public_score": len(lost), "lost_symbols": lost[:20],
        "mean_abs_change": round(sum(deltas) / len(deltas), 2) if deltas else None,
        "median_abs_change": round(deltas[len(deltas) // 2], 2) if deltas else None,
        "max_abs_change": round(deltas[-1], 1) if deltas else None,
        "rating_band_changes": rating_changes,
        "mean_rank_position_shift_pct": round(sum(pct_shift) / len(pct_shift), 1) if pct_shift else None,
        "max_rank_position_shift_pct": round(max(pct_shift), 1) if pct_shift else None,
    }


async def _build_and_commit(sector: str, symbols: list[str], peer_group: list[str] | None,
                            cache: dict | None, tally: dict) -> dict[str, Any]:
    """Build every company's snapshot, then commit the whole sector in ONE
    transaction: readers see either the previous complete sector or the new
    complete one, never a mix of peer sets. A crash mid-sector writes nothing."""
    from app.db.session import AsyncSessionLocal
    from app.services.marketripple_score.snapshot import build_snapshot

    t0 = time.perf_counter()
    before = await _previous_published(symbols)
    built: list = []
    errors = 0
    async with AsyncSessionLocal() as db:
        for symbol in symbols:
            _progress(sector, symbol, tally)
            tally["attempted"] += 1
            try:
                built.append(await build_snapshot(db, symbol, peer_group=peer_group, industrial_cache=cache))
            except Exception as exc:  # one company never aborts the sector
                errors += 1
                tally["errors"].append({"symbol": symbol, "error": f"{type(exc).__name__}: {exc}"[:300]})
            await asyncio.sleep(PAUSE_BETWEEN_COMPANIES_S)
        if errors:
            # All-or-nothing: a sector with ANY failed company is not switched, so
            # Rankings never mixes companies scored against different peer sets.
            await db.rollback()
            built = []
        else:
            db.add_all(built)
            await db.commit()
    for snap in built:
        _tally_snapshot(snap, tally)
    from collections import Counter

    from app.services.marketripple_score.data_quality import snapshot_data_quality_reasons
    from app.services.marketripple_score.public_projection import is_publicly_published

    na: Counter = Counter()
    for b in built:
        if is_publicly_published(b):
            continue
        reasons = list(b.publication_block_reasons or []) + [r for r in snapshot_data_quality_reasons(b) if r not in (b.publication_block_reasons or [])]
        if b.score is None and not reasons:
            reasons = ["NO_HEADLINE_SCORE (a required pillar is missing)"]
        for r in (reasons or ["NOT_PUBLISHABLE"]):
            na[r] += 1
    return {
        "candidates": len(symbols),
        "committed": errors == 0,  # False = sector left untouched (see the all-or-nothing rule above)
        "numeric": sum(1 for b in built if b.score is not None),
        "published": sum(1 for b in built if is_publicly_published(b)),
        "na_reasons": dict(na.most_common()),
        "errors": errors,
        "elapsed_s": round(time.perf_counter() - t0, 1),
        "score_movement": _movement(before, built),
    }


async def _refresh_sector(
    sector: str, universe: list[str], tally: dict, market_cutoff_date: date | None = None,
) -> dict[str, Any] | None:
    from app.services.marketripple_score.financial_strength_industrial import prefetch_industrial_inputs
    from app.services.marketripple_score.market_behaviour import (
        _NIFTY_TICKER, _SECTOR_ETFS, _SECTOR_LABEL_TO_ETF_KEY,
    )
    from app.services.marketripple_score.market_behaviour import (
        _fetch_daily_close_observations_sync, completed_session_cutoff_date,
    )
    from app.services.marketripple_score.valuation import prefetch_valuation_snapshots

    if not universe:
        return None
    market_cutoff_date = market_cutoff_date or completed_session_cutoff_date()
    t0 = time.perf_counter()
    _progress(sector, "(prefetching sector data)", tally)
    loop = asyncio.get_running_loop()
    sector_ticker = _SECTOR_ETFS.get(_SECTOR_LABEL_TO_ETF_KEY.get(sector, sector))
    tickers = [_NIFTY_TICKER] + ([sector_ticker] if sector_ticker else [])
    observations = await asyncio.gather(*[
        loop.run_in_executor(None, _fetch_daily_close_observations_sync, ticker)
        for ticker in tickers
    ])
    benchmarks_fetched_at = datetime.now(timezone.utc).isoformat()
    cache = {
        "financial_inputs": await prefetch_industrial_inputs(universe),
        "valuation_snapshots": await prefetch_valuation_snapshots(universe),
        "benchmarks": dict(zip(tickers, observations)),
        "market_cutoff_date": market_cutoff_date.isoformat(),
        "benchmarks_fetched_at": benchmarks_fetched_at,
    }
    prefetch_s = round(time.perf_counter() - t0, 1)
    # Every candidate is scored against the same full directory peer set.
    stats = await _build_and_commit(sector, universe, universe, cache, tally)
    stats["prefetch_s"] = prefetch_s
    stats["elapsed_s"] = round(time.perf_counter() - t0, 1)
    return stats


async def refresh_all_scores(include_banks: bool = True, sectors: list[str] | None = None) -> dict[str, Any]:
    """Run one refresh in the CURRENT process. Call only from
    scripts/run_marketripple_score_refresh.py (never from a web worker).
    `sectors` limits the run (e.g. a two-sector pilot); None = all."""
    from app.db.session import AsyncSessionLocal
    from app.services.marketripple_score.banking_universe import ALL_ELIGIBLE_NSE_BANKS
    from app.services.marketripple_score.coverage import sector_candidates
    from app.services.marketripple_score.market_behaviour import completed_session_cutoff_date

    started = datetime.now(timezone.utc)
    market_cutoff_date = completed_session_cutoff_date(started)
    t0 = time.perf_counter()
    tally: dict[str, Any] = {
        "attempted": 0, "numeric": 0, "partial": 0, "unusable": 0, "published": 0,
        "ratings": {}, "block_reasons": {}, "missing_pillars": {}, "errors": [], "sector_failures": [],
        "sectors": {}, "requested_sectors": sectors,
    }
    async with AsyncSessionLocal() as db:
        candidates = await sector_candidates(db)
    if sectors:
        candidates = {s: v for s, v in candidates.items() if s in sectors}
        include_banks = include_banks and "Banking" in sectors
    log.info("marketripple_score.refresh.start", sectors=list(candidates),
             candidates=sum(len(v) for v in candidates.values()),
             banks=len(ALL_ELIGIBLE_NSE_BANKS) if include_banks else 0)
    try:
        for sector, universe in candidates.items():
            try:
                stats = await _refresh_sector(sector, universe, tally, market_cutoff_date)
                if stats:
                    tally["sectors"][sector] = stats
            except Exception as exc:
                tally["sector_failures"].append({"sector": sector, "error": f"{type(exc).__name__}: {exc}"[:300]})
        if include_banks:
            # Banking's pillars take no shared cache; its peer group is its own universe.
            banking_cache = {
                "market_cutoff_date": market_cutoff_date.isoformat(),
                "benchmarks_fetched_at": datetime.now(timezone.utc).isoformat(),
            }
            tally["sectors"]["Banking"] = await _build_and_commit(
                "Banking", list(ALL_ELIGIBLE_NSE_BANKS), None, banking_cache, tally,
            )
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
