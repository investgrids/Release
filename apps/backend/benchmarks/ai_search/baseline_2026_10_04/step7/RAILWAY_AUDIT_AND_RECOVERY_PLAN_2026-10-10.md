# Railway read-only audit and recovery/migration plan (2026-10-10)

Read-only: Railway metrics and API reads, the backend code, and Railway's backup records. Nothing on production was changed by this audit. (Before it, at the owner's request, the `backend` and `Redis` services were stopped; see `railway_pause_2026-10-10.md`.)

## 1. Peak RAM and CPU (backend, 30 days, 4-hour averages)

| | median | p90 | p99 | max |
|---|---|---|---|---|
| Memory (GB) | 1.54 | 2.96 | 8.42 | **14.55** |
| CPU (vCPU) | 0.036 | 0.097 | 0.236 | 0.544 |

- Steady state is **about 1.5–1.85 GB of memory and 0.04 vCPU**. The app alone idles at about 250 MB with the scheduler off (measured locally), so roughly 1.3–1.6 GB is scheduled-job and in-process cache memory.
- 19 of 181 buckets exceed 3 GB. The large ones fall on operation days, not normal days: 18 Sep (8.4 GB, DFE deploy), 20 Sep (7.0 GB, canary promote and production scripts), 28 Sep (7.0 GB, score deploy), 3 Oct (14.6 GB), 4 Oct (10.0 GB, score refresh and HEG deploy). A 4-hour average of 14.6 GB is above the 8 GB container limit, so those buckets include **more than one process at a time**: the old and new container overlapping during a deploy, plus one-off scripts run inside the container.
- CPU is not a constraint: p99 0.24 vCPU against an 8 vCPU limit.

## 2. What the memory costs (Railway's published memory rate)

30 days = 1,454 GB-hours = **about $20.2**: baseline (1.8 GB steady) $15.6, spikes $3.9. CPU is about $1. Egress was 31 GB in the first 10 days of October (about $1.6 at $0.05/GB). This reconciles with the $20–30 invoices. The steady baseline is the main cost, then spikes, then egress.

## 3. SQLite, volume and backup sizes

- `backend-volume`: **2.6 GB used of 4.88 GB** (30-day average 1.98 GB, peak 3.03 GB). It was about 0.9 GB in September.
- The database itself was about 290 MB on 10 Sep (notes); the Railway volume backups are 246 MB (31 Aug) and 201 MB (20 Sep), consistent with a database of a few hundred MB. The growth is therefore **not the database**. The likely cause is generated article images: `run_image_generation_cycle` runs every minute and writes to `/data/media` on the same volume. **Not measured** (reading the volume needs a production read that was not authorised).
- Railway volume backups: backend 3 (31 Aug, 20 Sep, 10 Oct), Redis 1 (5 Sep), none scheduled. Off-volume copies: `ig-backups` bucket, about 1 GB of verified objects (CR-0b), last re-verified in September.
- Orphan `postgres-volume` (88 MB, empty database, attached to nothing): delete requested, still listed.
- Storage in total costs well under $1 a month. The risk is disk full (4.88 GB limit), which has happened twice before.

## 4. Scheduler and ingestion concurrency

- 34 scheduled jobs; each job is limited to one running copy (`max_instances=1`, `coalesce=True`), so a job cannot pile up on itself.
- Different jobs do run together. Four 5-minute jobs (`refresh_mie_state`, `run_aipe_cycle`, `run_signal_publish_cycle`, `run_signal_enrichment_cycle`) fire on the same minute boundary; a 1-minute image job and a 2-minute price monitor run alongside them. The DB pool allows 10 connections plus 20 overflow on SQLite.
- Boot: a cluster of repair jobs runs on every start (about 2.4 restarts a day in September), each staggered but all inside the first minutes, which is a known contention window.
- Egress callers seen in logs (from the Railway assistant, not independently measured): Bingbot on `/api/events/*`, the frontend server-side render polling `/api/data/quotes`, `/api/insights/*`, `/api/stocks/*`, and a long SSE stream.

