"""
Persistence for the filing-backed score: immutable runs, atomic activation, rollback. Writers only append; readers only see the active run.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.filing_score import FilingScoreRun, FilingScoreSnapshot

_SNAPSHOT_FIELDS = (
    "symbol", "segment", "peer_group", "state", "score", "rating", "financial_strength", "valuation", "market_behaviour", "coverage_pct", "metrics_used",
    "withheld_reason", "na_label", "metadata_flags", "rule_tags", "metrics", "valuation_detail", "provenance", "inputs", "contract_version",
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def start_run(db: AsyncSession, method_version: str, trigger: str = "manual", contracts: dict | None = None, notes: str | None = None) -> FilingScoreRun:
    run = FilingScoreRun(method_version=method_version, status="running", trigger=trigger, contracts=contracts or {}, notes=notes)
    db.add(run)
    await db.flush()
    return run


async def write_snapshots(db: AsyncSession, run: FilingScoreRun, rows: list[dict]) -> int:
    """Append snapshot rows to a RUNNING run. A run that is complete (or failed) is immutable."""
    if run.status != "running":
        raise ValueError(f"run {run.id} is {run.status}: snapshots are append-only while running")
    seen: set[str] = set()
    for r in rows:
        sym = r["symbol"]
        if sym in seen:
            raise ValueError(f"duplicate symbol in one run: {sym}")
        seen.add(sym)
        db.add(FilingScoreSnapshot(run_id=run.id, **{k: r.get(k) for k in _SNAPSHOT_FIELDS}))
    await db.flush()
    return len(rows)


async def complete_run(db: AsyncSession, run: FilingScoreRun, counts: dict) -> FilingScoreRun:
    run.status, run.finished_at, run.counts = "complete", _now(), counts
    await db.flush()
    return run


async def fail_run(db: AsyncSession, run: FilingScoreRun, why: str) -> FilingScoreRun:
    run.status, run.finished_at, run.notes = "failed", _now(), why[:2000]
    await db.flush()
    return run


async def activate_run(db: AsyncSession, run_id: str) -> FilingScoreRun:
    """Make a COMPLETE run the one readers use (one active run per method version). Single transaction: the previous active run is deactivated in the same
    commit, so a reader never sees zero or two active runs."""
    run = await db.get(FilingScoreRun, run_id)
    if run is None or run.status != "complete":
        raise ValueError("only a complete run can be activated")
    await db.execute(update(FilingScoreRun).where(FilingScoreRun.method_version == run.method_version, FilingScoreRun.is_active.is_(True)).values(is_active=False))
    top = (await db.execute(select(func.max(FilingScoreRun.activation_seq)).where(FilingScoreRun.method_version == run.method_version))).scalar() or 0
    run.is_active, run.activated_at, run.activation_seq = True, _now(), top + 1
    await db.flush()
    return run


async def rollback_active(db: AsyncSession, method_version: str) -> FilingScoreRun | None:
    """Retire the active run (status rolled_back) and move the pointer to the most recent complete run activated before it; None if there is none, in which case
    readers see no filing score."""
    cur = (await db.execute(select(FilingScoreRun).where(FilingScoreRun.method_version == method_version, FilingScoreRun.is_active.is_(True)))).scalars().first()
    prev = None
    if cur is not None:
        prev = (await db.execute(
            select(FilingScoreRun).where(FilingScoreRun.method_version == method_version, FilingScoreRun.status == "complete", FilingScoreRun.id != cur.id,
                                         FilingScoreRun.activation_seq.is_not(None), FilingScoreRun.activation_seq < cur.activation_seq)
            .order_by(FilingScoreRun.activation_seq.desc()))).scalars().first()
        cur.is_active, cur.status = False, "rolled_back"   # a rolled-back run is never restored automatically (no flip-flopping); re-enable by computing a new run
        if prev is not None:
            prev.is_active, prev.activated_at = True, _now()
    await db.flush()
    return prev


async def active_run(db: AsyncSession, method_version: str) -> FilingScoreRun | None:
    return (await db.execute(select(FilingScoreRun).where(FilingScoreRun.method_version == method_version, FilingScoreRun.is_active.is_(True)))).scalars().first()


async def get_active_snapshot(db: AsyncSession, method_version: str, symbol: str) -> FilingScoreSnapshot | None:
    run = await active_run(db, method_version)
    if run is None:
        return None
    return (await db.execute(select(FilingScoreSnapshot).where(FilingScoreSnapshot.run_id == run.id, FilingScoreSnapshot.symbol == symbol.upper()))).scalars().first()
