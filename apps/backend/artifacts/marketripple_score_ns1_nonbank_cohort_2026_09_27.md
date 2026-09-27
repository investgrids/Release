# MarketRipple Score — Non-Banking Commercial & Industrial V1 (NS1)

**Date:** 2026-09-27
**Status:** Engine implemented, locally computed and tested. `publishable` remains hardcoded False (S2 phase lock, unchanged) for every methodology, Banking included. No production DB writes, no push, no deploy.
**Scope:** Local dev DB (`ig_dev.db`) only.

## 1. Data inventory (measured, not assumed)

Real sector distribution of the live company universe (`app.api.companies._NSE_UNIVERSE`, 512 companies):

| Sector | Count | Sector | Count |
|---|---|---|---|
| Infrastructure | 68 | Power | 18 |
| Finance | 62 | Healthcare | 18 |
| Consumer | 40 | Metals | 18 |
| Automotive | 39 | Energy | 17 |
| Technology | 33 | Defence | 13 |
| Pharmaceuticals | 31 | Cement | 11 |
| Banking | 27 | Real Estate | 11 |
| Chemicals | 27 | Media / Telecom / Insurance / Textiles / ETF / REIT / InvIT / Electronics / Retail | ≤10 each |
| FMCG | 26 | | |

Sampled 3 real companies each across 9 candidate sectors live via `scripts/ns1_nonbank_data_inventory.py` (no fixtures — every value below is a real, live yfinance fetch), checking: currency, multi-period revenue/net income (for growth), EBIT/interest expense (for interest coverage), balance-sheet total debt/equity/total assets/current liabilities (for ROE/ROCE/D-E), and 1-year daily price depth.

