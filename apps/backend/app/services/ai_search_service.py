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
# Company matching reuses the real 202-company NSE universe (app.api.companies
# ._NSE_UNIVERSE — symbol/name/sector/industry/cap/aliases, already the source
# of truth for /api/companies and for entity_resolver.resolve_entities() used
# elsewhere in this same file's ripple-chain building) instead of a 27-name
# hardcoded list. This also fixes a latent bug: the old list matched on
# arbitrary lowercase words like "hdfc", which _fetch_valuation_sync then
# .upper()'d into "HDFC" — not a real ticker (HDFC Bank's actual symbol is
# HDFCBANK) — so valuation data silently never loaded for it. Returning real
# symbols directly fixes that as a side effect.
_SECTORS = [
    "railway", "infrastructure", "banking", "it", "technology", "defence", "energy",
    "pharma", "auto", "fmcg", "metals", "realty", "telecom", "power", "finance", "logistics",
]
_POLICIES = [
    "budget", "rbi", "sebi", "gst", "pli", "fdi", "npa", "repo rate",
    "monetary policy", "fiscal policy", "make in india", "pm gati shakti",
]


def _match_companies(q: str) -> list[str]:
    """
    Word-boundary-aware alias matching. Plain substring containment (the
    original implementation) let short tickers/aliases match inside
    unrelated words — found live via a broad test sweep: "ITC" matched
    inside "sw-ITC-h", "REC" matched inside "REC-ent", "LIC" matched inside
    "po-LIC-y". Every one of those produced a spurious extra company in the
    response with no real connection to the query.
    """
    from app.api.companies import _NSE_UNIVERSE
    matched: list[str] = []
    for co in _NSE_UNIVERSE:
        aliases = (co.get("aliases") or []) + [co["name"].lower(), co["symbol"].lower()]
        for a in aliases:
            if len(a) < 3:
                continue
            idx = q.find(a)
            if idx == -1:
                continue
            before_ok = idx == 0 or not q[idx - 1].isalnum()
            after_idx = idx + len(a)
            after_ok = after_idx == len(q) or not q[after_idx].isalnum()
            if before_ok and after_ok:
                matched.append(co["symbol"])
                break
    return matched


def _extract_entities(query: str) -> dict:
    q = query.lower()
    return {
        "companies": _match_companies(q),
        "sectors":   [s for s in _SECTORS   if s in q],
        "policies":  [p for p in _POLICIES   if p in q],
    }


# ── Market Pulse intent — real-data-first, never LLM-ranked ──────────────────
# "Which stocks performed well", "best sector", "market summary" and similar
# queries used to fall through to the generic `general` intent, where the LLM
# picked companies/sectors from nothing and got live prices bolted on
# afterward. This intent short-circuits that entirely: market_pulse_service
# fetches real top movers / sector performance / verified drivers BEFORE any
# LLM call, and the model's only job is to explain what it's given.
_MARKET_PULSE_RE = re.compile(
    r"\b("
    r"top\s+gainers?|top\s+losers?|"
    r"which\s+stocks?\s+(?:performed|did)\s+well|"
    r"which\s+stocks?\s+(?:fell|dropped|rose|gained|rallied|rallying|surged|crashed|are\s+up|are\s+down)|"
    r"stocks?\s+(?:that\s+)?(?:performed|did)\s+well|"
    r"(?:stocks?|large.?caps?)\s+(?:that\s+)?(?:rallied|rallying|surged|crashed|declined|declining|falling)|"
    r"(?:rallying|declining|falling|crashing)\s+(?:in\s+the\s+market|today|the\s+most)|"
    r"gaining\s+stocks?|declining\s+stocks?|"
    r"outperform\w*\s+(?:the\s+)?(?:index|nifty|market)|underperform\w*\s+(?:the\s+)?(?:index|nifty|market)|"
    r"strongest\s+momentum|weakest\s+momentum|"
    r"dragging\s+(?:the\s+)?market|weighing\s+on\s+(?:the\s+)?market|"
    r"best[- ]perform\w*|worst[- ]perform\w*|top[- ]perform\w*|"
    r"best\s+sector|worst\s+sector|"
    r"(?:leading|lagging|top|strongest|weakest)\s+sectors?|sector\s+rotation|"
    r"sector\w*\s+(?:is|are)\s+(?:leading|lagging|outperform\w*|underperform\w*)|"
    r"sector\s+(?:is\s+)?(?:institutional\s+money|money)\s+(?:is\s+)?flowing|"
    r"market\s+summary|market\s+(?:today|recap|wrap|update)|"
    r"how\s+is\s+the\s+market|how(?:'s|\s+is)\s+the\s+market\s+doing|"
    r"(?:overall\s+)?mood\s+in\s+the\s+market|"
    r"(?:good|bad)\s+day\s+for\s+the\s+markets?|"
    r"summarize\s+(?:today'?s|this\s+week'?s)\s+(?:trading|market)|"
    r"market\s+(?:bullish|bearish)\s+right\s+now|is\s+the\s+market\s+(?:bullish|bearish)|"
    r"recap\s+of\s+(?:this\s+week|today)\s+in\s+the\s+markets?|"
    r"how\s+did\s+(?:nifty|sensex|the\s+market)\s+(?:close|do)|"
    r"today'?s\s+(?:top\s+|biggest\s+)?(?:gainers?|losers?|winners?|movers?|gaining\s+stocks?)|"
    r"biggest\s+(?:gainers?|losers?|winners?|movers?)|"
    r"52.?week\s+highs?|52.?week\s+lows?|most\s+active\s+stocks?|highest\s+volume\s+stocks?|"
    r"what'?s\s+(?:driving|moving)\s+the\s+market|"
    r"why\s+is\s+(?:the\s+)?(?:nifty|sensex|market)\s+(?:up|down)"
    r")\b",
    re.IGNORECASE,
)


