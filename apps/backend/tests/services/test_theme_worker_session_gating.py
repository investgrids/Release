"""
CR-3 (2026-09-13) — regression tests for theme_worker.py's session gating.

Locked policy under test: the expensive path (48 yfinance calls across
12 themes + an EventTriage query) only runs when Indian equities are
open (_market_session()=="live"). Off-hours (any non-"live" session,
including weekends), the same 10-minute cadence instead rebuilds
market:themes:ranked from the DB's current ThemeState rows -- zero
network calls, zero EventTriage query, zero ThemeState write (its
updated_at must stay at the last REAL computation time).

The off-hours payload must be schema-identical to the live-generated
one: same fields, same theme keys, same score-descending ranking.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import delete

from app.db.models.intelligence import ThemeState
from app.db.session import AsyncSessionLocal
from app.services.intelligence import theme_worker as tw


async def _seed_theme_state(theme: str, score: float, **overrides) -> None:
    base = dict(
        id=str(uuid.uuid4()), theme=theme, score=score, momentum="stable",
        top_stocks=[{"sym": "TEST", "change_pct": 0.0}], top_events=[],
        news_count_24h=0, price_signal=0.0, news_signal=0.0,
    )
    base.update(overrides)
    async with AsyncSessionLocal() as db:
        db.add(ThemeState(**base))
        await db.commit()


async def _cleanup(*themes: str) -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(delete(ThemeState).where(ThemeState.theme.in_(themes)))
        await db.commit()


@pytest.mark.asyncio
async def test_live_session_runs_the_full_expensive_path():
    with patch("app.services.intelligence.engine._market_session", return_value="live"), \
         patch.object(tw, "_score_theme", AsyncMock(return_value={
             "score": 55.0, "price_signal": 1.0, "news_signal": 10.0,
             "news_count_24h": 1, "top_stocks": [], "momentum": "rising",
         })) as score_mock, \
         patch("app.core.redis.cache_set", AsyncMock()) as cache_mock:
        await tw.run_theme_scoring()
    assert score_mock.call_count == len(tw.THEMES), "every theme must be scored live"
    cache_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_offhours_session_never_calls_score_theme_or_writes_db():
    """Off-hours (post_market/pre_market/weekend, tested as one
    representative non-live value here) must take the cheap rebuild
    path -- zero yfinance calls, zero EventTriage query (both live
    inside _score_theme), zero ThemeState write."""
    test_theme = f"TestTheme{uuid.uuid4().hex[:6]}"
    await _seed_theme_state(test_theme, score=42.0)
    try:
        with patch("app.services.intelligence.engine._market_session", return_value="post_market"), \
             patch.object(tw, "_score_theme", AsyncMock()) as score_mock, \
             patch("app.core.redis.cache_set", AsyncMock()) as cache_mock:
            await tw.run_theme_scoring()
        score_mock.assert_not_called()
        cache_mock.assert_awaited_once()
    finally:
        await _cleanup(test_theme)


@pytest.mark.asyncio
async def test_weekend_also_takes_the_cheap_rebuild_path():
    test_theme = f"TestTheme{uuid.uuid4().hex[:6]}"
    await _seed_theme_state(test_theme, score=42.0)
    try:
        with patch("app.services.intelligence.engine._market_session", return_value="weekend"), \
             patch.object(tw, "_score_theme", AsyncMock()) as score_mock, \
             patch("app.core.redis.cache_set", AsyncMock()) as cache_mock:
            await tw.run_theme_scoring()
        score_mock.assert_not_called()
        cache_mock.assert_awaited_once()
    finally:
        await _cleanup(test_theme)


@pytest.mark.asyncio
async def test_offhours_does_not_bump_updated_at():
    """ThemeState.updated_at must honestly reflect the last REAL
    computation -- an off-hours cycle that computed nothing new must
    not touch it."""
    test_theme = f"TestTheme{uuid.uuid4().hex[:6]}"
    frozen_time = datetime(2026, 9, 12, 10, 0, 0, tzinfo=timezone.utc)
    await _seed_theme_state(test_theme, score=42.0, updated_at=frozen_time)
    try:
        with patch("app.services.intelligence.engine._market_session", return_value="post_market"), \
             patch.object(tw, "_score_theme", AsyncMock()), \
             patch("app.core.redis.cache_set", AsyncMock()):
            await tw.run_theme_scoring()

        async with AsyncSessionLocal() as db:
            row = (await db.execute(
                ThemeState.__table__.select().where(ThemeState.theme == test_theme)
            )).mappings().first()
        assert row["updated_at"].replace(tzinfo=timezone.utc) == frozen_time
    finally:
        await _cleanup(test_theme)


@pytest.mark.asyncio
async def test_offhours_payload_schema_and_ranking_match_the_live_path():
    """The core equivalence proof the owner asked for: same public
    schema, same fields, same score-descending ranking as the
    live-generated payload -- not just 'some list gets cached'."""
    theme_a = f"TestThemeA{uuid.uuid4().hex[:6]}"
    theme_b = f"TestThemeB{uuid.uuid4().hex[:6]}"
    await _seed_theme_state(theme_a, score=30.0, momentum="falling", price_signal=-1.2, news_signal=5.0, news_count_24h=2, top_stocks=[{"sym": "A", "change_pct": -1.0}])
    await _seed_theme_state(theme_b, score=80.0, momentum="rising", price_signal=2.5, news_signal=20.0, news_count_24h=4, top_stocks=[{"sym": "B", "change_pct": 3.0}])
    try:
        captured = {}

        async def _capture_cache_set(key, value, ttl):
            captured["key"], captured["value"], captured["ttl"] = key, value, ttl

        with patch("app.services.intelligence.engine._market_session", return_value="weekend"), \
             patch.object(tw, "_score_theme", AsyncMock()), \
             patch("app.core.redis.cache_set", _capture_cache_set):
            await tw.run_theme_scoring()

        assert captured["key"] == "market:themes:ranked"
        assert captured["ttl"] == 700  # same TTL as the live path

        payload = captured["value"]
        entries = {e["theme"]: e for e in payload if e["theme"] in (theme_a, theme_b)}
        assert set(entries.keys()) == {theme_a, theme_b}

        # Same field set the live path's `{"theme": t, **s}` produces.
        expected_fields = {"theme", "score", "price_signal", "news_signal", "news_count_24h", "top_stocks", "momentum"}
        assert set(entries[theme_a].keys()) == expected_fields
        assert set(entries[theme_b].keys()) == expected_fields

        # Same values, read back correctly.
        assert entries[theme_b]["score"] == 80.0
        assert entries[theme_b]["momentum"] == "rising"
        assert entries[theme_a]["score"] == 30.0

        # Same ranking semantics: score-descending.
        idx_a = next(i for i, e in enumerate(payload) if e["theme"] == theme_a)
        idx_b = next(i for i, e in enumerate(payload) if e["theme"] == theme_b)
        assert idx_b < idx_a, "higher score (theme_b) must rank before lower score (theme_a)"
    finally:
        await _cleanup(theme_a, theme_b)
