"""
The one shared post-processing pipeline every /api/ai/search* route runs
its resolved V3 core response through, before it ever reaches a client —
and the one place a canonical core is built for presentation, and the
one place a search is recorded to the prediction/calibration learning
engine:

    cached/fresh V3 core (research-shaped OR market-pulse-shaped)
    -> recommendation-language safety gate (unconditional, any AEV2 mode;
       shape-aware implementation, same boundary)
    -> honest degraded response on violation
    -> one immutable CanonicalAnswerCore projection (CoreAnswer OR
       CoreMarketPulse — see aev2/assemble.py's own CanonicalAnswerCore
       docstring for why no shared base class ties them together)
    -> optional AEV2 assembly, reading only that canonical core
       (assemble_aev2 itself dispatches on which variant it received)
    -> prediction recording (research only — fresh + clean only, see
       below)
    -> strip internal-only attribution plumbing (see below)
    -> return the V3 dict presenter (unchanged), optionally + AEV2's

Market Pulse (2026-09-21, intent audit + Phase 1 fix; restructured
2026-09-22, Market Pulse AEV2 audit): Market Pulse short-circuits
_run_v3_steps with a STRUCTURALLY DIFFERENT response shape ({"type":
"market_pulse", "market_summary": str, ...} — no `answer`/`companies`/
`investment_verdict`), but every route still calls this same
finalize_v3_response on whatever _run_v3_steps yields. The 2026-09-21
fix routed this shape through market_pulse_safety.py's own field-aware
safety check (safety_gate.py's fixed field paths don't exist on this
shape) but then RETURNED EARLY — a second, independently-wired
finalization path that never built a canonical core, never ran AEV2,
never went through the shared serialization gate. The 2026-09-22 audit
concluded this was the wrong shape for the architecture (Market Pulse
must not become "a second AI-answer pipeline") — Market Pulse now
builds its own CoreMarketPulse (core_market_pulse.py) at the exact same
step CoreAnswer is built for a research query, and flows through every
step below it identically. Prediction recording is the one step Market
Pulse still skips deliberately (not one of the required shared
boundaries — it has no confidence_breakdown/investment-thesis concept
for the calibration engine to record against).

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

import structlog

from app.services.ai_search import market_pulse_safety, safety_gate
from app.services.ai_search.aev2.assemble import assemble_aev2
from app.services.ai_search.aev2.mode import get_aev2_mode, should_assemble, should_return_to_client
from app.services.ai_search.core_answer import from_v3_response
from app.services.ai_search.core_market_pulse import from_market_pulse_response

log = structlog.get_logger(__name__)

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


# ── answer_availability (2026-09-23) — the backend's own honest account
# of WHY a response has limited or no evidence, so the frontend never
# again has to infer "no evidence exists" from an empty array alone (an
# empty related_events/news/policies list can just as easily mean
# retrieval itself never completed, e.g. a provider/capacity failure, as
# it can mean retrieval completed and genuinely found nothing).
#
# Derived entirely from `degraded_reason`/`synthesis_incomplete` — never
# a new field threaded through pipeline.py — because degraded_reason is
# already, per pipeline.py's own comment ("degraded_reason is the single
# source of truth"), a complete account of every degradation path,
# research-shaped or market-pulse-shaped. Reading it here rather than
# adding a parallel marker also means this survives EVERY response
# reconstruction downstream of the original assembly — including
# safety_gate.build_v3_safety_degraded_response's rebuild via
# build_degraded_shape, which passes through an explicit field whitelist
# that a bolted-on marker would simply be dropped by.
#
# Computed fresh on every call, from `result` as it exists RIGHT NOW —
# never stored in or read from the cache. Both cache layers hold the
# pre-safety-gate `result` (see this module's own docstring), and this
# function runs strictly after that gate, so a stale cached degraded
# response can never misreport its own availability; re-deriving costs
# nothing (it's pure dict inspection, no I/O).
_PRE_RETRIEVAL_DEGRADED_REASONS = frozenset({
    # Set by pipeline.py's _referential_no_context_response/
    # _ambiguous_entity_response/_unrecognized_company_response_v3 —
    # confident, deterministic classifications made BEFORE
    # evidence_mod.collect() ever runs. Not a capacity/provider failure
    # (not "temporarily_unavailable") and not "retrieval completed with
    # zero results" in the literal sense (retrieval never started) — of
    # the 4 available states, "no_verified_evidence" is the honest
    # closest fit: there genuinely is no evidence to show, and it is not
    # a transient condition a retry would fix.
    "referential_no_context", "ambiguous_entity", "unsupported_entity",
})

# Set by specialists/base.py's parse_specialist_json when the LLM
# provider returned no text at all ("capacity") or text that didn't
# parse ("parse_failure") — both fire strictly AFTER evidence_mod.
# collect() already succeeded (see pipeline.py's own ordering: evidence
# collection at line ~336, the specialist/LLM call afterward). Real
# evidence may already be sitting in `result`, but the ANALYSIS did not
# complete — the user should be told to retry, never told "no evidence
# exists" or given a confident "limited" take assembled from nothing.
_PROVIDER_FAILURE_DEGRADED_REASONS = frozenset({"capacity", "parse_failure"})


def _research_evidence_count(result: dict) -> int:
    return (
        len(result.get("related_events") or [])
        + len(result.get("news") or [])
        + len(result.get("policies") or [])
    )


def _market_pulse_evidence_count(result: dict) -> int:
    return (
        len(result.get("indices") or [])
        + len(result.get("top_gainers") or [])
        + len(result.get("top_losers") or [])
        + len(result.get("leading_sectors") or [])
        + len(result.get("lagging_sectors") or [])
    )


def _derive_answer_availability(result: dict, *, is_market_pulse: bool) -> dict:
    """The one function that computes `answer_availability`. Fails
    closed on anything it doesn't explicitly recognize: an unrecognized
    degraded_reason with real evidence present lands on the more modest
    `limited_evidence` rather than `available` — see the final branch."""
    synthesis_incomplete = bool(result.get("synthesis_incomplete"))
    evidence_count = (
        _market_pulse_evidence_count(result) if is_market_pulse else _research_evidence_count(result)
    )

    if not synthesis_incomplete:
        return {"state": "available", "evidence_retrieval_completed": True, "evidence_count": evidence_count}

    if is_market_pulse:
        # Market Pulse's only degraded path is an LLM narrative failure
        # over real, already-fetched market data (market_pulse.py's own
        # `synthesis_incomplete = not bool(ai)`) — there is no "zero
        # evidence" state for market-wide data, only "we couldn't
        # narrate it right now." `market_status` truthiness is this
        # shape's own signal for whether get_market_pulse() itself
        # returned real data or the `{}` fallback on a fetch failure.
        return {
            "state": "temporarily_unavailable",
            "evidence_retrieval_completed": bool(result.get("market_status")),
            "evidence_count": evidence_count,
        }

    degraded_reason = result.get("degraded_reason")

    if degraded_reason in _PRE_RETRIEVAL_DEGRADED_REASONS:
        return {"state": "no_verified_evidence", "evidence_retrieval_completed": False, "evidence_count": 0}

    if degraded_reason in _PROVIDER_FAILURE_DEGRADED_REASONS:
        return {
            "state": "temporarily_unavailable",
            "evidence_retrieval_completed": True,
            "evidence_count": evidence_count,
        }

    # grounding_collapsed / multi_entity_partial / recommendation_language_
    # violation / any future reason: retrieval and at least partial
    # synthesis both ran — the honest remaining distinction is whether
    # any real evidence survived to actually show.
    if evidence_count == 0:
        return {"state": "no_verified_evidence", "evidence_retrieval_completed": True, "evidence_count": 0}
    return {"state": "limited_evidence", "evidence_retrieval_completed": True, "evidence_count": evidence_count}


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

    is_market_pulse = result.get("type") == "market_pulse"

    # ── 1. Deterministic recommendation-language safety net — runs
    # UNCONDITIONALLY, regardless of AI_SEARCH_AEV2_MODE, for BOTH
    # canonical-core variants. Market Pulse's response shape has no
    # `answer.bottom_line`/`ai_conclusion.investor_action_note`/etc. for
    # safety_gate.py's fixed field paths to find (see that module's own
    # docstring for the real incident this closes for the research
    # shape) — market_pulse_safety.py is the shape-aware implementation
    # of this SAME boundary for Market Pulse's own field set
    # (market_summary/sector_narrative/ai_conclusion/
    # what_to_watch_summary/mover narratives).
    #
    # 2026-09-23 fix (Phase 1.3 live verification, BEL/HAL switch query):
    # this gate used to rebuild `result` on ANY violation, even when
    # `result` was ALREADY a degraded response (synthesis_incomplete=
    # True) for some earlier, unrelated reason — e.g. a capacity failure
    # whose own generic fallback text happened to echo the user's raw
    # query, which itself contained an advisory-shaped phrase ("...
    # continue holding BEL or switch to HAL?"). The rebuild silently
    # replaced the real degraded_reason ("capacity") with "recommendation_
    # language_violation", destroying the original failure cause that
    # answer_availability (and any operator debugging a real outage)
    # depends on. `degraded_response()` itself no longer echoes the raw
    # query (see specialists/base.py's own 2026-09-23 fix) — this is
    # defense in depth for any OTHER field/path that could still
    # legitimately or accidentally carry advisory-shaped text on an
    # already-degraded response. The original degraded_reason is now
    # immutable once set: a safety hit on an already-degraded response is
    # recorded in telemetry only, never promoted to the public primary
    # cause. `recommendation_language_violation` remains reachable only
    # the way it always mattered — rejecting an otherwise SUCCESSFUL
    # response whose generated conclusion failed this check. ────────────
    if is_market_pulse:
        violated = market_pulse_safety.find_market_pulse_violation(result)
        if violated:
            if result.get("synthesis_incomplete"):
                log.warning(
                    "ai_search_v3.safety_hit_on_already_degraded_response",
                    field=violated, original_degraded_reason=result.get("degraded_reason"),
                )
            else:
                result = market_pulse_safety.build_market_pulse_degraded_response(result, violated)
    else:
        violated_field = safety_gate.find_v3_safety_violation(result)
        if violated_field:
            if result.get("synthesis_incomplete"):
                log.warning(
                    "ai_search_v3.safety_hit_on_already_degraded_response",
                    field=violated_field, original_degraded_reason=result.get("degraded_reason"),
                )
            else:
                result = safety_gate.build_v3_safety_degraded_response(result, violated_field)

    # ── 2. One immutable CanonicalAnswerCore, built once from whatever
    # `result` is at this point (the real response, or the safety-
    # degraded one above) — the single object every presenter (V3's own
    # dict, already `result`; AEV2, below) derives from. Market Pulse
    # builds CoreMarketPulse here instead of CoreAnswer — same step, same
    # "build exactly once, unconditionally" discipline, never a second
    # finalization path that skips this. ────────────────────────────────
    core = from_market_pulse_response(result) if is_market_pulse else from_v3_response(result)

    # ── 3. Optional AEV2 assembly — a presenter over `core`, never over
    # `result` directly, and never mutating either. assemble_aev2 itself
    # dispatches on which CanonicalAnswerCore variant `core` is (see its
    # own docstring) — this call site never needs to know or care which
    # one it's holding. should_return_to_client is the SAME public-
    # serialization gate for both. ──────────────────────────────────────
    from app.core.security import has_valid_admin_key

    aev2_mode = get_aev2_mode()
    if should_assemble(aev2_mode):
        aev2_value = assemble_aev2(core, mode=aev2_mode)
        if aev2_value is not None and should_return_to_client(
            aev2_mode, has_valid_admin_key=has_valid_admin_key(x_admin_key),
        ):
            result = {**result, "answer_experience_v2": aev2_value}

    # ── 4. Prediction recording — research only. Not one of the shared
    # canonical-core boundaries: Market Pulse has no confidence_breakdown
    # or investment-thesis concept for the calibration engine to record
    # a prediction against (see module docstring). Fresh + clean only
    # for the research path — never on a cache hit (the same answer
    # already recorded one the first time it was computed) and never on
    # a gate rejection (result["synthesis_incomplete"] is True on both
    # the specialist-degraded and the safety-gate-degraded shape — see
    # degraded_shape.py). Fire-and-forget — a prediction-store failure
    # must never affect the answer already being returned. ─────────────
    if not is_market_pulse and not was_cached and not result.get("synthesis_incomplete"):
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

    # ── 5. answer_availability — see this module's own section above for
    # why it must be derived here, fresh, on every call. ─────────────────
    result = {**result, "answer_availability": _derive_answer_availability(result, is_market_pulse=is_market_pulse)}

    # ── 6. Strip internal-only attribution plumbing — the one point
    # every route, every cache-hit/fresh/mode combination, and both
    # canonical-core variants pass through before a response is actually
    # returned. A no-op for Market Pulse (its shape never carries
    # "announcements"), applied unconditionally anyway rather than
    # special-cased — one shared exit, not two. ─────────────────────────
    return _strip_internal_only_fields(result)
