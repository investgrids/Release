"""
Atomic version-creation helpers for WeekendIntelligenceSnapshot.

See design doc §7/§13/§14: every row is immutable once committed —
callers must never mutate a WeekendIntelligenceSnapshot's intelligence
content after the fact, only `is_current` transitions, and only via
create_next_version below. This mirrors ScoreHistory's own established
"the 83 -> 87 -> 91 progression" pattern (score_history_service.py) rather
than inventing a new one.

Concurrency: this codebase runs a single gunicorn worker (`-w 1`, per
apps/backend/Dockerfile — confirmed in
WEEKEND_INTELLIGENCE_PHASE1_ARCHITECTURE.md §23), so there is no real
multi-process race to defend against today. The DB-level partial unique
index on WeekendIntelligenceSnapshot (see the model's __table_args__) is
the actual protection against two callers both ending up "current" for
the same target_trading_date — deliberately not adding SELECT FOR UPDATE
or any other row-locking on top of that, per the task brief's explicit
"do not overengineer distributed locking."
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.weekend_intelligence import WeekendIntelligenceSnapshot


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def get_current_snapshot(
    db: AsyncSession, target_trading_date: str
) -> WeekendIntelligenceSnapshot | None:
    """The single is_current=True row for a target_trading_date, or None
    if no snapshot has ever been created for it."""
    return (await db.execute(
        select(WeekendIntelligenceSnapshot).where(
            WeekendIntelligenceSnapshot.target_trading_date == target_trading_date,
            WeekendIntelligenceSnapshot.is_current.is_(True),
        )
    )).scalar_one_or_none()


async def get_version_history(
    db: AsyncSession, target_trading_date: str
) -> list[WeekendIntelligenceSnapshot]:
    """Every version for a target_trading_date, oldest first — the full
    immutable timeline, not just the current row."""
    return list((await db.execute(
        select(WeekendIntelligenceSnapshot)
        .where(WeekendIntelligenceSnapshot.target_trading_date == target_trading_date)
        .order_by(WeekendIntelligenceSnapshot.version.asc())
    )).scalars().all())


async def create_next_version(
    db: AsyncSession,
    *,
    target_trading_date: str,
    last_trading_date: str,
    checkpoint_label: str | None = None,
    status: str = "ok",
    **fields: Any,
) -> WeekendIntelligenceSnapshot:
    """
    Supersede the current snapshot (if any) for target_trading_date and
    stage the next version's insert, within the caller's own transaction.

    Version numbering is monotonic starting at 1; the prior current row
    (if any) has is_current flipped to False in the same call so exactly
    one row is current before/after this function ever runs to
    completion. Caller owns commit()/rollback() — this only calls db.add()
    and mutates the prior row's flag, it does not commit.

    `**fields` accepts any other WeekendIntelligenceSnapshot column
    (overall_bias, production_confidence, top_sector_refs, etc.) — Phase
    1A callers (tests) typically pass none of these since Phase 1B owns
    actually populating them; Phase 1B's aggregator will call this same
    function with real values.
    """
    current = await get_current_snapshot(db, target_trading_date)
    version = (current.version + 1) if current else 1
    if current is not None:
        current.is_current = False

    snapshot = WeekendIntelligenceSnapshot(
        id=str(uuid4()),
        target_trading_date=target_trading_date,
        last_trading_date=last_trading_date,
        version=version,
        is_current=True,
        generated_at=_now(),
        checkpoint_label=checkpoint_label,
        status=status,
        **fields,
    )
    db.add(snapshot)
    return snapshot
