# Current Intelligence Dedup + Company Rankings — Release Review Package

**Branch:** `marketripple-score/current-intelligence-dedup` (off `origin/main` @ `c84c28a`)
**Status:** Local only. Not pushed, not deployed. Public activation: 0%.
**Revision 5** (2026-09-26, later same day) — Revision 4 closed the
Intelligence/Opportunities-tab renames and flagged the Compare page's
fabricated "AI Score"/"AI winner" as a new, more severe, explicitly
NOT-yet-fixed finding (section 11). This revision closes it (section 12):
the fabricated scoring formula and every winner declaration built on it
are removed, replaced by the same real MarketRipple Score projection the
Company page reads, and the hardcoded 30-company selector is replaced by
the real backend directory. This closes every item raised in the owner's
one-score migration instructions across the Company page, Company
Rankings, and the Compare page.

## 1. Commits (20 total, chronological)

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
| 17 | `424b089` | Overview tab: delete the competing-rating fallback (`useCompanyRating`/`CurrentIntelligenceCard`) |
| 18 | `6d96fd2` | Intelligence tab: rename/strip `CompanyScoreContributors` ("AI Company Score" → "Recent Intelligence Evidence") |
| 19 | `0accb62` | Opportunities tab: rename/strip `OpportunityRadarSection` the same way, closing the sweep |
| 20 | `d18133c` | Compare page: replace the fabricated AI Score/winner with the real MarketRipple Score; real directory search |

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

## 9. Intelligence tab — `CompanyScoreContributors` competing rating removed

**Finding:** the Overview-tab fix (section 8) didn't close the gap — a different tab under a different name was still a second public company rating. `CompanyScoreContributors` (Intelligence tab, titled "AI Company Score") showed a standalone 36px score headline, an "AI Powered" badge, an "Evidence quality" gauge (`_evidenceLabel(risk_level)`), Risk/Trend colour pills, and a `verdict.reasoning` sentence that itself embedded the same score/risk as prose (e.g. "Opportunity score 62/100 · Medium risk"). Users landing on the Intelligence tab could see this number sitting alongside the canonical MarketRipple Score's own card.

