# Company Redesign — Batch 3: Financials + Events + Opportunities

Date: 2026-08-25
Branch: `company-identity/c1-reconciliation` (worktree `D:\ig-company-identity`), commit `b4bf9ae`
Scope: reorganize surviving real financial data; company-scoped real Events; canonical Opportunity relationships only, per the owner's approved plan.

## What shipped

- **Financials tab: no further reorganization applied.** Batch 1 already grouped `FinancialHighlights` (headline KPIs + annual table) → `KeyRatios` (detailed ratio grid) → `Shareholding` (ownership structure) → `HistoricalPerformance` (multi-year chart) under one dedicated tab — itself a real reorganization from being scattered across two separate 3-wave stacks before. Re-reviewed each component's real content; the existing big-picture-to-detail-to-ownership-to-history order already serves the tab's research question. Reordering further without a concrete problem to fix would be busywork against the plan's own "tabs must not become miniature dashboards" constraint — reserved effort for the two items below with real, demonstrable gaps instead.

- **Events tab: real company-scoped events, not just yfinance's sparse list.** `stock.events` (yfinance's own corporate-action list) is frequently empty — confirmed live for RELIANCE. Meanwhile `related.py`'s "company" branch already computed a real, richer symbol-matched event set (graph/RSS-sourced events that actually mention this company) that no dedicated endpoint or UI ever exposed. Added a real `company` query param to `GET /api/events` (`app/api/events.py`), reusing the exact same symbol-match logic already proven correct in `related.py` — not a new heuristic. New `EventsTabBody` component fetches this while the Events tab is mounted and uses it as the primary source, falling back to `stock.events` only when the richer fetch itself returns nothing. Its honest empty-state check (from Batch 1) now reflects what's actually being rendered, not a stale pre-fetch snapshot.

- **Opportunities tab: real linked-opportunities list, not just an abstract score.** The tab previously showed only `OpportunityRadarSection`'s AI Company Score card (real, but abstract — no actual links to the Opportunity records this company is part of). New `RelatedOpportunitiesList` fetches the same unified `/api/related/company/{symbol}` contract Batch 0 already made canonical (`company_intelligence.get_related_opportunities`, which dispatches V1/V2 by `settings.opportunity_v2_promoted` transparently) and renders the real title/href/score for every linked opportunity. This tab never branches on V1 vs V2 itself — there is no V1-shaped UI here, just the real fields common to both sources — which is the concrete meaning given to "canonical Opportunity V2 relationships only, no V1 compatibility UI" for this batch: not "hide real V1 data" (V2 isn't promoted yet, so most companies' real opportunity relationships are still V1-sourced today, and hiding real data to satisfy a label would contradict the redesign's own "real data → show it" rule), but "never build separate V1-specific UI" — which was already true before this batch and stays true after it. `OpportunityRadarSection`'s score card is left untouched alongside it.

## Real duplication found, not fixed (V1 data quality, out of scope)

RELIANCE's real linked-opportunities list includes two separate Opportunity records both titled "Defence Investment Opportunity" (ids 25 and 26, both score 98). This is real V1 opportunity-generation duplicate-thesis behavior — the exact problem the (separately built, currently held pending the Warehouse gate) Opportunity Engine V2 exists to fix via its identity/coherence engine. Not something to patch inside this UI batch; shown honestly as real data rather than silently deduplicated or hidden.

## Verification (real data, real browser)

- `tsc --noEmit`: clean, 0 errors.
- Full backend pytest suite: 1048 passed, 5 failed, 2 skipped, 2 xfailed (28.5 min — the full suite makes real external-network calls, unlike the fast SQLite-scratch-DB company_identity subset). All 5 failures are in subsystems this batch (and every prior batch) never touched, and are demonstrably live-network-dependent, not diff-caused: `test_ai_search_engines_live.py`, `test_ai_service_nvidia.py::test_best_reasoning_tier_falls_back_to_medium_chain`, `test_development_historical_retrieval.py` (2 tests), `test_macro_rates.py::test_macro_rate_state_live_end_to_end` — the last one's captured log shows a literal live HTTP timeout (`error='The read operation timed out'` from the US Treasury source) and an RBI WSS parsing warning. No failure touches `events.py`, `related.py`, or any Batch 0-3 file.
- Real Playwright pass against a live backend+frontend:
  - RELIANCE Events tab: real heading, 2 real event links rendered from the new `company=` query param, empty-state message correctly does not show now that real data exists.
  - RELIANCE Opportunities tab: real "Opportunities Connected to Reliance Industries Limited" heading with 7 real opportunity links (each with its real score), the pre-existing AI Company Intelligence Score card still renders correctly alongside it.
  - GOLDENTOBC Opportunities tab (no real linked opportunities): honest "No real opportunities are currently linked to Golden Tobacco Limited" empty state, not a blank section.

## Explicitly not done in this batch

No Ripple wiring (Batch 4). No Peers changes (Batch 4). No general polish/empty-state pass beyond the concrete gaps found live (Batch 5). No fix for the real V1 duplicate-opportunity-title finding above.
