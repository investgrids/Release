"""
AEV2 assembly — a deterministic PRESENTER over the one canonical
CoreAnswer (see app/services/ai_search/core_answer.py), never a second
reasoning pipeline. Architecture decision (2026-09-21): this module must
never call an LLM, retrieve evidence, resolve entities, run a fallback
chain, or maintain its own degraded-response logic — every one of those
already happened once, upstream, to produce the CoreAnswer this function
reads from.

Build 1 (2026-09-21, hardened in review's second pass same day):
populates every deterministic restructuring field the approved spec
defines, from CoreAnswer alone:
  - direct_conclusion / what_happened / why_it_matters — CoreAnswer's own
    already-generated text (bottom_line/what_happened/why_it_happened),
    through the shared recommendation-language gate AND the citation
    validator (evidence_ref validity, supported-number rule, entity
    match) — a violation of either drops the claim to its honest
    fallback/empty shape. Zero regeneration: a rejected claim is never
    reworded or retried, only replaced with a fixed string or omitted.
    evidence_refs for these fields is citation_validator.
    deterministic_claim_evidence_refs(core)'s output — the one real
    company<->event structured-field relationship this codebase has —
    NEVER the whole evidence catalog attached indiscriminately. It can
    be, and often honestly is, empty.
  - companies_affected — deterministic, live-price-movement grouping
    (price_movement.py), not the specialist's own impact_type judgment.
  - time_horizon — primary_horizon is CoreAnswer.horizon (a timeframe
    bucket, not a recommendation); timeline_phases are CoreAnswer's own
    immediate/medium/long-term text, each independently gated+validated
    against the SAME deterministic claim evidence, dropped (not
    replaced with a fallback) on failure.
  - risks_and_invalidation.risks — CoreAnswer's own risk-analysis
    strings, each independently gated+validated. invalidates_if/
    watch_for have no CoreAnswer source yet — left honestly empty rather
    than invented.
  - related_intelligence.events — CoreAnswer.related_events reformatted;
    id/title/date only, deliberately no url/link/route field (Slice 3's
    canonical route-builder doesn't exist yet — see this function's own
    "no links" note below). opportunities/ripple have no CoreAnswer
    source yet (would require a new retrieval this module is not
    allowed to make) — left empty/None.
  - confidence — the CLOSED-SPEC four-component score (confidence.py):
    0.35 evidence_quality + 0.25 market_confirmation +
    0.25 historical_similarity + 0.15 data_freshness, all reused
    verbatim from postprocess.py's already-computed breakdown.

Deliberately absent, by design, not oversight: verdict, scenarios,
suitability, and top-pick concepts. CoreAnswer itself carries none of
investment_verdict's advisory sub-fields (see its own docstring), so
there is nothing here to accidentally surface even if a future edit
tried to.

No links yet (review requirement, 2026-09-21): related_intelligence.
events entries carry only id/title/date — no url/link/href/path key —
until Slice 3's canonical route-builder and route-existence tests exist.
The readiness latch (AEV2_BUILD_COMPLETE=False) already keeps this
whole response off canary/public regardless; this is a second, belt-
and-braces boundary at the data shape itself.
"""
from __future__ import annotations

import time

import structlog

from app.services.ai_search.aev2 import citation_validator, language_gate, schema, telemetry
from app.services.ai_search.aev2.comparison import assemble_comparison
from app.services.ai_search.aev2.confidence import compute_aev2_confidence
from app.services.ai_search.aev2.event_impact import assemble_event_impact
from app.services.ai_search.aev2.market_pulse import assemble_market_pulse
from app.services.ai_search.aev2.mode import AEV2Mode
from app.services.ai_search.aev2.price_movement import build_price_movement_groups
from app.services.ai_search.aev2.switch_analysis import assemble_switch_analysis
from app.services.ai_search.core_answer import CoreAnswer
from app.services.ai_search.core_market_pulse import CoreMarketPulse

log = structlog.get_logger(__name__)

# CanonicalAnswerCore (2026-09-22, Market Pulse AEV2 audit) — the
# discriminated union every presenter downstream of response_finalize.py
# now reads from. No shared base class or `kind` field ties the two
# together (see core_market_pulse.py's own docstring for why); Python's
# `isinstance` below is the discriminant. Both variants share this exact
# `assemble_aev2` entry point, the same OFF-mode short-circuit, and the
# same telemetry module (telemetry.emit_assembly_success/_failed) — a
# market-pulse-shaped query never reaches a second, independently-wired
# AEV2 pipeline.
CanonicalAnswerCore = CoreAnswer | CoreMarketPulse


