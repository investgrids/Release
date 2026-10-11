# Hostinger KVM 1 migration runbook

Server: Hostinger VPS 2052469, KVM 1 (1 vCPU, 4 GB RAM, 50 GB disk), Mumbai, Ubuntu 24.04, IPv4 `157.173.218.197`, name `api.marketripple.in` (A record, TTL 300).
Why: Railway cost about $20-30 a month, mostly ~1.8 GB of always-on memory. See `apps/backend/benchmarks/ai_search/baseline_2026_10_04/step7/RAILWAY_AUDIT_AND_RECOVERY_PLAN_2026-10-10.md`.

## State of the server today
Hardened (key-only SSH, firewall 22/80/443, swap, fail2ban), Docker installed, Caddy answering HTTPS with a valid certificate. **No backend, no data, no secrets yet.** `scripts/nse_check.sh` already passed from this IP (7/7 data calls 200).

## The kit
| File | Purpose |
|---|---|
| `compose.yml` | Caddy + backend (3 GB cap) + Redis. Only Caddy publishes ports. Sets `JSON_LOGS` and `RAILWAY_ENVIRONMENT` so the app knows it is production. |
| `Caddyfile` | HTTPS for `api.marketripple.in`, reverse proxy, SSE streams unbuffered. |
| `.env.example` | Names of the 33 settings. Real values live only in `/opt/marketripple/.env` (mode 600, never in git). |
| `scripts/bootstrap.sh` | One-time server setup (already done by hand; rebuilds a fresh server the same way). |
| `scripts/deploy.sh <sha>` | Deploys an exact 40-character commit, waits for healthy, proves the image, refuses to serve if `is_production` is false. Same command rolls back (previous SHA). |
| `scripts/backup_now.sh` | Verified online backup of the live database (SQLite backup API). |
| `scripts/restore_db.sh <file> [sha256]` | Verifies, then swaps a database in, keeping the old one. |
| `scripts/verify_cutover.sh` | External checks (health, suggestions, TLS, robots/noindex, CORS from the real site). Run from anywhere. |
| `scripts/nse_check.sh` | NSE reachability from the server's IP. |

## Decisions the owner must make (the kit does not decide them)
1. **Secrets:** copy the values from Railway to `/opt/marketripple/.env` without printing them (pipe straight over SSH). Rotate the AI provider keys, Fyers, and the admin key afterwards: 13 credentials were baked into old images and none were rotated.
2. **Database copy:** (a) briefly start the stopped Railway backend so its backup job writes a current copy to the bucket, then stop it again; or (b) use the newest existing bucket copy, which may be older. Either way verify with `restore_db.sh` (SHA-256 + `quick_check`) before use.
3. **Article images (`/data/media`):** copy them (needs a read of the production volume) or let them regenerate (hero images missing for a while). They are not in the database backups.

## Dry run (nothing public changes)
1. On the server: clone the repo to `/opt/marketripple/src`, create `/opt/marketripple/.env` from `.env.example` with `DISABLE_SCHEDULER=1`, `chmod 600`.
2. `scripts/deploy.sh <sha>` → expect "is_production = True" and healthy.
3. `scripts/restore_db.sh <verified copy>`.
4. Replace the placeholder in Caddy's config (this kit's `Caddyfile` already proxies to the backend) and `docker compose up -d caddy`.
5. `scripts/verify_cutover.sh` → all PASS. `scripts/nse_check.sh` → all 200.
6. Watch memory for a day with the scheduler **on** only after step 7; during this dry run it stays off.
7. Turn the scheduler on (`DISABLE_SCHEDULER=0`, restart) and watch `docker stats` and logs for at least an hour. Expect ~1.5-2 GB; the 3 GB cap should never be reached. If it climbs steadily, stop and investigate before cutover.

## Cutover (a few minutes)
1. Take a final `backup_now.sh`. Make sure the Railway backend stays **stopped** (two schedulers on two databases must never run together).
2. Vercel (project `release-web`, Production): set `NEXT_PUBLIC_API_BASE_URL=https://api.marketripple.in`, then redeploy (`vercel --prod`). The site's security policy takes the API origin from this same value.
3. Check the live site: AI Search landing (suggestions), a company page, an event page, the browser console.
4. Leave Railway stopped, not deleted, for two weeks. Delete it only after two clean weeks and a verified off-box backup.

## Rollback
- **Bad deploy:** `scripts/deploy.sh <previous-sha>`.
- **Bad data:** stop backend, copy `/data/ig.db.pre-restore-<ts>` back over `/data/ig.db` (see the end of `restore_db.sh` output), start.
- **Bad cutover:** set `NEXT_PUBLIC_API_BASE_URL` back to the Railway URL and redeploy the frontend, then restart Railway from the saved deployment IDs in `railway_pause_2026-10-10.md` (needs a Railway plan).

## Things that will bite
- A host without `RAILWAY_ENVIRONMENT`/`JSON_LOGS` serves unpublished scores and demo endpoints. `compose.yml` sets both and `deploy.sh` verifies it.
- Docker publishes ports around the firewall. Never add `ports:` to `backend` or `redis`.
- Heavy one-off jobs (score refresh, backfills) must not run on a 4 GB box next to the live app: run them on a copy elsewhere.
- NSE can flag an IP later. Re-run `nse_check.sh` after a day and after any ingestion alert.
- Disk: watch `/data` (images grew the Railway volume from 0.9 to 2.6 GB). 50 GB here is plenty; still alert at 70 %.
- Certificates renew automatically only while the `caddy_data` volume exists.
