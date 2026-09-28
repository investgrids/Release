"""
Owner instruction (2026-09-28): "make sure in prod we don't show the
preview text." The frontend hides every preview branch behind
NODE_ENV === "development" (dead code in a production `next build`), but
the raw API is public too — these tests lock in that every backend source
of unpublished (local-preview) scores is withheld whenever
settings.is_production is true, and that is_production can't be switched
off on a deployed Railway server just because JSON_LOGS went missing.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import delete

from app.core.config import Settings
from app.db.models.marketripple_score_snapshot import MarketRippleScoreSnapshot
from app.db.session import AsyncSessionLocal

SYMBOL = "3MINDIA"  # real Infrastructure company, early in the alphabetical directory


def test_is_production_true_on_any_railway_deployment_even_without_json_logs(monkeypatch):
    monkeypatch.setenv("RAILWAY_ENVIRONMENT", "production")
    assert Settings(json_logs=False).is_production is True


def test_is_production_false_locally(monkeypatch):
    monkeypatch.delenv("RAILWAY_ENVIRONMENT", raising=False)
    assert Settings(json_logs=False).is_production is False


@pytest.fixture
def force_production(monkeypatch):
    def _set(value: bool):
        # Patch the settings object the app reads *now*: another test reloads
        # app.core.config, which replaces `settings` (and its class), so the
        # module-level import above can be a stale copy by the time this runs.
        import app.core.config as config
        monkeypatch.setattr(type(config.settings), "is_production", property(lambda self: value))
    return _set


@pytest.fixture
async def eligible_unpublished_snapshot():
    async with AsyncSessionLocal() as db:
        db.add(MarketRippleScoreSnapshot(
            symbol=SYMBOL, score=72.4, rating="Positive",
            financial_strength=70.0, valuation=60.0, market_behaviour=90.0,
            coverage_pct=95.0, methodology_version="MARKETRIPPLE_SCORE_V1",
            peer_universe=[], peer_universe_count=68, calculated_at=datetime.now(timezone.utc),
            publishable=False, publication_block_reasons=[], pillar_coverage_status="complete",
        ))
        await db.commit()
    from app.services.marketripple_score import rankings
    rankings._ALL_COMPANIES_LOOKUP_CACHE.update(data=None, at=0.0)
    yield
    async with AsyncSessionLocal() as db:
        await db.execute(delete(MarketRippleScoreSnapshot).where(MarketRippleScoreSnapshot.symbol == SYMBOL))
        await db.commit()
    rankings._ALL_COMPANIES_LOOKUP_CACHE.update(data=None, at=0.0)


async def _list(db):
    from app.api.companies import list_companies
    return await list_companies(q=SYMBOL, sector="", cap="", sort="name", min_score=None,
                                page=1, page_size=24, live=False, db=db)


async def test_list_companies_withholds_local_preview_in_production(force_production, eligible_unpublished_snapshot):
    async with AsyncSessionLocal() as db:
        force_production(False)
        dev_row = next(c for c in (await _list(db))["companies"] if c["symbol"] == SYMBOL)
        force_production(True)
        prod_row = next(c for c in (await _list(db))["companies"] if c["symbol"] == SYMBOL)
    assert dev_row["marketripple_score_local_preview"]["score"] == 72.4  # the fixture really is there
    assert prod_row["marketripple_score_local_preview"] is None
    assert prod_row["marketripple_score"]["score"] is None  # unpublished -> public score withheld too


async def test_min_score_filter_cannot_reveal_unpublished_scores_in_production(force_production, eligible_unpublished_snapshot):
    """Filtering by score must not become a side channel: in production an
    unpublished company can't appear under ">= 70" at all."""
    from app.api.companies import list_companies
    force_production(True)
    async with AsyncSessionLocal() as db:
        res = await list_companies(q=SYMBOL, sector="", cap="", sort="name", min_score=70,
                                   page=1, page_size=24, live=False, db=db)
    assert SYMBOL not in {c["symbol"] for c in res["companies"]}


async def test_rankings_route_strips_local_preview_in_production(force_production, eligible_unpublished_snapshot):
    from app.api.company_rankings import get_all_company_rankings
    async with AsyncSessionLocal() as db:
        force_production(False)
        dev = await get_all_company_rankings(page=1, page_size=50, db=db)
        force_production(True)
        prod = await get_all_company_rankings(page=1, page_size=50, db=db)
    dev_row = next(r for r in dev["companies"] if r["symbol"] == SYMBOL)
    prod_row = next(r for r in prod["companies"] if r["symbol"] == SYMBOL)
    assert dev_row["local_preview"]["score"] == 72.4
    assert prod_row["local_preview"] is None
    assert prod_row["score"] is None


async def test_local_preview_endpoints_404_in_production(force_production):
    from app.api.companies import get_company_marketripple_score_local_preview
    from app.api.company_rankings import get_top_local_preview
    force_production(True)
    async with AsyncSessionLocal() as db:
        with pytest.raises(HTTPException) as e1:
            await get_company_marketripple_score_local_preview(SYMBOL, db=db)
        with pytest.raises(HTTPException) as e2:
            await get_top_local_preview(limit=5, db=db)
    assert e1.value.status_code == 404 and e2.value.status_code == 404
