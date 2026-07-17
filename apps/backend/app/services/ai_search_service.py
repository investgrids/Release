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


def _cget(key: str, ttl: int = _TTL) -> Any | None:
    e = _CACHE.get(key)
    return e[1] if e and time.time() - e[0] < ttl else None


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
    return [w for w in re.findall(r"\w+", query.lower()) if len(w) >= 2][:8]


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


# ── Intent detection ──────────────────────────────────────────────────────────
_DECISION_INTENTS = {
    "switch":           [r"\bswitch(?:ing)?\b", r"\brotate?\b", r"\binstead of\b", r"\bsell.{1,30}buy\b", r"\bmove from\b", r"\breplace\b"],
    "hold":             [r"\bshould i hold\b", r"\bkeep holding\b", r"\bcontinue holding\b", r"\bstill hold\b", r"\bhold or sell\b"],
    "compare":          [r"\bcompare\b", r"\bvs\.?\b", r"\bversus\b", r"\bbetter than\b", r"\bwhich is better\b", r"\bwhich (?:one|company|stock)\b"],
    "sell":             [r"\bshould i sell\b", r"\bwhen to sell\b", r"\bexit\b", r"\bbook (?:profit|loss)\b"],
    "list_picks":       [r"\bgive me \d+\b", r"\btop \d+ stocks?\b", r"\bbest \d+ stocks?\b", r"\brecommend \d+\b", r"\b\d+ best (?:stocks?|picks?)\b", r"\bwhich \d+ stocks?\b"],
    "news_reaction":    [r"\bjust (?:announced|reported|won|got|received|published)\b", r"\bafter.*q[1-4].*results?\b", r"\bq[1-4].*results?.*\bwhat\b", r"\bbreaking.*market\b", r"\breaction to\b", r"\bwhat (?:should i do|does this mean|now)\b.*\b(?:won|lost|beat|missed|announced)\b"],
    "earnings_preview": [r"\bbefore (?:earnings|results|q[1-4])\b", r"\bpre.?(?:earnings|results?)\b", r"\bahead of (?:earnings|results?)\b", r"\bearnings (?:this|next) (?:week|month)\b"],
    "entry_timing":     [r"\bgood time to enter\b", r"\bright time to (?:buy|invest)\b", r"\bentry (?:point|level|price)\b", r"\bwhen (?:to|should i) enter\b"],
    "portfolio_review": [r"\bmy portfolio\b", r"\bconcentration risk\b", r"\basset allocation\b", r"\brebalance\b", r"\bportfolio (?:is|has|with)\b", r"\bi (?:own|hold|have) .+,"],
    "buy":              [r"\bshould i buy\b", r"\bgood time to buy\b", r"\bworth buying\b", r"\bcan i buy\b"],
    "decision":         [r"\bshould i\b", r"\bworth it\b", r"\bgood investment\b", r"\bsafe to invest\b"],
}

_HOLDING_RE = re.compile(
    r"(?:i (?:hold|own|have|bought|invested in|am holding|currently hold|am in)|"
    r"my (?:investment|portfolio|position|holding) (?:in|of)|"
    r"i already (?:have|own|hold)|"
    r"i (?:am planning to sell|want to sell))\s+([A-Za-z0-9 &.]+?)(?:\.|,|$|\?| and | should)",
    re.IGNORECASE,
)
_TARGET_RE = re.compile(
    r"(?:(?:buy|switch to|move to|invest in|purchase|rotate to|into)\s+([A-Za-z0-9 &.]+?)(?:\.|,|$|\?| instead| rather| now)|"
    r"(?:and buy|to buy|or buy)\s+([A-Za-z0-9 &.]+?)(?:\.|,|$|\?))",
    re.IGNORECASE,
)
_HORIZON_RE = re.compile(
    r"\b(\d+[-\s](?:month|year|week)s?|short.?term|medium.?term|long.?term|"
    r"1\s*month|3\s*months?|6\s*months?|1\s*year|3.5\s*years?)\b",
    re.IGNORECASE,
)
_RISK_RE = re.compile(
    r"\b(conservative|moderate|aggressive|low risk|high risk|safe)\b", re.IGNORECASE
)
_COMPARE_RE = re.compile(
    r"(?:is\s+)?([A-Za-z][A-Za-z0-9 &.]{2,30}?)\s+"
    r"(?:vs\.?|versus|better than|or)\s+"
    r"([A-Za-z][A-Za-z0-9 &.]{2,30}?)(?:\s+for|\s+in|[?.,]|$)",
    re.IGNORECASE,
)
_COMPARE_RE_3 = re.compile(
    r"([A-Za-z][A-Za-z0-9 &.]{2,30}?)\s+(?:vs\.?|versus|or)\s+"
    r"([A-Za-z][A-Za-z0-9 &.]{2,30}?)\s+(?:vs\.?|versus|or)\s+"
    r"([A-Za-z][A-Za-z0-9 &.]{2,30}?)(?:\s+for|\s+in|[?.,]|$)",
    re.IGNORECASE,
)
_BUDGET_RE = re.compile(
    r"₹\s*([\d,]+)\s*(lakh|crore|thousand|k)?|(\d+)\s*(lakh|crore|thousand)\b",
    re.IGNORECASE,
)
_SECTOR_NAMES = {
    "banking", "it", "technology", "defence", "energy", "pharma", "auto",
    "fmcg", "metals", "realty", "telecom", "power", "finance", "logistics",
    "infrastructure", "railway", "railways", "healthcare", "consumption",
    "manufacturing", "chemicals", "fertilizers", "insurance",
}
_COMMODITY_NAMES = {
    "gold", "silver", "oil", "crude", "crude oil", "brent", "copper", "zinc",
    "aluminium", "nickel", "platinum", "palladium", "natural gas",
    "nifty", "sensex", "bank nifty", "nifty 50", "nifty50",
    "bitcoin", "btc", "ethereum", "eth", "crypto", "cryptocurrency",
    "real estate", "property", "land",
    "usd", "dollar", "euro", "yen", "pound", "rupee",
    "fd", "fixed deposit", "ppf", "bonds", "debt", "nps",
    "mutual fund", "index fund", "etf",
    "sgb", "sovereign gold bond",
}
# Commodity ETF tickers for common assets — used in prompt hints
_COMMODITY_TICKERS = {
    "gold": "GOLDBEES", "silver": "SILVERETF", "nifty": "NIFTYBEES",
    "oil": "OILCOUNTRY", "crude": "OILCOUNTRY",
}
_VALUATION_TRIGGERS = re.compile(
    r"\b(?:overvalued|undervalued|p[/\-]?e|pe ratio|price[- ]to[- ]earnings?|book value|"
    r"fundamentals?|valuation|fair value|intrinsic value|expensive|cheap)\b",
    re.IGNORECASE,
)
_VIX_TRIGGER = re.compile(r"\b(?:vix|volatility index|india vix)\b", re.IGNORECASE)


def _detect_decision_intent(query: str) -> dict:
    q = query.lower()
    detected_intent = "general"
    for intent, patterns in _DECISION_INTENTS.items():
        if any(re.search(p, q) for p in patterns):
            detected_intent = intent
            break

    is_decision = detected_intent != "general"

    holding = None
    m = _HOLDING_RE.search(query)
    if m:
        holding = m.group(1).strip()

    target = None
    m2 = _TARGET_RE.search(query)
    if m2:
        target = (m2.group(1) or m2.group(2) or "").strip()

    # Compare: try 3-way first, then 2-way
    third_entity = None
    if detected_intent == "compare":
        mc3 = _COMPARE_RE_3.search(query)
        if mc3:
            holding = mc3.group(1).strip()
            target  = mc3.group(2).strip()
            third_entity = mc3.group(3).strip()
        elif not holding and not target:
            mc = _COMPARE_RE.search(query)
            if mc:
                holding = mc.group(1).strip()
                target  = mc.group(2).strip()
    elif detected_intent in ("switch", "hold", "sell", "buy", "decision") and not holding and not target:
        # Fallback: try compare regex for "X vs Y" phrasing in non-compare intents
        mc = _COMPARE_RE.search(query)
        if mc:
            holding = mc.group(1).strip()
            target  = mc.group(2).strip()

    horizon = None
    m3 = _HORIZON_RE.search(query)
    if m3:
        horizon = m3.group(1)

    risk = None
    m4 = _RISK_RE.search(query)
    if m4:
        risk = m4.group(1)

    # Budget/amount extraction
    budget = None
    mb = _BUDGET_RE.search(query)
    if mb:
        amt_str = ((mb.group(1) or mb.group(3)) or "").replace(",", "")
        unit    = ((mb.group(2) or mb.group(4)) or "").lower()
        if amt_str:
            try:
                amt = float(amt_str)
                if unit in ("lakh",):
                    budget = f"₹{amt:.0f} lakh"
                elif unit in ("crore",):
                    budget = f"₹{amt:.0f} crore"
                elif unit in ("thousand", "k"):
                    budget = f"₹{amt * 1000:.0f}"
                else:
                    budget = f"₹{amt_str}"
            except ValueError:
                pass

    # Count for list_picks
    pick_count = 3
    if detected_intent == "list_picks":
        cm = re.search(r"\b(\d+)\b", query)
        if cm:
            pick_count = min(int(cm.group(1)), 10)

    # Sector entity detection — flag when holding/target is a sector, not a company
    holding_is_sector    = bool(holding and holding.lower().strip() in _SECTOR_NAMES)
    target_is_sector     = bool(target  and target.lower().strip()  in _SECTOR_NAMES)
    # Commodity/asset class detection — Gold, Silver, Nifty, crypto, bonds, etc.
    holding_is_commodity = bool(holding and holding.lower().strip() in _COMMODITY_NAMES)
    target_is_commodity  = bool(target  and target.lower().strip()  in _COMMODITY_NAMES)

    # Portfolio extraction for multi-stock queries
    portfolio: list[str] = []
    if detected_intent == "portfolio_review":
        pm = re.search(
            r"(?:i (?:own|hold|have)|portfolio (?:is|has|includes?))[^\w]+"
            r"((?:[A-Za-z][A-Za-z0-9 &.]+(?:,\s*|\s+and\s+)){1,5}[A-Za-z][A-Za-z0-9 &.]+)",
            query, re.IGNORECASE,
        )
        if pm:
            raw = pm.group(1)
            portfolio = [p.strip() for p in re.split(r",\s*|\s+and\s+", raw) if p.strip()][:6]

    # A genuine two-asset comparison needs BOTH sides actually named by the
    # user — "should I invest in defence stocks" only ever fills `target`
    # (via the "invest in X" pattern), never `holding`. Without this check,
    # the decision-comparison prompt used to fabricate a placeholder
    # "Asset A" / RELIANCE holding and frame every single-entity question as
    # a two-way switch decision nobody asked for.
    is_comparison = bool(holding) and bool(target)

    return {
        "is_decision":       is_decision,
        "is_comparison":     is_comparison,
        "intent":            detected_intent,
        "holding":           holding,
        "target":            target,
        "third_entity":      third_entity,
        "horizon":           horizon,
        "risk":              risk,
        "budget":            budget,
        "pick_count":        pick_count,
        "holding_is_sector":    holding_is_sector,
        "target_is_sector":     target_is_sector,
        "holding_is_commodity": holding_is_commodity,
        "target_is_commodity":  target_is_commodity,
        "portfolio":            portfolio,
    }


