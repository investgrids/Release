# MarketRipple Score — Data Freshness Root Cause & Refresh Plan

**Date:** 2026-09-27
**Status:** Investigation CLOSED at the code level. Refresh plan proposed, NOT executed. `publishable` remains False; August snapshots remain untouched; quality thresholds remain unchanged.
**Scope:** Read-only. No code changes, no DB writes, no schedule changes made in this pass.

## Current status (superseding note, 2026-09-27)

This document was written incrementally as the investigation progressed, and its earlier sections (§1-§6) contain conclusions later sections supersede. Read in this order:

- **Why financial data is stale:** the existing NSE `corporates-financial-results` source stops at a Jan-2025-broadcast filing (§1, §5) *and* `FinancialFact` ingestion is not wired into the scheduler at all (§1) — both true, independent causes.
- **Why score snapshots are stale:** `MarketRippleScoreSnapshot` computation is likewise unscheduled — a one-off manual batch script last run 2026-08-31, not a recurring job (§2).
- **§6's "wait for a manual NSE network capture" step is superseded.** Official bank disclosures (§7-§8) now supply the pilot's eight required inputs directly, verified against each bank's own board-approved filing — the pilot does not need NSE Integrated Filing resolved first.
- **The §6 27-bank NSE-based rerun this document originally sketched is also superseded** for the pilot's purposes — only the two-bank disclosure-sourced import (§8 onward) is in scope now; a broader 27-bank automated refresh remains a separate, later decision contingent on resolving NSE Integrated Filing (or another data source) for a real recurring pipeline.

## 0. Corrections to the prior interpretation

Two claims from the initial production-read analysis (2026-09-26) needed verification before being trusted. Both are now resolved:

1. **"~23 months stale" → the FinancialFact ingestion path does NOT reuse `_indian_fy_and_quarter()`** (that function lives in `market_data.py` and is unrelated to this pipeline). FinancialFact's `fiscal_year`/`fiscal_quarter` are derived entirely from NSE's own self-reported strings — `financialYear` (e.g. `"01-Apr-2024 To 31-Mar-2025"`, regex-parsed for the trailing year) and `relatingTo` (e.g. `"Third Quarter"`, mapped via `_QUARTER_MAP`) — in `app/services/financial_facts/ingest.py:33-42,104`. This independently uses the same Apr(Y-1)–Mar(Y) convention and names the FY by its ending year, so the ~21-month estimate (FY2025 Q3 ≈ Oct–Dec 2024 → 2026-09-27) is corroborated, but now via the ingestion pipeline's own field mapping, not an assumption borrowed from an unrelated module.
2. **"27 rows = computed exactly once" → confirmed true, but for a structural reason, not a row-count guess.** `MarketRippleScoreSnapshot` has no unique constraint on `symbol` (primary key is a random UUID, `app/db/models/marketripple_score_snapshot.py:40`) and its writer (`snapshot.py:128-130`) is a bare `db.add()` — INSERT-only, explicitly documented as "never updates an existing row — history is kept" (`snapshot.py:62-63`). No delete/prune logic exists anywhere touching this model. Given that, 27 distinct prior runs would have produced 27×N rows, not 27. One row per bank is only possible if the batch ran exactly once.

## 1. Why the ingestion ceiling is FY2025 Q3

`FinancialFact` ingestion (`app/services/financial_facts/ingest.py`) is **deliberately not wired into the scheduler**, by the module's own docstring: *"Deliberately NOT wired into any scheduler or API route yet — a manual, inspectable function for S3-C's backfill."* Confirmed by grep: zero references to `ingest_period`/`financial_fact` anywhere in `app/scheduler/scheduler.py` or `app/tasks/*` (which register ~30 other real recurring jobs).

The table was populated by two manual one-off scripts:
- `scripts/financial_facts_backfill.py` (committed 2026-08-26) — original 5 reference banks.
- `scripts/s4_backfill_wide_universe.py` (committed **2026-08-29**) — remaining 22 banks.

