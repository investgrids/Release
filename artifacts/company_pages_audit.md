# MarketRipple — Company Pages Audit
## Entity Hub Design + Fake-Field Audit + SEO/AEO/GEO + Taste + Performance
### READ-ONLY — no implementation. Grounded in the real files read (listed inline) — no code changed, no backend touched.

Date: 2026-08-23. Scope: `/companies` (hub), `/companies/[symbol]` (detail — server wrapper +
`CompanyPageClient.tsx`, 2008 lines, the largest single frontend file audited this session).

---

## 1. Executive Verdict

**This is the most fabrication-heavy surface found in any audit this session — worse than
Opportunity Radar V1 and worse than the AI Article pipeline, both individually and combined.** The
company detail page renders roughly a dozen sections built entirely or mostly from hardcoded,
sector-generic, or formula-invented numbers presented with full visual authority (large fonts,
percentage bars, "confidence" badges) identically for every one of the real 512 companies on the
platform. The worst single instance — an "AI Forecast" section badged **"Premium"** — shows the
exact same three outlook labels, the exact same four catalysts, the exact same four risks, and the
exact same "confidence" percentages for literally every company, plus a large unlabeled composite
number computed as `(ROE + governance score) / 2`, an arithmetic operation with no financial meaning
whatsoever.

The good news, and it matters: **the team has already proven, five separate times on this exact
page, that they know how to fix this correctly** — `OpportunityRadarSection`, `NewsImpact`,
`EconomicCalendarSection`, `CompareWithSection`, and the entire `/companies` hub/list page are all
real, honestly-gated (hide when no real data exists), and well-built. The fabricated sections are
not a knowledge gap; they're unremediated technical debt sitting right next to the proof that the
fix pattern already works. This audit's job is mostly triage and consistent application of a pattern
this codebase has already validated four times over, not invention of a new approach.

Separately, and just as important for Company Pages specifically (a "central entity node" as you put
it): the page fires an already-self-diagnosed ~18+ concurrent client-side requests on load, several
of them sequential-dependent (5 individual peer-stock fetches, one per peer, awaited in a
`Promise.all` after the main stock loads). This is a real, severe, already-documented-in-code
performance problem independent of the fabrication issue.

---

## 2. Current UI Audit

### 2.1 `/companies` hub — genuinely good, keep as the model

- Server-rendered, real `generateMetadata`, canonical URL collapses all `?tab=` variants onto one
  page (correct duplicate-content prevention).
- Real stats (`companiesTotal`/`sectorsCount`/`articlesTotal`) fetched live — explicit code comment
  confirms a **previously real bug**: the hub used to read a static, hand-maintained company list
  (`lib/companies-data.ts`) that had silently drifted to 194 companies vs. the backend's real 512.
  Fixed to read the live source. Directly relevant precedent for the detail page's fabricated
  sections below — same class of problem (a plausible-looking static substitute quietly diverging
  from reality), already fixed once here.
- `OverviewTab` is explicitly, deliberately honest by design: its own code comment states two
  candidate sections ("Fastest Improving Companies," "Recently Compared Companies") were **omitted
  entirely** because no real backing data exists for them — the same "real data or nothing" principle
  already established for Opportunity Radar and Weekend Intelligence, applied here first, if
  anything, before those other surfaces.
- `AllCompaniesTab` (the "All Companies" table): real, server-rendered, real pagination, real
  filters. One small, low-stakes decorative fabrication: its `Sparkline` component draws one of two
  hardcoded zigzag shapes based only on the `positive` boolean — not a real 1-day price series, a
  generic up/down squiggle reused identically for every company. Minor, worth fixing, not urgent.

**Classification: KEEP** — the hub is the reference standard for the rest of this audit, not a
redesign target.

### 2.2 `/companies/[symbol]` detail — server wrapper: also genuinely good

`page.tsx` (the server wrapper) is a mature, already-audited SEO surface: real `generateMetadata`,
a real `Corporation` JSON-LD block, a real `FAQPage` JSON-LD block built from **honestly-gated**
real fields (price always included; market cap/PE/sector/analyst-consensus FAQs only appear when
that field has a real, non-placeholder value — nothing invented to hit a fixed FAQ count), correct
404-vs-transient-failure distinction (confirmed live via real symbol tests), and an explicit fix
avoiding a duplicate `BreadcrumbList` (root layout already emits one globally). This wrapper is the
same quality tier as Opportunity Radar's and the Newsroom article page's server wrappers — no
changes needed here.

**Classification: KEEP.**

### 2.3 `/companies/[symbol]/CompanyPageClient.tsx` — where the fabrication concentrates

