"""
AI service — multi-provider free-tier AI with automatic fallback.

Provider chain (fastest/freest first):
  1. OmniRoute local  — pol/gpt-5, pol/claude-sonnet, if/deepseek-r1 (no key, unlimited)
  2. Groq             — llama-3.1-8b-instant, 14,400 req/day free
  3. Cerebras         — llama3.1-8b, 10,000 req/day free, ultra-fast
  4. Gemini           — gemini-2.0-flash, 1,500 req/day / 4M tokens free
  5. OpenRouter       — free models as last-resort fallback

At 50 users the first two providers alone cover >100x the needed capacity.
"""
import httpx
import structlog
from app.core.config import settings
from app.core.redis import cache_get, cache_set

log = structlog.get_logger(__name__)

# ── Provider endpoints ────────────────────────────────────────────────────────
_OR_URL       = "https://openrouter.ai/api/v1/chat/completions"
_GROQ_URL     = "https://api.groq.com/openai/v1/chat/completions"
_CEREBRAS_URL = "https://api.cerebras.ai/v1/chat/completions"
_GEMINI_URL   = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"

# OmniRoute free providers — no API key required, unlimited via Pollinations/Qoder
_OMNIROUTE_MODELS = [
    "pol/gpt-5",              # GPT-5 via Pollinations — free, no key
    "if/deepseek-r1",         # DeepSeek R1 via Qoder — unlimited
    "pol/claude-sonnet-4-5",  # Claude Sonnet 4.5 via Pollinations — free
    "if/qwen3-coder-plus",    # Qwen3 Coder via Qoder — unlimited
    "pol/gemini",             # Gemini via Pollinations — free
]

# Groq: verified live 2026-06-30 — 9 text models, ~13.2M tokens/day combined
_GROQ_MODELS = [
    "llama-3.1-8b-instant",                      # 14,400 req/day, 6K TPM  — primary workhorse
    "qwen/qwen3-32b",                            # 1,000 req/day, 6K TPM
    "qwen/qwen3.6-27b",                          # 1,000 req/day, 8K TPM
    "meta-llama/llama-4-scout-17b-16e-instruct", # 1,000 req/day, 30K TPM  — highest TPM
    "llama-3.3-70b-versatile",                   # 1,000 req/day, 12K TPM
    "openai/gpt-oss-20b",                        # 1,000 req/day, 8K TPM
    "openai/gpt-oss-120b",                       # 1,000 req/day, 8K TPM   — highest quality
    "groq/compound-mini",                        # 250 req/day,  70K TPM
    "groq/compound",                             # 250 req/day,  70K TPM
]

# Cerebras: 10,000 req/day free — fastest inference in the market
_CEREBRAS_MODELS = [
    "llama3.1-8b",
    "llama3.1-70b",
]

# Gemini: 1,500 req/day, 1M–4M tokens/day free
_GEMINI_MODELS = [
    "gemini-2.0-flash",
    "gemini-1.5-flash",
]

# OpenRouter free models — verified live 2026-06-30 via /api/v1/models
# 22 active models × ~50 req/day = ~1,100 req/day = ~770K tokens/day
_OR_FREE_MODELS = [
    # High-quality large models first
    "openai/gpt-oss-120b:free",                              # GPT OSS 120B
    "nvidia/nemotron-3-ultra-550b-a55b:free",                # NVIDIA 550B, 1M ctx
    "nvidia/nemotron-3-super-120b-a12b:free",                # NVIDIA 120B, 1M ctx
    "qwen/qwen3-coder:free",                                 # Qwen3 Coder, 1M ctx
    "meta-llama/llama-3.3-70b-instruct:free",               # Llama 70B
    "qwen/qwen3-next-80b-a3b-instruct:free",                # Qwen3 80B
    "nousresearch/hermes-3-llama-3.1-405b:free",            # Hermes 405B
    "openai/gpt-oss-20b:free",                              # GPT OSS 20B
    # Google Gemma
    "google/gemma-4-31b-it:free",                           # Gemma 4 31B, 262K ctx
    "google/gemma-4-26b-a4b-it:free",                       # Gemma 4 26B
    # Poolside
    "poolside/laguna-m.1:free",                             # Laguna M.1, 262K ctx
    "poolside/laguna-xs.2:free",                            # Laguna XS.2
    # NVIDIA smaller
    "nvidia/nemotron-3-nano-30b-a3b:free",                  # Nemotron 30B
    "nvidia/nemotron-nano-12b-v2-vl:free",                  # Nemotron 12B
    "nvidia/nemotron-nano-9b-v2:free",                      # Nemotron 9B
    # Smaller / fast
    "meta-llama/llama-3.2-3b-instruct:free",               # Llama 3B fast
    "cohere/north-mini-code:free",                          # Cohere North Mini
    "cognitivecomputations/dolphin-mistral-24b-venice-edition:free",
    "liquid/lfm-2.5-1.2b-thinking:free",                   # Liquid thinking
    "liquid/lfm-2.5-1.2b-instruct:free",                   # Liquid instruct
    "nvidia/nemotron-3.5-content-safety:free",
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
]