# ── Research outlook enum (replaces Buy/Sell/Hold advisory language) ──────────
# This is a research platform, not an advisory platform — no recommendation
# language is allowed to reach the response. Enforced twice: the prompt asks
# for one of these exact 8 labels, and _normalize_outlook() below forcibly
# remaps whatever the AI actually returns, so a model ignoring instructions
# (or an older cached response) can never leak "Buy"/"Sell"/"Hold" to the UI.
_OUTLOOK_LABELS = [
    "Strongly Constructive", "Constructive", "Positive Outlook",
    "Selectively Constructive", "Neutral", "Cautious",
    "Elevated Risk", "High Uncertainty",
]
_OUTLOOK_LABELS_LOWER = {lbl.lower(): lbl for lbl in _OUTLOOK_LABELS}
_ADVISORY_LANGUAGE_MAP = {
    "strong buy": "Strongly Constructive", "buy": "Constructive", "accumulate": "Constructive",
    "outperform": "Positive Outlook", "add": "Positive Outlook",
    "hold": "Neutral", "market perform": "Neutral",
    "reduce": "Cautious", "underperform": "Cautious", "trim": "Cautious",
    "sell": "Elevated Risk", "underweight": "Elevated Risk",
    "strong sell": "High Uncertainty", "avoid": "High Uncertainty",
}


def _normalize_outlook(rating: str, direction: str, confidence: float, opportunity_score: float) -> str:
    """Coerce any rating string into one of the 8 allowed research-outlook labels."""
    r = (rating or "").strip().lower()
    if r in _OUTLOOK_LABELS_LOWER:
        return _OUTLOOK_LABELS_LOWER[r]
    for phrase, mapped in _ADVISORY_LANGUAGE_MAP.items():
        if phrase in r:
            return mapped
    # No usable rating string at all — derive purely from the numeric signals.
    d = (direction or "neutral").lower()
    conf = confidence or 0
    opp = opportunity_score or 0
    if d == "bullish":
        if opp >= 85 and conf >= 80:
            return "Strongly Constructive"
        if opp >= 70:
            return "Constructive"
        return "Positive Outlook"
    if d == "bearish":
        if opp <= 30 or conf < 40:
            return "High Uncertainty"
        return "Elevated Risk"
    if conf < 50:
        return "Cautious"
    return "Selectively Constructive" if opp >= 55 else "Neutral"


def _suitable_for(horizon: str, risk_level: str) -> str:
    h = (horizon or "").lower()
    r = (risk_level or "").lower()
    long_term = any(k in h for k in ("12", "18", "24", "2 year", "3 year", "long"))
    short_term = any(k in h for k in ("day", "week", "1 month", "intraday", "short"))
    if "high" in r or "aggressive" in r:
        return "Active Traders" if short_term else "Growth-Oriented Investors"
    if short_term:
        return "Tactical / Short-Term Investors"
    if long_term:
        return "Long-term Investors"
    return "Balanced / Medium-Term Investors"


def _sector_status(positive: bool, score: float) -> str:
    s = score or 0
    if positive:
        if s >= 85:
            return "Structural Tailwind"
        if s >= 65:
            return "Beneficiary"
        return "Indirect Benefit"
    if s <= 35:
        return "Structural Headwind"
    return "Headwind"


def _sector_time_horizon(status: str) -> str:
    return {
        "Structural Tailwind": "3-5 Years", "Structural Headwind": "3-5 Years",
        "Beneficiary": "2-3 Years", "Headwind": "2-3 Years",
        "Indirect Benefit": "1-2 Years",
    }.get(status, "1-2 Years")


def _classify_ripple_position(companies: list[dict]) -> None:
    """
    Mutates `companies` in place, adding `ripple_position`. Deterministic,
    based on sort rank within each impact_type group — not left entirely to
    the AI, so labeling is consistent regardless of prompt compliance.
    """
    beneficiaries = [c for c in companies if (c.get("impact_type") or "").lower() == "beneficiary"]
    at_risk       = [c for c in companies if (c.get("impact_type") or "").lower() == "at_risk"]
    for i, c in enumerate(beneficiaries):
        c["ripple_position"] = "Primary Beneficiary" if i < 2 else "Secondary Beneficiary"
    for i, c in enumerate(at_risk):
        c["ripple_position"] = "Primary Pressure" if i < 2 else "Secondary Pressure"
    for c in companies:
        c.setdefault("ripple_position", "Indirect Exposure")


# Canonical vocabulary used by historical_memory_service's seed table — live
# events only ever carry event_type="macro", which never matches this, so
# historical comparison must be inferred from the query text itself instead.
_HIST_CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "Monetary Policy":       ("rbi", "repo rate", "interest rate", "rate cut", "rate hike", "monetary policy"),
    "Union Budget":          ("union budget", "budget 20", "capex outlay", "fiscal budget", "finance bill", "budget capex", "the budget", "latest budget", "budget announcement", "budget spending"),
    "Infrastructure Policy": ("pli scheme", "production-linked incentive", "infrastructure policy", "production linked"),
    "Geopolitical":          ("war", "geopolitical", "sanctions", "conflict", "border tension", "pakistan", "ukraine", "military"),
    "Global Market Shock":   ("global market", "recession", "financial crisis", "bankruptcy", "fed taper", "contagion", "circuit breaker"),
    "Corporate Crisis":      ("fraud", "default", "scam", "corporate crisis", "insolvency", "moratorium"),
    "Commodity Shock":       ("crude", "oil price", "commodity shock", "gold price", "wti"),
    "Election":              ("election", "lok sabha", "poll result", "government formation"),
    "Regulatory":            ("gst", "regulation", "sebi", "compliance", "regulatory", "demonetization", "demonetisation"),
    "Trade Policy":          ("trade deal", "tariff", "import duty", "export ban"),
}
_HIST_SECTOR_NAMES = [
    "PSU Banks", "Housing Finance", "Capital Markets", "Capital Goods", "Specialty Chemicals",
    "Consumer Durables", "Real Estate", "Oil & Gas", "Banking", "NBFC", "Defence", "Infrastructure",
    "Metal", "Cement", "Auto", "Retail", "FMCG", "Aviation", "Railway", "PSU", "Pharma",
    "Electronics", "Textile", "Telecom", "Media", "Ports", "Utilities", "Jewellery", "Hotels",
    "Fertilizers", "Paints", "Tyres", "Financials", "Consumer", "Tourism", "Logistics", "Finance",
]


def _cap_words(text: str, limit: int = 120) -> str:
    """Hard safety net behind the prompt's own word-limit instruction — the
    model doesn't always obey it, and an Executive Summary is worthless if
    it silently balloons into a wall of text."""
    words = (text or "").split()
    if len(words) <= limit:
        return text or ""
    return " ".join(words[:limit]).rstrip(",.;:") + "…"


