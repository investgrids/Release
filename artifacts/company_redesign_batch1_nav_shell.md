# Company Redesign — Batch 1: Navigation Shell

Date: 2026-08-25
Branch: `company-identity/c1-reconciliation` (worktree `D:\ig-company-identity`), commit `2bd6d30`
Scope: shell/navigation mechanics, per the owner's approved 6-batch plan — get desktop/mobile/back-forward/URL behavior right before the per-tab content redesign in Batches 2-4.

## What shipped

Replaced the old single-scroll, 3-wave progressive-reveal Company page with a persistent `CompanyHero` header + a real, URL-addressable 7-tab strip: **Overview · Intelligence · Financials · Events · Opportunities · Ripple · Peers**.

- **URL-driven, not local-only state.** The active tab reads/writes a `?tab=` query param via `next/navigation`'s `useRouter`/`usePathname`/`useSearchParams`. A tab is shareable, survives a reload, and clicking through tabs creates real browser history entries — back/forward moves between tabs the same way it moves between pages, not just scroll position. `useSearchParams()` requires a Suspense boundary in the App Router, so `StockPage` now wraps the real implementation (`StockPageInner`) in one.
- **Tabs replace the body, not scroll to an anchor.** Selecting a tab swaps what's rendered below the persistent header; the previous tab's content unmounts.
- **Every existing real section preserved, regrouped by research question**, not redesigned yet (that's Batch 2-4):
  - Overview: `CompanyIntelligenceSection`, `PriceChart`, `AISummary`, `ShareInsightCard`, `NextSteps`, `RelatedStories`
  - Intelligence: `StockDNA`, `AISentiment`, `IntelligenceBlock`, `InvestmentThesis`, `ScenarioAnalysis`, `OpportunityLifecycleCard`, `MonitoringChecklist`, `PatternIntelligenceCard`, `RelatedContent` — no longer hidden behind a collapse-to-expand button, since it's now its own dedicated tab
  - Financials: `FinancialHighlights`, `KeyRatios`, `Shareholding`, `HistoricalPerformance`
  - Events: `EventTimeline`, `NewsImpact`
  - Opportunities: `OpportunityRadarSection`
  - Peers: `PeerComparison`, `CompareWithSection`
  - Ripple: a new, honest `RipplePlaceholder` — states plainly that the real `/api/ripple/company/{ticker}` view isn't wired into this tab yet (that's Batch 4) and links to the existing `/ripple` page, rather than fabricating relationship data to fill the slot.
- **Sticky right-rail `IntelligencePanel`** stays present across every tab (unchanged from before), matching a persistent-context pattern rather than duplicating it per tab.

## Real bug found and fixed during live testing (not left as a known gap)

`EventTimeline`/`NewsImpact` already returned `null` on empty data — correct, no fabricated filler — but that was harmless when they were two of ~15 stacked sections on one long page. With Events now a dedicated tab containing only these two, a company with no tracked events/news (confirmed live: RELIANCE's `stock.events` and both news sources were all empty in the current real dataset) left the Events tab completely blank with zero explanation, immediately followed by the sidebar. Fixed with a minimal, honest one-line empty state scoped to this exact case. This is a shell-correctness fix (a tab must never render silently blank), not new content design — full empty/partial-state work across every tab remains Batch 5's job per the approved plan, and the same theoretical risk likely exists in other tabs pending that pass.

## Verification (real browser, not test-only)

- `tsc --noEmit`: clean, 0 errors.
- Real Playwright pass (desktop 1400×900 + mobile 390×844) against a live backend+frontend on `/companies/RELIANCE`:
  - All 7 tabs render in the correct order.
  - Clicking Opportunities swaps the body (`Company Ripple` text correctly absent) and updates the URL to `?tab=opportunities`; `aria-current="page"` tracks the active tab.
  - Clicking Ripple shows the real placeholder text and updates the URL.
  - Real browser back/forward (`page.goBack()`/`goForward()`) correctly replays tab history (ripple → opportunities → ripple).
  - A direct cold-load of `?tab=peers` renders Peers active and its real `Peer Comparison` content, with no click required — confirms shareable/bookmarkable tab URLs work.
  - Mobile: the tab strip scrolls horizontally (`scrollWidth` 626px > `clientWidth` 358px for 7 tabs on a 390px viewport) while the page body itself does not scroll horizontally (`scrollWidth` == `clientWidth` == 390).
  - After the Events empty-state fix, re-verified live: the honest empty-state message is present in the DOM on `?tab=events` for RELIANCE.

## Explicitly not done in this batch

No per-tab content redesign or compacting (the exact Overview mockup, real Intelligence-tab Company Score contributors, etc. are Batches 2-3). No Ripple API wiring (Batch 4). No general empty/partial-state design pass beyond the one concrete bug found live (Batch 5).
