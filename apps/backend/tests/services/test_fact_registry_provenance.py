"""
Provenance contract, Stage C (2026-10-19) -- fact_registry.py's
refresh_event_facts() labels Fact.evidence with triage_source, sourced
from the same read_top_events() chokepoint Stage A wired. No schema
change: both real readers (api/facts.py, api/daily_brief_intelligence.py)
already pass the `evidence` dict through unchanged, so this is additive.
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.db.base import Base
from app.services import fact_registry


def _event(event_id: str, triage_source: str | None, priority_tier: str = "Critical") -> dict:
    return {
        "id": event_id, "headline": f"Headline {event_id}", "one_liner": f"One-liner {event_id}",
        "urgency": 8, "importance": 8, "confidence": 4, "sentiment": "neutral",
        "market_impact": "medium", "direction": "sideways", "priority_tier": priority_tier,
        "priority_score": 80, "sectors": [], "tickers": [], "origin": None, "source": "news",
        **({"triage_source": triage_source} if triage_source is not None else {}),
    }


@pytest.mark.asyncio
async def test_refresh_event_facts_labels_evidence_with_triage_source():
    with tempfile.TemporaryDirectory() as tmpdir:
        engine = create_async_engine(f"sqlite+aiosqlite:///{Path(tmpdir) / 'facts.db'}")
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            Session = async_sessionmaker(engine, expire_on_commit=False)

            fake_events = [
                _event("ev-ai-1", "ai"),
                _event("ev-fallback-1", "rule_based_fallback"),
                _event("ev-unknown-1", "unknown"),
                _event("ev-missing-1", None),  # defensive case: key absent entirely
            ]
            with patch("app.services.intelligence.engine.read_top_events", new=AsyncMock(return_value=fake_events)):
                async with Session() as db:
                    facts = await fact_registry.refresh_event_facts(db, limit=10)

            by_key = {f.fact_key: f for f in facts}
            assert by_key["event:ev-ai-1"].evidence["triage_source"] == "ai"
            assert by_key["event:ev-fallback-1"].evidence["triage_source"] == "rule_based_fallback"
            assert by_key["event:ev-unknown-1"].evidence["triage_source"] == "unknown"
            assert by_key["event:ev-missing-1"].evidence["triage_source"] == "unknown", \
                "must default to unknown, never silently become ai, when the key is absent"
        finally:
            await engine.dispose()


@pytest.mark.asyncio
async def test_a_fact_row_outside_the_refresh_window_is_never_retroactively_rewritten():
    """An event that has aged out of read_top_events()'s 24h window is simply
    never revisited by refresh_event_facts() again -- its Fact row (written
    before this change shipped, with no triage_source in evidence) must stay
    exactly as it was, not get silently backfilled."""
    with tempfile.TemporaryDirectory() as tmpdir:
        engine = create_async_engine(f"sqlite+aiosqlite:///{Path(tmpdir) / 'facts2.db'}")
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            Session = async_sessionmaker(engine, expire_on_commit=False)

            from app.db.models.fact import Fact
            import uuid
            async with Session() as db:
                db.add(Fact(
                    id=str(uuid.uuid4()), fact_key="event:ev-aged-out-1",
                    valid_date=fact_registry._today_ist(), entity_type="event",
                    entity_key="ev-aged-out-1", name="Old headline",
                    claim="Old one-liner", source="MarketRipple Event Triage",
                    evidence={"sentiment": "neutral", "market_impact": "medium"},
                    generated_at=fact_registry._now(),
                ))
                await db.commit()

            # The event is no longer in the read_top_events() window at all.
            with patch("app.services.intelligence.engine.read_top_events", new=AsyncMock(return_value=[])):
                async with Session() as db:
                    await fact_registry.refresh_event_facts(db, limit=10)

            async with Session() as db:
                from sqlalchemy import select
                row = (await db.execute(select(Fact).where(Fact.fact_key == "event:ev-aged-out-1"))).scalar_one()
                assert "triage_source" not in row.evidence, "a row outside the refresh window must not be rewritten"
        finally:
            await engine.dispose()
