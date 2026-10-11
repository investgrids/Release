#!/usr/bin/env bash
# Deploy an EXACT commit to the VPS, wait until the backend is healthy, and prove what is running.
#   ./deploy.sh <full-40-char-sha>            deploy that commit
#   ./deploy.sh <sha> --keep-scheduler-off     deploy but leave DISABLE_SCHEDULER as it is in .env (default behaviour already)
# Rollback = run it again with the previous known-good SHA (the previous image is kept, so this is fast).
set -euo pipefail
SHA="${1:?usage: deploy.sh <full-40-char-sha>}"
[[ "$SHA" =~ ^[0-9a-f]{40}$ ]] || { echo "refusing: give the full 40-character commit SHA, not a branch or short hash"; exit 2; }
ROOT=/opt/marketripple
SRC=$ROOT/src
ENVF=$ROOT/.env
[ -f "$ENVF" ] || { echo "missing $ENVF (secrets file)"; exit 2; }
[ "$(stat -c %a "$ENVF")" = "600" ] || { echo "$ENVF must be mode 600"; exit 2; }

echo "== fetch and check out exactly $SHA"
[ -d "$SRC/.git" ] || { echo "no checkout at $SRC (clone the repo there first)"; exit 2; }
git -C "$SRC" fetch --quiet origin
git -C "$SRC" checkout --quiet --detach "$SHA"
test "$(git -C "$SRC" rev-parse HEAD)" = "$SHA"
test -z "$(git -C "$SRC" status --porcelain)" || { echo "working tree is not clean; refusing"; exit 2; }
echo "checked out $(git -C "$SRC" log -1 --format='%h %s')"

cd "$SRC/deploy/hostinger"
export GIT_SHA="${SHA:0:12}"
echo "== build and start (image marketripple-backend:$GIT_SHA)"
docker compose --env-file "$ENVF" build backend
docker compose --env-file "$ENVF" up -d --remove-orphans

echo "== wait for healthy (up to 5 min)"
for i in $(seq 1 60); do
  s=$(docker inspect -f '{{.State.Health.Status}}' marketripple-backend-1 2>/dev/null || echo starting)
  [ "$s" = healthy ] && break
  sleep 5
done
[ "$s" = healthy ] || { echo "NOT healthy after 5 minutes; last logs:"; docker logs --tail 40 marketripple-backend-1; exit 1; }

echo "== prove what is running"
echo "image: $(docker inspect -f '{{.Config.Image}}' marketripple-backend-1)"
echo "source commit in checkout: $(git -C "$SRC" rev-parse --short=12 HEAD)"
docker exec marketripple-backend-1 python -c "from app.core.config import settings as s; print('is_production =', s.is_production); print('scheduler disabled =', __import__('os').environ.get('DISABLE_SCHEDULER') == '1')"
docker exec marketripple-backend-1 python -c "from app.core.config import settings as s; assert s.is_production, 'is_production is False: refusing to serve'" || { echo "PRODUCTION FLAG NOT SET: stopping the backend"; docker compose --env-file "$ENVF" stop backend; exit 1; }
echo "DEPLOYED $SHA"
