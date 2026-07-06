"""
Multi-Horizon Investment Outlook Service.

Generates structured AI analysis across 5 investment horizons for any context:
  - Immediate  (1–7 Days)
  - Short Term  (1–3 Months)
  - Medium Term (3–12 Months)
  - Long Term   (1–3 Years)
  - Structural  (3–5+ Years)

Callable from any API module. Caches results 30 min in Redis, falls back to
in-process cache. All AI calls route through _call_with_fallback (free-only).
"""
from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Literal

import structlog

from app.services.ai_service import _call_with_fallback
from app.core.redis import cache_get, cache_set

log = structlog.get_logger(__name__)

# ── In-process fallback cache ─────────────────────────────────────────────────
_CACHE: dict[str, tuple[float, Any]] = {}
_TTL = 1800  # 30 min

ContextType = Literal["stock", "event", "opportunity", "story", "ripple", "query"]

_SYSTEM = (
    "You are a senior Indian equity market analyst at an institutional fund. "
    "Generate precise multi-horizon investment intelligence for professional investors. "
    "Each horizon must have DIFFERENT reasoning, catalysts, risks, and confidence. "
    "Respond with valid JSON only. No markdown fences. No commentary."
)


def _cache_key(context_type: str, context_id: str) -> str:
    raw = f"mh:{context_type}:{context_id}"
    return hashlib.md5(raw.encode()).hexdigest()


def _build_prompt(
    context_type: ContextType,
    title: str,
    symbol: str | None,
    context: str,
    sectors: list[str],
) -> str:
    symbol_line = f"Symbol: {symbol} (NSE)\n" if symbol else ""
    sectors_line = f"Sectors: {', '.join(sectors)}\n" if sectors else ""
    ctx_label = {
        "stock":       "Stock Analysis",
        "event":       "Market Event",
        "opportunity": "Investment Opportunity",
        "story":       "Market Theme",
        "ripple":      "Ripple Intelligence",
        "query":       "Investment Query",
    }.get(context_type, "Market Analysis")

    return f"""Type: {ctx_label}
Title: {title}
{symbol_line}{sectors_line}Context: {context}

Generate Multi-Horizon Investment Outlook. Return ONLY this JSON (no fences):
{{
  "horizons": [
    {{
      "id": "immediate",
      "label": "Immediate",
      "range": "1–7 Days",
      "icon": "⚡",
      "outlook": "Positive",
      "outlook_level": 3,
      "confidence": 74,
      "reason": "One specific sentence about immediate market reaction.",
      "catalysts": ["Specific near-term catalyst 1", "Specific near-term catalyst 2"],
      "risks": ["Specific near-term risk 1", "Specific near-term risk 2"]
    }},
    {{
      "id": "short_term",
      "label": "Short Term",
      "range": "1–3 Months",
      "icon": "📈",
      "outlook": "Strong Positive",
      "outlook_level": 4,
      "confidence": 81,
      "reason": "One specific sentence about 1–3 month trajectory.",
      "catalysts": ["Quarterly catalyst 1", "Order/revenue catalyst 2"],
      "risks": ["Execution risk", "Market timing risk"]
    }},
    {{
      "id": "medium_term",
      "label": "Medium Term",
      "range": "3–12 Months",
      "icon": "📊",
      "outlook": "Positive",
      "outlook_level": 3,
      "confidence": 79,
      "reason": "One specific sentence about the medium-term business trajectory.",
      "catalysts": ["Revenue growth catalyst", "Margin expansion driver"],
      "risks": ["Competitive risk", "Macro risk"]
    }},
    {{
      "id": "long_term",
      "label": "Long Term",
      "range": "1–3 Years",
      "icon": "🚀",
      "outlook": "Very Strong",
      "outlook_level": 4,
      "confidence": 86,
      "reason": "One specific sentence about 1–3 year business expansion.",
      "catalysts": ["Capex cycle catalyst", "Market share catalyst"],
      "risks": ["Structural competition risk", "Capital allocation risk"]
    }},
    {{
      "id": "structural",
      "label": "Structural Outlook",
      "range": "3–5+ Years",
      "icon": "🌍",
      "outlook": "Exceptional",
      "outlook_level": 5,
      "confidence": 88,
      "reason": "One specific sentence about structural/demographic tailwinds.",
      "catalysts": ["Decade-long structural driver 1", "Mega-trend driver 2"],
      "risks": ["Regulatory disruption risk", "Technology substitution risk"]
    }}
  ]
}}

OUTLOOK VALUES: Use exactly one of: "Exceptional", "Very Strong", "Strong Positive",
"Positive", "Neutral", "Cautious", "Negative". No other values.

OUTLOOK_LEVEL: 5=Exceptional, 4=Very Strong/Strong Positive, 3=Positive,
2=Neutral, 1=Cautious, 0=Negative. Match level to outlook exactly.

CRITICAL: Each horizon must have genuinely DIFFERENT reasoning. Use real Indian
market context: actual rupee amounts, NSE/BSE references, sector-specific dynamics.
SYMBOL hints: {symbol or 'N/A'} — {', '.join(sectors) or 'Indian equity market'}."""


