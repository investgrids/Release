"""
AI Search Service — Market Intelligence Research Engine.

Pipeline:
  1. In-process / Redis cache check
  2. Entity extraction (regex + keyword — fast, no AI call)
  3. Parallel DB search (events, news, policies)
  4. AI generation (single structured JSON call)
  5. Live price enrichment (yfinance, best-effort)
  6. Network graph + market chart assembly
  7. Cache store + return
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import re
import time
from typing import Any

import structlog
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models.event import Event, GovernmentPolicy
from app.db.models_legacy import NewsArticle as NewsModel
from app.services.ai_service import _call_with_fallback
from app.services.news_fetcher import get_live_news

log = structlog.get_logger(__name__)

# ── In-process cache (fallback when Redis unavailable) ───────────────────────
_CACHE: dict[str, tuple[float, Any]] = {}
_TTL = 1800  # 30 min


def _ck(query: str) -> str:
    return hashlib.md5(query.lower().strip().encode()).hexdigest()


def _cget(key: str) -> Any | None:
    e = _CACHE.get(key)
    return e[1] if e and time.time() - e[0] < _TTL else None


def _cset(key: str, val: Any) -> None:
    _CACHE[key] = (time.time(), val)


# ── Entity extraction ─────────────────────────────────────────────────────────
_COMPANIES = [
    "rvnl", "irfc", "beml", "ircon", "reliance", "tcs", "infosys", "hdfc", "icici",
    "sbi", "ntpc", "bhel", "l&t", "larsen", "hal", "bel", "adani", "tata", "wipro",
    "sun pharma", "maruti", "bajaj", "kotak", "axis", "powergrid", "ongc", "coal india",
    "irctc", "rail vikas", "indian railway", "texmaco",
]
_SECTORS = [
    "railway", "infrastructure", "banking", "it", "technology", "defence", "energy",
    "pharma", "auto", "fmcg", "metals", "realty", "telecom", "power", "finance", "logistics",
]
_POLICIES = [
    "budget", "rbi", "sebi", "gst", "pli", "fdi", "npa", "repo rate",
    "monetary policy", "fiscal policy", "make in india", "pm gati shakti",
]


def _extract_entities(query: str) -> dict:
    q = query.lower()
    return {
        "companies": [c for c in _COMPANIES if c in q],
        "sectors":   [s for s in _SECTORS   if s in q],
        "policies":  [p for p in _POLICIES   if p in q],
    }


# ── DB search helpers ─────────────────────────────────────────────────────────
def _words(query: str) -> list[str]:
    return [w for w in re.findall(r"\w+", query.lower()) if len(w) > 3][:6]


async def _search_events(db: AsyncSession, query: str, limit: int = 10) -> list[dict]:
    ws = _words(query)
    conds = [Event.title.ilike(f"%{w}%") for w in ws] + [Event.summary.ilike(f"%{w}%") for w in ws]
    stmt = (
        select(Event).where(or_(*conds)).order_by(Event.impact_score.desc()).limit(limit)
        if conds else
        select(Event).order_by(Event.impact_score.desc()).limit(limit)
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [
        {
            "id": e.id,
            "title": e.title,
            "summary": (e.summary or "")[:300],
            "category": e.category or "Market",
            "impact_score": round(float(e.impact_score or 0), 1),
            "confidence": round(float(e.confidence or 0), 1),
            "sectors": e.sectors or [],
            "companies": e.companies or [],
            "date": (
                e.event_date.strftime("%b %d, %Y") if e.event_date else
                e.published_at.strftime("%b %d, %Y") if e.published_at else ""
            ),
        }
        for e in rows
    ]


async def _search_news(db: AsyncSession, query: str, limit: int = 8) -> list[dict]:
    ws = _words(query)

    def _matches(text: str) -> bool:
        t = text.lower()
        return any(w in t for w in ws)

    results: list[dict] = []
    try:
        live = await get_live_news(limit=20) or []
        for a in live:
            if _matches(a.get("headline", "") + " " + a.get("summary", "")):
                results.append({
                    "id": a["id"], "headline": a["headline"],
                    "summary": (a.get("summary") or "")[:200],
                    "source": a.get("source", ""), "published_at": a.get("published_at", ""),
                    "impact_score": float(a.get("impact_score", 5.0)),
                    "url": a.get("url"),
                })
    except Exception:
        pass

    if len(results) < limit and ws:
        conds = [NewsModel.headline.ilike(f"%{w}%") for w in ws]
        rows = (await db.execute(select(NewsModel).where(or_(*conds)).limit(limit))).scalars().all()
        for r in rows:
            if not any(x["id"] == r.id for x in results):
                results.append({
                    "id": r.id, "headline": r.headline,
                    "summary": (r.summary or "")[:200],
                    "source": r.source, "published_at": r.published_at,
                    "impact_score": float(r.impact_score or 5.0) * 10,
                    "url": None,
                })

    return results[:limit]


async def _search_policies(db: AsyncSession, query: str, limit: int = 5) -> list[dict]:
    ws = _words(query)
    conds = [GovernmentPolicy.title.ilike(f"%{w}%") for w in ws]
    stmt = (
        select(GovernmentPolicy).where(or_(*conds)).limit(limit)
        if conds else
        select(GovernmentPolicy).limit(limit)
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [
        {
            "id": p.id, "title": p.title,
            "ministry": p.ministry or "Ministry of Finance",
            "summary": (p.summary or "")[:200],
            "status": "Active", "impact_score": 75, "url": p.url,
        }
        for p in rows
    ]


# ── AI prompt ─────────────────────────────────────────────────────────────────
_SYSTEM = (
    "You are a senior Indian equity market analyst at an institutional fund. "
    "Generate structured market intelligence for professional investors. "
    "Respond with valid JSON only. No markdown fences. No commentary."
)


def _build_prompt(query: str, events: list, news: list, policies: list) -> str:
    evs = "\n".join(f"- [{e['category']}] {e['title']} (score:{e['impact_score']:.0f})" for e in events[:5]) or "None"
    nws = "\n".join(f"- {a['headline']}" for a in news[:5]) or "None"
    pols = "\n".join(f"- {p['title']} [{p['ministry']}]" for p in policies[:3]) or "None"

    return f"""Query: "{query}"

