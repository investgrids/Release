"""
Runtime proof of the "one canonical AI-answer pipeline" invariant
(2026-09-21 architecture decision + its 2026-09-21 follow-up correction).

Static call-site counting (test_ai_search_consolidation.py) proves the
CODE only has one call site in each place that matters. It cannot prove
that a real run_ai_search_v3() invocation actually EXERCISES each of
those call sites exactly once at runtime — that's this file's job.

Mocks exactly 3 stage boundaries (entity resolution, evidence retrieval,
the routed specialist's own run()) plus the prediction-recording sink —
no live provider, no live DB fixture beyond the same AsyncSessionLocal()
every other live pipeline test in this suite already uses. "One
specialist/fallback orchestration invocation" means one call to the
routed specialist's run() — the fallback chain INSIDE that call may
legitimately contact several providers before one answers; that's not
counted here (see ai_service.py's own cooldown/fallback tests for that
layer), consistent with the 2026-09-21 correction that clarified this.

Every test uses its own unique query text (uuid-suffixed) so this
module's mocked runs never collide with another test's real cache entry
— cache.py's Layer 1 key is the normalized query text alone.
"""
from __future__ import annotations

import asyncio
import uuid

import pytest

from app.db.session import AsyncSessionLocal
from app.services.ai_search import cache as cache_mod
from app.services.ai_search import entities as entities_mod
from app.services.ai_search import evidence as evidence_mod
from app.services.ai_search.aev2 import mode as mode_mod
from app.services.ai_search.core_answer import from_v3_response
from app.services.ai_search.evidence import EvidenceBundle
from app.services.ai_search.pipeline import run_ai_search_v3
from app.services.ai_search.response_finalize import finalize_v3_response
from app.services.ai_search.specialists import company as company_specialist

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def _isolated_cache(monkeypatch):
    """cache.py's Layer 2 (semantic) key is derived from resolved
    entities/intent, not raw query text — and every test in this module
    mocks entity resolution to the SAME fixed entities dict. Without this,
    tests would silently share one semantic cache entry across the whole
    module (a uuid-suffixed query text is only enough to dodge the Layer 1
    exact-key cache, not Layer 2). A fresh _CACHE per test makes each
    test's own cache behavior fully self-contained."""
    monkeypatch.setattr(cache_mod, "_CACHE", {})


def _unique_query(label: str) -> str:
    return f"Should I invest in Reliance Industries? (pytest-{label}-{uuid.uuid4().hex[:8]})"


_ENTITIES = {
    "companies": ["RELIANCE"],
    "company_matches": [{"symbol": "RELIANCE", "name": "Reliance Industries Ltd", "match_type": "exact"}],
    "sectors": [], "policies": [],
}


def _counting_stub_entities():
    calls = {"n": 0}

    def _extract(query: str) -> dict:
        calls["n"] += 1
        return dict(_ENTITIES)

    return _extract, calls


def _counting_stub_evidence():
    calls = {"n": 0}

    async def _collect(query, intent_data, entities, db):
        calls["n"] += 1
        return EvidenceBundle()

    return _collect, calls


def _counting_stub_specialist(parsed: dict, was_degraded: bool):
    calls = {"n": 0}

    async def _run(query, evidence, intent_data, entities):
        calls["n"] += 1
        return dict(parsed), was_degraded

    return _run, calls


def _counting_stub_predictions():
    calls = {"n": 0, "args": []}

    async def _store(*, result, confidence_score, confidence_level, confidence_breakdown):
        calls["n"] += 1
        calls["args"].append(result.get("query"))

    return _store, calls


_CLEAN_PARSED = {
    "summary": "Reliance Industries reported strong quarterly results.",
    "bottom_line": "Reliance Industries reported strong quarterly results.",
    "companies": [],  # empty — keeps _enrich_sync's live market-data fetch from ever running
    "sectors": [],
    "investment_verdict": {"direction": "bullish", "confidence": 70, "horizon": "1 month"},
}

_ADVISORY_PARSED = {
    **_CLEAN_PARSED,
    "bottom_line": "Reliance Industries remains a solid buy candidate.",
}


async def _drain_background_tasks() -> None:
    """asyncio.create_task schedules but does not run a task inline —
    yield control a few times so a fire-and-forget prediction-store task
    actually completes before a test inspects its counter."""
    for _ in range(5):
        await asyncio.sleep(0)


