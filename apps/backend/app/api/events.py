"""
Events API — list + detail + market-data + market-chart endpoints.
"""
from __future__ import annotations

import structlog
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.crud import get_events
from app.db.session import get_db
from app.schemas.event import CompanyImpact, EventSummary
from app.schemas.event_deep_research import DeepResearchResponse
from app.schemas.event_detail import EventDetailResponse
from app.services import coverage_engine
from app.services.event_deep_research_service import get_deep_research
from app.services.event_service import EventService
from app.services.event_scale import normalize_impact_score, normalize_confidence
from app.services.event_lifecycle import compute_active_score, compute_lifecycle

logger = structlog.get_logger(__name__)

router = APIRouter()


def _build_summary(e, companies: list, indexable: bool = False) -> EventSummary:
    impact = normalize_impact_score(e.id, e.impact_score)
    return EventSummary(
        id=e.id,
        slug=e.slug or "",
        title=e.title,
        summary=e.summary or "",
        impact_score=impact,
        confidence=normalize_confidence(e.id, e.confidence),
        sectors=e.sectors or [],
        companies=companies,
        date=e.published_at,
        category=e.category or e.event_type or "Macro",
        event_type=e.event_type or "",
        source=e.source or "",
        active_score=compute_active_score(impact, e.published_at),
        lifecycle=compute_lifecycle(e.published_at),
        indexable=indexable,
    )


def _to_summary(e, indexable: bool = False) -> EventSummary:
    companies = [
        CompanyImpact(symbol=c.get("symbol", ""), name=c.get("name", ""), impact=c.get("impact", "Neutral"))
        if isinstance(c, dict) else
        CompanyImpact(symbol=c.strip(), name=c.strip(), impact="Neutral")
        for c in (e.companies or []) if isinstance(c, dict) or (isinstance(c, str) and c.strip())
    ]
    return _build_summary(e, companies, indexable)


async def _attach_indexable(db: AsyncSession, summaries: list[EventSummary]) -> list[EventSummary]:
    """Batch-computes indexability for an already-built summary list —
    kept as a separate pass (rather than threading a per-row lookup
    through every sort_by branch below) so each branch's existing
    control flow doesn't need to change."""
    flags = await coverage_engine.compute_indexable_batch(db, [s.id for s in summaries])
    for s in summaries:
        s.indexable = flags.get(s.id, False)
    return summaries


@router.get("/", response_model=List[EventSummary])
async def list_events(
    limit: int = Query(20, ge=1, le=100),
    page_size: int = Query(None, ge=1, le=100),
    sort_by: str = Query("published_at"),
    # Most raw NSE/BSE exchange filings (chairman resignations, share-
    # certificate reissues, routine compliance disclosures — see
    # events/page.tsx's "Unscored" badge) never clear the Scoring Engine's
    # minimum-evidence bar and stay impact_score=null forever — confirmed
    # live: ~94% of a 100-event sample. Surfacing them in the main feed is
    # just noise with no assessed company impact. scored_only widens the
    # DB pool and filters to impact_score is not None before truncating to
    # the requested limit, instead of limiting-then-filtering (which would
    # return almost nothing at limit=20 given the ~6% scored rate).
    scored_only: bool = Query(False),
    # Company redesign Batch 3 — the Company page's Events tab previously
    # only had yfinance's own sparse corporate-action list (stock.events)
    # to show; real graph/RSS-sourced events that actually mention this
    # company (already computed inline in related.py's "company" branch)
    # were never reachable from a dedicated endpoint. Reuses the exact
    # same real symbol-match logic against Event.companies, not a new
    # heuristic.
    company: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    effective_limit = page_size if page_size is not None else limit

    if company:
        sym_lower = company.strip().upper().lower()
        pool = await get_events(db, limit=500, sort_by="impact_score")
        matched = []
        for e in pool:
            mentions = any(
                (c.get("symbol", "").lower() == sym_lower if isinstance(c, dict) else str(c).lower() == sym_lower)
                for c in (e.companies or [])
            )
            if mentions:
                matched.append(e)
            if len(matched) >= effective_limit:
                break
        result = [_to_summary(e) for e in matched]
        return await _attach_indexable(db, result)

    if scored_only and sort_by not in ("impact_score", "active"):
        pool_limit = min(max(effective_limit * 15, 300), 1000)
        rows = await get_events(db, limit=pool_limit, sort_by=sort_by)
        result = [_to_summary(e) for e in rows if e.impact_score is not None]
        return await _attach_indexable(db, result[:effective_limit])

    if sort_by == "active":
        # THE Latest Biggest Events Engine — see event_lifecycle.py's
        # module docstring. This is the single ranking function every
        # surface (this endpoint, the homepage hero) reads, never its own
        # independent computation.
        from app.services.event_lifecycle import get_top_active_events
        return await _attach_indexable(db, await get_top_active_events(db, limit=effective_limit))

    if sort_by == "impact_score":
        # Fetch a wider pool so mixed-scale scores can be normalized and re-sorted in Python.
        # Pipeline events use 0-100 (score=60), seed events use 0-10 (score=8.7 → norm 87).
        # DB ordering on raw values would put 60 before 8.7, hiding high-quality seeds.
        pool_rows = await get_events(db, limit=200, sort_by="published_at")
        result = [_to_summary(e) for e in pool_rows]
        # A pure impact_score sort with no recency bound let a handful of old
        # high-score events (weeks-old macro/policy items) permanently occupy
        # this list's top slots since nothing more recent ever outscored them
        # — confirmed live: "events page not showing latest events." Same root
        # cause already fixed client-side for PriorityEventsBar's 48h window
        # (events/page.tsx), never applied here even though this endpoint
        # feeds that same page's main timeline/list. Fix: rank events from the
        # last 14 days by impact_score first (still "ranked by impact," per
        # this page's own header copy, just recency-bounded); only reach into
        # older events if the recent window doesn't fill the requested limit,
        # so genuinely major old events can still appear rather than vanish,
        # but never at the cost of hiding today's news behind them.
        from datetime import datetime, timedelta, timezone
        cutoff = datetime.now(timezone.utc) - timedelta(days=14)

        def _aware(dt):
            if dt is None:
                return None
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)

        def _score_key(x):
            return x.impact_score if x.impact_score is not None else -1

        recent, older = [], []
        for r, e in zip(result, pool_rows):
            published = _aware(getattr(e, "published_at", None))
            (recent if published is not None and published >= cutoff else older).append(r)
        recent.sort(key=_score_key, reverse=True)
        older.sort(key=_score_key, reverse=True)
        return await _attach_indexable(db, (recent + older)[:effective_limit])
    else:
        rows = await get_events(db, limit=effective_limit, sort_by=sort_by)
        return await _attach_indexable(db, [_to_summary(e) for e in rows])