def _key_difference(hist_query: dict, h: dict) -> str:
    """
    Deterministic, factual diff between the current query's inferred context
    and a matched historical event — never AI-invented, so it can't overstate
    how similar the two situations actually are.
    """
    parts: list[str] = []
    q_cat, h_cat = hist_query.get("category"), h.get("category")
    if q_cat and h_cat:
        parts.append("same category" if q_cat == h_cat else f"category differs ({h_cat} vs current {q_cat})")

    q_sec, h_sec = set(hist_query.get("sectors") or []), set(h.get("sectors") or [])
    if q_sec and h_sec:
        overlap, only_hist = q_sec & h_sec, h_sec - q_sec
        if overlap and only_hist:
            parts.append(f"shares {', '.join(sorted(overlap))} but this event also touched {', '.join(sorted(only_hist))}")
        elif overlap:
            parts.append(f"same sector focus ({', '.join(sorted(overlap))})")
        else:
            parts.append(f"different sectors ({', '.join(sorted(h_sec))} vs current {', '.join(sorted(q_sec))})")

    if not parts:
        return "Limited structured overlap — treat as a loose historical reference only."
    return ("; ".join(parts) + ".")[0].upper() + ("; ".join(parts) + ".")[1:]


def _infer_historical_category(query_lower: str) -> str | None:
    for category, keywords in _HIST_CATEGORY_KEYWORDS.items():
        if any(k in query_lower for k in keywords):
            return category
    return None


def _infer_historical_sectors(query_lower: str) -> list[str]:
    return [s for s in _HIST_SECTOR_NAMES if s.lower() in query_lower]


def _build_market_horizons(ai: dict, confidence: float, sentiment: str) -> list[dict]:
    """
    Deterministic Immediate/Next Quarter/Long Term confidence bars, replacing
    the old meaningless price-line chart. Confidence naturally decays further
    out — near-term reaction is more predictable than a 6-12 month outcome —
    and each bar reuses the AI's own impact narrative rather than fabricating
    a new one, so it stays grounded in what was actually said.
    """
    direction = "positive" if sentiment == "positive" else ("negative" if sentiment == "negative" else "neutral")
    base = max(0.0, min(100.0, confidence or 0))
    return [
        {
            "horizon": "Immediate", "window": "1-2 weeks",
            "confidence": round(min(95, base + 10)), "direction": direction,
            "description": ai.get("immediate_impact") or "Short-term price action likely to reflect the news within days.",
        },
        {
            "horizon": "Next Quarter", "window": "1-3 months",
            "confidence": round(base), "direction": direction,
            "description": ai.get("medium_term") or "Medium-term fundamentals will determine whether the initial move sustains.",
        },
        {
            "horizon": "Long Term", "window": "6-12 months",
            "confidence": round(max(15, base - 20)), "direction": direction,
            "description": ai.get("long_term") or "Longer-term outcome depends on execution and macro conditions beyond current visibility.",
        },
    ]


def _build_reasoning_methods(
    events: list, similar: list, extra_context_lines: list[str],
    mie_state: dict, ripple_chain: list, companies: list,
    news: list | None = None, policies: list | None = None,
) -> list[dict]:
    """
    Deterministic — reports which data sources ACTUALLY contributed to this
    specific answer, not a hardcoded marketing list. `used: False` entries
    stay visible so the transparency panel is honest about gaps, not just a
    checklist of things that sound good.
    """
    valuation_used = any("P/E" in l or "P/B" in l for l in extra_context_lines)
    return [
        {"label": "News",                  "used": bool(news) or bool(events)},
        {"label": "Policies",              "used": bool(policies)},
        {"label": "Historical Events",     "used": bool(similar)},
        {"label": "Financial Statements",  "used": bool(companies)},
        {"label": "Valuation",             "used": valuation_used},
        {"label": "Intelligence Graph",    "used": bool(ripple_chain)},
        {"label": "Ripple Engine",         "used": bool(ripple_chain)},
        {"label": "Company Relationships", "used": len(companies) >= 2},
    ]


def _confidence_caveats(conf_result: Any, events: list, similar: list, source_count: int) -> list[str]:
    """What would raise or lower trust in this specific answer — derived from
    the same signals `confidence_service` already scored, not a separate
    guess."""
    caveats: list[str] = []
    if not events:
        caveats.append("No matching events found in the database for this query")
    if not similar:
        caveats.append("No closely matching historical precedent found")
    if source_count < 3:
        caveats.append("Limited data coverage — fewer than 3 corroborating sources")
    if conf_result is not None:
        breakdown = conf_result.breakdown or {}
        if breakdown.get("market_confirmation", 0) < 5:
            caveats.append("Live market signals not yet confirming this thesis")
        if breakdown.get("historical", 0) < 5:
            caveats.append("Weak historical match for this scenario")
    return caveats


# ── AI prompt ─────────────────────────────────────────────────────────────────
_SYSTEM = (
    "You are a senior Indian equity market analyst at an institutional fund. "
    "Generate structured market intelligence for professional investors. "
    "Respond with valid JSON only. No markdown fences. No commentary."
)


def _build_decision_prompt(
    query: str,
    intent_data: dict,
    events: list,
    news: list,
    policies: list,
    extra_context: str = "",
) -> str:
    holding = intent_data.get("holding") or "Asset A"
    target  = intent_data.get("target")  or "Asset B"
    horizon = intent_data.get("horizon") or "medium-term"
    risk    = intent_data.get("risk")    or "moderate"
    intent  = intent_data.get("intent",  "decision")

    holding_is_commodity = intent_data.get("holding_is_commodity", False)
    target_is_commodity  = intent_data.get("target_is_commodity",  False)
    holding_is_sector    = intent_data.get("holding_is_sector",    False)
    target_is_sector     = intent_data.get("target_is_sector",     False)

    # Determine entity label and symbol instructions per entity type
    def entity_label(name: str, is_commodity: bool, is_sector: bool) -> str:
        if is_commodity: return f"{name} (commodity/asset class)"
        if is_sector:    return f"{name} (market sector)"
        return name

    def symbol_hint(name: str, is_commodity: bool, is_sector: bool) -> str:
        if is_commodity:
            tick = _COMMODITY_TICKERS.get(name.lower(), "null")
            return f'Set "symbol" to "{tick}" (ETF proxy) or null. Do NOT use equity tickers.'
        if is_sector:
            return f'Set "symbol" to null. This is a sector, not a single stock.'
        return f'Set "symbol" to the real NSE ticker (e.g. TATAMOTORS, RELIANCE, HDFCBANK).'

    a_label = entity_label(holding, holding_is_commodity, holding_is_sector)
    b_label = entity_label(target,  target_is_commodity,  target_is_sector)

    evs = "\n".join(f"- {e['title']}" for e in events[:4]) or "None"
    nws = "\n".join(f"- {a['headline']}" for a in news[:4]) or "None"

    # Comparison dimensions differ for commodity vs equity queries
    if holding_is_commodity or target_is_commodity:
        comp_dims = [
            "Inflation Hedge", "Liquidity", "Volatility", "Store of Value",
            "Growth Potential", "Correlation to Equity"
        ]
    elif holding_is_sector or target_is_sector:
        comp_dims = [
            "Sector Outlook", "Policy Tailwinds", "Valuation", "Earnings Growth",
            "Risk Profile", "FII Interest"
        ]
    else:
        comp_dims = [
            "Business Model", "Sector Outlook", "Growth Drivers",
            "Risk Profile", "Market Position", "Valuation"
        ]
    comp_rows = "\n".join(
        f'      {{"dimension": "{d}", "holding": "", "target": "", "advantage": "neutral"}},'
        for d in comp_dims
    ).rstrip(",")

    ctx_block = f"\nCONTEXT:\n{extra_context}\n" if extra_context else ""
    return f"""You are a senior Indian market analyst. Analyse this investor query and return a single JSON object.
{ctx_block}
QUERY: "{query}"
ENTITY A (holding/first): {a_label}
ENTITY B (target/second): {b_label}
HORIZON: {horizon} | RISK TOLERANCE: {risk}
MARKET NEWS: {nws}
RELATED EVENTS: {evs}

INSTRUCTIONS:
- Fill every string field with real, specific analysis about {holding} and {target}.
- All strings must be your original analytical content — never copy field descriptions.
- This is a RESEARCH platform, not an advisory one. Never say Buy/Sell/Hold/Strong Buy/Strong Sell/Accumulate/Reduce anywhere. Explain trade-offs only. No direct financial advice.
- "investment_verdict.rating" MUST be exactly one of these 8 values, nothing else: {", ".join(f'"{l}"' for l in _OUTLOOK_LABELS)}.
- Entity A symbol hint: {symbol_hint(holding, holding_is_commodity, holding_is_sector)}
- Entity B symbol hint: {symbol_hint(target, target_is_commodity, target_is_sector)}
- Use the entity name exactly as given in "entity" field (e.g. "{holding}", "{target}").
- "advantage" in comparison rows must be "holding", "target", or "neutral".
- "near_term_outlook" must be "positive", "cautious", "neutral", or "negative".
- "sentiment" must be "bullish", "bearish", or "neutral".
- "key_drivers[].icon" must be ONE lowercase keyword from: procurement, policy, manufacturing, export, valuation, risk, demand, technology, capex, regulation, earnings, supply-chain, currency, commodity, credit.
- Return valid JSON only. No markdown. No commentary outside the JSON.

JSON to fill and return:
{{
  "summary": "",
  "bottom_line": "MAX 120 WORDS. ONE paragraph answering ONLY this exact question directly — name the specific trade-off between {holding} and {target}, who comes out ahead on the metric that actually matters here, and the one factor most likely to change that. No generic filler.",
  "what_happened": "",
  "why_it_happened": "",
  "immediate_impact": "",
  "medium_term": "",
  "long_term": "",
  "what_priced_in": "1-2 sentences: how much of this trade-off is already reflected in current prices/positioning for {holding} and {target}?",
  "risks": ["", "", ""],
  "opportunities": ["", "", ""],
  "key_drivers": [
    {{"icon": "valuation", "title": "2-4 word driver name", "explanation": "1 sentence mechanism behind this trade-off", "confidence": 85}},
    {{"icon": "risk", "title": "2-4 word driver name", "explanation": "1 sentence mechanism", "confidence": 76}}
  ],
  "confidence": 70,
  "confidence_self_rating": 7,
  "sentiment": "neutral",
  "companies": [
    {{"symbol": "", "name": "{holding}", "impact_type": "neutral", "impact_score": 70, "confidence": 68, "reason": ""}},
    {{"symbol": "", "name": "{target}",  "impact_type": "neutral", "impact_score": 70, "confidence": 68, "reason": ""}}
  ],
  "sectors": [
    {{"name": "", "score": 65, "confidence": 62, "outlook": "Moderate", "positive": true, "explanation": "1 sentence on why this sector is exposed and to what degree"}},
    {{"name": "", "score": 70, "confidence": 65, "outlook": "Moderate", "positive": true, "explanation": "1 sentence"}}
  ],
  "investment_verdict": {{
    "rating": "Selectively Constructive",
    "direction": "neutral",
    "confidence": 68,
    "horizon": "{horizon}",
    "top_picks": [],
    "risks": ["", ""],
    "catalysts": ["", ""],
    "opportunity_score": 65
  }},
  "follow_up_questions": [
    "What is your investment horizon for this decision?",
    "What is your risk tolerance - conservative, moderate, or aggressive?",
    "Are you seeking capital appreciation or dividend income?",
    "Have you considered the tax implications of switching?"
  ],
  "timeline": [
    {{"date": "Near-term", "title": "", "description": ""}},
    {{"date": "3-6 months", "title": "", "description": ""}},
    {{"date": "12 months", "title": "", "description": ""}}
  ],
  "decision_intelligence": {{
    "intent": "{intent}",
    "context_complete": true,
    "missing_context": [],
    "decision_summary": "",
    "holding_analysis": {{
      "entity": "{holding}",
      "symbol": "",
      "sector": "",
      "thesis": "",
      "strengths": ["", "", ""],
      "risks": ["", "", ""],
      "catalysts": ["", ""],
      "near_term_outlook": "neutral",
      "confidence": 65
    }},
    "target_analysis": {{
      "entity": "{target}",
      "symbol": "",
      "sector": "",
      "thesis": "",
      "strengths": ["", "", ""],
      "risks": ["", "", ""],
      "catalysts": ["", ""],
      "near_term_outlook": "neutral",
      "confidence": 65
    }},
    "comparison": [
{comp_rows}
    ],
    "tradeoff": {{
      "reasons_to_switch": ["", "", ""],
      "reasons_to_hold":   ["", "", ""],
      "risks_of_switching": ["", ""],
      "risks_of_holding":   ["", ""],
      "when_to_wait": ""
    }},
    "decision_framework": {{
      "supports_switch": ["", "", ""],
      "argues_against":  ["", ""],
      "key_unknowns":    ["", ""],
      "ai_stance": ""
    }}
  }}
}}"""


