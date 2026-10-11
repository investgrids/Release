# Release runbook: AI usage metering + capacity protection (2026-10-11)

**Status: prepared, NOT executed.** Nothing here has been pushed or deployed. Run it only after explicit approval.

| | |
|---|---|
| Release commit | `ab17d67757165769cb5c30df2f953580bf60cc7d` on `release/cost-and-migration` |
| Currently deployed (verified on the server) | `7c0d85c32c6a710ed9745c05020c6e03231fdf4e`, an ancestor of the release (4 commits ahead, backend only, no web, no new dependencies) |
| Commits in the release | `8963bf5` instrumentation, `78a5e99` bounded report + skip bookkeeping, `da8d114` chain-level skip counting + hardening tests, `ab17d67` capacity protection |
| Schema change | 3 NEW tables (`ai_usage_attempt`, `ai_search_request_log`, `ai_usage_daily`) + 4 indexes, created by `create_all` at startup. No existing table touched (verified on an isolated copy of production). |
| Downtime | about 1 minute (container recreate), same as every previous deploy |
| Rollback | redeploy the previous SHA; the previous image is kept. New tables are additive and ignored by old code, so no database rollback is needed. |

## 0. Preconditions (read-only checks, all must pass)

```bash
# on your PC, in D:\IG-ai-v2-release
git rev-parse HEAD                                   # must be ab17d67757165769cb5c30df2f953580bf60cc7d
git merge-base --is-ancestor 7c0d85c32c6a710ed9745c05020c6e03231fdf4e HEAD && echo "ancestry ok"
git status --short | grep -v '^??' | grep -v benchmarks    # must print nothing (no unrelated tracked changes)

# on the server
ssh -i ~/.ssh/marketripple_hostinger root@157.173.218.197 '
  cd /opt/marketripple/src && git rev-parse HEAD                      # expect 7c0d85c32c6a... (the deployed commit)
  docker inspect -f "{{.State.Health.Status}}" marketripple-backend-1 # expect healthy
  df -h / | tail -1                                                   # expect plenty free (39 GB at preparation time)
  docker images marketripple-backend --format "{{.Tag}}" | grep -c 7c0d85c32c6a   # expect 1: the rollback image exists
'
```

Capture an AI Search baseline (no personal question; a fixed public one) to compare the answer contract after deploy:

```bash
curl -s -N -m 120 "https://api.marketripple.in/api/ai/search/stream?q=What%20is%20the%20outlook%20for%20the%20IT%20sector%3F" \
 | python -c "
import sys,json
t=sys.stdin.read(); d=[l[6:] for l in t.split('\n') if l.startswith('data: {\"result\"')]
r=json.loads(d[0])['result']; print(sorted(r.keys())); print('schema_version', r.get('schema_version'))" > /tmp/ai_search_contract_before.txt
cat /tmp/ai_search_contract_before.txt
```

## 1. Backup (before any change)

```bash
ssh -i ~/.ssh/marketripple_hostinger root@157.173.218.197 'bash /opt/marketripple/src/deploy/hostinger/scripts/backup_now.sh'
# prints "quick_check: ok" and "BACKUP OK: /opt/marketripple/backups/ig-<timestamp>.db" plus its sha256. Note the file name.
# The app also uploads verified, compressed boot/daily backups to Cloudflare R2; the restart in step 3 produces a fresh verified boot backup too.
```

## 2. Ship the commits to the server repository

```bash
cd /d/IG-ai-v2-release
GIT_SSH_COMMAND="ssh -i ~/.ssh/marketripple_hostinger" git push root@157.173.218.197:/opt/marketripple/repo.git release/cost-and-migration
```

## 3. Deploy (exact commit; builds, restarts, waits for healthy, proves what is running)

```bash
ssh -i ~/.ssh/marketripple_hostinger root@157.173.218.197 \
  'cd /opt/marketripple/src && bash deploy/hostinger/scripts/deploy.sh ab17d67757165769cb5c30df2f953580bf60cc7d'
# expected last lines:  image: marketripple-backend:ab17d6775716 / is_production = True / scheduler disabled = False / DEPLOYED ab17d677...
```

## 4. Verification (run all; any failure means roll back, section 5)

