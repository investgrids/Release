# Current Intelligence Dedup + Company Rankings — Release Review Package

**Branch:** `marketripple-score/current-intelligence-dedup` (off `origin/main` @ `c84c28a`)
**Status:** Local only. Not pushed, not deployed. Public activation: 0%.
**Revision 3** (2026-09-26, later same day) — Revision 2 rewrote section 3
after the public-content freeze widened and added sections 6-7 (Company
Rankings, remaining surfaces). This revision adds section 8: the Company
page's own competing-rating fallback (`CurrentIntelligenceCard`/
`useCompanyRating`) is now deleted, closing the last one-score gap.

## 1. Commits (19 total, chronological)

| # | Hash | Summary |
|---|---|---|
| 1 | `d2048c3` | Dedupe signals by real event lineage; retire unvalidated COMPLETE threshold |
| 2 | `beeb0cf` | Withhold headline score below 4-of-4 pillar coverage; synthetic shadow comparability |
| 3 | `84a2c28` | Per-metric provenance instead of one pillar-wide freshness claim |
| 4 | `d77c913` | Persist/surface partial-coverage state; Company page UI |
| 5 | `5a22752` | Prove public-row orchestration behavior (original, buggy state); event_id backfill v1 |
| 6 | `d528170` | Real component tests for MarketRipple Score comparability states |
| 7 | `e704e82` | Real-data (5-bank) pillar comparability run |
| 8 | `aed784e` | *(cherry-pick)* declare `sqlalchemy[asyncio]` explicitly |
| 9 | `25ae90a` | *(cherry-pick)* exclude secrets from Docker build context, disable dotenv fallback in production |
| 10 | `9a0cb48` | Freeze public-row score/signal fields (narrower, first version); dry-run backfill reporting |
| 11 | `d1bc50d` | Financial Strength metric-coverage gap investigation |
| 12 | `092f977` | Tighten comparability scope; full-path public-row field survey (still narrower freeze) |
| 13 | `22b3d82` | **Widen public-row freeze** to cover narrative content and Development linkage |
| 14 | `3e8bedb` | Company Rankings backend endpoint (`get_banking_rankings`) |
| 15 | `5c9a196` | Company Rankings frontend (Best Stocks retired, tab renamed) |
| 16 | `73028ff` | Remaining surfaces: `/best-stocks/[sector]`, Overview widgets, `/sectors/[sector]`, fixture tests |

**Grouped diff since revision 1** (+7 files touched, +9 new tests):
- `orchestration.py`: `_process_cluster()` now returns early on any matched public row — no score write, no linkage, no narrative regen, no slug touch.
- New: `rankings.py`, `company_rankings.py` (API), `lib/companyRankings.ts`, `app/company-rankings/*`.
- Rewritten: `best-stocks/[sector]/page.tsx`, `sectors/[sector]/page.tsx`, `OverviewTab.tsx`, `sitemap.xml/route.ts`, `next.config.ts`.

## 2. Test totals

**Authoritative full-suite number** (branch HEAD @ `73028ff`, final confirmation run): **28 failed, 2130 passed, 2 skipped, 2 xfailed** (384.95s). Identical failure list — same 28 tests, by name — across all 4 full-suite runs taken this session (369.8s/371.7s/352.4s/384.95s); only the passed count grows as new tests are added (2116 → 2120 → 2129 → 2130).

**Parent-baseline comparison** (unchanged from revision 1, still holds): the 2 non-live-network extra failures (`test_opportunity_v2_batch_e_consumers.py`) were reproduced on a clean `origin/main` checkout with zero application-code changes — confirmed pre-existing, not a regression from this branch.

## 3. Public-content freeze — end-to-end result (REVISED, widened scope)

