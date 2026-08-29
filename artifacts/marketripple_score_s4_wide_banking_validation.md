# MarketRipple Score — S4 Wide Banking Validation

**Date:** 2026-08-29
**Scope:** Frozen S3-D algorithm and weights (zero code changes to scoring logic during this phase). 27 real NSE-listed banks (5 Large Private, 13 PSU, 8 Mid/Small Private, 1 Small Finance), `peer_group=ALL_BANKS`. `publishable=False` throughout.
**Branch:** `company-identity/c1-reconciliation` (local worktree, not merged to `main`)

## Universe

`LARGE_PRIVATE` (5): HDFCBANK, ICICIBANK, KOTAKBANK, AXISBANK, INDUSINDBK
`PSU` (13): SBIN, PNB, BANKBARODA, UNIONBANK, CANBK, BANKINDIA, CENTRALBK, IDBI, INDIANB, IOB, MAHABANK, UCOBANK, PSB
`MID_SMALL_PRIVATE` (8): FEDERALBNK, IDFCFIRSTB, BANDHANBNK, RBLBANK, CUB, J&KBANK, KARURVYSYA, YESBANK
`SMALL_FINANCE` (1): AUBANK

Derived from `app.api.companies._NSE_UNIVERSE` filtered to `sector == "Banking"` — 27 real matches, no synthetic entries.

## Full result table (27-bank peer universe)

| Symbol | Type | FinStr | Val | Mkt | Intel | MRScore | Coverage |
|---|---|---|---|---|---|---|---|
| MAHABANK | PSU | 83.5 | 51.2 | 80.8 | — | **74.3** | 77.8% |
| KARURVYSYA | Mid/Small Private | 89.1 | 18.9 | 93.0 | — | **71.2** | 73.3% |
| IDBI | PSU | 61.0 | 62.9 | 84.4 | — | **66.2** | 77.8% |
| IOB | PSU | 69.4 | 71.7 | 30.1 | — | **62.2** | 77.8% |
| ICICIBANK | Large Private | 68.7 | 30.8 | 84.3 | 56.4 | **60.4** | 83.3% |
| KOTAKBANK | Large Private | 71.8 | 16.9 | 78.0 | 55.4 | **57.6** | 80.0% |
| CUB | Mid/Small Private | 62.2 | 20.2 | 93.5 | — | **57.3** | 73.3% |
| UNIONBANK | PSU | 39.8 | 62.7 | 86.9 | — | **55.3** | 77.8% |
| INDIANB | PSU | 56.5 | 47.9 | 68.1 | — | **56.5** | 77.8% |
| PNB | PSU | 32.0 | 80.9 | 70.1 | — | **53.6** | 65.8% |
| HDFCBANK | Large Private | 64.5 | 42.7 | 19.1 | 55.0 | **51.0** | 83.3% |
| AUBANK | Small Finance | 62.2 | 4.1 | 81.4 | — | **50.5** | 73.3% |
| YESBANK | Mid/Small Private | 52.8 | 44.7 | 40.6 | 56.3 | **50.2** | 70.8% |
| INDUSINDBK | Large Private | 38.4 | 29.1 | 77.1 | 76.0 | **51.7** | 57.5% |
| FEDERALBNK | Mid/Small Private | 52.6 | 13.4 | 88.8 | — | **49.4** | 73.3% |
| AXISBANK | Large Private | 58.3 | 32.1 | 38.4 | 53.2 | **48.8** | 83.3% |
| BANKINDIA | PSU | 31.2 | 80.5 | 52.3 | — | **48.6** | 77.8% |
| SBIN | PSU | 45.5 | 37.3 | 57.0 | 54.8 | **47.9** | 83.3% |
| J&KBANK | Mid/Small Private | 34.4 | 57.7 | 70.6 | — | **47.9** | 77.8% |
| IDFCFIRSTB | Mid/Small Private | 48.7 | 16.1 | 86.0 | — | **47.5** | 73.3% |
| CENTRALBK | PSU | 37.6 | 83.8 | 25.8 | — | **47.6** | 77.8% |
| UCOBANK | PSU | 37.7 | 59.9 | 34.6 | — | **43.0** | 77.8% |
| RBLBANK | Mid/Small Private | 36.5 | 21.6 | 81.7 | — | **41.6** | 73.3% |
| CANBK | PSU | 28.8 | 69.4 | 37.3 | — | **41.3** | 73.3% |
| BANKBARODA | PSU | 35.1 | 48.7 | 15.1 | — | **39.0** | 68.3% |
| PSB | PSU | 32.5 | 55.0 | 28.5 | — | **37.7** (rerun: 39.8) | 77.8% |
| BANDHANBNK | Mid/Small Private | 25.0 | 30.9 | 21.0 | — | **25.8** | 73.3% |

## 1. Distribution test — PASS

Range 25.8 (BANDHANBNK) to 74.3 (MAHABANK), spread of 48.5 points, mean ≈51.3. Rough buckets: 3 banks <40, 10 in 40-50, 9 in 50-60, 5 in 60-75. Real, meaningful dispersion across all four bank types, not a collapse around a neutral midpoint, and not artificially bimodal.

