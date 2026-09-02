"""
CD3-B — typed claim provenance tagging on live_intelligence.py's real
detectors (anomaly, early_theme, policy_ripple). These are the producers
CD3-A traced as EVENT_DIRECTION (one event-level LLM direction broadcast
to every matched company) and PRICE_SIGN (real observed price move) --
this suite proves the tags actually reach the API response, using real
DB rows rather than mocking the detector internals.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import delete

from app.api.companies import _NSE_UNIVERSE
from app.db.models.intelligence import EventTriage, ThemeState
from app.db.session import AsyncSessionLocal
from app.services.claim_provenance import ClaimProvenance
from app.services.live_intelligence import _detect_anomaly, _detect_early_theme

# Three real, same-sector companies from the real curated universe --
# picked at test time rather than hardcoded, so this doesn't silently
# drift if the universe changes.
_BANKING = [co["symbol"] for co in _NSE_UNIVERSE if co.get("sector") == "Banking"][:3]


@pytest.mark.asyncio
async def test_anomaly_detector_tags_companies_as_event_direction():
    assert len(_BANKING) >= 3, "test needs >=3 real Banking-sector companies in _NSE_UNIVERSE"
    ids = [str(uuid.uuid4()) for _ in _BANKING]
    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db:
        for rid, sym in zip(ids, _BANKING):
            db.add(EventTriage(
                id=rid, event_id=f"test-evt-{rid[:8]}", source="news",
                headline=f"Real test headline for {sym}", urgency=8, importance=7,
                confidence=70, direction="up", sectors=["Banking"], tickers=[sym],
                triaged_at=now,
            ))
        await db.commit()

    try:
        async with AsyncSessionLocal() as db:
            result = await _detect_anomaly(db)
        assert result is not None, "expected a real anomaly cluster from the 3 fixture rows"
        assert result["companies"], "expected at least one company chip"
        for c in result["companies"]:
            assert c["impact_provenance"] == ClaimProvenance.EVENT_DIRECTION.value
            # Original field untouched.
            assert c["impact"] in ("positive", "negative", "neutral", None)
    finally:
        async with AsyncSessionLocal() as db:
            await db.execute(delete(EventTriage).where(EventTriage.id.in_(ids)))
            await db.commit()


@pytest.mark.asyncio
async def test_early_theme_detector_tags_top_stocks_as_price_sign():
    theme_id = str(uuid.uuid4())
    theme_name = f"Test Theme {theme_id[:8]}"
    async with AsyncSessionLocal() as db:
        db.add(ThemeState(
            id=theme_id, theme=theme_name, score=72.0, momentum="rising",
            top_stocks=[{"sym": "HDFCBANK", "change_pct": 2.4}, {"sym": "ICICIBANK", "change_pct": -1.1}],
            top_events=[], news_count_24h=5,
        ))
        await db.commit()

    try:
        async with AsyncSessionLocal() as db:
            result = await _detect_early_theme(db)
        assert result is not None
        # _detect_early_theme returns top_stocks under the "companies" key.
        assert result["companies"], "expected companies to be populated"
        for s in result["companies"]:
            assert s["impact_provenance"] == ClaimProvenance.PRICE_SIGN.value
        # Real observed price signs preserved correctly.
        by_symbol = {s["symbol"]: s["impact"] for s in result["companies"]}
        assert by_symbol["HDFCBANK"] == "positive"
        assert by_symbol["ICICIBANK"] == "negative"
    finally:
        async with AsyncSessionLocal() as db:
            await db.execute(delete(ThemeState).where(ThemeState.id == theme_id))
            await db.commit()
