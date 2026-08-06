"""
Market Pulse detection/classification/prompt-building — shared by both AI
Search pipelines (V2: ai_search_service.py, V3: this package) — extracted
verbatim from ai_search_service.py during P5 Stage 1 (2026-08-06), zero
behavior change.

Note: the actual Market Pulse SEARCH orchestration (_run_market_pulse_search
in ai_search_service.py) deliberately stays in V2 — its own docstring
confirms Market Pulse "stays V2's exact mechanism," not an oversight — this
module only holds the detection/classification/prompt-building pieces both
pipelines share.
"""
from __future__ import annotations

import re

import structlog

from app.services.ai_service import _call_with_fallback

log = structlog.get_logger(__name__)

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
        raw = await _call_with_fallback(f'Query: "{query}"', _MARKET_PULSE_CLASSIFY_SYSTEM, max_tokens=5, priority="interactive")
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
