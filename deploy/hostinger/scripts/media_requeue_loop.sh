#!/usr/bin/env bash
# Re-queue lost hero images in small tranches, newest first, until none are left. Runs on the VPS host (nohup). The image worker does 3 per minute, so 60 every 20 minutes keeps it busy
# without piling up, and only asks the free image service for what it can deliver. Skips a round if the worker still has a backlog.
#   nohup bash media_requeue_loop.sh > /opt/marketripple/media_requeue.log 2>&1 &
set -uo pipefail
SCRIPT=/opt/marketripple/media_requeue.py
BATCH=60
INTERVAL=1200
while true; do
  state=$(docker exec -i marketripple-backend-1 python - <<'PY' 2>/dev/null
import sqlite3
c = sqlite3.connect("file:/data/ig.db?mode=ro", uri=True, timeout=30)
q = lambda s: c.execute(s).fetchone()[0]
print(q("select count(*) from generated_media where status='lost_file'"), q("select count(*) from generated_media where status in ('pending','generating') or (status='failed' and attempts<3)"))
PY
)
  lost=${state%% *}; backlog=${state##* }
  echo "$(date -u +%FT%TZ) lost_file=$lost worker_backlog=$backlog"
  [ -z "$lost" ] && { echo "could not read state; will retry"; sleep 300; continue; }
  [ "$lost" -eq 0 ] && { echo "DONE: no lost images left"; exit 0; }
  if [ "${backlog:-0}" -lt 30 ]; then
    docker exec -i marketripple-backend-1 python - --requeue "$BATCH" < "$SCRIPT" 2>&1 | python3 -c "import sys,json; d=json.load(sys.stdin); print('  requeued', d.get('requeued'), '->', d['after'])" 2>&1
  else
    echo "  worker still busy, skipping this round"
  fi
  sleep "$INTERVAL"
done
