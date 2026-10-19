"""
Provenance contract, Stage D remaining consumers (2026-10-19) --
live_intelligence.py::_detect_anomaly() must not show a rule_based_fallback/
unknown event's one_liner as the cluster card's "why_it_matters" text.
Cluster membership (tickers/directions) is a real statistical signal and
is deliberately left untouched regardless of provenance -- only the
explanatory headline text is restricted. Not touching the pre-existing,
separately-flagged first-headline-selection order.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import delete

from app.db.session import AsyncSessionLocal
from app.db.models.intelligence import EventTriage
from app.services.live_intelligence import _detect_anomaly

_TECH_TICKERS = ["TCS", "INFY", "WIPRO"]
_IDS = [f"li-prov-{t}" for t in _TECH_TICKERS]


async def _cleanup():
    async with AsyncSessionLocal() as db:
        await db.execute(delete(EventTriage).where(EventTriage.event_id.in_(_IDS)))
        await db.commit()


async def _seed(triage_source: str):
    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db:
        for i, t in enumerate(_TECH_TICKERS):
            db.add(EventTriage(
                id=f"t-{_IDS[i]}", event_id=_IDS[i], source="news",
                headline=f"{t} headline", urgency=7, importance=6, confidence=5,
                one_liner=f"{t} raw or AI one-liner", triage_source=triage_source,
                sectors=["Technology"], tickers=[t], direction="up", triaged_at=now,
            ))
        await db.commit()


@pytest.mark.asyncio
async def test_fallback_sourced_cluster_has_no_why_it_matters_text():
    await _cleanup()
    try:
        await _seed("rule_based_fallback")
        async with AsyncSessionLocal() as db:
            result = await _detect_anomaly(db)
        assert result is not None, "cluster membership itself must still be detected (3 real companies, real sector)"
        assert result["why_it_matters"] is None, "a fallback-sourced headline must never become the card's explanation text"
        assert len(result["companies"]) == 3, "ticker/cluster-membership logic must be unaffected by provenance"
    finally:
        await _cleanup()


@pytest.mark.asyncio
async def test_ai_sourced_cluster_is_unaffected():
    await _cleanup()
    try:
        await _seed("ai")
        async with AsyncSessionLocal() as db:
            result = await _detect_anomaly(db)
        assert result is not None
        assert result["why_it_matters"] is not None
        assert "raw or AI one-liner" in result["why_it_matters"]
    finally:
        await _cleanup()
