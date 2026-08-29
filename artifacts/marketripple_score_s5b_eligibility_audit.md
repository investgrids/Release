# MarketRipple Score — S5-B: Publication Eligibility Audit

**Date:** 2026-08-29
**Scope:** Analysis only, per owner instruction — no threshold implemented, no `publishable` flip, no API/UI, no change to `BANKING_V1` scoring. Builds the reusable eligibility contract and runs a real 27-bank audit comparing 3 candidate policies.
**Branch:** `company-identity/c1-reconciliation`

## What was built

- **`app/services/marketripple_score/eligibility.py`** — `EligibilityPolicy` (a parameterized candidate policy: min real Financial Strength metrics used, min overall coverage, whether Financial Strength is a required pillar) and `evaluate_eligibility()`, which never chooses a threshold itself — every candidate policy is passed in explicitly. Stable, machine-readable reason codes (`MISSING_REQUIRED_PILLAR`, `NO_ELIGIBLE_FINANCIAL_PERIOD`, `INSUFFICIENT_FINANCIAL_METRICS`, `INSUFFICIENT_OVERALL_COVERAGE`, `STALE_FINANCIAL_DATA` reserved) — never LLM prose, so a future frontend renders fixed copy per code.
- **`financial_metrics_used_from_coverage_pct()`** — recovers the exact count of real Financial Strength metrics used (0-7) from the already-persisted `financial_coverage_pct` (stored scaled against the original 12-metric ambition) with zero information loss and zero new network calls — verified exactly against real, already-observed values (YESBANK: 50.0%→6 pre-quarantine, 25.0%→3 post-quarantine).
- **Snapshot model extended** (`MarketRippleScoreSnapshot`) with `valuation_coverage_pct`, `market_behaviour_coverage_pct`, `current_intelligence_coverage_pct` — S5-A only persisted Financial Strength's own coverage; this audit needed all four pillars', so the schema was completed before auditing rather than shipping an incomplete table. Re-ran the real 27-bank backfill once to populate them.
- **`scripts/s5b_eligibility_audit.py`** — reads the real, already-persisted S5-A snapshots (zero new network calls) plus a cheap DB-only quarantine check, evaluates 3 candidate policies side by side, and computes a real, population-derived freshness reference (the mode of `financial_data_as_of` across all 27 banks) rather than a guessed staleness rule.
- 6 new pure-logic tests (`test_marketripple_score_eligibility.py`). Full relevant suite: **35/35 pass**.

## Real 27-bank audit results

