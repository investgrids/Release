"""
One refresh = one immutable run. Activation is a separate, guarded step: a run that scores far fewer companies than the active one (a broken source, an NSE
outage) is completed and kept for inspection but NOT activated automatically.
"""
from __future__ import annotations

import asyncio
import os
import time
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.filing_score import store
from app.services.filing_score.pipeline import CONTRACTS, METHOD_VERSION, Collector, Company, score_universe

MIN_RATIO_OF_ACTIVE = 0.90   # a new run must score at least 90% as many companies as the active one to be activated automatically


async def load_universe(db: AsyncSession) -> list[Company]:
    """The production company universe exactly as the Companies directory builds it (get_full_company_directory: the static NSE universe plus the qualified
    company-master entries, with the site sector each company is shown under). A company with no sector gets an explicit NO_SECTOR_ASSIGNED row, never a guess.
    Inside a grouped sector the peer group comes from the explicit assignment file. CompanyEntity.sector is not used: it is empty in production."""
    from app.api.companies import get_full_company_directory
    from app.services.marketripple_score.peer_groups import GROUPED_SECTORS, peer_group_for
    out: dict[str, Company] = {}
    for row in await get_full_company_directory(db):
        sym, sec = row["symbol"], (row.get("sector") or None)
        out[sym] = Company(symbol=sym, sector=sec, peer_group=peer_group_for(sym) if sec in GROUPED_SECTORS else None)
    return sorted(out.values(), key=lambda c: c.symbol)


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


# ---- start / status for the admin endpoints (a separate process, never inside a web worker; NEVER activates: activation stays a deliberate, separate step) ----
def _report_dir() -> Path:
    return lock_path().parent


def _lock_pid() -> int | None:
    try:
        pid = int(lock_path().read_text().strip())
    except (OSError, ValueError):
        return None
    fresh = (time.time() - lock_path().stat().st_mtime) < 6 * 3600
    return pid if (pid > 0 and fresh and _pid_alive(pid)) else None


def start_refresh_process(symbols: list[str] | None = None) -> dict:
    import subprocess
    import sys
    pid = _lock_pid()
    if pid:
        return {"started": False, "reason": "a filing-score refresh is already running", "pid": pid}
    cmd = [sys.executable, "-u", "-m", "app.tasks.filing_score_refresh"]   # no --activate, by design
    if symbols:
        cmd += ["--symbols", ",".join(symbols)]
    log_file = open(_report_dir() / "last_run.log", "w", encoding="utf-8")  # noqa: SIM115 — owned by the child
    kwargs: dict = {"cwd": str(Path(__file__).resolve().parents[3]), "stdout": log_file, "stderr": subprocess.STDOUT, "stdin": subprocess.DEVNULL}
    if os.name != "nt":
        kwargs["start_new_session"] = True
    proc = subprocess.Popen(cmd, **kwargs)
    log_file.close()
    return {"started": True, "pid": proc.pid, "symbols": symbols, "activates": False}


def refresh_status() -> dict:
    pid = _lock_pid()
    tail = None
    try:
        tail = (_report_dir() / "last_run.log").read_text(encoding="utf-8", errors="replace")[-1500:]
    except OSError:
        pass
    return {"running": pid is not None, "pid": pid, "log_tail": tail}
