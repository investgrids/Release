#!/usr/bin/env bash
# Type the Requesty API key ON THE SERVER with hidden input (never through chat or a log), save it to .env, restart the backend.
# Run from your PC:   ssh -t -i ~/.ssh/marketripple_hostinger root@157.173.218.197 'bash /opt/marketripple/src/deploy/hostinger/scripts/set_requesty_key.sh'
# The AI tier stays OFF until REQUESTY_MODELS is also set (done separately after the account's models and limits are checked).
set -euo pipefail
ENVF=/opt/marketripple/.env
[ -t 0 ] || { echo "run this with ssh -t so the prompt works"; exit 2; }
read -rs -p "Requesty API key (hidden): " KEY; echo
KEY="$(echo -n "$KEY" | tr -d ' \r\n')"
[ "${#KEY}" -ge 20 ] || { echo "that looks too short to be an API key: aborting, nothing changed"; exit 2; }
TS=$(date -u +%Y%m%dT%H%M%SZ); cp -p "$ENVF" "$ENVF.before-requesty-$TS"; chmod 600 "$ENVF.before-requesty-$TS"
umask 177
grep -v '^REQUESTY_API_KEY=' "$ENVF.before-requesty-$TS" > "$ENVF.new"; echo "REQUESTY_API_KEY=$KEY" >> "$ENVF.new"; mv "$ENVF.new" "$ENVF"; chmod 600 "$ENVF"
cd /opt/marketripple/src/deploy/hostinger; export GIT_SHA=$(git -C /opt/marketripple/src rev-parse --short=12 HEAD)
docker compose --env-file "$ENVF" up -d --force-recreate backend 2>&1 | grep -E "Recreated|Started|rror" || true
for i in $(seq 1 40); do s=$(docker inspect -f '{{.State.Health.Status}}' marketripple-backend-1 2>/dev/null || echo starting); [ "$s" = healthy ] && break; sleep 5; done
[ "$s" = healthy ] || { echo "backend not healthy; restoring the old .env"; cp -p "$ENVF.before-requesty-$TS" "$ENVF"; docker compose --env-file "$ENVF" up -d --force-recreate backend >/dev/null 2>&1; exit 1; }
echo "saved (old .env kept as .env.before-requesty-$TS). Backend healthy. Tell Claude to check the account's models."
