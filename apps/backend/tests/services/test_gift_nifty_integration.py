"""
Phase 5B integration — proves the two real consumers of GIFT Nifty
(market.py's /premarket endpoint and opening_prediction_service.py's
signal layer) consume the SAME result rather than each independently
fetching/parsing NSE's endpoint, and that neither ever relabels spot
as GIFT Nifty when the real source is unavailable. Deliberately uses
real live data (matching this module's existing test philosophy) —
the strongest proof the shared-adapter architecture actually works is
observing it against the real NSE endpoint, not a mock of it.
"""
from __future__ import annotations

import pytest

from app.api import market as market_module
from app.services import gift_nifty_service as gns_module
from app.services import opening_prediction_service as ops_module


@pytest.mark.asyncio
async def test_both_callers_share_the_same_gift_nifty_result(monkeypatch):
    """market.py and opening_prediction_service.py both read GIFT Nifty
    through _fetch_enhanced_premarket's shared "pm_enh" TTL cache — one
    real fetch, two consumers, never two independent answers."""
    market_module._cache.clear()

    real_fetch = gns_module._fetch_market_status_sync
    calls = {"n": 0}

    def counting_fetch():
        calls["n"] += 1
        return real_fetch()

    monkeypatch.setattr(gns_module, "_fetch_market_status_sync", counting_fetch)

    # Seed the shared cache exactly as the real /premarket endpoint does.
    enhanced = market_module._cached_sync("pm_enh", 900, market_module._fetch_enhanced_premarket)
    assert calls["n"] == 1

    signals = await ops_module._gather_signals()
    # No second network fetch — opening_prediction_service reused the cache.
    assert calls["n"] == 1

    assert signals["gift_nifty"]["value"] == enhanced["gift_nifty"]["value"]
    assert signals["gift_nifty"]["status"] == enhanced["gift_nifty"]["status"]


def test_gift_nifty_row_is_not_a_domestic_futures_construction():
    """The old _nifty_futures_ticker() (NIFTY26AUGFUT.NS-style) is gone
    from market.py entirely — GIFT Nifty now comes only from the shared
    NSE marketStatus adapter."""
    assert not hasattr(market_module, "_nifty_futures_ticker")
    row = market_module._gift_nifty_row()
    assert "FUT.NS" not in row["ticker"]
    assert row["ticker"] == "GIFT_NIFTY_NSEIX"


def test_gift_unavailable_never_relabeled_as_spot(monkeypatch):
    """When the real source is unavailable, market.py's row must show
    status=unavailable / value="—" — never silently substitute Nifty
    spot and call it GIFT Nifty."""
    async def fake_unavailable(spot_price=None):
        return gns_module.GiftNiftyResult(
            status="unavailable", reason="source_fetch_failed", spot_price=spot_price,
        )

    monkeypatch.setattr(gns_module, "get_gift_nifty", fake_unavailable)

    row = market_module._gift_nifty_row()
    assert row["status"] == "unavailable"
    assert row["value"] == "—"
    assert "price_raw" not in row
