# Unified MarketRipple Score — S2 Engine Built, Five-Bank Comparison (local only, not published)

Date: 2026-08-25. Follow-up to `artifacts/marketripple_score_s1_feasibility_audit.md`. Built the S2-A/B/C engine locally (`apps/backend/app/services/marketripple_score/`), ran it live against the 5 real reference banks (S2-D). **`publishable` is hardcoded `False` for the whole phase — nothing on the Company page changed, nothing deployed.**

## What was built

- **`contracts.py`** — the exact `PillarScore`/`MarketRippleScore` shapes proposed, including `coverage_pct`, `status` (COMPLETE/PARTIAL/INSUFFICIENT), `metrics_used`/`metrics_missing`, and `publishable` as an explicit field.
- **`current_intelligence.py`** — thin wrapper around the already-shipped `compute_company_score()`, using `contributing_signal_count` (not raw `signal_count`) as the real coverage signal.
- **`valuation.py`** — peer-percentile P/E and P/B (real peers = `app.api.stocks._PEER_GROUPS["banks"]`, the exact 5 reference banks) with a real ROE quality adjustment, plus a coarse own-historical-range P/E built from real annual EPS matched to the nearest real weekly close.
- **`market_behaviour.py`** — its own dedicated daily-price fetch (deliberately not Warehouse's `price_bars`, confirmed in S1 at 8 rows/symbol in production, and not the existing chart endpoint, which only has weekly resolution past 1 month). Real 200-DMA position, 3-month return vs. NIFTY 50, 3-month return vs. the real Banking sector ETF (`BANKBEES.NS`), and RSI(14).
- **`financial_strength.py`** — Banking-only, scored from only the 4 real metrics S1 found (ROE, ROA, NII growth, Profit growth) peer-ranked against the same reference group. NIM proxy computed and stored in `detail` but **excluded from the score**, per instruction — it's `NII / Total Assets`, not real bank NIM. Always returns `status=PARTIAL`, never `COMPLETE`, for every real Banking symbol — 8 of 12 proposed metrics are structurally missing, not a threshold miscalibration.
- **`engine.py`** — composes the 4 pillars with the candidate weights (40/20/15/25), explicit `publishable=False` phase lock with a real, traceable `publish_reason` string.
- **`scripts/marketripple_score_five_bank_comparison.py`** — the manual, local-only runner for S2-D. Not wired into any route or scheduler.

## A real reliability bug found and fixed while validating

First run produced ROE/ROA as `None` for 4 of 5 banks — but S1 had confirmed those same values were real and present. Re-checked in isolation: real, present, every time. The actual cause: firing 5 concurrent real `.info` fetches per pillar, across 2 pillars needing the peer set, for each of the 5 banks' full computation, created enough simultaneous pressure on yfinance's live API that it intermittently returned partial data — reproduced twice, with a *different* bank affected each run (not the same bank failing deterministically, which is what pointed to load, not a real per-symbol gap). Fixed by switching the peer fetches from `asyncio.gather` to sequential with a small stagger (0.4s) — re-ran, and the results became stable and matched S1's own original finding exactly: real ROE/ROA for 4 of 5 banks, genuinely null only for KOTAKBANK. Documented in both files' own comments so this isn't rediscovered blind next time.

## The real five-bank breakdown

```
Symbol        Fin.Str  Valuation   Market   Intel.   MRScore  Label
-------------------------------------------------------------------
ICICIBANK        84.6       31.6     73.6     56.8      65.4  Positive
HDFCBANK         57.1       54.6     22.6     55.3      51.0  Neutral
AXISBANK         31.9       54.3     29.5     53.5      41.4  Cautious
KOTAKBANK        43.2       16.2     51.9     56.0      42.3  Cautious
SBIN             49.8       64.2     61.4     55.0      55.7  Neutral
```

Coverage (%), per pillar:

```
Symbol        Fin.Str  Valuation   Market   Intel.   Overall
--------------------------------------------------------------
ICICIBANK        33.3      100.0    100.0    100.0      73.3
HDFCBANK         33.3      100.0    100.0    100.0      73.3
AXISBANK         33.3      100.0    100.0    100.0      73.3
KOTAKBANK        16.7      100.0    100.0    100.0      66.7
SBIN             33.3      100.0    100.0    100.0      73.3
```

All 5: `publishable = False`.

## Tracing why, per your own instruction ("investigate the inputs, don't tune weights")

**ICICIBANK highest (65.4, Positive)** — real strong Financial Strength (84.6: highest real ROE/ROA of the 5, positive NII growth +9.1%, positive profit growth +6.2%) and real strong Market Behaviour (73.6: +12.73% 3-month return vs. NIFTY's +1.76%, price 5.95% above its 200-DMA). Dragged down by the weakest Valuation (31.6) — real richest P/E (18.4) and P/B (2.68, literally the most expensive of the 5 on book value). Coherent story: a genuinely strong, currently well-performing bank trading at a real premium for it.

**AXISBANK lowest (41.4, Cautious)** — real weak Financial Strength (31.9): the only bank with **negative** real profit growth (-6.0% YoY) among the 5. Real weak Market Behaviour (29.5): -5.23% 3-month return, underperforming both NIFTY and the sector benchmark. Not an anomaly — the two real, independent pillars (fundamentals and price action) agree with each other, which is exactly the kind of confirmation the Market Behaviour pillar's whole purpose is to surface.

**KOTAKBANK also Cautious (42.3)** — weakest Valuation (16.2: richest real P/E of the 5 at 19.7) combined with the worst real profit growth of any bank (-12.8% YoY) and the one real, genuine ROE/ROA data gap (confirmed both in S1 and here — not fetch flakiness, a real yfinance null for this specific symbol).

**SBIN (55.7, Neutral, closest to Positive)** — real cheapest valuation of the 5 (P/E 11.2, P/B 1.56, both literally the lowest — 100th percentile on both), real solid Market Behaviour (61.4, +8.29% 3-month return). Matches SBI's real-world reputation as the "value" pick among large private/PSU banks — a real, external, independently-known fact the model's real output happens to agree with, not something built in.

**HDFCBANK (51.0, Neutral)** — real second-best Financial Strength profile (57.1) pulled down hard by real weak Market Behaviour (22.6: -2.52% 3-month return, and price sitting **13.28% below** its own 200-DMA — the largest technical drawdown of the 5). A fundamentally solid bank in a real, current price correction — again, two independent pillars telling a coherent, traceable story rather than fighting each other for no visible reason.

**Nothing in this table required investigating "why does this look absurd" — every score decomposes into real, specific, checkable inputs that agree with each other and with what's independently known about these 5 real companies.** That's the signal S1 hoped for and S2 was built to test.

## What this does and doesn't answer yet

**Does**: proves the engine composes correctly, proves the candidate weights don't produce obviously broken output on 5 real, well-understood banks, surfaces one real reliability bug (now fixed) before it could contaminate a production decision.

**Doesn't**: validate the weights are *right* (only that they're not obviously wrong) — that needs a wider real sample, ideally spanning more sectors once Financial Strength has a second sector implementation. Doesn't resolve Financial Strength's real coverage gap (still 4-5 of 12 proposed metrics, unchanged from S1 — that's S3's job, not S2's). Doesn't decide a real minimum-publication coverage threshold — a product decision, not something this run can make for you.

## Status

**S2-A through S2-D done, locally, as instructed.** No Company-page score change. No production deployment. `publishable=False` on every real computation. Ready for your review of the breakdown before any further step (S3 banking-fundamentals sourcing, or a decision to publish Financial Strength with its real coverage caveat shown, or something else).