```bash
# V1 tables exist, integrity ok
ssh -i ~/.ssh/marketripple_hostinger root@157.173.218.197 'docker exec marketripple-backend-1 python -c "
import sqlite3; c=sqlite3.connect(\"file:/data/ig.db?mode=ro\",uri=True)
print([r[0] for r in c.execute(\"select name from sqlite_master where name like \x27ai_%usage%\x27 or name=\x27ai_search_request_log\x27 order by 1\")])
print(\"quick_check:\", c.execute(\"pragma quick_check\").fetchone()[0])"'
#   expect the 3 tables and quick_check: ok

# V2 scheduler: 37 jobs, including ai_usage_flush, ai_usage_daily, keep_market_warm; no duplicate execution
ssh -i ~/.ssh/marketripple_hostinger root@157.173.218.197 'docker logs --since 5m marketripple-backend-1 2>&1 | grep -E "scheduler.jobs_registered|db.tables_ready"'

# V3 site healthy
curl -s -o /dev/null -w "%{http_code}\n" https://api.marketripple.in/api/ai/search/suggestions     # 200
curl -s -o /dev/null -w "%{http_code}\n" https://www.marketripple.in/                                # 200

# V4 AI Search contract unchanged: same top-level keys and schema_version as the baseline
#     (repeat the baseline command above writing to /tmp/ai_search_contract_after.txt, then:)
diff /tmp/ai_search_contract_before.txt /tmp/ai_search_contract_after.txt && echo "contract identical"

# V5 admin report is authenticated (key read on the server, never printed)
curl -s -o /dev/null -w "no key: %{http_code}\n" "https://api.marketripple.in/api/admin/ai-usage"       # 401
ssh -i ~/.ssh/marketripple_hostinger root@157.173.218.197 '
  KEY=$(grep "^ADMIN_API_KEY=" /opt/marketripple/.env | cut -d= -f2-)
  curl -s -H "X-Admin-Key: $KEY" "https://api.marketripple.in/api/admin/ai-usage?hours=1" | python3 -c "import sys,json; d=json.load(sys.stdin); print(sorted(d)); print(d[\"recorder\"])"'
#   expect keys ai_search, features, models, gaps, recorder... and recorder.flush_errors == 0 after the first minutes

# V6 telemetry flowing: after ~5 minutes the report shows features (event_enrichment, triage, ...) with attempts > 0
# V7 no flush trouble:
ssh -i ~/.ssh/marketripple_hostinger root@157.173.218.197 'docker logs --since 15m marketripple-backend-1 2>&1 | grep -c "ai_usage.flush_failed"'   # expect 0 (a few "will_retry" under heavy ingestion is acceptable; "dropped" is not)

# V8 one AI Search request produces exactly one request row (counts only, no question text)
#     run one search, wait 1 minute, then GET /api/admin/ai-usage?hours=1 and confirm ai_search.user_requests.requests increased by exactly 1.

# V9 capacity protection visible: during provider cooldown windows the report shows skipped_no_capacity / skipped_cooldown_event under features.event_enrichment.skipped
```

Stop conditions during the first hour: container unhealthy, `quick_check` not ok, AI Search contract diff, any AI Search 5xx rate increase, `flush_failed_dropped` in the logs, or the event backlog count *growing faster* than before (see the 24-hour audit).

## 5. Rollback

```bash
# Fast rollback: the previous image is kept, so no rebuild is needed.
ssh -i ~/.ssh/marketripple_hostinger root@157.173.218.197 \
  'cd /opt/marketripple/src && bash deploy/hostinger/scripts/deploy.sh 7c0d85c32c6a710ed9745c05020c6e03231fdf4e'
# The three new tables stay in the database, empty or partly filled; the old code ignores them. Nothing else needs undoing.
# Only if the database itself were damaged (not expected: the change is additive and was verified on a copy):
#   stop the backend and restore the backup from section 1 with scripts/restore_db.sh <file> <sha256>.
```

## 6. 24-hour audit after deploy (what the new telemetry must answer)

```bash
ssh -i ~/.ssh/marketripple_hostinger root@157.173.218.197 '
  KEY=$(grep "^ADMIN_API_KEY=" /opt/marketripple/.env | cut -d= -f2-)
  curl -s -H "X-Admin-Key: $KEY" "https://api.marketripple.in/api/admin/ai-usage?hours=24" | python3 -m json.tool > /tmp/ai_usage_24h.json && head -80 /tmp/ai_usage_24h.json'
```

It reports: AI Search user requests (answered / degraded / error, cache hits, LLM calls and attempts, provider-reported tokens or "unknown"), calls and success rates per feature (article_generation, scheduled_market_article, event_enrichment, triage, article_update), per-model failures, skipped work by kind, and cost only where a documented price exists. Compare against these pre-release numbers: 219 of 232 scheduled runs failed with 85% of provider tries "already exhausted"; 8,167 overdue failed events; 2,235 events failed in the last 7 days with 99.9% `provider_unavailable`.
