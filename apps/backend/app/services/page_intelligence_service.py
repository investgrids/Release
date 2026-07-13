"""
Page Intelligence Service — the single intelligence brain.

Every page endpoint calls one function here, which:
  1. Pulls all relevant context from DB + MIE state
  2. Makes ONE AI call with all that context
  3. Returns a standardized intelligence object

Pages never generate their own intelligence. Pages only render.

Contexts: home | company | event | theme | news | search
"""
from __future__ import annotations

import json
import re
import time
import structlog
from datetime import datetime, timezone, timedelta
from typing import Any

log = structlog.get_logger(__name__)

# ── In-memory cache ───────────────────────────────────────────────────────────
_CACHE: dict[str, tuple[float, dict]] = {}

_CONTEXT_TTL: dict[str, int] = {
    "home":    900,    # 15 min
    "company": 1800,   # 30 min
    "event":   3600,   # 1 hour
    "theme":   900,    # 15 min
    "news":    7200,   # 2 hours
    "search":  300,    # 5 min
}

def _ck(ctype: str, cid: str = "") -> str:
    return f"pi:{ctype}:{cid.lower()[:80]}"

def _cget(key: str, ttl: int) -> dict | None:
    entry = _CACHE.get(key)
    if entry and (time.time() - entry[0]) < ttl:
        return entry[1]
    return None

def _cset(key: str, value: dict) -> None:
    _CACHE[key] = (time.time(), value)


# ── AI system prompt ──────────────────────────────────────────────────────────
_SYSTEM = (
    "You are the MarketRipple Intelligence Engine — the AI brain for Indian stock market analysis. "
    "Given any market context (event, company, news, theme, or macro), generate precise, professional, "
    "actionable intelligence that a fund manager would rely on. "
    "Always respond with valid JSON only. No markdown fences. No extra text. "
    "Ground everything in the provided data. Name specific companies, prices, and sectors where given."
)

# ── Standard JSON schema ──────────────────────────────────────────────────────
_SCHEMA = """{
  "market_story": "2-3 sentences: what is happening and why it matters for Indian markets",
  "key_takeaway": "The single most important insight an investor must not miss — one sentence",
  "opportunities": [
    {"title": "Short name", "description": "Specific detail with companies/numbers", "companies": ["NSE_TICKER"], "horizon": "short|medium|long", "confidence": 75}
  ],
  "risks": [
    {"title": "Risk name", "description": "Specific description of the risk", "severity": "high|medium|low"}
  ],
  "companies": [
    {"symbol": "NSE_TICKER", "name": "Full Name", "stance": "bullish|bearish|neutral", "reason": "One-line reason", "confidence": 72}
  ],
  "sectors": [
    {"name": "Sector Name", "outlook": "positive|negative|neutral", "score": 75, "reason": "Why this sector is affected"}
  ],
  "themes": [
    {"name": "Theme Name", "strength": "strong|moderate|weak", "description": "Current relevance to markets"}
  ],
  "historical_context": "What happened in similar past situations and what the outcome was — be specific",
  "monitoring_points": [
    "Specific thing to watch — data point, event, or threshold",
    "Second monitoring point",
    "Third monitoring point",
    "Fourth monitoring point"
  ],
  "confidence_self_rating": 7
}"""


# ── Shared helpers ────────────────────────────────────────────────────────────
def _safe_list(val: Any) -> list:
    return val if isinstance(val, list) else []


