"""
AEV2 assembly — the cache-safe integration point (spec §"Implementation
contract", errata operational criteria).

Called with the FINAL V3 response dict — after `run_ai_search_v3` has
already resolved a cache hit or a fresh computation, in
app/api/ai_search.py — never the object passed into
cache_mod.set_response, and never mutated in place here or by the caller
(the caller must build a new dict via `{**v3_response, ...}` when
attaching this function's result, never assign into `v3_response`
directly). This is what "assemble AEV2 only after cache retrieval" means
structurally: a cached V3 core response replayed on a later cache hit is
bit-for-bit identical to a fresh computation, and AEV2 is computed fresh
by this function on every call regardless of how the caller obtained
`v3_response`.

Foundation-slice scope: only `direct_conclusion` carries real content — a
fail-closed pass-through of `answer.bottom_line` through the
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

log = structlog.get_logger(__name__)


def assemble_aev2(query: str, v3_response: dict, *, mode: AEV2Mode) -> dict | None:
    """Returns a freshly-built answer_experience_v2 dict, or None if
    `mode` is OFF (assembly never runs — see mode.should_assemble) or if
    assembly raised (telemetered, then degraded to None). Never mutates
    `v3_response`; only reads from it."""
    if mode == AEV2Mode.OFF:
        return None

    _t0 = time.monotonic()
    stage_ms: dict[str, float] = {}
    try:
        answer = (v3_response or {}).get("answer") or {}
        bottom_line = answer.get("bottom_line") or ""
        gated = language_gate.gate("direct_conclusion", bottom_line)
        stage_ms["language_gate_ms"] = round((time.monotonic() - _t0) * 1000, 1)

        response = schema.build_response(
            direct_conclusion={"text": gated.text, "evidence_refs": []},
        )
    except Exception as exc:
        stage_ms["failed_after_ms"] = round((time.monotonic() - _t0) * 1000, 1)
        log.warning("ai_search.aev2_assembly_exception", exc=str(exc)[:160])
        telemetry.emit_assembly_failed(
            query=query, mode=mode.value, failure_reason="assembly_exception", stage_ms=stage_ms,
        )
        return None

    telemetry.emit_assembly_success(
        query=query,
        mode=mode.value,
        response_id=(v3_response or {}).get("response_id"),
        had_language_violation=gated.had_violation,
        is_fallback=gated.had_violation,
        stage_ms=stage_ms,
    )
    return response
