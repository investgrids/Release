"""
The Latest Biggest Events Engine — the ONE place that decides "what is
today's biggest story," consumed by every surface that needs it (the
Events page's `sort_by=active`, and the homepage hero/ripple/companies/
opportunity/risk — see get_homepage_event_intelligence below). Before
this, the homepage independently guessed at "today's story" from a
separate AIPE article while the Events page ranked by raw impact_score —
two sources that could (and did) disagree. Now there is exactly one
ranking function (get_top_active_events) and exactly one place that turns
the #1 event into homepage-shaped intelligence
(get_homepage_event_intelligence) — every consumer reads the same result,
never recomputes its own.

impact_score itself is never changed — active_score is a derived, second
signal layered on top of it, for recency-aware SURFACES only. Historical
Intelligence keeps using raw impact_score/published_at unchanged.

Lifecycle is computed purely from two real fields (published_at,
impact_score) — no invented "still trending" signal, since nothing in
this app tracks ongoing follow-up coverage per event yet:
  LIVE        — published within the last 24 hours
  Developing  — published within the last 3 days
  Active      — published within the last 7 days
  Historical  — older than 7 days
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

LIVE_HOURS = 24
DEVELOPING_HOURS = 72
ACTIVE_DAYS = 7

# How fast recency decays to 0 — at RECENCY_HALF_LIFE_DAYS old, an event's
# recency contribution has halved. 7 days chosen to match ACTIVE_DAYS: an
# event just past the "Active" cutoff should also be near the bottom of
# the recency curve, not still scoring high on a technicality.
_RECENCY_HALF_LIFE_DAYS = 3.5


def _age_hours(published_at: datetime, now: datetime) -> float:
    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=timezone.utc)
    return max(0.0, (now - published_at).total_seconds() / 3600.0)


def compute_lifecycle(published_at: datetime | None, now: datetime | None = None) -> str:
    if not published_at:
        return "Historical"
    now = now or datetime.now(timezone.utc)
    age_h = _age_hours(published_at, now)
    if age_h < LIVE_HOURS:
        return "LIVE"
    if age_h < DEVELOPING_HOURS:
        return "Developing"
    if age_h < ACTIVE_DAYS * 24:
        return "Active"
    return "Historical"


def compute_active_score(impact_score: float | None, published_at: datetime | None, now: datetime | None = None) -> float:
    """0-100. 55% real impact_score (preserved, unmodified elsewhere) + 45%
    exponential recency decay — recency is a comparable factor, not a
    tie-breaker, since the whole point is that a stale high-impact event
    shouldn't permanently bury a fresher one."""
    now = now or datetime.now(timezone.utc)
    impact = impact_score if impact_score is not None else 0.0
    if not published_at:
        recency = 0.0
    else:
        age_days = _age_hours(published_at, now) / 24.0
        recency = 100.0 * (0.5 ** (age_days / _RECENCY_HALF_LIFE_DAYS))
    return round(0.55 * impact + 0.45 * recency, 2)


