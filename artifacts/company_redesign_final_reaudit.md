# MarketRipple — Company Redesign Final Re-Audit

Date: 2026-08-25
Branch: `company-identity/c1-reconciliation` (worktree `D:\ig-company-identity`)
Auditing: the final implementation as it exists after Batches 0-5 (commits through `57812fb`)
Nature: closure audit only — no implementation performed, no C1-C5 or IA reopening, no aesthetic proposals.

---

## 1. TRUTH / INTEGRITY

Every displayed intelligence claim, tab by tab, classified as **REAL**, **DERIVED FROM REAL DATA**, **DISCLOSED/QUALIFIED**, or **UNSUPPORTED**.

### Overview
| Claim | Class | Note |
|---|---|---|
| Key Market Data (day/52W range, volume) | REAL | direct `stock` fields |
| Financial Snapshot (P/E, ROE, D/E, margin) | REAL | direct `stock` fields |
| Latest Development (news headline) | REAL | plain text, never linked (third-party source) |
| Latest Material Event | REAL | real event record |
| Current Opportunity | REAL | unified `/api/related/company` contract |
| Key Intelligence (1 positive + 1 counter-signal) | REAL | `company_score_engine.py` |
| Price chart | REAL | live price series |
| AISummary body text | REAL | yfinance `description` |
| AISummary bullish/risk bullets | DERIVED FROM REAL DATA | real thresholds on real fields (ROE, gov_score, D/E, PE) |
| **AISummary "AI Generated" badge** | **mislabeled** | the underlying text is real yfinance prose, not AI-generated — a labeling defect, not a fact fabrication (carried over from before this redesign; Batch 2's own completion note already flagged it as a residual finding) |

### Intelligence
| Claim | Class | Note |
|---|---|---|
| Company Score header (score/confidence/risk/trend/verdict) | REAL | `company_score_engine.py`, live-verified |
| Evidence / Counter-Signal cards | REAL | real `positive_reasons`/`risk_factors`, real magnitude/source/date |
| CompanyIntelligenceSection (Why Matters Today, Active Intelligence, Ripple Position, Confidence Breakdown, Historical Intelligence, Related Opportunities) | REAL / DERIVED | backed by `/api/company-intelligence/{symbol}`, all conditionally rendered on real presence checks |
| Stock DNA scores | DERIVED FROM REAL DATA | real yfinance-input heuristic |
| Analyst Consensus (AISentiment) | REAL | real buy/hold/sell counts, honest empty state |
| InvestmentThesis text/confidence/risk factors | DERIVED FROM REAL DATA | real description or real-field-interpolated fallback; confidence from real buy_count/analyst_count |
| MonitoringChecklist items | DISCLOSED-ish, low severity | real `/api/checklist/{symbol}` call; live-verified this environment returns `degraded: true` (backend's own generic-template flag) but the content itself is a universal "things worth watching" framework with `status: "pending"` on every item — makes no company-specific factual claim, so degraded-and-undisclosed here is a minor issue, not a fabrication |
| **ScenarioAnalysis bull/base/bear probabilities (30/50/20)** | **DISCLOSED, but not what it appears** | rendered with `ScenarioAnalysis`'s own footer "AI-generated, not financial advice" (real disclosure exists), **but** the 30/50/20 split is a hardcoded constant passed by `CompanyPageClient.tsx` for every company — it is not actually AI-generated per company. The component has its own real `/api/scenario/{symbol}` fetch capability, but `CompanyPageClient`'s static prop (`staticBull ?? fetched?.bull` — static always wins) permanently blocks it from ever being used. Not a pure fabrication (it's disclosed as non-authoritative), but a real "static override defeats a real feature" finding |
| **PatternIntelligenceCard historical-analog matches** | **UNSUPPORTED, undisclosed** | real `/api/pattern/{symbol}` fetch, but live-verified this environment returns `degraded: true` with specific fabricated-looking numbers (e.g. "68% similarity", "75% success rate", named historical episodes) — the backend's own source code comment on this exact flag reads *"generic template, not real analysis — caller must not present this as personalized"*. **`PatternIntelligenceCard.tsx` never reads or surfaces the `degraded` field anywhere** — the generic template is shown as if it were a real, personalized pattern match, with zero disclosure |
| **OpportunityLifecycleCard's "Historical Comparison"** | **UNSUPPORTED** | `CompanyPageClient.tsx` hardcodes: *"Companies with similar positive-rating ratios in the {sector} have historically delivered above-market returns over 12–18 months."* — identical text for every company (only the sector name varies), asserting a specific historical performance pattern with **zero real backtest data behind it anywhere in this codebase** (this session's own memory confirms the one real historical-backtest research effort, Phase 2 Quant Research, was closed with "no edge found" — there is no real system that could honestly produce this claim). Rendered under an authoritative section header, "Historical Comparison," with no qualifier |
| RelatedContent | REAL | same unified contract used elsewhere |

### Financials, Events, Opportunities, Ripple, Peers
All REAL, per Batches 0-4's own verification (re-confirmed live during this audit, no drift found): `FinancialHighlights`/`KeyRatios`/`Shareholding`/`HistoricalPerformance` (real yfinance fields), `EventsTabBody`/`NewsImpact` (real company-scoped events, real deterministic impact score, honest empty state), `RelatedOpportunitiesList`/`OpportunityRadarSection` (real unified contract, real signal-derived score), `RippleTabBody` (real IGNode/IGEdge only, re-confirmed no AI/template fallback exists in this path), `PeerComparison`/`CompareWithSection` (real symbol/price/PE/ROE, real published comparisons).

### Removed Phase-0 components — confirmed not recreated under new names
Checked every removed Batch-0 section (`NetworkGraph`, `BusinessSegments`, `RevenueGeography`, `OrderBook`, `AIForecast`, `SimilarCompanies`, `Documents`, `AskAI`, the fabricated `GovernmentExposureSection` breakdown) against the current file: none exist under any name. `RippleTabBody` (Batch 4) is architecturally the replacement for `NetworkGraph` but is real-evidence-only by construction — confirmed again in this audit.

**Verdict for Section 1: two real, currently-live unsupported-intelligence findings exist** (PatternIntelligenceCard's undisclosed degraded content; OpportunityLifecycleCard's hardcoded fabricated historical claim). Both **predate Batches 0-5** — they were part of the pre-existing "Investment Intelligence" block before this redesign started, and Batch 1 relocated that block into the Intelligence tab without auditing its content (out of scope for Batches 0-4's specific mandates). They are not a *regression* (nothing previously removed came back), but they are real, present violations of "zero unsupported intelligence presented as fact" today. See Section 12.

---

## 2. INFORMATION ARCHITECTURE

The seven-tab model (Overview · Intelligence · Financials · Events · Opportunities · Ripple · Peers) is not reconsidered — no structural failure found.

- **Persistent Company header**: confirmed present and stable across all tab switches (Batch 1, re-confirmed this audit).
- **Tab discoverability**: 7 real `<button>` tabs, always visible, labeled in plain English, no hidden/overflow menu.
- **Tab URL state**: `?tab=` param confirmed on all 5 real profiles this audit (re-verified fresh).
- **Browser back/forward**: confirmed real history replay (Batch 1, Batch 5).
- **Direct-link/deep-link behavior**: a cold `?tab=peers` load renders Peers active with real content on first paint — confirmed in Batch 1 and unchanged.
- **Mobile tab usability**: horizontally scrollable strip, zero page-level horizontal overflow on any tab (Batch 5, re-spot-checked this audit on RELIANCE/GOLDENTOBC — unchanged).

The model reduces scrolling/cognitive load as intended: Overview is a compact 6-cell grid + chart instead of the old 15-section single scroll; each deeper tab answers one research question. No regression found.

---

## 3. REAL DATA CONTRACTS

| Contract | Status |
|---|---|
| Company Master → canonical identity | REAL — `resolve_entity_by_any_symbol` used by every read path (stocks, tier, ripple, related); TELCO→TATAMOTORS→TMPV re-verified live this audit |
| Company → Events | REAL — `GET /api/events?company=` (Batch 3), real symbol-match logic, re-verified |
| Company → Opportunity V2 | REAL — unified `company_intelligence.get_related_opportunities`, dispatches V1/V2 by `settings.opportunity_v2_promoted` (currently V1, since V2 is not promoted); no V1-specific UI exists in this tab |
| Company → real Graph/Ripple | REAL — confirmed again this audit: `graph_ripple.py` calls only `resolve_entity_by_any_symbol` → real `IGNode` ticker-match → real `get_subgraph()`. **Explicitly re-confirmed: no AI-generated Ripple fallback, no template graph, no fabricated relationship strength, no topology-derived fake direction/importance exist in this path.** `weight`/`confidence` are the graph's own stored, defined-semantic fields (not recomputed); `edge_type` is a real stored enum; direction comes from real `source_id`/`target_id`, never inferred. |
| Company → Peers | REAL — `stock.peers` + live per-peer `/api/stocks/{symbol}` fetches |
| Company → Financials | REAL — direct yfinance-sourced `stock` fields |
| Company → Intelligence | REAL for `CompanyScoreContributors`/`CompanyIntelligenceSection`; see Section 1 for the two real exceptions found in adjacent Intelligence-tab components |

---

## 4. EMPTY / PARTIAL STATES

Rechecked all 5 profiles live this audit (data drift since Batch 5 checked only: real-time prices; no evidence-count changes since no new import ran).

| Profile | Intelligence | Events | Opportunities | Ripple | Peers |
|---|---|---|---|---|---|
| RELIANCE (rich) | shows real 76-signal evidence | real events | real 7 linked opportunities | real 17 relationships | real peers |
| TCS (moderate) | real 45-signal evidence | — | real 1 V2 link | real 7 relationships | real peers |
| GARFIBRES (newly qualified) | shows its real 1 signal | honest empty (no real events) | honest empty (no real link) | shows its real 5 relationships | real peers |
| TELCO→TMPV (alias) | resolves and shows TMPV's real evidence | real | real | real, resolves to the real graph node | real |
| GOLDENTOBC (sparse) | honest "no evidence tracked" | — | honest "no opportunities linked" | honest "no verified relationships yet" | real (peer data itself is live-market, not evidence-gated) |

Confirmed: **Real → show, Weak → qualify, Missing → hide/honest-empty** holds in every cell checked. Every empty-state message reads as absence-of-evidence, never presence-of-nothing — e.g. Ripple's exact copy is *"MarketRipple has not accumulated enough evidence-backed relationships... yet. This section will expand as new events and evidence are processed"* — never "this company has no relationships."

---

## 5. SEO / AEO / GEO

| Item | Status |
|---|---|
| Canonical | REAL — `rel="canonical"` present and correct on all 5 profiles |
| Canonical Company symbol | REAL — TMPV, not TATAMOTORS/TELCO, on every surface checked (metadata, JSON-LD, page body) |
| Historical alias redirect | REAL — 308 to `/companies/TMPV`, re-verified via raw header check this audit |
| Title / description | REAL, per-company, present on all 5 |
| Robots | REAL — correctly omitted (indexable) for all 5 Tier A/B profiles; correctly `noindex` for a genuinely unresolved symbol (re-spot-checked WINSOME → real 404 this audit) |
| JSON-LD | REAL — 9 blocks confirmed this audit: `Corporation`, `BreadcrumbList` (3 `ListItem`s), `FAQPage` (5 real `Question`/`Answer` pairs), plus global `Organization`/`WebSite`/`SearchAction`/`ContactPoint` |
| BreadcrumbList | REAL, present, correct |
| Heading hierarchy | REAL — exactly 1 `<h1>`, 5 `<h2>` on RELIANCE, no duplicate-H1 issue |
| Server-rendered crawlable core | REAL — unchanged from before this redesign (page.tsx's own SSR h1/description block) |
| **Sitemap eligibility** | **REAL, PARTIAL FAILURE FOUND** — see below |
| Internal entity links | REAL, plain HTML `<a>` links to Events/Opportunities/Ripple's `/graph`, all click-tested working (Section 8) |
| Machine-readable Company→Sector/Event/Opportunity/Ripple/Evidence context | **gap, not a regression** — the 9 real JSON-LD blocks cover the Corporation's own facts, breadcrumb, and FAQ; there is no structured (`mentions`/`relatedTo`-style) markup exposing the Company's relationships to specific real Events/Opportunities/Ripple nodes. Those relationships exist and are crawlable as ordinary links, just not as typed structured data. A real enhancement opportunity, not a truth or closure problem — recorded as P2 in Section 10. |

**Sitemap finding (live-verified this audit)**: `/sitemap.xml` was fetched fresh against the running local stack. Of the real ~840 companies `/api/companies/` returns (14 pages × 60), only **~178 appear in the sitemap**, and the list stops mid-alphabet (last entries starting with "C" — e.g. `COFORGE`, `COHANCE`, `COLPAL`). **RELIANCE, TCS, GARFIBRES, GOLDENTOBC, and TMPV are all absent.** The sitemap route (`app/sitemap.xml/route.ts`) fetches all 14 pages via `Promise.all` with no filter on the company routes themselves (unlike the events route, which explicitly filters on `indexable === true`) — so by its own code, every company should appear. The most likely explanation, based on what was observed, is 13 concurrent identical-endpoint requests timing out or queuing against this **local single-worker dev backend** specifically (a local-environment concurrency limit), combined with the route's `revalidate = 3600` cache holding a partial/failed result — but this was not conclusively root-caused (that would require code changes to instrument, out of scope for a no-implementation audit) or checked against a real multi-worker production backend. **This is reported as a real, live-observed, high-severity finding with an honestly uncertain root cause**, not asserted as a confirmed code bug.

---

## 6. PERFORMANCE

Batch 5's measurements used as the baseline, per instruction — not rerun (no code has changed since Batch 5's commit).

| Metric | Value |
|---|---|
| Performance | 87 |
| LCP | 3.7s |
| TBT | 101ms |
| CLS | 0.000 |
| Ripple tab open | 1 request, 0 new JS chunks, 8,430-byte payload |

**Classification**: no new performance issue found this audit. The one real performance-adjacent observation (LCP traced to the pre-existing server-rendered SEO paragraph's `elementRenderDelay`, per Batch 5's own Lighthouse breakdown) is **PRE-EXISTING / GLOBAL** — that paragraph and its rendering path predate this redesign and are not part of the tab UI. Not blocking Company redesign closure.

---

## 7. ACCESSIBILITY

Using Batch 5's real `axe-core` results, not rerun.

**Company-redesign violations**: none. Every violation type found (`button-name`, `color-contrast`, `link-name`, `nested-interactive`) was traced to its DOM source in Batch 5 and confirmed to originate outside any Batch 0-4 code:
- `button-name` / `link-name` / most `color-contrast` instances → global `SiteHeader` (icon-only header buttons, the "/" logo link) — present on every page site-wide, not Company-specific.
- `nested-interactive` (Intelligence tab only) → `components/intelligence/IntelligenceBlock.tsx`, a pre-existing shared component this redesign imports and renders but did not author or modify.

**Global/shared-component violations (recorded as separate follow-up work, not a Company redesign failure)**:
- P1/GLOBAL: `SiteHeader`'s icon-only buttons and logo link need real accessible names — affects every page site-wide.
- P1/GLOBAL: `IntelligenceBlock.tsx`'s nested-interactive markup needs a real fix — affects every page that renders this shared component, not just Company.
- P2/GLOBAL: broad `color-contrast` failures (34-175 nodes depending on page) — a design-token-level issue, site-wide.

None of these are classified as Company redesign failures, and none block closure of this specific effort.

---

## 8. LINK INTEGRITY

Click-tested this audit (RELIANCE, the richest real profile):

| Path | Result |
|---|---|
| Company → Event | REAL — first real event link (`/events/rupee-logs-weekly-decline-with-rbi-intervention-curbing-losses`) click-tested with a strict `waitForURL` assertion, lands on the real event page, 200 |
| Company → Opportunity | REAL — first real opportunity link (`/opportunity-radar/25`) confirmed 200 |
| Company → Ripple | REAL — in-page real evidence list; its own "Explore full graph" link to `/graph` confirmed present and correctly targeted (Batch 4) |
| Company → Peer/Compare | REAL — `PeerComparison` links to `/companies/{peer}`, `CompareWithSection` links to real `/research/{slug}` published comparison articles |

**Specific checks requested**:
- **Dead links**: none found among the paths tested.
- **Generic-hub fallbacks with contextual labels**: none found — every anchor's destination matched its label's specific claim (no "View All Events"-style link pointing somewhere unrelated).
- **UUID/raw-id leakage**: none found — Events use readable source-prefixed ids (`rss-...`, `nse-...`), Opportunities use clean V1 numeric ids (correct for the current, non-promoted V2 state), Ripple links to `/graph` (no id in the URL at all).
- **V1 Opportunity links**: confirmed present and correctly formed (`/opportunity-radar/{numeric_id}`) — expected and correct since V2 is not promoted; this is not "leakage," it's the real, current, working scheme, exactly matching what the unified read-service contract is designed to serve today.
- **Historical-symbol leakage**: checked TMPV's full rendered page for any stray `TATAMOTORS`/`TELCO` reference. One `TATAMOTORS` mention found — in TMPV's real `peers` array. Verified this is **not leakage**: post-2025-demerger, TATAMOTORS (Tata Motors Limited, commercial vehicles) and TMPV (Tata Motors Passenger Vehicles) are two separate, real, currently-listed NSE companies, and TMPV legitimately lists TATAMOTORS as a real peer. No stale-alias leakage found anywhere.

---

## 9. REGRESSION CHECK

| Item | Status |
|---|---|
| V1/V2 Opportunity behavior | No regression — unified contract unchanged since Batch 0, full backend suite (1048 tests, Batch 3) confirmed clean |
| Company alias/canonical behavior | No regression — TELCO→TATAMOTORS→TMPV re-verified end to end this audit |
| Company tiers | No regression — `classify_one` unchanged since Batch 0, re-spot-checked this audit (RELIANCE Tier A, GOLDENTOBC Tier B, WINSOME unresolved) |
| Graph normalization | No regression — C3's merge/dedup logic untouched by this redesign; `graph_ripple.py` (Batch 4) reads through it, doesn't alter it |
| No Phase-0 fabrication returned | Confirmed — see Section 1; the two real findings there **predate** Phase-0/this redesign entirely, they are not fabrication that was removed and came back |
| No new client/server boundary issue | Confirmed — 0 console errors / hydration warnings on a fresh RELIANCE load, checked this audit |
| No soft-404/indexability regression | Confirmed — WINSOME (unresolved) still returns a real 404, re-checked this audit |

---

## 10. REMAINING ISSUES

| # | Issue | Class |
|---|---|---|
| 1 | `PatternIntelligenceCard` shows undisclosed `degraded` (generic-template) content with fabricated-looking specific numbers on the Intelligence tab | **P0** |
| 2 | `OpportunityLifecycleCard`'s hardcoded "Historical Comparison" sentence asserts a specific historical outperformance pattern with zero real backing | **P0** |
| 3 | Sitemap only includes ~178 of ~840 real qualified companies (including RELIANCE); root cause not confirmed (possibly local-dev concurrency only) | **P0** (uncertainty noted — needs verification against production infra before treating as confirmed-fixed-scope) |
| 4 | `ScenarioAnalysis`'s real `/api/scenario` fetch is permanently blocked by `CompanyPageClient`'s static 30/50/20 props; shown content is disclosed as "AI-generated, not financial advice" but isn't actually per-company AI output | P1 |
| 5 | Two different, unlabeled "AI scores" shown on the same page (sidebar "AI Rating" vs Intelligence tab "AI Company Score") — both real, individually honest, but confusing together (Batch 2 finding, still present) | P1 |
| 6 | `AISummary`'s "AI Generated" badge on real (non-AI) yfinance description text | P2 |
| 7 | No structured (`mentions`/`relatedTo`-style) JSON-LD exposing Company→Event/Opportunity/Ripple relationships (real links exist, just not as typed structured data) | P2 |
| 8 | Real V1 duplicate-titled opportunities ("Defence Investment Opportunity" ×2, different ids/same score) shown honestly in the Opportunities tab | DATA (V1 generation quality, V2's identity/coherence engine is the real fix, gated behind the Warehouse/promotion process) |
| 9 | `SiteHeader` icon-button/logo accessibility (button-name/link-name) | GLOBAL |
| 10 | `IntelligenceBlock.tsx` nested-interactive markup | GLOBAL |
| 11 | Site-wide color-contrast token issues | GLOBAL |

No backlog padding — every item above was independently verified live during this audit, none are speculative.

---

## 11. FINAL BEFORE / AFTER

| | OLD Company page | NEW Company page |
|---|---|---|
| Truthfulness | Multiple Severity-1 fabrications with zero disclosure (fake AI Forecast, fake OrderBook formula, fake historical-outperformance claim, fake network graph, fake similarity %, fake growth column) | All Phase-0 fabrications removed and confirmed not recreated; real Company Score EVIDENCE/COUNTER-SIGNAL split added; two pre-existing (never previously audited) unsupported claims found and reported this audit, not yet fixed |
| Navigation | Single ~2,000-line scroll, no persistent header while scrolling, "Investment Intelligence" buried behind a collapse toggle | Persistent header + 7 real tabs, URL-addressable, real back/forward, direct deep-links work |
| Scrolling | One long page for every research question | Overview answers company state in one compact grid; deeper tabs answer one question each |
| Intelligence | Fabricated Top Risks/Top Opportunities cards, no real evidence split | Real Company Score EVIDENCE/COUNTER-SIGNAL cards with real magnitude/source/date |
| Opportunities | Abstract AI score only, no visible link to actual linked opportunities | Real, full list of linked Opportunity records (title/href/score) plus the existing score card |
| Ripple | 100% fabricated supply-chain graph | Real Intelligence Graph evidence only (real edge_type/weight/confidence/lag_days/source), honest empty states, zero AI/template fallback |
| SEO/AEO/GEO | Duplicate BreadcrumbList bug, no generateMetadata, always-indexable regardless of substance | Real per-tier metadata/robots/canonical, 308 alias redirects, 9 real JSON-LD blocks; sitemap coverage gap found this audit, not yet fixed |
| Performance | Never measured under this discipline | Real median-of-3 production measurement: perf 87, CLS 0.000; Ripple's lazy-load confirmed to add exactly 1 request/0 JS/8.4KB |
| Sparse-data behavior | Fabricated content filled every empty slot | Real → show, Weak → qualify, Missing → hide, confirmed across 5 real profiles including two dedicated sparse cases |

---

## 12. FINAL VERDICT

**COMPANY REDESIGN — BLOCKED**

Exact closure blockers (all independently verified live during this audit, all real, none speculative):

1. **`PatternIntelligenceCard` presents undisclosed generic-template content as personalized company analysis.** The backend's own `degraded: true` flag (with its own source comment: *"generic template, not real analysis — caller must not present this as personalized"*) is never read or surfaced by the frontend component. Live-verified for RELIANCE: specific fabricated-looking numbers (68% similarity score, 75% success rate) shown with zero disclosure.

2. **`OpportunityLifecycleCard`'s "Historical Comparison" text is a hardcoded, unsupported historical-performance claim** ("have historically delivered above-market returns over 12–18 months") shown for every company under an authoritative section label, with no real backtest data anywhere in the codebase to support it, and no disclosure.

3. **The sitemap excludes the large majority of real, qualified companies — including RELIANCE, the primary profile used throughout this entire redesign effort's own testing.** Root cause not conclusively established (possibly a local-dev-only concurrency artifact); needs verification against real production infrastructure before this can be closed either as "not a real bug" or as a confirmed fix target.

These three are the only items blocking closure. Every other finding in Section 10 (items 4-11) is real but does not block closure — they are follow-up work (P1/P2/GLOBAL/DATA), not closure blockers.

Once items 1-3 are resolved (or item 3 is confirmed to be a local-environment-only artifact with no real production impact), this redesign is otherwise ready: the tab architecture, real data contracts, empty-state discipline, Ripple evidence-only design, and performance profile all independently passed this audit with no structural issues found. No reopening of C1-C5 or the information architecture is warranted by anything found here.
