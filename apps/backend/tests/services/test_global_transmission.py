"""
Global transmission relationships — isolated store, eligibility predicate and
deterministic linkage (2026-10-20). Verifies that unapproved/under-sourced
relationships never produce a hypothesis, temporal ordering is enforced, and
the empty state is correct. Pure/fast — fake rows via SimpleNamespace.
"""
from __future__ import annotations

import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy.ext.asyncio import create_async_engine

from app.db.base import Base
from app.services.global_transmission import (
    is_eligible, derive_india_implications, observed_global_triggers,
)


def _rel(**kw):
    base = dict(
        id="r1", approved=True, citation="RBI Bulletin, Jan 2026, p.42",
        evidence_basis="Higher US yields raise relative attractiveness of US assets, pressuring EM rate-sensitive equities.",
        source_factor="US_10Y_YIELD", source_factor_label="US 10Y Treasury yield",
        target_type="sector", target_key="rate_sensitive", target_label="Indian rate-sensitive sectors",
        direction="negative", confidence=0.6, lag_days_min=0, lag_days_max=5,
    )
    base.update(kw)
    return SimpleNamespace(**base)


# ── eligibility predicate ─────────────────────────────────────────────────────

def test_fully_valid_relationship_is_eligible():
    assert is_eligible(_rel()) is True


@pytest.mark.parametrize("override", [
    {"approved": False},
    {"citation": ""},
    {"citation": None},
    {"evidence_basis": ""},
    {"direction": "sideways"},
    {"target_type": "country"},
    {"source_factor": ""},
    {"lag_days_min": None},
    {"lag_days_max": None},
    {"lag_days_min": -1},
    {"lag_days_min": 6, "lag_days_max": 2},  # min > max
])
def test_ineligible_when_any_requirement_fails(override):
    assert is_eligible(_rel(**override)) is False


# ── deterministic linkage ─────────────────────────────────────────────────────

def _trigger(age_days, factor="US_10Y_YIELD", label="US 10Y Treasury yield"):
    return {"factor": factor, "label": label, "observed_at": datetime.now(timezone.utc) - timedelta(days=age_days),
            "source": "macro_rates"}


def test_trigger_within_window_produces_one_hypothesis():
    out = derive_india_implications([_rel(lag_days_min=0, lag_days_max=5)], [_trigger(2)])
    assert len(out) == 1
    h = out[0]
    assert "could exert" in h["hypothesis"] and h["confidence"] == "hypothesis"
    assert h["limitation"] == "Potential relationship; actual market impact is not confirmed."
    assert "could exert downward pressure on Indian rate-sensitive sectors" in h["hypothesis"]
    # internal provenance present for review
    assert h["_provenance"]["citation"] and h["_provenance"]["relationship_id"] == "r1"


def test_trigger_outside_window_produces_nothing():
    assert derive_india_implications([_rel(lag_days_min=0, lag_days_max=5)], [_trigger(10)]) == []


def test_trigger_too_early_produces_nothing():
    assert derive_india_implications([_rel(lag_days_min=3, lag_days_max=7)], [_trigger(1)]) == []


def test_unapproved_relationship_never_triggers():
    assert derive_india_implications([_rel(approved=False)], [_trigger(2)]) == []


def test_no_trigger_means_empty():
    assert derive_india_implications([_rel()], []) == []


def test_factor_mismatch_means_empty():
    assert derive_india_implications([_rel(source_factor="DXY")], [_trigger(2, factor="US_10Y_YIELD")]) == []


def test_positive_direction_wording():
    out = derive_india_implications(
        [_rel(direction="positive", target_label="Indian exporters")], [_trigger(2)])
    assert "could exert upward pressure on Indian exporters" in out[0]["hypothesis"]


# ── trigger source: OFF by default, US 10Y feed when flag ON (Candidate 4 G3) ──

@pytest.mark.asyncio
async def test_observed_triggers_empty_when_flag_off():
    # default flag state is False → [] exactly as before G3
    assert await observed_global_triggers() == []


def _fake_state(**kw):
    from datetime import date
    from app.services.macro_rates.us_treasury_source import UsTreasuryState
    base = dict(status="live", latest_date=date.today(), y10=4.5, y10_trend="rising")
    base.update(kw)
    return UsTreasuryState(**base)


@pytest.mark.asyncio
async def test_observed_triggers_flag_on_rising_emits_one(monkeypatch):
    import app.services.global_transmission as gt
    monkeypatch.setattr(gt.settings, "global_transmission_triggers_enabled", True, raising=False)

    async def fake():
        return _fake_state()
    monkeypatch.setattr(gt, "get_us_treasury_state", fake)

    out = await gt.observed_global_triggers()
    assert len(out) == 1
    assert out[0]["factor"] == "US_10Y_YIELD" and out[0]["value"] == 4.5


@pytest.mark.asyncio
async def test_observed_triggers_flag_on_not_rising_empty(monkeypatch):
    import app.services.global_transmission as gt
    monkeypatch.setattr(gt.settings, "global_transmission_triggers_enabled", True, raising=False)

    async def fake():
        return _fake_state(y10_trend="stable")
    monkeypatch.setattr(gt, "get_us_treasury_state", fake)

    assert await gt.observed_global_triggers() == []


@pytest.mark.asyncio
async def test_end_to_end_flag_on_but_unapproved_rel_still_empty(monkeypatch):
    # The flag ON + a real rising trigger must STILL surface nothing without an
    # approved relationship — the activation gate, proven end to end.
    import app.services.global_transmission as gt
    monkeypatch.setattr(gt.settings, "global_transmission_triggers_enabled", True, raising=False)

    async def fake():
        return _fake_state()
    monkeypatch.setattr(gt, "get_us_treasury_state", fake)

    triggers = await gt.observed_global_triggers()
    assert len(triggers) == 1
    # unapproved relationship → no implication despite a valid trigger in-window
    assert derive_india_implications([_rel(approved=False, lag_days_min=0, lag_days_max=10)], triggers) == []
    # approved relationship within window → exactly one hypothesis
    out = derive_india_implications([_rel(lag_days_min=0, lag_days_max=10)], triggers)
    assert len(out) == 1 and out[0]["limitation"] == "Potential relationship; actual market impact is not confirmed."


# ── model registration (new isolated table is created by create_all) ─────────

@pytest.mark.asyncio
async def test_isolated_table_is_registered_and_created():
    import app.db.models.global_transmission  # noqa: F401
    assert "global_transmission_relationships" in Base.metadata.tables
    with tempfile.TemporaryDirectory() as tmp:
        engine = create_async_engine(f"sqlite+aiosqlite:///{Path(tmp) / 'gt.db'}")
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            from sqlalchemy import text
            async with engine.begin() as conn:
                r = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='global_transmission_relationships'"))
                assert r.first() is not None
        finally:
            await engine.dispose()