def _build_prompt(
    query: str,
    events: list,
    news: list,
    policies: list,
    intent_data: dict | None = None,
    extra_context: str = "",
) -> str:
    evs  = "\n".join(f"- [{e['category']}] {e['title']} (score:{e['impact_score']:.0f})" for e in events[:5]) or "None"
    nws  = "\n".join(f"- {a['headline']}" for a in news[:5]) or "None"
    pols = "\n".join(f"- {p['title']} [{p['ministry']}]" for p in policies[:3]) or "None"

    return f"""Query: "{query}"

DB Events: {evs}
News: {nws}
Policies: {pols}

Return ONLY this JSON (no fences, no extra keys):
{{
  "summary": "2-3 sentence executive summary specific to the query",
  "bottom_line": "MAX 120 WORDS. ONE paragraph that answers ONLY this exact question, directly and specifically. No generic filler, no restating the question, no boilerplate market commentary. Name the specific mechanism (e.g. what actually drives the outcome), who benefits most and why, and the one factor that most determines whether that plays out.",
  "what_happened": "1 factual sentence about what actually happened",
  "why_it_happened": "1 contextual sentence explaining the cause",
  "immediate_impact": "1 sentence on near-term market effect",
  "medium_term": "1 sentence on 3-12 month outlook",
  "long_term": "1 sentence on structural implications",
  "what_priced_in": "1-2 sentences: has the market already priced this in? Reference recent sector/stock performance if you have context for it, and state plainly whether future returns now depend more on new catalysts or on execution of what's already known.",
  "risks": ["specific risk 1", "specific risk 2", "specific risk 3"],
  "opportunities": ["specific opportunity 1", "specific opportunity 2", "specific opportunity 3"],
  "key_drivers": [
    {{"icon": "procurement", "title": "2-4 word driver name", "explanation": "1 sentence on the actual mechanism, not a restatement of the title", "confidence": 92}},
    {{"icon": "policy", "title": "2-4 word driver name", "explanation": "1 sentence mechanism", "confidence": 87}},
    {{"icon": "export", "title": "2-4 word driver name", "explanation": "1 sentence mechanism", "confidence": 74}}
  ],
  "confidence": 78,
  "confidence_self_rating": 7,
  "sentiment": "bullish",
  "companies": [
    {{"symbol": "SYMBOL1", "name": "Full Company Name", "impact_type": "beneficiary", "impact_score": 90, "confidence": 85, "reason": "specific 1-line reason tied to the query — this is shown to the user as literally why the company matters here"}},
    {{"symbol": "SYMBOL2", "name": "Full Company Name", "impact_type": "beneficiary", "impact_score": 85, "confidence": 80, "reason": "specific 1-line reason"}},
    {{"symbol": "SYMBOL3", "name": "Full Company Name", "impact_type": "beneficiary", "impact_score": 78, "confidence": 74, "reason": "specific 1-line reason"}},
    {{"symbol": "SYMBOL4", "name": "Full Company Name", "impact_type": "neutral",     "impact_score": 65, "confidence": 60, "reason": "specific 1-line reason"}},
    {{"symbol": "SYMBOL5", "name": "Full Company Name", "impact_type": "at_risk",     "impact_score": 45, "confidence": 55, "reason": "specific 1-line reason"}}
  ],
  "sectors": [
    {{"name": "Most Relevant Sector", "score": 90, "confidence": 85, "outlook": "Strong Growth", "positive": true, "explanation": "1 sentence on the mechanism connecting this sector to the query"}},
    {{"name": "Second Sector",        "score": 82, "confidence": 78, "outlook": "Positive",      "positive": true, "explanation": "1 sentence"}},
    {{"name": "Third Sector",         "score": 70, "confidence": 65, "outlook": "Moderate",      "positive": true, "explanation": "1 sentence"}},
    {{"name": "Fourth Sector",        "score": 60, "confidence": 58, "outlook": "Neutral",       "positive": true, "explanation": "1 sentence"}},
    {{"name": "Affected Sector",      "score": 45, "confidence": 50, "outlook": "Cautious",      "positive": false, "explanation": "1 sentence"}}
  ],
  "investment_verdict": {{
    "rating": "Constructive",
    "direction": "bullish",
    "confidence": 78,
    "horizon": "12-18 months",
    "top_picks": ["SYMBOL1", "SYMBOL2", "SYMBOL3"],
    "risks": ["Specific risk 1", "Specific risk 2", "Specific risk 3"],
    "catalysts": ["Specific catalyst 1", "Specific catalyst 2", "Specific catalyst 3"],
    "opportunity_score": 85
  }},
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

CRITICAL RULES:
- "investment_verdict.rating" MUST be exactly one of these 8 values, nothing else: {", ".join(f'"{l}"' for l in _OUTLOOK_LABELS)}. This is a RESEARCH platform, not an advisory one — never say Buy, Sell, Hold, Strong Buy, Strong Sell, Accumulate, or Reduce anywhere in any field.
- "companies" must ONLY include companies with a direct, specific, mechanistic connection to this exact query. Do not pad the list with generic large-caps (e.g. HUL, Reliance, Tata Motors) unless the query is genuinely and specifically about them. Every entry must be a listed, tradeable equity with a real NSE symbol — never a government body, ministry, PSU research arm, or other unlisted entity (e.g. DRDO is not investable; if relevant, name the listed contractors it drives orders to instead).
- "key_drivers[].icon" must be ONE lowercase keyword from: procurement, policy, manufacturing, export, valuation, risk, demand, technology, capex, regulation, earnings, supply-chain, currency, commodity, credit.
- The "insights" titles must be SPECIFIC to the query "{query}" — choose angles that make sense for this exact topic. Use real NSE symbols, actual rupee amounts, and genuine Indian market context throughout.{_intent_overlay(intent_data, extra_context)}"""


