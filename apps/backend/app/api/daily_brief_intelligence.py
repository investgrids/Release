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
from datetime import datetime, timezone

import structlog
from fastapi import APIRouter

from app.db.session import AsyncSessionLocal
from app.services import daily_brief_composer as composer
from app.services import daily_brief_content as content
from app.services.market_session_state import (
    AFTER_CLOSE, HOLIDAY, OPEN, PRE_OPEN, WEEKEND, MarketSession, classify_session, ist_now,
)

router = APIRouter()
log = structlog.get_logger(__name__)


async def _get_forecast_verdict(session: MarketSession) -> dict:
    """The opening forecast. Only called before the open (session.shows_forecast); after the close, on weekends and on
    holidays the page reports the realized session and this function is never reached, so no prediction is generated."""
    from app.services.opening_prediction_service import build_opening_prediction
    try:
        async with AsyncSessionLocal() as db:
            raw = await build_opening_prediction(db)
        pred = raw.get("prediction") or {}
        return {
            "kind": "forecast",
            "headline": "Signals disagree" if (pred.get("direction_check") or {}).get("withheld") else "Opening outlook",
            "session_state": session.state,
            "target_date": session.forecast_target_date.isoformat(),
            "session_date": session.reference_session_date.isoformat(),
            "direction": pred.get("direction"),
            "confidence": pred.get("confidence"),
            "direction_check": pred.get("direction_check"),
            "forecast": raw.get("forecast"),
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
            "kind": "unavailable", "headline": "Outlook unavailable", "session_state": session.state,
            "target_date": session.forecast_target_date.isoformat(), "forecast": None, "direction_check": None,
            "direction": None, "confidence": None, "primary_drivers": [], "risks": [],
            "expected_range": {"low": None, "high": None}, "reasoning": None,
            "ai_generated": False, "generated_at": None, "unavailable": True,
        }


def _status_for(session: MarketSession) -> dict:
    """Backward-compatible market_status block, now fed by the canonical (holiday-aware) session state."""
    legacy = {PRE_OPEN: "pre_market", OPEN: "open", AFTER_CLOSE: "closed", WEEKEND: "weekend", HOLIDAY: "holiday"}[session.state]
    now = ist_now()
    return {"is_open": session.state == OPEN, "status": legacy, "time_ist": now.strftime("%I:%M %p"), "date": now.strftime("%d %b %Y")}


