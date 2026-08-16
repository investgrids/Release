"""
Phase 5A.9 — adapts real EconomicCalendarEvent rows into the shape
every pre-existing dead-table consumer already expects, so migrating
them off the legacy `calendar_events` table needs zero changes to
their own parsing logic.

Confirmed by reading every caller directly (not assumed): `engine.py`'s
read_upcoming_calendar and opening_prediction_service.py's
_gather_events both parse `.date` with
`datetime.strptime(row.date, "%b %d, %Y")` — a specific, strict format
the legacy seed data happened to use. `date` here is formatted
identically (in IST — India being this product's primary timezone),
so both callers' existing strptime calls keep working unchanged.

`description` is built only from fields the row genuinely has
(importance, actual/previous/unit, source) — never invented text.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.economic_calendar import EconomicCalendarEvent
from app.services.economic_calendar.sync_orchestrator import REAL_SOURCES

_IST = ZoneInfo("Asia/Kolkata")


@dataclass
class LegacyCalendarRow:
    """Duck-types the legacy CalendarEvent ORM row's exact attribute
    surface (id/category/title/date/description) — every existing
    caller accesses these five attributes and nothing else (confirmed
    by reading app/api/calendar.py, app/api/market.py, engine.py's
    read_upcoming_calendar, opening_prediction_service.py's
    _gather_events)."""
    id: str
    category: str
    title: str
    date: str
    description: str


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _build_description(row: EconomicCalendarEvent) -> str:
    parts = [f"{row.importance.capitalize()} importance."]
    if row.actual is not None:
        parts.append(f"Actual: {row.actual}{row.unit or ''}.")
    if row.previous is not None:
        parts.append(f"Previous: {row.previous}{row.unit or ''}.")
    parts.append(f"Source: {row.source.upper()}.")
    return " ".join(parts)


async def get_legacy_shaped_calendar(db: AsyncSession) -> list[LegacyCalendarRow]:
    """Real E2E finding (Phase 5A.12): every consumer of the legacy
    get_calendar() is an "upcoming"/"what's next" surface (Watch
    Tomorrow, the /calendar page's "Upcoming Calendar" section,
    tomorrow_watch, Pre-Market's Event Layer) — the original dead table
    always implicitly guaranteed this, since its only writer (db/seed.py)
    only ever generated forward-dated entries. EconomicCalendarEvent
    intentionally retains full multi-year history (real research value,
    Phase 5A §23) alongside future rows, so without a floor here every
    one of those "what's next" surfaces would show 2021 FOMC decisions
    first — confirmed live, caught by an actual screenshot of /calendar
    before this fix, not by a unit test alone. A small back-window (1
    day) is kept rather than a strict `>= now`, so an event that just
    passed doesn't disappear mid-day for a caller in a different
    timezone context."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=1)
    rows = (await db.execute(
        select(EconomicCalendarEvent)
        .where(
            EconomicCalendarEvent.is_current.is_(True),
            EconomicCalendarEvent.source.in_(REAL_SOURCES),
            EconomicCalendarEvent.scheduled_at >= cutoff,
        )
        .order_by(EconomicCalendarEvent.scheduled_at.asc())
    )).scalars().all()

    out = []
    for r in rows:
        scheduled_ist = _aware(r.scheduled_at).astimezone(_IST)
        out.append(LegacyCalendarRow(
            id=r.id, category=r.category, title=r.title,
            date=scheduled_ist.strftime("%b %d, %Y"),
            description=_build_description(r),
        ))
    return out
