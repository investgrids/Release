"""
OpenRouterProvider — uses OpenRouter's OpenAI-compatible API.
Supports any model available on openrouter.ai.
Default model: deepseek/deepseek-chat-v3-0324:free (free tier).
"""
from __future__ import annotations

from app.core.config import settings
from app.services.deepseek_provider import DeepSeekProvider


class OpenRouterProvider(DeepSeekProvider):
    """
    OpenRouter provider inherits the full DeepSeek/OpenAI-compatible
    implementation. Only the base_url, model, and API key differ.
    OpenRouter forwards requests to the underlying model.
    """

    def __init__(self, api_key: str, base_url: str, model: str) -> None:
        super().__init__(api_key=api_key, base_url=base_url, model=model)
        # OpenRouter requires these headers for attribution/rate-limiting
        self._headers.update({
            "HTTP-Referer": settings.frontend_url or "https://investgrids.com",
            "X-Title": "InvestGrids Market Intelligence",
        })