def _build_singular_field(
    field_kind: str, raw_text: str, claim_refs: list[str], catalog_ids: set[str],
    claim_supporting_text: str, recognized_symbols: set[str], name_tokens: set[str],
) -> tuple[str, list[str], bool]:
    """Returns (final_text, evidence_refs, had_violation) for a field
    that must always carry SOME text — real, with evidence_refs limited
    to `claim_refs` (deterministic_claim_evidence_refs's output, which
    may be empty), or the field's fixed fallback string (evidence_refs
    always [] on a fallback) on any violation."""
    gated = language_gate.gate(field_kind, raw_text)
    if gated.had_violation:
        return gated.text, [], True
    if not raw_text:
        return "", [], False
    claim = citation_validator.validate_claim(
        raw_text, claim_refs, catalog_ids, recognized_symbols, claim_supporting_text, name_tokens,
    )
    if not claim.valid:
        fallback = language_gate.FALLBACK_TEXT.get(field_kind, language_gate.FALLBACK_TEXT["why_it_matters"])
        return fallback, [], True
    return raw_text, claim_refs, False


def _build_list_field_texts(
    texts: list[str], claim_refs: list[str], catalog_ids: set[str], claim_supporting_text: str,
    recognized_symbols: set[str], name_tokens: set[str],
) -> list[str]:
    """For list-shaped fields (risks, timeline phases) — an invalid
    entry is DROPPED, not replaced with a fallback placeholder (a list
    of N-1 real risks is more honest than N risks where one is a filler
    sentence)."""
    kept = []
    for text in texts:
        if not text or language_gate.scan(text):
            continue
        claim = citation_validator.validate_claim(
            text, claim_refs, catalog_ids, recognized_symbols, claim_supporting_text, name_tokens,
        )
        if not claim.valid:
            continue
        kept.append(text)
    return kept


