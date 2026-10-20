"""
Provenance contract -- prompt-builder remediation, Path 2 (2026-10-19):
story_engine.py's _fetch_context() feeds a persisted (MarketStory) and
Redis-cached market narrative, reused downstream by engine.py's
"ai_synthesis" Biggest Risk fallback and continuous_updater.py's
mie_context["story"]. A rule_based_fallback/unknown event's one_liner
must never enter that analytical context.
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import delete

from app.db.session import AsyncSessionLocal
from app.db.models.intelligence import EventTriage
from app.services.intelligence.engine import _derive_biggest_risk
from app.services.intelligence.story_engine import _fetch_context, _generate

_IDS = ["story-prov-fallback-1", "story-prov-ai-1", "story-prov-unknown-1"]


async def _cleanup():
    async with AsyncSessionLocal() as db:
        await db.execute(delete(EventTriage).where(EventTriage.event_id.in_(_IDS)))
        await db.commit()


async def _seed(*rows: tuple[str, str]):
    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db:
        for event_id, triage_source in rows:
            db.add(EventTriage(
                id=f"t-{event_id}", event_id=event_id, source="news",
                headline=f"Headline for {event_id}", urgency=8, importance=6, confidence=5,
                one_liner=f"One-liner for {event_id}", triage_source=triage_source,
                triaged_at=now,
            ))
        await db.commit()


@pytest.mark.asyncio
async def test_fetch_context_excludes_fallback_and_unknown_events():
    await _cleanup()
    try:
        await _seed(
            (_IDS[0], "rule_based_fallback"),
            (_IDS[1], "ai"),
            (_IDS[2], "unknown"),
        )
        with patch("app.services.market_data.get_extended_indices", new=AsyncMock(return_value=[])), \
             patch("app.services.market_data.get_sector_changes", new=AsyncMock(return_value=[])):
            ctx = await _fetch_context()
        bullets = "\n".join(ctx["recent_events"])
        assert "One-liner for story-prov-ai-1" in bullets
        assert "story-prov-fallback-1" not in bullets
        assert "story-prov-unknown-1" not in bullets
    finally:
        await _cleanup()


@pytest.mark.asyncio
async def test_fetch_context_with_only_fallback_events_yields_empty_event_list():
    """Preserves other market evidence: an empty recent_events list still
    produces a valid context (indices/sectors untouched); _generate()'s
    existing '- None' fallback represents this honestly, no fabrication."""
    await _cleanup()
    try:
        await _seed((_IDS[0], "rule_based_fallback"))
        with patch("app.services.market_data.get_extended_indices", new=AsyncMock(return_value=[{"name": "NIFTY 50", "value": "25000", "pct": 0.5}])), \
             patch("app.services.market_data.get_sector_changes", new=AsyncMock(return_value=[])):
            ctx = await _fetch_context()
        assert ctx["recent_events"] == []
        assert ctx["nifty"]["value"] == "25000"
    finally:
        await _cleanup()


@pytest.mark.asyncio
async def test_generate_prompt_never_contains_fallback_headline_text():
    await _cleanup()
    try:
        await _seed((_IDS[0], "rule_based_fallback"), (_IDS[1], "ai"))
        with patch("app.services.market_data.get_extended_indices", new=AsyncMock(return_value=[])), \
             patch("app.services.market_data.get_sector_changes", new=AsyncMock(return_value=[])):
            ctx = await _fetch_context()

        fake_story = '{"story": "Markets steady.", "mood": "Sideways", "pulse": "=", "sector_rotation": "s", "direction": "sideways", "opportunity": "o", "risk": "Only the AI-sourced signal informed this.", "trader_watch": "t", "investor_watch": "i", "confidence": 60}'
        with patch("app.services.ai_service._call_with_fallback", new=AsyncMock(return_value=fake_story)) as mock_call:
            data = await _generate(ctx)
        prompt = mock_call.call_args[0][0]
        assert "One-liner for story-prov-ai-1" in prompt
        assert "story-prov-fallback-1" not in prompt
        assert data["risk"] == "Only the AI-sourced signal informed this."
    finally:
        await _cleanup()


# ── Downstream: ai_synthesis -> Biggest Risk ─────────────────────────────────

def test_ai_synthesis_story_feeds_biggest_risk_when_no_tracked_event_exists():
    """The downstream consumer (_derive_biggest_risk) still correctly uses
    a story_engine-produced narrative via the pre-existing ai_synthesis
    branch -- unaffected by this change, since filtering happens upstream
    at generation time, not here."""
    story = {"risk": "Global rate uncertainty, based only on verified signals", "confidence": 55}
    result = _derive_biggest_risk(story=story, events=[])
    assert result["source"] == "ai_synthesis"
    assert result["reason"] == "Global rate uncertainty, based only on verified signals"
