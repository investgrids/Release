"""
Phase 1E §5/§6 — Friday close capture boundary verification, through the
REAL capture_close_snapshot() path (not a hand-built MarketSnapshot row).

Real discovery worth stating up front (not a bug, not fixed here — both
are pre-existing frozen-phase code in different modules): the WINDOW gate
(_within_close_capture_window, price_monitor.py) is inclusive of exactly
15:30-15:40 IST, but the SESSION gate capture_close_snapshot() also
requires (_market_session() == "post_market", engine.py), and
_market_session()'s own "live" cutoff is `mins <= 15:30` — i.e. 15:30
itself is STILL "live", not yet "post_market". The two gates independently
agree on eligibility for 15:31-15:40 but disagree at the single minute
15:30 exactly (window says eligible, session says not yet post-market).
Net effect: real capture in practice starts at 15:31 IST, not 15:30 —
tested honestly below as two separate concerns (the window function's own
boundary vs. the full function's actual observed behavior), rather than
silently asserting the window's boundary as if it were the whole story.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest
from sqlalchemy import select

from app.db.models.intelligence import MarketSnapshot
from tests.integration.conftest import FRIDAY, MONDAY, SATURDAY, ist

_FAKE_NIFTY_QUOTE = {"price": 24500.0, "prev_close": 24400.0, "change": 100.0, "pct": 0.41, "positive": True}


def _patch_market_data():
    """The one blocking external call capture_close_snapshot() makes
    (Nifty primary quote) — every other source (BankNifty, VIX, FII/DII,
    PCR, sector ETFs, top movers, themes/story) is already individually
    try/except-wrapped in the real function and degrades to None/[] on
    its own when unreachable, exactly as it would for a real
    unreachable-provider case; not separately mocked here on purpose."""
    return patch("app.services.market_data._fetch_quote", return_value=_FAKE_NIFTY_QUOTE)


# ── Pure window-eligibility boundary (brief §5's literal 5 cases) ──────────

def test_within_close_capture_window_boundaries():
    from app.services.intelligence.price_monitor import _within_close_capture_window

    assert _within_close_capture_window(ist(FRIDAY, 15, 29)) is False
    assert _within_close_capture_window(ist(FRIDAY, 15, 30)) is True
    assert _within_close_capture_window(ist(FRIDAY, 15, 35)) is True
    assert _within_close_capture_window(ist(FRIDAY, 15, 40)) is True
    assert _within_close_capture_window(ist(FRIDAY, 15, 41)) is False


# ── Full capture_close_snapshot() integration — real observed behavior ─────

@pytest.mark.asyncio
async def test_1529_no_capture(isolated_db, frozen_time):
    frozen_time(ist(FRIDAY, 15, 29))
    from app.services.intelligence.price_monitor import capture_close_snapshot
    with _patch_market_data():
        await capture_close_snapshot()
    rows = (await isolated_db.execute(select(MarketSnapshot))).scalars().all()
    assert rows == []


@pytest.mark.asyncio
async def test_1530_exact_boundary_does_not_yet_capture(isolated_db, frozen_time):
    """See module docstring: at exactly 15:30, _market_session() still
    reports "live" (its own cutoff is inclusive), so the outer session
    gate blocks capture for this one minute even though the window
    function alone would allow it. Documenting the real behavior, not
    the brief's simplified assumption."""
    frozen_time(ist(FRIDAY, 15, 30))
    from app.services.intelligence.price_monitor import capture_close_snapshot
    with _patch_market_data():
        await capture_close_snapshot()
    rows = (await isolated_db.execute(select(MarketSnapshot))).scalars().all()
    assert rows == []


@pytest.mark.asyncio
async def test_1531_captured(isolated_db, frozen_time):
    frozen_time(ist(FRIDAY, 15, 31))
    from app.services.intelligence.price_monitor import capture_close_snapshot
    with _patch_market_data():
        await capture_close_snapshot()
    rows = (await isolated_db.execute(select(MarketSnapshot))).scalars().all()
    assert len(rows) == 1
    assert rows[0].snapshot_type == "close"
    assert rows[0].trading_date == FRIDAY.isoformat()
    assert rows[0].nifty_level == 24500.0