**The freeze now covers the entire `run_shadow_pass()` outcome for a matched public row, not just score/signal fields.** Tracing `read_service.py`'s real consumers found two more real exposure paths the narrower version (commit `9a0cb48`) missed:
- `title`/`why_this_exists` fall back to `current_title`/`current_summary` whenever no `editorial_title`/`editorial_summary` is set — a real, valid public-row state (promotion doesn't require an override).
- `evidence_count`/`supporting_evidence`/`ripple`/`development_impacts` are all built live from current Development linkage, which grew unconditionally.

**Fix (`22b3d82`):** `_process_cluster()` returns early the instant it matches an already-public row — no score write, no new Development linkage, no narrative regeneration, no slug touch. Logs `opportunity_v2.orchestration.public_row_frozen` with what would have happened.

**Verification, both at the ORM level and through the real public read path:**
- `test_opportunity_v2_orchestration_public_row_field_survey.py::test_full_field_survey_including_the_real_public_read_path_for_a_row_without_editorial_override` — **PASS**. The harder, more exposed case (a public row with NO editorial override). Calls the real `get_opportunity_v2_detail()` before and after a real reprocess with new evidence available, asserting byte-identical: `title`, `why_this_exists`, `current_strength`, `evidence_count`, `supporting_evidence` (dev IDs), `ripple` (node/edge IDs), `development_impacts`, `companies_connected`, `sectors_themes`, `contradictions_risks`, `updated_at`. Also confirms at the ORM level that `generate_narrative` is never even called for a frozen row (call-count assertion, not just output comparison).
- `test_opportunity_v2_orchestration_public_row_field_survey.py::test_shadow_row_still_updates_everything_normally` — **PASS** (control). An ordinary shadow row keeps updating score, narrative, and linkage exactly as before.
- `test_opportunity_v2_orchestration_public_row_scoring.py` — both tests updated to assert the widened behavior (Development linkage no longer happens for a frozen row either) rather than the old, now-incorrect expectation.

129/129 `opportunity_v2` tests pass with the widened freeze in place.

## 4. Backfill dry-run — counts, conflict handling, idempotency, rollback

Unchanged from revision 1: `backfill_company_signal_event_ids(db, dry_run=True)` reports `candidates`/`resolvable`/`unresolved_no_real_lineage`/`symbols_with_new_conflicting_groups`. Local dev DB dry-run: 1734 signals, 1398 resolvable, 128 duplicate-event groups, 15 conflicting. 5 tests pass. Idempotent. Rollback: targeted `UPDATE ... SET event_id = NULL` on just the values a real run wrote — not yet needed, script remains unexecuted against production.

## 5. Production snapshot / FinancialFact coverage

**Still blocked and still unknown**, unchanged from revision 1. Local zero-snapshot/zero-`financial_facts` findings establish nothing about production's real state.

## 6. Company Rankings — the one-score migration

**Backend** (`rankings.py`, `company_rankings.py`): `GET /api/company-rankings/{sector}`. Banking reads `get_marketripple_score_projection()` per symbol — the exact function the Company page already calls, so score/rating/coverage/timestamp match by construction. Categorizes every real bank into `ranked` / `partial_coverage` / `unavailable` (with real reason: no snapshot, publication-locked, ineligible, or stale — 30-day threshold explicitly flagged provisional/unvalidated). Non-Banking sectors get an honest "not yet available" response, never an empty list dressed as complete.

**Frontend**: "Best Stocks" retired as a brand — tab renamed to "Company Rankings" across the hub, nav, footer, breadcrumbs, with 301 redirects preserved (`/best-stocks`, `/company-rankings` both → `/companies?tab=company-rankings`).

**Remaining surfaces closed this round:**
- `/best-stocks/[sector]`: Banking redirects (301) to the canonical page. Every other sector shows an honest "not yet available" notice plus the real, fully browsable company list for that sector — no score, no fallback to the retired engine.
- Overview "AI Top Picks" → "MarketRipple Top Picks": reads the same approved projections; honest empty state verified live ("No banks have a published MarketRipple Score yet").
- Overview "Companies Under Pressure": **removed outright**, not re-implemented on the new score — a low composite (old or new) was never a real signal of selling pressure.
- `/sectors/[sector]`: Banking constituents now rank by the real MarketRipple Score; every other sector reverts to price/change only (no score at all), matching the page's own pre-existing honest fallback for signal-less stocks.
- Reviewed and intentionally **not** changed: Overview "Trending Companies" (shows a recency reason, never a score — not a competing rating); `CompanyPageClient.tsx`'s `useCompanyRating`/`CurrentIntelligenceCard` (the already-disambiguated, 2026-08-25-decided "Current Intelligence" surface — a genuinely different concept, out of scope for a ranking-specific migration).

**Fixture coverage (this round's explicit ask, not just the live empty-state check):**
- Backend: `test_marketripple_score_rankings.py` — 9 tests covering populated/partial/stale/ineligible/locked/unsupported-sector states via `MarketRippleScoreSnapshot` fixtures, plus `test_ranked_row_matches_the_same_symbol_s_company_page_projection_exactly` — a regression guard proving a ranking row and `get_marketripple_score_projection()` agree on score/rating/coverage/timestamp for the same symbol.
- Frontend: `CompanyRankingsView.test.tsx` — 4 tests, local fixtures for all 4 states (populated table, partial coverage, stale/ineligible in the collapsible unavailable section, unsupported sector).

**End-to-end dev-server verification** (both rounds, real backend + real frontend, real local DB, servers stopped after each check): `/api/company-rankings/Banking` returns 200 with real data; `/companies?tab=company-rankings`, `/best-stocks/technology` (200, honest unavailable + real company list), `/best-stocks/banking` (308 → Company Rankings), `/sectors/banking` (200, no stale score badges), `/companies?tab=overview` (200, new widget + confirmed absence of "Companies Under Pressure") — all verified, no server errors in either log.

## 7. Compile/test totals, revision 2 round

`tsc --noEmit`: 0 new errors (3 pre-existing, unrelated `AISearchClient.test.tsx` errors persist unchanged). `vitest`: 384/384 pass (9 new this round). Backend `test_marketripple_score_rankings.py`: 9/9 pass.

## 8. Company page — competing rating fallback removed (closes the one-score gap)

**Finding:** `MarketRippleScoreSection` (Overview tab) still fell back to `CurrentIntelligenceCard` — the older single-engine score, verdict, and reasons — whenever MarketRipple Score had no snapshot for a company (unsupported sector, or not yet computed). This was a real second public company rating, not just an internal detail: the August 2026 decision that gave the older score its own "Current Intelligence" identity never authorized it a *fallback* slot for the canonical score's own card.

**Fix:** `useCompanyRating()` and `CurrentIntelligenceCard` deleted entirely from `CompanyPageClient.tsx` (each was the other's only call site — no orphaned code left behind). `MarketRippleScoreSection` now always renders `MarketRippleScoreCard`, in whichever real state the projection is in — including "no snapshot at all," which the card's existing `!eligible` branch already renders correctly as "Unavailable" with no code change needed there. The older engine's real calculation is untouched and still runs internally (Current Intelligence pillar input) and still has its own, separately-labeled, different-tab home (`CompanyScoreContributors`, "AI Company Score" on the Intelligence tab) — that surface was not named in scope and was left alone.

**Renamed**: Overview's "AI Top Picks" → "Highest MarketRipple Scores" ("Top Picks" implied a recommendation this score has never been validated to make).

**Regression test** (`MarketRippleScoreCard.test.tsx`, 2 new cases): both the `{resolved:true,snapshot:false}` and raw `{resolved:false}` shapes render the honest "Unavailable" state and never the old engine's title/text/score — verified by asserting the old component's exact strings ("Current Intelligence", "Insufficient evidence for a current-intelligence view...") are absent alongside asserting the new honest state is present.

**Verification caveat, stated plainly**: full client-hydrated browser verification wasn't possible in this environment (no Playwright browser installed here) — the score card fetches client-side via `useEffect`, so a plain `curl` of the SSR HTML cannot show its post-hydration state either way. Verified instead via: (1) component tests rendering the exact real API response shapes directly, and (2) confirming live against the real backend that `{"resolved":false}` is indeed what `/api/companies/{symbol}/marketripple-score` returns for the local test symbols, and that the Company page itself loads 200 with the new code path live.

`tsc --noEmit`: 0 new errors. `vitest`: 386/386 pass (2 new).

## Held per instruction

Lineage backfill execution and public activation (`publishable` flip) remain held pending review sign-off.
