"""
One refresh = one immutable run. Activation is a separate, guarded step: a run that scores far fewer companies than the active one (a broken source, an NSE
outage) is completed and kept for inspection but NOT activated automatically.
"""
from __future__ import annotations

import asyncio
import os
import time
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.company_entity import CompanyEntity
from app.services.filing_score import store
from app.services.filing_score.pipeline import CONTRACTS, METHOD_VERSION, Collector, Company, score_universe

MIN_RATIO_OF_ACTIVE = 0.90   # a new run must score at least 90% as many companies as the active one to be activated automatically


async def load_universe(db: AsyncSession) -> list[Company]:
    """Every active NSE company in the company master. Sector is exactly what the master holds (never inferred); inside a grouped sector the company's
    peer group comes from the explicit assignment file."""
    from app.services.marketripple_score.peer_groups import GROUPED_SECTORS, peer_group_for
    rows = (await db.execute(select(CompanyEntity).where(CompanyEntity.exchange == "NSE", CompanyEntity.listing_status == "active"))).scalars().all()
    seen, out = set(), []
    for r in rows:
        if r.symbol in seen:
            continue
        seen.add(r.symbol)
        out.append(Company(symbol=r.symbol, sector=r.sector, peer_group=peer_group_for(r.symbol) if r.sector in GROUPED_SECTORS else None))
    return sorted(out, key=lambda c: c.symbol)


async def run_refresh(db: AsyncSession, collector: Collector, *, trigger: str = "manual", universe: list[Company] | None = None,
                      taxonomy: dict[str, str] | None = None, activate: bool = False, notes: str | None = None) -> dict:
    """Compute one run and persist it. Returns {run_id, status, counts, activated, activation_note}. The caller commits."""
    run = await store.start_run(db, METHOD_VERSION, trigger=trigger, contracts=CONTRACTS, notes=notes)
    try:
        uni = universe if universe is not None else await load_universe(db)
        rows, counts = await asyncio.to_thread(score_universe, uni, collector, taxonomy)   # collection is blocking network work
        await store.write_snapshots(db, run, rows)
        await store.complete_run(db, run, counts)
    except Exception as exc:
        await store.fail_run(db, run, f"{type(exc).__name__}: {exc}")
        return {"run_id": run.id, "status": "failed", "counts": None, "activated": False, "activation_note": str(exc)[:200]}
    activated, note = False, "not requested"
    if activate:
        prev = await store.active_run(db, METHOD_VERSION)
        prev_scored = ((prev.counts or {}).get("scored") if prev else None)
        if prev_scored and counts["scored"] < MIN_RATIO_OF_ACTIVE * prev_scored:
            note = f"not activated: scored {counts['scored']} vs {prev_scored} in the active run (< {int(MIN_RATIO_OF_ACTIVE * 100)}%)"
        else:
            await store.activate_run(db, run.id)
            activated, note = True, "activated"
    return {"run_id": run.id, "status": "complete", "counts": counts, "activated": activated, "activation_note": note}


# ---- single-process guard (same semantics as the existing score refresh: a lock file holding the pid, stale locks recovered) ----
def lock_path() -> Path:
    base = Path("/data") if Path("/data").is_dir() else Path(__file__).resolve().parents[3] / "artifacts"
    d = base / "filing_score_refresh"
    d.mkdir(parents=True, exist_ok=True)
    return d / "running.lock"


def _pid_alive(pid: int) -> bool:
    if os.name == "nt":
        return True   # os.kill(pid, 0) terminates on Windows; trust the lock file (a stale one is removed by hand or by max age)
    try:
        os.kill(pid, 0)
    except (OSError, SystemError):
        return False
    return True


def acquire_lock(max_age_s: int = 6 * 3600) -> bool:
    p = lock_path()
    if p.exists():
        try:
            pid = int(p.read_text().strip())
        except (OSError, ValueError):
            pid = -1
        fresh = (time.time() - p.stat().st_mtime) < max_age_s
        if pid > 0 and _pid_alive(pid) and fresh:
            return False
    p.write_text(str(os.getpid()))
    return True


def release_lock() -> None:
    try:
        lock_path().unlink()
    except OSError:
        pass
