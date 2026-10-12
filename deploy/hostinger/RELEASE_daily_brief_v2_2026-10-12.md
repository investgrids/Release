# Release runbook: Daily Brief V2 (session correctness, forecast integrity, honest content)

**Status: prepared, NOT executed. Do not run without explicit approval.**

| | |
|---|---|
| Release commit | `972f234425b6da9292be9e6a2b2ab61036a60cbc` on `feature/daily-brief-v2` |
| Production baseline (verified on the server) | `579cae884023ca804eed447e2fdcefa27284f04f`, an ancestor of the release (4 commits ahead) |
| Schema change | none (one row delete on the existing `facts` table when a forecast is withheld) |
| Backend downtime | about 1 minute (container recreate) |
| Frontend | Vercel build of the same commits, merged into `main` through a reviewed PR (`main` merges cleanly; it keeps the AdSense meta tag) |
| Rollback, backend | `bash deploy/hostinger/scripts/deploy.sh 579cae884023ca804eed447e2fdcefa27284f04f` (previous image is kept) |
| Rollback, frontend | promote the previous Vercel deployment, or revert the merge commit |

## Order

1. **Backend first.** A new backend works with the currently deployed page (verified by reading it: every key the old page reads is kept). The old page shows the realized result with a Bearish label and a "Market Wrap" header immediately.
   Known cosmetic effect until step 2: the old After Market tab prints `null%` if a forecast confidence is null (withheld direction, or the model omitted confidence), and the old Pre-Market hero labels a withheld forecast "Neutral". Keep the gap between steps short.
2. **Frontend second**, through the PR. The new page also accepts the old API shape (tested), so the order can be reversed without breaking anything; frontend-first leaves today's trust bug visible until the backend ships.

## Preconditions

```bash
git rev-parse HEAD                                              # 972f234425b6da9292be9e6a2b2ab61036a60cbc
git merge-base --is-ancestor 579cae884023ca804eed447e2fdcefa27284f04f HEAD && echo ancestry ok
ssh -i ~/.ssh/marketripple_hostinger root@157.173.218.197 'cd /opt/marketripple/src && git rev-parse HEAD; docker inspect -f "{{.Config.Image}} {{.State.Health.Status}}" marketripple-backend-1'
#   expect 579cae884023... and "marketripple-backend:579cae884023 healthy"
bash deploy/hostinger/scripts/backup_now.sh   # on the server, as in the previous runbook; note the file name
```

## Deploy

```bash
GIT_SSH_COMMAND="ssh -i ~/.ssh/marketripple_hostinger" git push root@157.173.218.197:/opt/marketripple/repo.git feature/daily-brief-v2
ssh -i ~/.ssh/marketripple_hostinger root@157.173.218.197 \
  'cd /opt/marketripple/src && bash deploy/hostinger/scripts/deploy.sh 972f234425b6da9292be9e6a2b2ab61036a60cbc'
```

## Verification (any failure: roll back)

```bash
B=https://api.marketripple.in
curl -s $B/api/daily-brief/intelligence | python -c "
import sys,json; d=json.load(sys.stdin)
print(d['session']['state'], d['market_verdict']['kind'], d['market_verdict'].get('direction'), d['market_verdict'].get('headline'))
print(d['summary']); print(len(d['questions']), 'questions', len(d['evidence']), 'evidence')"
# after 15:30 IST on a trading day: kind == realized, headline Lower/Higher/Flat close, no 'opening' wording in reasoning
# before 09:15 IST: kind == forecast, target_date set; if direction is null, headline == "Signals disagree"
curl -s $B/api/market/insights                     # sentiment/fear_greed vary with breadth; null only when there is no sample
curl -s $B/api/facts/today | python -c "import sys,json; print([f['entity_type'] for f in json.load(sys.stdin)['facts']].count('macro'))"   # 0 outside the pre-open window
curl -s -o /dev/null -w "%{http_code}\n" $B/api/market/opening-prediction   # 200
ssh -i ~/.ssh/marketripple_hostinger root@157.173.218.197 'docker logs --since 10m marketripple-backend-1 2>&1 | grep -c "Traceback"'   # no new tracebacks
# Frontend: https://www.marketripple.in/newsroom/daily-brief renders; view source: one FAQPage JSON-LD whose questions match the page
```

## Known, deliberately not changed here

- `job_keep_market_warm` calls the opening-prediction endpoint every 5 minutes at all hours, so opening-prediction LLM calls continue around the clock (about 51 calls / 131 attempts in the 24 h to 2026-10-12 per the usage report), independent of the Daily Brief. Changing it is a scheduled-job change and needs an owner decision.
- The session-keyed cache adds at most about 3 extra regenerations a day (one per session-state change).
- Index quotes still carry placeholder `high`/`low` (price +/- 0.5%) in `/api/indices/`; no page shows them, and the Daily Brief facts hide them.
- The Weekend Intelligence session resolver is separate from `market_session_state`.
