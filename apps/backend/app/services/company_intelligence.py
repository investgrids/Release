"""
Company Intelligence — "why does this company matter today," reusing every
real engine this session already built rather than recomputing a fourth
version of the same signals:

  - active_events    — the SAME Unified Event Intelligence Engine
                        (event_lifecycle.py) that ranks the Events page and
                        the homepage, filtered to events that name this
                        ticker or its real sector.
  - investment_watch  — Phase 2B's Investment Watch, called verbatim
                        (app.services.ai_search.investment_watch), not a
                        second competing verdict/last-change computation.
  - historical        — historical_memory_service.find_similar_events,
                        the same engine Live Intelligence / Opportunity
                        Radar 2.0 / AI Search all already use.
  - ripple_position    — real data only: the seeded intelligence graph's
                        real upstream path INTO this company's sector (via
                        ai_search_service._build_ripple_chain, unchanged),
                        bridged to the company by its real, structural
                        sector membership (_NSE_UNIVERSE — not a graph
                        edge, since most individual companies are isolated
                        leaf nodes in the graph, verified live for HAL),
                        then real same-industry competitors downstream
                        (same _competitors_for logic as ripple_graph.py /
                        opportunity_intelligence.py). "Suppliers"/
                        "Customers" from the original spec are NOT built —
                        no real data source in this app models supply-chain
                        relationships, and fabricating one would violate
                        this app's core rule.
  - confidence        — confidence_service.calculate_confidence, the exact
                        same deterministic engine AI Search's confidence
                        breakdown already wraps, fed real company-context
                        signals (event count/urgency, historical match
                        strength, government exposure, live price
                        direction) instead of a query's evidence bundle.
  - related_opportunities — OpportunityCompany, the real junction table
                        Opportunity Radar already populates.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

_LOOKBACK_DAYS = 30
_MIN_URGENCY = 3


def _clean_tickers(raw: list[str] | None) -> set[str]:
    out = set()
    for t in (raw or []):
        sym = t.upper().replace("NSE:", "").replace(".NS", "").replace(".BO", "")
        if sym:
            out.add(sym)
    return out


async def get_active_events(db: AsyncSession, symbol: str, sector: str | None, limit: int = 4) -> list[dict]:
    """Real events naming this ticker (preferred) or its real sector,
    scored by the same active_score/lifecycle engine that ranks every
    other event surface — never a second, company-specific ranking."""
    from app.db.models.intelligence import EventTriage
    from app.db.models.event import Event
    from app.services.event_lifecycle import compute_active_score, compute_lifecycle

    cutoff = datetime.now(timezone.utc) - timedelta(days=_LOOKBACK_DAYS)
    rows = (await db.execute(
        select(EventTriage)
        .where(EventTriage.triaged_at >= cutoff)
        .where(EventTriage.urgency >= _MIN_URGENCY)
    )).scalars().all()

    sector_l = (sector or "").lower()
    direct, sector_matches = [], []
    for r in rows:
        tickers = _clean_tickers(r.tickers)
        if symbol.upper() in tickers:
            direct.append(r)
        elif sector_l and any(sector_l in s.lower() or s.lower() in sector_l for s in (r.sectors or [])):
            sector_matches.append(r)

    pool = direct + sector_matches
    # Found live: EventTriage.id is its own row id (a UUID) — never the same
    # value as EventTriage.event_id (the real Event this triage result is
    # about, e.g. "nse-1f3ac042b7"). The frontend link this feeds
    # (CompanyIntelligenceSection.tsx) was built from r.id, so it has never
    # pointed at a real /events/{id} page for any of these — unrelated to
    # the nse- slug migration, a pre-existing dead link, fixed here too.
    event_ids = list({r.event_id for r in pool if r.event_id})
    slug_by_event_id: dict[str, str] = {}
    if event_ids:
        ev_rows = (await db.execute(select(Event.id, Event.slug).where(Event.id.in_(event_ids)))).all()
        slug_by_event_id = {eid: (slug or "") for eid, slug in ev_rows}

    seen_ids = set()
    items = []
    for r in pool:
        if r.id in seen_ids:
            continue
        seen_ids.add(r.id)
        items.append({
            "id": r.event_id,
            "slug": slug_by_event_id.get(r.event_id, ""),
            "headline": r.one_liner or r.headline,
            "urgency": r.urgency,
            "sentiment": r.sentiment,
            "lifecycle": compute_lifecycle(r.triaged_at),
            "active_score": compute_active_score(r.urgency * 10, r.triaged_at),
            "direct": r in direct,
        })
    items.sort(key=lambda x: (x["direct"], x["active_score"]), reverse=True)
    return items[:limit]


async def get_ripple_position(symbol: str, sector: str | None) -> dict:
    """Real upstream path (seeded intelligence graph) -> real sector
    membership bridge -> real same-industry competitors downstream. See
    module docstring for why Suppliers/Customers aren't included."""
    from app.services.ai_search.ripple_graph import _build_ripple_chain

    chain: list[dict] = []
    if sector:
        try:
            chain = await _build_ripple_chain(sector)
        except Exception:
            chain = []

    # _build_ripple_chain resolves its argument via free-text word-overlap
    # matching against EVERY graph node, not just sectors — found live for
    # "Finance" (ICICIGI's sector, not itself a seeded sector label; the
    # seed only has "Banking"/"NBFC"): it latched onto an unrelated,
    # auto-added EVENT node whose headline happened to mention "Bajaj
    # Finance," and returned that headline plus its own un-normalized,
    # lowercase auto-added sector edges ("auto") as if they were this
    # company's real sector position. A sector lookup must only ever
    # accept a chain that actually resolved to a sector node — anything
    # else (event, company, ...) is discarded in favor of the same minimal
    # fallback already used when the chain comes back empty.
    root_type = chain[0]["nodes"][0].get("type") if chain and chain[0].get("nodes") else None
    if root_type != "sector":
        chain = []

    upstream = [level["nodes"][0]["label"] for level in chain if level["nodes"]][:3] if chain else []
    if sector and (not upstream or upstream[-1].lower() != sector.lower()):
        upstream = upstream + [sector] if sector not in upstream else upstream

    competitors = _competitors_for(symbol, sector, limit=3)

    return {"upstream": upstream, "company": symbol, "downstream": competitors}


