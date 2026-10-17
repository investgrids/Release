"""
Opportunity V1 shared provider chain integration (2026-10-17).

Design audit confirmed opportunity_generator.py's _call_ai called only
DeepSeek (a single raw httpx call, no retry, no fallback) and
DEEPSEEK_API_KEY is unconfigured in this deployment -- every V1 opportunity
has gone through the heuristic fallback unconditionally. Rewired onto the
shared ai_service._call_with_fallback cascade (Groq/OpenRouter/Gemini/
Requesty), the same precedent already used for event enrichment's
identical single-provider failure (fallback_chain_provider.py).

_call_with_fallback never raises and returns "" on any failure; `text or
None` preserves _call_ai's own documented None-on-failure contract exactly
-- every caller below it (the `if ai_text:` check and everything
downstream) is unchanged by this swap, confirmed by this file's tests
exercising the real generate_opportunity_from_events path with only
_call_ai's new internal dependency (_call_with_fallback) mocked, never
_call_ai itself.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete

from app.db.models.opportunity import Opportunity
from app.db.session import AsyncSessionLocal
from app.pipeline import opportunity_generator as gen_mod
from app.services import ai_service


def _ev(id_: str, title: str, summary: str = "", hours_ago: float = 0) -> dict:
    published = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
    return {"id": id_, "title": title, "summary": summary, "published_at": published.isoformat(), "category": "General"}


async def _cleanup(opportunity_id: int | None):
    if opportunity_id is None:
        return
    async with AsyncSessionLocal() as db:
        await db.execute(delete(Opportunity).where(Opportunity.id == opportunity_id))
        await db.commit()


@pytest.mark.asyncio
async def test_valid_json_from_shared_chain_produces_a_real_classification(monkeypatch):
    valid_json = (
        '{"title": "Shared Chain Title", "summary": "Shared chain summary.", '
        '"trend": "Negative", "risk_level": "High", "time_horizon": "1-3 Years", '
        '"matters": "m", "benefits": "b", "risks": ["r1"], "invalidate": "i", '
        '"why_bullets": ["w1"]}'
    )

    async def fake_fallback(prompt, system="", max_tokens=200, failure_log=None, *, priority):
        return valid_json

    monkeypatch.setattr(ai_service, "_call_with_fallback", fake_fallback)
    events = [_ev(f"e-{uuid.uuid4()}", "A Shared-Chain Real Corporate Event Title")]
    opp_id = None
    try:
        async with AsyncSessionLocal() as db:
            opp = await gen_mod.generate_opportunity_from_events(db, events)
            assert opp is not None
            opp_id = opp.id
            assert opp.title == "Shared Chain Title"
            assert opp.trend == "Negative"
            assert opp.risk_level == "High"
    finally:
        await _cleanup(opp_id)


@pytest.mark.asyncio
async def test_empty_result_from_shared_chain_produces_the_existing_honest_fallback(monkeypatch):
    async def fake_fallback(prompt, system="", max_tokens=200, failure_log=None, *, priority):
        return ""  # _call_with_fallback's real failure contract -- "", never None, never a raise

    monkeypatch.setattr(ai_service, "_call_with_fallback", fake_fallback)
    events = [_ev(f"e-{uuid.uuid4()}", "A Shared-Chain Empty-Response Event Title")]
    opp_id = None
    try:
        async with AsyncSessionLocal() as db:
            opp = await gen_mod.generate_opportunity_from_events(db, events)
            assert opp is not None
            opp_id = opp.id
            # Honest-classification fix (merged into main alongside this
            # patch) changed the heuristic fallback's default from
            # "Positive" to "Neutral" -- validated combined-context value,
            # see D:\IG-opp-integration.
            assert opp.trend == "Neutral"
            assert opp.risk_level == "Medium"
            assert "Investment opportunity driven by:" in opp.summary
    finally:
        await _cleanup(opp_id)


@pytest.mark.asyncio
async def test_shared_chain_is_called_with_background_priority(monkeypatch):
    captured = {}

    async def fake_fallback(prompt, system="", max_tokens=200, failure_log=None, *, priority):
        captured["priority"] = priority
        captured["prompt_len"] = len(prompt)
        return ""

    monkeypatch.setattr(ai_service, "_call_with_fallback", fake_fallback)
    result = await gen_mod._call_ai("a test prompt")

    assert captured["priority"] == "background"
    assert result is None  # "" from the chain must still surface as None, not ""


@pytest.mark.asyncio
async def test_max_tokens_is_forwarded_correctly(monkeypatch):
    captured = {}

    async def fake_fallback(prompt, system="", max_tokens=200, failure_log=None, *, priority):
        captured["max_tokens"] = max_tokens
        return "some text"

    monkeypatch.setattr(ai_service, "_call_with_fallback", fake_fallback)
    result = await gen_mod._call_ai("prompt", max_tokens=777)

    assert captured["max_tokens"] == 777
    assert result == "some text"


@pytest.mark.asyncio
async def test_default_max_tokens_matches_the_original_deepseek_only_default(monkeypatch):
    captured = {}

    async def fake_fallback(prompt, system="", max_tokens=200, failure_log=None, *, priority):
        captured["max_tokens"] = max_tokens
        return "x"

    monkeypatch.setattr(ai_service, "_call_with_fallback", fake_fallback)
    await gen_mod._call_ai("prompt")

    assert captured["max_tokens"] == 600  # _call_ai's own documented default, unchanged


@pytest.mark.asyncio
async def test_a_genuine_exception_from_the_shared_chain_is_not_silently_swallowed_here(monkeypatch):
    """_call_with_fallback never raises (confirmed by source read) -- but
    this proves _call_ai itself adds no new try/except that could mask a
    real bug if that contract were ever violated. An exception from the
    mock must propagate, not be converted into a quiet None."""
    async def raising_fallback(prompt, system="", max_tokens=200, failure_log=None, *, priority):
        raise RuntimeError("simulated unexpected failure")

    monkeypatch.setattr(ai_service, "_call_with_fallback", raising_fallback)
    with pytest.raises(RuntimeError):
        await gen_mod._call_ai("prompt")


@pytest.mark.asyncio
async def test_generate_opportunity_from_events_still_handles_a_raising_call_ai_via_its_existing_try_except(monkeypatch):
    """Confirms job_daily_opportunities' own per-sector try/except (which
    already wraps generate_opportunity_from_events) remains the real
    safety net for this new, unlikely-but-possible exception path -- not
    a new one added inside the generator itself, preserving existing
    error-handling behavior exactly."""
    async def raising_fallback(prompt, system="", max_tokens=200, failure_log=None, *, priority):
        raise RuntimeError("simulated provider chain crash")

    monkeypatch.setattr(ai_service, "_call_with_fallback", raising_fallback)
    events = [_ev(f"e-{uuid.uuid4()}", "A Shared-Chain Exception Event Title")]
    with pytest.raises(RuntimeError):
        async with AsyncSessionLocal() as db:
            await gen_mod.generate_opportunity_from_events(db, events)