| Symbol | FinMetrics | Fin%(of 7) | ValCov% | MktCov% | CICov% | Overall% | FinDataAsOf | Quarantined | A | B | C |
|---|---|---|---|---|---|---|---|---|---|---|---|
| AUBANK | 6 | 85.7 | 100.0 | 100.0 | 0.0 | 73.3 | FY2025Q3 | | Y | Y | Y |
| AXISBANK | 7 | 100.0 | 100.0 | 100.0 | 100.0 | 83.3 | FY2025Q3 | | Y | Y | Y |
| BANDHANBNK | 6 | 85.7 | 100.0 | 100.0 | 0.0 | 73.3 | FY2025Q3 | | Y | Y | Y |
| BANKBARODA | 7 | 100.0 | 100.0 | 100.0 | 40.0 | 68.3 | FY2025Q3 | | Y | Y | **N** |
| BANKINDIA | 7 | 100.0 | 100.0 | 100.0 | 0.0 | 77.8 | FY2025Q3 | | Y | Y | Y |
| CANBK | 6 | 85.7 | 100.0 | 100.0 | 0.0 | 73.3 | FY2025Q3 | | Y | Y | Y |
| CENTRALBK | 7 | 100.0 | 100.0 | 100.0 | 0.0 | 77.8 | FY2025Q3 | | Y | Y | Y |
| CUB | 6 | 85.7 | 100.0 | 100.0 | 0.0 | 73.3 | FY2025Q3 | | Y | Y | Y |
| FEDERALBNK | 6 | 85.7 | 100.0 | 100.0 | 0.0 | 73.3 | FY2025Q3 | | Y | Y | Y |
| HDFCBANK | 7 | 100.0 | 100.0 | 100.0 | 100.0 | 83.3 | FY2025Q3 | | Y | Y | Y |
| ICICIBANK | 7 | 100.0 | 100.0 | 100.0 | 100.0 | 83.3 | FY2025Q3 | | Y | Y | Y |
| IDBI | 7 | 100.0 | 100.0 | 100.0 | 0.0 | 77.8 | FY2025Q3 | | Y | Y | Y |
| IDFCFIRSTB | 6 | 85.7 | 100.0 | 100.0 | 0.0 | 73.3 | FY2025Q3 | | Y | Y | Y |
| INDIANB | 7 | 100.0 | 100.0 | 100.0 | 0.0 | 77.8 | FY2025Q3 | | Y | Y | Y |
| INDUSINDBK | 6 | 85.7 | 100.0 | 100.0 | 10.0 | **57.5** | FY2025Q3 | | **N** | **N** | **N** |
| IOB | 7 | 100.0 | 100.0 | 100.0 | 0.0 | 77.8 | FY2025Q3 | | Y | Y | Y |
| J&KBANK | 7 | 100.0 | 100.0 | 100.0 | 0.0 | 77.8 | FY2025Q3 | | Y | Y | Y |
| KARURVYSYA | 6 | 85.7 | 100.0 | 100.0 | 0.0 | 73.3 | FY2025Q3 | | Y | Y | Y |
| KOTAKBANK | 6 | 85.7 | 100.0 | 100.0 | 100.0 | 80.0 | FY2025Q3 | | Y | Y | Y |
| MAHABANK | 7 | 100.0 | 100.0 | 100.0 | 0.0 | 77.8 | FY2025Q3 | | Y | Y | Y |
| PNB | 7 | 100.0 | 100.0 | 100.0 | 30.0 | 65.8 | FY2025Q3 | | Y | Y | **N** |
| PSB | 7 | 100.0 | 100.0 | 100.0 | 0.0 | 77.8 | FY2025Q3 | | Y | Y | Y |
| RBLBANK | 6 | 85.7 | 100.0 | 100.0 | 0.0 | 73.3 | FY2025Q3 | | Y | Y | Y |
| SBIN | 7 | 100.0 | 100.0 | 100.0 | 100.0 | 83.3 | FY2025Q3 | | Y | Y | Y |
| UCOBANK | 7 | 100.0 | 100.0 | 100.0 | 0.0 | 77.8 | FY2025Q3 | | Y | Y | Y |
| UNIONBANK | 7 | 100.0 | 100.0 | 100.0 | 0.0 | 77.8 | FY2025Q3 | | Y | Y | Y |
| **YESBANK** | **3** | **42.9** | 100.0 | 100.0 | 50.0 | **57.5** | **none** | **YES** | **N** | **N** | **N** |

Policies: **A** = ≥4/7 financial metrics, ≥60% overall coverage. **B** = ≥5/7, ≥65%. **C** = ≥6/7, ≥70%.

## Real findings

**1. Metric-count distribution is cleanly bimodal — there is no ambiguous boundary case in the real population.** 16 banks use 7/7 real Financial Strength metrics, 10 use 6/7, and exactly **one** bank (YESBANK) sits at 3/7. Zero banks fall in the 1/7-5/7 range. This means, for today's real universe, **any `min_financial_metrics_used` threshold from 4 through 6 produces the identical outcome** — it excludes only YESBANK either way. The choice within that range doesn't change today's result; it only matters for future-proofing against a similar case.

**2. Financial data freshness is currently a non-issue.** Every real bank's newest eligible financial period is the same `FY2025Q3` (YESBANK excepted, which has none at all after quarantine). No bank lags the population. The freshness check in `EligibilityPolicy` exists but has nothing to bite on yet in this real population — a real, honest "not a problem today" finding, not a guessed rule imposed preemptively.

**3. The real, binding constraint on Banking V1 eligibility is Current Intelligence coverage, not Financial Strength.** 15 of 27 real banks show 0.0% Current Intelligence coverage — no contributing AI signal evidence exists for them at all. This is what actually excludes **INDUSINDBK** under every single candidate policy, including the most lenient (Policy A): it has excellent financial data (6/7 metrics, 100% Valuation/Market coverage) but only 10% Current Intelligence coverage, dragging its overall coverage to 57.5% — below even Policy A's 60% floor. **INDUSINDBK's exclusion has nothing to do with data quality** — it's a real evidence-thinness case, categorically different from YESBANK's.

**4. YESBANK is excluded on three independent grounds under every policy** — missing required financial period, insufficient financial metric count, and insufficient overall coverage — while INDUSINDBK fails on only one (overall coverage). That's a real, meaningful distinction worth carrying into the eventual UI copy: a "data quality" block reads differently from an "evidence still building" block.