def _competitors_for(symbol: str, sector: str | None, limit: int = 3) -> list[str]:
    """Same reasoning as ripple_graph.py's _competitors_for / opportunity_
    intelligence.py — sector alone isn't precise enough, so a candidate's
    industry must also share a real word with this company's own industry."""
    import re
    from app.api.companies import _NSE_UNIVERSE

    me = next((c for c in _NSE_UNIVERSE if c["symbol"] == symbol), None)
    if not me or not sector:
        return []
    my_words = {w.lower() for w in (me.get("industry") or "").split() if len(w) > 3}
    out = []
    for co in _NSE_UNIVERSE:
        if co["symbol"] == symbol or co["sector"] != sector:
            continue
        if my_words:
            cand_words = {w.lower() for w in re.sub(r"[.,()&]", " ", co.get("industry") or "").split() if len(w) > 3}
            if not (my_words & cand_words):
                continue
        out.append(co["symbol"])
        if len(out) >= limit:
            break
    return out


async def get_historical(sector: str | None, company_name: str) -> dict | None:
    from app.services.ai_search.retrieval import _infer_historical_category
    from app.services.historical_memory_service import find_similar_events

    if not sector:
        return None
    category = _infer_historical_category(company_name.lower())
    matches = await find_similar_events({"sectors": [sector], "category": category}, limit=1, min_similarity=10.0)
    if not matches:
        return None
    m = matches[0]
    return {
        "event_title": m["event_title"], "similarity": m["similarity"], "key_lesson": m.get("key_lesson"),
        "winners": [w.get("symbol") or w.get("name") for w in (m.get("historical_winners") or [])][:4],
        "losers": [l.get("symbol") or l.get("name") for l in (m.get("historical_losers") or [])][:4],
    }


async def get_related_opportunities(db: AsyncSession, symbol: str, limit: int = 3) -> list[dict]:
    """Batch E consumer migration, 2026-08-24 — dispatches on
    settings.opportunity_read_source. Both branches return `href`
    pre-resolved (never a raw id/slug pair — the exact ambiguity that
    404'd on CompanyIntelligenceSection.tsx before this)."""
    from app.core.config import settings

    if settings.opportunity_v2_promoted:
        from app.services.opportunity_v2.read_service import list_public_opportunities_v2_for_company
        return await list_public_opportunities_v2_for_company(db, symbol, limit)

    from app.db.models.opportunity import Opportunity, OpportunityCompany

    rows = (await db.execute(
        select(Opportunity, OpportunityCompany)
        .join(OpportunityCompany, OpportunityCompany.opportunity_id == Opportunity.id)
        .where(OpportunityCompany.company_id == symbol)
        .order_by(Opportunity.opportunity_score.desc())
        .limit(limit)
    )).all()
    return [{"id": str(opp.id), "title": opp.title, "href": f"/opportunity-radar/{opp.id}", "score": opp.opportunity_score} for opp, _ in rows]


