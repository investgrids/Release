"""
Model tier definitions. "medium" maps to the existing multi-provider
fallback chain in `app/services/ai_service.py`. "best_reasoning" calls
NVIDIA NIM on a best-effort basis (`_call_nvidia` owns the hard 2.5s
timeout, 429/5xx classification, and circuit breaker — see
`app/services/ai_service.py`) and falls back to the same chain the instant
NVIDIA doesn't deliver, whether that's a slow response, a rate limit, a
server error, or the circuit breaker skipping the attempt entirely. This
wrapper only needs to know "did I get text back or not" — all the
resilience logic lives at the call site so it's exercised no matter which
tier ends up calling `_call_nvidia`. Later phases add "fast" (no network
call — the regex classifier itself) and "small_refine" (used by the
validator's repair loop) — each a new registration here, no orchestrator
changes required.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Awaitable, Callable

import structlog

from app.ai_pipeline.registry import MODEL_TIER_REGISTRY

log = structlog.get_logger(__name__)


@dataclass(frozen=True)
class ModelTier:
    key: str
    call: Callable[[str, str, int], Awaitable[str]]
    max_tokens_default: int


async def _medium_call(prompt: str, system: str = "", max_tokens: int = 900) -> str:
    from app.services.ai_service import _call_with_fallback
    return await _call_with_fallback(prompt, system, max_tokens)


async def _best_reasoning_call(prompt: str, system: str = "", max_tokens: int = 900) -> str:
    from app.services.ai_service import _call_nvidia, _call_with_fallback
    result = await _call_nvidia(prompt, system, max_tokens)
    if result:
        return result
    log.info("ai_pipeline.best_reasoning.fallback_to_medium")
    return await _call_with_fallback(prompt, system, max_tokens)


MODEL_TIER_REGISTRY.register("medium")(ModelTier(
    key="medium",
    call=_medium_call,
    max_tokens_default=900,
))

MODEL_TIER_REGISTRY.register("best_reasoning")(ModelTier(
    key="best_reasoning",
    call=_best_reasoning_call,
    max_tokens_default=900,
))
