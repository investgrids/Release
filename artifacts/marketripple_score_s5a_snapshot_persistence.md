# MarketRipple Score — S5-A: Snapshot Persistence

**Date:** 2026-08-29
**Scope:** First S5 sub-phase only (owner's own sequencing: S5-A must precede Company-page UI). Builds the persistence boundary between the real, frozen scoring engine and any future read path — no scheduler wiring, no API route, no Company-page or methodology-page changes yet. `publishable=False` unchanged.
**Branch:** `company-identity/c1-reconciliation`

## What was built

- **`MarketRippleScoreSnapshot`** (`app/db/models/marketripple_score_snapshot.py`) — one row per (symbol, calculated_at); latest row per symbol is authoritative. Every field is a real value the engine already computes via `MarketRippleScore`/`PillarScore` — this persists the existing contract, it doesn't invent new derived data. `entity_id` is resolved via the real `resolve_entity_by_any_symbol()` (Company Identity C1-C5's own resolver), never a second, ad hoc symbol lookup.
- **`compute_and_persist_snapshot(db, symbol, peer_group=None)`** (`app/services/marketripple_score/snapshot.py`) — the only writer. Calls the existing, frozen `compute_marketripple_score()` verbatim (zero new scoring logic) and persists its real output, including a real `financial_data_as_of` derived from the newest FinancialFact period that actually passed every S4.5/S4.5-B exclusion (`ANOMALY`, `IMPLAUSIBLE_SCALE`, `SOURCE_DOCUMENT_QUARANTINED`) — not just the newest period that exists in the table.
- **`get_latest_snapshot(db, symbol)`** — the only reader a Company page should use going forward. Pure DB read, zero network calls.
- `market_data_as_of`/`intelligence_as_of` are deliberately set equal to `calculated_at`, not a fabricated finer-grained timestamp — Market Behaviour is a live read at compute time with no other real "as of" to report, and `current_intelligence`'s `compute_company_score()` doesn't currently expose its most recent contributing signal's own timestamp. Reporting a guessed time would be false precision.
- 4 new real DB-backed tests (`test_marketripple_score_snapshot.py`): `financial_data_as_of` correctly skips a newer-but-fully-quarantined period, returns `None` when nothing is eligible, `get_latest_snapshot` picks the most recent row by `calculated_at`, and returns `None` when no snapshot exists. Combined MarketRipple Score test suite: **29/29 pass**.

## Real end-to-end verification

Ran `scripts/s5_backfill_snapshots.py` — a real `compute_and_persist_snapshot()` call for all 27 real banks in `ALL_ELIGIBLE_NSE_BANKS`, real network + real DB, no shortcuts:

| Check | Result |
|---|---|
| Every bank gets a real, resolved `entity_id` | ✅ all 27 (e.g. ICICIBANK → `cmp_7044ee48aeaa`) |
| Every bank carries `methodology_version=BANKING_V1` | ✅ all 27 |
| `financial_data_as_of` reflects real, eligible fiscal periods | ✅ 26 banks → `FY2025Q3`; **YESBANK → none** (correctly empty — every one of its FinancialFact-sourced metrics is now S4.5-B quarantined, exactly the intended behavior, confirmed independently here) |
| `publishable=False` preserved | ✅ all 27 |
| Read path (`get_latest_snapshot`) returns the just-persisted row with zero network calls | ✅ confirmed (ICICIBANK: same `id`, same `score`) |

## Explicitly not done in this batch

Per the owner's own S5 sequencing and this initiative's standing "small, checkpointed batches" discipline — not attempted here, each is its own real next step:

- **S5-B** (publication eligibility gate, coverage threshold)
- **S5-C** (Company-page UI — single score display)
- **S5-D** (`/methodology/marketripple-score` page)
- **S5-E** (multi-cycle shadow validation before flipping `publishable`)
- Scheduler/cron wiring for automatic recomputation (S5-A only proves the persistence path works; nothing runs unsupervised yet)

## Status

S5-A done and verified with real, complete data across the full 27-bank universe. Ready for S5-B.
