"""
CD3-C follow-up (2026-09-03) — narrow containment patch for a real public
provenance/integrity defect: GET /api/scenario/{type}/{id} used to return
generate_scenario_analysis()'s raw dict unfiltered, including full
bull/base/bear content from its `degraded: True` fallback template
(identical boilerplate for every entity -- "Strong performance for
{title} driven by favourable macro conditions... 25-40% returns"). The
consolidated Deep Research path already checked `degraded` correctly;
this standalone route did not, and ScenarioAnalysis.tsx (confirmed live
on the real Ripple page) only checked whether bull/base/bear keys
existed -- true for both real and fallback content.

This suite exercises the REAL route through TestClient (the actual
public contract boundary), mocking only generate_scenario_analysis's
return value -- the exact chain the CD3-C review named:

    provider failure -> degraded/fallback result -> GET /api/scenario/{type}/{id}
    -> serialized response -> ScenarioAnalysis consumer

Per the CD3-C review's explicit ask, this does NOT rely on the frontend
"remembering" not to render fallback content -- the backend nulls
bull/base/bear whenever content isn't genuinely generated, so there's
nothing left to accidentally display.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

# The exact live fallback specimen (ai_service.py's own template text,
# verbatim) -- must never appear in a real API response.
_FALLBACK_SPECIMEN_PHRASES = [
    "driven by favourable macro conditions",
    "25–40% returns",
    "25-40% returns",
]


def _real_scenario_payload() -> dict:
    return {
        "bull": {"probability": 30, "outcome": "Strong outperformance driven by real catalysts.", "confidence": 65},
        "base": {"probability": 50, "outcome": "Meets consensus expectations.", "confidence": 70},
        "bear": {"probability": 20, "outcome": "Underperformance due to real headwinds.", "confidence": 60},
        "last_updated": "2026-09-03T05:00:00+00:00",
    }


def _degraded_fallback_payload(title: str = "Test Entity") -> dict:
    # Reproduces ai_service.py's real fallback template shape/content.
    return {
        "degraded": True,
        "bull": {
            "probability": 30,
            "outcome": f"Strong performance for {title} driven by favourable macro conditions, sector tailwinds, and above-consensus delivery.",
            "supporting_evidence": "Historical setups with similar macro alignment have produced 25–40% returns over 12 months.",
            "confidence": 60,
        },
        "base": {"probability": 50, "outcome": f"In-line performance for {title}.", "confidence": 70},
        "bear": {"probability": 20, "outcome": f"Underperformance for {title}.", "confidence": 55},
        "last_updated": "2026-09-03T05:00:00+00:00",
    }


def _empty_payload() -> dict:
    # Total provider failure with no parseable response at all -- the
    # route must not assume `degraded` is always present.
    return {}


@pytest.mark.asyncio
async def test_real_generated_scenario_is_publicly_available():
    with patch("app.api.scenario.generate_scenario_analysis", new=AsyncMock(return_value=_real_scenario_payload())):
        resp = client.get("/api/scenario/event/test-real-1?title=Test+Entity")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "available"
    assert body["provenance"] == "generated"
    assert body["degraded"] is False
    assert body["bull"]["outcome"] == "Strong outperformance driven by real catalysts."
    assert body["base"] is not None
    assert body["bear"] is not None


@pytest.mark.asyncio
async def test_degraded_fallback_is_publicly_unavailable_not_leaked():
    with patch("app.api.scenario.generate_scenario_analysis", new=AsyncMock(return_value=_degraded_fallback_payload("Test Entity"))):
        resp = client.get("/api/scenario/event/test-degraded-1?title=Test+Entity")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "unavailable"
    assert body["provenance"] == "fallback"
    assert body["degraded"] is True
    assert body["bull"] is None
    assert body["base"] is None
    assert body["bear"] is None


@pytest.mark.asyncio
async def test_missing_generation_total_failure_is_unavailable():
    """No `degraded` key at all, no bull/base/bear -- a total provider
    failure the service function couldn't even wrap in its own fallback
    template. The route must not assume `degraded` is always set."""
    with patch("app.api.scenario.generate_scenario_analysis", new=AsyncMock(return_value=_empty_payload())):
        resp = client.get("/api/scenario/event/test-empty-1?title=Test+Entity")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "unavailable"
    assert body["provenance"] == "unavailable"  # not "fallback" -- degraded was never set
    assert body["degraded"] is False
    assert body["bull"] is None
    assert body["base"] is None
    assert body["bear"] is None


@pytest.mark.asyncio
async def test_degraded_true_never_coexists_with_renderable_content():
    """Property check across several degraded-shaped inputs: whenever
    degraded is True (or content is incomplete), the public response's
    bull/base/bear must ALL be None -- never a partial leak."""
    cases = [
        _degraded_fallback_payload("Entity A"),
        {"degraded": True, "bull": {"probability": 30, "outcome": "x"}},  # partial -- missing base/bear
        {"degraded": True},  # degraded with nothing else at all
        {"bull": {"probability": 30, "outcome": "x"}},  # not degraded, but incomplete (no base/bear)
    ]
    for raw in cases:
        with patch("app.api.scenario.generate_scenario_analysis", new=AsyncMock(return_value=raw)):
            resp = client.get("/api/scenario/event/test-property-1?title=Entity")
        body = resp.json()
        if body["degraded"] or body["status"] != "available":
            assert body["bull"] is None, f"leaked bull for input {raw!r}"
            assert body["base"] is None, f"leaked base for input {raw!r}"
            assert body["bear"] is None, f"leaked bear for input {raw!r}"


@pytest.mark.asyncio
async def test_exact_live_fallback_specimen_cannot_appear_in_response():
    """The exact live boilerplate text (ai_service.py's own template,
    verbatim phrases) must never appear anywhere in a real API response,
    regardless of which entity/title triggered it."""
    with patch("app.api.scenario.generate_scenario_analysis", new=AsyncMock(return_value=_degraded_fallback_payload("RELIANCE"))):
        resp = client.get("/api/scenario/company/test-reliance-1?title=RELIANCE")
    raw_text = resp.text
    for phrase in _FALLBACK_SPECIMEN_PHRASES:
        assert phrase not in raw_text, f"leaked fallback specimen phrase: {phrase!r}"


@pytest.mark.asyncio
async def test_last_updated_still_surfaces_even_when_unavailable():
    """Non-content metadata (last_updated) is not itself sensitive --
    confirms the containment is scoped to bull/base/bear specifically,
    not an overly broad response wipe."""
    with patch("app.api.scenario.generate_scenario_analysis", new=AsyncMock(return_value=_degraded_fallback_payload())):
        resp = client.get("/api/scenario/event/test-metadata-1?title=Entity")
    body = resp.json()
    assert body["last_updated"] == "2026-09-03T05:00:00+00:00"
