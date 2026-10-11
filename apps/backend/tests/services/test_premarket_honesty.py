"""Premarket honesty: the stale-GIFT note states the real age, and market breadth is never scaled up from the tracked sample."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.api import market


def test_gift_note_states_the_real_age():
    now = datetime.now(timezone.utc)
    assert "3 hours ago" in market._gift_stale_note(now - timedelta(hours=3))
    assert "1 hour ago" in market._gift_stale_note(now - timedelta(hours=1))
    assert "2 days ago" in market._gift_stale_note(now - timedelta(hours=39 + 10))      # past the 48h mark it switches to days
    assert "39 hours ago" in market._gift_stale_note(now - timedelta(hours=39))
    assert "unknown" in market._gift_stale_note(None)


def test_breadth_is_never_scaled_to_an_invented_universe():
    import inspect
    src = inspect.getsource(market)
    assert "* 1200" not in src and "1500 - est_advances" not in src and "Estimated from Nifty 500 sample" not in src
