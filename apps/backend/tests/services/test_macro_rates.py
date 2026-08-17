"""
Phase 5C — Macro Rate Intelligence.

Real, live proof of all three sources (matching this codebase's `_live`
test convention — allowed to occasionally fail on external outages, not
mocked to fake success), plus deterministic tests of the pure trend/
classification logic that don't depend on network state.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

import pytest
from sqlalchemy import delete

from app.db.models.macro_release import MacroRelease
from app.db.session import AsyncSessionLocal
from app.services.macro_rates.fed_funds_source import FedFundsObservation, get_fed_funds_rate
from app.services.macro_rates.persistence import get_rate_history, upsert_rate_observation
from app.services.macro_rates.rbi_wss_source import RbiWssState, get_rbi_wss_state
from app.services.macro_rates.service import get_macro_rate_state
from app.services.macro_rates.trend import build_macro_rate_state
from app.services.macro_rates.us_treasury_source import UsTreasuryState, get_us_treasury_state


# ── Live source checks ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_us_treasury_live():
    r = await get_us_treasury_state()
    assert r.status == "live"
    assert r.y2 is not None and r.y10 is not None
    assert r.spread == round(r.y10 - r.y2, 2)
    assert r.curve_state in ("inverted", "flat", "normal", "steep")


@pytest.mark.asyncio
async def test_fed_funds_live():
    r = await get_fed_funds_rate()
    assert r.status == "live"
    assert r.value is not None and r.value > 0
    assert r.observation_date is not None


@pytest.mark.asyncio
async def test_rbi_wss_live():
    r = await get_rbi_wss_state()
    assert r.status == "live"
    assert r.india_10y_gsec is not None
    assert r.repo_rate is not None
    assert r.india_10y_gsec_history is not None and len(r.india_10y_gsec_history) == 6
    assert r.repo_rate_history is not None and len(r.repo_rate_history) == 6
    # The rightmost (most recent) history entry must match the reported "latest" value.
    assert r.india_10y_gsec_history[-1][1] == r.india_10y_gsec
    assert r.repo_rate_history[-1][1] == r.repo_rate
    assert "WSSView.aspx?Id=" in r.source_url


@pytest.mark.asyncio
async def test_macro_rate_state_live_end_to_end():
    state = await get_macro_rate_state(force_refresh=True)
    assert state.india_data_status == "live"
    assert state.us_data_status == "live"
    assert state.interest_rate_trend in ("rising", "falling", "stable")
    assert state.interest_rate_trend_basis in ("india_repo_rate", "india_10y_gsec")


# ── Deterministic trend/classification logic ────────────────────────────────

def test_india_repo_trend_dominates_when_it_moved():
    wss = RbiWssState(
        status="live",
        repo_rate=5.25,
        repo_rate_history=[
            (date(2025, 8, 8), 5.50),
            (date(2026, 7, 10), 5.50), (date(2026, 7, 17), 5.50),
            (date(2026, 7, 24), 5.25), (date(2026, 7, 31), 5.25), (date(2026, 8, 7), 5.25),
        ],
        india_10y_gsec=6.79,
        india_10y_gsec_history=[
            (date(2025, 8, 8), 6.45),
            (date(2026, 7, 10), 6.72), (date(2026, 7, 17), 6.78),
            (date(2026, 7, 24), 6.84), (date(2026, 7, 31), 6.84), (date(2026, 8, 7), 6.79),
        ],
    )
    treasury = UsTreasuryState(status="unavailable")
    fed = FedFundsObservation(status="unavailable")
    state = build_macro_rate_state(treasury, fed, wss)
    assert state.india_repo_rate_trend == "falling"
    assert state.interest_rate_trend == "falling"
    assert state.interest_rate_trend_basis == "india_repo_rate"


def test_india_gsec_trend_is_tiebreaker_when_repo_flat():
    wss = RbiWssState(
        status="live",
        repo_rate=5.25,
        repo_rate_history=[(date(2025, 8, 8), 5.25)] + [(date(2026, 7, d), 5.25) for d in (10, 17, 24, 31)] + [(date(2026, 8, 7), 5.25)],
        india_10y_gsec=6.95,
        india_10y_gsec_history=[
            (date(2025, 8, 8), 6.45),
            (date(2026, 7, 10), 6.70), (date(2026, 7, 17), 6.78),
            (date(2026, 7, 24), 6.85), (date(2026, 7, 31), 6.90), (date(2026, 8, 7), 6.95),
        ],
    )
    treasury = UsTreasuryState(status="unavailable")
    fed = FedFundsObservation(status="unavailable")
    state = build_macro_rate_state(treasury, fed, wss)
    assert state.india_repo_rate_trend == "stable"
    # 6.70 -> 6.95 over the 4 recent weeks = +25bps, above the 15bps threshold.
    assert state.india_10y_gsec_trend == "rising"
    assert state.interest_rate_trend == "rising"
    assert state.interest_rate_trend_basis == "india_10y_gsec"


def test_small_gsec_move_is_stable_not_rising():
    wss = RbiWssState(
        status="live",
        repo_rate=5.25,
        repo_rate_history=[(date(2025, 8, 8), 5.25)] + [(date(2026, 7, d), 5.25) for d in (10, 17, 24, 31)] + [(date(2026, 8, 7), 5.25)],
        india_10y_gsec=6.79,
        india_10y_gsec_history=[
            (date(2025, 8, 8), 6.45),
            (date(2026, 7, 10), 6.72), (date(2026, 7, 17), 6.78),
            (date(2026, 7, 24), 6.84), (date(2026, 7, 31), 6.84), (date(2026, 8, 7), 6.79),
        ],
    )
    state = build_macro_rate_state(UsTreasuryState(status="unavailable"), FedFundsObservation(status="unavailable"), wss)
    # 6.72 -> 6.79 = +7bps, within the 15bps threshold.
    assert state.india_10y_gsec_trend == "stable"
    assert state.interest_rate_trend == "stable"


def test_india_unavailable_never_fabricates_a_trend():
    wss = RbiWssState(status="unavailable", reason="no_publishable_issue_in_window")
    state = build_macro_rate_state(UsTreasuryState(status="unavailable"), FedFundsObservation(status="unavailable"), wss)
    assert state.india_data_status == "unavailable"
    assert state.interest_rate_trend is None
    assert state.interest_rate_trend_basis is None
    assert state.interest_rate_trend_status == "unavailable"


def test_repo_flat_and_gsec_unavailable_is_insufficient_evidence_not_stable():
    """Owner's explicit safeguard (2026-08-17): a flat repo rate must
    NEVER be reported as a "stable" trend when the G-Sec tiebreaker is
    missing — that would silently recreate the exact hardcoded-"stable"
    bug Phase 5C exists to fix. This must resolve to None / explicitly
    "insufficient_evidence", not "stable"."""
    wss = RbiWssState(
        status="live",
        repo_rate=5.25,
        repo_rate_history=[(date(2025, 8, 8), 5.25)] + [(date(2026, 7, d), 5.25) for d in (10, 17, 24, 31)] + [(date(2026, 8, 7), 5.25)],
        india_10y_gsec=None,
        india_10y_gsec_history=None,  # G-Sec row failed to parse this issue
    )
    state = build_macro_rate_state(UsTreasuryState(status="unavailable"), FedFundsObservation(status="unavailable"), wss)
    assert state.india_repo_rate_trend == "stable"
    assert state.india_10y_gsec_trend is None
    assert state.interest_rate_trend is None
    assert state.interest_rate_trend_basis is None
    assert state.interest_rate_trend_status == "insufficient_evidence"


def test_rate_trend_version_is_recorded():
    from app.services.macro_rates.config import RATE_TREND_VERSION
    wss = RbiWssState(status="unavailable")
    state = build_macro_rate_state(UsTreasuryState(status="unavailable"), FedFundsObservation(status="unavailable"), wss)
    assert state.rate_trend_version == RATE_TREND_VERSION == "v1"


def test_us_curve_state_thresholds():
    from app.services.macro_rates.us_treasury_source import _classify_curve
    assert _classify_curve(-0.05) == "inverted"
    assert _classify_curve(0.10) == "flat"
    assert _classify_curve(0.51) == "normal"
    assert _classify_curve(1.20) == "steep"
    assert _classify_curve(None) is None


def test_us_trend_thresholds():
    from app.services.macro_rates.us_treasury_source import _classify_trend
    assert _classify_trend(20.0) == "rising"
    assert _classify_trend(-20.0) == "falling"
    assert _classify_trend(5.0) == "stable"
    assert _classify_trend(None) is None


# ── Persistence: on-change, not on-every-fetch ──────────────────────────────

async def _cleanup(metric: str, geography: str) -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(delete(MacroRelease).where(MacroRelease.metric == metric, MacroRelease.geography == geography))
        await db.commit()


@pytest.mark.asyncio
async def test_upsert_rate_observation_dedupes_unchanged_value():
    metric = f"test_metric_{uuid.uuid4().hex[:8]}"
    geography = "XX"
    async with AsyncSessionLocal() as db:
        r1 = await upsert_rate_observation(
            db, metric=metric, value=5.25, observation_date=date(2026, 8, 7), unit="%",
            source="test", source_url=None, geography=geography, headline="test",
        )
        assert r1["action"] == "created"

        r2 = await upsert_rate_observation(
            db, metric=metric, value=5.25, observation_date=date(2026, 8, 14), unit="%",
            source="test", source_url=None, geography=geography, headline="test",
        )
        assert r2["action"] == "unchanged"
        assert r2["id"] == r1["id"]

        r3 = await upsert_rate_observation(
            db, metric=metric, value=5.00, observation_date=date(2026, 8, 21), unit="%",
            source="test", source_url=None, geography=geography, headline="test",
        )
        assert r3["action"] == "created"
        assert r3["id"] != r1["id"]

        history = await get_rate_history(db, metric=metric, geography=geography, limit=10)
        assert len(history) == 2
        assert history[0].release_value == 5.00  # newest first
        assert history[0].previous_value == 5.25

    await _cleanup(metric, geography)