## 2. Outlier test — PASS

Every top-5 and bottom-5 bank traces to a coherent, real evidence trail. No bank required a weight change to become explicable.

**Top 5:**
- **MAHABANK** (FinStr 83.5, highest MRScore) — driven by Net NPA 0.20%, ROA 1.74%, ROE 22.96% (highest observed), profit growth 26.6%. CET1 13.60% is middling — the top score is earned on asset quality and returns, not capital ratio.
- **KARURVYSYA** (FinStr 89.1, highest FinStr of all 27) — Gross NPA 0.83% (best-in-class), Net NPA 0.20%, ROA 1.72%, profit growth 29.3%. CET1 15.91%, upper-middle only.
- **IDBI** (FinStr 61.0) — CET1 19.91% (highest in the detailed sample), ROE 13.87%, profit growth 20.7%, but NII growth −7.6% (real, negative) — a genuinely mixed profile that still clears a respectable score.
- **IOB** (FinStr 69.4) — ROE 16.53%, profit growth 59.6% (highest in this group), Gross NPA 2.55% / Net NPA 0.42%, CET1 14.33% mid-pack.
- **ICICIBANK** (FinStr 68.7, stable across two independent runs) — ROA 2.38% (best among large privates), ROE 16.07%, Gross NPA 1.96% / Net NPA 0.42%, but profit growth only 6.2% — real and modest, matching ICICI's known slower recent earnings growth.

**Bottom 5:**
- **BANDHANBNK** (FinStr 25.0, lowest of 27) — profit growth **−55.4%** (real, severe), Gross NPA 4.68% / Net NPA 1.28% (weakest asset quality sampled), NII growth −5.8%. CET1 14.54% is unremarkable-but-fine — proof a normal capital ratio cannot rescue a bank whose other real metrics are poor.
- **PSB** (FinStr 32.5) — ROA 0.73%, ROE 9.79%, Gross NPA 3.83% / Net NPA 1.25% — weak across the board; CET1 14.04% again mid-pack, not the driver.
- **BANKBARODA** (FinStr 35.1) — profit growth **−4.2%** (negative), CET1 12.38% (lowest CET1 in the detailed sample).
- **CANBK** (FinStr 28.8, 2nd lowest of 27) — NII growth −4.3%, Gross NPA 3.34% / Net NPA 0.89%, CET1 11.97% — the lowest CET1 observed in this batch, consistent with a genuinely weak capital position compounding weak NPA trends. ROE missing (correctly excluded, not defaulted).
- **RBLBANK** (FinStr 36.5) — ROA 0.61% (weakest in this batch), CET1 13.16%. ROE missing, correctly excluded.

## 3. Peer-universe sensitivity — REAL FINDING, methodology decision needed

| Symbol | FinStr (5-bank) | FinStr (27-bank) | Δ | MRScore (5-bank) | MRScore (27-bank) | Δ |
|---|---|---|---|---|---|---|
| ICICIBANK | 67.9 | 68.7 | +0.8 | 60.2 | 60.4 | +0.2 |
| HDFCBANK | 51.2 | 64.5 | +13.3 | 48.6 | 51.0 | +2.4 |
| AXISBANK | 42.9 | 58.3 | +15.4 | 48.2 | 48.8 | +0.6 |
| KOTAKBANK | 62.5 | 71.8 | +9.3 | 53.8 | 57.6 | +3.8 |
| SBIN | 27.4 | 45.5 | +18.1 | 45.5 | 47.9 | +1.9 |

Three of the five original banks move 9-18 points in Financial Strength purely from widening the comparison population — not from any new data. The 5-bank group was all large private banks, a strong, tight cohort, so ranking within it looked harsher; against the full 27-bank universe (13 of which are structurally weaker PSU banks) the same real metrics land in a much higher percentile. **This is not a bug — the percentile math is unchanged — but it means "peer universe" is a real product/methodology decision that materially changes a published score, not an implementation detail.** It must be fixed and disclosed (e.g., "ranked against 27 NSE-listed banks") before S5 publication; leaving it ambiguous risks two surfaces showing two different "real" scores for the same bank.

## 4. Missing-data test — PASS

Coverage ranges 57.5% (INDUSINDBK, missing several inputs) to 83.3% (banks with all 4 pillars populated). Banks missing Current Intelligence (mostly PSU/mid-small private, 18 of 27) span the *entire* score range — from BANDHANBNK (25.8, lowest) to MAHABANK (74.3, highest) — with no correlation toward inflated scores. Coverage_pct correctly drops (73.3-77.8%) for every bank missing a pillar versus the 80-83.3% of fully-covered banks. No evidence anywhere of a missing metric being silently treated as zero or as a score booster.

## 5. Metric dominance — CET1 measured, not dominant (no change made)

