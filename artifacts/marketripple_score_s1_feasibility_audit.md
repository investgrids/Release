# Unified MarketRipple Score — Phase S1: Data & Formula Feasibility Audit (read-only)

Date: 2026-08-25. Scope: for each proposed pillar (Financial Strength, Valuation, Market Behaviour, Current Intelligence), trace the exact existing backend producer for every required input and measure real coverage/freshness/depth against real data — Banking reference sector, using ICICIBANK, HDFCBANK, AXISBANK, KOTAKBANK, SBIN. **No scoring code written. No weights, thresholds, or missing values invented.** Every number below is a live query against real yfinance data, the real dev DB, or real production data (via read-only `railway ssh`).

## Verdict: **PARTIALLY READY**

Two pillars are genuinely production-ready today (Current Intelligence, most of Market Behaviour). Valuation is ready for a coarser version than proposed. **Financial Strength — the pillar you want weighted heaviest (40%) — is the least ready**, and the gap is specifically in the two categories that matter most for judging a bank: asset quality (NPA) and capital adequacy (CET1/CAR). Those aren't degraded or stale — they are **completely absent** from every real data source this app has access to today, confirmed by direct search, not assumed.

---

## 1. Financial Strength (Banking reference sector)

Traced every proposed metric to `yfinance` (`Ticker.info`, `.financials`, `.balance_sheet` — the only real data source this app has for company financials; confirmed via `apps/backend/app/services/market_data.py`, the same source Financials/Ratios/Capital Structure already use). Verified real, populated values (not just row-label presence) for all 5 reference banks.

