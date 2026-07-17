"""Retriever specification and the shared context passed to every retriever."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai_pipeline.contracts import Evidence


@dataclass(frozen=True)
class RetrievalContext:
    query: str
    db: AsyncSession
    intent: str


@dataclass(frozen=True)
class RetrieverSpec:
    """
    Every retriever module registers exactly one of these. `fetch` must
    return `[]` on any internal failure — never raise past the retrieval
    engine's own timeout/exception guard, so one bad data source degrades
    gracefully instead of failing the whole query.
    """
    key: str
    fetch: Callable[[RetrievalContext], Awaitable[list[Evidence]]]
    timeout_s: float = 5.0
