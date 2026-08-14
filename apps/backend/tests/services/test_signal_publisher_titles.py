"""
Regression suite — live_intelligence.py detector headlines +
signal_publisher.py's slug/seo_title handling of them (SEO/AEO/GEO title
fix, 2026-08 audit: "Latest Intelligence Articles" was showing bare
fragments like "Defence" or "5 Banking companies showing simultaneous
activity" as the entire headline for live_signal articles — every other
article type already had real, specific titles).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete

from app.db.session import AsyncSessionLocal
from app.db.models.intelligence import EventTriage, ThemeState
from app.services.aipe.signal_publisher import slug_for_item, _seo_title_for_item, _companies_for_item
from app.services.live_intelligence import (
    _detect_anomaly, _detect_early_theme, _direction_to_impact, _change_pct_to_impact,
)


# ── Pure unit tests (no DB) ─────────────────────────────────────────────────

def test_early_theme_slug_uses_stable_theme_field_not_headline():
    # The headline now embeds a real, potentially-drifting opportunity
    # score — slugging off it would fragment the same theme's page across
    # re-detections. slug_for_item must key off item["theme"] instead.
    item = {
        "type": "early_theme", "theme": "Defence",
        "headline": "Defence: Emerging Investment Theme — Opportunity Score 80/100",
    }
    assert slug_for_item(item) == "theme-defence"

    item2 = dict(item, headline="Defence: Emerging Investment Theme — Opportunity Score 82/100")
    assert slug_for_item(item2) == "theme-defence"  # same slug despite the score drifting


def test_early_theme_slug_falls_back_to_headline_if_theme_field_missing():
    item = {"type": "early_theme", "headline": "Real Estate"}
    assert slug_for_item(item) == "theme-real-estate"


def test_anomaly_slug_still_keyed_off_sector_not_headline():
    item = {"type": "anomaly", "sector": "Defence", "headline": "Defence Sector: 5 Stocks Show Simultaneous Activity — August 13, 2026"}
    assert slug_for_item(item).startswith("defence-cluster-")


def test_seo_title_does_not_duplicate_label_for_anomaly_and_early_theme():
    headline = "Defence: Emerging Investment Theme — Opportunity Score 80/100"
    result = _seo_title_for_item({"type": "early_theme"}, headline, "Emerging Theme")
    assert result == headline  # no redundant " - Emerging Theme" suffix

    headline2 = "Defence Sector: 5 Stocks Show Simultaneous Activity — August 13, 2026"
    result2 = _seo_title_for_item({"type": "anomaly"}, headline2, "Intelligence Detection")
    assert result2 == headline2


def test_seo_title_still_appends_label_for_policy_ripple_and_historical():
    result = _seo_title_for_item({"type": "policy_ripple"}, "RBI Rate Cut", "Policy Intelligence")
    assert result == "RBI Rate Cut - Policy Intelligence"
    result2 = _seo_title_for_item({"type": "historical_match"}, "Union Budget 2020", "Pattern Detected")
    assert result2 == "Union Budget 2020 - Pattern Detected"


# ── DB-touching tests (real detector functions) ─────────────────────────────

@pytest.mark.asyncio
async def test_early_theme_headline_is_no_longer_bare_theme_name():
    theme_name = f"Pytest Theme {uuid.uuid4().hex[:8]}"
    async with AsyncSessionLocal() as db:
        await db.execute(delete(ThemeState).where(ThemeState.theme == theme_name))
        await db.commit()
    try:
        async with AsyncSessionLocal() as db:
            db.add(ThemeState(
                id=str(uuid.uuid4()), theme=theme_name, score=72.0, momentum="rising",
                top_stocks=["LT", "BHEL"],
            ))
            await db.commit()

            item = await _detect_early_theme(db)
        assert item is not None
        assert item["headline"] != theme_name  # not the bare name anymore
        assert theme_name in item["headline"]  # but still names the real theme
        assert item["theme"] == theme_name  # stable field present for slugging
        assert str(item["opportunity_score"]) in item["headline"]  # real score, not omitted
    finally:
        async with AsyncSessionLocal() as db:
            await db.execute(delete(ThemeState).where(ThemeState.theme == theme_name))
            await db.commit()


@pytest.mark.asyncio
async def test_anomaly_headline_includes_sector_count_and_date():
    # _detect_anomaly scans ALL real EventTriage rows in the window and
    # picks whichever sector cluster is largest — it isn't scoped to just
    # this test's injected rows, so a real, larger same-day cluster can
    # legitimately outrank the 3 seeded here. This test asserts the
    # HEADLINE FORMAT (real sector name + real count + real date, not the
    # old bare/generic template), not which specific sector wins.
    now = datetime.now(timezone.utc)
    ids = [f"pytest-triage-{uuid.uuid4().hex[:8]}" for _ in range(3)]
    symbols = ["LT", "BHEL", "ADANIENT"]  # real, same-sector (Infrastructure) companies
    try:
        async with AsyncSessionLocal() as db:
            for tid, sym in zip(ids, symbols):
                db.add(EventTriage(
                    id=tid, event_id=tid, source="news", headline=f"Test event for {sym}",
                    urgency=8, importance=7, sectors=["Infrastructure"], tickers=[sym],
                    triaged_at=now,
                ))
            await db.commit()

            item = await _detect_anomaly(db)
        assert item is not None
        assert item["sector"] in item["headline"]  # real winning sector, whichever it is
        assert "Sector:" in item["headline"]
        assert "Stocks Show Simultaneous Activity" in item["headline"]
        assert now.strftime("%B") in item["headline"]  # real detection month present
        assert str(now.year) in item["headline"]
    finally:
        async with AsyncSessionLocal() as db:
            await db.execute(delete(EventTriage).where(EventTriage.id.in_(ids)))
            await db.commit()


# ── Company impact coloring (2026-08 audit) ─────────────────────────────────

def test_direction_to_impact_mapping():
    assert _direction_to_impact("up") == "positive"
    assert _direction_to_impact("down") == "negative"
    assert _direction_to_impact("sideways") == "neutral"
    assert _direction_to_impact(None) is None


def test_change_pct_to_impact_mapping():
    assert _change_pct_to_impact(1.5) == "positive"
    assert _change_pct_to_impact(-0.3) == "negative"
    assert _change_pct_to_impact(0.0) == "neutral"
    assert _change_pct_to_impact(None) is None


def test_companies_for_item_reads_real_impact_from_dict_entries():
    item = {"type": "anomaly", "companies": [
        {"symbol": "TCS", "impact": "positive"},
        {"symbol": "INFY", "impact": "negative"},
        {"symbol": "WIPRO", "impact": None},
    ]}
    result = _companies_for_item(item)
    by_symbol = {c["symbol"]: c["impact"] for c in result}
    assert by_symbol["TCS"] == "positive"
    assert by_symbol["INFY"] == "negative"
    assert by_symbol["WIPRO"] == "neutral"  # None -> honest neutral fallback, not fabricated


def test_companies_for_item_backward_compatible_with_plain_strings():
    item = {"type": "policy_ripple", "companies": ["TCS", "INFY"]}
    result = _companies_for_item(item)
    assert all(c["impact"] == "neutral" for c in result)
    assert {c["symbol"] for c in result} == {"TCS", "INFY"}


@pytest.mark.asyncio
async def test_early_theme_companies_carry_real_change_pct_impact():
    theme_name = f"Pytest Impact Theme {uuid.uuid4().hex[:8]}"
    async with AsyncSessionLocal() as db:
        await db.execute(delete(ThemeState).where(ThemeState.theme == theme_name))
        await db.commit()
    try:
        async with AsyncSessionLocal() as db:
            db.add(ThemeState(
                id=str(uuid.uuid4()), theme=theme_name, score=70.0, momentum="rising",
                top_stocks=[
                    {"sym": "TCS", "change_pct": 1.2},
                    {"sym": "INFY", "change_pct": -0.8},
                    {"sym": "WIPRO", "change_pct": 0.0},
                ],
            ))
            await db.commit()

            item = await _detect_early_theme(db)
        assert item is not None
        by_symbol = {c["symbol"]: c["impact"] for c in item["companies"]}
        assert by_symbol["TCS"] == "positive"
        assert by_symbol["INFY"] == "negative"
        assert by_symbol["WIPRO"] == "neutral"
    finally:
        async with AsyncSessionLocal() as db:
            await db.execute(delete(ThemeState).where(ThemeState.theme == theme_name))
            await db.commit()


@pytest.mark.asyncio
async def test_anomaly_companies_carry_real_direction_impact():
    now = datetime.now(timezone.utc)
    ids = [f"pytest-triage-impact-{uuid.uuid4().hex[:8]}" for _ in range(3)]
    # Real, same-sector (Infrastructure) companies, each from an event
    # with a distinct, real triage direction.
    plan = [("LT", "up"), ("BHEL", "down"), ("ADANIENT", "sideways")]
    try:
        async with AsyncSessionLocal() as db:
            for tid, (sym, direction) in zip(ids, plan):
                db.add(EventTriage(
                    id=tid, event_id=tid, source="news", headline=f"Test event for {sym}",
                    urgency=8, importance=7, sectors=["Infrastructure"], tickers=[sym],
                    direction=direction, triaged_at=now,
                ))
            await db.commit()

            item = await _detect_anomaly(db)
        assert item is not None
        if item["sector"] == "Infrastructure":
            by_symbol = {c["symbol"]: c["impact"] for c in item["companies"]}
            assert by_symbol.get("LT") == "positive"
            assert by_symbol.get("BHEL") == "negative"
            assert by_symbol.get("ADANIENT") == "neutral"
        # else: a larger real-data cluster won — nothing to assert about
        # our seeded companies specifically (see the headline test above
        # for why this function isn't scoped to test-only data).
    finally:
        async with AsyncSessionLocal() as db:
            await db.execute(delete(EventTriage).where(EventTriage.id.in_(ids)))
            await db.commit()
