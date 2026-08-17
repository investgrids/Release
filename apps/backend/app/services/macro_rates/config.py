"""
Versioned, explicit research assumptions for Phase 5C's trend
classification — owner's explicit instruction (2026-08-17): the ±15bps
threshold must be a named, documented constant tied to a version label,
not a bare magic number duplicated across files. When outcome research
(CompanyIntelligenceObservation and friends, once mature) suggests a
different threshold discriminates historical regimes better, bump
RATE_TREND_VERSION alongside the new value so any persisted or logged
trend classification can be traced back to which definition produced it.

Derivation of v1's 15bps (see us_treasury_source.py and trend.py for
the live verification): the observed standard deviation of 20-trading-
day (~4 calendar week) yield changes across 156 real 2026 US Treasury
trading days was ~14.8bps (2Y) / ~15.2bps (10Y) — i.e. ~15bps is
approximately one standard deviation of real observed noise, not an
arbitrary round number. Cross-checked against India 10Y G-Sec via two
real, non-overlapping RBI WSS windows (Jan-Feb 2026: +11bps/4wk;
Jul-Aug 2026: +7bps/4wk — both correctly below the threshold). The
India cross-check is a thin sample (11 real weekly points total) —
revisit as more real WSS weeks accumulate through the sync job.
"""
from __future__ import annotations

RATE_TREND_VERSION = "v1"

# Trading days for US Treasury (~4 calendar weeks); the RBI WSS lookback
# uses 4 real weekly columns directly (see rbi_wss_source.py) rather
# than a day count, since WSS itself is already weekly-cadence data.
YIELD_TREND_WINDOW_TRADING_DAYS = 20
YIELD_TREND_THRESHOLD_BPS = 15.0