async def _cached_async(key: str, ttl: int = 900) -> str | None:
    return await cache_get(key)


async def _store_async(key: str, value: str, ttl: int = 900) -> None:
    await cache_set(key, value, ttl)


async def _call_provider(
    base_url: str,
    api_key: str,
    model: str,
    prompt: str,
    system: str = "",
    max_tokens: int = 200,
    extra_headers: dict | None = None,
) -> str:
    """Generic OpenAI-compatible call. Returns '' on any failure or rate-limit."""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    headers = {"Content-Type": "application/json", **(extra_headers or {})}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.4,
    }
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(base_url, json=payload, headers=headers)
            if r.status_code in (429, 402, 503, 529):
                log.warning("ai.rate_limited", model=model, status=r.status_code)
                return ""
            r.raise_for_status()
            data = r.json()
            if "error" in data:
                log.warning("ai.api_error", model=model, err=str(data["error"])[:120])
                return ""
            content = data["choices"][0]["message"]["content"]
            return content.strip() if content else ""
    except Exception as exc:
        log.warning("ai.exception", model=model, exc=str(exc)[:120])
        return ""


async def _call_with_fallback(
    prompt: str,
    system: str = "",
    max_tokens: int = 200,
) -> str:
    """
    Try providers in order until one returns a non-empty response.
    Providers with no URL/key configured are skipped silently.
    """
    # 1. OmniRoute local — free providers, no key, effectively unlimited
    if settings.omniroute_url:
        chat_url = f"{settings.omniroute_url.rstrip('/')}/chat/completions"
        for model in _OMNIROUTE_MODELS:
            result = await _call_provider(chat_url, "", model, prompt, system, max_tokens)
            if result:
                log.info("ai.success", provider="omniroute", model=model)
                return result

    # 2. Groq — fastest direct inference, 14,400 req/day free
    if settings.groq_api_key:
        for model in _GROQ_MODELS:
            result = await _call_provider(_GROQ_URL, settings.groq_api_key, model, prompt, system, max_tokens)
            if result:
                log.info("ai.success", provider="groq", model=model)
                return result

    # 3. Cerebras — ultra-fast, 10K req/day free
    if settings.cerebras_api_key:
        for model in _CEREBRAS_MODELS:
            result = await _call_provider(_CEREBRAS_URL, settings.cerebras_api_key, model, prompt, system, max_tokens)
            if result:
                log.info("ai.success", provider="cerebras", model=model)
                return result

    # 4. Gemini — 1M–4M tokens/day free
    if settings.gemini_api_key:
        for model in _GEMINI_MODELS:
            result = await _call_provider(_GEMINI_URL, settings.gemini_api_key, model, prompt, system, max_tokens)
            if result:
                log.info("ai.success", provider="gemini", model=model)
                return result

    # 5. OpenRouter free models — aggregate fallback
    if settings.openrouter_api_key:
        or_headers = {
            "HTTP-Referer": "https://investgrids.com",
            "X-Title": "InvestGrids Market Intelligence",
        }
        for model in _OR_FREE_MODELS:
            result = await _call_provider(_OR_URL, settings.openrouter_api_key, model, prompt, system, max_tokens, or_headers)
            if result:
                log.info("ai.success", provider="openrouter", model=model)
                return result
            log.warning("ai.skip", provider="openrouter", model=model)

    log.error("ai.all_providers_failed")
    return ""


async def get_market_summary(indices: list[dict], events: list[dict]) -> str:
    """
    Generate a 2-sentence live market summary for the dashboard.
    Cached for 15 minutes.
    """
    cache_key = "dashboard:ai_summary"
    hit = await _cached_async(cache_key, 900)
    if hit:
        return hit

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

    result = await _call_with_fallback(prompt, system, max_tokens=120)

    if not result:
        result = (
            "Indian markets are showing mixed momentum across major indices. "
            "Monitor key sector developments and macro policy signals for near-term direction."
        )

    await _store_async(cache_key, result)
    return result


