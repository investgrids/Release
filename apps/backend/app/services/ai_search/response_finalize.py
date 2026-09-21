"""
The one shared post-processing pipeline every /api/ai/search* route runs
its resolved V3 core response through, before it ever reaches a client —
and the one place the canonical CoreAnswer is built for presentation,
and the one place a search is recorded to the prediction/calibration
learning engine:

    cached/fresh V3 core
    -> recommendation-language safety gate (unconditional, any AEV2 mode)
    -> honest degraded response on violation
    -> CoreAnswer.from_v3_response (one immutable projection)
    -> optional AEV2 assembly, reading only the CoreAnswer
    -> prediction recording (fresh + clean only — see below)
    -> strip internal-only attribution plumbing (see below)
    -> return the V3 dict presenter (unchanged), optionally + AEV2's

Internal-only field stripping (2026-09-21, review): pipeline.py's
response dict carries an "announcements" key (CompanyAnnouncement rows,
added so CoreAnswer/AEV2's citation validator can attribute claims to
them) that was never part of V3's public contract before AEV2 existed.
It must never reach an actual HTTP caller, cached or fresh, regardless
of AEV2 mode — this function is the one place downstream of both cache
retrieval AND CoreAnswer construction, so it's the only correct place to
strip it: late enough that CoreAnswer has already read it (AEV2 still
gets its attribution data), early enough that no route-specific
serialization step could accidentally let it through unstripped.

Prediction recording (2026-09-21): moved here from pipeline.py's
_assemble_response, which fired store_search_predictions
unconditionally on every was_degraded=False result — including one that
would go on to fail THIS module's own safety gate a few lines later.
That ordering meant a response degraded for unsafe generated language
could still have already recorded a prediction from its pre-gate
content. This is the one place downstream of the gate that also knows
was_cached (threaded in from each route's own run_ai_search_v3 call),
so it's the only correct place to enforce all three: no prediction on a
cache hit, no prediction on a gate rejection, exactly one prediction on
a fresh clean answer.

Exists because wiring this into only one of the three real serving routes
(/search, /search/v3, /search/stream) would leave the others unprotected
— found in review (2026-09-21) that /search/stream, not /search/v3, is
the route actual production frontend traffic uses today (per its own
docstring: NEXT_PUBLIC_AI_SEARCH_V3 is unset in prod, so the SSE route is
what real users hit). Every route calls this one function so the ordering
above is defined and tested in exactly one place.

Architecture decision (2026-09-21): MarketRipple has one canonical
reasoning pipeline (run_ai_search_v3, upstream of this function) and two
PRESENTERS — the existing V3 response dict (returned as `result` below,
unchanged) and AEV2 (`answer_experience_v2`, optionally attached). Both
presenters are derived from the identical `CoreAnswer` built once here;
AEV2 never sees or re-derives anything upstream of it. The rollout mode
changes only which presenter is serialized, never how the answer was
produced.

Never mutates `result` — every step reads from it and, if something needs
to change, returns a brand new dict. The object cache_mod.set_response
stored (deep inside run_ai_search_v3, upstream of this function) is
therefore never touched, regardless of how many times a cached response
passes back through this pipeline under different rollout modes.
"""
from __future__ import annotations

import asyncio

from app.services.ai_search import safety_gate
from app.services.ai_search.aev2.assemble import assemble_aev2
from app.services.ai_search.aev2.mode import get_aev2_mode, should_assemble, should_return_to_client
from app.services.ai_search.core_answer import from_v3_response

# Internal-only fields CoreAnswer is allowed to read from `result` that
# must never be serialized to an actual HTTP caller — see this module's
# docstring. A set, not a single name, so a future internal-only
# addition (e.g. a second attribution source) has one obvious place to
# register rather than a new ad hoc strip somewhere else.
_INTERNAL_ONLY_FIELDS = frozenset({"announcements"})


def _strip_internal_only_fields(result: dict) -> dict:
    if not any(k in result for k in _INTERNAL_ONLY_FIELDS):
        return result
    return {k: v for k, v in result.items() if k not in _INTERNAL_ONLY_FIELDS}


def finalize_v3_response(
    query: str, result: dict | None, *, x_admin_key: str | None = None, was_cached: bool = False,
) -> dict | None:
    """`x_admin_key` is None for routes that structurally cannot carry
    one — /search/stream is a browser EventSource GET, and the
    EventSource API supports no custom request headers at all, so canary
    mode is simply unreachable from that route. That is the correct, safe
    default (matches the non-negotiable "X-Admin-Key never in client
    code" rule) — not a gap that needs a workaround.

    `was_cached` must be the caller's own was_cached flag from
    run_ai_search_v3 (or the SSE route's equivalent derivation) — it is
    the only signal this function has for "don't record a second
    prediction for an answer already recorded the first time it was
    computed."""
    if result is None:
        return result

    # ── 1. Deterministic recommendation-language safety net — runs
    # UNCONDITIONALLY, regardless of AI_SEARCH_AEV2_MODE. See
    # safety_gate.py's module docstring for the real incident this closes.
    violated_field = safety_gate.find_v3_safety_violation(result)
    if violated_field:
        result = safety_gate.build_v3_safety_degraded_response(result, violated_field)

    # ── 2. One immutable CoreAnswer, built once from whatever `result`
    # is at this point (the real response, or the safety-degraded one
    # above) — the single object every presenter (V3's own dict, already
    # `result`; AEV2, below) derives from. ─────────────────────────────
    core = from_v3_response(result)

    # ── 3. Optional AEV2 assembly — a presenter over `core`, never over
    # `result` directly, and never mutating either. ────────────────────
    from app.core.security import has_valid_admin_key

    aev2_mode = get_aev2_mode()
    if should_assemble(aev2_mode):
        aev2_value = assemble_aev2(core, mode=aev2_mode)
        if aev2_value is not None and should_return_to_client(
            aev2_mode, has_valid_admin_key=has_valid_admin_key(x_admin_key),
        ):
            result = {**result, "answer_experience_v2": aev2_value}

    # ── 4. Prediction recording — fresh + clean only. Never on a cache
    # hit (the same answer already recorded one the first time it was
    # computed) and never on a gate rejection (result["synthesis_incomplete"]
    # is True on both the specialist-degraded and the safety-gate-degraded
    # shape — see degraded_shape.py). Fire-and-forget, exactly as the
    # prior in-pipeline call site was — a prediction-store failure must
    # never affect the answer already being returned. ──────────────────
    if not was_cached and not result.get("synthesis_incomplete"):
        from app.services.ai_search.prediction_recording import store_search_predictions

        breakdown = result.get("confidence_breakdown") or {}
        asyncio.create_task(
            store_search_predictions(
                result=result,
                confidence_score=breakdown.get("final_confidence"),
                confidence_level=breakdown.get("level", "unscored"),
                confidence_breakdown=breakdown,
            ),
            name="prediction-store-v3",
        )

    # ── 5. Strip internal-only attribution plumbing — the one point
    # every route and every cache-hit/fresh/mode combination passes
    # through before a response is actually returned. ──────────────────
    return _strip_internal_only_fields(result)
