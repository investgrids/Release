"""
Point-in-time NIFTY 50 universe query — Phase B0 leakage-lock (owner
instruction, 2026-08-23). Reads the real, sourced IndexMembership table
(app/services/quant/index_membership_seed.py) instead of
universe.py::NIFTY_50's single static current-day snapshot.

A stock is eligible at as-of date T if and only if T falls within one of
its real membership intervals: effective_from <= T AND (effective_to IS
NULL OR effective_to >= T). This is the only change needed to fix the
survivorship/future-composition bias confirmed in Phase B0: a company
added later (e.g. ETERNAL, 2025-03-28) contributes zero observations
before its real inclusion date; a company removed historically (e.g.
HEROMOTOCO, removed 2025-09-29) stays eligible up to its real removal
date and becomes ineligible after — changing today's static NIFTY_50
list has no effect on what this function returns for a past date,
because it never reads that list at all.
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.index_membership import IndexMembership


async def universe_as_of(db: AsyncSession, as_of: date, index_name: str = "NIFTY50") -> list[str]:
    """Real NIFTY 50 constituents as of `as_of`, sourced from the
    IndexMembership table — never from today's static universe.py list."""
    rows = (await db.execute(
        select(IndexMembership.symbol).where(
            IndexMembership.index_name == index_name,
            IndexMembership.effective_from <= as_of,
            or_(IndexMembership.effective_to.is_(None), IndexMembership.effective_to >= as_of),
        )
    )).scalars().all()
    return sorted(set(rows))


async def is_member_at(db: AsyncSession, symbol: str, as_of: date, index_name: str = "NIFTY50") -> bool:
    """Single-symbol point-in-time membership check — used to filter an
    already-generated prediction set (e.g. Phase 2D's stored rows)
    without re-deriving the whole universe per date."""
    row = (await db.execute(
        select(IndexMembership.id).where(
            IndexMembership.index_name == index_name,
            IndexMembership.symbol == symbol,
            IndexMembership.effective_from <= as_of,
            or_(IndexMembership.effective_to.is_(None), IndexMembership.effective_to >= as_of),
        ).limit(1)
    )).scalar_one_or_none()
    return row is not None


async def load_membership_intervals(db: AsyncSession, index_name: str = "NIFTY50") -> dict[str, list[tuple[date, date | None]]]:
    """All real membership intervals grouped by symbol — for bulk
    point-in-time filtering of a large stored prediction set without one
    query per (symbol, as_of_date) pair."""
    rows = (await db.execute(
        select(IndexMembership.symbol, IndexMembership.effective_from, IndexMembership.effective_to)
        .where(IndexMembership.index_name == index_name)
        .order_by(IndexMembership.symbol, IndexMembership.effective_from)
    )).all()
    out: dict[str, list[tuple[date, date | None]]] = {}
    for symbol, eff_from, eff_to in rows:
        out.setdefault(symbol, []).append((eff_from, eff_to))
    return out


def is_in_intervals(intervals: list[tuple[date, date | None]], as_of: date) -> bool:
    """Pure, in-memory point-in-time check against pre-loaded intervals —
    the fast path for filtering tens of thousands of already-stored
    predictions without a query per row."""
    return any(eff_from <= as_of and (eff_to is None or eff_to >= as_of) for eff_from, eff_to in intervals)