async def _get_snapshot(session: MarketSession) -> dict:
    from app.api.market import market_overview
    try:
        overview = await market_overview()
        movers = overview.get("movers") or {}
        indices_by_name = {i.get("name"): i for i in overview.get("indices", [])}
        return {
            "nifty": indices_by_name.get("NIFTY 50"),
            "banknifty": indices_by_name.get("BANK NIFTY"),
            "sensex": indices_by_name.get("SENSEX"),
            "vix": indices_by_name.get("INDIA VIX"),
            "breadth": overview.get("breadth"),
            "sentiment_score": overview.get("sentiment_score"),
            "market_status": _status_for(session),
            "sectors": overview.get("sectors", []),
            "movers": {"gainers": (movers.get("gainers") or [])[:3], "losers": (movers.get("losers") or [])[:3]},
        }
    except Exception as exc:
        log.warning("daily_brief_intelligence.snapshot_failed", error=str(exc))
        return {
            "nifty": None, "banknifty": None, "sensex": None, "vix": None,
            "breadth": None, "sentiment_score": None, "market_status": _status_for(session),
            "sectors": [], "movers": {"gainers": [], "losers": []}, "unavailable": True,
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


def _present_fact(f, session: MarketSession) -> dict:
    """Fact -> API row. Index claims are re-worded for the session being described ('today' is wrong on a weekend), and the
    placeholder high/low the provider derives from price (+/-0.5%) is not exposed."""
    claim, evidence = f.claim, dict(f.evidence or {})
    evidence.pop("high", None)
    evidence.pop("low", None)
    if f.entity_type == "market_index" and f.value not in (None, "", "—"):
        pct = f.numeric_value
        move = f" ({pct:+.2f}%)" if isinstance(pct, (int, float)) else ""
        when = f"in the {composer._fmt_date(session.reference_session_date)} session"
        verb = "is trading at" if session.state == OPEN else "closed at"
        claim = f"{f.name} {verb} {f.value}{move} {when}."
    return {
        "fact_key": f.fact_key, "entity_type": f.entity_type, "entity_key": f.entity_key,
        "name": f.name, "claim": claim, "value": f.value, "direction": f.direction,
        "change_pct": f.change_pct, "numeric_value": f.numeric_value,
        "confidence": f.confidence, "source": f.source, "evidence": evidence,
        "affected_sectors": f.affected_sectors, "affected_companies": f.affected_companies,
        "as_of_session": session.reference_session_date.isoformat() if f.entity_type == "market_index" else None,
        "observed_at": f.observed_at.replace(tzinfo=None).isoformat() + "Z" if f.observed_at else None,
    }


async def _get_facts(session: MarketSession) -> list[dict]:
    from app.services import fact_registry
    try:
        # refresh=True is cheap here — build_opening_prediction/market_overview
        # are both already cached (30-min / short TTL) inside those engines
        # themselves, so a same-request re-call just hits that cache. Own
        # session — this runs concurrently with other calls in the same
        # request via asyncio.gather, and AsyncSession isn't safe to share
        # across concurrently-running coroutines.
        async with AsyncSessionLocal() as db:
            facts = await fact_registry.get_facts_for_today(db, refresh=True, include_forecast=session.shows_forecast)
        # The opening-forecast fact restates the verdict card; it is never listed as evidence.
        return [_present_fact(f, session) for f in facts if f.entity_type != "macro"]
    except Exception as exc:
        log.warning("daily_brief_intelligence.facts_failed", error=str(exc))
        return []


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
                # Named in a high-priority event's text. This is attention, not an assessment of the company's outlook.
                "basis": "named_in_event",
            })
            if len(out) >= 8:
                return out
    return out


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
    today = ist_now().date()
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


@router.get("/intelligence")
async def get_daily_brief_intelligence():
    # Each of these opens its own DB session internally — AsyncSession
    # can't safely be shared across coroutines running concurrently here.
    session = classify_session()
    snapshot, raw_events, facts = await asyncio.gather(_get_snapshot(session), _read_raw_events(), _get_facts(session))
    if session.shows_forecast:
        verdict = await _get_forecast_verdict(session)
    else:
        verdict = composer.realized_verdict(session, snapshot, datetime.now(timezone.utc).isoformat())

    events_block = _tier_events(raw_events)
    historical, watch_next = await asyncio.gather(
        _get_historical_context(raw_events), _get_watch_next(),
    )

    signals_block = content.catalysts_and_risks(facts)
    ledger = content.Ledger()
    ledger.add(verdict.get("reasoning") or "")
    summary = content.build_summary(session, verdict, signals_block["catalyst_details"], signals_block["risk_details"], events_block["top"])
    ledger.add(summary)
    questions = content.build_questions(session, verdict, snapshot, events_block["top"], facts, watch_next,
                                        signals_block["risk_details"], ledger)
    evidence = content.dedupe_evidence(facts, ledger)

    return {
        "session": composer.session_block(session),
        "market_verdict": verdict,
        "market_snapshot": snapshot,
        "events": events_block,
        "facts": facts,
        "summary": summary,
        "why_today_matters": content.why_today_matters(facts),
        "stocks_to_watch": _stocks_to_watch(raw_events),
        "sector_intelligence": snapshot.get("sectors", []),
        "historical_context": historical,
        **signals_block,
        "what_to_watch_next": watch_next,
        "questions": questions,
        "evidence": evidence,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
