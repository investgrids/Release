"""
Provider factory — returns an AIProvider based on the AI_PROVIDER env variable.
Add new providers here; never instantiate providers directly elsewhere.
"""
from __future__ import annotations

from app.core.config import settings
from app.services.ai_provider import AIProvider


def get_ai_provider() -> AIProvider:
    provider = settings.ai_provider.lower()

    if provider == "openrouter":
        from app.services.openrouter_provider import OpenRouterProvider
        return OpenRouterProvider(
            api_key=settings.openrouter_api_key,
            base_url=settings.openrouter_base_url,
            model=settings.openrouter_model,
        )

    if provider == "openai":
        from app.services.openai_provider import OpenAIProvider
        return OpenAIProvider(api_key=settings.openai_api_key)

    if provider == "gemini":
        from app.services.gemini_provider import GeminiProvider
        return GeminiProvider(api_key=settings.gemini_api_key)

    # Default: DeepSeek
    from app.services.deepseek_provider import DeepSeekProvider
    return DeepSeekProvider(
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
        model=settings.deepseek_model,
    )