def _intent_overlay(intent_data: dict | None, extra_context: str = "") -> str:
    """Return an intent-specific instruction block appended to the main prompt."""
    if not intent_data:
        return f"\n\nADDITIONAL CONTEXT:\n{extra_context}" if extra_context else ""

    intent     = intent_data.get("intent", "general")
    budget     = intent_data.get("budget") or ""
    pick_count = intent_data.get("pick_count") or 3
    portfolio  = intent_data.get("portfolio") or []
    horizon    = intent_data.get("horizon") or "medium-term"
    budget_note = f"\n- User has {budget} to invest — calibrate sizing accordingly." if budget else ""
    portfolio_note = f"\n- Portfolio holdings: {', '.join(portfolio)}" if portfolio else ""

    overlays: dict[str, str] = {
        "list_picks": f"""

INTENT: LIST PICKS — User wants a ranked stock list, not an essay.
- Return exactly {pick_count} companies in "companies" array, ranked by conviction (highest first).
- "investment_verdict.rating" must be "Top {pick_count} Picks Identified".
- "investment_verdict.top_picks" must contain the top 3 NSE symbols.
- Each company "reason" must be a specific 1-sentence thesis (not generic).
- "follow_up_questions" must address: position sizing, entry triggers, stop-loss, time horizon.{budget_note}""",

        "news_reaction": f"""

INTENT: NEWS REACTION — A recent event just happened; user wants immediate guidance.
- "summary" must be exactly what this news means for investors RIGHT NOW (2 sentences).
- "immediate_impact" must name specific sectors/stocks and expected directional move.
- "medium_term" must describe the thesis window (days/weeks, not months).
- "follow_up_questions" must include: price level where thesis breaks, add/reduce decision, key upcoming catalyst.
- Prioritize recency — today's news beats older context.{budget_note}""",

        "earnings_preview": f"""

INTENT: EARNINGS PREVIEW — User is positioning ahead of results.
- "summary" must cover: consensus expectations, key metrics to watch, beat vs miss thresholds.
- "risks" must list miss scenarios with expected stock reactions (e.g. "-5% if revenue misses by 2%").
- "opportunities" must list beat scenarios with upside estimates.
- "key_drivers" should reference the company's recent earnings reaction pattern where relevant.
- "follow_up_questions" must address: historical move range, key metric focus, risk/reward ratio.
- "timeline" must show: results date, pre-result window, post-result action.{budget_note}""",

        "entry_timing": f"""

INTENT: ENTRY TIMING — User wants to know if now is a good entry point.
- "summary" must assess: current price vs historical range, risk/reward at today's level.
- "immediate_impact" must state the current technical setup (near 52W high/low, recent trend).
- "opportunities" must list: entry triggers and what confirms the setup.
- "risks" must list: why this level could be a trap (overhead resistance, near-term catalysts).
- "follow_up_questions" must include: stop-loss level, scale-in strategy, what invalidates the thesis.
- HORIZON: {horizon}.{budget_note}""",

        "portfolio_review": f"""

INTENT: PORTFOLIO REVIEW — User wants portfolio-level analysis.
- "summary" must cover: sector concentration, single-factor exposure, missing diversifiers.
- "sectors" must list all sectors covered AND key missing ones (label missing ones "Underweight").
- "risks" must include portfolio-level risks: concentration, correlation, liquidity.
- "opportunities" must include: diversification adds, rebalancing actions.
- "follow_up_questions" must address: rebalancing triggers, missing asset classes, hedging options, tax implications.{portfolio_note}{budget_note}""",

        "sell": f"""

INTENT: SELL / EXIT ANALYSIS — User is evaluating whether to exit a position.
- "summary" must weigh: exit thesis strength vs opportunity cost of remaining.
- "investment_verdict.direction" should be "bearish" if exit is recommended, "neutral" otherwise.
- "risks" must include: what happens if the bearish thesis is wrong (false exit risk).
- "opportunities" must include: where to redeploy capital after exiting.
- "follow_up_questions" must include: tax implications, redeployment options, what would reverse the sell thesis.{budget_note}""",
    }

    overlay = overlays.get(intent, "")
    ctx_block = f"\n\nADDITIONAL CONTEXT:\n{extra_context}" if extra_context else ""
    return overlay + ctx_block


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


# ── Valuation data fetch ──────────────────────────────────────────────────────
def _fetch_valuation_sync(symbols: list[str]) -> dict:
    """Fetch P/E, P/B, 52W range from yfinance for valuation-sensitive queries."""
    import yfinance as yf
    result: dict = {}
    for sym in symbols[:3]:
        try:
            info = yf.Ticker(f"{sym}.NS").info or {}
            pe  = info.get("trailingPE") or info.get("forwardPE")
            pb  = info.get("priceToBook")
            hi  = info.get("fiftyTwoWeekHigh")
            lo  = info.get("fiftyTwoWeekLow")
            result[sym] = {
                k: v for k, v in {
                    "pe": round(float(pe), 1) if pe else None,
                    "pb": round(float(pb), 2) if pb else None,
                    "52w_high": round(float(hi), 1) if hi else None,
                    "52w_low":  round(float(lo), 1) if lo else None,
                }.items() if v is not None
            }
        except Exception:
            pass
    return result


def _fetch_vix_sync() -> float | None:
    """Fetch current India VIX level."""
    import yfinance as yf
    try:
        hist = yf.download("^INDIAVIX", period="1d", interval="1d", progress=False, auto_adjust=True, timeout=10)
        if not hist.empty:
            close = hist["Close"].iloc[-1]
            v = float(close.iloc[0] if hasattr(close, "iloc") else close)
            return round(v, 2)
    except Exception:
        pass
    return None


# ── Market chart ──────────────────────────────────────────────────────────────
def _fetch_chart_sync(tickers: list) -> dict:
    """Fetch 1D intraday chart. Uses company tickers when provided, else indices."""
    import yfinance as yf
    import math

    def _series(ticker: str):
        try:
            hist = yf.download(ticker, period="1d", interval="60m",
                               progress=False, auto_adjust=True, timeout=10)
            if hist.empty:
                return [], []
            labels, vals = [], []
            for idx, row in hist.iterrows():
                try:
                    close = row["Close"]
                    v = float(close.iloc[0] if hasattr(close, "iloc") else close)
                    if math.isnan(v) or math.isinf(v):
                        continue
                    labels.append(idx.strftime("%H:%M"))
                    vals.append(v)
                except Exception:
                    continue
            return labels, vals
        except Exception:
            return [], []

    def _norm(vals: list) -> list:
        if not vals:
            return []
        base = vals[0] or 1
        return [round((v / base - 1) * 100, 3) for v in vals]

    # Company-specific chart when companies were identified in the query
    if tickers:
        series, labels = [], []
        for name, ticker, color in tickers[:4]:
            lbls, vals = _series(ticker)
            if vals:
                if len(lbls) > len(labels):
                    labels = lbls
                series.append({"name": name, "data": _norm(vals), "color": color})
        if series:
            return {"labels": labels, "series": series}

    # Fallback: generic market indices
    n_l, n_v = _series("^NSEI")
    _, b_v   = _series("^NSEBANK")
    _, it_v  = _series("^CNXIT")
    return {
        "labels": n_l,
        "series": [
            {"name": "Nifty 50",   "data": _norm(n_v),  "color": "#818cf8"},
            {"name": "Bank Nifty", "data": _norm(b_v),  "color": "#34d399"},
            {"name": "Nifty IT",   "data": _norm(it_v), "color": "#fb923c"},
        ],
    }


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


# ── Ripple chain (real graph traversal — MarketRipple's differentiator) ───────
_FALL_WORDS = re.compile(r"\b(falls?|falling|drops?|declin\w*|cuts?|lower|down|crash\w*|slump\w*)\b", re.IGNORECASE)


