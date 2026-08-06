"""
Standalone trigger regexes, label enums, and lookup constants shared by both
AI Search pipelines (V2: ai_search_service.py, V3: this package) — extracted
verbatim from ai_search_service.py during P5 Stage 1 (2026-08-06), zero
behavior change. See that file's git history for original context/comments
on each constant if needed; kept here unchanged.
"""
from __future__ import annotations

import re

_SECTORS = [
    "railway", "infrastructure", "banking", "it", "technology", "defence", "energy",
    "pharma", "auto", "fmcg", "metals", "realty", "telecom", "power", "finance", "logistics",
]
_POLICIES = [
    "budget", "rbi", "sebi", "gst", "pli", "fdi", "npa", "repo rate",
    "monetary policy", "fiscal policy", "make in india", "pm gati shakti",
]

_STOPWORDS = {
    "what", "whats", "how", "hows", "why", "when", "where", "who", "which",
    "is", "are", "was", "were", "do", "does", "did",
    "the", "a", "an", "and", "or", "for", "with", "from", "into", "this", "that",
    "give", "me", "top", "best", "should", "recommend", "picks", "pick",
    "stock", "stocks", "companies", "shares", "invest", "buy", "list", "some",
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

# ── Research outlook enum (replaces Buy/Sell/Hold advisory language) ──────────
# This is a research platform, not an advisory platform — no recommendation
# language is allowed to reach the response. Enforced twice: the prompt asks
# for one of these exact 8 labels, and _normalize_outlook() (ai_search_service.py)
# forcibly remaps whatever the AI actually returns, so a model ignoring
# instructions (or an older cached response) can never leak "Buy"/"Sell"/"Hold"
# to the UI.
_OUTLOOK_LABELS = [
    "Strongly Constructive", "Constructive", "Positive Outlook",
    "Selectively Constructive", "Neutral", "Cautious",
    "Elevated Risk", "High Uncertainty",
]
