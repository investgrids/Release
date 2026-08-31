# Company Redesign — Batch 2: Overview + Intelligence Content

Date: 2026-08-25
Branch: `company-identity/c1-reconciliation` (worktree `D:\ig-company-identity`), commit `d3e870c`
Scope: compact Overview per the redesign's own target mockup; Intelligence tab gets real Company Score contributors (including real negative ones) instead of the fabricated Top Risks/Top Opportunities removed in Batch 0.

## What shipped

- **`OverviewGrid`** — six real, independently-hiding cells at the top of the Overview tab, matching the redesign's own target mockup shape: Key Market Data (day/52W range, volume), Financial Snapshot (P/E, ROE, D/E, margin), Latest Development (most recent real news headline — plain text, never a clickable link, since the source is third-party and this repo's standing rule is no external links; matches `NewsImpact`'s own existing attribution style), Latest Material Event (most recent real event, linked to its real `/events/{slug}` page), Current Opportunity (the top real opportunity from the now-unified Batch 0 `/api/related/company/{symbol}` contract), and Key Intelligence (the single strongest real positive signal + real counter-signal, from the new company-score fetch below). Every cell hides itself independently when its real data is missing — nothing is padded to fill the grid.
- **Moved `CompanyIntelligenceSection`** from Overview to Intelligence. Its content (Why This Company Matters Today, Active Intelligence, Ripple Position, Confidence Breakdown, Investment Watch, Historical Intelligence, Related Opportunities) is real but deep — a research-question surface, not a quick-glance one — so it fits the Intelligence tab's job better than the now-compact Overview.
- **New `CompanyScoreContributors`**, at the top of the Intelligence tab. Fetches the same, already-live `GET /api/company-scores/{symbol}` (`company_score_engine.py`) that `OpportunityRadarSection` (Opportunities tab, untouched — its own redesign is Batch 3's job) already calls, but renders fields the API already returned and no UI ever used: `positive_reasons`/`risk_factors`, the same weighted signals as `top_contributors` just pre-split by sign. Rendered as two columns — **Real Supporting Evidence** (green, "EVIDENCE" badge) and **Real Counter-Signals** (rose, "COUNTER-SIGNAL" badge) — each card showing its real reason, real signed magnitude, real source type (opportunity tracking vs published analysis), and real date. Score/confidence/risk-level/trend/verdict header reuses the same real fields `OpportunityRadarSection` already surfaced. Honest empty state — "No AI Company Score evidence tracked... this score is built only from real published analysis and opportunity tracking, never estimated" — when a company has zero `AICompanySignal` rows (`score: null`), never a manufactured 0.

## Real residual finding (not fixed in this batch, flagged for later)

The sidebar's `IntelligencePanel` "AI Rating" (e.g. 58/100, derived from `stock.dna_scores`) and the new Intelligence tab's "AI Company Score" (e.g. 53.8, from `company_score_engine.py`'s `AICompanySignal` evidence) are two different real scores, computed from two different real data sources, shown on the same page with no label distinguishing what each one means or why they differ. Both are real and honest individually, but next to each other with near-identical names this reads as confusing/inconsistent to a real user. Not fixed here — flagged for a later consistency pass (naming or a short explanatory label), since resolving it well may mean deciding which score is canonical for the sidebar rather than a quick label tweak.

## Verification (real data, real browser)

- `tsc --noEmit`: clean, 0 errors.
- Real Playwright pass against a live backend+frontend:
  - RELIANCE (76 real `AICompanySignal` rows): all 6 Overview cells render with real data (verified via screenshot — Day range ₹1,300.00–₹1,306.10, 52W ₹1,249.80–₹1,611.80, P/E 23.7, Current Opportunity "Defence Investment Opportunity" score 98, Key Intelligence showing one real positive + one real negative line). Intelligence tab renders the real 53.8 score, 78% confidence, Medium Risk, and 5 real EVIDENCE cards (+82, +89, +87, +97, +72) alongside 5 real COUNTER-SIGNAL cards (-60 ×3 with distinct real reasons about crude-oil exposure), each with real dates and real source attribution.
  - GOLDENTOBC (Tier B, zero `AICompanySignal` evidence, confirmed via direct `/api/company-scores/GOLDENTOBC` → `score: null, signal_count: 0`): Intelligence tab renders the honest empty-evidence message instead of a blank or fabricated section.

## Explicitly not done in this batch

Opportunities tab still shows the pre-existing `OpportunityRadarSection` (mixed positive/negative `top_contributors`, not the real split) — deliberately left untouched since Batch 3 is the batch that redesigns Opportunities around the canonical V2 relationship contract; touching it now would be work Batch 3 immediately redoes. No Financials/Events/Peers content changes (Batch 3/4). No fix for the two-different-AI-scores finding above.