DB Events: {evs}
News: {nws}
Policies: {pols}

Return ONLY this JSON (no fences, no extra keys):
{{
  "summary": "2-3 sentence executive summary specific to the query",
  "what_happened": "1 factual sentence about what actually happened",
  "why_it_happened": "1 contextual sentence explaining the cause",
  "immediate_impact": "1 sentence — near-term market effect",
  "medium_term": "1 sentence — 3-12 month outlook",
  "long_term": "1 sentence — structural implications",
  "risks": ["specific risk 1", "specific risk 2", "specific risk 3"],
  "opportunities": ["specific opportunity 1", "specific opportunity 2", "specific opportunity 3"],
  "confidence": 78,
  "sentiment": "bullish",
  "companies": [
    {{"symbol": "SYMBOL1", "name": "Full Company Name", "impact_type": "beneficiary", "impact_score": 90, "confidence": 85, "reason": "specific 1-line reason tied to the query"}},
    {{"symbol": "SYMBOL2", "name": "Full Company Name", "impact_type": "beneficiary", "impact_score": 85, "confidence": 80, "reason": "specific 1-line reason"}},
    {{"symbol": "SYMBOL3", "name": "Full Company Name", "impact_type": "beneficiary", "impact_score": 78, "confidence": 74, "reason": "specific 1-line reason"}},
    {{"symbol": "SYMBOL4", "name": "Full Company Name", "impact_type": "neutral",     "impact_score": 65, "confidence": 60, "reason": "specific 1-line reason"}},
    {{"symbol": "SYMBOL5", "name": "Full Company Name", "impact_type": "at_risk",     "impact_score": 45, "confidence": 55, "reason": "specific 1-line reason"}}
  ],
  "sectors": [
    {{"name": "Most Relevant Sector", "score": 90, "confidence": 85, "outlook": "Strong Growth", "positive": true}},
    {{"name": "Second Sector",        "score": 82, "confidence": 78, "outlook": "Positive",      "positive": true}},
    {{"name": "Third Sector",         "score": 70, "confidence": 65, "outlook": "Moderate",      "positive": true}},
    {{"name": "Fourth Sector",        "score": 60, "confidence": 58, "outlook": "Neutral",       "positive": true}},
    {{"name": "Affected Sector",      "score": 45, "confidence": 50, "outlook": "Cautious",      "positive": false}}
  ],
  "investment_verdict": {{
    "rating": "Strong Buy",
    "direction": "bullish",
    "confidence": 78,
    "horizon": "12-18 months",
    "top_picks": ["SYMBOL1", "SYMBOL2", "SYMBOL3"],
    "risks": ["Specific risk 1", "Specific risk 2", "Specific risk 3"],
    "catalysts": ["Specific catalyst 1", "Specific catalyst 2", "Specific catalyst 3"],
    "opportunity_score": 85
  }},
  "similar_events": [
    {{"title": "Relevant historical event title", "date": "Month Year", "outcome": "What happened to relevant stocks/sectors", "winners": ["SYMBOL1", "SYMBOL2"], "losers": ["SYMBOL3"], "similarity": 0.80}},
    {{"title": "Another relevant historical event", "date": "Month Year", "outcome": "Market outcome description", "winners": ["SYMBOL4"], "losers": ["SYMBOL5"], "similarity": 0.65}}
  ],
  "follow_up_questions": [
    "Specific follow-up question relevant to this query?",
    "Another specific follow-up question?",
    "Third specific follow-up question?",
    "Fourth specific follow-up question?"
  ],
  "timeline": [
    {{"date": "Near-term date", "title": "First milestone title", "description": "What happens at this stage"}},
    {{"date": "Mid-term date",  "title": "Second milestone",      "description": "What happens next"}},
    {{"date": "Later date",     "title": "Third milestone",       "description": "What happens after"}},
    {{"date": "Long-term date", "title": "Final milestone",       "description": "Long-term outcome"}}
  ]
}}

