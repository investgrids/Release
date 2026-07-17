"""
Generic decorator-based registry used by every pluggable stage of the AI
pipeline (intents, retrievers, templates, model tiers).

Modules register themselves on import via `@REGISTRY.register("key")`; the
orchestrator only ever calls `REGISTRY.get(key)` — no `if key == "x"` chains
anywhere in the pipeline. Each package's `__init__.py` imports every sibling
module once (for its side effect of registration), mirroring the existing
`app/db/models/__init__.py` pattern already used for SQLAlchemy model
registration in this codebase.
"""
from __future__ import annotations

from typing import Generic, TypeVar

T = TypeVar("T")


class Registry(Generic[T]):
    def __init__(self, kind: str) -> None:
        self._kind = kind
        self._items: dict[str, T] = {}

    def register(self, key: str):
        def deco(obj: T) -> T:
            if key in self._items:
                raise ValueError(f"{self._kind} '{key}' is already registered")
            self._items[key] = obj
            return obj
        return deco

    def get(self, key: str) -> T | None:
        return self._items.get(key)

    def all(self) -> dict[str, T]:
        return dict(self._items)

    def keys(self) -> list[str]:
        return list(self._items.keys())


INTENT_REGISTRY: Registry = Registry("intent")
RETRIEVER_REGISTRY: Registry = Registry("retriever")
TEMPLATE_REGISTRY: Registry = Registry("template")
MODEL_TIER_REGISTRY: Registry = Registry("model_tier")