async def get_top_active_events(db: AsyncSession, limit: int = 3, pool_size: int = 300) -> list:
    """THE ranking function — every surface that needs "today's biggest
    events" calls this, never reimplements the window/filter/sort logic
    itself (see module docstring). Progressive window: try the last 7 days
    first, widen to 14 then 30 only if that isn't enough to fill the page,
    and only fall back to genuinely historical events as an explicit last
    resort (the caller can tell, via each item's own `lifecycle` field)."""
    from app.db.crud import get_events
    from app.schemas.event import CompanyImpact, EventSummary
    from app.api.events import _build_summary

    pool_rows = await get_events(db, limit=pool_size, sort_by="published_at")
    all_events: list[EventSummary] = []
    for e in pool_rows:
        # 0/None means "not yet scored" (routine NSE compliance filings
        # etc.), not a real low score. Without this filter, a same-day
        # unscored filing's recency alone would outrank a real, already-
        # scored event.
        if e.impact_score is None or e.impact_score == 0:
            continue
        companies = [
            CompanyImpact(symbol=c.get("symbol", ""), name=c.get("name", ""), impact=c.get("impact", "Neutral"))
            if isinstance(c, dict) else
            CompanyImpact(symbol=c.strip(), name=c.strip(), impact="Neutral")
            for c in (e.companies or []) if isinstance(c, dict) or (isinstance(c, str) and c.strip())
        ]
        all_events.append(_build_summary(e, companies))

    now = datetime.now(timezone.utc)

    def _age_days(ev: "EventSummary") -> float:
        d = ev.date
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return (now - d).total_seconds() / 86400.0

    def _sorted(pool: list) -> list:
        return sorted(pool, key=lambda x: x.active_score or 0.0, reverse=True)

    for window_days in (7, 14, 30):
        # Age-window only — NOT also filtered by the fixed 7-day lifecycle
        # boundary (lifecycle is a display label, not this check). A
        # 13-day-old event must be able to qualify once the window itself
        # has expanded to 14/30 days.
        windowed = [e for e in all_events if _age_days(e) <= window_days]
        if len(windowed) >= min(3, limit):
            return _sorted(windowed)[:limit]

    # Nothing recent at all — explicit last-resort fallback to the
    # highest-impact events regardless of age.
    return _sorted(all_events)[:limit]


async def get_homepage_event_intelligence(db: AsyncSession) -> dict:
    """Turns the #1 event from get_top_active_events into everything the
    homepage hero needs — Today's Biggest Story, Today's Ripple, Companies
    Most Likely To Move, Biggest Opportunity, Highest Risk — all derived
    from that ONE event's own real detail record (EventService.
    get_event_detail, the same data events/[id] already renders), never
    a second independently-computed narrative. {"available": False} when
    there's no active event at all (e.g. empty dev DB)."""
    from app.services.event_service import EventService

    top = await get_top_active_events(db, limit=3)
    if not top:
        return {"available": False}

    primary_summary = top[0]
    detail = await EventService(db).get_event_detail(primary_summary.id)
    if not detail:
        return {"available": False, "top_events": [e.model_dump() for e in top]}

    sectors = detail.get("affectedSectors") or []
    opportunity_sector = next((s for s in sectors if (s.get("impact") or "").lower() == "positive"), None)
    risk_sector = next((s for s in sectors if (s.get("impact") or "").lower() == "negative"), None)

    companies = (detail.get("beneficiaries") or [])[:3] or (detail.get("companies") or [])[:3]

    # deepseek_provider.py's own degraded-response placeholder — real text,
    # just not a real answer. Showing it on the homepage hero would read as
    # genuine analysis; better to omit and let the frontend fall back to
    # nothing than present a non-answer as one.
    why = (detail.get("summary") or {}).get("why_it_matters") or ""
    if why.strip() == "This event may have market implications.":
        why = ""

    graph = detail.get("graph") or {}
    ripple_edges = [
        {"from_entity": n_by_id.get(edge["source"], {}).get("label", edge["source"]),
         "to_entity": n_by_id.get(edge["target"], {}).get("label", edge["target"])}
        for n_by_id in [{n["id"]: n for n in (graph.get("nodes") or [])}]
        for edge in (graph.get("edges") or [])[:3]
    ] if graph.get("nodes") else []

    return {
        "available": True,
        "top_events": [e.model_dump() for e in top],
        "primary": {
            "id": primary_summary.id,
            "slug": detail["event"].get("slug", ""),
            "title": detail["event"]["title"],
            "why_it_matters": why,
            "sectors": [s.get("sector") for s in sectors][:4],
            "opportunity_sector": (opportunity_sector or {}).get("sector"),
            "risk_sector": (risk_sector or {}).get("sector"),
            "companies": [{"symbol": c.get("symbol"), "name": c.get("name")} for c in companies],
            "ripple": ripple_edges,
            "confidence": detail.get("confidence"),
            "impact_score": detail.get("impactScore"),
            "lifecycle": primary_summary.lifecycle,
        },
    }
