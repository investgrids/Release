# MarketRipple — Global Fabrication Audit
### READ-ONLY sweep of the entire frontend for hardcoded/formula-invented content presented as real intelligence. No code changed.

Date: 2026-08-23. Method: systematic search across `apps/web` for (a) the exact fabrication
signatures already confirmed in the Opportunity Radar, AI Article, and Company Pages audits
(hardcoded percentage/score fallbacks, `market_cap × constant` formulas, fake historical/trend
arrays, sector-generic canned text, synthetic relationship graphs), and (b) the codebase's own
extensive self-documentation habit (comments confirming what was deliberately NOT fabricated, and
comments describing bugs already found and fixed) — both real signal for where the problem is, and
isn't.

---

## Headline result

**The fabrication problem is real but concentrated, not uniform.** The large majority of the app —
Ripple, Historical Patterns, Tools (Portfolio Confidence), Events, Best Stocks, Sectors, most of
Market Intelligence's tabs, AI Search's components, Research/Comparisons, and every Knowledge page
checked — already carries explicit, consistent "real data or nothing" discipline, much of it with
comments describing a prior fabricated version that was found and deliberately fixed. This sweep
found **two more real, live instances** beyond the three already-audited surfaces
(Opportunity Radar, AI Articles, Company Pages) — smaller in scope than any of those three, but
real, live, and previously undiscovered.

---

## 1. Confirmed clean (spot-checked, no action needed)

| Surface | Evidence |
|---|---|
| `/ripple` (`InvestmentThesisTab`, `RippleChainTab`) | Explicit comments: "not new fabricated copy," "never show fabricated examples when the API has nothing" |
| `/historical` (`HistoricalPatternsMasterDetail`, `[id]/page.tsx`) | Explicit comments: "not an invented causal chain," FAQs "not a second LLM call, not invented" |
| `/tools/portfolio-confidence` | Page-level and layout-level copy publicly states "no fabricated numbers"; loading-stage cycling text explicitly shows no percentage so nothing claims false precision |
| `/events` (`EventPageClient.tsx`, `page.tsx`) | Extensive, repeated explicit guards: "No fabricated historical statistic," sectors "never a fabricated 'why' reason... omitted rather than invented," today-counts fix removing a previous `veryHigh * 0.2`-style fabrication |
| `/best-stocks` | "Never a fabricated number... no single fabricated hero number" |
| `/sectors/[sector]` | "an honest 'no live index for this one' rather than a fabricated 0%" |
| Market Intelligence tabs (`LiveMarketTab`, most of `OverviewTab`) | "nothing here is inferred/fabricated," a previously hardcoded "92%" stat already replaced with the real shared MIE state |
| AI Search components (`SearchProgressStages`, `AISearchFindingsRecap`, `ConfidenceBreakdownPanel`, `AISearchGraphReveal`, `DecisionTimelinePanel`, `AISearchHistory`, `ResearchWorkspace`) | Consistently the most rigorously documented anti-fabrication code in the app — real elapsed times, real confidence components (not a fabricated 6-way split), real search history only |
| `/research`, `/research/comparisons` | Real Organization-type JSON-LD (not a fabricated human byline), no fabricated sector categories |
| Knowledge pages (`about`, `how-it-works`, `ai-methodology`) | Publicly state MarketRipple's own honesty commitments — see §3 for why this matters |
| `CompanyIntelligenceSection.tsx` (used on Company Pages) | Real backend endpoint, reuses real engines (Unified Event Intelligence, Investment Watch, Confidence Explainability panel), honestly gates on `data.available` |

---

## 2. New findings — not covered by the three prior audits

### 2.1 News Article detail (`app/news/[id]/NewsPageClient.tsx`) — a fabricated "AI Analysis" tab

A component literally named `AIAnalysisTab` renders output from `deriveAIInsights()`, which is
**100% deterministic client-side template logic — no AI or backend call involved at all**:

- `deriveSentiment()` classifies Bullish/Bearish/Neutral by counting hits against two hardcoded
  word lists (`BULLISH_WORDS`/`BEARISH_WORDS`) against the headline/summary text — a crude keyword
  heuristic, not a real sentiment classification.
