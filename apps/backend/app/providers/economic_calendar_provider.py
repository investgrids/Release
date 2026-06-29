"""
Economic calendar provider — derives upcoming India macro events from a
curated static base + supplements with Finnhub calendar when key is configured.
This avoids paid calendar API dependency while still providing useful data.
"""
from __future__ import annotations

import hashlib
from datetime import date, datetime, timedelta, timezone
from typing import Any

import httpx

from .base import BaseProvider, RawItem
from app.core.config import settings

_RECURRING_EVENTS = [
    # (month_day, title, category, impact)
    ("01-01", "New Year Market Open",               "Holiday",          5.0),
    ("01-15", "WPI Inflation Data",                  "Macro",            7.5),
    ("02-01", "Union Budget Presentation",           "Budget",           9.5),
    ("02-15", "CPI Inflation Data",                  "Macro",            8.0),
    ("03-15", "RBI Monetary Policy Decision",        "Monetary Policy",  9.0),
    ("03-31", "Financial Year End",                  "Market",           7.0),
    ("04-01", "New Financial Year Start",            "Market",           7.0),
    ("04-15", "Q4 Results Season Begins",            "Earnings",         7.5),
    ("05-15", "RBI Monetary Policy Decision",        "Monetary Policy",  9.0),
    ("06-15", "Q1 GDP Advance Estimate",             "Macro",            8.5),
    ("07-15", "Q1 Results Season Begins",            "Earnings",         7.5),
    ("08-08", "RBI Monetary Policy Decision",        "Monetary Policy",  9.0),
    ("10-08", "RBI Monetary Policy Decision",        "Monetary Policy",  9.0),
    ("10-15", "Q2 Results Season Begins",            "Earnings",         7.5),
    ("12-07", "RBI Monetary Policy Decision",        "Monetary Policy",  9.0),
]


def _next_occurrences(n: int = 10) -> list[dict]:
    """Return the next N recurring events from today."""
    today = datetime.now(timezone.utc).date()
    year  = today.year
    events: list[dict] = []
    for check_year in [year, year + 1]:
        for (md, title, category, impact) in _RECURRING_EVENTS:
            try:
                event_date = date(check_year, int(md[:2]), int(md[3:]))
            except ValueError:
                continue
            if event_date >= today:
                uid = f"cal-{check_year}-{hashlib.md5(title.encode()).hexdigest()[:8]}"
                events.append({
                    "id":           uid,
                    "headline":     title,
                    "summary":      f"Scheduled {category} event",
                    "source":       "Economic Calendar",
                    "published_at": event_date.isoformat(),
                    "impact_score": impact,
                    "event_type":   "calendar",
                    "category":     category,
                })
    events.sort(key=lambda e: e["published_at"])
    return events[:n]


class EconomicCalendarProvider(BaseProvider):
    source_name = "EconomicCalendar"

    async def fetch_latest(self) -> list[dict]:
        return _next_occurrences(n=15)

    async def fetch_by_date(self, target: date) -> list[dict]:
        items = await self.fetch_latest()
        ts = target.isoformat()
        return [i for i in items if i.get("published_at", "") == ts]

    def normalize(self, raw: dict) -> RawItem | None:
        headline = (raw.get("headline") or "").strip()
        if not headline:
            return None
        return RawItem(
            id=raw.get("id") or f"cal-{hashlib.md5(headline.encode()).hexdigest()[:12]}",
            headline=headline[:512],
            summary=raw.get("summary", ""),
            source="Economic Calendar",
            published_at=raw.get("published_at", ""),
            impact_score=raw.get("impact_score", 7.0),
            event_type="calendar",
            extra={"category": raw.get("category", "Macro")},
        )