CRITICAL: The "insights" titles must be SPECIFIC to the query "{query}" — choose angles that make sense for this exact topic. Use real NSE symbols, actual rupee amounts, and genuine Indian market context throughout."""


# ── Insight card generation (separate focused call) ───────────────────────────
async def _generate_insights(query: str, summary: str) -> list[dict]:
    """
    Dedicated call for 4 insight cards so the model isn't distracted by
    the large main JSON template. Returns a list of {icon, title, summary}.
    """
    prompt = (
        f'Market query: "{query}"\n'
        f"Context: {summary[:300]}\n\n"
        "Return a JSON array of exactly 4 insight cards for this specific query.\n"
        "Each card: {\"icon\": <single emoji>, \"title\": <4-6 words>, \"summary\": <1 short sentence, max 20 words>}\n\n"
        "The title must be a unique analytical angle relevant to THIS exact query.\n"
        "Example — for 'Infosys Q4 miss': [\"Revenue Guidance Shock\", \"Deal Win Momentum\", \"Margin Pressure Analysis\", \"Peer Valuation Reset\"]\n"
        "Example — for 'RBI rate cut': [\"Rate Transmission Speed\", \"NIM Expansion Outlook\", \"Credit Demand Catalyst\", \"Bond Market Rally\"]\n"
        "Example — for 'Defence CAPEX hike': [\"Order Book Surge\", \"Make-in-India Push\", \"Export Market Entry\", \"R&D Investment Cycle\"]\n\n"
        "Return ONLY the JSON array, no other text."
    )
    raw = await _call_with_fallback(prompt, max_tokens=1000)
    if not raw:
        return []
    try:
        clean = raw.strip()
        if clean.startswith("```"):
            clean = re.sub(r"^```(?:json)?\s*", "", clean)
            clean = re.sub(r"\s*```$", "", clean).strip()
        parsed = json.loads(clean)
        if isinstance(parsed, list):
            return parsed[:4]
        # Model returned {"insights": [...]} or similar wrapper
        if isinstance(parsed, dict):
            for v in parsed.values():
                if isinstance(v, list) and v:
                    return v[:4]
    except Exception:
        # Truncated JSON — extract any complete array items via regex
        m = re.search(r"\[.*\]", raw, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())[:4]
            except Exception:
                pass
        # Try to salvage partial items: find all complete {...} objects inside the array
        items = re.findall(r'\{[^{}]+\}', raw, re.DOTALL)
        result = []
        for item in items[:4]:
            try:
                result.append(json.loads(item))
            except Exception:
                pass
        if result:
            return result
    return []


# ── Company price enrichment ──────────────────────────────────────────────────
def _enrich_sync(companies: list[dict]) -> list[dict]:
    """Add live prices synchronously (runs in executor)."""
    from app.services.market_data import _fetch_quote, _fmt_price, _fetch_history
    enriched = []
    for c in companies:
        sym = c.get("symbol", "")
        # Strip exchange suffix if AI already included it (e.g. HDFCBANK.NS → HDFCBANK)
        sym_base = re.sub(r'\.(NS|BO|BSE|NSE)$', '', sym.strip().upper())
        try:
            q = _fetch_quote(f"{sym_base}.NS")
            if q:
                c["price"]    = _fmt_price(q["price"])
                c["change"]   = f"{'+' if q['positive'] else ''}{q['pct']:.2f}%"
                c["positive"] = q["positive"]
                # Tiny sparkline (5d daily)
                hist = _fetch_history(f"{sym_base}.NS", "5d", "1d")
                c["chart"] = [h["value"] for h in (hist or [])][-5:]
            else:
                c["price"] = "—"; c["change"] = "—"; c["positive"] = True; c["chart"] = []
        except Exception:
            c["price"] = "—"; c["change"] = "—"; c["positive"] = True; c["chart"] = []
        enriched.append(c)
    return enriched


# ── Market chart ──────────────────────────────────────────────────────────────
def _fetch_chart_sync(_: list) -> dict:
    """Fetch 1D intraday chart for 3 indices (runs in executor)."""
    from app.services.market_data import _fetch_history

    def _norm(hist: list[dict]) -> list[float]:
        if not hist:
            return []
        base = hist[0]["value"] or 1
        return [round((h["value"] / base - 1) * 100, 3) for h in hist]

    try:
        n  = _fetch_history("^NSEI",   "1d", "60m") or []
        b  = _fetch_history("^NSEBANK","1d", "60m") or []
        it = _fetch_history("^CNXIT",  "1d", "60m") or []
        labels = [h["label"] for h in n]
        return {
            "labels": labels,
            "series": [
                {"name": "Nifty 50",    "data": _norm(n),  "color": "#818cf8"},
                {"name": "Bank Nifty",  "data": _norm(b),  "color": "#34d399"},
                {"name": "Nifty IT",    "data": _norm(it), "color": "#fb923c"},
            ],
        }
    except Exception:
        return {"labels": [], "series": []}


# ── Network graph ─────────────────────────────────────────────────────────────
def _build_graph(query: str, sectors: list[dict], companies: list[dict]) -> dict:
    nodes: list[dict] = []
    edges: list[dict] = []

    q_label = query[:28] + ("…" if len(query) > 28 else "")
    nodes.append({"id": "q",  "label": q_label, "type": "query",  "x": 360, "y": 0})

    for i, s in enumerate(sectors[:5]):
        sid = f"s{i}"
        nodes.append({"id": sid, "label": s["name"], "type": "sector", "x": i * 180, "y": 140})
        edges.append({"id": f"q-{sid}", "source": "q", "target": sid, "label": "impacts"})

    for j, c in enumerate(companies[:5]):
        cid = f"c{j}"
        nodes.append({"id": cid, "label": c["symbol"], "type": "company", "x": j * 175, "y": 290})
        parent_id = f"s{j % max(len(sectors[:5]), 1)}"
        edges.append({"id": f"{parent_id}-{cid}", "source": parent_id, "target": cid, "label": "benefits"})

    return {"nodes": nodes, "edges": edges}


# ── Main pipeline ─────────────────────────────────────────────────────────────
async def run_ai_search(query: str, db: AsyncSession) -> dict:
    """Full AI search pipeline. Returns complete research report dict."""
    ck = _ck(query)
    cached = _cget(ck)
    if cached:
        log.info("ai_search.cache_hit", query=query[:50])
        return cached

    log.info("ai_search.start", query=query[:50])
    entities = _extract_entities(query)
    loop = asyncio.get_running_loop()

    # Parallel: DB search + market chart
    events, news, policies, chart = await asyncio.gather(
        _search_events(db, query),
        _search_news(db, query),
        _search_policies(db, query),
        loop.run_in_executor(None, _fetch_chart_sync, []),
        return_exceptions=True,
    )
    if isinstance(events,   Exception): events   = []
    if isinstance(news,     Exception): news     = []
    if isinstance(policies, Exception): policies = []
    if isinstance(chart,    Exception): chart    = {"labels": [], "series": []}

    # AI generation — tries fastest free model first, falls back in order
    prompt = _build_prompt(query, events, news, policies)
    raw = await _call_with_fallback(prompt, _SYSTEM, max_tokens=3000)
    log.info("ai_search.raw_len", chars=len(raw) if raw else 0, starts=raw[:60] if raw else "")

    ai: dict = {}
    if raw:
        try:
            clean = raw.strip()
            # Strip markdown code fences (model often wraps with ```json ... ```)
            if clean.startswith("```"):
                clean = re.sub(r"^```(?:json)?\s*", "", clean)
                clean = re.sub(r"\s*```$", "", clean).strip()
            ai = json.loads(clean)
        except json.JSONDecodeError:
            # Try extracting first JSON object from response
            m = re.search(r"\{.*\}", raw, re.DOTALL)
            if m:
                try:
                    ai = json.loads(m.group())
                except Exception:
                    pass
            if not ai:
                log.warning("ai_search.json_parse_fail", raw=raw[:300])

    # Graceful defaults when AI fails
    if not ai:
        ai = {
            "summary": f"Market intelligence analysis for: {query}. Analysis based on real-time database events and news.",
            "what_happened": "A significant market development has been identified related to the queried topic.",
            "why_it_happened": "Multiple macro, policy, and sector-specific factors are driving this development.",
            "immediate_impact": "Near-term markets are reacting to this development with sector-specific movement.",
            "medium_term": "The 3-12 month outlook depends on policy execution and global macro environment.",
            "long_term": "Structural implications are broadly positive for India's capital markets.",
            "risks": ["Execution risk", "Global headwinds", "Regulatory uncertainty"],
            "opportunities": ["Sector rotation", "Infrastructure capex", "Export growth"],
            "confidence": 60, "sentiment": "neutral",
            "insights": [
                {"icon": "📊", "title": "Market Overview",   "summary": "Current market conditions reflect mixed global and domestic signals with selective sector strength."},
                {"icon": "🏛️", "title": "Policy Framework", "summary": "Government policy remains focused on infrastructure, manufacturing, and economic growth enablement."},
                {"icon": "🏆", "title": "Sector Leaders",   "summary": "Infrastructure and defence sectors are well positioned to outperform peers in this environment."},
                {"icon": "⚠️", "title": "Risk Watch",       "summary": "Monitor global commodity prices, currency movements, and domestic fiscal deficit trajectory."},
            ],
            "companies": [], "sectors": [], "similar_events": [], "timeline": [],
            "follow_up_questions": ["Which sectors benefit most?", "What is the timeline?", "Key risks?", "Historical precedents?"],
            "investment_verdict": {
                "rating": "Neutral", "direction": "neutral", "confidence": 55,
                "horizon": "6-12 months", "top_picks": [],
                "risks": ["Macro uncertainty"], "catalysts": ["Policy clarity"],
                "opportunity_score": 60,
            },
        }

    # Enrich companies with live prices (in thread executor)
    raw_cos = ai.get("companies", [])
    ai_summary = ai.get("summary", query)
    try:
        companies_enriched = await loop.run_in_executor(None, _enrich_sync, raw_cos) if raw_cos else []
    except Exception as _e:
        log.warning("ai_search.enrich_fail", exc=str(_e)[:80])
        companies_enriched = []

    # Generate dynamic insights (sequential, after main call)
    try:
        insights = await _generate_insights(query, ai_summary)
    except Exception as _e:
        log.warning("ai_search.insights_fail", exc=str(_e)[:80])
        insights = []

    graph = _build_graph(query, ai.get("sectors", []), companies_enriched)

    result = {
        "query": query,
        "entities": entities,
        "answer": {
            "summary":          ai.get("summary", ""),
            "what_happened":    ai.get("what_happened", ""),
            "why_it_happened":  ai.get("why_it_happened", ""),
            "immediate_impact": ai.get("immediate_impact", ""),
            "medium_term":      ai.get("medium_term", ""),
            "long_term":        ai.get("long_term", ""),
            "risks":            ai.get("risks", []),
            "opportunities":    ai.get("opportunities", []),
            "confidence":       ai.get("confidence", 65),
            "sentiment":        ai.get("sentiment", "neutral"),
            "sources_count":    len(news) + len(events),
        },
        "insights":             insights or ai.get("insights", []),
        "companies":            companies_enriched,
        "sectors":              ai.get("sectors", []),
        "related_events":       events[:6],
        "news":                 news[:6],
        "policies":             policies[:4],
        "timeline":             ai.get("timeline", []),
        "similar_events":       ai.get("similar_events", []),
        "follow_up_questions":  ai.get("follow_up_questions", []),
        "investment_verdict":   ai.get("investment_verdict", {}),
        "market_chart":         chart,
        "graph":                graph,
        "citations":            list({a.get("source", "") for a in news if a.get("source")}),
    }

    _cset(ck, result)
    log.info("ai_search.done", query=query[:50], cos=len(companies_enriched), events=len(events))
    return result