def _detect_market_pulse(query: str) -> bool:
    return bool(_MARKET_PULSE_RE.search(query))


# ── Market Pulse — semantic fallback classifier ───────────────────────────────
# The regex above is fast and free but has a hard recall ceiling: it matches
# patterns, not meaning, so "which large-cap stocks rallied today" and "top
# gainers" can land on opposite sides of the same regex even though they're
# the same question. Confirmed empirically — re-running the regex against a
# 308-question test set found 91%→18% recall across market-pulse-shaped
# categories depending on phrasing. This is the actual fix: when the regex
# doesn't match, ask a cheap/fast model a tightly-scoped yes/no question
# instead of adding another 30 regex alternations that will still miss the
# next paraphrase. Fails closed (False) on any error — a classifier hiccup
# must never block the existing general-path pipeline, only add to it.
_MARKET_PULSE_CLASSIFY_SYSTEM = (
    "You classify Indian stock market search queries for a routing system. "
    "Respond with exactly one word, 'yes' or 'no', nothing else.\n\n"
    "Say 'yes' ONLY if the query is asking for real-time market data with NO "
    "specific company and NO specific named sector in it — e.g. today's top "
    "gaining/losing stocks, best/worst-performing sector (asked generically, "
    "not naming which sector), most active stocks, or an overall market mood/"
    "summary/recap.\n\n"
    "Say 'no' for everything else: company research or recommendations, "
    "comparisons ('X vs Y'), buy/sell/hold decisions, a SPECIFIC sector named "
    "by the user (e.g. 'how is banking doing'), valuation, portfolio questions, "
    "historical comparisons, macro/policy questions, IPOs, commodities, "
    "currency, or general investing questions."
)


async def _classify_market_pulse_llm(query: str) -> bool:
    try:
        from app.services.ai_service import _call_with_fallback
        raw = await _call_with_fallback(f'Query: "{query}"', _MARKET_PULSE_CLASSIFY_SYSTEM, max_tokens=5)
        return bool(raw) and raw.strip().lower().lstrip('"\'').startswith("y")
    except Exception as exc:
        log.warning("ai_search.market_pulse_classify_failed", error=str(exc)[:120])
        return False


