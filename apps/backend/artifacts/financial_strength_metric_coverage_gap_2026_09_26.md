# Financial Strength — real metric-coverage gap investigation

**2026-09-26, verification follow-up.** The live 5-bank run showed Financial
Strength coverage of only 16.7-25% for every real reference bank. This
investigates precisely which of the 7 real Banking V1 metrics are present
per bank and why the rest are missing.

## Method

Live pull of ROE/NII growth/Profit growth via
`scripts/marketripple_score_five_bank_comparison.py` (yfinance, real-time).
Direct query of the local `financial_facts` table (`ig_dev.db`) for the 4
XBRL-sourced metrics (Gross NPA%, Net NPA%, CET1 Ratio, ROA), checking for
rows of ANY quality_status (not just valid ones) to distinguish an
ingestion gap from a quality exclusion.

## Coverage table

| Metric | Source | ICICIBANK | HDFCBANK | AXISBANK | KOTAKBANK | SBIN |
|---|---|:-:|:-:|:-:|:-:|:-:|
| Gross NPA % | NSE XBRL | ✗ | ✗ | ✗ | ✗ | ✗ |
| Net NPA % | NSE XBRL | ✗ | ✗ | ✗ | ✗ | ✗ |
| CET1 Ratio | NSE XBRL | ✗ | ✗ | ✗ | ✗ | ✗ |
| ROA | NSE XBRL | ✗ | ✗ | ✗ | ✗ | ✗ |
| ROE | yfinance | ✓ 0.1607 | ✓ 0.1384 | ✓ 0.1335 | ✗ | ✓ 0.1518 |
| NII growth | yfinance | ✓ 9.1% | ✓ 6.8% | ✓ 3.8% | ✓ 7.4% | ✓ 5.6% |
| Profit growth | yfinance | ✓ 6.2% | ✓ 4.6% | ✓ -6.0% | ✓ -12.8% | ✓ 7.4% |
| **Present / 7** | | **3** | **3** | **3** | **2** | **3** |

3/7 → 25% of `_PROPOSED_BANKING_METRICS` (12); 2/7 → 16.7% — matches the
live-observed coverage_pct exactly for all 5 banks.

## Root cause — critical scoping note

**`financial_facts` has ZERO rows in the local dev database — for any
symbol, any metric, at all** (`SELECT COUNT(*) FROM financial_facts` → 0).
This is a **total local ingestion gap in this development environment**,
not a per-metric quality exclusion: no ANOMALY/IMPLAUSIBLE_SCALE/
SOURCE_DOCUMENT_QUARANTINED rows exist either, because no rows of any kind
exist.

**This finding does not establish anything about production's real
Financial Strength coverage.** The module's own docstring (financial_strength.py)
states these 4 metrics were "confirmed real and reliably available"
(S3-B/C, 2026-08-25) — presumably validated against production data at
the time. Verifying whether that still holds today requires a real
production-DB read, which this session could not obtain (blocked by the
"Production Reads" classifier throughout). Until that read happens, the
honest state is: **local environment has no financial_facts data; production's
current state is unknown, not "also missing."**

KOTAKBANK's ROE gap is independently confirmed as a real, live yfinance
data gap (unrelated to the local-DB issue) — every other bank's ROE
resolved successfully in the same live run.

## What this does NOT justify

No change to `BANKING_V1_P1`'s eligibility thresholds. The gap identified
here is a data-availability question (what data exists to score), entirely
separate from the eligibility policy question (how much of the available
data must exist before publishing) — conflating the two would be lowering
the bar to compensate for missing data, which was explicitly rejected.

## Follow-up needed (not actioned in this session)

1. An authorized read-only production query confirming whether
   `financial_facts` actually has real rows for these 5 banks in production
   (the same kind of check attempted and blocked earlier in this
   engagement for `marketripple_score_snapshots`).
2. If production genuinely also lacks this data: the S3-B/C "confirmed
   real and reliably available" claim needs re-validation or retraction,
   since it currently overstates real coverage.
3. If production DOES have this data and only the local dev DB is stale:
   a documented note that local Financial Strength testing/exploration
   should not be trusted to reflect real coverage until the local DB is
   refreshed from a real production snapshot.
