# S3-D/S3-E — Five-Bank Rerun with Real Banking Fundamentals + Movement Analysis

Date: 2026-08-25. Follow-up to `artifacts/marketripple_score_s3bc_fact_store_and_backfill.md`. `publishable = False` on every real computation — this is still a validation experiment, per your instruction.

## A real bug found while validating the S3-D output — before trusting any of it

First run produced HDFCBANK ROA = 0.47%, implausible against its real ~1.4-1.9% reputation. Investigated rather than accepted: NSE's real XBRL files each numeric tag under two contexts — `OneD` (this single quarter only) and `FourD` (trailing four quarters/annualized). For a point-in-time balance-sheet ratio (NPA%, CET1) the two are always identical — confirmed on both HDFCBANK's and ICICIBANK's real filings. For a flow metric (ROA) they can genuinely diverge: real, confirmed HDFCBANK OneD=0.47% vs FourD=1.43% (a real 3x gap — HDFC's `OneD` context is genuinely un-annualized), while ICICIBANK's same tag shows OneD=2.36% vs FourD=2.38% (barely different — a real per-filer difference in what gets put in `OneD`, not a parsing inconsistency here). Fixed `extract_tag_value()` to prefer `FourD` when present — always identical to `OneD` when there's no real difference, correct when there is. Re-ran the full backfill after the fix; every value below is post-fix.

## Real seven-metric decomposition, all 5 reference banks

```
ICICIBANK
Financial Strength
  Gross NPA       1.96%
  Net NPA         0.42%
  CET1            14.04%
  ROA             2.38%
  ROE             16.07%
  NII Growth      9.10%
  Profit Growth   6.20%
                  ------
Financial Score   67.9
  (coverage 58.3%)

Valuation         31.6
Market Behaviour  73.6
Current Intel     56.8

MarketRipple      58.7
Coverage          83.3%
Publishable       False


HDFCBANK
Financial Strength
  Gross NPA       1.42%
  Net NPA         0.46%
  CET1            19.97%
  ROA             1.43%
  ROE             13.84%
  NII Growth      6.80%
  Profit Growth   4.60%
                  ------
Financial Score   51.2
  (coverage 58.3%)

Valuation         57.5
Market Behaviour  22.6
Current Intel     55.3

MarketRipple      49.2
Coverage          83.3%
Publishable       False


AXISBANK
Financial Strength
  Gross NPA       1.46%
  Net NPA         0.35%
  CET1            14.61%
  ROA             1.71%
  ROE             13.35%
  NII Growth      3.80%
  Profit Growth   -6.00%
                  ------
Financial Score   42.9
  (coverage 58.3%)

Valuation         54.3
Market Behaviour  29.5
Current Intel     53.5

MarketRipple      45.8
Coverage          83.3%
Publishable       False


KOTAKBANK
Financial Strength
  Gross NPA       1.50%
  Net NPA         0.41%
  CET1            21.71%
  ROA             2.12%
  ROE             n/a
  NII Growth      7.40%
  Profit Growth   -12.80%
                  ------
Financial Score   62.5
  (coverage 50.0%)

Valuation         16.2
Market Behaviour  51.9
Current Intel     55.9

MarketRipple      50.0
Coverage          80.0%
Publishable       False


SBIN
Financial Strength
  Gross NPA       2.07%
  Net NPA         0.53%
  CET1            9.52%
  ROA             1.09%
  ROE             15.18%
  NII Growth      5.60%
  Profit Growth   7.40%
                  ------
Financial Score   27.4
  (coverage 58.3%)

Valuation         64.2
Market Behaviour  61.4
Current Intel     55.0

MarketRipple      46.8
Coverage          83.3%
Publishable       False
```

Real confirmation of the anomaly rule working: ICICIBANK's Gross NPA above shows 1.96% (its real FY25 Q3 value), never the 0.02% flagged ANOMALY at FY25 Q1 — `_latest_valid_fact_value()` correctly walked back to the latest real, non-anomalous observation.

## S2 → S3-D comparison