24 distinct sections, `renderGroup`-staged into 3 progressive waves (a real, deliberate performance
technique — see §7). Section-by-section:

**Already real and correctly built (no action needed):**
- `CompanyHero` — real price/market data, correct single-`<h1>` handling matching the server
  wrapper's pattern.
- `PriceChart` — real chart data, real OHLC strip.
- `FinancialHighlights`, `KeyRatios`, `HistoricalPerformance` — real fundamentals data throughout.
- `EventTimeline` — explicit code comment confirms a **previously fixed bug**: this used to show
  fake per-event impact/sentiment badges "from a hardcoded cycling array"; now shows only real
  title+date, no invented badge.
- `NewsImpact` — same pattern, explicit comment: only real, deterministic `impact_score` is shown;
  no fabricated sentiment classification exists anywhere in the pipeline, so none is displayed.
- `OpportunityRadarSection` ("AI Company Intelligence Score") — explicit comment confirms this
  **replaced 3 entirely fabricated cards** (invented titles, invented scores/confidence/revenue/
  timeline) with the real `company_score_engine.py` output — real score, real confidence, real
  `top_contributors[]` with real source attribution and dates. Hides entirely when a company has
  zero real signals rather than showing a fabricated fallback.
- `EconomicCalendarSection` — explicit comment confirms this **used to render five identical
  hardcoded fake dates on every single company page** ("Q1 Results 15 Jul, RBI Policy 05 Aug...");
  now returns `null` because no trustworthy per-company forward-looking event source exists yet.
- `CompareWithSection` — real, only shows genuinely published `comparison_publisher.py` articles for
  this company's real peers; renders nothing when none exist rather than a 404-prone stub link.
- `Shareholding` — real `yfinance` holdings data via an honest 3-way split (Insiders/Institutions/
  Public), explicitly NOT a fabricated 4-way SEBI-style Promoter/FII/DII/Retail breakdown the real
  data source can't actually support; returns an honest "unavailable" state when no data exists.
- `RelatedStories` — real internal linking from `/api/insights/company/{symbol}`.

**Fabricated — presented as real, needs the exact same treatment as the sections above:**

| Section | What's fabricated | Severity |
|---|---|---|
| `AIForecast` | Entire section: 3 outlook labels + 3 "confidence" percentages, 4 catalysts, 4 risks — all 100% hardcoded, identical for every company. Plus an unlabeled `(ROE + gov_score)/2` composite number with no financial meaning. Badged **"Premium"**. | **Critical** |
| `deriveSegments()` → `BusinessSegments` | Hardcoded per-sector lookup table (5 sectors + 1 generic fallback) of business-segment %/growth/margin — same numbers for every company sharing a sector. Has an honest "Indicative · Sector Averages" disclosure badge, but the underlying data isn't real sector benchmarks, it's hand-typed placeholder numbers. | High |
| `deriveGeography()` → `RevenueGeography` | Same pattern as Segments — hardcoded per-sector revenue-by-region table, same disclosure badge, same underlying fabrication. | High |
| Government Exposure → "Policy Impact Cards" | 3 hardcoded policy names/impacts/scores (78/65/72) for every company — including a fake rupee figure computed as `market_cap × 0.05` presented as a real "opportunity" value with zero backing. No disclosure badge at all. | **Critical** |
| `OrderBook` | Entire section is a formula fabrication: `market_cap × 2.8/1.9/0.9` for Total/Pending/Completed order-book values, plus a static "68%" execution rate — for every company, including ones with no order-book business model at all (e.g. IT services, banks). No disclosure badge. | **Critical** |
| `AISentiment` | Falls back to hardcoded 62%/15%/23% bull/bear/neutral when no real analyst buy/sell/hold data exists (silently indistinguishable from a real reading). The "Bullish % Weekly Trend" chart is a fully invented 5-point historical line — the same `buildScoreHistory()`-style fabrication already flagged and removed from Opportunity Radar V1. | **Critical** |
| `deriveNetworkNodes()` → `NetworkGraph` | A synthetic star graph — generic "Government"/"Policy"/"Suppliers"/"Customers" nodes at fixed pixel positions with canned edge labels ("Policy," "Budget," "Revenue," "Supply") — only 2 of ~7 nodes (peers) are real. The exact same fabrication pattern as V1 Opportunity's `OpportunityRippleGraph`, already found and flagged for replacement in that audit. | **Critical** |
| `PeerComparison` | The self-row always shows a hardcoded "+12%" revenue growth for every company; peer rows honestly show "—" when unavailable — the self-row's fake specific number is more misleading than an honest dash. | Medium |
| `SimilarCompanies` | Hardcoded similarity percentages `[92, 88, 84, 79, 74]` and hardcoded cycling reason text, applied regardless of which real peer is in which position. | Medium |
| `Documents` | Entirely fake static document list ("Annual Report FY24," fake file sizes like "4.2 MB") with no real href — a fake document library with non-functional download buttons. | Medium |
| Right sidebar → "Top Risks" / "Top Opportunities" | Both mostly hardcoded text + hardcoded severity/score numbers (72/58/45 and 88/74/68) for every company; "Export order growth" shown even for domestic-only businesses. | High |
| Right sidebar → "Quick Stats" | One field, "Face Value," is hardcoded `₹1.00` for every company regardless of the real, varying face values of Indian-listed stocks. | Low |
| `InvestmentThesis`/`ScenarioAnalysis`/`OpportunityLifecycleCard` (collapsed "Investment Intelligence" panel) | `ScenarioAnalysis`'s bull/base/bear probabilities are hardcoded to exactly 30/50/20 for every company regardless of any real volatility/dispersion signal (real target prices are used for the dollar figures, but the probabilities attached to them are invented). `OpportunityLifecycleCard`'s `historicalComparison` text asserts a specific, confident historical performance claim ("Companies with similar positive-rating ratios... have historically delivered above-market returns over 12–18 months") with **zero real historical data behind it anywhere in the component's props** — an outright fabricated statistical claim, not merely an unsupported inference. | **Critical** |
| `AskAI` suggestion chips | Cosmetic only — real feature (links to AI Search), fine as-is. |  — |

