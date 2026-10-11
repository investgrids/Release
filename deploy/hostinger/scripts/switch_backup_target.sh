#!/usr/bin/env bash
# Point the app's off-box backups at the new bucket (/opt/marketripple/bucket.r2.env), prove it works with a real backup, and roll back automatically if it does not.
# Preconditions it checks itself: the new bucket already holds every backup from the old one (run copy_backups.sh --execute first).
set -euo pipefail
ROOT=/opt/marketripple; ENVF=$ROOT/.env; NEWF=$ROOT/bucket.r2.env; HERE="$(cd "$(dirname "$0")" && pwd)"
[ -f "$NEWF" ] || { echo "missing $NEWF (run set_r2_credentials.sh first)"; exit 2; }
echo "== 1. is everything already copied?"
left=$(bash "$HERE/copy_backups.sh" "$NEWF" 2>&1 | grep -o "to copy: [0-9]* objects" | head -1)
echo "   $left"
[ "$left" = "to copy: 0 objects" ] || { echo "the new bucket does not hold every backup yet: run copy_backups.sh $NEWF --execute"; exit 1; }

TS=$(date -u +%Y%m%dT%H%M%SZ); cp -p "$ENVF" "$ENVF.before-bucket-switch-$TS"; chmod 600 "$ENVF.before-bucket-switch-$TS"
echo "== 2. switch (old settings kept as .env.before-bucket-switch-$TS)"
umask 177
grep -v '^BACKUP_BUCKET_' "$ENVF.before-bucket-switch-$TS" > "$ENVF.new"; cat "$NEWF" >> "$ENVF.new"; mv "$ENVF.new" "$ENVF"; chmod 600 "$ENVF"
cd "$ROOT/src/deploy/hostinger"; export GIT_SHA=$(git -C "$ROOT/src" rev-parse --short=12 HEAD)
rollback() { echo "ROLLING BACK to the old bucket settings"; cp -p "$ENVF.before-bucket-switch-$TS" "$ENVF"; docker compose --env-file "$ENVF" up -d --force-recreate backend >/dev/null 2>&1; echo "rolled back"; exit 1; }
docker compose --env-file "$ENVF" up -d --force-recreate backend 2>&1 | grep -E "Recreated|Started|rror" || true
for i in $(seq 1 40); do s=$(docker inspect -f '{{.State.Health.Status}}' marketripple-backend-1 2>/dev/null || echo starting); [ "$s" = healthy ] && break; sleep 5; done
[ "$s" = healthy ] || { echo "backend not healthy"; rollback; }

echo "== 3. a real backup to the new bucket, run now (about 80 s)"
res=$(docker exec marketripple-backend-1 python -c "from app.db.remote_backup import backup_to_bucket; import json; r = backup_to_bucket('boot'); print(json.dumps({k: r.get(k) for k in ('status','reason','object_key','size_bytes','remote_verified','cleanup_complete')}))" 2>&1 | tail -1)
echo "   $res"
echo "$res" | grep -q '"status": "ok"' && echo "$res" | grep -q '"remote_verified": true' || { echo "the test backup did not verify"; rollback; }
echo "SWITCHED. The app now uploads to the new bucket. The old bucket is untouched; keep it until you are happy, then delete it."
