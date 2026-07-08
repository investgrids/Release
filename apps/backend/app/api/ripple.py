"""Ripple Engine API — event dependency graph and what-if scenario analysis."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.db.models.event import Event, EventCompany, EventSector
from app.db.models_legacy import Story
from app.services.ripple_service import get_or_generate_ripple, generate_scenario_ripple

router = APIRouter()

# Static demo ripples — shown on the list page when the DB has no high-impact events
_DEMO_RIPPLES: dict[str, dict] = {
    "1": {"title": "India-Pakistan Military Tensions",   "event_type": "geopolitical", "impact": 9.2},
    "2": {"title": "RBI Emergency Rate Cut — 50 bps",   "event_type": "monetary",     "impact": 8.7},
    "3": {"title": "Union Budget 2026 — Capex Surge",   "event_type": "fiscal",       "impact": 8.1},
    "4": {"title": "OPEC+ Cuts Production by 2M bbl/d", "event_type": "commodity",    "impact": 8.5},
    "5": {"title": "FII Record Inflows — ₹45,000Cr",    "event_type": "macro",        "impact": 7.8},
    "6": {"title": "India GDP Growth Hits 8.4% Q2",     "event_type": "macro",        "impact": 7.3},
}


# ── GET /api/ripple/event/{event_id} ─────────────────────────────────────────

@router.get("/event/{event_id}")
async def get_event_ripple(
    event_id: str,
    regenerate: bool = Query(False, description="Force AI regeneration"),
    db: AsyncSession = Depends(get_db),
):
    """Get or generate the Ripple Engine dependency graph for a specific event."""
    ev_res = await db.execute(select(Event).where(Event.id == event_id))
    event  = ev_res.scalar_one_or_none()
    if not event:
        # Handle demo IDs from the static fallback list page
        if event_id in _DEMO_RIPPLES:
            demo = _DEMO_RIPPLES[event_id]
            return await generate_scenario_ripple(
                f"{demo['title']}: market ripple analysis — cascading effects across sectors, commodities, and companies",
                db,
            )
        raise HTTPException(status_code=404, detail="Event not found")

    # Load junction-table companies/sectors
    comp_res = await db.execute(select(EventCompany).where(EventCompany.event_id == event_id))
    companies = [{"symbol": c.symbol, "name": c.name, "impact_type": c.impact_type} for c in comp_res.scalars()]

    sec_res  = await db.execute(select(EventSector).where(EventSector.event_id == event_id))
    sectors  = [{"sector": s.sector, "impact": s.impact} for s in sec_res.scalars()]

    # Fall back to JSON fields if junction tables are empty
    if not companies and isinstance(event.companies, list):
        companies = event.companies
    if not sectors and isinstance(event.sectors, list):
        sectors = [{"sector": s} if isinstance(s, str) else s for s in event.sectors]

    return await get_or_generate_ripple(
        event_id=event_id,
        event_title=event.title or "",
        event_summary=(event.summary or event.description or "")[:1000],
        event_type=event.event_type or "macro",
        event_impact=float(event.impact_score or 7.0),
        companies=companies,
        sectors=sectors,
        db=db,
        force_regenerate=regenerate,
    )


# ── POST /api/ripple/scenario ─────────────────────────────────────────────────

class ScenarioRequest(BaseModel):
    scenario: str


@router.post("/scenario")
async def run_scenario(
    body: ScenarioRequest,
    db: AsyncSession = Depends(get_db),
):
    """Generate a ripple graph for a hypothetical 'what if' scenario."""
    text = (body.scenario or "").strip()
    if len(text) < 5:
        raise HTTPException(status_code=400, detail="Scenario description too short (min 5 chars)")
    return await generate_scenario_ripple(text, db)


# ── GET /api/ripple/featured ──────────────────────────────────────────────────

# ── GET /api/ripple/company/{ticker} ─────────────────────────────────────────

@router.get("/company/{ticker}")
async def get_company_ripple(
    ticker: str,
    db: AsyncSession = Depends(get_db),
):
    """Generate a ripple graph centred on a single company / NSE ticker."""
    ticker = ticker.upper().strip()

    # Find events that mention this company and pick the highest-impact one
    comp_rows = await db.execute(
        select(EventCompany).where(EventCompany.symbol == ticker).limit(20)
    )
    event_ids = [r.event_id for r in comp_rows.scalars()]

    event = None
    if event_ids:
        ev_res = await db.execute(
            select(Event)
            .where(Event.id.in_(event_ids))
            .order_by(Event.impact_score.desc())
            .limit(1)
        )
        event = ev_res.scalar_one_or_none()

    if event:
        # Re-use the event ripple (already cached or generates once)
        comp_res = await db.execute(select(EventCompany).where(EventCompany.event_id == event.id))
        companies = [{"symbol": c.symbol, "name": c.name, "impact_type": c.impact_type} for c in comp_res.scalars()]
        sec_res  = await db.execute(select(EventSector).where(EventSector.event_id == event.id))
        sectors  = [{"sector": s.sector, "impact": s.impact} for s in sec_res.scalars()]
        return await get_or_generate_ripple(
            event_id=event.id,
            event_title=event.title or ticker,
            event_summary=(event.summary or event.description or "")[:1000],
            event_type=event.event_type or "macro",
            event_impact=float(event.impact_score or 7.0),
            companies=companies,
            sectors=sectors,
            db=db,
        )

    # No matching event — generate a company-centric scenario directly
    return await generate_scenario_ripple(
        f"Market ripple analysis for {ticker} stock — impact on related sectors, suppliers, and competitors",
        db,
    )


# ── GET /api/ripple/story/{story_id} ─────────────────────────────────────────

@router.get("/story/{story_id}")
async def get_story_ripple(
    story_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Generate a ripple graph for a market story / theme narrative."""
    res = await db.execute(select(Story).where(Story.id == story_id))
    story = res.scalar_one_or_none()
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")

    return await generate_scenario_ripple(
        f"{story.title}: {story.description[:400]}",
        db,
    )


