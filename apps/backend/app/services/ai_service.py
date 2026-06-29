"""
AI service — wraps OpenRouter free-tier API.
Default model: deepseek/deepseek-chat-v3-0324:free (free, no rate-limit key required).
Falls back gracefully if the key is absent or the call fails.
"""
import asyncio
import time
import httpx
from app.core.config import settings

_BASE_URL = "https://openrouter.ai/api/v1/chat/completions"

# Simple in-process cache: {key: (timestamp, value)}
_cache: dict = {}


def _cached(key: str, ttl: int = 900):
    entry = _cache.get(key)
    if entry and time.time() - entry[0] < ttl:
        return entry[1]
    return None


def _store(key: str, value: str) -> None:
    _cache[key] = (time.time(), value)


async def _call_openrouter(prompt: str, system: str = "", max_tokens: int = 200) -> str:
    """Single call to OpenRouter. Returns empty string on failure."""
    if not settings.openrouter_api_key:
        return ""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    payload = {
        "model": settings.openrouter_model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.4,
    }
    headers = {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://investgrids.com",
        "X-Title": "InvestGrids Market Intelligence",
    }
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(_BASE_URL, json=payload, headers=headers)
            r.raise_for_status()
            data = r.json()
            return data["choices"][0]["message"]["content"].strip()
    except Exception:
        return ""


async def get_market_summary(indices: list[dict], events: list[dict]) -> str:
    """
    Generate a 2-sentence live market summary for the dashboard.
    Cached for 15 minutes.
    """
    cache_key = "dashboard:ai_summary"
    hit = _cached(cache_key, 900)
    if hit:
        return hit

    # Build compact context so the prompt stays small
    index_lines = [
        f"{idx.get('title', idx.get('name', ''))} {idx.get('value', '')} ({idx.get('change', '')})"
        for idx in (indices or [])[:4]
    ]
    event_lines = [
        f"- {e.get('title', '')} [score {int(e.get('impact_score', 0))}]"
        for e in (events or [])[:4]
    ]

    prompt = (
        "Summarize the current Indian stock market in exactly 2 sentences (max 60 words). "
        "Be factual, concise, and forward-looking. Mention index direction, key sector trends, "
        "and one macro factor.\n\n"
        f"Indices:\n{chr(10).join(index_lines) or 'Data unavailable'}\n\n"
        f"Trending events:\n{chr(10).join(event_lines) or 'None'}"
    )
    system = "You are a professional Indian equity market analyst. Respond only with the 2-sentence summary."

    result = await _call_openrouter(prompt, system, max_tokens=120)

    if not result:
        result = (
            "Indian markets are showing mixed momentum across major indices. "
            "Monitor key sector developments and macro policy signals for near-term direction."
        )

    _store(cache_key, result)
    return result


async def get_event_ai_summary(title: str, description: str) -> dict:
    """
    Generate AI bullets for a market event.
    Returns {summary, why_it_matters, key_bullets, risk_factors, opportunities}
    """
    cache_key = f"event_ai:{hash(title)}"
    hit = _cached(cache_key, 3600)  # 1-hour cache
    if hit:
        return hit

    prompt = (
        f"Analyze this Indian market event:\nTitle: {title}\nDescription: {description[:500]}\n\n"
        "Return a JSON object with these keys:\n"
        '- "summary": one-sentence plain English summary\n'
        '- "why_it_matters": one sentence on market significance\n'
        '- "key_bullets": list of 3 short bullet strings\n'
        '- "risk_factors": list of 2 risk strings\n'
        '- "opportunities": list of 2 opportunity strings\n'
        "Respond with valid JSON only, no markdown fences."
    )

    raw = await _call_openrouter(prompt, max_tokens=400)
    if not raw:
        return {}

    try:
        import json
        result = json.loads(raw)
        _store(cache_key, result)
        return result
    except Exception:
        return {}
