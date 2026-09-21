"""
The one shared post-processing pipeline every /api/ai/search* route runs
its resolved V3 core response through, before it ever reaches a client —
and the one place the canonical CoreAnswer is built for presentation:

    cached/fresh V3 core
    -> recommendation-language safety gate (unconditional, any AEV2 mode)
    -> honest degraded response on violation
    -> CoreAnswer.from_v3_response (one immutable projection)
    -> optional AEV2 assembly, reading only the CoreAnswer
    -> return the V3 dict presenter (unchanged), optionally + AEV2's

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

from app.services.ai_search import safety_gate
from app.services.ai_search.aev2.assemble import assemble_aev2
from app.services.ai_search.aev2.mode import get_aev2_mode, should_assemble, should_return_to_client
from app.services.ai_search.core_answer import from_v3_response


def finalize_v3_response(query: str, result: dict | None, *, x_admin_key: str | None = None) -> dict | None:
    """`x_admin_key` is None for routes that structurally cannot carry
    one — /search/stream is a browser EventSource GET, and the
    EventSource API supports no custom request headers at all, so canary
    mode is simply unreachable from that route. That is the correct, safe
    default (matches the non-negotiable "X-Admin-Key never in client
    code" rule) — not a gap that needs a workaround."""
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

    return result
