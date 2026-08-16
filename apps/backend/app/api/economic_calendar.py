"""
Phase 5A.8 — canonical Economic Calendar read API.

Deliberately a NEW route (/api/economic-calendar), not a rewrite of the
existing /api/calendar (still backed by the dead legacy CalendarEvent
table, app/api/calendar.py) or /api/market/calendar (api/market.py) —
migrating those existing consumers onto this one is Phase 5A.9's job,
not this one's. Keeping this router isolated means nothing currently
live changes behavior until that migration is deliberate and tested.

Every read here is filtered to REAL_SOURCES and is_current=True — a
future seed/test fixture using an out-of-allowlist source tag can
never surface through this API by construction (Phase 5A.6's
isolation guarantee), and only the CURRENT version of each identity
is ever returned, never a superseded revision.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db.models.economic_calendar import EconomicCalendarEvent
from app.schemas.economic_calendar import EconomicCalendarEventOut, SourceHealthOut
from app.services.economic_calendar.sync_orchestrator import REAL_SOURCES, get_source_health

router = APIRouter()

_IST = ZoneInfo("Asia/Kolkata")


def _aware(dt: datetime) -> datetime:
    """Same SQLite naive-read-back normalization used throughout this
    package — see sync_engine.py's _aware for the full explanation."""
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _to_out(row: EconomicCalendarEvent) -> EconomicCalendarEventOut:
    scheduled_at = _aware(row.scheduled_at)
    return EconomicCalendarEventOut(
        id=row.id, title=row.title, category=row.category, country=row.country, region=row.region,
        scheduled_at=scheduled_at, scheduled_at_ist=scheduled_at.astimezone(_IST),
        source_timezone=row.source_timezone, importance=row.importance,
        actual=row.actual, forecast=row.forecast, previous=row.previous, unit=row.unit,
        status=row.status, source=row.source, source_tier=row.source_tier,
        companies=row.companies or [], sectors=row.sectors or [], themes=row.themes or [],
        last_verified_at=_aware(row.last_verified_at),
    )


async def _query(
    db: AsyncSession, *, from_dt: datetime | None, to_dt: datetime | None,
    country: str | None, category: str | None, importance: str | None,
) -> list[EconomicCalendarEvent]:
    stmt = select(EconomicCalendarEvent).where(
        EconomicCalendarEvent.is_current.is_(True),
        EconomicCalendarEvent.source.in_(REAL_SOURCES),
    )
    if from_dt is not None:
        stmt = stmt.where(EconomicCalendarEvent.scheduled_at >= from_dt)
    if to_dt is not None:
        stmt = stmt.where(EconomicCalendarEvent.scheduled_at <= to_dt)
    if country:
        stmt = stmt.where(EconomicCalendarEvent.country == country.upper())
    if category:
        stmt = stmt.where(EconomicCalendarEvent.category == category)
    if importance:
        stmt = stmt.where(EconomicCalendarEvent.importance == importance.lower())
    stmt = stmt.order_by(EconomicCalendarEvent.scheduled_at.asc())
    return list((await db.execute(stmt)).scalars().all())


@router.get("/", response_model=list[EconomicCalendarEventOut])
async def list_economic_calendar(
    from_: date | None = Query(None, alias="from"),
    to: date | None = Query(None),
    country: str | None = Query(None),
    category: str | None = Query(None),
    importance: str | None = Query(None),
    company: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    from_dt = datetime.combine(from_, time.min, tzinfo=timezone.utc) if from_ else None
    to_dt = datetime.combine(to, time.max, tzinfo=timezone.utc) if to else None
    rows = await _query(db, from_dt=from_dt, to_dt=to_dt, country=country, category=category, importance=importance)
    if company:
        # No current source populates `companies` (all macro-level today) —
        # a portable in-Python filter here rather than a JSON-contains
        # query, which is not a single cross-dialect expression this
        # codebase's SQLite-dev/Postgres-prod convention can rely on, and
        # this table is calendar-sized, not full-text-search-sized.
        rows = [r for r in rows if company.upper() in [c.upper() for c in (r.companies or [])]]
    return [_to_out(r) for r in rows]


@router.get("/upcoming", response_model=list[EconomicCalendarEventOut])
async def upcoming_economic_calendar(
    days: int = Query(30, ge=1, le=180),
    country: str | None = Query(None),
    category: str | None = Query(None),
    importance: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    rows = await _query(db, from_dt=now, to_dt=now + timedelta(days=days),
                         country=country, category=category, importance=importance)
    return [_to_out(r) for r in rows]


@router.get("/today", response_model=list[EconomicCalendarEventOut])
async def today_economic_calendar(db: AsyncSession = Depends(get_db)):
    """"Today" in IST — the product's own primary timezone (Phase 5A §4) —
    not UTC, so a release at 23:00 IST / an already-past-midnight-UTC
    event still shows up on today's IST calendar day, and vice versa."""
    now_ist = datetime.now(timezone.utc).astimezone(_IST)
    start_ist = datetime.combine(now_ist.date(), time.min, tzinfo=_IST)
    end_ist = datetime.combine(now_ist.date(), time.max, tzinfo=_IST)
    rows = await _query(db, from_dt=start_ist.astimezone(timezone.utc), to_dt=end_ist.astimezone(timezone.utc),
                         country=None, category=None, importance=None)
    return [_to_out(r) for r in rows]


@router.get("/health", response_model=list[SourceHealthOut])
async def economic_calendar_health(db: AsyncSession = Depends(get_db)):
    """Ops visibility — per-source row counts, last verification,
    staleness. Reads Phase 5A.6's get_source_health() directly; no
    separate tracking table."""
    return await get_source_health(db)