**Classification**: **KEEP** (9 real sections + hub/list page) · **REPLACE-OR-REMOVE** (12 fabricated
sections, ranked Critical/High/Medium above) — following the exact same hide-when-no-real-data
pattern already proven 5 times on this same page.

---

## 3. Why This Matters More Here Than Elsewhere

Opportunity Radar's and the AI Article pipeline's fabrication problems were real but scoped —
specific fields, specific sections, traceable to specific prompt/schema decisions. Company Pages'
fabrication is broader and more visually authoritative: full sections with progress bars, "Premium"
badges, and percentage "confidence" figures, applied identically across all 512 real companies
regardless of sector, business model, or real fundamentals. A reader has no way to tell, from the
page itself, that "Export order growth: 74" or "AI Forecast: Bullish, 72% confidence" is not
computed from anything — it's typed once and shown to everyone. For a page you've named as MarketRipple's
central entity hub with "strong evergreen Google-search potential," this is the highest-leverage
place in the whole product to fix first, exactly as you said.

---

## 4. Information Architecture — Entity Hub Redesign

Your framing: Company → Developments → Events → Newsroom → Opportunities → Ripple → AI Search.
Checked against what's real today:

| Relationship | Real today? | Where |
|---|---|---|
| Company → Events | Yes | `EventTimeline` (real, `/events/{id}` links) |
| Company → News/Articles | Yes | `NewsImpact` (real `impact_score`), `RelatedStories` (real `/api/insights/company/{symbol}`) |
| Company → Company Score (AIPE-derived) | Yes | `OpportunityRadarSection` — real `company_score_engine.py` signals with source attribution |
| Company → Comparisons | Yes | `CompareWithSection` — real `comparison_publisher.py` output |
| Company → Opportunities (V2) | **Not found** | No `OpportunityV2` reference anywhere in this file — a real gap. `company_signals` in V2's own `score_breakdown` already stores per-company `real_direction`/`confirms_thesis` data (built this session, Batch C) — the reverse direction (an opportunity showing which companies confirm it) exists; the forward direction (a company page showing which open V2 opportunities it's connected to) does not. |
| Company → Developments | **Not found** | No `Development`/`DevelopmentEvidence` reference anywhere in this file — same gap the Newsroom Article audit flagged for articles. |
| Company → Intelligence Graph / Ripple | **Fabricated substitute exists** (`NetworkGraph`) | Should become the same evidence-scoped real-graph pattern already speced for Opportunity Radar's Ripple redesign — a company's real `IGNode` neighborhood, not invented Government/Policy/Supplier/Customer boxes. |
| Company → AI Search | Yes | `AskAI` section, hero "Ask AI" button, `NextSteps` block — all real, well-built |
| Company → Sectors | Yes | Sector chips, `deriveSegments`/`deriveGeography` (fabricated content, but the *link target* concept — sector — is real) |

**Recommended redesign direction**: once the fabricated sections are removed, replace the vacated
space not with decorative filler but with the two real, missing connections — a real "Linked
Developments" section (mirroring Opportunity Radar's `supporting_evidence` pattern) and a real
"Open Opportunities" section (this company's real `company_signals` entries across all open V2
opportunities, once V2 is promoted) — turning the page into the actual entity hub you described,
built from real accumulated intelligence rather than backfilled with more invented content.