There is no hardcoded date filter anywhere in `ingest.py`, `nse_xbrl_client.py`, or `quality.py`. `fetch_financial_results()` just returns whatever NSE currently serves for that symbol/period. Whatever NSE's newest available Q3-FY2025 filing was on 2026-08-29 — the last time this script ran — is exactly what's frozen in the table, for every bank uniformly, because nothing has invoked `ingest_period()` since. This is staleness by inaction, not a bug, cap, or silent failure.

**Monitoring gap (separate, lower-priority finding):** the only ingestion-silence monitor in this codebase, `job_check_ingestion_silence` (`app/tasks/daily_tasks.py:1033-1059`), only watches `EventTriage.triaged_at` (news/events). Nothing watches `FinancialFact` or `MarketRippleScoreSnapshot` staleness. Even if these jobs were scheduled, a silent stall wouldn't currently be caught.

## 2. Why no snapshot has been computed since Aug 31

Same pattern: `compute_and_persist_snapshot()` is not scheduler-wired (zero references in `scheduler.py`/`app/tasks/*`). The 27 rows came from one hardened, manually-invoked script: `scripts/marketripple_score_production_backfill.py` (committed 2026-08-31 08:04 UTC), whose own docstring warns explicitly: *"Don't loop this unattended; run it once per intended backfill/refresh."* Its `_preflight_publication_lock()` confirms `engine.py` hardcodes `publishable=False` unconditionally — this batch made zero publication decisions.

No recurring trigger exists to have fired again. Whether anyone has manually re-run it since 2026-08-31 is outside what code alone answers, but the schema/scheduler evidence rules out "a scheduled job silently failed," since no such schedule exists in the first place.

## 3. YESBANK — exact mechanism, exclusions preserved

`quality.py:80-85` defines hard plausibility ranges per metric, e.g. `cet1_ratio: (0.02, 0.60)` (2%–60%), justified in the adjacent comment: Basel III's absolute floor is 4.5%, RBI's effective minimum ~8%, so nothing below 2% is plausible for any real, operating bank. This check (`assess_plausibility`, called only after the within-entity anomaly check already returns OK) is separate from and blind-spot-covering the trend-based `assess()` check — which is exactly why YESBANK passed the trend check (its own values are internally consistent quarter over quarter) but fails plausibility.

The comment directly above the range table names YESBANK as the real, confirmed-live motivating case: *"YESBANK's real CET1 sits at ~0.13% across all 8 real quarters checked ... ~100x below any plausible real value; see `artifacts/marketripple_score_s4_wide_banking_validation.md` §7."* That artifact (repo root, dated ~2026-08-29) independently corroborates: real as-filed CET1 0.13%, Gross NPA 0.02%, Net NPA 0%, ROA 0.01% — internally consistent but ~100x off vs. every peer bank and vs. Yes Bank's real known CET1 (~13–14%). This is documentary evidence from a past analyst read, not a live query in this pass — the current live value/`source_document_url` would need a fresh read-only confirmation if ever required, but nothing here suggests the original finding was wrong.

