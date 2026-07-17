"""AI Model Router — tier lookup, no hardcoded per-call model selection."""
from __future__ import annotations

from app.ai_pipeline.registry import MODEL_TIER_REGISTRY


async def call(tier_key: str, prompt: str, system: str = "", max_tokens: int | None = None) -> str:
    tier = MODEL_TIER_REGISTRY.get(tier_key)
    if tier is None:
        raise ValueError(f"Unknown model tier: '{tier_key}'. Registered: {MODEL_TIER_REGISTRY.keys()}")
    return await tier.call(prompt, system, max_tokens or tier.max_tokens_default)
