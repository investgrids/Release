# MarketRipple Score — real-data pillar-combination comparability

**2026-09-26, Current Intelligence dedup verification follow-up.** Supersedes
the synthetic 5-company comparability demonstration in
`scripts/marketripple_score_shadow_pillar_comparability.py` with real data —
the synthetic version establishes the mechanism is real; this establishes the
magnitude on actual banks is not a contrived edge case.

**Scope correction (2026-09-26, second pass):** this run's "real" Financial
Strength scores were computed against a local database with zero
`financial_facts` rows (see `financial_strength_metric_coverage_gap_2026_09_26.md`)
— every bank's Financial Strength value below is built from the 3
yfinance-sourced metrics only (ROE/NII growth/Profit growth), not the full
7-metric real mix. This experiment demonstrates that the scoring formula
is genuinely sensitive to missing pillars/metrics on real (not synthetic)
numbers — it does **not** establish production's actual Banking coverage,
nor production rank stability under real full-coverage conditions. That
requires re-running this same method once a verified production
`financial_facts` read is available.

## Method

Ran `scripts/marketripple_score_five_bank_comparison.py` live against the 5
real reference banks (ICICIBANK, HDFCBANK, AXISBANK, KOTAKBANK, SBIN),
capturing their real 4-of-4 pillar scores as of this date. Then simulated,
for each bank, every "this one pillar went missing" (3-of-4, renormalized)
and "Financial Strength + one other pillar went missing" (2-of-4,
renormalized) case, using the exact same weighting formula
`compute_marketripple_score()` uses today — holding peers at full coverage.

## Real 4-of-4 scores (2026-09-26)

| Bank | Fin. Strength | Valuation | Market Behaviour | Current Intel. | Score | Rank |
|---|---:|---:|---:|---:|---:|---:|
| ICICIBANK | 62.1 | 38.5 | 43.0 | 52.8 | 52.2 | 1 |
| SBIN | 53.0 | 45.2 | 39.1 | 52.1 | 49.1 | 2 |
| HDFCBANK | 45.2 | 42.7 | 29.5 | 52.7 | 44.2 | 3 |
| KOTAKBANK | 36.6 | 18.2 | 59.2 | 52.0 | 40.2 | 4 |
| AXISBANK | 29.7 | 32.8 | 31.4 | 52.0 | 36.1 | 5 |

Local Financial Strength coverage today, every bank: 16.7–25% (2-3 of 7
real metrics, driven entirely by the local financial_facts gap above) —
the single-pillar drop below is not a hypothetical relative to this local
environment, but whether it reflects production's real coverage is
unverified.

## 1-pillar-drop results (real data)

**3 of 20 cases (15%) change rank**, max score delta **6.6 points**:
- ICICIBANK missing Financial Strength: rank 1→2 (−6.6)
- AXISBANK missing Financial Strength: rank 5→4 (+4.4)
- KOTAKBANK missing Valuation: rank 4→3 (+5.4)

## 2-pillar-drop results (real data) — Financial Strength + one other

Realistic given Financial Strength's actual current coverage. Deltas are
**larger than any single-pillar case**:
- KOTAKBANK missing Financial Strength + Valuation: **+14.5** (40.2 → 54.7 — would jump from last-but-one to first)
- ICICIBANK missing Financial Strength + Current Intelligence: **−11.8**
- AXISBANK missing Financial Strength + Valuation: **+8.2**

## Conclusion

Real bank data confirms the synthetic demonstration's *mechanism* was not
overstated — the renormalization sensitivity is real, not a contrived
synthetic artifact, and the realistic 2-pillar-thin case produces larger
swings than the single-pillar case alone. This is real evidence in support
of `engine.py`'s comparability interim rule (score withheld below 4-of-4
pillars).

**What this does NOT establish:** production's actual Banking Financial
Strength coverage (this local run used yfinance-only inputs due to the
local `financial_facts` gap), or production rank stability under real
full-coverage conditions. Both require re-running this method against a
verified production data read. Treat this artifact as "the formula is
sensitive to missing pillars — proven on real numbers," not "this is what
production ranking risk looks like."

Not re-run automatically (live yfinance/NSE data changes daily, same
established convention as `scripts/marketripple_score_five_bank_comparison.py`
itself) — re-run manually via
`python scripts/marketripple_score_five_bank_comparison.py` followed by
plugging the printed pillar values into a comparability pass when a fresh
read is needed.
