"""
FallbackChainAIProvider — Phase 5F.2a.

event_pipeline.py's enrichment used get_ai_provider() (provider_factory.py),
which returns a SINGLE provider (OpenRouterProvider by current
settings.ai_provider config) with no fallback. Confirmed live: this
codebase's entire event-enrichment pipeline had been failing 100% of
its recent attempts (1,583 events stuck "failed", every one with reason
provider_unavailable) because OpenRouter alone was rate-limited
(reproduced directly: HTTP 429 from openrouter.ai). Every OTHER AI
feature in this codebase already routes through app.services.ai_service.
_call_with_fallback — a resilient cascade across Groq, Cerebras, Groq
fast, OpenRouter, Mistral, Gemini, Cloudflare — and stays healthy under
the exact same rate-limiting that starves a single-provider caller.

This class is a drop-in AIProvider implementation for that cascade,
built by inheriting DeepSeekProvider (whose classify_event/
summarize_event/extract_companies/etc. already have the right
prompts, JSON-parsing, and per-method fallback contracts — see that
file) and overriding ONLY the one low-level primitive every one of
those methods ultimately calls: _chat(). Nothing about the prompts,
fallback values, or method contracts changes — only how the HTTP call
happens. This means:
  - classify_event()'s input/output contract is byte-for-byte
    unchanged (DeepSeekProvider's own implementation, inherited).
  - The fallback ordering/config is _call_with_fallback's own —
    identical to every other AI feature, not a second copy.
  - If every provider in the chain fails, _chat() raises, which every
    inherited method already catches via its own try/except (either
    directly, or through _safe_json_call) and returns ITS designated
    fallback — for classify_event specifically, this is
    {"category": "macro", "confidence": 0.7, "subcategory": "general"},
    the exact value event_pipeline.py's _CLASSIFY_FALLBACK already
    checks for. The existing "degraded stub -> _AIUnavailable -> retry
    with backoff" behavior is therefore fully preserved, just now only
    reached after every provider in the real cascade has failed, not
    after a single one has.
  - _call_with_fallback already logs which provider/model succeeded
    (ai.success) and which failed (ai.all_providers_failed) — no new
    logging needed here.

get_ai_provider()/provider_factory.py is completely untouched — this
is a separate entry point (get_resilient_ai_provider, below), used
only by event_pipeline.py, so no other caller of get_ai_provider()
changes behavior.
"""
from __future__ import annotations

from app.services.deepseek_provider import DeepSeekProvider


class FallbackChainAIProvider(DeepSeekProvider):
    def __init__(self) -> None:
        # DeepSeekProvider.__init__ stores api_key/base_url/model for its
        # own _chat() — irrelevant here since _chat is fully overridden
        # below and never reads them. Empty strings keep attribute
        # access safe without implying they're actually used for auth.
        super().__init__(api_key="", base_url="", model="")

    async def _chat(self, system: str, user: str, max_tokens: int = 2048) -> str:
        from app.services.ai_service import _call_with_fallback
        # priority="background": enrichment is a queued batch job, never
        # a user waiting on a response — it must not compete with
        # interactive AI Search traffic for the same tier slots (see
        # ai_service.py's _tier_slot priority-aware concurrency control).
        result = await _call_with_fallback(user, system, max_tokens=max_tokens, priority="background")
        if not result:
            # Every provider in the cascade failed or returned empty —
            # raising (rather than returning "") is what makes BOTH
            # _safe_json_call's try/except AND the direct-try/except
            # methods (summarize_news, generate_story, generate_radar)
            # correctly fall through to their own designated fallback,
            # not silently treat an empty string as a real answer.
            raise RuntimeError("fallback_chain_provider: every provider failed or returned empty")
        return result


def get_resilient_ai_provider() -> FallbackChainAIProvider:
    """The one entry point event_pipeline.py uses instead of
    get_ai_provider(). A plain function (not a singleton) — DeepSeekProvider
    instances are cheap and stateless beyond the unused credentials, so
    there's no reason to share one across calls."""
    return FallbackChainAIProvider()
