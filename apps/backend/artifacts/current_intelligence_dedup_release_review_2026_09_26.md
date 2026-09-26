# Current Intelligence Dedup — Release Review Package

**Branch:** `marketripple-score/current-intelligence-dedup` (off `origin/main` @ `c84c28a`)
**Status:** Local only. Not pushed, not deployed. Public activation: 0%.

## 1. Commits (12 total, chronological)

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
| 10 | `9a0cb48` | **Freeze public-row score/signal fields**; dry-run backfill reporting |
| 11 | `d1bc50d` | Financial Strength metric-coverage gap investigation |
| 12 | `092f977` | Tighten comparability scope; full-path public-row field survey |

**Grouped diff** (30 files, +2304/-75):
- Backend scoring core: `company_score_engine.py`, `current_intelligence.py`, `engine.py`, `contracts.py`, `financial_strength.py`, `public_projection.py`, `snapshot.py`
- New backend module: `company_signal_event_id_backfill.py`
- Schema: `company_signal.py`, `marketripple_score_snapshot.py`, `schema_patches.py` (2 new nullable columns each, additive only)
- Opportunity V2: `orchestration.py` (the public-row freeze)
- Reconciled baseline: `.dockerignore`, `config.py`, `pyproject.toml` (cherry-picked from production hotfixes)
- Frontend: `CompanyPageClient.tsx`, new `MarketRippleScoreCard.test.tsx`, `vitest.setup.ts`
- 10 new/modified backend test files, 2 artifacts (comparability + coverage-gap), 1 shadow-comparability script

## 2. Test totals (clarifying the ambiguity)

**Authoritative full-suite number** (branch HEAD @ `092f977`, `tests/` — the whole tree, not a subset, final confirmation run): **28 failed, 2120 passed, 2 skipped, 2 xfailed** (369.8s). Identical failure list across all 3 full-suite runs taken during this session (369.8s/371.7s/352.4s) — stable, not flaky on this branch's own commits.

All other numbers reported earlier this session (2038, 1336, 1313, 1296, 1319 passed) were **partial/bisection subset runs** (`tests/services/` only, or explicit file-list slices) used purely to isolate the 2 extra failures — not competing totals. Retracting the ambiguity: there is one real full-suite number, above.

**Parent-baseline comparison** (the actual requested check — equivalent dependencies, config, test order, zero application-code changes):
- Created a disposable worktree from `origin/main` (untouched).
- Cherry-picked the same 2 production hotfixes (`aed784e`/`25ae90a`'s originals) for dependency parity.
- Copied the same `.env`.
- Ran the exact same-position file slice (first 146 files in that checkout's own natural collection order — files differ slightly since this branch's new test files aren't present, so "first 146" there ≠ "first 146" here by content, but is the equivalent-scope set).
- **Result: the same 2 `test_opportunity_v2_batch_e_consumers.py` failures reproduce identically, with zero application-code changes present.** This is conclusive: pre-existing, order-dependent test-isolation bug in `origin/main` itself, not a regression from any commit in this branch. Root cause not further investigated (out of scope — a pre-existing bug, not something this branch's changes should be blocked on fixing).
- The other 26 failures are the same live-network/external-dependency category confirmed earlier (AI search live engines, comparison publisher V3 live, quant leakage/membership, macro rates live, etc.) — unaffected either way.

**Net: this branch introduces zero new test failures.** 28 vs 26 was never a real regression count; it's 26 pre-existing + 2 pre-existing-but-not-previously-observed-in-this-session's-earlier-narrower-runs.

## 3. Public-row freeze — end-to-end result

Two tests now cover this, run through the real `run_shadow_pass()` pipeline (never a direct call to the private `_process_cluster()`):

- `test_opportunity_v2_orchestration_public_row_scoring.py::test_public_row_score_and_signals_are_frozen_when_a_cluster_reprocesses` — **PASS**. Promotes a row to public with an editorial override, adds a real new signal, forces a real reprocess. Confirms `current_score`/`score_breakdown`/`contradictions`/`companies` are byte-identical before/after, and the new signal is provably NOT folded in.
- `test_opportunity_v2_orchestration_public_row_scoring.py::test_shadow_row_still_updates_normally` — **PASS** (control). An ordinary shadow row with the identical scenario DOES pick up the new signal — proves the freeze is `public_status`-specific, not a general break.
- `test_opportunity_v2_orchestration_public_row_field_survey.py::test_full_field_survey_of_a_reprocessed_public_row` — **PASS**. Full-path survey covering every field `run_shadow_pass()` can touch, not just the score-write block: confirms `public_status` + all 4 `editorial_*` fields + `current_score`/`score_breakdown`/`contradictions`/`sectors`/`companies` are frozen; confirms `narrative_status`/`current_title`/`current_summary`/`narrative_input_hash` are **not** frozen (proven to actually change across 2 real narrative-generation calls, not just untested); confirms Development linkage is additive regardless of `public_status`.

## 4. Backfill dry-run — counts, conflict handling, idempotency, rollback

`company_signal_event_id_backfill.py::backfill_company_signal_event_ids(db, dry_run=True)`:
- Reports `candidates`, `resolvable`, `unresolved_no_real_lineage`, `symbols_with_new_conflicting_groups` (+count).
- **Local dev DB dry-run result** (from the earlier one-off measurement, same derivation logic): 1734 total signals, 1398 resolvable (80.6%), 128 real duplicate-event groups, 15 genuinely conflicting.
- 5 tests, all passing: article-lineage derivation, opportunity-lineage (highest-importance tie-break), no-real-lineage (never fabricates), dry-run writes nothing at all, dry-run correctly flags a newly-introduced conflicting group.
- **Idempotency**: proven — a second real run against an already-backfilled row is a no-op (`event_id IS NULL` filter naturally excludes it).
- **Rollback procedure**: not applicable in the traditional sense — this backfill only ever sets a currently-NULL column to a derived value; it never overwrites a non-NULL value. To undo, a real rollback would be `UPDATE ai_company_signals SET event_id = NULL WHERE event_id IN (<the specific derived values written this run>)` — not yet needed since the script has never been run against any real database beyond ad hoc local measurement copies, and remains unexecuted against production.

## 5. Production snapshot / FinancialFact coverage

**Still blocked.** The "Production Reads" classifier denied both attempts this session. Status: **unknown**, not zero — do not treat the local-DB findings (zero `financial_facts` rows, zero `marketripple_score_snapshots` rows) as evidence about production's real state. This remains the one open item requiring either an explicit permission grant or the owner running the read directly.

## Held per instruction

Lineage backfill execution and public activation (`publishable` flip) remain held pending this review's sign-off.
