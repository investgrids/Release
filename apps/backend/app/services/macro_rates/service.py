"""
Cached entry point into Phase 5C's macro rate data — the one function
real consumers (opening_prediction_service.py, weekend_intelligence/
historical_integration.py) call. Fetches all three sources in
parallel, each independently failure-isolated (one source failing
never blocks the others — build_macro_rate_state only uses whichever
came back "live"). TTL matches the sources' own real update cadence:
Treasury/Fed update at most once a day, WSS once a week — refetching
every request would be pure overhead, not freshness.
"""
from __future__ import annotations

import asyncio
import time

from app.services.macro_rates.fed_funds_source import get_fed_funds_rate
from app.services.macro_rates.rbi_wss_source import get_rbi_wss_state
from app.services.macro_rates.trend import MacroRateState, build_macro_rate_state
from app.services.macro_rates.us_treasury_source import get_us_treasury_state

_CACHE: dict[str, tuple[float, MacroRateState]] = {}
_TTL_SECONDS = 6 * 3600


async def get_macro_rate_state(*, force_refresh: bool = False) -> MacroRateState:
    now = time.time()
    cached = _CACHE.get("state")
    if not force_refresh and cached and (now - cached[0]) < _TTL_SECONDS:
        return cached[1]

    treasury, fed, wss = await asyncio.gather(
        get_us_treasury_state(), get_fed_funds_rate(), get_rbi_wss_state(),
        return_exceptions=True,
    )
    from app.services.macro_rates.fed_funds_source import FedFundsObservation
    from app.services.macro_rates.rbi_wss_source import RbiWssState
    from app.services.macro_rates.us_treasury_source import UsTreasuryState

    if isinstance(treasury, BaseException):
        treasury = UsTreasuryState(status="unavailable", reason="exception")
    if isinstance(fed, BaseException):
        fed = FedFundsObservation(status="unavailable", reason="exception")
    if isinstance(wss, BaseException):
        wss = RbiWssState(status="unavailable", reason="exception")

    state = build_macro_rate_state(treasury, fed, wss)
    _CACHE["state"] = (now, state)
    return state