async def _build_ripple_chain(query: str) -> list[dict]:
    """
    Resolves the query's primary entity to a real intelligence-graph node and
    returns a branching, depth-leveled causal structure — every node at every
    level is a genuine weighted-edge traversal result from
    `intelligence_graph_service.ripple_from_node` (first-order, second-order,
    third-order effects), never a single cherry-picked linear path and never
    an invented node. Returns [] when the query's entity isn't a graph node
    yet (graceful — not every query has one).

    Shape: [{"depth": 0, "nodes": [{id,label,type,direction,weight,parent_id}]}, ...]
    """
    try:
        from app.ai_pipeline.retrieval.entity_resolver import resolve_entities
        from app.services.intelligence_graph_service import ripple_from_node

        entities = [e for e in await resolve_entities(query, limit=5) if e.get("in_graph")]
        if not entities:
            return []
        change = "fall" if _FALL_WORDS.search(query) else "rise"

        # The highest-scored entity isn't always useful as a ripple source —
        # e.g. "Defence" (sector) can outrank "Union Budget Defence Boost"
        # (policy) on text-match score alone, yet Defence is a sink node
        # with no outgoing edges. Try candidates in score order and use the
        # first one that actually produces a real traversal.
        source, impacts = None, []
        for candidate in entities:
            result = await ripple_from_node(candidate["id"], change=change, max_depth=4)
            candidate_impacts = result.get("impacts", [])
            if candidate_impacts:
                source, impacts = candidate, candidate_impacts
                break
        if not impacts:
            return []

        # ripple_from_node's BFS can append the same node more than once
        # (each time a higher-weight path to it is found via a different
        # parent) without removing the earlier, weaker entry — collapse to
        # one entry per node, keeping its strongest path, before grouping by
        # depth. Without this a node could land in the level-nodes list
        # twice, producing duplicate React keys on render.
        best_by_node: dict[str, dict] = {}
        for impact in impacts:
            nid = (impact.get("node") or {}).get("id")
            if not nid:
                continue
            prev = best_by_node.get(nid)
            if prev is None or float(impact.get("accumulated_weight", 0) or 0) > float(prev.get("accumulated_weight", 0) or 0):
                best_by_node[nid] = impact

        by_depth: dict[int, list[dict]] = {}
        for impact in best_by_node.values():
            node = impact.get("node", {}) or {}
            depth = impact.get("depth", 1)
            path = impact.get("path", [])
            parent_id = path[-1].get("from") if path else source["id"]
            by_depth.setdefault(depth, []).append({
                "id": node.get("id"), "label": node.get("label"), "type": node.get("node_type"),
                "direction": impact.get("impact_direction", "uncertain"),
                "weight": round(float(impact.get("accumulated_weight", 0) or 0), 2),
                "parent_id": parent_id,
            })

        levels: list[dict] = [{
            "depth": 0,
            "nodes": [{
                "id": source["id"], "label": source["label"], "type": source["node_type"],
                "direction": "positive" if change == "rise" else "negative", "weight": 1.0, "parent_id": None,
            }],
        }]
        for depth in sorted(by_depth.keys())[:4]:
            # Cap branch width per level so the diagram stays readable —
            # strongest real edges win, nothing here is invented.
            nodes = sorted(by_depth[depth], key=lambda n: n["weight"], reverse=True)[:5]
            levels.append({"depth": depth, "nodes": nodes})
        return levels
    except Exception as exc:
        log.warning("ai_search.ripple_chain_failed", error=str(exc)[:150])
        return []