def _parse_ai(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        clean = raw.strip()
        if clean.startswith("```"):
            clean = re.sub(r"^```(?:json)?\s*", "", clean)
            clean = re.sub(r"\s*```$", "", clean).strip()
        return json.loads(clean)
    except Exception:
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except Exception:
                pass
    return {}


def _build_confidence(ai: dict, source_count: int, similar: list) -> dict:
    try:
        from app.services.confidence_service import ConfidenceFactors, calculate_confidence
        factors = ConfidenceFactors(
            source_count=source_count,
            historical_count=len(similar),
            historical_accuracy=(
                sum(s.get("confidence", 80) for s in similar) / (100.0 * len(similar))
                if similar else 0.0
            ),
            ai_certainty=min(10, max(1, int(ai.get("confidence_self_rating", 5) or 5))),
        )
        res = calculate_confidence(factors)
        raw_score = round(res.total_score)

        # Apply learning engine calibration factor (evidence-based accuracy adjustment)
        calibration_note: str | None = None
        try:
            from app.services.prediction_service import get_calibration_data
            cal = get_calibration_data()
            cal_entry = cal.get("aipe") or cal.get("overall") or {}
            factor = float(cal_entry.get("calibration_factor", 1.0))
            if 0.5 <= factor <= 1.5 and factor != 1.0:
                raw_score = round(min(95, max(10, raw_score * factor)))
                calibration_note = (
                    f"Calibrated ×{factor:.2f} from "
                    f"{cal_entry.get('total_predictions', 0)} past predictions"
                )
        except Exception:
            pass

        reasons = list(res.reasons)
        if calibration_note:
            reasons.append(calibration_note)

        return {
            "level":     res.level,
            "score":     raw_score,
            "reasons":   reasons,
            "breakdown": dict(res.breakdown),
        }
    except Exception:
        return {"level": "Medium", "score": 55, "reasons": [], "breakdown": {}}


def _wrap(ai: dict, conf: dict, ctype: str, cid: str) -> dict:
    return {
        "market_story":         ai.get("market_story", ""),
        "key_takeaway":         ai.get("key_takeaway", ""),
        "opportunities":        _safe_list(ai.get("opportunities")),
        "risks":                _safe_list(ai.get("risks")),
        "companies":            _safe_list(ai.get("companies")),
        "sectors":              _safe_list(ai.get("sectors")),
        "themes":               _safe_list(ai.get("themes")),
        "historical_context":   ai.get("historical_context", ""),
        "monitoring_points":    _safe_list(ai.get("monitoring_points")),
        "related_intelligence": [],
        "confidence":           conf,
        "generated_at":         datetime.now(timezone.utc).isoformat(),
        "context_type":         ctype,
        "context_id":           cid or None,
    }


def _fallback(ctype: str, cid: str = "") -> dict:
    return _wrap({}, {"level": "Low", "score": 20, "reasons": ["Insufficient data"], "breakdown": {}}, ctype, cid)


async def _ai_call(ctype: str, cid: str, context_data: str, source_count: int = 0, similar: list | None = None) -> dict:
    from app.services.ai_service import _call_with_fallback
    prompt = (
        f"CONTEXT TYPE: {ctype.upper()}\n"
        f"CONTEXT ID: {cid or 'N/A'}\n\n"
        f"{context_data}\n\n"
        f"Return ONLY this JSON structure:\n{_SCHEMA}"
    )
    raw = await _call_with_fallback(prompt, _SYSTEM, max_tokens=1800)
    ai  = _parse_ai(raw)
    conf = _build_confidence(ai, source_count, similar or [])
    return _wrap(ai, conf, ctype, cid)


# ══════════════════════════════════════════════════════════════════════════════
# Public intelligence generators — one per context type
# ══════════════════════════════════════════════════════════════════════════════

async def get_home_intelligence() -> dict:
    """Macro-level market intelligence for the home page."""
    ck, ttl = _ck("home"), _CONTEXT_TTL["home"]
    if (cached := _cget(ck, ttl)):
        return cached

    try:
        # MIE state (cached — no extra AI call)
        mie: dict = {}
        try:
            from app.services.intelligence.engine import get_intelligence_state
            mie = await get_intelligence_state()
        except Exception:
            pass

        signals  = mie.get("signals", {})
        top_evts = [e for e in mie.get("top_events", []) if e.get("urgency", 0) >= 5][:6]

        from app.db.session import AsyncSessionLocal
        from app.db.models_legacy import Event, NewsArticle
        from sqlalchemy import select, desc

        async with AsyncSessionLocal() as db:
            events = (await db.execute(
                select(Event).order_by(desc(Event.impact_score)).limit(8)
            )).scalars().all()
            news_rows = (await db.execute(
                select(NewsArticle)
                .where(NewsArticle.created_at >= datetime.now(timezone.utc) - timedelta(hours=24))
                .order_by(desc(NewsArticle.impact_score))
                .limit(6)
            )).scalars().all()

        similar: list = []
        try:
            from app.services.historical_memory_service import find_similar_events
            similar = await find_similar_events(
                {"sentiment": signals.get("direction", ""), "category": None, "sectors": []},
                limit=4, min_similarity=25.0,
            )
        except Exception:
            pass

        parts = [
            f"DATE: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
            f"MARKET MOOD: {signals.get('mood', 'Unknown')} | DIRECTION: {signals.get('direction', 'Unknown')} | RISK: {signals.get('risk_level', 'MODERATE')}",
            f"TOP THEME: {signals.get('top_theme', 'N/A')} (score: {signals.get('top_theme_score', 0):.0f})",
        ]
        if top_evts:
            parts.append("LIVE HIGH-URGENCY EVENTS:")
            for e in top_evts[:5]:
                parts.append(f"  [{e['urgency']}/10] {(e.get('one_liner') or e.get('headline', ''))[:100]}")
        if events:
            parts.append("TOP DB EVENTS:")
            for ev in events[:5]:
                parts.append(f"  [{ev.category or 'General'}] {ev.title} (score: {ev.impact_score:.0f})")
        if news_rows:
            parts.append("RECENT NEWS (24h):")
            for n in news_rows[:5]:
                parts.append(f"  - {n.headline[:100]}")
        if similar:
            parts.append("HISTORICAL PRECEDENTS:")
            for s in similar:
                parts.append(f"  - {s.get('title', '')} → {s.get('outcome', '')[:80]}")

        result = await _ai_call(
            "home", "", "\n".join(parts),
            source_count=len(events) + len(news_rows), similar=similar,
        )
        result["related_intelligence"] = [
            {"type": "event", "id": str(ev.id), "title": ev.title, "relevance_score": ev.impact_score or 50}
            for ev in events[:4]
        ]
        _cset(ck, result)
        return result

    except Exception as exc:
        log.error("intelligence.home_failed", error=str(exc))
        return _fallback("home")


async def get_company_intelligence(symbol: str) -> dict:
    """Company-specific intelligence for a given NSE ticker."""
    sym = symbol.upper()
    ck, ttl = _ck("company", sym), _CONTEXT_TTL["company"]
    if (cached := _cget(ck, ttl)):
        return cached

    try:
        from app.db.session import AsyncSessionLocal
        from app.db.models.intelligence import EventTriage
        from app.db.models_legacy import NewsArticle
        from sqlalchemy import select, desc

        async with AsyncSessionLocal() as db:
            # EventTriage rows mentioning this ticker
            triage_rows = (await db.execute(
                select(EventTriage).order_by(desc(EventTriage.triaged_at)).limit(40)
            )).scalars().all()

            news_rows = (await db.execute(
                select(NewsArticle).order_by(desc(NewsArticle.created_at)).limit(10)
            )).scalars().all()

        # Filter triage to rows mentioning this symbol
        sym_lower = sym.lower()
        company_triage = [
            r for r in triage_rows
            if any(sym_lower in (t or "").lower() for t in (r.tickers or []))
            or sym_lower in (r.headline or "").lower()
        ][:6]

        # Filter news mentioning this symbol
        company_news = [
            n for n in news_rows
            if sym_lower in (n.headline or "").lower()
            or any(sym_lower in (c or "").lower() for c in (n.companies or []))
        ][:5]

        # Fallback: if nothing company-specific, use recent context
        if not company_triage:
            company_triage = triage_rows[:4]
        if not company_news:
            company_news = news_rows[:4]

        # Inject MIE master story as base context — all pages share the same story
        mie_story = ""
        mie_mood = ""
        try:
            from app.services.intelligence.engine import get_intelligence_state
            mie = await get_intelligence_state()
            mie_story = mie.get("story", "")
            mie_mood  = mie.get("signals", {}).get("mood", "")
        except Exception:
            pass

        parts = [f"COMPANY: {sym}", "EXCHANGE: NSE India"]
        if mie_story:
            parts.append(f"MASTER MARKET NARRATIVE: {mie_story[:300]}")
        if mie_mood:
            parts.append(f"MARKET MOOD: {mie_mood}")
        if company_triage:
            parts.append("RECENT MARKET EVENTS RELATED TO THIS COMPANY:")
            for r in company_triage:
                parts.append(f"  [{r.urgency}/10 urgency, {r.sentiment}] {r.headline[:120]}")
                if r.one_liner:
                    parts.append(f"    → {r.one_liner[:100]}")
        if company_news:
            parts.append("RECENT NEWS:")
            for n in company_news:
                parts.append(f"  - {n.headline[:100]}")

        result = await _ai_call(
            "company", sym, "\n".join(parts),
            source_count=len(company_triage) + len(company_news),
        )
        _cset(ck, result)
        return result

    except Exception as exc:
        log.error("intelligence.company_failed", symbol=sym, error=str(exc))
        return _fallback("company", sym)


async def get_event_intelligence(event_id: str) -> dict:
    """Intelligence for a specific market event."""
    ck, ttl = _ck("event", event_id), _CONTEXT_TTL["event"]
    if (cached := _cget(ck, ttl)):
        return cached

    try:
        from app.db.session import AsyncSessionLocal
        from app.db.models_legacy import Event, NewsArticle
        from sqlalchemy import select, desc

        async with AsyncSessionLocal() as db:
            event = (await db.execute(
                select(Event).where(Event.id == event_id)
            )).scalar_one_or_none()

            if not event:
                return _fallback("event", event_id)

            news_rows = (await db.execute(
                select(NewsArticle).order_by(desc(NewsArticle.impact_score)).limit(5)
            )).scalars().all()

        similar: list = []
        try:
            from app.services.historical_memory_service import find_similar_events
            similar = await find_similar_events(
                {"category": event.category, "sectors": list(event.sectors or [])[:4], "sentiment": None},
                limit=5, min_similarity=20.0,
            )
        except Exception:
            pass

        # Inject MIE master story as base context
        mie_story = ""
        try:
            from app.services.intelligence.engine import get_intelligence_state
            mie = await get_intelligence_state()
            mie_story = mie.get("story", "")
        except Exception:
            pass

        parts = [
            f"EVENT: {event.title}",
            f"CATEGORY: {event.category or 'General'}",
            f"IMPACT SCORE: {(event.impact_score or 0):.0f}/100",
            f"SUMMARY: {(event.summary or '')[:400]}",
        ]
        if mie_story:
            parts.append(f"MASTER MARKET NARRATIVE: {mie_story[:250]}")
        if event.sectors:
            parts.append(f"SECTORS: {', '.join(event.sectors)}")
        if event.companies:
            parts.append(f"COMPANIES: {', '.join(event.companies)}")
        if news_rows:
            parts.append("RELATED MARKET NEWS:")
            for n in news_rows[:4]:
                parts.append(f"  - {n.headline[:100]}")
        if similar:
            parts.append("HISTORICAL PRECEDENTS:")
            for s in similar:
                parts.append(f"  - {s.get('title', '')} ({s.get('date', '')}): {s.get('outcome', '')[:80]}")

        result = await _ai_call(
            "event", event_id, "\n".join(parts),
            source_count=len(news_rows) + 1, similar=similar,
        )
        _cset(ck, result)
        return result

    except Exception as exc:
        log.error("intelligence.event_failed", event_id=event_id, error=str(exc))
        return _fallback("event", event_id)


async def get_theme_intelligence(theme_id: str) -> dict:
    """Intelligence for a market theme."""
    ck, ttl = _ck("theme", theme_id), _CONTEXT_TTL["theme"]
    if (cached := _cget(ck, ttl)):
        return cached

    try:
        theme_name = theme_id.replace("-", " ").title()

        from app.db.session import AsyncSessionLocal
        from app.db.models.intelligence import EventTriage
        from sqlalchemy import select, desc

        async with AsyncSessionLocal() as db:
            rows = (await db.execute(
                select(EventTriage).order_by(desc(EventTriage.triaged_at)).limit(40)
            )).scalars().all()

        # Filter to rows tagged with this theme
        theme_lower = theme_name.lower()
        themed = [
            r for r in rows
            if any(theme_lower in (t or "").lower() for t in (r.themes or []))
            or theme_lower in (r.headline or "").lower()
        ][:8]

        if not themed:
            themed = rows[:6]  # fallback: recent market context

        # Inject MIE master story as base context
        mie_story = ""
        mie_top_theme = ""
        try:
            from app.services.intelligence.engine import get_intelligence_state
            mie = await get_intelligence_state()
            mie_story     = mie.get("story", "")
            mie_top_theme = mie.get("signals", {}).get("top_theme", "")
        except Exception:
            pass

        parts = [f"THEME: {theme_name}"]
        if mie_story:
            parts.append(f"MASTER MARKET NARRATIVE: {mie_story[:250]}")
        if mie_top_theme:
            parts.append(f"CURRENT DOMINANT THEME: {mie_top_theme}")
        if themed:
            parts.append("RELATED MARKET EVENTS:")
            for r in themed[:6]:
                parts.append(f"  [{r.urgency}/10, {r.sentiment}] {r.headline[:120]}")
                if r.one_liner:
                    parts.append(f"    → {r.one_liner[:80]}")

        all_sectors = []
        all_tickers = []
        for r in themed:
            all_sectors.extend(r.sectors or [])
            all_tickers.extend(r.tickers or [])
        if all_sectors:
            parts.append(f"AFFECTED SECTORS: {', '.join(list(dict.fromkeys(all_sectors))[:6])}")
        if all_tickers:
            parts.append(f"AFFECTED COMPANIES: {', '.join(list(dict.fromkeys(all_tickers))[:8])}")

        result = await _ai_call(
            "theme", theme_id, "\n".join(parts),
            source_count=len(themed),
        )
        _cset(ck, result)
        return result

    except Exception as exc:
        log.error("intelligence.theme_failed", theme_id=theme_id, error=str(exc))
        return _fallback("theme", theme_id)


async def get_news_intelligence(news_id: str) -> dict:
    """Intelligence for a specific news article."""
    ck, ttl = _ck("news", news_id), _CONTEXT_TTL["news"]
    if (cached := _cget(ck, ttl)):
        return cached

    try:
        from app.db.session import AsyncSessionLocal
        from app.db.models_legacy import NewsArticle, Event
        from sqlalchemy import select, desc

        async with AsyncSessionLocal() as db:
            article = (await db.execute(
                select(NewsArticle).where(NewsArticle.id == news_id)
            )).scalar_one_or_none()

            if not article:
                return _fallback("news", news_id)

            related_events = (await db.execute(
                select(Event).order_by(desc(Event.impact_score)).limit(4)
            )).scalars().all()

        parts = [
            f"HEADLINE: {article.headline}",
            f"SOURCE: {article.source}",
            f"SUMMARY: {(article.summary or '')[:400]}",
            f"IMPACT SCORE: {article.impact_score:.0f}",
        ]
        if article.companies:
            parts.append(f"COMPANIES: {', '.join(article.companies[:6])}")
        if related_events:
            parts.append("CURRENT MARKET CONTEXT (top events):")
            for ev in related_events[:3]:
                parts.append(f"  - {ev.title} (score: {(ev.impact_score or 0):.0f})")

        result = await _ai_call("news", news_id, "\n".join(parts), source_count=1)
        _cset(ck, result)
        return result

    except Exception as exc:
        log.error("intelligence.news_failed", news_id=news_id, error=str(exc))
        return _fallback("news", news_id)


async def get_search_intelligence(query: str) -> dict:
    """Intelligence for a free-text search query — wraps the AI search pipeline."""
    q = query.strip()
    ck, ttl = _ck("search", q[:80]), _CONTEXT_TTL["search"]
    if (cached := _cget(ck, ttl)):
        return cached

    try:
        from app.db.session import AsyncSessionLocal
        from app.services.ai_search_service import run_ai_search

        async with AsyncSessionLocal() as db:
            raw = await run_ai_search(q, db)

        answer = raw.get("answer", {})
        conf_d = raw.get("confidence_data", {})

        result: dict = {
            "market_story":       answer.get("summary", ""),
            "key_takeaway":       answer.get("immediate_impact", ""),
            "opportunities": [
                {"title": o, "description": o, "companies": [], "horizon": "medium", "confidence": 65}
                for o in _safe_list(answer.get("opportunities"))
            ],
            "risks": [
                {"title": r, "description": r, "severity": "medium"}
                for r in _safe_list(answer.get("risks"))
            ],
            "companies": [
                {
                    "symbol":     c.get("symbol", ""),
                    "name":       c.get("name", ""),
                    "stance":     (
                        "bullish" if c.get("impact_type") == "beneficiary" else
                        "bearish" if c.get("impact_type") == "at_risk" else "neutral"
                    ),
                    "reason":     c.get("reason", ""),
                    "confidence": c.get("confidence", 65),
                }
                for c in _safe_list(raw.get("companies"))[:6]
            ],
            "sectors": [
                {
                    "name":    s.get("name", ""),
                    "outlook": "positive" if s.get("positive") else "negative",
                    "score":   s.get("score", 60),
                    "reason":  s.get("outlook", ""),
                }
                for s in _safe_list(raw.get("sectors"))[:5]
            ],
            "themes":             [],
            "historical_context": "",
            "monitoring_points":  _safe_list(answer.get("risks"))[:4],
            "related_intelligence": [],
            "confidence":  conf_d or {"level": "Medium", "score": 60, "reasons": [], "breakdown": {}},
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "context_type": "search",
            "context_id":   q,
        }
        _cset(ck, result)
        return result

    except Exception as exc:
        log.error("intelligence.search_failed", query=q[:50], error=str(exc))
        return _fallback("search", q)


def invalidate(context_type: str, context_id: str = "") -> None:
    """Evict a specific entry from the in-memory cache."""
    _CACHE.pop(_ck(context_type, context_id), None)