| Category | Proposed metric | Status | Real evidence |
|---|---|---|---|
| Asset quality | Net NPA, Gross NPA | **BLOCKED** | Not in `yfinance.info` (checked all keys). Not in `.financials`/`.balance_sheet` row labels. Not in any raw_evidence text (see §5 — even the raw NSE filing text doesn't carry it; the numbers live inside unparsed PDF attachments) |
| Asset quality | Provision coverage | **BLOCKED** | Same — no source anywhere |
| Capital | CET1, CAR | **BLOCKED** | Same — no source anywhere |
| Profitability | ROE | **READY (4/5)** | Real: ICICIBANK 16.1%, HDFCBANK 13.8%, AXISBANK 13.4%, SBIN 15.2%. **Null for KOTAKBANK** — confirmed live, not a bug, yfinance simply doesn't populate it for this symbol |
| Profitability | ROA | **READY (4/5)** | Same pattern: real for 4/5, null for KOTAKBANK |
| Profitability | NIM | **PROXY ONLY** | Real `Net Interest Income`/`Interest Income`/`Interest Expense` line items exist and are populated (confirmed: ICICIBANK NII = ₹1,06,190 Cr TTM) — but real NIM is NII ÷ *average interest-earning assets*, and "earning assets" isn't a labeled row; only `Total Assets` is. A `NII / Total Assets` proxy is computable and real, but it is not the number banks actually report as NIM |
| Funding | CASA | **BLOCKED** | No deposits breakdown anywhere in `.balance_sheet` — no "Deposits" row at all for a bank symbol |
| Funding | Deposit growth | **BLOCKED** | Same — no Deposits row to compute growth from |
| Growth | Advances (loan book) | **BLOCKED** | No "Advances"/"Loans" row; closest is `Investments And Advances`, a different, combined figure, not loan book |
| Growth | NII growth | **READY** | Real, computable YoY from the real NII line item above |
| Growth | Profit growth | **READY** | Real, already computed elsewhere on this page (annual_financials YoY) |

**Net: of 12 proposed banking-specific metrics, 4 are genuinely ready (ROE, ROA, NII growth, Profit growth), 1 is a real-but-imprecise proxy (NIM), and 7 — including both asset quality metrics and both capital metrics — are completely blocked.** This is the real headline finding: the two categories a credit analyst would check *first* for a bank are the two categories this app cannot measure at all today.

## 2. Valuation

| Component | Status | Real evidence |
|---|---|---|
| Current P/E, P/B, forward P/E | **READY** | Real, live, complete for 4/5 (KOTAKBANK's `trailingPE`/`priceToBook` present; only ROE/ROA null there). ICICIBANK PE 18.4/PB 2.68, HDFCBANK PE 15.9/PB 1.85, AXISBANK PE 13.9/PB 1.72, KOTAKBANK PE 19.6/PB 2.20, SBIN PE 11.2/PB 1.56 |
| Peer percentile | **READY** | The real `_PEER_GROUPS["banks"]` list already built for Peer Comparison (2026-08-25 fix) is exactly these 5 symbols. A live percentile rank across real peer P/E, P/B, ROE is directly computable today with no new infrastructure — same yfinance calls already made |
| Own historical valuation range | **PARTIALLY READY** | Real quarterly EPS depth is only 6 real periods (~1.5 years, 1 real gap: Sep-2025 quarter is null for ICICIBANK, matching the earlier Financials-tab audit finding); real annual EPS is 5 periods (~4-5 usable years). Combined with real 5-year daily/weekly price history (confirmed available), a **coarse annual P/E range** (4-5 data points) is computable now. A smooth rolling/quarterly percentile is not — the underlying EPS series isn't dense enough |
| Quality/growth context | **READY (partial)** | Real ROE/growth data (§1) can weight the peer-percentile comparison so a higher-quality bank isn't penalized for a higher P/B — the inputs exist; this is a formula design question, not a data gap |

## 3. Market Behaviour

| Component | Status | Real evidence |
|---|---|---|
| 200-DMA position | **READY, needs new code** | Live-tested: `yf.download(symbol, period="1y", interval="1d")` returns 251 real daily rows for ICICIBANK — enough for a genuine 200-day average. The **existing** `/chart` endpoint (`get_stock_chart`) only fetches weekly resolution beyond 1 month (`_PERIOD_MAP`), so this needs its own daily fetch, not a reuse of the existing chart data — a real but small new-code item, not a data gap |
| Medium-term relative performance | **READY** | Same real daily series supports 1M/3M/6M relative return vs. NIFTY 50 |
| Sector-relative performance | **READY** | Real `_SECTOR_ETFS["Banking"] = "BANKBEES.NS"` already exists (built for the Warehouse sector-metrics work, confirmed capturing "fresh" as of the 2026-08-25 sector-ETF fix) — a real, liquid benchmark, not something to build from scratch |
| RSI | **READY** | Pure derived calculation from the same real daily price series — no new data source, just new code |

**Important caveat found**: real production `price_bars` (the Warehouse table) only holds **8 rows per symbol** for all 5 reference banks — confirmed live via read-only production query. This table is **not** what should feed Market Behaviour. The existing Price Chart already doesn't use it either (`get_stock_chart` calls `yf.download()` live) — Market Behaviour should follow the same live-fetch pattern, not `price_bars`, which is real but far too thin for this purpose today.

## 4. Current Intelligence — reconstructed using `contributing_signal_count`

This is the pillar that survives from the work already done today. Real, live numbers for all 5 reference banks, using the just-shipped cleaned semantics:

| Symbol | Score (0-100) | signal_count | contributing_signal_count | risk_level | trend |
|---|---|---|---|---|---|
| ICICIBANK | 56.9 | 103 | 63 | Medium | up |
| HDFCBANK | 55.4 | 155 | 96 | Medium | up |
| AXISBANK | 53.6 | 27 | 14 | Medium | neutral |
| KOTAKBANK | 56.0 | 29 | 17 | Medium | up |
| SBIN | 55.0 | 85 | 49 | Medium | up |

**READY** — this is literally already in production-shape (`compute_company_score()`, shipped this session, tested, guarded against the name/symbol and semantic-integrity issues found earlier today). Real coverage variance is honest and worth carrying forward as a visible signal, not smoothed over: AXISBANK/KOTAKBANK have meaningfully thinner evidence (14-17 contributing signals) than ICICIBANK/HDFCBANK (63-96) — a real difference in how much the platform has published about each company, not a scoring artifact.

## 5. What Warehouse would need to supply (your question 7)

Checked directly rather than assumed: does the Intelligence Warehouse's already-captured raw NSE filing text contain any of the blocked banking metrics, even unstructured? **No** — a precise, word-boundary search across all real NSE `raw_evidence` rows for "NPA"/"CASA" returns **zero** matches (an earlier looser substring search returned 15 false positives, all from "CRAR" matching inside the unrelated word "ICRARating" — corrected before reporting). Separately, NSE's raw filing capture only stores the announcement's short text and a link to the underlying PDF (`attchmntFile`) — it does not fetch or parse PDF content at all. So even a genuine quarterly-results filing that *does* disclose NPA/CET1/CASA numbers has that data locked inside an unparsed PDF, not in anything Warehouse currently ingests.

**Real implication**: closing the Financial Strength gap isn't "wire in an existing Warehouse table" — it requires either (a) a new PDF-parsing capability for NSE quarterly result filings (a real, nontrivial new engineering initiative, not a data-source connection), or (b) a paid/third-party financial data API that already structures Indian bank regulatory disclosures (e.g., the kind Screener.in or a Bloomberg-class provider carries) — a sourcing/budget decision, not something this audit can resolve.

## 6. Candidate normalization methods (not implemented, just what's feasible)

- **Available now**: peer-percentile rank (Valuation), z-score or min-max against the 5-bank reference set (Financial Strength's ready subset: ROE/ROA/growth), simple threshold bands reused from the existing `metricColor`/`ratioFieldColor` conventions already shipped this session.
- **Needs the coarse-data caveat carried through**: any "own historical range" percentile should visibly flag it's built from ~5 annual points, not a dense series, until deeper history exists.
- **Not proposed**: anything that fills a blocked metric (NPA/CET1/CASA) with an estimate, an industry average, or a neutral default — per your own instruction, missing structural data should show as missing, not as 50.

## 7. Proposed missing-data / publication policy (a proposal to review, not implemented)

Mirroring your own sketch:
```
Financial Strength = computed from {ROE, ROA, NIM-proxy, NII growth, Profit growth} only
Financial Strength coverage = 5/12 proposed metrics real = ~42% — this coverage number itself should be shown
```
A real minimum-publication threshold is a judgment call this audit can't make for you (what coverage % is "enough" is a product decision, not a data fact) — but the *coverage number itself* is real and computable today, and I'd surface it rather than silently score off a thinner metric set than the pillar's name implies.

## 8. What's production-ready now vs. blocked

**Ready to build on today, no new data sourcing required:**
- Current Intelligence (fully ready — already shipped)
- Valuation: current P/E, P/B, peer percentile (fully ready); own historical range (ready at reduced/annual resolution only)
- Market Behaviour: all 4 proposed inputs (real data exists; needs new fetch code, not new data)
- Financial Strength: ROE, ROA, NII growth, Profit growth, NIM-as-proxy (ready but partial — 4-5 of 12 proposed metrics)

**Blocked, depends on new sourcing work (§5), not something S2 implementation can work around:**
- Financial Strength: Net NPA, Gross NPA, Provision coverage, CET1, CAR, CASA, Deposit growth, Advances — 7 of 12 proposed metrics, including the two categories (asset quality, capital adequacy) most central to judging a bank

## 9. Proposed S2 implementation architecture (sketch only, not built)

A common scoring interface with one `PillarScore` shape (`raw_value`, `normalized_0_100`, `coverage_pct`, `data_sources: []`) per pillar, sector-dispatched only for Financial Strength (Banking as the reference implementation, `_sector_for()` already exists to route it). Current Intelligence, Valuation, and Market Behaviour are sector-agnostic and can be built once. The final `MarketRippleScore` composes the 4 pillar scores with the candidate weights you proposed (40/20/15/25) — explicitly flagged as candidate, not validated, since this audit didn't test whether those weights produce sensible scores against real companies; that's real S2 work (build it, then run it against ICICIBANK/HDFCBANK/AXISBANK/KOTAKBANK/SBIN and sanity-check the outputs before trusting the weights).

---

## READY / PARTIALLY READY / BLOCKED — final verdict

**PARTIALLY READY.**

- Current Intelligence: **READY**
- Market Behaviour: **READY** (real data confirmed; needs new fetch code)
- Valuation: **READY** for current-value + peer-percentile; **PARTIALLY READY** for historical range (annual-only resolution)
- Financial Strength (Banking): **PARTIALLY READY** — 4-5 of 12 proposed metrics real, but the two most decision-relevant categories (asset quality, capital adequacy) are fully blocked and require new sourcing work, not new code, to close

Building S2 today would produce a real, honest, defensible score for 3 of 4 pillars, and a Financial Strength pillar that's genuinely useful (ROE/ROA/growth are real signals) but narrower than its name promises unless the coverage percentage is shown alongside it, exactly as you proposed. The recommendation is to proceed to S2 with that coverage-transparency built in from day one, rather than wait for NPA/CET1/CASA sourcing to be resolved first — those are a separate, larger initiative whose timeline shouldn't block shipping the 3 ready pillars plus an honestly-labeled fourth.