@router.get("/{event_id}/market-data")
async def get_event_market_data(
    event_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Real-time market status + sector-relevant index quotes (never cached)."""
    from app.repositories.event_repository import EventRepository
    from app.services.market_data import get_market_status, get_event_market_indices

    repo = EventRepository(db)
    sectors_obj = await repo.get_sectors(event_id)
    sector_names = [s.sector for s in sectors_obj]

    market_status = get_market_status()
    indices = await get_event_market_indices(sector_names)
    return {"marketStatus": market_status, "marketIndices": indices}


@router.get("/{event_id}/market-chart")
async def get_event_market_chart(
    event_id: str,
    period: str = Query("1D"),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns chart data for the primary sector index of this event.
    Falls back to Nifty 50 when no sectors are mapped.
    """
    from app.repositories.event_repository import EventRepository
    from app.services.market_data import (
        get_ticker_chart, _SECTOR_INDEX_MAP,
    )

    repo = EventRepository(db)
    sectors_obj = await repo.get_sectors(event_id)
    sector_names = [s.sector for s in sectors_obj]

    primary_ticker = "^NSEI"
    primary_name   = "Nifty 50"
    for sector in sector_names:
        key = sector.lower().strip()
        for keyword, (name, ticker) in _SECTOR_INDEX_MAP.items():
            if keyword in key:
                primary_ticker = ticker
                primary_name   = name
                break
        else:
            continue
        break

    data = await get_ticker_chart(primary_ticker, period)
    return {"period": period, "ticker": primary_ticker, "name": primary_name, "data": data}


@router.get("/{event_id}/deep-research", response_model=DeepResearchResponse)
async def get_event_deep_research(
    event_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Layer 2 (2026-08 event page redesign) — a single consolidated fetch
    replacing what used to be up to 5 independent AI-backed component
    calls. See event_deep_research_service for the reuse/no-fabrication
    contract."""
    logger.info("GET /api/events/%s/deep-research", event_id)
    result = await get_deep_research(db, event_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Event '{event_id}' not found")
    return result


@router.get("/{event_id}", response_model=EventDetailResponse)
async def get_event_detail(
    event_id: str,
    db: AsyncSession = Depends(get_db),
):
    logger.info("GET /api/events/%s", event_id)
    service = EventService(db)
    detail = await service.get_event_detail(event_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"Event '{event_id}' not found")
    return detail

