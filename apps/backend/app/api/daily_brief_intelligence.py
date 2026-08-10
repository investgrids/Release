"""
Daily Brief Intelligence API — the single aggregation endpoint that
connects existing, already-real engines for the Daily Brief page instead
of the frontend making N separate calls or calculating anything itself.
Nothing in this file is a new intelligence engine — every section wraps
an engine that already exists:

  - Market verdict + numeric global signals: opening_prediction_service.py
  - Market snapshot (Nifty/BankNifty/Sensex/VIX/breadth/sectors): market_overview()
  - Event tiering (Critical/High/Medium/Low): read_top_events/compute_priority
  - Facts + evidence: app/services/fact_registry.py (Phase 2)
  - Historical context: historical_memory_service.find_similar_events
  - What to watch next: /api/calendar's real economic calendar
  - Stocks to watch / Why Today Matters / Questions (AEO): all derived
    deterministically from the above — no new LLM calls, no invented text.

GET /api/daily-brief/intelligence
"""
from __future__ import annotations

import asyncio
from datetime import date, datetime, timezone

import structlog
from fastapi import APIRouter

from app.db.session import AsyncSessionLocal

router = APIRouter()
log = structlog.get_logger(__name__)


async def _get_verdict() -> dict:
    from app.services.opening_prediction_service import build_opening_prediction
    try:
        async with AsyncSessionLocal() as db:
            raw = await build_opening_prediction(db)
        pred = raw.get("prediction") or {}
        return {
            "direction": pred.get("direction", "Neutral"),
            "confidence": pred.get("confidence"),
            "primary_drivers": pred.get("primary_drivers", [])[:4],
            "risks": pred.get("risks", [])[:4],
            "expected_range": {"low": pred.get("range_low"), "high": pred.get("range_high")},
            "reasoning": pred.get("reasoning"),
            "ai_generated": pred.get("ai_generated", False),
            "generated_at": raw.get("generated_at"),
        }
    except Exception as exc:
        log.warning("daily_brief_intelligence.verdict_failed", error=str(exc))
        return {
            "direction": None, "confidence": None, "primary_drivers": [], "risks": [],
            "expected_range": {"low": None, "high": None}, "reasoning": None,
            "ai_generated": False, "generated_at": None, "unavailable": True,
        }


async def _get_snapshot() -> dict:
    from app.api.market import market_overview
    try:
        overview = await market_overview()
        indices_by_name = {i.get("name"): i for i in overview.get("indices", [])}
        return {
            "nifty": indices_by_name.get("NIFTY 50"),
            "banknifty": indices_by_name.get("BANK NIFTY"),
            "sensex": indices_by_name.get("SENSEX"),
            "vix": indices_by_name.get("INDIA VIX"),
            "breadth": overview.get("breadth"),
            "sentiment_score": overview.get("sentiment_score"),
            "market_status": overview.get("status"),
            "sectors": overview.get("sectors", []),
        }
    except Exception as exc:
        log.warning("daily_brief_intelligence.snapshot_failed", error=str(exc))
        return {
            "nifty": None, "banknifty": None, "sensex": None, "vix": None,
            "breadth": None, "sentiment_score": None, "market_status": None,
            "sectors": [], "unavailable": True,
        }


async def _read_raw_events() -> list[dict]:
    from app.services.intelligence.engine import read_top_events
    try:
        # Wide net (min_urgency=0) so tier COUNTS reflect everything triaged
        # today, not just what already passed AIPE's own publish threshold.
        return await read_top_events(limit=200, min_urgency=0, hours=24)
    except Exception as exc:
        log.warning("daily_brief_intelligence.events_failed", error=str(exc))
        return []


def _tier_events(events: list[dict]) -> dict:
    tiers = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0}
    for e in events:
        tier = e.get("priority_tier", "Low")
        tiers[tier] = tiers.get(tier, 0) + 1
    top = sorted(events, key=lambda e: e.get("priority_score", 0), reverse=True)[:5]
    return {
        "tiers": {
            "critical": tiers["Critical"], "high": tiers["High"],
            "medium": tiers["Medium"], "other": tiers["Low"],
        },
        "total": len(events),
        "top": [
            {
                "id": e.get("id"), "headline": e.get("headline"), "one_liner": e.get("one_liner"),
                "priority_tier": e.get("priority_tier"), "priority_score": e.get("priority_score"),
                "sectors": e.get("sectors"), "tickers": e.get("tickers"),
                "sentiment": e.get("sentiment"), "source": e.get("origin") or e.get("source"),
                "triaged_at": e.get("triaged_at"),
            }
            for e in top
        ],
    }


