"""
OpenAIProvider — uses the OpenAI API (GPT-4o).
Shares the same request format as DeepSeek (OpenAI-compatible).
"""
from __future__ import annotations

from typing import Any, Dict, List

from app.services.deepseek_provider import DeepSeekProvider


class OpenAIProvider(DeepSeekProvider):
    """
    OpenAI GPT-4o provider.
    Inherits all DeepSeek logic since they share the same API contract.
    Only the base_url, model, and api_key differ.
    """

    def __init__(self, api_key: str) -> None:
        super().__init__(
            api_key=api_key,
            base_url="https://api.openai.com/v1",
            model="gpt-4o-mini",
        )