async def _run_fresh(query: str, parsed: dict, was_degraded: bool, aev2_mode: str, monkeypatch, x_admin_key=None):
    extract, entity_calls = _counting_stub_entities()
    collect, evidence_calls = _counting_stub_evidence()
    run, specialist_calls = _counting_stub_specialist(parsed, was_degraded)
    store, prediction_calls = _counting_stub_predictions()

    monkeypatch.setattr(entities_mod, "extract_entities", extract)
    monkeypatch.setattr(evidence_mod, "collect", collect)
    monkeypatch.setattr(company_specialist, "run", run)
    monkeypatch.setattr("app.services.ai_search.prediction_recording.store_search_predictions", store)

    from app.core.config import settings
    monkeypatch.setattr(settings, "ai_search_aev2_mode", aev2_mode)
    monkeypatch.setattr(mode_mod, "AEV2_BUILD_COMPLETE", True)
    monkeypatch.setattr(settings, "admin_api_key", "real-secret")

    async with AsyncSessionLocal() as db:
        result, was_cached = await run_ai_search_v3(query, db, None)

    final = finalize_v3_response(query, result, x_admin_key=x_admin_key, was_cached=was_cached)
    await _drain_background_tasks()

    return {
        "result": result, "was_cached": was_cached, "final": final,
        "entity_calls": entity_calls, "evidence_calls": evidence_calls,
        "specialist_calls": specialist_calls, "prediction_calls": prediction_calls,
    }


# ── One entity/evidence/specialist call per fresh request, across every mode ──

@pytest.mark.parametrize("aev2_mode", ["off", "shadow", "canary", "public"])
async def test_fresh_request_makes_exactly_one_call_at_each_stage_boundary(monkeypatch, aev2_mode):
    query = _unique_query(f"fresh-{aev2_mode}")
    ctx = await _run_fresh(query, _CLEAN_PARSED, was_degraded=False, aev2_mode=aev2_mode, monkeypatch=monkeypatch, x_admin_key="real-secret")

    assert ctx["entity_calls"]["n"] == 1, f"expected exactly 1 entity-resolution call, got {ctx['entity_calls']['n']}"
    assert ctx["evidence_calls"]["n"] == 1, f"expected exactly 1 evidence-retrieval call, got {ctx['evidence_calls']['n']}"
    assert ctx["specialist_calls"]["n"] == 1, f"expected exactly 1 specialist call, got {ctx['specialist_calls']['n']}"
    assert not ctx["was_cached"]


# ── Cache hit: zero new resolution/retrieval/specialist/prediction work ────

async def test_cache_hit_performs_zero_new_work_at_any_stage_boundary(monkeypatch):
    query = _unique_query("cachehit")

    # First call — fresh, populates the cache (mode=off keeps this focused
    # purely on the resolution/evidence/specialist/prediction invariant).
    first = await _run_fresh(query, _CLEAN_PARSED, was_degraded=False, aev2_mode="off", monkeypatch=monkeypatch)
    assert first["entity_calls"]["n"] == 1
    assert first["specialist_calls"]["n"] == 1
    assert first["prediction_calls"]["n"] == 1, "fresh clean response should record exactly one prediction pass"

    # Second call, same exact query text — Layer 1 exact-key cache hit,
    # checked in _run_v3_steps BEFORE entity resolution even runs. Fresh
    # stubs + fresh counters so any call at all is unambiguous.
    extract, entity_calls = _counting_stub_entities()
    collect, evidence_calls = _counting_stub_evidence()
    run, specialist_calls = _counting_stub_specialist(_CLEAN_PARSED, False)
    store, prediction_calls = _counting_stub_predictions()
    monkeypatch.setattr(entities_mod, "extract_entities", extract)
    monkeypatch.setattr(evidence_mod, "collect", collect)
    monkeypatch.setattr(company_specialist, "run", run)
    monkeypatch.setattr("app.services.ai_search.prediction_recording.store_search_predictions", store)

    async with AsyncSessionLocal() as db:
        result2, was_cached2 = await run_ai_search_v3(query, db, None)
    assert was_cached2, "second call with identical query text should be a cache hit"

    finalize_v3_response(query, result2, was_cached=was_cached2)
    await _drain_background_tasks()

    assert entity_calls["n"] == 0, "cache hit must not re-run entity resolution"
    assert evidence_calls["n"] == 0, "cache hit must not re-run evidence retrieval"
    assert specialist_calls["n"] == 0, "cache hit must not re-invoke the specialist"
    assert prediction_calls["n"] == 0, "cache hit must not record a second prediction for the same answer"


# ── Prediction recording: fresh+clean=1, degraded=0, gate-rejected=0 ───────

async def test_degraded_specialist_response_records_zero_predictions(monkeypatch):
    query = _unique_query("degraded")
    degraded_parsed = {"_degraded_reason": "parse_failure"}
    ctx = await _run_fresh(query, degraded_parsed, was_degraded=True, aev2_mode="off", monkeypatch=monkeypatch)

    assert ctx["result"]["synthesis_incomplete"] is True
    assert ctx["result"]["degraded_reason"] == "parse_failure"
    assert ctx["prediction_calls"]["n"] == 0, "a genuinely failed synthesis must record zero predictions"
    # Uses the one shared skeleton — see degraded_shape.build_degraded_shape.
    from app.services.ai_search.degraded_shape import build_degraded_shape
    assert set(ctx["result"].keys()) >= set(build_degraded_shape(
        query="q", response_id=None, schema_version=None, specialist_kind=None,
        degraded_reason=None, summary="s",
    ).keys()) - {"query", "response_id", "schema_version", "specialist"}