def assemble_aev2(core: CanonicalAnswerCore, *, mode: AEV2Mode) -> dict | None:
    """Returns a freshly-built AEV2 dict, or None if `mode` is OFF
    (assembly never runs — see mode.should_assemble) or if assembly
    raised (telemetered, then degraded to None). Reads only from `core`;
    never mutates it, never re-derives entities/evidence, never calls a
    provider.

    Dispatches on which CanonicalAnswerCore variant `core` is — a
    CoreMarketPulse gets the entirely different AEV2MarketPulse shape
    (aev2/market_pulse.py), never nested inside the research-shaped
    envelope schema.build_response defines below. Both branches share
    this one entry point, the OFF-mode short-circuit above, and the
    telemetry module (see each branch's own emit_assembly_success/
    _failed calls) — this is the "same AEV2 dispatch" boundary, not two
    independently-wired assembly pipelines that happen to live in the
    same file."""
    if mode == AEV2Mode.OFF:
        return None

    if isinstance(core, CoreMarketPulse):
        _t0 = time.monotonic()
        try:
            response = assemble_market_pulse(core)
        except Exception as exc:
            log.warning("ai_search.aev2_market_pulse_assembly_exception", exc=str(exc)[:160])
            telemetry.emit_assembly_failed(
                query=core.query, mode=mode.value, failure_reason="market_pulse_assembly_exception",
                stage_ms={"failed_after_ms": round((time.monotonic() - _t0) * 1000, 1)},
            )
            return None
        telemetry.emit_assembly_success(
            query=core.query, mode=mode.value, response_id=core.response_id,
            had_language_violation=response["synthesis_status"] == "unavailable" and bool(core.generated_summary),
            is_fallback=response["synthesis_status"] == "unavailable",
            stage_ms={"total_ms": round((time.monotonic() - _t0) * 1000, 1)},
        )
        return response

    _t0 = time.monotonic()
    stage_ms: dict[str, float] = {}
    try:
        catalog = citation_validator.build_evidence_catalog(core)
        catalog_by_id = {c["id"]: c for c in catalog}
        catalog_ids = set(catalog_by_id)

        # The one deterministic per-claim relationship this codebase has
        # — see citation_validator's module docstring. Deliberately NOT
        # `list(catalog_ids)`: that would be exactly the "blanket
        # attachment of every source" the 2026-09-21 review rejected.
        claim_refs = citation_validator.deterministic_claim_evidence_refs(core)
        claim_supporting_text = " ".join(
            catalog_by_id[r]["title"] for r in claim_refs if r in catalog_by_id and catalog_by_id[r].get("title")
        )

        recognized_symbols = {
            (c.get("symbol") or "").upper() for c in core.companies if c.get("symbol")
        }
        name_tokens = citation_validator.recognized_name_tokens(core.companies)
        stage_ms["catalog_build_ms"] = round((time.monotonic() - _t0) * 1000, 1)
        _t_stage = time.monotonic()

        any_violation = False

        dc_text, dc_refs, dc_violation = _build_singular_field(
            "direct_conclusion", core.bottom_line, claim_refs, catalog_ids,
            claim_supporting_text, recognized_symbols, name_tokens,
        )
        any_violation = any_violation or dc_violation

        wh_text, wh_refs, wh_violation = _build_singular_field(
            "what_happened", core.what_happened, claim_refs, catalog_ids,
            claim_supporting_text, recognized_symbols, name_tokens,
        )
        any_violation = any_violation or wh_violation

        wim_text, wim_refs, wim_violation = _build_singular_field(
            "why_it_matters", core.why_it_happened, claim_refs, catalog_ids,
            claim_supporting_text, recognized_symbols, name_tokens,
        )
        any_violation = any_violation or wim_violation

        stage_ms["language_gate_ms"] = round((time.monotonic() - _t_stage) * 1000, 1)
        _t_stage = time.monotonic()

        price_movement = build_price_movement_groups(core.companies)

        timeline_phases = []
        for phase, text in (
            ("immediate", core.immediate_impact),
            ("medium_term", core.medium_term),
            ("long_term", core.long_term),
        ):
            kept = _build_list_field_texts(
                [text], claim_refs, catalog_ids, claim_supporting_text, recognized_symbols, name_tokens,
            )
            if kept:
                timeline_phases.append({"phase": phase, "text": kept[0]})

        risks = _build_list_field_texts(
            list(core.risks), claim_refs, catalog_ids, claim_supporting_text, recognized_symbols, name_tokens,
        )

        # Reuses the same catalog entries built above, rather than
        # re-deriving event shape a second time from core.related_events
        # — one source of truth for "what an event citation looks like."
        # id/title/date ONLY — no url/link/href/path key; see module
        # docstring's "No links yet" note.
        related_events = [
            {"id": c["id"], "title": c["title"], "date": c["date"]}
            for c in catalog if c["type"] == "event"
        ]

        confidence = compute_aev2_confidence(core)

        # switch_analysis (aev2.2) + comparison (aev2.3) + event_impact
        # (aev2.4, 2026-09-22) — all three reuse the SAME catalog/
        # claim_refs/claim_supporting_text/recognized_symbols/name_tokens
        # already computed above, and each is None for any query its own
        # assembler doesn't apply to (see each module's own docstring for
        # its "not applicable" scope).
        switch_analysis = assemble_switch_analysis(
            core, catalog_ids=catalog_ids, claim_refs=claim_refs,
            claim_supporting_text=claim_supporting_text,
            recognized_symbols=recognized_symbols, name_tokens=name_tokens,
        )
        comparison = assemble_comparison(
            core, catalog_ids=catalog_ids, claim_refs=claim_refs,
            claim_supporting_text=claim_supporting_text,
            recognized_symbols=recognized_symbols, name_tokens=name_tokens,
        )
        # event_impact deliberately does NOT take claim_refs/claim_
        # supporting_text/recognized_symbols/name_tokens — see its own
        # docstring for why the globally-scoped citation set (correct
        # for switch_analysis/comparison's multi-company dimensions) is
        # too wide for a single-Event contract.
        event_impact = assemble_event_impact(core, catalog_ids=catalog_ids)
        stage_ms["restructuring_ms"] = round((time.monotonic() - _t_stage) * 1000, 1)

        response = schema.build_response(
            direct_conclusion=schema.build_validated_claim(dc_text, dc_refs, had_violation=dc_violation),
            what_happened={"summary": wh_text, "evidence_refs": wh_refs, "items": []},
            why_it_matters={"text": wim_text, "evidence_refs": wim_refs, "is_fallback": wim_violation},
            companies_affected=price_movement,
            time_horizon={"primary_horizon": core.horizon, "timeline_phases": timeline_phases},
            risks_and_invalidation={"kind": "analysis", "risks": risks, "invalidates_if": [], "watch_for": []},
            evidence=catalog,
            related_intelligence={"opportunities": [], "events": related_events, "ripple": None},
            confidence=confidence,
            switch_analysis=switch_analysis,
            comparison=comparison,
            event_impact=event_impact,
        )
    except Exception as exc:
        stage_ms["failed_after_ms"] = round((time.monotonic() - _t0) * 1000, 1)
        log.warning("ai_search.aev2_assembly_exception", exc=str(exc)[:160])
        telemetry.emit_assembly_failed(
            query=core.query, mode=mode.value, failure_reason="assembly_exception", stage_ms=stage_ms,
        )
        return None

    telemetry.emit_assembly_success(
        query=core.query,
        mode=mode.value,
        response_id=core.response_id,
        had_language_violation=any_violation,
        is_fallback=any_violation,
        stage_ms=stage_ms,
    )
    return response