async def _get_facts() -> list[dict]:
    from app.services import fact_registry
    try:
        # refresh=True is cheap here — build_opening_prediction/market_overview
        # are both already cached (30-min / short TTL) inside those engines
        # themselves, so a same-request re-call just hits that cache. Own
        # session — this runs concurrently with other calls in the same
        # request via asyncio.gather, and AsyncSession isn't safe to share
        # across concurrently-running coroutines.
        async with AsyncSessionLocal() as db:
            facts = await fact_registry.get_facts_for_today(db, refresh=True)
        return [
            {
                "fact_key": f.fact_key, "entity_type": f.entity_type, "entity_key": f.entity_key,
                "name": f.name, "claim": f.claim, "value": f.value, "direction": f.direction,
                "confidence": f.confidence, "source": f.source, "evidence": f.evidence,
                "affected_sectors": f.affected_sectors, "affected_companies": f.affected_companies,
                "observed_at": f.observed_at.replace(tzinfo=None).isoformat() + "Z" if f.observed_at else None,
            }
            for f in facts
        ]
    except Exception as exc:
        log.warning("daily_brief_intelligence.facts_failed", error=str(exc))
        return []


def _why_today_matters(facts: list[dict]) -> list[dict]:
    """Event -> consequence -> affected entities, one bullet per real fact
    that has real affected sectors/companies — never a generic filler
    bullet, and never the same fact repeated with different wording."""
    bullets = []
    for f in facts:
        affected = (f.get("affected_sectors") or []) + (f.get("affected_companies") or [])
        if not affected:
            continue
        bullets.append({
            "event": f["name"], "consequence": f["claim"], "affected": affected[:5],
        })
        if len(bullets) >= 5:
            break
    return bullets


def _stocks_to_watch(events: list[dict]) -> list[dict]:
    """Real companies named in today's Critical/High events — not a
    ranked recommendation list, just which tickers are actually in real,
    important news today, with the real reason."""
    seen: set[str] = set()
    out = []
    for e in events:
        if e.get("priority_tier") not in ("Critical", "High"):
            continue
        for raw_sym in (e.get("tickers") or []):
            # EventTriage.tickers is LLM-extracted and sometimes carries a
            # ".NS"/".BO" exchange suffix — this app's own symbol
            # convention (used by /companies/{symbol}) never does, so an
            # unstripped suffix would silently 404 the company link.
            sym = (raw_sym or "").upper().split(".")[0]
            if not sym or sym in seen:
                continue
            seen.add(sym)
            out.append({
                "symbol": sym, "reason": e.get("one_liner") or e.get("headline"),
                "priority_tier": e.get("priority_tier"), "sentiment": e.get("sentiment"),
            })
            if len(out) >= 8:
                return out
    return out


# Entities where a RISE is bad for Indian markets (import cost pressure,
# rupee depreciation) rather than good — naively treating "direction: up"
# as always positive would mislabel rising crude/a weakening rupee as a
# "catalyst" instead of the risk it actually is.
_RISK_ON_RISE_ENTITIES = {"BRENT_CRUDE", "USD_INR"}


def _catalysts_and_risks(facts: list[dict]) -> dict:
    catalysts, risks = [], []
    for f in facts:
        entity_type = f.get("entity_type")
        name = f.get("name")

        if entity_type == "event":
            # Event facts already carry a real, LLM-assessed bullish/
            # bearish sentiment (EventTriage.sentiment) — a much more
            # honest catalyst/risk signal than re-deriving one from price
            # direction, which events don't even have.
            sentiment = (f.get("evidence") or {}).get("sentiment")
            if sentiment == "bullish":
                catalysts.append(name)
            elif sentiment == "bearish":
                risks.append(name)
            continue

        if entity_type == "macro":
            continue  # the verdict itself is a summary, not a driver to list twice

        direction = (f.get("direction") or "").lower()
        if direction not in ("up", "down", "rising", "falling"):
            continue
        rising = direction in ("up", "rising")
        bad_when_rising = f.get("entity_key") in _RISK_ON_RISE_ENTITIES
        is_risk = rising == bad_when_rising
        (risks if is_risk else catalysts).append(name)

    return {"catalysts": catalysts[:4], "risks": risks[:4]}


