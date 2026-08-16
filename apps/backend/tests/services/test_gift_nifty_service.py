"""
Phase 5B — GIFT Nifty service. Deterministic tests via normalize()
(the pure function) cover every case the owner listed without
depending on network timing; one live test proves the real endpoint
integration end-to-end, including outside normal NSE cash-market hours
if the environment happens to run it then (the strongest proof the
original problem — GIFT Nifty silently degrading to domestic futures
or spot — is actually fixed).
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from app.services.gift_nifty_service import GiftNiftyResult, normalize, get_gift_nifty, _STALE_AFTER_HOURS


def _raw(gift_row: dict | None = "DEFAULT") -> dict:
    if gift_row == "DEFAULT":
        gift_row = {
            "LASTPRICE": 24423, "DAYCHANGE": -8, "PERCHANGE": -0.03,
            "EXPIRYDATE": "25-Aug-2026", "TIMESTMP": "16-Aug-2026 02:29",
        }
    return {"giftnifty": gift_row} if gift_row is not None else {}


# ── Real live endpoint ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_live_endpoint_returns_real_giftnifty_data():
    result = await get_gift_nifty()
    assert result.price is not None
    assert result.price > 0
    assert result.source == "nse_market_status"
    assert result.status in ("live", "stale")   # never "unavailable" while the real endpoint works
    assert result.expiry is not None


# ── Normalization: live case ────────────────────────────────────────────

def test_live_case_correct_normalized_values():
    now = datetime(2026, 8, 16, 3, 0, tzinfo=timezone.utc)   # 30 min after the fixture's timestamp
    raw = _raw({
        "LASTPRICE": 24423, "DAYCHANGE": -8, "PERCHANGE": -0.03,
        "EXPIRYDATE": "25-Aug-2026", "TIMESTMP": "16-Aug-2026 08:00",   # 08:00 IST = 02:30 UTC
    })
    result = normalize(raw, spot_price=24366.0, now=now)
    assert result.status == "live"
    assert result.price == 24423.0
    assert result.change == -8.0
    assert result.change_pct == -0.03
    assert result.expiry == date(2026, 8, 25)


def test_premium_to_spot_arithmetic_is_correct():
    now = datetime(2026, 8, 16, 3, 0, tzinfo=timezone.utc)
    raw = _raw({
        "LASTPRICE": 24423, "DAYCHANGE": -8, "PERCHANGE": -0.03,
        "EXPIRYDATE": "25-Aug-2026", "TIMESTMP": "16-Aug-2026 08:00",
    })
    result = normalize(raw, spot_price=24366.0, now=now)
    assert result.premium_points == round(24423.0 - 24366.0, 2)
    assert result.premium_pct == round((24423.0 - 24366.0) / 24366.0 * 100, 3)
    assert result.premium_points == 57.0
    assert result.premium_pct > 0   # premium, not discount, in this fixture


# ── Failure modes ────────────────────────────────────────────────────────

def test_endpoint_failure_marks_unavailable_not_fallback():
    result = normalize(None, spot_price=24366.0, now=datetime.now(timezone.utc))
    assert result.status == "unavailable"
    assert result.reason == "source_fetch_failed"
    assert result.price is None
    # spot is recorded but never becomes the GIFT Nifty price
    assert result.spot_price == 24366.0


def test_missing_giftnifty_row_marks_unavailable():
    raw = _raw(gift_row=None)   # marketStatus responded, but no "giftnifty" key at all
    result = normalize(raw, spot_price=24366.0, now=datetime.now(timezone.utc))
    assert result.status == "unavailable"
    assert result.reason == "giftnifty_row_missing"
    assert result.price is None


def test_malformed_giftnifty_row_marks_unavailable_no_fake_fallback():
    raw = _raw({"LASTPRICE": "not_a_number", "DAYCHANGE": -8, "PERCHANGE": -0.03,
                 "EXPIRYDATE": "25-Aug-2026", "TIMESTMP": "16-Aug-2026 08:00"})
    result = normalize(raw, spot_price=24366.0, now=datetime.now(timezone.utc))
    assert result.status == "unavailable"
    assert result.reason == "giftnifty_row_malformed"
    assert result.price is None   # never a guessed/interpolated number


def test_giftnifty_row_missing_required_key_marks_unavailable():
    raw = _raw({"DAYCHANGE": -8, "PERCHANGE": -0.03,
                 "EXPIRYDATE": "25-Aug-2026", "TIMESTMP": "16-Aug-2026 08:00"})   # no LASTPRICE
    result = normalize(raw, spot_price=24366.0, now=datetime.now(timezone.utc))
    assert result.status == "unavailable"
    assert result.reason == "giftnifty_row_malformed"


# ── Staleness ────────────────────────────────────────────────────────────

def test_stale_timestamp_marked_stale_not_live():
    now = datetime(2026, 8, 16, 12, 0, tzinfo=timezone.utc)
    raw = _raw({
        "LASTPRICE": 24423, "DAYCHANGE": -8, "PERCHANGE": -0.03,
        "EXPIRYDATE": "25-Aug-2026", "TIMESTMP": "14-Aug-2026 08:00",   # ~2 days old
    })
    result = normalize(raw, spot_price=24366.0, now=now)
    assert result.status == "stale"
    assert result.reason == "source_timestamp_too_old"
    assert result.price == 24423.0   # still reports the real value — just honestly labeled


def test_fresh_timestamp_within_session_gap_stays_live():
    """GIFT Nifty's own documented session gap (~02:45-06:30 IST) must
    not itself get flagged as staleness — a fresh close-of-session
    timestamp only ~4 hours old should still read "live" (well inside
    the 8h threshold). Values verified independently: TIMESTMP
    "16-Aug-2026 02:30" IST == 2026-08-15 21:00 UTC; `now` is exactly
    4 hours later."""
    now = datetime(2026, 8, 16, 1, 0, tzinfo=timezone.utc)
    raw = _raw({
        "LASTPRICE": 24423, "DAYCHANGE": -8, "PERCHANGE": -0.03,
        "EXPIRYDATE": "25-Aug-2026", "TIMESTMP": "16-Aug-2026 02:30",
    })
    result = normalize(raw, spot_price=24366.0, now=now)
    assert result.status == "live"


def test_unparseable_timestamp_marked_stale():
    raw = _raw({
        "LASTPRICE": 24423, "DAYCHANGE": -8, "PERCHANGE": -0.03,
        "EXPIRYDATE": "25-Aug-2026", "TIMESTMP": "not-a-real-timestamp",
    })
    result = normalize(raw, spot_price=24366.0, now=datetime.now(timezone.utc))
    assert result.status == "stale"
    assert result.reason == "source_timestamp_unparseable"


# ── Spot failure ─────────────────────────────────────────────────────────

def test_spot_failure_gift_still_reported_premium_null():
    now = datetime(2026, 8, 16, 3, 0, tzinfo=timezone.utc)
    raw = _raw({
        "LASTPRICE": 24423, "DAYCHANGE": -8, "PERCHANGE": -0.03,
        "EXPIRYDATE": "25-Aug-2026", "TIMESTMP": "16-Aug-2026 08:00",
    })
    result = normalize(raw, spot_price=None, now=now)
    assert result.status == "live"
    assert result.price == 24423.0   # GIFT Nifty itself unaffected by spot failure
    assert result.premium_points is None
    assert result.premium_pct is None


# ── Expiry parsing ───────────────────────────────────────────────────────

def test_expiry_parsed_to_real_date():
    raw = _raw({
        "LASTPRICE": 24423, "DAYCHANGE": -8, "PERCHANGE": -0.03,
        "EXPIRYDATE": "25-Aug-2026", "TIMESTMP": "16-Aug-2026 08:00",
    })
    result = normalize(raw, spot_price=None, now=datetime.now(timezone.utc))
    assert result.expiry == date(2026, 8, 25)


def test_unparseable_expiry_is_none_not_fabricated():
    raw = _raw({
        "LASTPRICE": 24423, "DAYCHANGE": -8, "PERCHANGE": -0.03,
        "EXPIRYDATE": "garbage", "TIMESTMP": "16-Aug-2026 08:00",
    })
    result = normalize(raw, spot_price=None, now=datetime.now(timezone.utc))
    assert result.expiry is None


# ── Overnight timestamp handling ─────────────────────────────────────────

def test_overnight_ist_timestamp_converts_to_correct_utc():
    """02:29 IST is 20:59 UTC the PREVIOUS calendar day — a real
    day-boundary-crossing case, confirmed against the actual live
    fixture captured from NSE (15-Aug-2026 02:29 IST)."""
    now = datetime(2026, 8, 15, 3, 0, tzinfo=timezone.utc)
    raw = _raw({
        "LASTPRICE": 24423, "DAYCHANGE": -8, "PERCHANGE": -0.03,
        "EXPIRYDATE": "25-Aug-2026", "TIMESTMP": "15-Aug-2026 02:29",
    })
    result = normalize(raw, spot_price=None, now=now)
    assert result.source_timestamp == datetime(2026, 8, 14, 20, 59, tzinfo=timezone.utc)
    assert result.status == "live"

