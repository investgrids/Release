#!/usr/bin/env bash
# Restore a SQLite database file onto the app volume, safely.
#   ./restore_db.sh /path/to/ig.db [expected-sha256]
# Never deletes the database it replaces: the old file is kept as ig.db.pre-restore-<timestamp> on the same volume.
# The backend is stopped for the swap, and started again at the end. Run with DISABLE_SCHEDULER=1 in .env (no background writes during checks).
set -euo pipefail
SRC="${1:?usage: restore_db.sh <file.db> [expected-sha256]}"
WANT="${2:-}"
ROOT=/opt/marketripple
ENVF=$ROOT/.env
cd "$ROOT/src/deploy/hostinger"
export GIT_SHA="$(git -C "$ROOT/src" rev-parse --short=12 HEAD)"   # same image tag deploy.sh uses, so a restart here never builds a differently tagged image
[ -f "$SRC" ] || { echo "no such file: $SRC"; exit 2; }

echo "== 1. verify the file BEFORE touching anything"
GOT=$(sha256sum "$SRC" | cut -d' ' -f1)
echo "sha256: $GOT"
[ -z "$WANT" ] || [ "$GOT" = "$WANT" ] || { echo "SHA-256 MISMATCH (expected $WANT): refusing"; exit 1; }
python3 - "$SRC" <<'PY'
import sqlite3, sys
con = sqlite3.connect("file:%s?mode=ro" % sys.argv[1], uri=True)
r = con.execute("PRAGMA quick_check").fetchone()[0]
print("quick_check:", r)
if r != "ok":
    sys.exit("integrity check failed: refusing")
tabs = [t[0] for t in con.execute("select name from sqlite_master where type='table' and name not like 'sqlite_%'")]
counts = sorted(((con.execute('select count(*) from "%s"' % t).fetchone()[0], t) for t in tabs), reverse=True)
print("tables:", len(tabs), "| largest:", ", ".join("%s=%d" % (t, n) for n, t in counts[:8]))
PY

echo "== 2. stop the backend (Redis and Caddy keep running)"
docker compose --env-file "$ENVF" stop backend

echo "== 3. swap on the volume, keeping the old file"
TS=$(date -u +%Y%m%dT%H%M%SZ)
docker run --rm -v marketripple_appdata:/data -v "$(dirname "$(readlink -f "$SRC")")":/in:ro alpine sh -c "
  set -e
  [ -f /data/ig.db ] && cp -p /data/ig.db /data/ig.db.pre-restore-$TS && echo 'kept old database as ig.db.pre-restore-$TS'
  rm -f /data/ig.db-wal /data/ig.db-shm
  cp /in/$(basename "$SRC") /data/ig.db.new && mv /data/ig.db.new /data/ig.db
  ls -la /data/ig.db"

echo "== 4. start and verify"
docker compose --env-file "$ENVF" up -d backend
for i in $(seq 1 60); do
  s=$(docker inspect -f '{{.State.Health.Status}}' marketripple-backend-1 2>/dev/null || echo starting); [ "$s" = healthy ] && break; sleep 5
done
[ "$s" = healthy ] || { echo "backend not healthy after restore; the previous database is still on the volume as ig.db.pre-restore-$TS"; exit 1; }
docker exec marketripple-backend-1 python -c "import sqlite3; c=sqlite3.connect('/data/ig.db'); print('live quick_check:', c.execute('pragma quick_check').fetchone()[0])"
echo "RESTORED. To roll back: stop backend, copy /data/ig.db.pre-restore-$TS back over /data/ig.db, start."
