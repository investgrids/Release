"""
Fail-closed degraded-mode gate (2026-09-21) — app/services/ai_search/pipeline.py.

Real defect found live: when specialist.run() genuinely failed to synthesize
(was_degraded=True, e.g. every AI provider exhausted), the response still
flowed through _assemble_response()'s full analytical machinery. A real,
evidence-derived confidence score and a real engine_verdict got computed and
attached right next to base.py's hardcoded "Neutral / 6-12 months / Macro
uncertainty / Policy clarity" degraded stub — a shell with no relation to
the actual query. The rendered page admitted "synthesis failed" in one
sentence while presenting a fully-dressed verdict, confidence %, horizon,
risk level, and scenarios two sections below it (reproduced live on a
"Should I invest in HDFC Bank?" query: unrelated Sensex/FII news shown as
supporting evidence, a fabricated "Neutral"/"6-12 months" verdict next to a
real-but-irreconcilable "Cautious"/"down" engine_verdict, and the LLM's own
default confidence_self_rating=5 dressed up as "AI Reasoning 50%").

These tests assert the fix: _assemble_response short-circuits to
_build_degraded_response() before any enrichment/graph/confidence/engine
computation runs, and that builder never emits a verdict, confidence score,
horizon, risk level, scenario, or engine_verdict — only real evidence
deterministically tied to the query's own resolved company.
"""
from __future__ import annotations

import pytest

from app.services.ai_search import pipeline
from app.services.ai_search.evidence import EvidenceBundle


def _event(id_: str, title: str, companies: list[dict]) -> dict:
    return {"id": id_, "slug": id_, "title": title, "summary": title, "category": "Market",
            "impact_score": 60.0, "confidence": 65.0, "sectors": [], "companies": companies,
            "date": "Sep 20, 2026"}


# ── _filter_events_to_entities: the one real, deterministic evidence link ──

def test_filter_events_keeps_only_events_tagged_with_the_resolved_symbol():
    events = [
        _event("e1", "HDFC Bank Q1 results", [{"symbol": "HDFCBANK", "name": "HDFC Bank"}]),
        _event("e2", "Unrelated Shiprocket funding round", [{"symbol": "SHIPROCKET", "name": "Shiprocket"}]),
        _event("e3", "RBI holds repo rate", [{"symbol": "HDFCBANK", "name": "HDFC Bank"}, {"symbol": "ICICIBANK", "name": "ICICI Bank"}]),
    ]
    result = pipeline._filter_events_to_entities(events, ["HDFCBANK"])
    assert {e["id"] for e in result} == {"e1", "e3"}


def test_filter_events_returns_nothing_when_no_symbol_resolved():
    events = [_event("e1", "Some event", [{"symbol": "HDFCBANK", "name": "HDFC Bank"}])]
    assert pipeline._filter_events_to_entities(events, []) == []


def test_filter_events_ignores_events_with_no_companies_field():
    events = [_event("e1", "No company tag", [])]
    assert pipeline._filter_events_to_entities(events, ["HDFCBANK"]) == []


# ── _build_degraded_response: the honest shape ──────────────────────────────

def _degraded_ai_stub(query: str) -> dict:
    """Mirrors base.py's real degraded_response() shape — the fabricated
    stub this fix must never let leak through unchanged."""
    return {
        "summary": f"Market intelligence analysis for: {query}.",
        "bottom_line": "There isn't enough freshly generated analysis to answer with confidence right now.",
        "confidence_self_rating": 5,
        "investment_verdict": {
            "rating": "Neutral", "direction": "neutral", "confidence": 40,
            "horizon": "6-12 months", "top_picks": [],
            "risks": ["Macro uncertainty"], "catalysts": ["Policy clarity"],
            "opportunity_score": 50,
        },
        "scenarios": {}, "decision_engine_v2": {
            "verdict_scale": "Neutral", "why": "Synthesis step did not complete.",
        },
        "_degraded_reason": "capacity",
    }