def _parse_horizons(raw: str) -> list[dict] | None:
    try:
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        data = json.loads(raw)
        horizons = data.get("horizons", [])
        if len(horizons) != 5:
            return None
        for h in horizons:
            if "id" not in h or "outlook" not in h or "confidence" not in h:
                return None
        return horizons
    except Exception:
        return None


def _fallback_horizons(title: str) -> list[dict]:
    """Deterministic fallback when AI is unavailable."""
    return [
        {
            "id": "immediate", "label": "Immediate", "range": "1–7 Days",
            "icon": "⚡", "outlook": "Neutral", "outlook_level": 2,
            "confidence": 55,
            "reason": f"Short-term direction for {title} depends on upcoming market catalysts and sentiment.",
            "catalysts": ["Upcoming results or announcements", "Market sentiment"],
            "risks": ["Profit booking", "Global volatility"],
        },
        {
            "id": "short_term", "label": "Short Term", "range": "1–3 Months",
            "icon": "📈", "outlook": "Positive", "outlook_level": 3,
            "confidence": 65,
            "reason": f"Order book and revenue pipeline for {title} support a constructive near-term outlook.",
            "catalysts": ["Quarterly earnings", "Government or sector catalysts"],
            "risks": ["Execution delays", "Input cost pressure"],
        },
        {
            "id": "medium_term", "label": "Medium Term", "range": "3–12 Months",
            "icon": "📊", "outlook": "Strong Positive", "outlook_level": 4,
            "confidence": 72,
            "reason": f"Revenue visibility and margin improvement position {title} positively over 3–12 months.",
            "catalysts": ["Revenue growth", "Margin expansion"],
            "risks": ["Competition", "Regulatory changes"],
        },
        {
            "id": "long_term", "label": "Long Term", "range": "1–3 Years",
            "icon": "🚀", "outlook": "Very Strong", "outlook_level": 4,
            "confidence": 78,
            "reason": f"Structural growth drivers across the sector support a strong 1–3 year outlook for {title}.",
            "catalysts": ["Business expansion", "Industry leadership"],
            "risks": ["Capital allocation", "Management execution"],
        },
        {
            "id": "structural", "label": "Structural Outlook", "range": "3–5+ Years",
            "icon": "🌍", "outlook": "Exceptional", "outlook_level": 5,
            "confidence": 82,
            "reason": f"Long-term demand tailwinds — infrastructure, digitisation, defence modernisation — support exceptional structural upside.",
            "catalysts": ["Structural industry growth", "Demographic dividend"],
            "risks": ["Technological disruption", "Policy reversals"],
        },
    ]


async def generate_multi_horizon(
    context_type: ContextType,
    title: str,
    symbol: str | None = None,
    context: str = "",
    sectors: list[str] | None = None,
    context_id: str | None = None,
) -> list[dict]:
    """
    Generate 5-horizon investment outlook for any context.

    Returns list of 5 dicts, each containing:
      id, label, range, icon, outlook, outlook_level (0-5),
      confidence (0-100), reason, catalysts, risks
    """
    sectors = sectors or []
    ctx_id = context_id or hashlib.md5(f"{context_type}:{title}:{symbol}".encode()).hexdigest()
    cache_key = _cache_key(context_type, ctx_id)

    # 1. In-process cache
    hit = _CACHE.get(cache_key)
    if hit and time.time() - hit[0] < _TTL:
        log.debug("multi_horizon.cache.hit.local", key=cache_key)
        return hit[1]

    # 2. Redis cache
    try:
        redis_hit = await cache_get(cache_key)
        if redis_hit:
            horizons = redis_hit if isinstance(redis_hit, list) else redis_hit.get("horizons", [])
            _CACHE[cache_key] = (time.time(), horizons)
            log.debug("multi_horizon.cache.hit.redis", key=cache_key)
            return horizons
    except Exception:
        pass

    # 3. Generate via AI
    prompt = _build_prompt(context_type, title, symbol, context, sectors)
    try:
        raw = await _call_with_fallback(prompt=prompt, system=_SYSTEM, max_tokens=900)
        horizons = _parse_horizons(raw) if raw else None
    except Exception as exc:
        log.warning("multi_horizon.ai_error", exc=str(exc))
        horizons = None

    if horizons is None:
        log.warning("multi_horizon.fallback", ctx=context_type, title=title)
        horizons = _fallback_horizons(title)

    # 4. Store in caches
    _CACHE[cache_key] = (time.time(), horizons)
    try:
        await cache_set(cache_key, horizons, _TTL)
    except Exception:
        pass

    return horizons
