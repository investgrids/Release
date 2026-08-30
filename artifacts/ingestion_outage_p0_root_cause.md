# P0 — Ingestion Outage Root-Cause Investigation & Fix

**Date:** 2026-08-30
**Trigger:** the scheduler/publication-failure audit found `EventTriage` received zero rows for two multi-day windows (08-19 to 08-21, 08-26 to 08-29) in the prior 30 days. Owner authorized a read-only root-cause investigation first, then the smallest demonstrated fix, then a silence detector.
**Method:** real Railway CLI access (`railway logs`, `railway deployment list`) against the actual production service (`ig-backend`), not assumptions.

## Root cause: confirmed, with direct log evidence

**The Railway persistent volume filled up, and every database write — including `EventTriage` inserts — started failing with `sqlite3.OperationalError: database or disk is full`.**

Direct evidence, in causal order:
1. `db.status` log, 2026-08-26 17:32:11: volume at **91.5% used, 28.6MB free** (`volume_total_bytes=454299648`, `volume_used_bytes=415576064`). Last *successful* backup was dated **2026-08-22** — every daily backup attempt since had already been silently failing for days before ingestion itself broke.
2. The very next line: the boot-triggered backup attempt (fired on this exact container restart) **immediately fails**: `backup.failed error="database or disk is full"`.
3. Real production logs from 2026-08-29 show the pipeline actively running (`job_enrich_events` executing on schedule, real events like `nse-1e3eedc2b2` entering the pipeline) — so ingestion itself wasn't stopped; classification/persistence was. `"[Pipeline] Could not mark failure for ...: (sqlite3.OperationalError) database or disk is full"` appears **204 times** in a single ~7-hour log window.
4. `triage_worker.stopped` / `triage_worker.started` fires once, 08-29 17:14 — a restart that did not fix the underlying disk-full state (restarting a container doesn't free disk space).

**This is the second occurrence of the same failure mode.** `app/db/backup.py`'s own docstring already documented a "2026-08-19 volume-full incident" and a fix (always prune on failure, not just on success) — confirmed via `git log`, that fix landed 2026-08-19 21:25 and is live in the current deployment. It reduced but did not eliminate the risk, because of what's below.

## Why the 08-19 fix didn't prevent the 08-26 recurrence

The fix hardcoded retention as **file counts** (`_DAILY_RETENTION=4`, `_BOOT_RETENTION=1` = 5 files), sized against a comment's assumption of "~49MB per backup." By 2026-08-26 the real live DB had grown to **~91MB** — roughly double that assumption. The same 5 retained files now cost ~455MB, already exceeding the volume's real 434MB capacity *before counting the live DB file itself*. The comment even said "Revisit these numbers if the DB grows materially" — that revisit never happened, because nothing forced it to happen; the DB just grew quietly until the same failure mode returned a week later.

## Fix implemented (smallest change that removes the recurrence mechanism, not just the symptom)

Rather than picking a new fixed count that will go stale again on the next growth cycle, `app/db/backup.py`'s retention is now **computed from the real, current DB file size on every backup run** (`_max_backup_slots()`): given the real 434MB volume budget and a 70% target ceiling, it works out how many full-size backup copies actually fit alongside the live DB, with a floor of 1 daily + 1 boot so history never drops to zero. This self-corrects as the DB grows — no future "revisit these numbers" step needed, and no second incident from the same stale-assumption mechanism.

- `app/db/backup.py`: `_max_backup_slots()` added; `_prune_old_backups()` now calls it instead of using fixed constants.
- `app/tasks/daily_tasks.py`: stale "kept ~14 days" comment on the daily backup job corrected to describe the real, dynamic retention.
- 3 tests updated/added in `tests/services/test_backup.py` (2 existing tests adapted to the new dynamic function via a pinned monkeypatch; 1 new test proving retention actually shrinks as DB size grows, with a real minimum floor). 12/12 pass.

## Silence detector added (owner's explicit request)

A real gap this severe went undetected for weeks — only surfaced by a retrospective 30-day audit. `app/tasks/daily_tasks.py::job_check_ingestion_silence()`, registered in `app/scheduler/scheduler.py` on a 30-minute interval: checks the real `max(EventTriage.triaged_at)` against now; logs `ingestion.silence_detected` (ERROR level) if the gap exceeds 90 minutes (~6x the real 15-minute ingestion cadence). **Deliberately log-only, no DB write** — so it keeps working during the exact disk-full scenario it exists to catch, rather than potentially failing itself for the same reason. 2 new tests in `tests/services/test_ingestion_silence_detector.py`, both pass against real DB-backed EventTriage rows.

## Verified locally before proposing deploy

- `_max_backup_slots()` run against a real local DB file: correctly returns a smaller slot count for a larger DB, never below the 1/1 floor.
- `job_check_ingestion_silence()` run against real local data: correctly detected a real stale gap (this local copy's own last real sync).
- Full scheduler registration (`register_jobs()`) run for real: all 30 jobs including the new `ingestion_silence_check` register without error.
- All 14 real tests (12 backup + 2 silence-detector) pass.

## What this fix does NOT address (explicitly out of scope, flagged for separate decisions)

- **Why the volume filled in the first place beyond backup accumulation** — the live DB's own growth rate (10,490 `events` rows, 582 `intelligence_articles` as of 08-26) isn't itself investigated; if the DB keeps growing, the computed retention will keep shrinking toward the 1/1 floor, and eventually even 1 daily + 1 boot backup won't fit safely alongside the live DB. That is a real, separate signal that the volume itself needs resizing (Railway dashboard only, not exposed via CLI) — not something this fix can solve from inside the app.
- **The AI-provider failures observed in the same log window** (Mistral 401 Unauthorized — an invalid/expired API key; several OpenRouter models returning 404 — stale model slugs) are real, separate problems visible in the same logs, unrelated to the disk-full root cause, and not fixed here.
- **The exact mechanism behind the 994 FAILED_UNKNOWN candidates from the scheduler audit** (daily cap vs stale candidate windows vs LLM rate-limiting) — separate, not addressed by this fix.
- Not yet deployed to production — code committed locally, deploy is a separate, explicit decision.
