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

Deliberate exclusion (Build 1, 2026-09-21): CoreAnswer carries no
rating, direction, top_picks, suitable_for, opportunity_score, risk_level,
engine_verdict, or scenarios field — investment_verdict's advisory/
recommendation-shaped sub-fields are not projected here at all. This is
the strongest form of "AEV2 has no verdict/scenario/suitability/top-pick
concepts": AEV2 cannot reference what CoreAnswer never exposes, so the
constraint holds at the type level, not just by assemble.py's own
discipline. `horizon` below is the one investment_verdict field that
does cross this boundary — a timeframe classification ("1-3 months") is
a factual bucket, not a recommendation, and time_horizon.primary_horizon
needs it. `risks` (free-text risk analysis from answer.risks) is kept
for the same reason; investment_verdict.risks (paired with catalysts,
ratings-adjacent) is not.

Frozen-but-shallow caveat (review finding, 2026-09-21 second pass): a
`@dataclass(frozen=True)` only blocks reassigning a FIELD
(`core.bottom_line = x` raises) — it does nothing to stop a presenter
from reaching into a nested dict a tuple field holds and mutating THAT
in place (`core.companies[0]["symbol"] = "x"` would succeed silently).
`from_v3_response()` therefore deep-copies every nested list/dict field
below, so a CoreAnswer never aliases the same dict objects the original
v3_response (or the V3 presenter still holding it) does — a mutation on
one side can never reach the other through shared references. This is
belt-and-braces alongside "don't write code that mutates it": the real
enforcement is still that assemble_aev2 has no reason to write to `core`
at all (see its own docstring), and test_ai_search_single_pipeline_
runtime.py / test_ai_search_consolidation.py snapshot-compare a
CoreAnswer before and after a presenter runs to prove neither actually
does.
"""
from __future__ import annotations

import copy
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
    what_happened: str = ""
    why_it_happened: str = ""
    immediate_impact: str = ""
    medium_term: str = ""
    long_term: str = ""
    # investment_verdict.horizon only — see the class docstring's
    # "Deliberate exclusion" note for why nothing else from
    # investment_verdict is projected onto CoreAnswer.
    horizon: str | None = None
    # Read-only passthrough of postprocess.compute_confidence_breakdown's
    # already-computed 6-part breakdown (evidence_quality/
    # market_confirmation/historical_similarity/data_freshness/
    # reasoning_confidence/final_confidence) — AEV2's own confidence
    # score reuses these existing signals (see aev2/confidence.py) rather
    # than recomputing anything; this is that shared source of truth.
    confidence_breakdown: dict = field(default_factory=dict)


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
        # Deep-copied, not just wrapped in tuple() — tuple() only freezes
        # the OUTER sequence; the dicts inside would still be the exact
        # same mutable objects the original v3_response holds without
        # this. See this function's own docstring above.
        companies=tuple(copy.deepcopy(v3_response.get("companies") or [])),
        sectors=tuple(copy.deepcopy(v3_response.get("sectors") or [])),
        related_events=tuple(copy.deepcopy(v3_response.get("related_events") or [])),
        news=tuple(copy.deepcopy(v3_response.get("news") or [])),
        policies=tuple(copy.deepcopy(v3_response.get("policies") or [])),
        risks=tuple(copy.deepcopy(answer.get("risks") or [])),
        confidence_score=answer.get("confidence"),
        confidence_level=answer.get("confidence_level") or "unscored",
        source_attribution=tuple(copy.deepcopy(v3_response.get("source_attribution") or [])),
        what_happened=answer.get("what_happened") or "",
        why_it_happened=answer.get("why_it_happened") or "",
        immediate_impact=answer.get("immediate_impact") or "",
        medium_term=answer.get("medium_term") or "",
        long_term=answer.get("long_term") or "",
        horizon=(v3_response.get("investment_verdict") or {}).get("horizon") or None,
        confidence_breakdown=copy.deepcopy(v3_response.get("confidence_breakdown") or {}),
    )