**Result:** Technology, FMCG, Automotive, Pharmaceuticals, Chemicals, Consumer, and Metals showed real, complete multi-period statement data for the large majority of sampled companies (5-period financials, 4-5 period balance sheets, 252 real daily price rows). Two real, live-confirmed staleness cases surfaced during sampling itself — TATAMOTORS (renamed TMPV, 2025-10-24, per `company_entity.py`'s own documented history) and a delisted-shaped gap for GMRINFRA — which is exactly why peer universes are derived live from `_NSE_UNIVERSE`, never hand-typed (see §2).

**Real finding that changed the metric design:** `.info.get("returnOnEquity")` was `None` for the majority of sampled non-Technology companies (HINDUNILVR, ITC, NESTLEIND, MARUTI, most Pharma/Chemicals/Consumer/Metals names), and `.info.get("debtToEquity")` was present but inconsistently scaled across companies (0.096 to 314.833 — not a uniform convention). Both are avoided; every industrial metric is self-computed directly from the company's own real `.financials`/`.balance_sheet` line items instead.

**Structurally excluded (real, cited reason, not "not tried yet"):**
- **Finance** (NBFC/AMC/Insurance) — sampled BAJFINANCE/SBILIFE were real but missing EBIT, Current Liabilities, and/or Total Debt in exactly the pattern a financial-company statement structure produces. Needs its own regulatory-capital/AUM-based methodology.
- **Insurance** — same structural reason.
- **Banking** — already has its own frozen BANKING_V1 methodology; never touched by this cohort.

**Not yet measured at all** (a different status from structural exclusion — simply outside this pass's sampling): Infrastructure, Power, Energy, Real Estate, Telecom, Media, Cement, Healthcare, Textiles, Electronics, Retail, Defence, ETF, REIT, InvIT. A future pass would need to actually sample these before claiming they fit or don't fit this metric shape.

## 2. Implementation

**New module:** `app/services/marketripple_score/sector_universe.py` — `NONBANK_INDUSTRIAL_SECTORS` (the measured 7-sector cohort), `sector_peer_universe(sector)` (derived live from `_NSE_UNIVERSE`, same discipline as `banking_universe.py`'s own `ALL_ELIGIBLE_NSE_BANKS` — never a hand-typed list, which is exactly what caught the TATAMOTORS/GMRINFRA staleness during sampling).

**New module:** `app/services/marketripple_score/financial_strength_industrial.py` — a completely separate metric set from Banking's, no NPA/CET1/regulatory ratio anywhere in it:

| Metric | Formula | Source |
|---|---|---|
| `revenue_growth_pct` | Total Revenue YoY | `.financials` |
| `profit_growth_pct` | Net Income YoY | `.financials` |
| `roe` | Net Income / Stockholders Equity (latest) | `.financials` + `.balance_sheet` |
| `roce` | EBIT / (Total Assets − Current Liabilities) (latest) | `.financials` + `.balance_sheet` |
| `debt_to_equity` | Total Debt / Stockholders Equity (latest) | `.balance_sheet` |
| `interest_coverage` | EBIT / Interest Expense (latest) | `.financials` |

Each metric is peer-percentile-ranked against the real sector universe (equal-weight average across whichever are available), mirroring Banking's own formula shape exactly. A missing statement line item removes that metric from `metrics_used` and reduces `coverage_pct` — never estimated, interpolated, or substituted. Full per-metric provenance (value, source, period, retrieved_at, observation_as_of) is recorded, same contract as Banking's `financial_strength.py`.

**Dispatch, not rewrite** — every touched pillar keeps its existing branch for Banking byte-for-byte unchanged, with a new branch added alongside it:
- `financial_strength.py` — routes to the new industrial scorer for `sector in NONBANK_INDUSTRIAL_SECTORS`, Banking's own branch untouched.
- `valuation.py` — the peer-PE/PB + ROE-quality-adjustment + own-historical-PE-range formula was never Banking-specific in its own logic, only the peer population was gated; now also accepts the industrial cohort with `sector_peer_universe(sector)` as the peer group.
- `market_behaviour.py` — already sector-agnostic, but a **real, found-live bug** surfaced while extending it: the shared `_SECTOR_ETFS` dict's keys ("IT", "Pharma", "Auto", "Metal", "Infra", "Realty") don't match `_NSE_UNIVERSE`'s real sector strings ("Technology", "Pharmaceuticals", "Automotive", "Metals", "Infrastructure", "Real Estate") — meaning the sector-relative-ETF metric was silently `None` for every one of those sectors before this fix, for any caller. Fixed with a local alias map in `market_behaviour.py` only (not by renaming the shared dict, which several *other*, unrelated features also key off of).
- `current_intelligence.py` — already fully sector-agnostic (calls `compute_company_score(db, symbol)` directly); no changes needed or made.
- `engine.py` — new `elif sector in NONBANK_INDUSTRIAL_SECTORS` branch sets `methodology_version=NONBANK_INDUSTRIAL_V1` and the real sector peer universe; Banking's own branch untouched.
- `eligibility.py` — new `NONBANK_INDUSTRIAL_V1_P1` policy: ≥4 of 6 real metrics (~67%, mirroring Banking's own ~71%/5-of-7 floor), ≥65% overall coverage (kept identical to Banking's — that floor is about whole-score evidence sufficiency, not specific to the Financial Strength formula).
- `snapshot.py` — dispatches `financial_data_as_of` and eligibility evaluation per methodology; a new `_industrial_financial_data_as_of()` reads the real statement date from the industrial pillar's own provenance (there is no FinancialFact-equivalent primary-source table for non-banks).
- `rankings.py` / `company_rankings.py` — `get_banking_rankings` and a new `get_industrial_sector_rankings` now share one extracted `_get_sector_rankings(db, sector, universe, methodology_version)` function (byte-identical behavior to the original for Banking), each producing its own separate ranked list. The API router dispatches by real sector name (case-insensitive) instead of hardcoding "banking" as the only real branch. **Rankings are never blended across methodologies** — a Technology ranking only ever iterates Technology's real peer universe; a Banking-tagged snapshot cannot structurally appear in it (confirmed by test).

**UI wiring — no frontend changes needed.** The Company page (`CompanyPageClient.tsx`), its header tile, the local-preview panel, and the Compare page's score tiles are all symbol-driven, not sector-hardcoded — they already work for any methodology's snapshot once one exists. Verified live (§4).

## 3. Real computed results (local only)

`compute_marketripple_score()` run live, unmodified, for TCS (Technology) as a full end-to-end validation before persisting the pilot set:

| Pillar | Score | Coverage | Status | Notes |
|---|---|---|---|---|
| Financial Strength | 59.4 | 100% (6/6) | COMPLETE | ROE 45.9%, ROCE 54.9%, D/E 0.105, revenue growth 4.6%, profit growth 1.4%, interest coverage 54.4× — all real, all plausible for a real, low-debt IT services company |
| Valuation | 74.4 | 100% | COMPLETE | Peer PE/PB + ROE quality adjustment + own 4-year historical PE range |
| Market Behaviour | 31.6 | 100% (4/4) | COMPLETE | Confirms the `_SECTOR_ETFS` fix — `relative_return_vs_sector_etf (ITBEES.NS)` populated |
| Current Intelligence | 50.6 | — | PARTIAL (by design, never COMPLETE) | Real `ai_company_score`, unchanged |
| **Overall** | **56.0 (Neutral)** | 4/4 pillars complete | `methodology_version=NONBANK_INDUSTRIAL_V1`, peer_count=33 | |

**Banking regression check:** re-ran `compute_marketripple_score(db, "ICICIBANK")` live after all changes — Financial Strength score is **40.9, identical to the pre-change baseline**. The overall blended score moved (41.4 → 43.7) purely from valuation/market_behaviour's own live market inputs (real price/PE movement in the ~30 minutes between runs), not from any code change — Banking's own branch in every touched file is untouched.

**Real pilot snapshots persisted** (`scripts/s9_industrial_pilot_snapshot_compute.py`, one company per measured sector): TCS (Technology), HINDUNILVR (FMCG), MARUTI (Automotive), SUNPHARMA (Pharmaceuticals), PIDILITIND (Chemicals), TITAN (Consumer), TATASTEEL (Metals). Results in §5.

## 4. UI verification (real browser, no frontend code changes)

Restarted the local backend to load all engine changes, then verified TCS live in a real headless-Chromium session against all three existing surfaces — none of which needed any frontend change, since they were already symbol-driven, not sector-hardcoded:

- **Company page, Overview tab (Local Unpublished Preview panel):** real 56/100, Neutral, all 4 pillars with correct effective weights (40/20/15/25%), "Financial metrics 6/6," "Evidence coverage 100%," real statement date.
- **Company page, header tile:** "56/100 · NEUTRAL · LOCAL PREVIEW," matching the Overview panel exactly.
- **All Companies listing, Score column:** "56 · PREVIEW" next to TCS's ticker, sector correctly shown as "Technology."
- **Company Rankings API** (`GET /api/company-rankings/Technology`): `methodology_version=NONBANK_INDUSTRIAL_V1`, `total_universe=33` (the real live Technology sector count), every other real Technology company honestly listed as `unavailable — no_snapshot_computed_yet`, and TCS itself correctly in `unavailable — publication_locked` (never in `ranked`) — exactly mirroring Banking's own real, current behavior under the same S2 phase lock.

## 5. Pilot snapshot results (real, local, `scripts/s9_industrial_pilot_snapshot_compute.py`)

One company per measured sector, real `compute_and_persist_snapshot()` output:

| Sector | Symbol | Score | Rating | Financial Strength | Valuation | Market Behaviour | Current Intelligence | Metrics | Eligible |
|---|---|---|---|---|---|---|---|---|---|
| Technology | TCS | 56.0 | Neutral | 59.4 | 74.4 | 31.6 | 50.6 | 6/6 | Yes |
| FMCG | HINDUNILVR | 53.9 | Neutral | 66.9 | 54.7 | 26.0 | 49.2 | 6/6 | Yes |
| Automotive | MARUTI | 54.0 | Neutral | 61.7 | 72.7 | 10.2 | 53.1 | 6/6 | Yes |
| Pharmaceuticals | SUNPHARMA | 52.1 | Neutral | 53.3 | 50.1 | 51.4 | 52.0 | 6/6 | Yes |
| Chemicals | PIDILITIND | **None** | — | 78.9 | 28.2 | 50.6 | **None** | 6/6 | Yes (but 3/4 pillars — see below) |
| Consumer | TITAN | **None** | — | 65.7 | 25.2 | 86.7 | **None** | 6/6 | Yes (but 3/4 pillars — see below) |
| Metals | TATASTEEL | 43.2 | Cautious | 29.4 | 59.1 | 47.1 | 50.3 | 6/6 | Yes |

**PIDILITIND and TITAN both show `score=None` because `current_intelligence=None`** (Current Intelligence found no real contributing evidence for either company at the time of this run) — only 3 of 4 pillars usable, correctly triggering the Comparability interim rule (headline score withheld, per-pillar scores still shown) exactly as Banking's own rule already does. This is the rule working correctly on real data, not a defect — two of seven real pilot companies genuinely don't have enough current evidence today for a combined number.

All 7 show **6/6 Financial Strength metrics** and **0 publication_block_reasons** (eligible under `NONBANK_INDUSTRIAL_V1_P1`) — a strong real signal that the metric set is reliably computable across the measured cohort, not just for the one company (TCS) used for initial validation.

**Banking regression, confirmed on real data:** re-ran `compute_marketripple_score(db, "ICICIBANK")` live after all changes — Financial Strength score is **40.9, byte-identical to the pre-change baseline**. The overall blended score moved (41.4 → 43.7) purely from valuation/market_behaviour's own live market inputs moving in the ~30 minutes between runs — not a code regression. `peer_universe_count` stayed the real 27.

## 6. Tests

New: `tests/services/test_financial_strength_industrial.py` (6 tests, mocked yfinance — valid full-data score, missing-statement-line reduces coverage without fabrication, single-period data can't compute growth, currency-invariant growth math, zero/negative-equity guard against divide-by-zero) and `tests/services/test_marketripple_score_industrial_rankings.py` (5 tests — real live sector universes non-empty, industrial ranking categorization mirrors Banking's, a Banking snapshot never appears in an industrial ranking, two industrial sectors ranked completely separately). Fixed one now-stale assertion in the existing `test_marketripple_score_rankings.py` (its "unsupported sector" example was "Technology," which NS1 just made real and supported — swapped for "Insurance," a real, still-excluded sector).

**Results:**
- `tests/ -k marketripple`: 41/41 passed (pre-existing suite, confirming no regression).
- New industrial tests + existing rankings tests together: 20/20 passed.
- Full backend suite (`tests/`): **2161 passed, 28 failed, 2 skipped, 2 xfailed**. All 28 failures are in files unrelated to this work (`test_macro_rates.py`, `test_quant_leakage.py`, `test_quant_membership.py`, `test_p5_stage*_v3_live.py`, `test_economic_calendar_api.py`, `test_ingest_news_shared_fetch.py`, `test_opportunity_v2_batch_e_consumers.py`, `test_weekend_intelligence_scheduler.py`) — confirmed via grep that none of them import any module touched in this pass; their own naming ("_live") and content point to pre-existing live-network/timing dependencies, not something this change introduced.

## 7. Remaining steps to publish

None of the following were done in this pass, per the explicit "keep production publication locked" instruction:
- `publishable` stays hardcoded False in `engine.py` for every methodology — flipping it (Banking or industrial) is a separate, later, explicitly-authorized decision, unrelated to this implementation.
- The public methodology page (`/methodology/marketripple-score`) still describes Banking V1 as "the first live methodology" and states other sectors have no approved methodology yet — intentionally NOT edited in this pass, since updating public-facing copy about a not-yet-approved-for-publication methodology would itself be a form of premature disclosure.
- A real, wider backfill (all ~214 companies across the 7 sectors, not just 7 pilot companies) needs its own bounded batch script and runtime budget, matching Banking's own `s5_backfill_snapshots.py`/`marketripple_score_production_backfill.py` precedent — not attempted here per the explicit "small set" scope.
- The 5 sectors not yet measured (Infrastructure, Power, Energy, Real Estate, Telecom, Media, Cement, Healthcare, Textiles, Electronics, Retail, Defence) need their own real data-inventory pass before any claim about whether they fit this metric shape or need a bespoke one (like Finance/Insurance do).
- Finance/Insurance need their own bespoke methodology (regulatory-capital/AUM/embedded-value-based) — not designed or attempted here.
