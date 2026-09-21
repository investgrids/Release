"""
CoreAnswer — the one canonical, presentation-agnostic result of a search
(entity resolution -> evidence retrieval -> one specialist call -> parsing
and validation -> the recommendation-language safety gate), from which
every presenter derives its own shape.

Owner architecture decision (2026-09-21): MarketRipple has ONE reasoning
pipeline (app.services.ai_search.pipeline.run_ai_search_v3 — entity
resolution, evidence.collect(), exactly one specialist call through the
single provider fallback chain, validation, the safety gate), not one per
presentation format. AEV2 is a deterministic PRESENTER over this same
CoreAnswer, never a second pipeline — it must never call an LLM, retrieve
evidence again, resolve entities independently, run its own fallback
chain, or maintain its own degraded-response logic.

This module is deliberately a THIN, READ-ONLY PROJECTION over the
existing V3 response dict (pipeline.py's own internals are unchanged and
carry all the real risk-bearing logic already tested elsewhere) — not a
rewrite of pipeline.py's data flow. `from_v3_response()` is a pure
function: same input always produces an equal CoreAnswer, and the
resulting object is frozen (immutable), so passing the identical
CoreAnswer instance to two different presenters (V3's own dict, already
built; AEV2's assemble_aev2) is what "both presenters receive the same
immutable CoreAnswer" means concretely — not two independent re-reads of
a mutable dict that could diverge.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class CoreAnswer:
    query: str
    response_id: str | None
    specialist: str | None
    synthesis_incomplete: bool
    degraded_reason: str | None
    bottom_line: str
    summary: str
    companies: tuple[dict, ...] = field(default_factory=tuple)
    sectors: tuple[dict, ...] = field(default_factory=tuple)
    related_events: tuple[dict, ...] = field(default_factory=tuple)
    news: tuple[dict, ...] = field(default_factory=tuple)
    policies: tuple[dict, ...] = field(default_factory=tuple)
    risks: tuple[str, ...] = field(default_factory=tuple)
    confidence_score: float | None = None
    confidence_level: str = "unscored"
    source_attribution: tuple[str, ...] = field(default_factory=tuple)


def from_v3_response(v3_response: dict | None) -> CoreAnswer:
    """Pure projection — reads `v3_response`, never mutates it, and never
    calls out to any provider/evidence/entity-resolution code (this
    function is the one place AEV2 or any other presenter is allowed to
    derive a CoreAnswer from, and it touches only the dict already
    computed by the real pipeline)."""
    v3_response = v3_response or {}
    answer = v3_response.get("answer") or {}
    return CoreAnswer(
        query=v3_response.get("query", ""),
        response_id=v3_response.get("response_id"),
        specialist=v3_response.get("specialist"),
        synthesis_incomplete=bool(v3_response.get("synthesis_incomplete", False)),
        degraded_reason=v3_response.get("degraded_reason"),
        bottom_line=answer.get("bottom_line") or "",
        summary=answer.get("summary") or "",
        companies=tuple(v3_response.get("companies") or []),
        sectors=tuple(v3_response.get("sectors") or []),
        related_events=tuple(v3_response.get("related_events") or []),
        news=tuple(v3_response.get("news") or []),
        policies=tuple(v3_response.get("policies") or []),
        risks=tuple(answer.get("risks") or []),
        confidence_score=answer.get("confidence"),
        confidence_level=answer.get("confidence_level") or "unscored",
        source_attribution=tuple(v3_response.get("source_attribution") or []),
    )