# ── GET /api/ripple/theme/{theme_slug} ───────────────────────────────────────

@router.get("/theme/{theme_slug}")
async def get_theme_ripple(
    theme_slug: str,
    db: AsyncSession = Depends(get_db),
):
    """Generate a ripple graph for a broad market theme (e.g. 'defence', 'ev', 'ai')."""
    theme = theme_slug.replace("-", " ").replace("_", " ").strip()

    # Find the most impactful event that matches this theme via sectors (JSON cast for SQLite/Postgres)
    from sqlalchemy import cast, String as SAStr
    ev_res = await db.execute(
        select(Event)
        .where(cast(Event.sectors, SAStr).ilike(f"%{theme}%"))
        .order_by(Event.impact_score.desc())
        .limit(1)
    )
    event = ev_res.scalar_one_or_none()

    if event:
        comp_res = await db.execute(select(EventCompany).where(EventCompany.event_id == event.id))
        companies = [{"symbol": c.symbol, "name": c.name, "impact_type": c.impact_type} for c in comp_res.scalars()]
        sec_res  = await db.execute(select(EventSector).where(EventSector.event_id == event.id))
        sectors  = [{"sector": s.sector, "impact": s.impact} for s in sec_res.scalars()]
        return await get_or_generate_ripple(
            event_id=event.id,
            event_title=f"{theme.title()} Theme: {event.title}",
            event_summary=(event.summary or "")[:800],
            event_type=event.event_type or "macro",
            event_impact=float(event.impact_score or 7.0),
            companies=companies,
            sectors=sectors,
            db=db,
        )

    # No event found — generate a theme-level scenario
    return await generate_scenario_ripple(
        f"Market ripple analysis for the '{theme}' investment theme in India — "
        f"sector rotation, beneficiary companies, policy tailwinds and risks",
        db,
    )


# ── GET /api/ripple/featured ──────────────────────────────────────────────────

@router.get("/featured")
async def get_featured_ripples(
    limit: int = Query(8, le=20),
    db: AsyncSession   = Depends(get_db),
):
    """Return top high-impact events suitable for Ripple Engine analysis."""
    result = await db.execute(
        select(Event)
        .where(Event.impact_score >= 5)
        .order_by(Event.impact_score.desc(), Event.created_at.desc())
        .limit(limit)
    )
    events = result.scalars().all()

    return [
        {
            "id":           e.id,
            "title":        e.title or "",
            "summary":      (e.summary or "")[:200],
            "event_type":   e.event_type or "macro",
            "impact_score": float(e.impact_score or 0),
            "event_date":   e.event_date.isoformat() if e.event_date else None,
            "categories":   (e.sectors or [])[:3] if isinstance(e.sectors, list) else [],
            "slug":         e.slug,
        }
        for e in events
    ]