async def _detect_market_pulse_async(query: str) -> bool:
    """Fast regex first (no LLM cost for the obvious cases); only escalates
    to the semantic classifier when the regex found nothing, so already-fast
    queries stay fast and only the ambiguous ~86% pay the classification cost."""
    if _detect_market_pulse(query):
        return True
    return await _classify_market_pulse_llm(query)


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
    # "move from" needed "move" directly before "from" — missed "move
    # INVESTMENT from X to Y" (found live). (?:\s+\w+){0,3} tolerates
    # filler words in between, same fix family as switch-from-to below.
    "switch":           [r"\bswitch(?:ing)?\b", r"\brotate?\b", r"\binstead of\b", r"\bsell.{1,30}buy\b", r"\bmove\b(?:\s+\w+){0,3}\s+from\b", r"\breplace\b"],
    "hold":             [r"\bshould i hold\b", r"\bkeep holding\b", r"\bcontinue holding\b", r"\bstill hold\b", r"\bhold or sell\b"],
    "compare":          [r"\bcompare\b", r"\bvs\.?\b", r"\bversus\b", r"\bbetter than\b", r"\bwhich is better\b", r"\bwhich (?:one|company|stock)\b"],
    "sell":             [r"\bshould i sell\b", r"\bwhen to sell\b", r"\bexit\b", r"\bbook (?:profit|loss)\b"],
    # "top \d+ stocks" alone missed any real-world phrasing with a sector/
    # theme qualifier between the count and the noun ("top 5 BANKING
    # stocks") — (?:\w+\s+){0,4} tolerates multi-word qualifiers in between
    # (found live: "top 5 EV AND DEFENCE stocks" needed {0,4}, not {0,2}),
    # same fix pattern as the switch-from-to gap found this session. The
    # last two patterns cover "best/top X stocks" with NO count at all
    # (also found live — "best defence companies", "best AI stocks") —
    # plural-only to avoid false-triggering on singular "the best stock to
    # buy" type single-entity decision queries.
    "list_picks":       [r"\bgive me \d+\b", r"\btop \d+ (?:\w+\s+){0,4}(?:stocks?|picks?|companies|shares)\b", r"\bbest \d+ (?:\w+\s+){0,4}(?:stocks?|picks?|companies|shares)\b", r"\brecommend \d+\b", r"\b\d+ best (?:stocks?|picks?)\b", r"\bwhich \d+ (?:\w+\s+){0,4}(?:stocks?|picks?)\b", r"\bbest (?:\w+\s+){0,3}(?:stocks|picks|companies|shares)\b", r"\btop (?:\w+\s+){0,3}(?:stocks|picks|companies|shares)\b"],
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
# Same as _COMPARE_RE plus "and" as a connector — "and" is too ambiguous a
# signal to trust in the general fallback (used for switch/hold/sell/buy/
# decision/general), but inside a query whose intent already contains the
# literal word "compare", "and" is the single most natural connector
# ("Compare TCS and Infosys" — found live, unmatched by the vs/versus/or
# original) and safe to accept there.
_COMPARE_RE_AND = re.compile(
    r"(?:is\s+)?([A-Za-z][A-Za-z0-9 &.]{2,30}?)\s+"
    r"(?:vs\.?|versus|better than|or|and)\s+"
    r"([A-Za-z][A-Za-z0-9 &.]{2,30}?)(?:\s+for|\s+in|[?.,]|$)",
    re.IGNORECASE,
)
_SWITCH_FROM_TO_RE = re.compile(
    r"(?:switch|rotate|move)(?:ing)?(?:\s+\w+){0,3}\s+(?:(?:out\s+of|away\s+from)|from)\s+"
    r"([A-Za-z][A-Za-z0-9 &.]{1,30}?)\s+(?:to|into|for)\s+"
    r"([A-Za-z][A-Za-z0-9 &.]{1,30}?)(?:\.|,|$|\?| now| instead)",
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

# Additional data-first triggers — same pattern as _VALUATION_TRIGGERS/_VIX_TRIGGER
# above: a cheap keyword regex gates a real (non-LLM) data fetch that gets
# appended to extra_context, so the general-path LLM explains real numbers
# instead of free-generating them. None of these change routing/schema —
# they only ground the existing general/decision prompts with more evidence.
_SECTOR_TRIGGER = re.compile(r"\b(?:sector|industry)\b", re.IGNORECASE)
_OPPORTUNITY_TRIGGER = re.compile(r"\bopportunit(?:y|ies)\b", re.IGNORECASE)
_THEME_TRIGGER = re.compile(r"\btheme\b", re.IGNORECASE)
_RISK_TRIGGER = re.compile(r"\brisks?\b", re.IGNORECASE)
_MACRO_TRIGGER = re.compile(
    r"\b(?:inflation|repo rate|interest rate|rbi rate|gdp|crude oil|oil price|"
    r"rupee|dollar|fii|dii|macro(?:economic)?)\b",
    re.IGNORECASE,
)
_RESULTS_TRIGGER = re.compile(
    r"\b(?:results?|earnings?)\b.*\b(?:announced|reported|posted|released|out|declared)\b|"
    r"\b(?:announced|reported|posted|released|declared)\b.*\b(?:results?|earnings?)\b",
    re.IGNORECASE,
)


def _commodity_safety_note(query: str) -> str:
    """
    The symbol-safety guidance that stops the model from inventing a fake
    equity ticker for a commodity/currency/index used to only exist inside
    the two-entity decision prompt (_build_decision_prompt's symbol_hint()).
    A bare single-entity query like "Should I invest in gold?" got no such
    guidance and went through the general schema, which expects a real NSE
    equity symbol for every companies[] entry. This extends the same real
    ETF-proxy mapping (_COMMODITY_TICKERS) to the general prompt whenever a
    commodity/currency/index name is detected in the query text.
    """
    q = query.lower()
    hit = next((name for name in _COMMODITY_NAMES if name in q), None)
    if not hit:
        return ""
    ticker = _COMMODITY_TICKERS.get(hit)
    ticker_note = f' A real ETF proxy exists for "{hit}": {ticker}.' if ticker else ""
    return (
        f'\n- The query mentions "{hit}", which is a commodity/currency/index/asset class, not a single '
        f"listed equity. Do NOT invent a fake equity ticker for it in \"companies\". Either omit it from "
        f'"companies" entirely, or if a real ETF/index-fund proxy exists, use that proxy\'s real NSE symbol '
        f"instead.{ticker_note}"
    )


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
            # _COMPARE_RE_AND (not the shared _COMPARE_RE) — "and" is only
            # trusted as a connector here, where the query already contains
            # the literal word "compare" ("Compare TCS and Infosys" — found
            # live, unmatched by vs/versus/better-than/or alone).
            mc = _COMPARE_RE_AND.search(query)
            if mc:
                holding = re.sub(r"^compare\s+(?:the\s+)?", "", mc.group(1).strip(), flags=re.IGNORECASE)
                target  = mc.group(2).strip()
    elif detected_intent == "switch" and not holding and not target:
        # "switch/rotate/move FROM X TO Y" — the single most natural way to
        # phrase a switch decision, and previously unhandled: _HOLDING_RE
        # needs first-person possession language ("I hold X"), _TARGET_RE
        # needs "switch TO X" (not "FROM X TO Y"), and _COMPARE_RE needs a
        # vs/versus/or connector. All three miss this phrasing, so is_comparison
        # silently came out False and the whole decision-comparison path
        # (including the Decision Engine) never ran for it.
        msft = _SWITCH_FROM_TO_RE.search(query)
        if msft:
            holding = msft.group(1).strip()
            target  = msft.group(2).strip()
        else:
            mc = _COMPARE_RE.search(query)
            if mc:
                holding = mc.group(1).strip()
                target  = mc.group(2).strip()
    elif detected_intent in ("hold", "sell", "buy", "decision", "general") and not holding and not target:
        # Fallback: try compare regex for "X vs Y" / "X or Y" phrasing even
        # when no decision-intent keyword fired at all — "HDFC or ICICI?"
        # (found live) previously stayed intent=general with is_comparison
        # never even attempted, because "general" wasn't in this tuple.
        # _COMPARE_RE's connector list already requires a real structural
        # signal (vs/versus/better than/or), so this is safe to attempt
        # unconditionally rather than gating it behind a specific intent.
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


def _fmt_drivers(drivers: list[dict]) -> str:
    if not drivers:
        return "no verified driver found"
    return "; ".join(f"{d['driver']} [{d['confidence_tier']} confidence] ({d['evidence']})" for d in drivers)


def _build_market_pulse_prompt(query: str, pulse: dict) -> str:
    """
    Market Pulse prompt — the LLM never selects or ranks anything here. Every
    stock, sector, and number below was fetched by market_pulse_service
    BEFORE this prompt was built. The model's only job is to explain the
    given data in prose; it must not add, remove, or reorder any entry, and
    must say so plainly (not invent a reason) when a stock has no verified
    driver attached.
    """
    status = pulse.get("market_status") or {}
    idx_lines = "\n".join(
        f"- {i['name']}: {i['value']} ({i['change']})" for i in (pulse.get("indices") or [])
    ) or "None"
    lead_sec = "\n".join(f"- {s['name']}: {s['value']}" for s in (pulse.get("leading_sectors") or [])) or "None"
    lag_sec  = "\n".join(f"- {s['name']}: {s['value']}" for s in (pulse.get("lagging_sectors") or [])) or "None"
    gainers  = "\n".join(
        f"- {g['company']} ({g['ticker']}) {g['value']} at {g['subtitle']} — verified drivers: {_fmt_drivers(g['verified_drivers'])}"
        for g in (pulse.get("top_gainers") or [])
    ) or "None"
    losers   = "\n".join(
        f"- {g['company']} ({g['ticker']}) {g['value']} at {g['subtitle']} — verified drivers: {_fmt_drivers(g['verified_drivers'])}"
        for g in (pulse.get("top_losers") or [])
    ) or "None"
    opp = pulse.get("biggest_opportunity") or {}
    risk = pulse.get("biggest_risk") or {}
    watch = "\n".join(
        f"- {w.get('date','')}: {w.get('title','')} ({w.get('category','')})" for w in (pulse.get("what_to_watch_next") or [])
    ) or "None scheduled"

    return f"""Query: "{query}"

REAL MARKET DATA (already fetched — do not add, remove, reorder, or re-rank anything below; your only job is to explain it):

Market status: {status.get('status', 'unknown')} ({status.get('time_ist', '')}, {status.get('date', '')})
Market mood (from live intelligence engine): {pulse.get('market_mood', 'Neutral')} · direction: {pulse.get('market_direction', 'sideways')}

Indices:
{idx_lines}

Leading sectors (real % change):
{lead_sec}

Lagging sectors (real % change):
{lag_sec}

Top gainers (real price + % change; verified drivers are the ONLY real evidence available for why each moved):
{gainers}

Top losers (real price + % change):
{losers}

Biggest opportunity on record: {opp.get('title', 'None')} — {opp.get('summary', '')}
Biggest risk on record: {risk.get('headline') or risk.get('reason') or 'None'}

Upcoming (real calendar):
{watch}

INSTRUCTIONS:
- For each gainer/loser, write ONE sentence using ONLY the verified drivers given for it. If a stock's verified drivers say "no verified driver found", your sentence MUST say that plainly (e.g. "No specific news or sector driver was identified for this move — likely broad-market or idiosyncratic trading."). Do not invent a reason.
- "market_summary" = 2-3 sentences synthesizing the real mood/index data above. Do not state index levels or % moves that aren't in the data above.
- "sector_narrative" = 1 sentence on what the real leading/lagging sector split suggests.
- "ai_conclusion" = 2-3 sentences: is today's move broad-based (many sectors/stocks participating) or narrow (isolated names)? What does the pattern across the real sectors and movers above suggest? This is synthesis of the given data, not new facts.
- "what_to_watch_summary" = 1-2 sentences framing the real upcoming calendar items above. Do not invent events not listed.
- Return valid JSON only. No markdown. No commentary outside the JSON.

JSON to fill and return:
{{
  "market_summary": "",
  "sector_narrative": "",
  "gainer_narratives": {{ "<TICKER>": "one sentence per gainer above, keyed by ticker" }},
  "loser_narratives": {{ "<TICKER>": "one sentence per loser above, keyed by ticker" }},
  "ai_conclusion": "",
  "what_to_watch_summary": ""
}}"""


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
- The "insights" titles must be SPECIFIC to the query "{query}" — choose angles that make sense for this exact topic. Use real NSE symbols, actual rupee amounts, and genuine Indian market context throughout.{_commodity_safety_note(query)}{_intent_overlay(intent_data, extra_context)}"""


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


# ── Market Pulse pipeline — real data first, AI explains only ─────────────────
def _parse_json_response(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        clean = raw.strip()
        if clean.startswith("```"):
            clean = re.sub(r"^```(?:json)?\s*", "", clean)
            clean = re.sub(r"\s*```$", "", clean).strip()
        return json.loads(clean)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except Exception:
                pass
    return {}


async def _run_market_pulse_search(query: str) -> dict:
    """
    Real-data-first path for "which stocks performed well", "best sector",
    "market summary" and similar queries. market_intelligence_service fetches
    every fact BEFORE any LLM call; the model is only allowed to explain what
    it's given (see _build_market_pulse_prompt) — it cannot add, remove, or
    reorder a single stock or sector.
    """
    from app.services.market_intelligence_service import get_market_pulse

    try:
        pulse = await get_market_pulse()
    except Exception as exc:
        log.warning("ai_search.market_pulse_fetch_failed", error=str(exc)[:150])
        pulse = {}

    prompt = _build_market_pulse_prompt(query, pulse)
    raw = await _call_with_fallback(prompt, _SYSTEM, max_tokens=2500)
    ai = _parse_json_response(raw)
    synthesis_incomplete = not bool(ai)

    def _attach_narrative(movers: list[dict], narratives: dict) -> list[dict]:
        out = []
        for m in movers:
            n = narratives.get(m.get("ticker", "")) if isinstance(narratives, dict) else None
            if not n:
                drivers = m.get("verified_drivers") or []
                n = ("; ".join(d["label"] for d in drivers) if drivers
                     else "No verified driver identified for this move — likely broad-market or idiosyncratic trading.")
            out.append({**m, "narrative": n})
        return out

    return {
        "type":                "market_pulse",
        "query":               query,
        "synthesis_incomplete": synthesis_incomplete,
        "generated_at":        pulse.get("generated_at"),
        "market_status":       pulse.get("market_status", {}),
        "indices":             pulse.get("indices", []),
        "market_mood":         pulse.get("market_mood"),
        "market_direction":    pulse.get("market_direction"),
        "market_summary":      ai.get("market_summary") or "Real-time market data is shown below; a written summary couldn't be generated right now.",
        "sector_narrative":    ai.get("sector_narrative") or "",
        "leading_sectors":     pulse.get("leading_sectors", []),
        "lagging_sectors":     pulse.get("lagging_sectors", []),
        "top_gainers":         _attach_narrative(pulse.get("top_gainers", []), ai.get("gainer_narratives") or {}),
        "top_losers":          _attach_narrative(pulse.get("top_losers", []), ai.get("loser_narratives") or {}),
        "most_active":         pulse.get("most_active", []),
        "biggest_opportunity": pulse.get("biggest_opportunity"),
        "biggest_risk":        pulse.get("biggest_risk"),
        "ai_conclusion":       ai.get("ai_conclusion") or "",
        "what_to_watch_next":  pulse.get("what_to_watch_next", []),
        "what_to_watch_summary": ai.get("what_to_watch_summary") or "",
        "scores":              pulse.get("scores", {}),
    }


# ── Main pipeline ─────────────────────────────────────────────────────────────
async def run_ai_search(query: str, db: AsyncSession) -> dict:
    """Full AI search pipeline. Returns complete research report dict."""
    ck = _ck(query)

    # Market Pulse — real-data-first path, checked before decision-intent
    # detection since it's a distinct query family (top movers / sector
    # performance / market summary), never the "LLM picks, price fetched
    # after" flow the rest of this pipeline still uses for other intents.
    # Short, separate TTL: this is live price data, not evergreen analysis.
    # Async: regex first (free), semantic classifier only when regex misses —
    # see _detect_market_pulse_async docstring for why both tiers exist.
    if await _detect_market_pulse_async(query):
        mp_key = f"mp:{ck}"
        cached_pulse = _cget(mp_key, ttl=300)
        if cached_pulse:
            log.info("ai_search.market_pulse_cache_hit", query=query[:50])
            return cached_pulse
        log.info("ai_search.market_pulse_start", query=query[:50])
        mp_result = await _run_market_pulse_search(query)
        if not mp_result.get("synthesis_incomplete"):
            _CACHE[mp_key] = (time.time(), mp_result)
        return mp_result

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
    _valuation_map: dict = {}  # captured for the Decision Engine's real P/E comparison
    if _VALUATION_TRIGGERS.search(query):
        co_syms = [c.upper() for c in entities.get("companies", [])[:2]]
        if co_syms:
            try:
                val = await loop.run_in_executor(None, _fetch_valuation_sync, co_syms)
                _valuation_map = val
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

    # ── Category-specific data-first grounding ──────────────────────────────
    # Same principle as market_pulse: fetch real data before the LLM writes
    # anything, for the query families that previously got zero dedicated
    # evidence and fell straight to a generic prompt. Each block is gated by
    # a cheap keyword regex (same pattern as _VALUATION_TRIGGERS/_VIX_TRIGGER
    # above) so untargeted queries don't pay the extra fetch cost. All calls
    # hit real DB/cache-backed services, never another LLM, and every block
    # fails silently to keep the general path's existing behavior intact.

    # Sector Analysis — real live per-sector % change (fixes categories that
    # previously got zero sector-specific grounding, e.g. "how is the
    # banking sector doing").
    if _SECTOR_TRIGGER.search(query):
        try:
            from app.services.market_data import get_sector_changes
            sector_rows = await get_sector_changes()
            q_lower = query.lower()
            named = [
                s for s in sector_rows
                if any(tok in q_lower for tok in s.get("name", "").lower().split() if len(tok) > 3)
            ]

            def _abs_pct(s: dict) -> float:
                try:
                    return abs(float(str(s.get("value", "0")).replace("%", "").replace("+", "")))
                except (ValueError, TypeError):
                    return 0.0

            shown = sorted(named or sector_rows, key=_abs_pct, reverse=True)[:5]
            if shown:
                block = "Sector performance (real, live 1-day change): " + "; ".join(
                    f"{s['name']} {s['value']}" for s in shown
                )
                extra_context = (extra_context + "\n\n" + block) if extra_context else block
        except Exception:
            pass

    # Opportunities — real Opportunity Engine, not the LLM inventing an
    # opportunities[] list from nothing.
    if _OPPORTUNITY_TRIGGER.search(query):
        try:
            from app.services.opportunity_service import OpportunityService
            terms = (entities.get("companies") or []) + _words(query)
            opps = await OpportunityService(db).list_by_sector_or_theme(terms[:6], limit=5)
            if opps:
                block = "Verified opportunities (real, from the Opportunity Engine): " + "; ".join(
                    f"{o['title']} (score {o['opportunity_score']}, {o['confidence']} confidence, "
                    f"trend {o['trend']}, risk {o['risk_level']})"
                    for o in opps
                )
                extra_context = (extra_context + "\n\n" + block) if extra_context else block
        except Exception:
            pass

    # Theme Analysis — real live Theme Engine (ThemeState rows), not a
    # generic "theme" the LLM makes up.
    if _THEME_TRIGGER.search(query):
        try:
            from app.services.intelligence.engine import read_themes
            themes = await read_themes()
            q_lower = query.lower()
            named = [
                t for t in themes
                if any(tok in q_lower for tok in (t.get("theme") or "").lower().split() if len(tok) > 3)
            ]
            shown = (named or themes)[:3]
            if shown:
                lines = []
                for t in shown:
                    stocks = ", ".join(
                        (s.get("sym", "") if isinstance(s, dict) else str(s))
                        for s in (t.get("top_stocks") or [])[:3]
                    )
                    lines.append(
                        f"{t.get('theme', 'Theme')} (momentum {t.get('momentum', 'n/a')})"
                        + (f" — top stocks: {stocks}" if stocks else "")
                    )
                block = "Live themes (real, from Theme Engine): " + "; ".join(lines)
                extra_context = (extra_context + "\n\n" + block) if extra_context else block
        except Exception:
            pass

    # Risk (direct "what are the risks" style asks) — the real deterministic
    # Risk Score formula, same one market_pulse uses, instead of an
    # unconstrained LLM risk list.
    # Fires for "should I sell" too now — that framing is exactly where a
    # real risk score matters most, and excluding it (the original
    # condition) meant the one intent most about risk got none of this.
    if _RISK_TRIGGER.search(query) or intent == "sell":
        try:
            from app.services.market_data import get_sector_changes
            from app.services.market_scoring_engine import score_risk
            risk_sectors = await get_sector_changes()

            def _pct(s: dict) -> float:
                try:
                    return float(str(s.get("value", "0")).replace("%", "").replace("+", ""))
                except (ValueError, TypeError):
                    return 0.0

            lagging = sorted(risk_sectors, key=_pct)[:3]
            bearish_high_urgency = sum(
                1 for e in (mie_state.get("top_events") or [])
                if e.get("sentiment") == "bearish" and (e.get("urgency") or 0) >= 7
            )
            # Enhancement: score_risk() used to be entirely market-wide —
            # every entity got the identical number regardless of what was
            # actually asked. When a specific company is named, count real
            # bearish events tied to THAT company (same tickers/headline
            # match get_symbol_context already uses) so the score can
            # actually differ between two different stocks.
            entity_bearish = 0
            if entities.get("companies"):
                _sym = entities["companies"][0].upper()
                entity_bearish = sum(
                    1 for e in (mie_state.get("top_events") or [])
                    if e.get("sentiment") == "bearish" and (
                        _sym in [str(t).upper() for t in (e.get("tickers") or [])]
                        or _sym in (str(e.get("headline", "")) + " " + str(e.get("one_liner") or "")).upper()
                    )
                )
            risk_val = score_risk(float(_vix_level or 0), bearish_high_urgency, lagging, entity_bearish)
            entity_note = f" · {entity_bearish} bearish events specific to {entities['companies'][0]}" if entity_bearish else ""
            block = (
                f"Computed Risk Score (real, deterministic formula): {risk_val}/100 · "
                f"India VIX {_vix_level or 'n/a'} · {bearish_high_urgency} high-urgency bearish market events · "
                f"weakest sectors: {', '.join(s['name'] for s in lagging) or 'none'}{entity_note}"
            )
            extra_context = (extra_context + "\n\n" + block) if extra_context else block
        except Exception:
            pass

    # Macro — real live index levels beyond just VIX (inflation/rate/GDP/
    # crude/rupee-shaped queries previously got no market-level grounding
    # at all).
    if _MACRO_TRIGGER.search(query):
        try:
            from app.services.market_data import get_extended_indices
            idx_rows = await get_extended_indices()
            want = [i for i in idx_rows if i.get("name") in ("NIFTY 50", "SENSEX", "BANK NIFTY", "INDIA VIX")]
            if want:
                block = "Macro indices (real, live): " + "; ".join(
                    f"{i['name']} {i['value']} ({i['change']})" for i in want
                )
                extra_context = (extra_context + "\n\n" + block) if extra_context else block
        except Exception:
            pass

    # Company Research — real Intelligence Graph context + real filed
    # announcements for a bare single-company query that isn't already a
    # buy/sell/hold/compare decision (those already get valuation/events/news).
    if intent == "general" and not intent_data.get("is_comparison") and len(entities.get("companies") or []) == 1:
        try:
            from app.services.intelligence.engine import get_symbol_context
            from app.services.company_announcements_service import get_recent_announcements
            sym = entities["companies"][0]
            ctx, ann = await asyncio.gather(
                get_symbol_context(sym), get_recent_announcements(sym, limit=5),
                return_exceptions=True,
            )
            if isinstance(ctx, dict) and ctx.get("story"):
                # story is a dict ({"text": ..., "mood": ..., ...}) from
                # read_story(), not a plain string — pull the text field.
                story_val = ctx["story"]
                story_text = story_val.get("text") if isinstance(story_val, dict) else str(story_val)
                if story_text:
                    block = f"Company context for {sym} (real, from Intelligence Graph): {story_text[:220]}"
                    if ctx.get("market_mood"):
                        block += f" · Mood: {ctx['market_mood']}"
                    extra_context = (extra_context + "\n\n" + block) if extra_context else block
            if isinstance(ann, list) and ann:
                ann_txt = "; ".join(
                    f"{a.get('subject', '')} ({a.get('category', '')}, {a.get('announcement_date', '')})"
                    for a in ann[:5]
                )
                block2 = f"Recent real filed announcements for {sym}: {ann_txt}"
                extra_context = (extra_context + "\n\n" + block2) if extra_context else block2
        except Exception:
            pass

    # Financial Results (post-results, not phrased as a reaction/preview) —
    # real filed results announcements, not an LLM guessing at numbers.
    if _RESULTS_TRIGGER.search(query):
        try:
            from app.services.company_announcements_service import get_recent_announcements
            for sym in (entities.get("companies") or [])[:2]:
                ann = await get_recent_announcements(sym, limit=8)
                results_ann = [
                    a for a in ann
                    if any(k in (a.get("category", "") or "").lower() for k in ("result", "financial"))
                ]
                if results_ann:
                    lines = "; ".join(
                        f"{a['subject']} ({a['announcement_date']})" for a in results_ann[:3]
                    )
                    block = f"Real filed results announcements for {sym}: {lines}"
                    extra_context = (extra_context + "\n\n" + block) if extra_context else block
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
            "degraded": True,  # generic template, not real analysis — surfaced to the frontend so it doesn't present this as a completed AI verdict
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

    if intent == "list_picks":
        # "Top N Picks Identified" isn't a research-outlook rating — it's a
        # different response shape entirely (a ranked list, not a verdict on
        # one entity). Forcing it through the 8-label enum (pre-existing
        # behavior) or reconciling it against the Verdict Engine would
        # silently destroy it. Leave it exactly as the AI wrote it.

        # AI Recommendation Engine (Phase 2) — real, sector/theme-matched
        # candidates from the Opportunity Engine, cross-referenced against
        # the real NSE universe, replace the AI's own free-invented list.
        _engine_picks: list[dict] = []
        try:
            from app.services.ai_recommendation_engine import compute_recommendations
            # _words() only filters len>=2 — fine for the OR-based event/news
            # search it was built for, but the Opportunity Engine's title
            # match is a plain substring test, so short stopwords produce
            # false positives (e.g. "me" from "give ME top 5..." matches
            # inside every "X Invest-ME-nt Opportunity" title regardless of
            # actual relevance — caught live: a "banking stocks" query
            # returned Automotive names via a "Defence Investment
            # Opportunity" row). Drop stopwords and anything under 4 chars
            # before it reaches that search.
            _pick_stopwords = {
                "give", "me", "the", "top", "best", "and", "for", "which", "what",
                "are", "should", "recommend", "picks", "pick", "stock", "stocks",
                "companies", "shares", "invest", "buy", "list", "some", "with",
            }
            _pick_terms = (entities.get("sectors") or []) + [
                w for w in _words(query) if w not in _pick_stopwords and len(w) >= 4
            ]
            _engine_picks = await compute_recommendations(db, _pick_terms, intent_data.get("pick_count") or 3)
        except Exception:
            _engine_picks = []

        investment_verdict = {
            **_verdict_raw,
            "confidence": _final_confidence,
            "risk_level": _verdict_risk,
            "suitable_for": _suitable_for(_verdict_horizon, _verdict_risk),
            "verdict_basis": "real_screener" if _engine_picks else "ai_only_no_real_match",
            "engine_verdict": None,
            "engine_recommendations": _engine_picks,
            # Real picks take precedence when the screener found any; the
            # AI's own list is kept only as a fallback when no real
            # sector/theme opportunity matched the query at all.
            "top_picks": [c["symbol"] for c in _engine_picks] or _verdict_raw.get("top_picks", []),
        }
    else:
        _ai_rating = _normalize_outlook(
            _verdict_raw.get("rating", ""), _verdict_raw.get("direction", "neutral"),
            _verdict_raw.get("confidence", _final_confidence), _verdict_raw.get("opportunity_score", 50),
        )

        # Investment Verdict Engine (Phase 2) — compute the rating from real
        # signals (MIE direction, the blended real confidence score, live VIX,
        # and a real Opportunity Engine score when the named entity/sector has
        # one) rather than trusting the AI's free-text rating outright. Close
        # agreement keeps the AI's label (it may carry stock-specific nuance
        # the formula can't see); a real disagreement is overridden by the
        # computed verdict, since real data wins over an unconstrained guess.
        _engine_verdict = None
        try:
            from app.services.investment_verdict_engine import compute_investment_verdict, _OUTLOOK_LABELS as _VE_LABELS
            _opp_score_for_verdict = None
            try:
                _verdict_terms = (entities.get("companies") or []) + (entities.get("sectors") or [])
                if _verdict_terms:
                    from app.services.opportunity_service import OpportunityService
                    _opp_hits = await OpportunityService(db).list_by_sector_or_theme(_verdict_terms[:4], limit=1)
                    if _opp_hits:
                        _opp_score_for_verdict = _opp_hits[0]["opportunity_score"]
            except Exception:
                pass
            _engine_verdict = compute_investment_verdict(
                direction=mie_state.get("signals", {}).get("direction", "sideways"),
                confidence_score=_final_confidence,
                opportunity_score=_opp_score_for_verdict,
                vix_level=_vix_level,
            )
            _tier_ai = _VE_LABELS.index(_ai_rating) if _ai_rating in _VE_LABELS else 4
            _tier_engine = _engine_verdict["tier"]
            if abs(_tier_ai - _tier_engine) <= 1:
                _final_rating, _verdict_basis = _ai_rating, "ai_aligned_with_data"
            else:
                _final_rating, _verdict_basis = _engine_verdict["rating"], "data_overridden_ai"
        except Exception:
            _final_rating, _verdict_basis = _ai_rating, "ai_only_engine_unavailable"

        investment_verdict = {
            **_verdict_raw,
            "rating": _final_rating,
            # Same canonical-confidence fix already applied on the frontend
            # this session (displayConfidence()) — investment_verdict.confidence
            # used to keep whatever number the AI itself wrote (or the
            # degraded-template default), which could silently disagree with
            # confidence_data.score. Force it to the one real blended number.
            "confidence": _final_confidence,
            "risk_level": _verdict_risk,
            "suitable_for": _suitable_for(_verdict_horizon, _verdict_risk),
            "verdict_basis": _verdict_basis,
            "engine_verdict": _engine_verdict,
        }

    # Decision Engine (Phase 2) — for a genuine two-entity decision (both a
    # holding AND a target actually named), compute which side the real data
    # favors: two independent Investment Verdict Engine reads (same
    # market-wide direction/confidence/VIX, each entity's own real
    # Opportunity Engine score when one matches) plus a real P/E comparison
    # when the valuation trigger already fetched both sides. No LLM call.
    if intent_data["is_comparison"] and decision_intelligence is not None:
        try:
            from app.services.decision_engine import compute_decision
            from app.services.opportunity_service import OpportunityService
            _sym_a = next(iter(_match_companies((intent_data.get("holding") or "").lower())), None)
            _sym_b = next(iter(_match_companies((intent_data.get("target") or "").lower())), None)
            if _sym_a and _sym_b:
                async def _opp_for(sym: str) -> float | None:
                    hits = await OpportunityService(db).list_by_sector_or_theme([sym], limit=1)
                    return hits[0]["opportunity_score"] if hits else None
                _opp_a, _opp_b = await asyncio.gather(_opp_for(_sym_a), _opp_for(_sym_b))
                decision_intelligence["engine_recommendation"] = compute_decision(
                    entity_a_symbol=_sym_a, entity_b_symbol=_sym_b,
                    direction=mie_state.get("signals", {}).get("direction", "sideways"),
                    confidence_score=_final_confidence, vix_level=_vix_level,
                    opportunity_score_a=_opp_a, opportunity_score_b=_opp_b,
                    valuation_a=_valuation_map.get(_sym_a), valuation_b=_valuation_map.get(_sym_b),
                )
        except Exception:
            pass

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

    # Surfaced to the frontend so a failed LLM synthesis renders as an honest
    # "couldn't complete analysis" state instead of a confident-looking report
    # built entirely from generic fallback templates (main answer and/or the
    # separately-generated scenarios/checklist can each degrade independently).
    _synthesis_incomplete = bool(ai.get("degraded")) or bool(isinstance(scenarios, dict) and scenarios.get("degraded"))

    result = {
        "query": query,
        "synthesis_incomplete": _synthesis_incomplete,
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

    if not _synthesis_incomplete:
        # Don't cache a degraded result for 30 minutes — a provider that
        # recovers moments later (or a different one in the fallback chain)
        # should get a real answer on the next identical query, not the same
        # fabricated report.
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
