"""Homepage Ripple Signals (2026-11-11): the feed may carry up to 2 sector
clusters + 2 rising themes, but the default (used by the signal publisher,
which mints durable signal pages) stays at 1 per detector."""
from unittest.mock import AsyncMock, patch

import pytest

import app.services.live_intelligence as li


def _item(t, n):
    return {"type": t, "headline": f"{t}-{n}"}


@pytest.mark.asyncio
@pytest.mark.parametrize("per_detector,expected", [(1, 1), (2, 2)])
async def test_per_detector_limit_is_passed_through(per_detector, expected):
    async def anomalies(db, limit=1):
        return [_item("anomaly", i) for i in range(min(limit, 3))]

    async def themes(db, exclude=None, limit=1):
        return [_item("early_theme", i) for i in range(min(limit, 3))]

    with patch.object(li, "_detect_anomalies", new=anomalies), \
         patch.object(li, "_detect_early_themes", new=themes), \
         patch.object(li, "_detect_policy_ripple", new=AsyncMock(return_value=None)):
        items = await li.get_live_intelligence(None, None, per_detector=per_detector)
    assert sum(i["type"] == "anomaly" for i in items) == expected
    assert sum(i["type"] == "early_theme" for i in items) == expected


@pytest.mark.asyncio
async def test_default_stays_one_per_detector_for_signal_publisher():
    seen = {}

    async def anomalies(db, limit=1):
        seen["anomaly"] = limit
        return []

    async def themes(db, exclude=None, limit=1):
        seen["theme"] = limit
        return []

    with patch.object(li, "_detect_anomalies", new=anomalies), \
         patch.object(li, "_detect_early_themes", new=themes), \
         patch.object(li, "_detect_policy_ripple", new=AsyncMock(return_value=None)):
        await li.get_live_intelligence(None, None)
    assert seen == {"anomaly": 1, "theme": 1}
