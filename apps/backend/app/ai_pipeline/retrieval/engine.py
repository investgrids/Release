"""
Parallel Retrieval Engine — fans out to every retriever an intent declares,
runs them concurrently, and degrades gracefully: a retriever that times out
or raises contributes zero evidence and its key is recorded, never fails
the whole query. (Same philosophy as the existing 3-way `asyncio.gather` in
`ai_search_service.run_ai_search` for events/news/policies — generalized
here to an arbitrary, registry-driven set of retrievers.)
"""
from __future__ import annotations

import asyncio

import structlog

from app.ai_pipeline.contracts import Evidence
from app.ai_pipeline.registry import RETRIEVER_REGISTRY
from app.ai_pipeline.retrieval.base import RetrievalContext, RetrieverSpec

log = structlog.get_logger(__name__)


async def _run_one(spec: RetrieverSpec, ctx: RetrievalContext) -> list[Evidence]:
    try:
        return await asyncio.wait_for(spec.fetch(ctx), timeout=spec.timeout_s)
    except asyncio.TimeoutError:
        log.warning("ai_pipeline.retriever_timeout", retriever=spec.key, query=ctx.query[:60])
        return []
    except Exception as exc:
        log.warning("ai_pipeline.retriever_error", retriever=spec.key, error=str(exc)[:200])
        return []


async def parallel_retrieve(retriever_keys: list[str], ctx: RetrievalContext) -> tuple[list[Evidence], list[str]]:
    """Returns (evidence, degraded_retriever_keys)."""
    specs: list[RetrieverSpec] = []
    for key in retriever_keys:
        spec = RETRIEVER_REGISTRY.get(key)
        if spec is None:
            log.warning("ai_pipeline.unknown_retriever", retriever=key)
            continue
        specs.append(spec)

    if not specs:
        return [], list(retriever_keys)

    results = await asyncio.gather(*[_run_one(s, ctx) for s in specs])

    evidence: list[Evidence] = []
    degraded: list[str] = []
    for spec, result in zip(specs, results):
        if result:
            evidence.extend(result)
        else:
            degraded.append(spec.key)
    return evidence, degraded