def test_degraded_response_has_no_verdict_confidence_horizon_or_risk_level():
    ai = _degraded_ai_stub("Should I invest in HDFC Bank?")
    bundle = EvidenceBundle(events=[_event("e1", "HDFC Bank news", [{"symbol": "HDFCBANK", "name": "HDFC Bank"}])])
    result = pipeline._build_degraded_response(
        "Should I invest in HDFC Bank?", ai, bundle, "company", "capacity",
        {"companies": ["HDFCBANK"]}, "resp-1",
    )

    verdict = result["investment_verdict"]
    assert verdict["rating"] == "Not Applicable"
    assert verdict["confidence"] is None
    assert verdict["horizon"] is None
    assert verdict["risk_level"] == ""
    assert verdict["suitable_for"] == ""
    assert verdict["engine_verdict"] is None
    assert result["answer"]["confidence"] is None
    assert result["answer"]["confidence_level"] == "unscored"
    assert result["confidence_data"]["score"] is None
    assert result["scenarios"] == {}
    assert result["monitoring"] == {"items": []}
    assert result["decision_engine_v2"] == {}
    assert result["graph"] == {"nodes": [], "edges": []}
    assert result["ripple_chain"] == []
    assert result["historical_comparison"] == []


def test_degraded_response_marks_itself_as_synthesis_incomplete():
    ai = _degraded_ai_stub("query")
    bundle = EvidenceBundle()
    result = pipeline._build_degraded_response("query", ai, bundle, "company", "capacity", {}, "resp-2")
    assert result["synthesis_incomplete"] is True
    assert result["degraded_reason"] == "capacity"


def test_degraded_response_shows_only_entity_matched_events_never_news_or_policy():
    ai = _degraded_ai_stub("Should I invest in HDFC Bank?")
    bundle = EvidenceBundle(
        events=[
            _event("e1", "HDFC Bank event", [{"symbol": "HDFCBANK", "name": "HDFC Bank"}]),
            _event("e2", "Unrelated GE Vernova event", [{"symbol": "GEVERNOVA", "name": "GE Vernova"}]),
        ],
        news=[{"id": "n1", "headline": "Gold eases on inflation woes"}],
        policies=[{"id": "p1", "title": "Some unrelated policy"}],
    )
    result = pipeline._build_degraded_response(
        "Should I invest in HDFC Bank?", ai, bundle, "company", "capacity",
        {"companies": ["HDFCBANK"]}, "resp-3",
    )

    assert [e["id"] for e in result["related_events"]] == ["e1"]
    assert result["news"] == []       # no company field exists on news rows — never shown as related
    assert result["policies"] == []   # same reasoning
    assert result["answer"]["sources_count"] == 1
    assert result["source_attribution"] == ["event:e1"]


def test_degraded_response_says_so_honestly_when_no_relevant_evidence_survives():
    ai = _degraded_ai_stub("Should I invest in HDFC Bank?")
    bundle = EvidenceBundle(events=[_event("e1", "Unrelated event", [{"symbol": "OTHERCO", "name": "Other Co"}])])
    result = pipeline._build_degraded_response(
        "Should I invest in HDFC Bank?", ai, bundle, "company", "capacity",
        {"companies": ["HDFCBANK"]}, "resp-4",
    )
    assert result["related_events"] == []
    assert result["answer"]["sources_count"] == 0
    # Still an honest, real message — not padded with fabricated content.
    bottom_line = result["answer"]["bottom_line"].lower()
    assert "isn't enough" in bottom_line or "wasn't available" in bottom_line or "didn't complete" in bottom_line


# ── _assemble_response: the gate actually fires before any analysis runs ───

async def test_assemble_response_short_circuits_on_degraded_without_touching_db_or_enrichment(monkeypatch):
    """was_degraded=True must never reach the enrichment/graph/confidence/
    engine_verdict block below the gate — asserted by passing db=None (a
    real AsyncSession would be required past the gate) and by confirming
    postprocess.compute_confidence_breakdown is never even called."""
    from app.services.ai_search import postprocess

    called = {"confidence_breakdown": False}

    async def _fail_if_called(*args, **kwargs):
        called["confidence_breakdown"] = True
        raise AssertionError("compute_confidence_breakdown must not run for a degraded response")

    monkeypatch.setattr(postprocess, "compute_confidence_breakdown", _fail_if_called)

    ai = _degraded_ai_stub("Should I invest in HDFC Bank?")
    bundle = EvidenceBundle(events=[_event("e1", "HDFC Bank event", [{"symbol": "HDFCBANK", "name": "HDFC Bank"}])])

    result = await pipeline._assemble_response(
        "Should I invest in HDFC Bank?", ai, bundle, "company",
        was_degraded=True, validation_report=None, db=None,
        entities={"companies": ["HDFCBANK"]},
    )

    assert called["confidence_breakdown"] is False
    assert result["synthesis_incomplete"] is True
    assert result["investment_verdict"]["rating"] == "Not Applicable"
    assert result["related_events"][0]["id"] == "e1"