**5. Policy C (≥6/7, ≥70%) additionally excludes BANKBARODA and PNB** — both have **perfect** financial data (7/7 metrics) but weaker Current Intelligence (40%/30%). Since Financial Strength was designated the one *required* pillar (the others were explicitly allowed to tolerate missing evidence), excluding two banks with complete financial data primarily on Current Intelligence thinness is a harder case to defend than excluding YESBANK or INDUSINDBK.

## Candidate policy summary

| Policy | Eligible | Excluded | Why |
|---|---|---|---|
| A (≥4/7, ≥60%) | 25/27 | INDUSINDBK, YESBANK | evidence-thinness + data-quality |
| B (≥5/7, ≥65%) | 25/27 | INDUSINDBK, YESBANK | same — identical real outcome to A |
| C (≥6/7, ≥70%) | 23/27 | + BANKBARODA, PNB | adds 2 banks excluded mainly for thin (not missing) Current Intelligence |

## Decision (owner, 2026-08-29): BANKING_V1_P1

**≥5 of 7 real Financial Strength metrics, ≥65% overall evidence coverage, Financial Strength required as a pillar, an eligible financial period required.** Chosen over Policy A's 4/7 floor (too permissive for a public score — almost half the core Banking model absent isn't defensible even though today's population doesn't have a bank sitting at exactly 4/7) and over Policy C's 70% overall floor (would have additionally excluded BANKBARODA/PNB, both with *perfect* financial data, primarily for thin Current Intelligence — a pillar this design explicitly does not require).

### Schema cleanup that came with the decision

`financial_metrics_used_from_coverage_pct()` (deriving the real metric count from the old 12-metric-denominator `financial_coverage_pct`) was retired as the source of truth — "historical implementation baggage" for a publication decision, in the owner's words. `MarketRippleScoreSnapshot` now persists `financial_metrics_used_count`/`financial_metrics_total_count` directly, read straight from `PillarScore.metrics_used` at compute time — no reconstruction. `REAL_BANKING_METRICS_TOTAL = 7` is now a real, code-derived constant in `financial_strength.py` (`len(_FACT_METRICS) + 3`), not a magic number.

### Two-tier publication gate, deliberately kept separate

- **`publishable` / `publication_block_reason`** (existing, unchanged): the standing, whole-initiative phase lock, reaffirmed at every S5 checkpoint — stays `False` for every real snapshot until S5-E's real, multi-cycle shadow validation actually passes. **Not touched by this decision.**
- **`publication_policy_version` / `publication_block_reasons`** (new): the real, per-bank `BANKING_V1_P1` verdict — whether *this bank's own evidence* would clear the bar, independent of the phase lock. An empty reasons list means "this bank's real evidence is sufficient under BANKING_V1_P1 today; the phase lock is the only thing still holding `publishable` at `False`."

This distinction matters: it lets the real per-bank eligibility work be built, computed, and verified now, without silently overriding the separate, repeatedly-reaffirmed "not live yet" gate.

## Real verification (re-run, not just asserted)

Re-ran the real 27-bank backfill with the new fields, then read back every persisted `publication_block_reasons`:

**Result: 25/27 eligible under BANKING_V1_P1. Blocked: YESBANK, INDUSINDBK. Matches the predicted outcome exactly.**

- **YESBANK** — 3 independent reasons: `NO_ELIGIBLE_FINANCIAL_PERIOD`, `INSUFFICIENT_FINANCIAL_METRICS`, `INSUFFICIENT_OVERALL_COVERAGE`. A real data-quality case.
- **INDUSINDBK** — 1 reason only: `INSUFFICIENT_OVERALL_COVERAGE` (6/7 financial metrics, real and sufficient; 57.5% overall, driven by thin Current Intelligence). A real evidence-thinness case, correctly distinguished from YESBANK's by having only one reason instead of three.
- **`publishable` on every one of the 27 real rows: `False`** — confirmed the standing phase lock was not touched by wiring in the new eligibility verdict.

Combined MarketRipple Score test suite: **36/36 pass** (6 eligibility tests rewritten for the direct-count contract, 30 carried over unchanged).

## Status: S5-B CLOSED

Real policy decided, implemented, and verified against real data — not asserted from the earlier audit. `publishable` remains `False` everywhere pending S5-E. Ready for S5-C (Company-page UI), restrained to one MarketRipple Score, four explanatory pillars, one evidence line — no resurrection of a second AI score or confidence meter.