@pytest.mark.asyncio
async def test_1535_captured(isolated_db, frozen_time):
    frozen_time(ist(FRIDAY, 15, 35))
    from app.services.intelligence.price_monitor import capture_close_snapshot
    with _patch_market_data():
        await capture_close_snapshot()
    rows = (await isolated_db.execute(select(MarketSnapshot))).scalars().all()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_1540_still_eligible(isolated_db, frozen_time):
    frozen_time(ist(FRIDAY, 15, 40))
    from app.services.intelligence.price_monitor import capture_close_snapshot
    with _patch_market_data():
        await capture_close_snapshot()
    rows = (await isolated_db.execute(select(MarketSnapshot))).scalars().all()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_1541_window_closed_no_capture(isolated_db, frozen_time):
    frozen_time(ist(FRIDAY, 15, 41))
    from app.services.intelligence.price_monitor import capture_close_snapshot
    with _patch_market_data():
        await capture_close_snapshot()
    rows = (await isolated_db.execute(select(MarketSnapshot))).scalars().all()
    assert rows == []


@pytest.mark.asyncio
async def test_repeated_execution_within_window_does_not_duplicate(isolated_db, frozen_time):
    frozen_time(ist(FRIDAY, 15, 33))
    from app.services.intelligence.price_monitor import capture_close_snapshot
    with _patch_market_data():
        await capture_close_snapshot()
        await capture_close_snapshot()
        await capture_close_snapshot()
    rows = (await isolated_db.execute(select(MarketSnapshot))).scalars().all()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_weekend_time_never_captures_even_inside_clock_window(isolated_db, frozen_time):
    """_market_session() gates on weekday first — Saturday 15:33 IST must
    not be miscaptured as a Friday-style close just because the
    minute-of-day matches the window."""
    frozen_time(ist(SATURDAY, 15, 33))
    from app.services.intelligence.price_monitor import capture_close_snapshot
    with _patch_market_data():
        await capture_close_snapshot()
    rows = (await isolated_db.execute(select(MarketSnapshot))).scalars().all()
    assert rows == []


# ── §6: restart after close with no snapshot captured ──────────────────────

@pytest.mark.asyncio
async def test_restart_at_1800_with_no_prior_capture_does_not_reconstruct(isolated_db, frozen_time):
    """Simulates: process boots at Friday 18:00 (well past the capture
    window), no close snapshot exists yet (e.g. it was never running
    during 15:30-15:40). capture_close_snapshot() must NOT retroactively
    reconstruct one from current/stale data — the bounded-window rule
    (Phase 1A) must hold exactly as before."""
    frozen_time(ist(FRIDAY, 18, 0))
    from app.services.intelligence.price_monitor import capture_close_snapshot
    with _patch_market_data():
        await capture_close_snapshot()
    rows = (await isolated_db.execute(select(MarketSnapshot))).scalars().all()
    assert rows == []


@pytest.mark.asyncio
async def test_missing_close_snapshot_makes_weekend_intelligence_honestly_degraded(isolated_db, frozen_time):
    """Downstream consequence of the above: with no close snapshot,
    build_weekend_intelligence must report baseline_available=False and
    status='degraded' (never fabricate a baseline, brief §6). Uses a
    checkpoint_time consistent with the fake 2099 calendar — real
    datetime.now() would sit far outside the evidence window and
    silently exclude the fixture, a mistake worth naming since it is an
    easy one to make when mixing frozen fake dates with real "now"."""
    from datetime import timezone
    from app.services.weekend_intelligence.aggregator import build_weekend_intelligence
    from tests.integration.conftest import make_event

    await make_event(isolated_db, title="Some Saturday development affecting Banking sector",
                      when=ist(SATURDAY, 10), sectors=["Banking"], companies=["HDFCBANK"])
    await isolated_db.commit()

    checkpoint_time = ist(MONDAY, 8, 0).astimezone(timezone.utc)
    result = await build_weekend_intelligence(isolated_db, MONDAY.isoformat(), checkpoint_time)
    assert result.evidence_count >= 1
    assert result.baseline_available is False
    assert result.status == "degraded"