def compute_confidence_breakdown(events: list[dict], historical: dict | None, gov_score: float | None, price_positive: bool | None) -> dict:
    """Exactly the same deterministic engine (confidence_service.
    calculate_confidence) AI Search's own confidence breakdown wraps — see
    postprocess.py's compute_confidence_breakdown for the AI Search
    version this mirrors. Fed real company-context signals instead of a
    query's evidence bundle: real event count/urgency, real historical
    match strength, real government-exposure score, real live price
    direction. ai_certainty has no LLM call to draw from here, so it's a
    fixed neutral baseline (6/10) rather than a fabricated "AI said X" —
    flagged in its own reason line, not hidden."""
    from app.services.confidence_service import ConfidenceFactors, calculate_confidence

    top_event = events[0] if events else None
    factors = ConfidenceFactors(
        source_count=len(events),
        historical_count=1 if historical else 0,
        historical_accuracy=(historical["similarity"] / 100.0) if historical else 0.0,
        market_confirming=1 if price_positive else 0,
        company_sensitivity="high" if (gov_score or 0) >= 60 else "medium" if (gov_score or 0) >= 30 else "low",
        sector_confirming=1 if top_event and top_event.get("sentiment") == "bullish" and price_positive else 0,
        macro_aligned=False,
        ai_certainty=6,
        vix_level=0.0,
    )
    result = calculate_confidence(factors)
    bd = result.breakdown

    evidence_quality = round(min(100, (bd.get("sources", 0) + bd.get("company_sensitivity", 0) + bd.get("sector_confirmation", 0)) / 40 * 100), 1)
    market_confirmation = round(min(100, bd.get("market_confirmation", 0) / 20 * 100), 1)
    historical_similarity = round(min(100, bd.get("historical", 0) / 25 * 100), 1)
    reasoning_confidence = round(min(100, bd.get("ai_certainty", 0) / 10 * 100), 1)
    data_freshness = 100.0 if (top_event and top_event.get("lifecycle") in ("LIVE", "Developing")) else 60.0 if top_event else 40.0

    return {
        "evidence_quality": evidence_quality, "market_confirmation": market_confirmation,
        "historical_similarity": historical_similarity, "data_freshness": data_freshness,
        "reasoning_confidence": reasoning_confidence, "final_confidence": result.total_score,
        "level": result.level, "reasons": result.reasons,
    }


def _stars(confidence: float) -> int:
    return max(1, min(5, round(confidence / 20)))


async def get_company_intelligence(
    db: AsyncSession, symbol: str,
    gov_score: float | None = None, price_positive: bool | None = None,
) -> dict:
    """gov_score/price_positive are optional real signals the caller may
    already have from /api/stocks/{symbol} (this module doesn't re-fetch
    them itself — no need for a second round-trip to data the frontend
    already has); confidence just degrades to a neutral default for those
    two factors when not supplied, never a fabricated value."""
    from app.api.companies import _NSE_UNIVERSE
    from app.services.ai_search import investment_watch as watch_mod

    company = next((c for c in _NSE_UNIVERSE if c["symbol"] == symbol.upper()), None)
    if not company:
        return {"available": False}
    name, sector = company["name"], company.get("sector")

    events = await get_active_events(db, symbol.upper(), sector)
    ripple = await get_ripple_position(symbol.upper(), sector)
    historical = await get_historical(sector, name)
    opportunities = await get_related_opportunities(db, symbol.upper())

    # Read-only — the verdict snapshot itself is written by AI Search's own
    # pipeline (pipeline.py) whenever this company is searched; this only
    # reads whatever real history already exists, never writes here.
    watch = await watch_mod.get_watch(db, f"company:{symbol.upper()}", symbol.upper())

    confidence = compute_confidence_breakdown(events, historical, gov_score, price_positive)

    reasons = []
    for e in events[:3]:
        if e["headline"]:
            reasons.append(e["headline"])

    # get_watch() (the service function, called directly above — not the
    # /investment-watch route) returns None on no history, or the real
    # payload directly with no "available" wrapper (that wrapping only
    # happens in ai_search_watch.py's route). Checking `watch.get("available")`
    # here was always falsy — found live: current_verdict/last_change
    # silently stayed null even when Investment Watch had real data.
    why_matters = {
        "stars": _stars(confidence["final_confidence"]),
        "verdict": (watch or {}).get("current_verdict", {}).get("verdict_scale") if watch else None,
        "last_change": (watch or {}).get("last_change") if watch else None,
        "reasons": reasons,
        "confidence": confidence["final_confidence"],
    }

    return {
        "available": True,
        "symbol": symbol.upper(),
        "name": name,
        "why_matters": why_matters,
        "active_events": events,
        "ripple_position": ripple,
        "confidence_breakdown": confidence,
        "historical": historical,
        "investment_watch": watch,
        "related_opportunities": opportunities,
    }
