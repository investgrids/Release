"""
AEV2 assembly — a deterministic PRESENTER over the one canonical
CoreAnswer (see app/services/ai_search/core_answer.py), never a second
reasoning pipeline. Architecture decision (2026-09-21): this module must
never call an LLM, retrieve evidence, resolve entities, run a fallback
chain, or maintain its own degraded-response logic — every one of those
already happened once, upstream, to produce the CoreAnswer this function
reads from.

Build 1 (2026-09-21): populates every deterministic restructuring field
the approved spec defines, from CoreAnswer alone:
  - direct_conclusion / what_happened / why_it_matters — CoreAnswer's own
    already-generated text (bottom_line/what_happened/why_it_happened),
    through the shared recommendation-language gate AND the citation
    validator (evidence_ref validity, supported-number rule, entity
    match) — a violation of either drops the claim to its honest
    fallback/empty shape. Zero regeneration: a rejected claim is never
    reworded or retried, only replaced with a fixed string or omitted.
  - companies_affected — deterministic, live-price-movement grouping
    (price_movement.py), not the specialist's own impact_type judgment.
  - time_horizon — primary_horizon is CoreAnswer.horizon (a timeframe
    bucket, not a recommendation); timeline_phases are CoreAnswer's own
    immediate/medium/long-term text, each independently gated+validated,
    dropped (not replaced with a fallback) on failure.
  - risks_and_invalidation.risks — CoreAnswer's own risk-analysis
    strings, each independently gated+validated. invalidates_if/
    watch_for have no CoreAnswer source yet — left honestly empty rather
    than invented.
  - related_intelligence.events — CoreAnswer.related_events reformatted;
    opportunities/ripple have no CoreAnswer source yet (would require a
    new retrieval this module is not allowed to make) — left empty/None.
  - confidence — the four-component AEV2 score (confidence.py), built
    entirely from already-computed signals.

Deliberately absent, by design, not oversight: verdict, scenarios,
suitability, and top-pick concepts. CoreAnswer itself carries none of
investment_verdict's advisory sub-fields (see its own docstring), so
there is nothing here to accidentally surface even if a future edit
tried to.
"""
from __future__ import annotations

import time

import structlog

from app.services.ai_search.aev2 import citation_validator, language_gate, schema, telemetry
from app.services.ai_search.aev2.confidence import compute_aev2_confidence
from app.services.ai_search.aev2.mode import AEV2Mode
from app.services.ai_search.aev2.price_movement import build_price_movement_groups
from app.services.ai_search.core_answer import CoreAnswer

log = structlog.get_logger(__name__)


def _build_singular_field(
    field_kind: str, raw_text: str, catalog_ids: list[str], supporting_text: str,
    recognized_symbols: set[str], name_tokens: set[str],
) -> tuple[str, list[str], bool]:
    """Returns (final_text, evidence_refs, had_violation) for a field
    that must always carry SOME text — real (attributed to the whole
    evidence catalog gathered for this query, the only claim-to-evidence
    granularity V3's current output supports) or the field's fixed
    fallback string on any violation."""
    gated = language_gate.gate(field_kind, raw_text)
    if gated.had_violation:
        return gated.text, [], True
    if not raw_text:
        return "", [], False
    claim = citation_validator.validate_claim(
        raw_text, catalog_ids, set(catalog_ids), recognized_symbols, supporting_text, name_tokens,
    )
    if not claim.valid:
        fallback = language_gate.FALLBACK_TEXT.get(field_kind, language_gate.FALLBACK_TEXT["why_it_matters"])
        return fallback, [], True
    return raw_text, catalog_ids, False


def _build_list_field_texts(
    texts: list[str], catalog_ids: list[str], supporting_text: str,
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
            text, catalog_ids, set(catalog_ids), recognized_symbols, supporting_text, name_tokens,
        )
        if not claim.valid:
            continue
        kept.append(text)
    return kept


def assemble_aev2(core: CoreAnswer, *, mode: AEV2Mode) -> dict | None:
    """Returns a freshly-built answer_experience_v2 dict, or None if
    `mode` is OFF (assembly never runs — see mode.should_assemble) or if
    assembly raised (telemetered, then degraded to None). Reads only from
    `core`; never mutates it, never re-derives entities/evidence, never
    calls a provider."""
    if mode == AEV2Mode.OFF:
        return None

    _t0 = time.monotonic()
    stage_ms: dict[str, float] = {}
    try:
        catalog = citation_validator.build_evidence_catalog(core)
        catalog_ids = [c["id"] for c in catalog]
        supporting_text = " ".join(c["title"] for c in catalog if c.get("title"))
        recognized_symbols = {
            (c.get("symbol") or "").upper() for c in core.companies if c.get("symbol")
        }
        name_tokens = citation_validator.recognized_name_tokens(core.companies)
        stage_ms["catalog_build_ms"] = round((time.monotonic() - _t0) * 1000, 1)
        _t_stage = time.monotonic()

        any_violation = False

        dc_text, dc_refs, dc_violation = _build_singular_field(
            "direct_conclusion", core.bottom_line, catalog_ids, supporting_text, recognized_symbols, name_tokens,
        )
        any_violation = any_violation or dc_violation

        wh_text, wh_refs, wh_violation = _build_singular_field(
            "what_happened", core.what_happened, catalog_ids, supporting_text, recognized_symbols, name_tokens,
        )
        any_violation = any_violation or wh_violation

        wim_text, wim_refs, wim_violation = _build_singular_field(
            "why_it_matters", core.why_it_happened, catalog_ids, supporting_text, recognized_symbols, name_tokens,
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
            kept = _build_list_field_texts([text], catalog_ids, supporting_text, recognized_symbols, name_tokens)
            if kept:
                timeline_phases.append({"phase": phase, "text": kept[0]})

        risks = _build_list_field_texts(list(core.risks), catalog_ids, supporting_text, recognized_symbols, name_tokens)

        # Reuses the same catalog entries built above, rather than
        # re-deriving event shape a second time from core.related_events
        # — one source of truth for "what an event citation looks like."
        related_events = [
            {"id": c["id"], "title": c["title"], "date": c["date"]}
            for c in catalog if c["type"] == "event"
        ]

        confidence = compute_aev2_confidence(core, price_movement)
        stage_ms["restructuring_ms"] = round((time.monotonic() - _t_stage) * 1000, 1)

        response = schema.build_response(
            direct_conclusion={"text": dc_text, "evidence_refs": dc_refs},
            what_happened={"summary": wh_text, "evidence_refs": wh_refs, "items": []},
            why_it_matters={"text": wim_text, "evidence_refs": wim_refs, "is_fallback": wim_violation},
            companies_affected=price_movement,
            time_horizon={"primary_horizon": core.horizon, "timeline_phases": timeline_phases},
            risks_and_invalidation={"kind": "analysis", "risks": risks, "invalidates_if": [], "watch_for": []},
            evidence=catalog,
            related_intelligence={"opportunities": [], "events": related_events, "ripple": None},
            confidence=confidence,
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
