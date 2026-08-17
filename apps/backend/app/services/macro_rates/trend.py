"""
MacroRateState — the shared read model for Phase 5C's rate data.

Combines the three sources (US Treasury, Fed funds, RBI WSS) into one
snapshot, and derives the single `interest_rate_trend` classification
that feeds historical_memory_service.compute_similarity()'s previously-
dead 8-point dimension (opening_prediction_service.py's hardcoded
"stable", weekend_intelligence/historical_integration.py's omitted key
— see this package's __init__.py for the full audit trail).

Why the trend is INDIA-derived, not US or blended: historical_memory_
service's ~20 seeded historical events are Indian-market setups (taper
tantrum, COVID stimulus, budget cycles, ...); their own
`interest_rate_trend` labels reflect the RBI policy-rate stance at the
time, not the Fed's. Feeding a US-derived trend into a same-named field
being compared against India-labeled seed data would silently compare
two different things. US Treasury/Fed data IS computed and exposed here
(us_10y_trend, us_curve_state, ...) for later consumers — AI Search
macro context, per the phase plan — but nothing wires them into
compute_similarity() in this phase; only interest_rate_trend does, and
it's India-only.

How interest_rate_trend is derived (two real signals, one tie-break
rule, not an LLM guess):
  1. RBI repo rate: decision-driven. Compare the value from ~4 weeks
     ago to the latest (both from real WSS weekly columns) — a step
     function, so ANY real change is a real signal, not noise. No
     statistical threshold needed or appropriate here.
  2. India 10Y G-Sec: continuous, market-quoted. Compare the same
     ~4-week window using a ±15bps threshold — empirically grounded:
     computed from two real, non-overlapping WSS windows (Jan-Feb 2026:
     +11bps/4wk; Jul-Aug 2026: +7bps/4wk), consistent with the same
     ±15bps threshold independently derived from 156 real days of US
     Treasury data (~1 standard deviation of the observed 4-week-change
     distribution — see us_treasury_source.py). Thin sample, revisit as
     more real WSS weeks accumulate via the sync job.
  Tie-break: repo rate is the authoritative signal (it IS the policy
  stance) — when it moved, that's the trend. When repo has been flat
  across the window, G-Sec's market-priced trend is used instead (it
  still reflects real rate expectations between meetings).

Safeguard (owner's explicit instruction, 2026-08-17): a flat repo rate
combined with an unavailable G-Sec tiebreaker must NEVER be reported as
"stable" — that would silently recreate the exact bug this phase exists
to fix (a value that looks like a real classification but is actually
just "we don't know"). interest_rate_trend stays None in that case, and
interest_rate_trend_status is explicitly "insufficient_evidence" rather
than the value simply being absent with no explanation — see
build_macro_rate_state's branching and
test_repo_flat_and_gsec_unavailable_is_insufficient_evidence_not_stable
in tests/services/test_macro_rates.py for the proof. Both
historical_memory_service.compute_similarity() and
weekend_intelligence's _build_query() already treat a missing
interest_rate_trend key as "award 0 points for this dimension" — never
as a false "stable" match.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.services.macro_rates.config import RATE_TREND_VERSION, YIELD_TREND_THRESHOLD_BPS
from app.services.macro_rates.fed_funds_source import FedFundsObservation
from app.services.macro_rates.rbi_wss_source import RbiWssState
from app.services.macro_rates.us_treasury_source import UsTreasuryState

_INDIA_TREND_THRESHOLD_BPS = YIELD_TREND_THRESHOLD_BPS


@dataclass
class MacroRateState:
    # India
    india_repo_rate: float | None = None
    india_repo_rate_trend: str | None = None       # "rising" | "falling" | "stable"
    india_10y_gsec: float | None = None
    india_10y_gsec_trend: str | None = None
    india_10y_gsec_observed_at: str | None = None   # ISO date; weekly-cadence data, see freshness note below
    india_data_status: str = "unavailable"           # "live" | "unavailable" — "live" here means a real WSS issue was parsed, NOT same-day fresh (weekly cadence by design)

    # US
    us_2y: float | None = None
    us_10y: float | None = None
    us_10y_trend: str | None = None
    us_curve_state: str | None = None                # "inverted" | "flat" | "normal" | "steep"
    us_fed_funds_rate: float | None = None
    us_data_status: str = "unavailable"

    # The single derived signal that feeds historical_memory_service.
    interest_rate_trend: str | None = None            # "rising" | "falling" | "stable" | None
    interest_rate_trend_basis: str | None = None       # which real signal decided it, for observability
    # "determined" | "insufficient_evidence" | "unavailable" — explicit,
    # auditable proof that a None interest_rate_trend was a deliberate
    # "we don't know", never silently coerced to "stable". See safeguard
    # note in this module's docstring.
    interest_rate_trend_status: str = "unavailable"
    rate_trend_version: str = RATE_TREND_VERSION


def _india_repo_trend(wss: RbiWssState) -> str | None:
    hist = wss.repo_rate_history
    if not hist or len(hist) < 2:
        return None
    # Columns 2-6 (index 1..5) are the 5 most recent consecutive weeks;
    # column 0 is the year-ago comparison point (not used for a 4-week trend).
    window = hist[1:] if len(hist) >= 6 else hist
    if len(window) < 2:
        return None
    _, start_val = window[0]
    _, end_val = window[-1]
    if end_val > start_val:
        return "rising"
    if end_val < start_val:
        return "falling"
    return "stable"


def _india_gsec_trend(wss: RbiWssState) -> str | None:
    hist = wss.india_10y_gsec_history
    if not hist or len(hist) < 2:
        return None
    window = hist[1:] if len(hist) >= 6 else hist
    if len(window) < 2:
        return None
    _, start_val = window[0]
    _, end_val = window[-1]
    change_bps = (end_val - start_val) * 100
    if change_bps > _INDIA_TREND_THRESHOLD_BPS:
        return "rising"
    if change_bps < -_INDIA_TREND_THRESHOLD_BPS:
        return "falling"
    return "stable"


def build_macro_rate_state(
    treasury: UsTreasuryState, fed: FedFundsObservation, wss: RbiWssState,
) -> MacroRateState:
    state = MacroRateState()

    if wss.status == "live":
        state.india_data_status = "live"
        state.india_repo_rate = wss.repo_rate
        state.india_10y_gsec = wss.india_10y_gsec
        state.india_10y_gsec_observed_at = wss.india_10y_gsec_observed_at.isoformat() if wss.india_10y_gsec_observed_at else None
        state.india_repo_rate_trend = _india_repo_trend(wss)
        state.india_10y_gsec_trend = _india_gsec_trend(wss)

        # Tie-break: repo rate is authoritative when it moved; otherwise
        # fall back to the market-priced G-Sec trend. If NEITHER yields a
        # real classification (e.g. repo flat AND G-Sec history missing/
        # unparseable), interest_rate_trend stays None and the status is
        # explicitly "insufficient_evidence" — never silently "stable".
        if state.india_repo_rate_trend in ("rising", "falling"):
            state.interest_rate_trend = state.india_repo_rate_trend
            state.interest_rate_trend_basis = "india_repo_rate"
            state.interest_rate_trend_status = "determined"
        elif state.india_10y_gsec_trend is not None:
            state.interest_rate_trend = state.india_10y_gsec_trend
            state.interest_rate_trend_basis = "india_10y_gsec"
            state.interest_rate_trend_status = "determined"
        else:
            state.interest_rate_trend_status = "insufficient_evidence"

    if treasury.status == "live":
        state.us_data_status = "live"
        state.us_2y = treasury.y2
        state.us_10y = treasury.y10
        state.us_10y_trend = treasury.y10_trend
        state.us_curve_state = treasury.curve_state

    if fed.status == "live":
        state.us_fed_funds_rate = fed.value

    return state
