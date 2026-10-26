"""
Candidate 4 G3 — US 10Y yield trigger adapter (pure mapper).

Maps a verified US Treasury 10Y observation (UsTreasuryState) to the
global-transmission trigger contract: {factor, observed_at, value, source}.

Pure: no I/O, no DB, no network. The ONLY "material move" definition used is the
Treasury source's own empirically-derived rising-trend flag (~15 bps over ~20
trading days; see us_treasury_source.py / macro_rates/config.py) — no new
threshold is invented here. A trigger is emitted ONLY for a live, materially
RISING 10Y whose reading is still fresh enough to fall inside a rule's lag window.
"""
from __future__ import annotations

from datetime import datetime, timezone

from app.services.macro_rates.us_treasury_source import UsTreasuryState

_FACTOR = "US_10Y_YIELD"
_LABEL = "US 10-year Treasury yield rising"
# Widest signed-off Candidate-4 lag window (0–10 days). A reading older than this
# can never fall inside any rule's window, so it is not a live trigger.
_MAX_FRESHNESS_DAYS = 10


def build_us_10y_trigger(state: UsTreasuryState, now: datetime | None = None) -> dict | None:
    """Return the trigger dict for a fresh, live, rising 10Y; otherwise None.

    `observed_at` is returned as a TIMEZONE-AWARE datetime — a hard requirement:
    the downstream linkage (derive_india_implications) computes `now - observed_at`
    and would raise on a naive datetime or a bare date.
    """
    now = now or datetime.now(timezone.utc)

    # material-move gate: only a RISING 10Y is a trigger for this (negative) rule
    if state.status != "live" or state.y10 is None or state.y10_trend != "rising":
        return None
    if state.latest_date is None:
        return None

    observed_at = datetime(
        state.latest_date.year, state.latest_date.month, state.latest_date.day,
        tzinfo=timezone.utc,
    )

    # freshness guard: an already-stale reading cannot be within any lag window
    if (now - observed_at).days > _MAX_FRESHNESS_DAYS:
        return None

    return {
        "factor": _FACTOR,
        "label": _LABEL,
        "observed_at": observed_at,
        "value": state.y10,          # percent par yield (e.g. 4.25)
        "source": state.source,      # "us_treasury_par_yield_curve"
    }