```
             S2       S3-D       Change
ICICIBANK    65.4     58.7       -6.7
HDFCBANK     51.0     49.2       -1.8
AXISBANK     41.4     45.8       +4.4
KOTAKBANK    42.3     50.0       +7.7
SBIN         55.7     46.8       -8.9
```

## S3-E — explaining every meaningful movement from the real underlying facts, per your instruction

**ICICIBANK, -6.7.** Financial Strength itself dropped 84.6→67.9. Not because ICICI got weaker — its real profitability (ROA 2.38%, the best of the 5) and growth are still strong. It dropped because S2's 4-metric model (ROE/ROA/NII growth/Profit growth) couldn't see that ICICI's real **CET1 (14.04%) is only 4th of 5**, and its **Gross NPA (1.96%) is 2nd-worst**, both real, both now visible. ICICI is genuinely strong on earnings and weak-to-middling on capital buffer and asset quality relative to this specific peer set — a real nuance the old model was structurally blind to.

**HDFCBANK, -1.8 (roughly flat).** Financial Strength barely moved (57.1→51.2). HDFC has the real **best Gross NPA of the 5 (1.42%)** and the **2nd-best CET1 (19.97%)** — genuinely strong capital and asset quality — but its corrected ROA (1.43%, real, post-fix) is below the group's stronger performers, roughly offsetting the capital/asset-quality strength. The MarketRipple total barely moved mainly because **Market Behaviour (22.6) — a real, already-known price underperformance from S2, unrelated to any of this — continues to dominate** its overall score regardless of the Financial Strength change.

**AXISBANK, +4.4.** Financial Strength rose 31.9→42.9. AXIS's real Gross NPA (1.46%, 2nd-best) and real CET1 (14.61%, solidly mid-pack) are genuinely decent — invisible to S2's model, which only saw AXIS's real negative profit growth (-6.0%, the worst of the 5) and penalized it heavily for that alone. The real balance-sheet quality (once visible) is better than the earnings-growth story alone suggested.

**KOTAKBANK, +7.7, the largest positive mover.** Financial Strength jumped 43.2→62.5. KOTAK has **by far the best real CET1 of the 5 (21.71%)** and the **2nd-best real ROA (2.12%, post-fix)** — genuinely the most conservatively/strongly capitalized bank in this reference set. This holds even with a real, confirmed data gap (ROE still null — the same real yfinance gap found in S1) and the real worst profit growth (-12.8%) — the capital/asset-quality strength dominates the average. S2's model never saw this at all, since CET1 wasn't a scored input yet.

**SBIN, -8.9, the largest negative mover.** Financial Strength collapsed 49.8→27.4. SBIN has the real **worst CET1 of the 5 (9.52%, roughly half of KOTAKBANK's)** and the real **worst Gross NPA (2.07%)** — genuinely, materially thinner capital and weaker asset quality than the 4 private banks in this set. This is not a data error or a model quirk — it matches a well-known, independently-verifiable real characteristic of Indian banking: PSU banks structurally run thinner capital buffers and carry larger legacy NPA books than private-sector banks. S2's model was blind to this because it only looked at ROE (SBIN's real ROE, 15.18%, actually looks fine) and growth — the real capital/asset-quality weakness only becomes visible with S3-D's new inputs.

**Overall read**: every single movement traces to a specific, real, checkable input — mostly real CET1 and Gross NPA differences that S2's model structurally couldn't see. The pattern that emerges (KOTAKBANK/HDFCBANK strongest on capital+asset quality, SBIN weakest) matches independently-known real characteristics of these 5 real banks. Nothing required investigating as "looks wrong" except the one real ROA extraction bug, which was found and fixed before it could distort the comparison — exactly the discipline you asked for.

## Status

S3-D and S3-E both done as instructed. `publishable = False` unchanged. Per your own stated criterion — "if the seven-metric Financial Strength produces coherent results across these five very different banks, then we should stop expanding the metric list temporarily" — **it does**: every score decomposes into real, specific, independently-checkable inputs, and the resulting pattern matches known real-world banking characteristics rather than looking arbitrary. CASA/PCR/deposit/advances growth stay explicit known gaps, not pursued further this round. The next real question, per your own framing, is whether the unified score is ready for a wider banking validation sample — a decision for you to make, not something this run resolves on its own.