async def _get_historical_context(events: list[dict]) -> dict:
    from app.db.session import AsyncSessionLocal as _Session
    from app.services.historical_memory_service import find_similar_events

    sectors: list[str] = []
    for e in events:
        if e.get("priority_tier") in ("Critical", "High"):
            sectors.extend(e.get("sectors") or [])
    sectors = list(dict.fromkeys(sectors))[:3]
    if not sectors:
        return {"available": False, "message": "Not enough historical data yet."}

    try:
        similar = await find_similar_events({"sectors": sectors}, limit=5)
    except Exception as exc:
        log.warning("daily_brief_intelligence.historical_failed", error=str(exc))
        similar = []

    if not similar:
        return {"available": False, "message": "Not enough historical data yet."}

    positive = sum(1 for s in similar if (s.get("nifty_1d") or 0) > 0)
    return {
        "available": True,
        "queried_sectors": sectors,
        "count": len(similar),
        "success_rate_pct": round(positive / len(similar) * 100) if similar else None,
        "events": similar[:5],
    }


async def _get_watch_next() -> list[dict]:
    from app.api.calendar import list_calendar
    try:
        async with AsyncSessionLocal() as db:
            events = await list_calendar(db)
    except Exception as exc:
        log.warning("daily_brief_intelligence.calendar_failed", error=str(exc))
        return []
    today = date.today()
    out = []
    for ev in events:
        raw_date = getattr(ev, "date", None)
        try:
            ev_date = datetime.strptime(raw_date, "%b %d, %Y").date() if raw_date else None
        except ValueError:
            ev_date = None
        if ev_date and ev_date < today:
            continue
        out.append({
            "date": raw_date, "category": getattr(ev, "category", None),
            "title": getattr(ev, "title", None), "description": getattr(ev, "description", None),
        })
        if len(out) >= 5:
            break
    return out


def _build_questions(verdict: dict, snapshot: dict, events_block: dict, facts: list[dict]) -> list[dict]:
    """AEO — direct-answer questions built entirely from real data already
    computed above. No question is added unless a real answer exists."""
    questions = []

    nifty = snapshot.get("nifty") or {}
    if verdict.get("direction") and nifty.get("change"):
        direction_word = "falling" if not nifty.get("positive") else "rising"
        questions.append({
            "question": f"Why is Nifty {direction_word} today?",
            "answer": (verdict.get("reasoning") or f"Nifty is at {nifty.get('value')}, {nifty.get('change')} today.").strip(),
            "links": [{"label": "Market Intelligence", "href": "/market-intelligence"}],
        })

    top_events = events_block.get("top") or []
    if top_events:
        questions.append({
            "question": "What is happening in Indian markets today?",
            "answer": top_events[0].get("one_liner") or top_events[0].get("headline"),
            "links": [{"label": "View all events", "href": "/events"}],
        })

    positive_sectors = [s for s in snapshot.get("sectors", []) if s.get("positive")]
    if positive_sectors:
        names = ", ".join(s["name"] for s in positive_sectors[:3])
        questions.append({
            "question": "Which sectors are strongest today?",
            "answer": f"{names} are showing positive movement today.",
            "links": [{"label": "Sector Intelligence", "href": "/sectors"}],
        })

    crude = next((f for f in facts if f.get("entity_type") == "commodity" and "Crude" in f.get("name", "")), None)
    if crude and crude.get("affected_sectors"):
        questions.append({
            "question": "How are crude oil prices affecting Indian stocks?",
            "answer": crude["claim"] + f" This typically affects {', '.join(crude['affected_sectors'][:3])}.",
            "links": [{"label": "Commodities", "href": "/commodities"}],
        })

    return questions[:5]


@router.get("/intelligence")
async def get_daily_brief_intelligence():
    # Each of these opens its own DB session internally — AsyncSession
    # can't safely be shared across coroutines running concurrently here.
    verdict, snapshot, raw_events, facts = await asyncio.gather(
        _get_verdict(), _get_snapshot(), _read_raw_events(), _get_facts(),
    )

    events_block = _tier_events(raw_events)
    historical, watch_next = await asyncio.gather(
        _get_historical_context(raw_events), _get_watch_next(),
    )

    return {
        "market_verdict": verdict,
        "market_snapshot": snapshot,
        "events": events_block,
        "facts": facts,
        "why_today_matters": _why_today_matters(facts),
        "stocks_to_watch": _stocks_to_watch(raw_events),
        "sector_intelligence": snapshot.get("sectors", []),
        "historical_context": historical,
        **_catalysts_and_risks(facts),
        "what_to_watch_next": watch_next,
        "questions": _build_questions(verdict, snapshot, events_block, facts),
        "evidence": [
            {"claim": f["claim"], "source": f["source"], "timestamp": f["observed_at"], "confidence": f["confidence"]}
            for f in facts
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
