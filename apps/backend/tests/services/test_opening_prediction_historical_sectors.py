"""
opening_prediction_service._gather_historical's sector-population fix
(2026-08 Pre-Market rebuild, Part A3).

Before this fix, query["sectors"] was never set, so
compute_similarity()'s largest single factor (sector Jaccard, 25/100 pts)
contributed ~0 on almost every call. This confirms the fix: non-stable
theme names (lightly split on "&"/"/") flow into the historical query,
and a read failure degrades gracefully (sectors simply omitted, exactly
today's pre-fix behavior) rather than raising.
"""
from __future__ import annotations

import pytest

from app.services import opening_prediction_service as ops


def _signals(global_label: str = "Mixed", crude_dir: str = "stable") -> dict:
    return {
        "global_sentiment": {"label": global_label},
        "crude_trend": crude_dir,
    }


@pytest.mark.asyncio
async def test_sectors_populated_from_non_stable_themes(monkeypatch):
    async def fake_read_themes():
        return [
            {"theme": "Banking", "momentum": "stable"},
            {"theme": "Auto & EV", "momentum": "falling"},
            {"theme": "Real Estate", "momentum": "rising"},
        ]

    captured_query = {}

    async def fake_find_similar_events(query, limit, min_similarity):
        captured_query.update(query)
        return []

    monkeypatch.setattr("app.services.intelligence.engine.read_themes", fake_read_themes)
    monkeypatch.setattr(
        "app.services.historical_memory_service.find_similar_events", fake_find_similar_events
    )

    await ops._gather_historical(_signals(), {"today": [], "tomorrow": []})

    assert "sectors" in captured_query
    # "Banking" is stable -> excluded. "Auto & EV" and "Real Estate" are
    # not stable -> included, with "Auto & EV" also split into parts.
    assert "Banking" not in captured_query["sectors"]
    assert "Auto & EV" in captured_query["sectors"]
    assert "Auto" in captured_query["sectors"]
    assert "EV" in captured_query["sectors"]
    assert "Real Estate" in captured_query["sectors"]


@pytest.mark.asyncio
async def test_sectors_omitted_when_all_themes_stable(monkeypatch):
    async def fake_read_themes():
        return [{"theme": "Banking", "momentum": "stable"}]

    captured_query = {}

    async def fake_find_similar_events(query, limit, min_similarity):
        captured_query.update(query)
        return []

    monkeypatch.setattr("app.services.intelligence.engine.read_themes", fake_read_themes)
    monkeypatch.setattr(
        "app.services.historical_memory_service.find_similar_events", fake_find_similar_events
    )

    await ops._gather_historical(_signals(), {"today": [], "tomorrow": []})

    assert "sectors" not in captured_query


@pytest.mark.asyncio
async def test_gracefully_omits_sectors_on_theme_read_failure(monkeypatch):
    async def failing_read_themes():
        raise RuntimeError("redis unavailable")

    captured_query = {}

    async def fake_find_similar_events(query, limit, min_similarity):
        captured_query.update(query)
        return []

    monkeypatch.setattr("app.services.intelligence.engine.read_themes", failing_read_themes)
    monkeypatch.setattr(
        "app.services.historical_memory_service.find_similar_events", fake_find_similar_events
    )

    result = await ops._gather_historical(_signals(), {"today": [], "tomorrow": []})

    assert "sectors" not in captured_query
    assert result["count"] == 0
