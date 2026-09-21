"""
AEV2 assembly — a deterministic PRESENTER over the one canonical
CoreAnswer (see app/services/ai_search/core_answer.py), never a second
reasoning pipeline. Architecture decision (2026-09-21): this module must
never call an LLM, retrieve evidence, resolve entities, run a fallback
chain, or maintain its own degraded-response logic — every one of those
already happened once, upstream, to produce the CoreAnswer this function
reads from.

Takes a `CoreAnswer` — the same frozen, immutable object the V3 dict
presenter's own fields were themselves read from — never a raw response
dict, so there is no way for this presenter to diverge from what the
other presenter shows for the same request. Never mutates the CoreAnswer
(the type is frozen, so this is enforced, not just documented).

Foundation-slice scope: only `direct_conclusion` carries real content — a
fail-closed pass-through of `core.bottom_line` through the
recommendation-language gate. Every other field is the schema's honest
empty default; see schema.py's own docstring for what's deferred to the
next slice (response restructuring and citations).

Backward-compatible fallback: any exception here is caught, telemetered
with a specific failure_reason, and this function returns None — the
caller's contract (never attach `answer_experience_v2` on None) then
degrades exactly like AEV2 being OFF, never a 500.
"""
from __future__ import annotations

import time

import structlog

from app.services.ai_search.aev2 import language_gate, schema, telemetry
from app.services.ai_search.aev2.mode import AEV2Mode
from app.services.ai_search.core_answer import CoreAnswer

log = structlog.get_logger(__name__)


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
        gated = language_gate.gate("direct_conclusion", core.bottom_line)
        stage_ms["language_gate_ms"] = round((time.monotonic() - _t0) * 1000, 1)

        response = schema.build_response(
            direct_conclusion={"text": gated.text, "evidence_refs": []},
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
        had_language_violation=gated.had_violation,
        is_fallback=gated.had_violation,
        stage_ms=stage_ms,
    )
    return response
