"""
Macro Rate Intelligence — Phase 5C.

Fixes a real, self-documented gap: historical_memory_service.compute_similarity()
has scored an "interest_rate_trend" dimension (8/100 points) since it was
built, but every caller has always fed it a hardcoded "stable" (or, in
weekend_intelligence/historical_integration.py, omitted the key entirely) —
the dimension has never once done real work. This package supplies the
real, source-backed rate data that dimension was always missing.

Four streams, each verified against real live data before being trusted:
  - us_treasury_source.py  — US 2Y/10Y/spread, home.treasury.gov (tier 1)
  - fed_funds_source.py    — US effective funds rate, federalreserve.gov H.15 (tier 1)
  - rbi_repo_source.py     — India repo rate, RBI's own homepage "Current Rates" widget (tier 1)
  - rbi_wss_source.py      — India repo rate history + 10Y G-Sec par yield (FBIL),
                              RBI's Weekly Statistical Supplement (tier 1, weekly cadence)

trend.py derives rising/falling/stable classifications from real data —
either a genuine decision-driven step function (RBI repo rate: did the
actual decided value change over N decisions) or empirically-grounded
thresholds computed from real historical distributions (US Treasury
yields: ~15bps over 20 trading days, approximately one standard
deviation of the observed 2026 4-week-change distribution — see
trend.py's own docstring for the derivation).

Scope discipline (owner's explicit instruction, 2026-08-17): this phase
feeds historical-analogue matching (historical_memory_service,
weekend_intelligence/historical_integration.py) and context only. It
does NOT add a direct bullish/bearish weight to Opening Prediction's
own scoring — that's a decision for later outcome research, not this
phase. India 10Y G-Sec is explicitly a historical/regime signal only
(weekly cadence) — never wired into any live Pre-Market consumer.
"""