async def generate_ripple_graph(
    title: str,
    summary: str,
    event_type: str = "macro",
    impact_score: float = 7.0,
    companies: list | None = None,
    sectors: list | None = None,
) -> dict:
    """
    Generate a comprehensive ripple effect dependency graph for a market event.
    Returns {nodes, edges, insights} dict or {} on failure.
    Cached 1 hour — ripple graphs are stable between refreshes.
    """
    cache_key = f"ripple_graph:{hash(title[:100])}"
    hit = await _cached_async(cache_key, 3600)
    if hit:
        return hit

    companies_str = ", ".join([
        c.get("symbol", c.get("name", "")) for c in (companies or [])[:10]
        if c.get("symbol") or c.get("name")
    ]) or "N/A"
    sectors_str = ", ".join([
        s.get("sector", "") for s in (sectors or [])[:8] if s.get("sector")
    ]) or "N/A"

    system = (
        "You are a senior Indian equity market analyst specializing in dependency and ripple effect analysis. "
        "Generate precise, factual JSON ripple graphs focused on the Indian stock market. "
        "Return ONLY valid JSON, no markdown, no explanation text."
    )

    prompt = (
        f"Analyze this market event and generate a complete ripple dependency graph.\n\n"
        f"Event: {title}\n"
        f"Summary: {summary[:400]}\n"
        f"Type: {event_type}\n"
        f"Impact Score: {impact_score:.1f}/10\n"
        f"Related Companies: {companies_str}\n"
        f"Related Sectors: {sectors_str}\n\n"
        "Return ONLY valid JSON with this structure:\n"
        "{\n"
        '  "nodes": [\n'
        '    {"id":"event_center","label":"<event title truncated>","type":"event","impact":"mixed",'
        f'"impact_strength":{impact_score/10:.1f},"depth":0,"icon":"event","change_direction":"neutral","subtitle":"Impact {impact_score:.0f}/10"}},\n'
        '    {"id":"unique_id","label":"Display Name","type":"commodity","impact":"positive",'
        '"impact_strength":0.85,"depth":1,"icon":"oil","change_direction":"up","subtitle":"+6.2%"}\n'
        "    // 18-24 more nodes across depths 1-4\n"
        "  ],\n"
        '  "edges": [\n'
        '    {"source":"event_center","target":"node_id","relationship":"causes",'
        '"impact_strength":0.9,"confidence":0.92,"explanation":"one sentence","time_horizon":"immediate"}\n'
        "    // 22-32 more edges\n"
        "  ],\n"
        '  "insights": {\n'
        '    "summary":"2-3 sentence executive summary",\n'
        '    "key_drivers":["driver1","driver2","driver3"],\n'
        '    "ripple_strength":{"direct":"High","indirect":"Medium","long_term":"Medium"},\n'
        '    "market_volatility":"High","inflation_risk":"Elevated","growth_impact":"Negative",\n'
        '    "beneficiaries":[{"name":"...","ticker":"NSE_SYMBOL","confidence":0.92,"impact":"Very Positive","reason":"..."}],\n'
        '    "losers":[{"name":"...","ticker":"NSE_SYMBOL","confidence":0.88,"impact":"Very Negative","reason":"..."}],\n'
        '    "impacted_commodities":[{"name":"...","current_price":"...","change_pct":6.21,"positive":true}],\n'
        '    "impacted_sectors":[{"name":"...","strength":"Very High","positive":true}],\n'
        '    "ripple_timeline":[\n'
        '      {"period":"0-7 Days","description":"..."},\n'
        '      {"period":"1-4 Weeks","description":"..."},\n'
        '      {"period":"1-3 Months","description":"..."},\n'
        '      {"period":"3-6 Months","description":"..."}\n'
        "    ]\n"
        "  }\n"
        "}\n\n"
        "Node types: event, commodity, currency, sector, company, policy, indicator\n"
        "Relationships: causes, hurts, benefits, influences, supports, risk, opportunity\n"
        "Time horizons: immediate, short_term, medium_term, long_term\n"
        "Depths: 0=event_center, 1=direct(0-7d), 2=secondary(1-4w), 3=tertiary(1-3m), 4=long-term(3-6m)\n"
        "Generate 20-25 nodes and 25-35 edges. Focus on Indian market context and NSE-listed companies."
    )

    raw = await _call_with_fallback(prompt, system, max_tokens=4000)
    if not raw:
        return {}

    try:
        import json, re
        clean = raw.strip()
        if clean.startswith("```"):
            clean = re.sub(r"^```(?:json)?\s*", "", clean)
            clean = re.sub(r"\s*```$", "", clean).strip()
        # Remove JS-style comments before parsing
        clean = re.sub(r"\s*//[^\n]*", "", clean)
        result = json.loads(clean)
        await _store_async(cache_key, result)
        return result
    except Exception:
        import json, re
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            try:
                clean2 = re.sub(r"\s*//[^\n]*", "", m.group())
                result = json.loads(clean2)
                await _store_async(cache_key, result)
                return result
            except Exception:
                pass
        log.warning("ripple.ai.parse_failed", raw_len=len(raw))
        return {}


async def get_event_ai_summary(title: str, description: str) -> dict:
    """
    Generate AI bullets for a market event.
    Returns {summary, why_it_matters, key_bullets, risk_factors, opportunities}
    """
    cache_key = f"event_ai:{hash(title)}"
    hit = await _cached_async(cache_key, 3600)  # 1-hour cache
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

    raw = await _call_with_fallback(prompt, max_tokens=600)
    if not raw:
        return {}

    try:
        import json, re
        clean = raw.strip()
        if clean.startswith("```"):
            clean = re.sub(r"^```(?:json)?\s*", "", clean)
            clean = re.sub(r"\s*```$", "", clean).strip()
        result = json.loads(clean)
        await _store_async(cache_key, result)
        return result
    except Exception:
        # Try extracting first JSON object from response
        import json, re
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except Exception:
                pass
        return {}