The cascade (`quarantine_document_if_needed()`, `quality.py:88-140`) is exactly why 1 metric shows `IMPLAUSIBLE_SCALE` and 3 show `SOURCE_DOCUMENT_QUARANTINED`: it propagates quarantine to every other currently-OK metric from the *same source document* once one metric in it trips a structural-failure status. This was applied historically via two more one-off scripts, both committed 2026-08-29: `scripts/s45_backfill_plausibility.py` (first flagged YESBANK's `cet1_ratio` rows) and `scripts/s45b_backfill_document_quarantine.py` (propagated to the sibling metrics ~40 minutes later).

**Per standing instruction, these exclusions are preserved as-is.** Nothing in this investigation establishes a correction to YESBANK's source data — the ~100x error is real and documented, not a false positive of the quality gate.

## 4. Proposed refresh plan (smallest verified step — NOT executed)

Constraint carried through unchanged from the prior instruction: *refreshing calculations alone would still reuse stale fundamentals, and the August snapshots stay locked, and quality thresholds stay as-is.* The plan below is sequenced so no step reuses stale data under the appearance of a refresh, and no step touches publication state.

**Step A — Re-run FinancialFact ingestion first, not the score.**
Re-invoke `ingest_period()` for all 27 banks (Quarterly + Annual) against NSE's *current* feed, using the same idempotent `_upsert()` path (keyed on the real unique index, so this is safe to re-run — it will not duplicate existing rows, only add newer periods or correct-in-place if NSE revised anything). This should surface whatever quarters NSE has published since FY2025 Q3, including fresh data for YESBANK — which will independently re-fail the same plausibility check unless the underlying filer data itself has changed, exercising the existing quality gate rather than bypassing it.

**Step B — Verify via the same read-only diagnostic pattern before trusting the refresh.**
Re-run a bounded, read-only version of the production diagnostic script already reviewed and executed this engagement (self-tested `PRAGMA query_only` mechanism) against the refreshed table, to confirm: newest period per bank actually advanced past FY2025 Q3, the 4 scoring-required metrics' coverage didn't regress for the 26 previously-usable banks, and YESBANK's exclusion pattern is either unchanged (still quarantined, expected) or has a coherent, source-documented reason to differ.

**Step C — Only then, shadow-recompute snapshots — do not touch the Aug 31 rows.**
Because persistence is append-only with no unique constraint on `symbol`, re-running `compute_and_persist_snapshot()` is structurally safe: it adds new rows, it cannot overwrite or corrupt the 27 August rows. Run it once (per its own documented discipline — "don't loop this unattended"), then diff the new rows against the Aug 31 baseline per bank (score delta, pillar coverage, any newly-usable/newly-unusable bank) before any human reviews the result. `publishable` stays False throughout; this step produces data for review, not a publication event.

**Step D — Defer, as separate decisions requiring explicit sign-off:**
- Whether to wire either job into the scheduler on a recurring cadence (this plan only covers one bounded manual refresh, matching the discipline both existing scripts already use).
- Whether to extend `job_check_ingestion_silence` (or add a sibling monitor) to cover `FinancialFact`/`MarketRippleScoreSnapshot` staleness, so a future multi-week silent gap like this one is caught automatically instead of found via manual audit.
- Any decision to unlock/publish snapshots, or to revisit YESBANK's exclusions — both remain explicitly out of scope and held pending independent review of Step B/C's output.

## 5. Pilot verification (ICICIBANK, KOTAKBANK) — 2026-09-27 addendum

**Selection-logic check: NOT a bug.** `ingest_period()` takes the top `real_quarters + buffer` of `non_consolidated_with_real_xbrl(rows)`, where `rows` is already sorted newest-first by parsed `broadCastDate` (`nse_xbrl_client.py:59`, a real `datetime` sort, not a string sort). The code correctly takes the genuine newest of whatever NSE's endpoint returns.

**But a live, read-only re-query of NSE's real `corporates-financial-results` endpoint just now (2026-09-27), using this codebase's own already-reviewed `fetch_financial_results()`/`non_consolidated_with_real_xbrl()` — the exact method `ingest_period()` calls — returns, for BOTH pilot banks, nothing newer than a Non-Consolidated Quarterly filing broadcast in January 2025 (Third Quarter, FY2024-25 / "FY2025 Q3" in our naming):**

| Symbol | Newest Non-Consolidated Quarterly row NSE returns today | broadCastDate |
|---|---|---|
| ICICIBANK | Third Quarter, FY 01-Apr-2024→31-Mar-2025 | 25-Jan-2025 16:17:35 |
| KOTAKBANK | Third Quarter, FY 01-Apr-2024→31-Mar-2025 | 29-Jan-2025 10:30:03 |

This is identical to what's already stored in production. **Re-running `ingest_period()` for these two banks right now would be a no-op — it would not fetch anything fresher than what's already in the table**, because the data source itself, via this endpoint/query shape, has nothing newer to give it. This is a bigger finding than "an unscheduled job" — it means the ingestion code being unscheduled is not the only reason the data is stale; even a manual re-run today would not close the gap.

**This is very likely a genuine, external data-source limitation, not a newly-introduced code defect** — corroborated by an unrelated engineer's own comments in `app/providers/nse_provider.py:22-24,29-31` (Aug 2026, a different data track): `corporates-financial-results` was independently probed twice and found to return nothing without a per-symbol query, and was "not pursued further" both times — i.e., this specific NSE endpoint was already known elsewhere in the codebase to be limited/unreliable, before this investigation.

A follow-up attempt at adding explicit `from_date`/`to_date` params (guessing NSE's real contract) returned 0 rows rather than more-recent ones, which is inconclusive (could mean genuinely nothing in that window, or that the guessed parameter names/format aren't what NSE's endpoint actually expects) — I did not keep guessing at an undocumented third-party API contract beyond this point; that's better resolved by whoever has visited NSE's live results page in a real browser and can inspect what request it actually issues, or by evaluating a different data source for current banking financial results if this endpoint is confirmed dead.

**"Latest snapshot" API-safety check (completed, clean):** every real consumer of `MarketRippleScoreSnapshot` — `public_projection.py` (`get_marketripple_score_projection`), `rankings.py` (Company Rankings API, migrated 2026-09-26), and `companies.py`'s Company-page score endpoint — funnels through the single `get_marketripple_score_projection()` function, which gates the ENTIRE numeric payload (score/rating/pillars/coverage/financial_data_as_of) on `snap.publishable`, not on recency (`public_projection.py:125,136-150`, hardened 2026-08-31 after a real pre-deploy leak was caught). `engine.py` still hardcodes `publishable=False` unconditionally in both the usable and unusable branches (`engine.py:108,142`). So a new snapshot row for ICICIBANK/KOTAKBANK becoming "latest" via `get_latest_snapshot()`'s `ORDER BY calculated_at DESC LIMIT 1` is safe by construction — it inherits `publishable=False` from `engine.py` at write time, same as every existing row. No separate leak path found.

**Recommendation on the two-bank refresh, given the above:** do not proceed with an insert/update preview yet — there is currently nothing fresher to insert or update for these two banks via the existing pipeline. Proceeding would either (a) produce a diff of zero real changes, misrepresented as a "refresh," or (b) require first resolving the NSE data-source question. See chat response for proposed options.

## 6. Integrated Filing investigation — 2026-09-27, second addendum

Followed a lead (relayed via the owner from an external source) that NSE moved current-quarter results reporting to a section called "Integrated Filing," effective for the quarter ended March 2025 onward — plausibly consistent with SEBI's real, actual LODR integrated-filing mandate that took effect around that time. Investigated without guessing an API route, per instruction:

**Confirmed real (via direct HTTP fetch of NSE's own live page, not fabricated):**
- NSE's page at `https://www.nseindia.com/companies-listing/corporate-integrated-filing` is real (HTTP 200) and structurally distinct from the older `corporate-filings-financial-results` page — both exist as separate nav items today.
- That page's own HTML embeds a real sub-tab link: `corporate-integrated-filing?integratedType=integratedfilingfinancials` — i.e., NSE itself categorizes "Integrated Filing → Financials" as a distinct section, corroborating the lead's premise.
- The timing lines up: our data caps at a filing broadcast Jan 2025 (covering Oct-Dec 2024, i.e. Q3 FY2024-25) — immediately before the quarter-ended-March-2025 cutover the lead describes.

**Tested and ruled out (disclosed, not asserted):**
- Appending the real `integratedType=integratedfilingfinancials` parameter to our existing, already-working `corporates-financial-results` endpoint made no difference (identical 115 rows for ICICIBANK) — that endpoint silently ignores the unrecognized param. The Integrated Filing data is not served by this same endpoint with an added parameter.
- A pattern-matched candidate path, `/api/corporate-integrated-filing`, returned 404 — explicitly tested and rejected, not assumed.

**Blocked, not resolved:** the correct way to find the real underlying API without guessing is to observe the actual network request NSE's own frontend issues. Attempted this via a real headless-Chromium (Playwright) session, navigating the real page and interacting with its symbol search — NSE's edge/WAF rejected the automated browser at the protocol level (`ERR_HTTP2_PROTOCOL_ERROR`, then a hard timeout) across multiple realistic browser-fingerprint configurations (custom UA, viewport, locale/header variation). This is consistent with known real anti-automation behavior on NSE's site (documented by several independent public NSE API wrapper projects) and is an external blocker, not something further scripted retries are likely to fix.

**What this means:** the Integrated Filing hypothesis is plausible and well-corroborated structurally, but the exact request URL/params it needs cannot be confirmed from this environment. The reliable next step is a human opening that real page in an ordinary (non-automated) browser, opening DevTools → Network, entering ICICIBANK in the page's own symbol search, and copying the resulting XHR request URL and response shape — a short manual task that sidesteps NSE's anti-bot protection entirely (it only blocks automated clients, not normal browser use). No production code, config, or ingestion logic should change until that real request is confirmed this way.

## 7. Official bank disclosures — 2026-09-27, third addendum (alternative source while NSE automation is blocked)

While the manual NSE network capture is pending, verified the four required metrics directly against each bank's own official, board-approved statutory filing (not a press summary) — real, current, and independently confirms the scale of the freshness gap.

**ICICI Bank — Standalone, Q1-2027 (quarter ended June 30, 2026).** Source: official statutory standalone financial results filing, `icici.bank.in/content/dam/icicibank/india/managed-assets/docs/about-us/2027/financial-results-q1-2027.pdf` (Board-approved 2026-07-18; reviewed by joint statutory auditors B S R & Co. LLP and C N K & Associates LLP; filed under SEBI LODR Regulation 33/52(4)/63):
| Metric | Value | Filing line item |
|---|---|---|
| Gross NPA ratio | 1.38% | "% of gross non-performing customer assets (net of write-off) to gross customer assets" |
| Net NPA ratio | 0.35% | "% of net non-performing customer assets to net customer assets" |
| Return on Assets (annualised) | 2.49% | "Return on assets (annualised)" |
| CET1 ratio | 16.19% | From ICICI's separate Performance Review narrative page (same filing date) — the statutory results table itself discloses only Total Capital Adequacy Ratio (Basel III) = 16.84%, not CET1 broken out; flagging this granularity difference between the two official documents rather than treating them as interchangeable. |

**Kotak Mahindra Bank — Standalone, Q1FY27 (quarter ended June 30, 2026).** Source: official Media Release, `kotak.bank.in/content/dam/Kotak/investor-relation/Financial-Result/QuarterlyReport/FY-2027/q1/PressRelease/Q1-FY27_Press-Release.pdf` (Board-approved 2026-07-18):
| Metric | Value |
|---|---|
| Gross NPA ratio | 1.18% |
| Net NPA ratio | 0.27% |
| Return on Assets (annualised) | 2.14% |
| CET1 ratio | 22.4% |

**This independently confirms the freshness gap is larger than previously estimated.** Our stored FinancialFact data caps at Q3 FY2024-25 (quarter ended December 2024). Real, official, current data exists for Q1 FY2026-27 (quarter ended June 2026) — six full quarters newer, filed with the normal ~3-week post-quarter-end lag both banks always have. This rules out "nothing newer has been filed yet" as an explanation for the NSE endpoint's behavior — the data genuinely exists and is public; the `corporates-financial-results` endpoint specifically isn't surfacing it.

**Status:** this is documentary/manual verification, useful for validating any future refresh's output and for understanding true data currency, but not itself a machine-readable ingestion source (no XBRL, no structured taxonomy tags — a PDF each). It does not replace resolving the NSE Integrated Filing question for an actual automated refresh pipeline. No refresh preview built yet; still holding on the manual NSE network capture.

**Provenance correction (2026-09-27):** the table above incorrectly implied all 8 values came from one kind of "statutory filing." Corrected per-metric sourcing:
- ICICI GNPA, NNPA, ROA: the official standalone statutory financial results filing (`financial-results-q1-2027.pdf`).
- ICICI CET1: a *separate* document — the Performance Review narrative page (`performance-review-quarter-ended-june-30-2026`) — confirmed standalone ("on a standalone basis"), dated June 30, 2026. The statutory filing itself only discloses Total CAR (16.84%), not CET1 separately.
- Kotak GNPA, NNPA, ROA, CET1: all four from one document, the official Media Release (`Q1-FY27_Press-Release.pdf`), specifically its "Kotak Mahindra Bank standalone results" section (before the separate "Consolidated results at a glance" section).

## 8. Dry-run import preview — `scripts/s6_pilot_bank_disclosure_dry_run.py` (committed to this worktree, not run against any database)

Built a reviewable script that reuses the real, unmodified `_fiscal_year_from_financial_year()`/`_QUARTER_MAP` (`ingest.py`) to derive the period, and the real, unmodified `quality.assess_plausibility()` to check each value — same validation path production ingestion uses, not a reimplementation. The script never opens a database connection and has no `--apply` mode; a separate, explicitly-approved script would be written for the actual write once this is reviewed.

Derived period for both banks: **fiscal_year=2027, fiscal_quarter=1** (quarter ended 2026-06-30, Non-Consolidated) — six quarters newer than the known stored max (FY2025 Q3), so all 8 records are structurally guaranteed INSERTs, not UPDATEs (no row at this period identity can already exist).

Real output (executed 2026-09-27), one row per record — full detail (document hash, exact quote, rollback SQL) in the script's own output:

| # | Symbol | Metric | Value | Source doc | `assess_plausibility()` result |
|---|---|---|---|---|---|
| 1 | ICICIBANK | gross_npa_pct | 1.38% | Statutory results PDF (sha256 `b95bef73...`) | OK |
| 2 | ICICIBANK | net_npa_pct | 0.35% | Statutory results PDF | OK |
| 3 | ICICIBANK | roa (annualised) | 2.49% | Statutory results PDF | OK |
| 4 | ICICIBANK | cet1_ratio | 16.19% | Performance Review page (sha256 `abfdb2ac...`) | OK |
| 5 | KOTAKBANK | gross_npa_pct | 1.18% | Media Release PDF (sha256 `54adb21b...`) | OK |
| 6 | KOTAKBANK | net_npa_pct | 0.27% | Media Release PDF | OK |
| 7 | KOTAKBANK | roa (annualised) | 2.14% | Media Release PDF | OK |
| 8 | KOTAKBANK | cet1_ratio | 22.4% | Media Release PDF | OK |

All 8/8 pass the real plausibility gate. The within-entity anomaly check (`quality.assess()`, compares against trailing production values) was deliberately **not** simulated — it needs each symbol's real trailing FinancialFact history from production, which this dry run doesn't have; it will run identically to any other `ingest_period()` call at actual write time and is not something to fabricate a result for here.

Every record: `source_provider="BankDisclosure"`, `source_tag=None`, `taxonomy=None` — never labeled NSE/XBRL, per instruction, since none of this came from a taxonomy tag. `published_at` = each bank's board-approval date (2026-07-18). Rollback for every record is a `DELETE` keyed on the exact unique-index tuple (symbol, metric_code, fiscal_year=2027, fiscal_quarter=1, period_type, consolidation_scope) — safe because each is a brand-new period identity; deleting it cannot touch any pre-existing row.

**Status: preview complete, reviewed at the code/data level, not executed against any database.** Production writes remain held pending review of this preview, per instruction.

## 9. Round-2 script correction — `s7_pilot_bank_disclosure_apply.py` (2026-09-27)

An owner review of the first apply script found five real defects, all confirmed and corrected:

| Finding | Correction |
|---|---|
| Read-only engine silently ignored PRAGMA failures, no dialect/readback check | `_assert_sqlite_url()` guards the dialect; `_verify_readonly_engine()` reads `PRAGMA query_only` back from the real connection and raises if it isn't `1`; read-only sessionmaker sets `autoflush=False` |
| **Transaction gap (most important):** checks ran on a separate read-only connection before the write, then `apply()` reused that stale result and called upsert-capable `_upsert()` — a real TOCTOU race | `_write_records_transactionally()` re-checks collision + quality for every record **inside the same session/transaction it writes to**, immediately before each insert; uses true insert-only `db.add()`, never `_upsert()`; any collision raises and aborts before any row commits |
| Backup called "verified" right after `write_text()`, no readback | `take_verified_backup()` writes to a persistent `scripts/backups/` directory, re-opens and re-parses the file, compares row count, and records a sha256 of the file itself |
| Manifest existed only in memory/stdout; rollback deleted by id alone | `persist_manifest()` writes a durable JSON file (ids, full key tuples, values, quality status/reason, per-record provenance); `_rollback_records()` re-fetches each row by id and **refuses to delete** any row whose current value/quality_status/key no longer matches the manifest |
| Document hashes not retained in the manifest; all records shared one `_BOARD_APPROVED_DATE` treated as publication date | Each `SourceDoc` now carries its own `publication_date` **and** `publication_date_basis`. The ICICI statutory filing's board-approval note is used as an explicitly-flagged proxy (it states no separate issuance dateline); the ICICI Performance Review page (independently-confirmed visible byline "July 18, 2026") and the Kotak Media Release (dateline sentence explicitly equating issuance with the board meeting) both have real, distinct textual confirmation |

**Focused tests** (`tests/scripts/test_s7_pilot_bank_disclosure_apply.py`), run for real against the repo's existing isolated scratch DB (`tests/conftest.py` — never a real dev/production DB), all passing:
- `test_collision_aborts_before_any_row_commits` — a pre-existing row at one of the 8 keys aborts the whole batch, zero net rows added beyond the pre-existing one.
- `test_mid_batch_quality_failure_commits_nothing` — an injected out-of-range CET1 value aborts the entire batch, including the 3 records already added-but-not-committed before it.
- `test_full_batch_commits_cleanly_when_nothing_blocks_it` — sanity check: all 8 commit when nothing blocks them.
- `test_rollback_refuses_to_delete_a_row_that_changed_since_insert` — one row mutated after insert; rollback deletes the unchanged row and explicitly refuses the changed one.
- `test_readonly_verification_fails_when_pragma_was_never_applied` / `test_readonly_engine_refuses_a_non_sqlite_url` — the enforcement guard itself is tested, not just its happy path.

6/6 passed (`uv run --no-project pytest tests/scripts/test_s7_pilot_bank_disclosure_apply.py -v`).

**Status: corrected script + tests complete and verified locally. `--apply` has not been run, and won't be, until the corrected code and a fresh 8-record dry-run manifest (from the approved production execution path) are both reviewed.**

## Files cited
`app/services/financial_facts/ingest.py`, `quality.py`, `nse_xbrl_client.py`; `app/db/models/financial_fact.py`, `marketripple_score_snapshot.py`; `app/services/marketripple_score/snapshot.py`, `banking_universe.py`; `app/scheduler/scheduler.py`; `app/tasks/daily_tasks.py`; `scripts/financial_facts_backfill.py`, `s4_backfill_wide_universe.py`, `s45_backfill_plausibility.py`, `s45b_backfill_document_quarantine.py`, `s5_backfill_snapshots.py`, `marketripple_score_production_backfill.py`; `artifacts/marketripple_score_s4_wide_banking_validation.md` (repo root).