- `bullPct`/`bearPct` (used elsewhere in the same file, `OverviewTab`) are computed as
  `score × 0.7` / `score × 0.15` / `score × 0.35` / `score × 0.65` — arbitrary multiplier constants
  with no stated methodology, applied to the one real number (`impact_score`) to manufacture a
  bull/bear percentage split that doesn't otherwise exist.
- `SECTOR_RISKS` — a hardcoded 10-sector lookup table of generic risk text (Banking, Technology,
  Energy, Defence, Pharmaceuticals, etc.) — the exact same structural pattern as Company Pages'
  already-flagged `deriveSegments()`/`deriveGeography()`, but here with **no disclosure badge at
  all**.
- `deriveAIInsights()`'s `shortTerm`/`longTerm` outlook text is template-interpolated prose keyed
  only by derived sentiment and sector membership (e.g. "Long-term outlook remains positive —
  government capex and policy push create multi-year tailwinds" for *any* Infrastructure/Defence
  article, regardless of its actual content) — the same canned-prose-by-category pattern as
  Company Pages' `AIForecast` catalysts/risks lists.
- One row is not even conditional: the "Medium-term (3–12M)" outlook text
  ("Monitor sector execution and policy follow-through...") is **hardcoded verbatim for every
  single article**, no branching at all.

**Why this one matters especially**: this directly contradicts a rule already established
*elsewhere in this exact codebase* — Company Pages' `NewsImpact` section has an explicit comment
stating "there is no real per-article sentiment classification anywhere in the pipeline," and
deliberately does not show one. The News detail page independently invented its own crude
classifier and presents its output under a tab literally labeled "AI Analysis." Two pages in the
same app disagree, in code, about whether per-article sentiment is a real, trustworthy thing to
show — one correctly says no, the other fabricates one anyway.

**Severity: Critical** (same tier as Company Pages' worst items) — an entire tab's worth of content,
unlabeled as anything other than real AI analysis, contradicting an already-established internal rule.

### 2.2 `AIOpportunitySection.tsx` (rendered live on Market Intelligence's Overview tab) — fake trend + fake sparkline

Confirmed live usage: `components/market/tabs/OverviewTab.tsx` imports and renders this component
with real `score`/`theme`/`category` data from the radar API — but:

- `trend` is fabricated at the call site: `trend: hasScore && rawScore >= 70 ? "up" : "stable"` —
  never "down," derived purely from the same score already being displayed, not from any real
  historical trend.
- `TrendSparkline` then draws that fake trend as a wiggly line using
  `Math.sin(seed + i * 0.9) * 5` (a deterministic pseudo-random function, `seed` = the row's array
  index) — a fabricated-looking-organic squiggle with zero connection to any real price or score
  history, visually implying a real multi-point time series that doesn't exist.

Same class of issue as `AllCompaniesTab`'s already-noted two-shape sparkline (Company Pages audit,
low severity) — but *more* convincing/deceptive here because the sine-wave shape looks like real
noisy data rather than an obviously generic icon.

**Severity: Medium** — smaller surface area than 2.1, but live, real, and unlabeled.

### 2.3 Dead code, no live risk

`components/CompanyImpactFeed.tsx` — a generic display component (no data-fetching, no fabrication
of its own) — grep-confirmed to have **zero importers anywhere in the app**. Not a live fabrication
risk; flagged only so it isn't mistaken for something needing a fix, or accidentally wired up later
without review.

---

## 3. A finding worth naming directly: the app makes public honesty claims that some of its own pages contradict

`app/(knowledge)/about/page.tsx` states, as one of MarketRipple's four public "AI Trust" pillars:
*"Every AI output carries a real, calculated confidence score — never a fabricated certainty, and
never hidden."* This claim is **true** of the majority of the app (confirmed extensively in §1) but
is **directly contradicted**, right now, by:
- Company Pages' `AIForecast` (hardcoded 78%/72%/68% "confidence" for every company, §Company
  Pages audit),
- Company Pages' `AISentiment` fallback (hardcoded 62% when no real analyst data exists),
- Company Pages' `ScenarioAnalysis` (hardcoded 30/50/20 probabilities for every company),
- News Article's `AIAnalysisTab` (an "AI Analysis" that is not AI at all).

This isn't a new finding beyond what's already catalogued — it's a reframing worth keeping: fixing
these isn't just data hygiene, it's closing a real gap between a public claim the product already
makes about itself and what a fraction of its own pages actually do.