**Fix (`6d96fd2`):** renamed to "Recent Intelligence Evidence"; removed all of the above. Kept the real, dated evidence columns (`ContributorRow`: reason text, source-type badge, formatted date, href link, and each row's own `signed_magnitude` — an individual evidence-item weight, not a company rating) untouched, plus one new factual sentence: the evidence feeds the MarketRipple Score's Current Intelligence pillar and is not itself a rating. The underlying calculation (`company_score_engine.py`) is untouched and keeps running internally as that pillar's real input. Exported `CompanyScoreContributors`/`CompanyScoreData`/`CompanyScoreContributor` for testability.

**Regression test** (`CompanyScoreContributors.test.tsx`, 3 new cases): full-content case asserts every removed element ("AI Company Score", the score number, "AI Score", "AI Powered", "Evidence quality", risk/trend text, verdict text) is absent and every real evidence string/date/source-type/contributing-signal-count line is present; empty-state case; pending-fetch case. All 3 pass.

**Real hydrated-browser verification** (this revision closes the caveat section 8 explicitly left open): installed `@playwright/test@^1.63.0` (version-matched to `release/ai-answer-v2`, reusing the globally-cached Chrome binaries at `C:\Users\Malini\AppData\Local\ms-playwright\` rather than downloading new ones), added `playwright.config.ts` + `e2e/one-score-company-page.spec.ts`. Started real local backend (port 8123) and frontend (port 3125) dev servers and confirmed via curl that `ICICIBANK` exercises both the Overview "Unavailable" state (`{"resolved":false}` from `/api/companies/ICICIBANK/marketripple-score`) and rich real Intelligence-tab evidence (`/api/company-scores/ICICIBANK`, score 52.8, 50 contributing signals) simultaneously. 2/2 real browser tests passed: Overview tab shows "Unavailable" and never the old fallback content; Intelligence tab shows "Recent Intelligence Evidence" with real evidence and never the old score/badge/pills/verdict. Both dev servers stopped after the run.

`tsc --noEmit`: no new errors; three pre-existing errors remain (`AISearchClient.test.tsx`, unrelated, unchanged). `vitest`: 389/389 pass (3 new).

## 10. Opportunities tab — `OpportunityRadarSection` competing rating removed (closes the sweep)

**Finding:** the owner's explicit full-sweep instruction ("the requirement applies across the entire Company page, not only components named individually") found one more live instance: `OpportunityRadarSection` (Opportunities tab, titled "AI Company Intelligence Score") read the *same* `/api/company-scores/{symbol}` endpoint as `CompanyScoreContributors` and showed the identical pattern — score headline, "AI Powered" badge, "Evidence quality" gauge.

**Fix (`0accb62`):** renamed to "Recent Intelligence Evidence" and stripped the same three elements, mirroring section 9 exactly. Kept the real per-signal evidence cards (reason, source-type badge, formatted date, href link, `signed_magnitude`) untouched — same distinction as `ContributorRow`. `RelatedOpportunitiesList`, rendered directly above this section on the same tab with its own real per-opportunity Opportunity Score badges (`o.score` from `/api/related/company/{symbol}`), is a separate, already-compliant concept and was correctly left untouched. Deleted `_evidenceLabel` entirely — this was its last remaining call site (its only other use, in `CompanyScoreContributors`, was already removed in section 9), so nothing was left orphaned. Exported `OpportunityRadarSection` for testability.

**Regression test** (`OpportunityRadarSection.test.tsx`, 2 new cases): asserts every removed element is absent and the real per-signal evidence, `signed_magnitude` values, contributing-signal count, and pillar-explanation sentence are present; empty-state (no signals) case. Both pass.

**Real hydrated-browser verification:** extended `e2e/one-score-company-page.spec.ts` with a third test covering the Opportunities tab. A stale frontend dev-server process left over from the section-9 verification round was found still holding port 3125 and serving pre-change code (confirmed via its actual OS process start time, well before this round's edits) — killed, then both servers were restarted clean. All 3 tests then passed against the fresh servers and real ICICIBANK data: Overview → "Unavailable"; Intelligence and Opportunities tabs → "Recent Intelligence Evidence" with real evidence, never the old score/badge/gauge, on all three tabs. Both dev servers stopped cleanly afterward.

`tsc --noEmit`: no new errors; three pre-existing errors remain (unrelated, unchanged). `vitest`: 391/391 pass (2 new).

## 11. Full sweep result — Company tabs and ranking surfaces

Per the owner's instruction, searched the whole Company page and every ranking surface for remaining competing company-score labels/components, not just the two named above:

- **Overview, Intelligence, Opportunities tabs** — closed (sections 8-10). Real hydrated-browser tests cover all three.
- **`IntelligencePanel`** (sticky sidebar, visible on every tab) — already clean; its own "AI Rating"/"AI Investment Rating" gauge was removed in Batch B (2026-08-25), confirmed by reading the code, not just the comment.
- **Company Rankings** (`/companies?tab=company-rankings`) — already compliant by construction: reads only `get_marketripple_score_projection()`, the same function the Company page itself calls.
- **`/best-stocks/[sector]`, `/sectors/[sector]`** — already fixed in commit `73028ff` (Banking reads the real MarketRipple Score; other sectors show no score at all).
- **`/best-stocks` (exact path, the old hub page)** — `BestStocksContent`/`RankingsView` still contain a live "AI Score" table column and hero number sourced from the retired `company_score_engine.py` ranking (`lib/bestStocks.ts`), but `next.config.ts` 301-redirects the exact `/best-stocks` path to `/companies?tab=company-rankings` — confirmed this makes the page unreachable in normal navigation, i.e. dead code, not a served competing surface. Not fixed (nothing user-visible to fix); flagged here only because it still exists on disk and would need deleting in a future cleanup pass, separate from this one-score effort.

**New finding, explicitly NOT fixed — flag for owner decision:** the Compare page (`/companies?tab=compare` and the `/compare` redirect, `CompareContent.tsx`) shows an "AI Score"/"AI winner" banner per compared company that is **not** the retired-but-real `company_score_engine.py` score — it's computed entirely client-side from a hardcoded formula (`let s = 50; s += roe*0.8; s += (30-pe)*0.5; s -= debt_to_equity*5; ...`, clamped 10-99) over a hardcoded 30-company registry, with no backend call at all. This is a different, more severe class of problem than the two closed above: not a second *real* rating living under a competing label, but an outright fabricated number with zero backend provenance — the same category of finding as the Company Pages Audit's worst fabrication case earlier this engagement. The fix isn't a like-for-like rename/strip: an "AI winner" banner, a "Best Future Potential" ranking, and a per-company score ring all depend on this fabricated formula, so removing it changes the page's UX meaningfully and needs the owner's steer on what (if anything) replaces it. Not touched in this round.

## 12. Compare page — fabricated AI Score/winner replaced with the real MarketRipple Score (closes section 11's flagged finding)

**Owner decision (this round):** fix it within the same migration. Confirmed first, per the owner's explicit instruction, that "a formula calculated in the browser is not automatically fabricated" — checked whether the underlying inputs were hardcoded samples or real sourced values. They're real: `GET /api/stocks/{symbol}` is backed by yfinance/Finnhub, confirmed live for both a bank (ICICIBANK) and a non-bank (TCS) symbol. The fabrication was specifically the scoring formula and the winner declarations built on top of those real inputs — not the inputs themselves.

**Removed:** the `aiScores` formula (`s = 50 + f(roe, pe, debt_to_equity, gross_margins, dividend_yield)`, clamped 10-99, no backend call); the "AI Comparison Summary" card's winner-declaring paragraph; "Best Future Potential" (no validated predictive metric exists to replace it with, per the owner's instruction); the entire "AI Recommended Pick" / "Winner summary" banner on the AI Analysis tab; the hardcoded 30-company `COMPANY_LIST`.

**Replaced with, following the owner's replacement table exactly:**
- *"AI Score" → the canonical MarketRipple Score projection, or its honest unavailable/partial state.* New `MrScoreTile` reads the same `GET /api/companies/{symbol}/marketripple-score` endpoint the Company page's own `MarketRippleScoreCard` reads — real score, "Partial coverage", or "Unavailable", never a fabricated fallback. Used on both the Valuation tab (renamed "Score Comparison" → "MarketRipple Score") and the AI Analysis tab. Deliberately never highlights or ranks the tiles against each other, even when every compared company is fully eligible — no declared winner, per the owner's explicit "do not declare an overall winner."
- *"AI winner" banner → neutral heading.* "AI Comparison Summary" → "Comparison Summary"; kept "Highest ROE" and "Lowest Beta" (transparent single-real-metric superlatives, not composite AI verdicts).
- *"Best Future Potential" → removed.*
- *Financial comparison rows → real metrics only, with reporting periods and units.* Found and fixed a real, previously-undiscovered bug while verifying the underlying data: `/api/stocks/{symbol}` has never actually returned top-level `revenue`/`profit` fields (confirmed live for both test symbols) — this component was reading fields that don't exist, so "Revenue"/"Net Profit" rows always rendered "—" for every company, in both the "Financial Highlights" table and the per-company Financials tab. The real figures were already being fetched into the same object as `annual_financials`; now derives the latest fiscal year from there instead. Every comparison row across Overview, Valuation, Profitability, Balance Sheet, Dividends, and AI Analysis now states its real period and unit inline (e.g. "ROE (%, TTM)", "P/E Ratio (TTM, x)", "Revenue (₹ Cr, Latest FY)") instead of one blanket, partly-inaccurate "(TTM)" card label.
- *Hardcoded company selector → the real directory.* "Add Company" now calls `GET /api/companies/search`, the same real, metadata-only backend directory `AllCompaniesTab.tsx` already uses for `/companies` — replacing a hardcoded list that could only ever find 30 of the real ~500+ company universe (the same class of drift this app's `/companies` page itself was fixed for once before).

**Regression test** (`CompareContent.test.tsx`, 3 new cases): a real populated score (72) and a real "Partial coverage" state side by side, with the revenue/profit fix and the neutral "Comparison Summary" confirmed, and every removed element ("AI Score", "AI Powered", "AI Recommended Pick", "Best Future Potential", "Scores highest...", "Score Comparison") asserted absent across the Valuation and AI Analysis tabs; a real "Unavailable" state; the real company-directory search (asserts the actual network call to `/api/companies/search`, and that a company only findable there gets added — not just present in a hardcoded list). All 3 pass.

**Real hydrated-browser verification, with an honest data-availability caveat:** confirmed live, before writing the browser test, that the local dev DB currently has **zero real MarketRipple Score snapshots for any company** — every one of 10 real Banking symbols queried returns `{"resolved":false}`, and `GET /api/company-rankings/Banking` itself returns `ranked:[]` and `partial_coverage:[]` for the whole sector. This is the same standing "local zero-snapshot findings establish nothing about production" gap already tracked elsewhere in this engagement (section 5), not something specific to the Compare page — and not something to paper over by hand-writing a snapshot row into the dev DB, which would just be fabricating test data under a different name. The populated/partial states are therefore verified via `CompareContent.test.tsx`'s fixtures (same precedent as `MarketRippleScoreCard.test.tsx` and `CompanyScoreContributors.test.tsx` earlier this session, for the same reason). The real browser check (2 new Playwright tests, `e2e/compare-one-score.spec.ts`) covers what real local data actually supports: the honest "Unavailable" state on two real companies (ICICIBANK, TCS), real financial data rendering, the real directory search (finds "Infosys" via a real `/api/companies/search` network request, asserted directly), and — the core of this fix — confirms no fabricated score or winner element survives real hydration anywhere on the page. All 5 Playwright tests pass together (this page's 2 plus the existing Company page suite's 3). Both dev servers stopped after the run.

`tsc --noEmit`: no new errors; three pre-existing errors remain (unrelated, unchanged). `vitest`: 394/394 pass (3 new).

## Held per instruction

Lineage backfill execution and public activation (`publishable` flip) remain held pending review sign-off. Production snapshot history and coverage remain unknown — no new read attempt was made this round. Every one-score finding raised across the Company page, Company Rankings, and the Compare page is now closed; the only remaining loose end from the sweep (section 11) is the dead, unreachable `/best-stocks` hub page code, flagged but not fixed as it serves nothing live.
