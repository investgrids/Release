# Company Redesign — Batch 0: Contracts + Truth Cleanup

Date: 2026-08-25
Branch: `company-identity/c1-reconciliation` (worktree `D:\ig-company-identity`), commit `4cd1032`
Scope: the owner-approved prerequisite batch before any visual redesign work — see `artifacts/company_redesign_audit_spec.md` for the full audit this batch executes against.

## What shipped

1. **Unified Company → Opportunity V2 relationship contract.** `app/api/related.py`'s `entity_type == "company"` branch previously called an unscoped `_recent_opportunities(db, 4)` — the same function used for the homepage feed, with no company scoping at all. It now calls the same canonical dispatcher (`app.services.company_intelligence.get_related_opportunities`) the Overview tab's `CompanyIntelligenceSection` already used. Before this fix, a Company page's "Related" widget and its Overview section could show *different* opportunities for the same company. Added the missing `id` field to both the V1 branch (`company_intelligence.py`) and the V2 branch (`opportunity_v2/read_service.py`) since the frontend keys list items on `item.id`.

2. **Real metadata/canonical/indexability for the Company detail page.** `[symbol]/page.tsx` gained a real `generateMetadata`: canonical URL built from C5's `canonical_symbol` (so a historical-alias request like `/companies/TELCO` reports the canonical `/companies/TMPV` URL even before the redirect fires), and `robots: {index: false}` only when the company doesn't qualify for a public page. Indexability is answered by a new cheap single-symbol classifier, `company_identity/tiers.py::classify_one()`, exposed at `GET /api/companies/{symbol}/tier`. This reuses C5's resolver + evidence checks (graph edges, AICompanySignals, V2 opportunity links) plus one bounded live-price check, rather than running the expensive batch classifier or fabricating a proxy signal.

3. **Removed fabricated/dead sections from `CompanyPageClient.tsx`** (2022 → ~1450 lines), per the redesign audit's KEEP/REMOVE/REPLACE table: `NetworkGraph` (fake reactflow star topology), `BusinessSegments`, `RevenueGeography`, `OrderBook`, `AIForecast`, the dead `EconomicCalendarSection` stub, `SimilarCompanies`, `Documents`, `AskAI`, and the fabricated donut/pill breakdown inside `GovernmentExposureSection` (the real `gov_score`/`gov_level` fields are kept elsewhere). Fixed in place rather than removed: `AISummary` (dropped an always-on fabricated risk line and an unbacked "Growth Drivers" list), `AISentiment` (dropped a fabricated weekly-trend chart and hardcoded 62/15% fallbacks, added an honest empty state), `PeerComparison` (dropped a fabricated growth column), `KeyRatios`/`FinancialHighlights`/`IntelligencePanel` (dropped dead buttons and fabricated Top Risks/Top Opportunities/Quick Actions/Export cards). Cleaned up the now-dead lucide icon imports, the `reactflow` package imports/CSS, the `GovBreakdownDonut`/`SentimentTrendChart` chart imports, and the unused `DONUT_C` color constant left behind by these removals.

## Verification (real data, not test-only)

- `tsc --noEmit`: clean, 0 errors.
- Backend suite (`test_company_identity.py`, `test_graph_migration_executor.py`, `test_company_qualification.py`, `test_company_tiers.py`): 37/37 pass.
- Live pass: safely copied the real dev DB (`sqlite3 .backup()`, never raw copy), re-ran the real C2 importer against it (2,557 NSE EQ entities, 492 old-symbol aliases, 4 provider aliases, 0 ISIN collisions), then booted backend+frontend against it and drove real requests:
  - `TELCO` → `308 Permanent Redirect` → `/companies/TMPV` (historical-alias redirect, live-verified end to end).
  - `RELIANCE` (Tier A via 18 graph relationships + 76 AICompanySignals + 2 V2 opportunities) → indexable, correct canonical link, correct title, no robots restriction.
  - `CEATLTD` (Tier A via V2-only evidence, no graph/AI signal) → indexable via the new tier endpoint. Its `related` opportunities widget correctly returns empty, because V2 is not promoted (`settings.opportunity_v2_promoted = False`) — the tier classifier deliberately looks at V2 shadow-pipeline evidence for indexability while the live-facing widget only serves what's actually promoted. Confirmed this is by-design divergence, not a regression.
  - `GOLDENTOBC` (Tier B, real live market data only) → indexable, correct canonical link, no robots restriction.
  - `WINSOME` (unresolved — not in current NSE EQ snapshot) → real Next.js 404, single real `noindex` robots tag in the actual `<head>` (confirmed by extracting the head section directly, since the raw response also contains serialized RSC flight-data strings that falsely double-count grep matches on the full body).
  - A true Tier C case (resolved, but neither real evidence nor live market data) did not turn up among ~20 additional real symbols sampled — most EQ-series entities have live yfinance data, so Tier C is genuinely rare in real current data. This is a real finding, not a gap in testing.

## Explicitly not done in this batch

No visual/navigation work — that starts with Batch 1 (shell/navigation: the Overview/Intelligence/Financials/Events/Opportunities/Ripple/Peers tab strip). No V2 promotion flag change. No Warehouse-adjacent code touched.
