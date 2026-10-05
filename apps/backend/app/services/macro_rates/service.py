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


_inflight: asyncio.Task | None = None
_inflight_loop = None


async def get_macro_rate_state(*, force_refresh: bool = False, max_wait_s: float | None = None) -> MacroRateState:
    """Cached macro rate state. Step 3 closure: the (slow, 10 to 20 s cold) fetch is single flight and SHIELDED, so a caller whose request deadline expires never cancels it: it completes in the
    background and warms the cache for the next caller (previously every cancelled cold fetch was discarded and retried, so a deadline-bound caller could never succeed). `max_wait_s` bounds how
    long THIS caller waits; on expiry it raises asyncio.TimeoutError and the fetch keeps running. No max_wait_s: wait as before."""
    global _inflight, _inflight_loop
    now = time.time()
    cached = _CACHE.get("state")
    if not force_refresh and cached and (now - cached[0]) < _TTL_SECONDS:
        return cached[1]
    loop = asyncio.get_running_loop()
    if _inflight is None or _inflight.done() or _inflight_loop is not loop:
        _inflight = asyncio.ensure_future(_fetch_state())
        _inflight_loop = loop
        _inflight.add_done_callback(_clear_inflight)
    waiter = asyncio.shield(_inflight)
    if max_wait_s is None:
        return await waiter
    return await asyncio.wait_for(waiter, timeout=max_wait_s)


def _clear_inflight(task: asyncio.Task) -> None:
    global _inflight
    if _inflight is task:
        _inflight = None
    if not task.cancelled():
        task.exception()            # mark retrieved: a failed fetch is reported to its waiters, never as an unhandled task error


async def _fetch_state() -> MacroRateState:
    now = time.time()
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