## 5. 4 GB or 8 GB?

- **8 GB is not justified for steady state.** The process needs about 2 GB; p90 is 3 GB.
- **4 GB is justified as a ceiling, not as the typical need.** It leaves headroom over the 3 GB p90 and the normal boot burst. It will cap runaway work, which is the point.
- What 4 GB will not tolerate: running heavy one-off jobs inside the live container (the score refresh over about 1,600 companies, backfills, ad-hoc scripts). Those caused the 7–14 GB buckets. Run them on a copy of the data off Railway, or as a separate short-lived service, and never overlap them with a deploy.
- Railway bills memory actually used, not the limit, so a limit does not lower the baseline. It only stops spikes. The baseline falls only by reducing what the process holds.

## 6. Plan choice

Railway's published pricing as I understand it (verify on the pricing page before buying): Hobby is $5 a month including $5 of usage; Pro is $20 a month including $20 of usage. For about $20–25 of real usage the two cost about the same, so the plan matters much less than usage. Hobby's limits (8 GB, 8 vCPU) fit this app. Pro is only needed for team or workspace features.

## 7. Safe database recovery plan (from the existing backups)

Use only when the volume or the database is damaged. Nothing here is executed by this document.
1. **Do not touch the live volume until a copy is verified.** Stop the `backend` service first so SQLite is not being written.
2. Pick the restore source: newest `ig-backups` bucket object (verified off-volume copy), else the newest Railway volume backup.
3. Download to a disposable path off the volume. Verify the SHA-256 recorded at upload and run `PRAGMA quick_check` (expect `ok`).
4. Check content, not just integrity: row counts for events, news articles, companies, opportunities, company scores and snapshots against the last known figures, and that the newest event date is recent.
5. Copy the verified file onto the volume as a new name, keep the damaged file aside (never delete it first), swap with the service stopped, then start.
6. Verify: `/health`, `/api/admin/db-status` (`type=sqlite, connected=true, writable=true`), a company page, the AI Search suggestions endpoint, and a clean scheduler boot in the logs.
7. Roll back by swapping the damaged file back (it was kept) if verification fails.
Gaps to close first: the bucket objects were last re-verified in September and should be re-verified before any move; media files on the volume are not covered by these database backups.

## 8. Migration plan (Railway to a cheaper host, only if the bill stays high)

1. Re-verify the newest bucket backup (step 7.3 to 7.4) and take a fresh Railway volume backup.
2. Inventory `/data`: database, `media/`, local backups, WAL files. Decide what moves (database and media) and what does not (local backups).
3. Build the same container image on the target (a 2 GB, 2 vCPU server is enough on current numbers), mount a data disk of at least 5 GB, and restore the database by step 7.
4. Run it alongside Railway read-only with the scheduler **off** and compare API responses for the main endpoints.
5. Cut over by changing the frontend's `NEXT_PUBLIC_API_BASE_URL` and the CSP origin; keep Railway stopped (not deleted) for at least two weeks as the rollback.
6. Only then delete Railway resources. Do not run two schedulers against two databases at once.
Risks: SEO and AdSense if the cutover has downtime; the SSE and cache behaviour changes; the second restore of a changing database loses writes made after the copy (use a short write freeze).

## 9. What to do, in order

1. Select a Railway plan (Hobby or Pro), then restart `Redis` and `backend` from the saved deployment IDs.
2. Deploy `bac3bd6` or later (cost guards and AI Search protections), then push the frontend cache branch (`cost/frontend-api-cache`).
3. Set the `backend` memory limit to 4 GB.
4. Stop running heavy one-off jobs inside the live container; run them off Railway.
5. Find which jobs and caches hold the extra 1.3–1.6 GB (profile locally with the AI providers disabled) and trim them; this is the largest remaining saving (about $10 a month).
6. Check what is filling `/data` (images versus database) before the disk reaches 4.88 GB.

## 10. Not measured

Database file size on the volume; the split of the 2.6 GB between database, media and backups; per-endpoint egress; which job holds the baseline memory; the actual invoice lines. Each needs a production read or the billing page.