---

## 4. One finite, whole-application cleanup list

Consolidating this audit with the three prior ones — every confirmed live fabrication instance found
across the entire frontend, in one place, as requested:

| # | Location | Item | Severity | Source audit |
|---|---|---|---|---|
| 1 | Company detail | `AIForecast` section | Critical | Company Pages |
| 2 | Company detail | Government Exposure "Policy Impact Cards" | Critical | Company Pages |
| 3 | Company detail | `OrderBook` | Critical | Company Pages |
| 4 | Company detail | `AISentiment` fallback + fake trend | Critical | Company Pages |
| 5 | Company detail | `NetworkGraph` synthetic star | Critical | Company Pages |
| 6 | Company detail | `ScenarioAnalysis`/`OpportunityLifecycleCard` (fixed probabilities + unsupported historical claim) | Critical | Company Pages |
| 7 | News Article detail | `AIAnalysisTab` / `deriveAIInsights` / `SECTOR_RISKS` | Critical | **This audit** |
| 8 | Company detail | `BusinessSegments` / `RevenueGeography` (disclosed but still fabricated) | High | Company Pages |
| 9 | Company detail | Right sidebar "Top Risks" / "Top Opportunities" | High | Company Pages |
| 10 | Opportunity Radar detail | `buildScoreHistory` fake chart | High | Opportunity Radar |
| 11 | Opportunity Radar detail | Financial Impact metrics | High | Opportunity Radar |
| 12 | Opportunity Radar detail | `OpportunityRippleGraph` synthetic star | High | Opportunity Radar |
| 13 | Opportunity Radar detail | Investment Verdict | High | Opportunity Radar (already decided: disabled for V2) |
| 14 | AI Articles | `key_takeaway` boilerplate contamination | High | AI Articles |
| 15 | AI Articles | `confidence_score`-gated publish check | High | AI Articles |
| 16 | AI Articles | Rigid What/How/Why headline template | Medium | AI Articles |
| 17 | Company detail | `PeerComparison` fake self-row growth | Medium | Company Pages |
| 18 | Company detail | `SimilarCompanies` fake similarity % | Medium | Company Pages |
| 19 | Company detail | `Documents` fake file list | Medium | Company Pages |
| 20 | Market Intelligence Overview | `AIOpportunitySection` fake trend + sparkline | Medium | **This audit** |
| 21 | Opportunity Radar list | `SectorDistributionDonut` | Medium | Opportunity Radar |
| 22 | Company detail | Sector distribution donut | Medium | Company Pages |
| 23 | Companies "All Companies" table | `Sparkline` two-shape fake | Low | Company Pages |
| 24 | Company detail | Right sidebar "Face Value" hardcoded ₹1.00 | Low | Company Pages |
| 25 | Newsroom `/newsroom/themes/[slug]` | Duplicate content (not fabrication, but same "looks complete, isn't real" family) | High | Opportunity Radar (§25) |

Items 1-7 and Newsroom item 25 are the highest-leverage fixes — full sections/pages, not single
fields, all Critical or High severity, all following the exact same already-proven remediation
pattern (fetch real data → hide entirely when none exists).

---

## 5. What this confirms about the platform-level pattern

Consistent with your own framing: every instance across all four audits traces to the same root
habit — a page trying to look complete by filling a slot with plausible-sounding invented content,
rather than accepting an honest gap. And every *fix* found in this sweep (the majority of the app)
follows the identical, already-proven counter-pattern: fetch real data, and when none exists, hide
the section rather than fabricate a fallback. Nothing found in this audit requires inventing a new
remediation approach — items 1-25 above are a checklist for applying a pattern this codebase has
already validated dozens of times, not a new design problem.

---

## Final answer

**Is the fabrication problem platform-wide, or contained?** Contained, but real. Two-thirds to
three-quarters of the app, by page count, is already clean and well-documented. The problem
concentrates in four places: Company Pages (worst, ~12 sections), Opportunity Radar V1's detail page
(~6 sections, already speced for replacement by V2), the AI Article pipeline (field-level, not
whole-section), and — newly found here — News Article detail's fabricated "AI Analysis" tab plus one
component (`AIOpportunitySection`) reused on Market Intelligence's Overview tab. Twenty-five items,
fully enumerated above, is the whole list — not an open-ended risk.