# ── Main pipeline ─────────────────────────────────────────────────────────────
async def run_ai_search(query: str, db: AsyncSession) -> dict:
    """Full AI search pipeline. Returns complete research report dict."""
    ck = _ck(query)

    # Detect intent first — needed to compute the right cache TTL
    intent_data = _detect_decision_intent(query)
    intent      = intent_data.get("intent", "general")
    ttl         = 300 if intent == "news_reaction" else _TTL

    cached = _cget(ck, ttl=ttl)
    if cached:
        log.info("ai_search.cache_hit", query=query[:50])
        return cached

    log.info("ai_search.start", query=query[:50])
    entities = _extract_entities(query)
    loop     = asyncio.get_running_loop()

    log.info("ai_search.intent", intent=intent, is_decision=intent_data["is_decision"])

    # Parallel: DB search (chart is built after enrichment so it uses the right companies)
    events, news, policies = await asyncio.gather(
        _search_events(db, query),
        _search_news(db, query),
        _search_policies(db, query),
        return_exceptions=True,
    )
    if isinstance(events,   Exception): events   = []
    if isinstance(news,     Exception): news     = []
    if isinstance(policies, Exception): policies = []

    # Optional: fetch valuation data for valuation-focused queries
    extra_context_lines: list[str] = []
    if _VALUATION_TRIGGERS.search(query):
        co_syms = [c.upper() for c in entities.get("companies", [])[:2]]
        if co_syms:
            try:
                val = await loop.run_in_executor(None, _fetch_valuation_sync, co_syms)
                for sym, v in val.items():
                    parts = []
                    if v.get("pe"):   parts.append(f"P/E {v['pe']}")
                    if v.get("pb"):   parts.append(f"P/B {v['pb']}")
                    if v.get("52w_high") and v.get("52w_low"):
                        parts.append(f"52W {v['52w_low']}-{v['52w_high']}")
                    if parts:
                        extra_context_lines.append(f"{sym}: {', '.join(parts)}")
            except Exception:
                pass

    # Fetch India VIX — always (used for confidence scoring; injected into context for VIX queries)
    _vix_level: float | None = None
    try:
        _vix_level = await loop.run_in_executor(None, _fetch_vix_sync)
        if _vix_level and _VIX_TRIGGER.search(query):
            extra_context_lines.append(f"India VIX current level: {_vix_level}")
    except Exception:
        pass

    extra_context = "\n".join(extra_context_lines)
    mie_state:  dict = {}  # captured for confidence signals
    similar:    list = []  # captured for confidence signals
    hist_query: dict = {}  # captured for the historical "key difference" note

    # Inject intelligence from the MIE — single source of truth for all AI context
    try:
        from app.services.intelligence.engine import get_intelligence_state
        mie = await get_intelligence_state()
        mie_state = mie  # capture for confidence signals

        intel_lines: list[str] = []

        # Market mood and direction from signals
        signals = mie.get("signals", {})
        if signals.get("mood") and signals.get("direction"):
            intel_lines.append(
                f"[MARKET MOOD] {signals['mood']} · {signals['direction'].upper()} · "
                f"Risk: {signals.get('risk_level', 'MODERATE')} · "
                f"AI confidence: {signals.get('confidence', 0)}%"
            )

        # Top theme
        if signals.get("top_theme"):
            intel_lines.append(f"[TOP THEME] {signals['top_theme']} (score {signals.get('top_theme_score', 0):.0f})")

        # High-urgency events (≥ 5) from MIE top_events (already ranked, last 8h)
        top_evts = [e for e in mie.get("top_events", []) if e.get("urgency", 0) >= 5][:6]
        for e in top_evts:
            intel_lines.append(
                f"[LIVE URGENCY {e['urgency']}/10] {e.get('one_liner') or e.get('headline', '')[:120]}"
            )

        if intel_lines:
            mie_block = "LIVE MARKET INTELLIGENCE (MIE):\n" + "\n".join(intel_lines)
            extra_context = (extra_context + "\n\n" + mie_block) if extra_context else mie_block
    except Exception:
        pass

    # Inject Historical Market Memory — verified past events to replace hallucinated comparisons
    try:
        from app.services.historical_memory_service import find_similar_events, format_for_ai_prompt

        # Derive search attributes from the query text first — live events only
        # ever carry event_type="macro" so they can't drive category matching —
        # falling back to event-derived sectors when the query itself is generic.
        hist_sectors: list[str] = []
        hist_category: str | None = None
        for ev in (events or [])[:3]:
            hist_sectors.extend(ev.get("affected_sectors", ev.get("sectors", [])) or [])
            if not hist_category:
                hist_category = ev.get("event_type") or ev.get("category")

        _query_lower = query.lower()
        hist_query = {
            "category":  _infer_historical_category(_query_lower) or hist_category,
            "sectors":   _infer_historical_sectors(_query_lower) or list(dict.fromkeys(hist_sectors))[:4],
            "sentiment": intent_data.get("sentiment"),
        }

        if hist_query.get("category") or hist_query.get("sectors"):
            similar = await find_similar_events(hist_query, limit=5, min_similarity=25.0)
            if similar:  # noqa: SIM102 — also captures outer `similar` for confidence
                hist_block = format_for_ai_prompt(similar, max_events=5)
                extra_context = (extra_context + "\n\n" + hist_block) if extra_context else hist_block
    except Exception:
        pass

    # Fetch calibration data (memory-cached, does not block significantly)
    _cal_data: dict = {}
    try:
        from app.services.prediction_service import get_calibration_data
        _cal_data = await get_calibration_data()
    except Exception:
        pass

    # Compute pre-AI evidence-based confidence estimate from observable signals
    _pre_factors = None
    _conf_result = None
    try:
        from app.services.confidence_service import ConfidenceFactors, calculate_confidence as _calc_conf
        _mie_sig  = mie_state.get("signals", {})
        _mie_dir  = _mie_sig.get("direction", "")
        _i_sent   = intent_data.get("sentiment", "")
        _macro_ok = (
            (_mie_dir == "up"   and _i_sent == "bullish") or
            (_mie_dir == "down" and _i_sent == "bearish")
        )
        _vix_val  = float(_vix_level or 0)
        _vix_rgm  = (
            "very_high" if _vix_val > 25 else
            "high"      if _vix_val > 18 else
            "low"       if 0 < _vix_val < 12 else
            "normal"
        )
        _hist_acc = (
            sum(s.get("confidence", 80) for s in similar) / (100.0 * len(similar))
            if similar else 0.0
        )
        _pre_factors = ConfidenceFactors(
            source_count=len(events) + len(news),
            historical_count=len(similar),
            historical_accuracy=_hist_acc,
            macro_aligned=_macro_ok,
            macro_reason=_mie_sig.get("top_theme", "") if _macro_ok else "",
            vix_level=_vix_val,
            volatility_regime=_vix_rgm,
            ai_certainty=5,
        )
        _pre_conf    = _calc_conf(_pre_factors)
        extra_context = (extra_context + "\n\n" + _pre_conf.explanation) if extra_context else _pre_conf.explanation
    except Exception:
        pass

    # AI generation — only genuine two-asset comparisons (both a holding AND
    # a target actually named by the user) get the switch/hold comparison
    # prompt. Everything else — including single-entity "should I invest in
    # X" questions — is an investment_opportunity query and goes through the
    # general prompt so it never fabricates a placeholder "Asset A".
    if intent_data["is_comparison"] and intent not in ("list_picks", "portfolio_review", "news_reaction", "earnings_preview", "entry_timing"):
        prompt  = _build_decision_prompt(query, intent_data, events, news, policies, extra_context=extra_context)
        max_tok = 4500
    else:
        prompt  = _build_prompt(query, events, news, policies, intent_data=intent_data, extra_context=extra_context)
        # The JSON schema grew substantially this session (bottom_line,
        # key_drivers, what_priced_in, per-sector explanation, etc.) — 3500
        # was tight enough to truncate mid-JSON on some fallback models,
        # which fails to parse and silently drops to the graceful default.
        max_tok = 4500
    raw = await _call_with_fallback(prompt, _SYSTEM, max_tokens=max_tok)
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
            "bottom_line": (
                f"There isn't enough freshly generated analysis to answer “{query}” with confidence right now "
                "— the underlying event and news data is available below, but the synthesis step didn't complete. "
                "Try rephrasing the question or checking back shortly."
            ),
            "what_happened": "A significant market development has been identified related to the queried topic.",
            "why_it_happened": "Multiple macro, policy, and sector-specific factors are driving this development.",
            "immediate_impact": "Near-term markets are reacting to this development with sector-specific movement.",
            "medium_term": "The 3-12 month outlook depends on policy execution and global macro environment.",
            "long_term": "Structural implications are broadly positive for India's capital markets.",
            "what_priced_in": "Insufficient data to assess current positioning — treat any near-term move as unconfirmed.",
            "risks": ["Execution risk", "Global headwinds", "Regulatory uncertainty"],
            "opportunities": ["Sector rotation", "Infrastructure capex", "Export growth"],
            "key_drivers": [],
            "confidence": 40, "sentiment": "neutral",
            "insights": [
                {"icon": "📊", "title": "Market Overview",   "summary": "Current market conditions reflect mixed global and domestic signals with selective sector strength."},
                {"icon": "🏛️", "title": "Policy Framework", "summary": "Government policy remains focused on infrastructure, manufacturing, and economic growth enablement."},
                {"icon": "🏆", "title": "Sector Leaders",   "summary": "Infrastructure and defence sectors are well positioned to outperform peers in this environment."},
                {"icon": "⚠️", "title": "Risk Watch",       "summary": "Monitor global commodity prices, currency movements, and domestic fiscal deficit trajectory."},
            ],
            "companies": [], "sectors": [], "timeline": [],
            "follow_up_questions": ["Which sectors benefit most?", "What is the timeline?", "Key risks?", "Historical precedents?"],
            "investment_verdict": {
                "rating": "Neutral", "direction": "neutral", "confidence": 40,
                "horizon": "6-12 months", "top_picks": [],
                "risks": ["Macro uncertainty"], "catalysts": ["Policy clarity"],
                "opportunity_score": 50,
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

    # De-duplicate by symbol — the AI occasionally returns the same company
    # twice under two different framings (e.g. once as a beneficiary, once
    # flagged as at-risk), which reads as a data-quality bug, not nuance.
    # Keep whichever occurrence has the higher impact score.
    _seen_symbols: dict[str, dict] = {}
    for _c in companies_enriched:
        _sym = (_c.get("symbol") or "").upper()
        if not _sym:
            continue
        _prev = _seen_symbols.get(_sym)
        if _prev is None or float(_c.get("impact_score", 0) or 0) > float(_prev.get("impact_score", 0) or 0):
            _seen_symbols[_sym] = _c
    companies_enriched = list(_seen_symbols.values())

    # Sort by actual impact score (defense-in-depth — don't trust AI ordering)
    # and classify each company's position in the ripple, deterministically.
    companies_enriched.sort(key=lambda c: float(c.get("impact_score", 0) or 0), reverse=True)
    _classify_ripple_position(companies_enriched)
    for _c in companies_enriched:
        _c.setdefault("why_it_matters", _c.get("reason", ""))

    # Sectors: time_horizon + status are computed server-side, not AI-generated,
    # so labeling stays consistent regardless of prompt compliance.
    sectors_raw = ai.get("sectors", [])
    for _s in sectors_raw:
        _status = _sector_status(bool(_s.get("positive", True)), float(_s.get("score", 0) or 0))
        _s["status"] = _status
        _s["time_horizon"] = _sector_time_horizon(_status)
        _s.setdefault("explanation", "")

    # Finalize evidence-based confidence — now that live company prices and
    # sector direction exist, feed the formula genuine market/sector
    # confirmation signals instead of leaving them at 0 (they were computed
    # before enrichment ran, so market_confirming/sector_confirming/
    # company_sensitivity never had real data to work with).
    if _pre_factors is not None:
        try:
            from app.services.confidence_service import calculate_confidence as _calc_conf, _THRESHOLDS
            _thesis = ai.get("sentiment") or "neutral"
            if _thesis == "bullish":
                _pre_factors.market_confirming = sum(
                    1 for c in companies_enriched if c.get("price") != "—" and c.get("positive")
                )
                _pre_factors.sector_confirming = sum(1 for s in sectors_raw if s.get("positive"))
            elif _thesis == "bearish":
                _pre_factors.market_confirming = sum(
                    1 for c in companies_enriched if c.get("price") != "—" and not c.get("positive")
                )
                _pre_factors.sector_confirming = sum(1 for s in sectors_raw if not s.get("positive"))
            _top_impact = max((float(c.get("impact_score", 0) or 0) for c in companies_enriched), default=0)
            _pre_factors.company_sensitivity = "high" if _top_impact >= 80 else ("medium" if _top_impact >= 55 else "low")
            _pre_factors.ai_certainty = min(10, max(1, int(ai.get("confidence_self_rating") or 5)))
            _conf_result = _calc_conf(_pre_factors)

            # Apply historical calibration (only when ≥ 10 verified predictions for this level)
            if _cal_data:
                _lvl_cal = _cal_data.get(_conf_result.level, {})
                _cal_f   = float(_lvl_cal.get("calibration_factor", 1.0))
                _cal_n   = int(_lvl_cal.get("total", 0))
                if _cal_n >= 10 and 0.4 <= _cal_f <= 1.8:
                    _new_score = min(100.0, max(0.0, round(_conf_result.total_score * _cal_f, 1)))
                    _new_level = next(lbl for thr, lbl in _THRESHOLDS if _new_score >= thr)
                    _acc_pct   = round(_lvl_cal.get("accuracy_rate", 0.5) * 100)
                    _conf_result.total_score = _new_score
                    _conf_result.level       = _new_level
                    _conf_result.reasons.append(
                        f"Calibrated from {_cal_n} verified predictions ({_acc_pct}% historical accuracy)"
                    )
        except Exception:
            pass

    # Build context-aware chart: use the query's companies when available, else indices
    _CHART_COLORS = ["#818cf8", "#34d399", "#fb923c", "#f472b6"]
    chart_tickers = []
    for _i, _c in enumerate(companies_enriched[:4]):
        _sym = re.sub(r"\.(NS|BO|BSE|NSE)$", "", _c.get("symbol", "").strip().upper())
        if _sym:
            _name = (_c.get("name") or _sym)[:22]
            chart_tickers.append((_name, f"{_sym}.NS", _CHART_COLORS[_i % 4]))

    # Everything below is independent — run it all concurrently rather than
    # as a chain of sequential awaits.
    top_sector = sectors_raw[0]["name"] if sectors_raw else None
    _entity_type = "search"

    async def _safe(coro, default, label: str):
        try:
            return await coro
        except Exception as _e:
            log.warning(f"ai_search.{label}_fail", exc=str(_e)[:120])
            return default

    from app.services.ai_service import generate_scenario_analysis, generate_monitoring_checklist

    (
        chart, insights, ripple_chain, scenarios, monitoring_raw,
    ) = await asyncio.gather(
        _safe(loop.run_in_executor(None, _fetch_chart_sync, chart_tickers), {"labels": [], "series": []}, "chart"),
        _safe(_generate_insights(query, ai_summary), [], "insights"),
        _safe(_build_ripple_chain(query), [], "ripple_chain"),
        _safe(
            generate_scenario_analysis(_entity_type, ck, title=query, description=ai_summary, sector=top_sector or ""),
            {}, "scenarios",
        ),
        _safe(
            generate_monitoring_checklist(_entity_type, ck, title=query, description=ai_summary, sector=top_sector or ""),
            {}, "monitoring",
        ),
    )
    horizons_raw = _build_market_horizons(
        ai, _conf_result.total_score if _conf_result else ai.get("confidence", 50), ai.get("sentiment", "neutral"),
    )

    what_to_monitor = [
        {
            "title": item.get("label", ""),
            "why_it_matters": item.get("why_it_matters", ""),
            "importance": item.get("importance", "medium"),
            "frequency": item.get("frequency", ""),
        }
        for item in (monitoring_raw.get("items", []) if isinstance(monitoring_raw, dict) else [])
    ]

    graph = _build_graph(query, sectors_raw, companies_enriched)

    # Extract decision_intelligence block when present — only for genuine
    # two-asset comparisons; a single-entity "should I invest in X" question
    # has no holding to compare against and must not render the
    # switch/hold comparison panel at all.
    raw_di = ai.get("decision_intelligence")
    decision_intelligence: dict | None = None
    if intent_data["is_comparison"] and isinstance(raw_di, dict):
        decision_intelligence = raw_di
        decision_intelligence.setdefault("intent",            intent_data["intent"])
        decision_intelligence.setdefault("detected_holding",  intent_data.get("holding"))
        decision_intelligence.setdefault("detected_target",   intent_data.get("target"))
        decision_intelligence.setdefault("detected_horizon",  intent_data.get("horizon"))
        decision_intelligence.setdefault("detected_risk",     intent_data.get("risk"))
        decision_intelligence.setdefault("detected_budget",   intent_data.get("budget"))
        decision_intelligence.setdefault("detected_third",    intent_data.get("third_entity"))
        # Tag entity_type so the frontend renders sectors/commodities vs companies differently
        type_map = {
            "holding_analysis": ("holding_is_commodity", "holding_is_sector"),
            "target_analysis":  ("target_is_commodity",  "target_is_sector"),
        }
        for side, (comm_flag, sec_flag) in type_map.items():
            block = decision_intelligence.get(side)
            if isinstance(block, dict):
                if intent_data.get(comm_flag):
                    block["entity_type"] = "commodity"
                elif intent_data.get(sec_flag):
                    block["entity_type"] = "sector"
                else:
                    block["entity_type"] = "company"
    elif intent_data["is_comparison"]:
        decision_intelligence = {
            "intent":           intent_data["intent"],
            "detected_holding": intent_data.get("holding"),
            "detected_target":  intent_data.get("target"),
            "detected_horizon": intent_data.get("horizon"),
            "detected_risk":    intent_data.get("risk"),
            "detected_budget":  intent_data.get("budget"),
            "context_complete": True,
            "missing_context":  [],
            "decision_summary": ai.get("summary", ""),
        }

    _final_confidence = round(_conf_result.total_score) if _conf_result else ai.get("confidence", 65)

    # Research Outlook — rating is forced through the 8-label enum regardless
    # of what the AI returned; this is a research platform, never advisory.
    _verdict_raw  = ai.get("investment_verdict", {}) or {}
    _verdict_horizon = _verdict_raw.get("horizon", "6-12 months")
    _verdict_risk    = "High" if _final_confidence < 50 else ("Medium" if _final_confidence < 75 else "Low")
    investment_verdict = {
        **_verdict_raw,
        "rating": _normalize_outlook(
            _verdict_raw.get("rating", ""), _verdict_raw.get("direction", "neutral"),
            _verdict_raw.get("confidence", _final_confidence), _verdict_raw.get("opportunity_score", 50),
        ),
        "risk_level": _verdict_risk,
        "suitable_for": _suitable_for(_verdict_horizon, _verdict_risk),
    }

    # Historical Comparison — real, structured data from historical_memory_service
    # (verified seed events with real per-company returns), never AI-invented.
    historical_comparison = [
        {
            "event_title":  h.get("event_title", ""),
            "event_date":   str(h.get("event_date", ""))[:10],
            "similarity":   h.get("similarity", 0),
            "key_lesson":   h.get("key_lesson", ""),
            "key_difference": _key_difference(hist_query, h),
            "what_happened": h.get("what_happened", ""),
            "sector_reactions":  h.get("sector_reactions", {}),
            "historical_winners": h.get("historical_winners", []),
            "historical_losers":  h.get("historical_losers", []),
            "nifty_1w": h.get("nifty_1w"),
            "nifty_1m": h.get("nifty_1m"),
        }
        for h in similar
    ]

    ai_reasoning_methods = _build_reasoning_methods(
        events, similar, extra_context_lines, mie_state, ripple_chain, companies_enriched,
        news=news, policies=policies,
    )
    confidence_caveats = _confidence_caveats(_conf_result, events, similar, len(news) + len(events))

    result = {
        "query": query,
        "entities": entities,
        "answer": {
            "summary":          ai.get("summary", ""),
            "bottom_line":      _cap_words(ai.get("bottom_line", ai.get("summary", "")), 120),
            "what_happened":    ai.get("what_happened", ""),
            "why_it_happened":  ai.get("why_it_happened", ""),
            "immediate_impact": ai.get("immediate_impact", ""),
            "medium_term":      ai.get("medium_term", ""),
            "long_term":        ai.get("long_term", ""),
            "what_priced_in":   ai.get("what_priced_in", ""),
            "risks":            ai.get("risks", []),
            "opportunities":    ai.get("opportunities", []),
            "confidence":       _final_confidence,
            "confidence_level": _conf_result.level if _conf_result else "Medium",
            "sentiment":        ai.get("sentiment", "neutral"),
            "sources_count":    len(news) + len(events),
        },
        "key_drivers":          ai.get("key_drivers", []),
        "insights":             insights or ai.get("insights", []),
        "companies":            companies_enriched,
        "sectors":              sectors_raw,
        "related_events":       events[:6],
        "news":                 news[:6],
        "policies":             policies[:4],
        "timeline":             ai.get("timeline", []),
        "historical_comparison": historical_comparison,
        "ripple_chain":         ripple_chain,
        "scenarios":            scenarios if isinstance(scenarios, dict) else {},
        "market_impact_horizons": horizons_raw if isinstance(horizons_raw, list) else [],
        "what_to_monitor":      what_to_monitor,
        "ai_reasoning_methods": ai_reasoning_methods,
        "follow_up_questions":  ai.get("follow_up_questions", []),
        "investment_verdict":   investment_verdict,
        "market_chart":         chart,
        "graph":                graph,
        "citations":            list({a.get("source", "") for a in news if a.get("source")}),
        "decision_intelligence": decision_intelligence,
        "confidence_data": {
            "level":     _conf_result.level if _conf_result else "Medium",
            "score":     _final_confidence,
            "reasons":   list(_conf_result.reasons) if _conf_result else [],
            "breakdown": dict(_conf_result.breakdown) if _conf_result else {},
            "caveats":   confidence_caveats,
        },
    }

    _CACHE[ck] = (time.time(), result)  # store with current timestamp; TTL applied on read

    # Asynchronously persist predictions for the learning engine (non-blocking)
    asyncio.create_task(
        _store_search_predictions(result, _conf_result),
        name="prediction-store",
    )

    log.info("ai_search.done", query=query[:50], cos=len(companies_enriched), events=len(events), intent=intent)
    return result


def _map_horizon(horizon_str: str) -> int:
    """Map investment_verdict.horizon text to calendar days."""
    h = (horizon_str or "").lower()
    if "intraday" in h or ("1" in h and "day" in h):    return 1
    if "week" in h or "3" in h and "day" in h:          return 3
    if "1 month" in h or "short" in h and "term" in h:  return 7
    return 30  # default: 30-day horizon for longer-term predictions


async def _store_search_predictions(result: dict, conf_result: Any) -> None:
    """Extract and persist predictions from an AI search result."""
    try:
        from app.services.prediction_service import store_prediction

        query    = result.get("query", "")
        verdict  = result.get("investment_verdict") or {}
        answer   = result.get("answer") or {}
        companies_list = result.get("companies") or []

        direction = (verdict.get("direction") or answer.get("sentiment") or "sideways").lower()
        if direction == "bullish":  direction = "up"
        if direction == "bearish":  direction = "down"
        if direction not in ("up", "down"): direction = "sideways"

        horizon   = _map_horizon(verdict.get("horizon", ""))
        conf_score = float((conf_result.total_score if conf_result else None) or verdict.get("confidence", 60) or 60)
        conf_level = (conf_result.level if conf_result else None) or "Medium"
        conf_break = dict(conf_result.breakdown) if conf_result else {}

        # 1) Overall market direction prediction (top company as primary entity)
        top_cos = [c for c in companies_list[:2] if c.get("symbol")]
        if top_cos or verdict.get("direction"):
            entities = [
                {
                    "type":   "company",
                    "symbol": c.get("symbol", ""),
                    "name":   c.get("name", ""),
                    "ticker": c.get("symbol", ""),
                }
                for c in top_cos[:2]
            ]
            pred_text = (
                f"{direction.upper()} on {', '.join(c.get('symbol','') for c in top_cos) or 'market'} "
                f"— {answer.get('immediate_impact', '')[:120]}"
            )
            await store_prediction(
                source="ai_search",
                prediction_text=pred_text,
                direction=direction,
                prediction_type="overall",
                target_entities=entities,
                confidence_score=conf_score,
                confidence_level=conf_level,
                confidence_factors=conf_break,
                horizon_days=horizon,
                query=query[:400],
            )

        # 2) Individual company predictions (beneficiary = up, at_risk = down)
        for company in companies_list[:3]:
            sym = company.get("symbol", "").strip()
            if not sym:
                continue
            impact = (company.get("impact_type") or "neutral").lower()
            co_dir = "up" if impact == "beneficiary" else "down" if impact == "at_risk" else "sideways"
            co_conf = min(100, max(0, float(company.get("confidence", conf_score) or conf_score)))
            await store_prediction(
                source="ai_search",
                prediction_text=f"{co_dir.upper()} on {sym}: {company.get('reason', '')[:120]}",
                direction=co_dir,
                prediction_type="company",
                target_entities=[{
                    "type":   "company",
                    "symbol": sym,
                    "name":   company.get("name", sym),
                    "ticker": sym,
                }],
                confidence_score=co_conf,
                confidence_level=conf_level,
                confidence_factors=conf_break,
                horizon_days=horizon,
                query=query[:400],
            )
    except Exception as exc:
        log.debug("prediction.store_search_fail", error=str(exc)[:80])
