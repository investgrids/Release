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

## Deployment & recovery verification (2026-08-30, same day)

**Deploy mechanics were not clean.** The GitHub-webhook-triggered build hung indefinitely at `"scheduling build on Metal builder"` with no progress and no deployment record for 10+ minutes — a Railway build-infrastructure stall, not a config problem (verified `rootDirectory`/`dockerfilePath` were correctly aligned, unlike a prior, superficially similar incident). `railway redeploy --from-source --yes` (forcing a fresh build from the same commit) worked where the webhook did not; the new deployment (`2e0a520e`) built and went live successfully, replacing the old one (`05ab21ee`).

**While the deploy was stuck, the disk-full condition was confirmed to be actively ongoing** (not just historical) — live logs at 07:32-07:36 UTC on 08-30 showed the same `database or disk is full` error hitting real, current triage events. Given active data loss with the proper deploy blocked, a manual, narrowly-scoped interim mitigation was made with explicit owner approval: `railway ssh` was used to delete exactly the two oldest daily backup files (`ig-daily-20260819.db`, `ig-daily-20260820.db`, 108MB total) by exact filename — never touching `/data/ig.db` (the live database) or its `-wal`/`-shm` files. This is exactly the kind of raw-CLI production action this project's own discipline normally avoids; it was used here only as a bounded, explicitly-approved bridge to stop active data loss until the real code fix could deploy, not as a substitute for it.

**Full 7-point recovery verification, all against real production state:**

1. **Disk recovery** — real `df -h /data` before/after: 434M total, 424M used, **0 available (100%)** immediately before the manual cleanup → 321M used, 104M available (76%) right after it → **261M used, 163M available (62%)** after the real code fix deployed and its own boot-triggered pruning ran. Confirmed via direct filesystem inspection, not the (stale/cached) Railway dashboard summary.
2. **Database writes** — zero `database or disk is full` errors in any post-deploy log window (checked from 07:49 UTC onward); `theme_worker.done` and other jobs that were erroring on this exact error before now complete cleanly.
3. **Ingestion recovery** — real, natural growth observed via `/api/coverage/funnel?hours=1`: `detected` count rose from 33 → 43 → still climbing across repeated live checks, with zero manual data inserted to force this.
4. **Silence detector** — `"Added job \"job_check_ingestion_silence\" to job store"` confirmed in real startup logs of the new deployment; code review confirms it never writes to the DB (log-only). Its first live 30-minute firing had not yet occurred at verification time (deploy was ~10 min old) — expected imminently, not separately re-checked.
5. **Backup / dynamic retention** — the new deployment's own boot-triggered backup attempt itself still failed once more (`backup.failed error="database or disk is full"` at 07:48:34 — the live DB, ~118MB, briefly didn't fit in the ~104MB then-free before this deploy's own pruning ran), but **pruning ran anyway** (by design — "always prune on failure") and correctly computed and applied the new dynamic retention: real inspection of `/data/backups` afterward shows exactly 1 daily (`ig-daily-20260822.db`) + 1 boot (`ig-20260822T193026Z.db`) backup remain — the intended minimum floor for a DB this size against this volume. With 163MB now genuinely free against a 118MB live DB, the next real backup attempt (2 AM IST daily cron, or any future restart) has real headroom to succeed; this wasn't separately forced/re-verified to avoid another unnecessary production restart.
6. **Persistence** — real record counts from the live DB's own `db.status` log, before vs. after: `intelligence_articles` 582 → 635, `events` 10,490 → 11,811, `opportunities` 263 → 287. Counts grew, not reset — the live database and its data survived the deploy and all pruning intact. Only backup *copies* were ever deleted.
7. **Post-deploy log watch** — scanned all logs from 07:49 UTC onward for any error besides the already-known, already-flagged AI-provider issues (Mistral 401, OpenRouter 404s): none found.

**A real, minor, separate finding surfaced during recovery** (not fixed, noted only): `/data/backups` also held ~60 orphaned `*.tmp-journal` files (1KB each, ~60KB total — negligible in size) going back to 08-18, one per failed backup attempt. `_prune_old_backups()`'s existing orphan cleanup only globs `*.tmp`, not `*.tmp-journal`. Byte impact is trivial and this did not contribute meaningfully to the incident; flagged for a future small cleanup, not addressed in this deployment per the owner's explicit instruction not to bundle unrelated changes in.

## What this fix does NOT address (explicitly out of scope, flagged for separate decisions)

- **Why the volume filled in the first place beyond backup accumulation** — the live DB's own growth rate (10,490 `events` rows, 582 `intelligence_articles` as of 08-26) isn't itself investigated; if the DB keeps growing, the computed retention will keep shrinking toward the 1/1 floor, and eventually even 1 daily + 1 boot backup won't fit safely alongside the live DB. That is a real, separate signal that the volume itself needs resizing (Railway dashboard only, not exposed via CLI) — not something this fix can solve from inside the app.
- **The AI-provider failures observed in the same log window** (Mistral 401 Unauthorized — an invalid/expired API key; several OpenRouter models returning 404 — stale model slugs) are real, separate problems visible in the same logs, unrelated to the disk-full root cause, and not fixed here.
- **The exact mechanism behind the 994 FAILED_UNKNOWN candidates from the scheduler audit** (daily cap vs stale candidate windows vs LLM rate-limiting) — separate, not addressed by this fix.
- Not yet deployed to production — code committed locally, deploy is a separate, explicit decision.