async def test_language_gate_rejection_records_zero_predictions_and_uses_shared_builder(monkeypatch):
    query = _unique_query("advisory")
    ctx = await _run_fresh(query, _ADVISORY_PARSED, was_degraded=False, aev2_mode="off", monkeypatch=monkeypatch)

    # Pipeline-level result is clean (was_degraded=False) — the specialist
    # itself didn't fail, only its generated prose is unsafe.
    assert not ctx["result"].get("synthesis_incomplete")
    # The gate, running downstream in finalize_v3_response, is what catches it.
    assert ctx["final"]["synthesis_incomplete"] is True
    assert ctx["final"]["degraded_reason"] == "recommendation_language_violation"
    assert ctx["prediction_calls"]["n"] == 0, "a language-gate rejection must record zero predictions"

    from app.services.ai_search.degraded_shape import build_degraded_shape
    skeleton_keys = set(build_degraded_shape(
        query="q", response_id=None, schema_version=None, specialist_kind=None,
        degraded_reason=None, summary="s",
    ).keys())
    assert set(ctx["final"].keys()) == skeleton_keys


async def test_fresh_clean_response_records_exactly_one_prediction(monkeypatch):
    query = _unique_query("cleanpred")
    ctx = await _run_fresh(query, _CLEAN_PARSED, was_degraded=False, aev2_mode="off", monkeypatch=monkeypatch)
    assert ctx["prediction_calls"]["n"] == 1
    assert ctx["prediction_calls"]["args"] == [query]


# ── Both presenters receive the same CoreAnswer; AEV2 never touches the
#    entity/evidence/specialist call sites — proven at runtime, not just
#    via the static import scan. ─────────────────────────────────────────

@pytest.mark.parametrize("aev2_mode", ["shadow", "canary", "public"])
async def test_aev2_presenter_never_bumps_any_pipeline_call_counter(monkeypatch, aev2_mode):
    query = _unique_query(f"aev2counters-{aev2_mode}")
    ctx = await _run_fresh(query, _CLEAN_PARSED, was_degraded=False, aev2_mode=aev2_mode, monkeypatch=monkeypatch, x_admin_key="real-secret")

    # finalize_v3_response (called inside _run_fresh) already ran AEV2
    # assembly for every mode except off. If assemble_aev2 had somehow
    # called through to a provider, entity resolver, or evidence
    # collector, these counts would be >1 — they must still read exactly
    # the single fresh-request call recorded before AEV2 ever ran.
    assert ctx["entity_calls"]["n"] == 1
    assert ctx["evidence_calls"]["n"] == 1
    assert ctx["specialist_calls"]["n"] == 1


async def test_both_presenters_derive_from_the_identical_core_answer_at_runtime(monkeypatch):
    query = _unique_query("samecore")
    extract, _ = _counting_stub_entities()
    collect, _ = _counting_stub_evidence()
    run, _ = _counting_stub_specialist(_CLEAN_PARSED, False)
    store, _ = _counting_stub_predictions()
    monkeypatch.setattr(entities_mod, "extract_entities", extract)
    monkeypatch.setattr(evidence_mod, "collect", collect)
    monkeypatch.setattr(company_specialist, "run", run)
    monkeypatch.setattr("app.services.ai_search.prediction_recording.store_search_predictions", store)

    from app.core.config import settings
    monkeypatch.setattr(settings, "ai_search_aev2_mode", "public")
    monkeypatch.setattr(mode_mod, "AEV2_BUILD_COMPLETE", True)

    captured: dict = {}
    real_assemble = __import__(
        "app.services.ai_search.aev2.assemble", fromlist=["assemble_aev2"],
    ).assemble_aev2

    def spy_assemble(core, *, mode):
        captured["core"] = core
        return real_assemble(core, mode=mode)

    monkeypatch.setattr("app.services.ai_search.response_finalize.assemble_aev2", spy_assemble)

    async with AsyncSessionLocal() as db:
        result, was_cached = await run_ai_search_v3(query, db, None)
    final = finalize_v3_response(query, result, was_cached=was_cached)
    await _drain_background_tasks()

    # The V3 presenter IS `final` itself (minus answer_experience_v2); the
    # AEV2 presenter derived from `captured["core"]`. Both must trace back
    # to the identical projection of the same post-gate response.
    v3_only = {k: v for k, v in final.items() if k != "answer_experience_v2"}
    assert captured["core"] == from_v3_response(v3_only)
    assert "answer_experience_v2" in final
