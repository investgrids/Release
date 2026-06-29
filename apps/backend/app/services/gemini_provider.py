"""
GeminiProvider — Google Gemini API.
Uses Gemini's OpenAI-compatibility endpoint (v1beta/openai).
"""
from __future__ import annotations

from app.services.deepseek_provider import DeepSeekProvider


class GeminiProvider(DeepSeekProvider):
    """
    Google Gemini provider via its OpenAI-compatible endpoint.
    Requires GEMINI_API_KEY in env.
    """

    def __init__(self, api_key: str) -> None:
        super().__init__(
            api_key=api_key,
            base_url="https://generativelanguage.googleapis.com/v1beta/openai",
            model="gemini-2.0-flash",
        )