---

## 5. SEO / Structured Data — already strong, minor gaps

- `Corporation` schema + `FAQPage` schema: real, honestly-gated, good.
- Real, honest H1/description handling matching the established pattern from Radar and Newsroom.
- **Gap**: no `BreadcrumbList` duplication risk (already solved), but no dedicated `Organization` /
  `tickerSymbol`-linked entity graph beyond the single `Corporation` block — not necessarily wrong,
  just not independently verified against Google's current stock-entity guidance in this pass.
- **Real content-depth question**: once the ~12 fabricated sections are removed, the page's real,
  substantive content shrinks meaningfully. This isn't a reason to keep the fabricated sections — but
  it does mean the replacement content (real Developments/Opportunities links, per §4) needs to
  actually ship, not just have the fake content deleted, or these very evergreen-SEO-valuable pages
  could thin out.

---

## 6. Internal Linking

Genuinely good already: peer links, sector links, event links, article links, comparison links, all
using real entities. The one broad gap is Company → Development / Company → Opportunity (§4) — the
same "real relationships, never keyword matching" principle already established for Radar and
Newsroom applies identically here once those two connections are built.

---

## 7. Performance — the second major finding

- **Real, already-diagnosed problem, confirmed in the code's own comments**: this page fires
  approximately 18+ concurrent same-origin client requests on load (stock detail, news, chart, one
  fetch each for company-scores/insights-company/insights-comparisons/peer-comparison ×5 individual
  peer fetches, plus `useIntelligence`'s own fetch, plus `CompanyIntelligenceSection`'s own fetch,
  plus an app-wide SSE connection that never releases its slot). The code's own comment states this
  can starve a late-queued fetch indefinitely under HTTP/1.1's 6-connections-per-origin cap — this is
  not a hypothetical risk, it's a documented, real, currently-live architectural problem.
- **Positive, real technique already in place**: `renderGroup`-staged progressive rendering (wave 1
  above-fold immediately, wave 2 at 120ms, wave 3 at 350ms) is a genuine, deliberate performance
  pattern — not decoration, actual render-cost management. Worth preserving and citing as a model.
- **`reactflow` is a real, sizeable dependency loaded specifically to render the fabricated
  `NetworkGraph`.** Once that section is replaced or removed, this dependency may become removable
  from this page's bundle entirely — a real, concrete bundle-size win, the same class of "fabrication
  removal is also a performance win" finding as Opportunity Radar's Recharts removal.
- **No baseline captured** in this read-only pass — per the established session methodology,
  capture median-of-3 Lighthouse numbers (isolated build, warmed server) before any implementation,
  same as Weekend Intelligence and the Radar spec.

---

## 8. Taste

The visual language here (rounded-[28px] cards, `hover:-translate-y-0.5`, gradient icon badges,
`framer-motion` `fadeUp` stagger on every section) is more ornate than Weekend Intelligence's or
Opportunity Radar's already-audited restraint — closer to "card soup" and decorative gradients
(`ScoreBadge`-style gradient circles, `AIForecast`'s violet-to-sky gradient background) than the
"instrument panel" weight established elsewhere this session. This is a real taste-consistency gap
across the app worth addressing in the same pass as the fabrication fixes — but secondary to the
fabrication problem itself; don't spend redesign effort on visual restraint before the underlying
data is honest, since restyling fabricated content just makes it a more polished fabrication.

---

## 9. What NOT to Build

Following the same discipline established in the two prior audits:
- No new fabricated section to "fill the space" once the ~12 fake sections are removed — real
  Development/Opportunity links (§4) are the honest replacement, and if those aren't ready yet, an
  honest gap is correct, matching `EconomicCalendarSection`'s own precedent (`return null`).
- No invented historical-performance claims of any kind (the `OpportunityLifecycleCard`
  `historicalComparison` fabrication is the single most serious individual finding in this section —
  remove the claim, don't soften its wording).
- No fabricated "confidence" percentage attached to any invented forecast, scenario, or opportunity
  score — same standing rule as Opportunity V2's "Opportunity Strength, never Confidence."

---

## Final answer

**Why does this matter more than another visual pass?** Because Company Pages are the one surface
in MarketRipple visited by users evaluating a *specific, real, individually named company* — and
right now, a meaningful fraction of what they see there (order book size, forecast confidence,
policy impact value, peer growth rate, historical outperformance claims) is not about that company at
all. It's the same typed text and the same three numbers shown to every visitor of every company page
on the platform. The fix is not a redesign — it's applying, five more times, the exact pattern this
codebase has already proven it knows how to execute correctly on this very page.
