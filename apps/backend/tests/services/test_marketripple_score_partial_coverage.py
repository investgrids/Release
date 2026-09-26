"""
Comparability interim rule — 2026-09-26 audit follow-up (owner decision):
a 2-of-4 or 3-of-4 pillar blend uses renormalized weights and is not
comparable to a real 4-of-4 blend, so no combined headline number or
ranking eligibility is shown for a partial-coverage symbol until a real
shadow comparison validates which partial combinations are safe. Per-
pillar scores that WERE produced must stay visible regardless — only the
combined number is withheld.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.services.marketripple_score.contracts import PillarScore, PillarStatus


def _pillar(name, score, coverage=100.0) -> PillarScore:
    return PillarScore(
        name=name, score=score, coverage_pct=coverage,
        status=PillarStatus.COMPLETE if score is not None else PillarStatus.INSUFFICIENT,
        metrics_used=["x"] if score is not None else [], metrics_missing=[], sources=["test"],
        as_of=datetime.now(timezone.utc),
    )


@pytest.mark.asyncio
async def test_headline_score_withheld_when_fewer_than_4_pillars_usable(monkeypatch):
    from app.services.marketripple_score import engine

    monkeypatch.setattr(engine, "score_financial_strength", _async_return(_pillar("financial_strength", 70.0)))
    monkeypatch.setattr(engine, "score_valuation", _async_return(_pillar("valuation", 60.0)))
    monkeypatch.setattr(engine, "score_market_behaviour", _async_return(_pillar("market_behaviour", None)))
    monkeypatch.setattr(engine, "score_current_intelligence", _async_return(_pillar("current_intelligence", None)))
    monkeypatch.setattr("app.services.aipe.company_score_engine._sector_for", lambda symbol: "Banking")

    result = await engine.compute_marketripple_score(db=None, symbol="TESTPARTIAL")

    assert result.score is None, "a 2-of-4 blend must never surface a combined headline number"
    assert result.label is None
    assert result.pillar_coverage_status == "partial"
    assert result.pillar_coverage_message == "Partial coverage — 2 of 4 pillars"
    # Per-pillar detail must still be real and visible — only the combined number is withheld.
    assert result.pillars["financial_strength"].score == 70.0
    assert result.pillars["valuation"].score == 60.0


@pytest.mark.asyncio
async def test_headline_score_present_when_all_4_pillars_usable(monkeypatch):
    from app.services.marketripple_score import engine

    monkeypatch.setattr(engine, "score_financial_strength", _async_return(_pillar("financial_strength", 70.0)))
    monkeypatch.setattr(engine, "score_valuation", _async_return(_pillar("valuation", 60.0)))
    monkeypatch.setattr(engine, "score_market_behaviour", _async_return(_pillar("market_behaviour", 50.0)))
    monkeypatch.setattr(engine, "score_current_intelligence", _async_return(_pillar("current_intelligence", 55.0)))
    monkeypatch.setattr("app.services.aipe.company_score_engine._sector_for", lambda symbol: "Banking")

    result = await engine.compute_marketripple_score(db=None, symbol="TESTCOMPLETE")

    assert result.score is not None
    assert result.pillar_coverage_status == "complete"
    assert result.pillar_coverage_message == "Complete coverage — 4 of 4 pillars"


def _async_return(value):
    async def _fn(*args, **kwargs):
        return value
    return _fn