- **KOTAKBANK**: CET1 21.71% — the single highest CET1 observed anywhere in this validation — correlates with a real top-3 FinStr (71.8), but is still outranked by KARURVYSYA (CET1 only 15.91%, FinStr 89.1) and MAHABANK (CET1 13.60%, FinStr 83.5), both winning on asset-quality/return metrics instead.
- **IDBI**: highest CET1 in the detailed 7-bank sample (19.91%) yet ranks *below* both KARURVYSYA and MAHABANK on FinStr.
- **BANDHANBNK**: CET1 14.54%, solidly unremarkable-but-fine — yet dead last overall, because every other real metric (profit growth −55.4%, weak NPA) is poor. If CET1 carried outsized weight, an ordinary capital ratio should have kept it out of last place; it didn't.
- **CANBK**: lowest observed CET1 (11.97%) does coincide with a low score, but compounds with real negative NII growth and weak NPA — CET1 alone can't be isolated as the driver.

**Conclusion: CET1 is one of seven equally-weighted metrics and behaves like one — it correlates but does not dominate.** No weight change is recommended.

## 6. Stability/determinism test — PASS

A same-day rerun of 7 banks (IDBI, IOB, ICICIBANK, CANBK, BANKBARODA, RBLBANK, AUBANK) against the identical frozen code and peer group produced **byte-identical Financial Strength scores for all 7** (e.g. ICICIBANK 68.7→68.7, CANBK 28.8→28.8). MRScore itself moved only where expected: ICICIBANK 60.4→58.1, IDBI 66.2→65.8, PSB 37.7→39.8; the other 4 were exactly unchanged. These moves are consistent with genuinely time-varying Market Behaviour (live price) and Current Intelligence (signal decay) inputs, exactly the two components the experiment design flagged as allowed to move — not with any nondeterminism in the fact-derived Financial Strength pillar.

## 7. Cross-sectional source-quality finding — YESBANK (documented, not fixed)

YESBANK's real, as-filed CET1 (0.13%), Gross NPA (0.02%), Net NPA (0%), and ROA (0.01%) are internally consistent across all 8 real quarters checked — so the existing within-entity trailing-history anomaly detector correctly reports no anomaly — but are ~100x smaller than every other bank and than Yes Bank's real, publicly known actual CET1 (~13-14%), strongly suggesting a genuine per-filer XBRL scale/unit submission error. Per instruction, this was **not corrected**; the frozen engine computed YESBANK's FinStr=52.8/MRScore=50.2 using the real, uncorrected values.

**Contamination counterfactual** (excluding YESBANK from the peer pool for 8 sampled other banks):

| Symbol | FinStr (+YESBANK) | FinStr (−YESBANK) | Δ |
|---|---|---|---|
| ICICIBANK | 68.7 | 69.7 | +1.0 |
| HDFCBANK | 64.5 | 65.1 | +0.6 |
| SBIN | 45.5 | 45.5 | 0.0 |
| BANKBARODA | 35.1 | 34.5 | −0.6 |
| FEDERALBNK | 52.6 | 52.7 | +0.1 |
| AUBANK | 62.2 | 62.7 | +0.5 |
| IDBI | 61.0 | 61.5 | +0.5 |
| KARURVYSYA | 89.1 | 90.7 | +1.6 |

Effect is small and bounded (≤1.6 points) — but this measures only the effect of *removing* a contaminated low outlier from the percentile pool, not the effect of a hypothetically *corrected* (~13-14%) value, which would land mid-pack on CET1 rather than dead-last and could shift other banks' CET1 percentiles by more than this bounded test shows. This is the real, scoped gap in the two-dimension quality model: within-entity validation (exists, `quality.py`) catches a filer whose values suddenly deviate from its own history; cross-sectional/plausibility-bound validation (does not exist) would catch a filer that's internally consistent but implausible against the whole population. Recommended as a prioritized engineering follow-up before S5 publication — not built during this validation run, per instruction not to invent thresholds reactively.

## Other real, non-blocking observations

- Real `parse_failed` counts during the wide backfill (INDUSINDBK 18, UCOBANK 9, IDFCFIRSTB 9, CUB 18, KARURVYSYA 27 of 72 attempted extractions each) — likely older/archived XBRL URLs failing for less-liquid banks' historical filings. Non-blocking: every affected bank still has a real, populated most-recent quarter (FY2025Q3).
- The 27-bank sequential peer-fetch run took ~37-40 minutes real wall time — a real productionization concern for S5 (caching/parallelization), not a correctness issue.

## GO/NO-GO recommendation: CONDITIONAL GO for S5

The frozen S3-D algorithm and weights hold up under wide validation: real distribution, fully explicable outliers, no missing-data inflation, deterministic fact-derived scoring, and no single-metric dominance. Two items should be resolved before actual publication — neither requires reopening the score design itself:

1. **Formalize the peer universe.** Decide and disclose what population a published score is ranked against (the peer-universe sensitivity test shows this is a ±18-point decision, not a rounding error).
2. **Build the cross-sectional plausibility check** the YESBANK finding surfaced, so a future internally-consistent-but-implausible filer doesn't silently enter the peer pool uncorrected.

Recommend: proceed to resolve these two items, then move to S5 publication prep as previously scoped (single MarketRipple Score display, four pillar sub-scores, evidence-coverage line — no second AI score, no separate confidence number).
