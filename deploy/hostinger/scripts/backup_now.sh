#!/usr/bin/env bash
# Take a consistent, verified online backup of the live SQLite database (SQLite's backup API: safe while the app is running) and copy it to the host.
#   ./backup_now.sh        -> /opt/marketripple/backups/ig-<timestamp>.db  (+ .sha256), keeps the newest 7 manual backups
# The app's own remote_backup job uploads to the off-box bucket on its schedule; this is the manual / pre-change one.
set -euo pipefail
TS=$(date -u +%Y%m%dT%H%M%SZ)
OUT=/opt/marketripple/backups
mkdir -p "$OUT"
docker exec -i marketripple-backend-1 python - <<PY
import sqlite3, sys
src = sqlite3.connect("file:/data/ig.db?mode=ro", uri=True)
dst = sqlite3.connect("/tmp/backup-$TS.db")
src.backup(dst); dst.close(); src.close()
chk = sqlite3.connect("/tmp/backup-$TS.db").execute("pragma quick_check").fetchone()[0]
print("quick_check:", chk)
sys.exit(0 if chk == "ok" else 1)
PY
docker cp "marketripple-backend-1:/tmp/backup-$TS.db" "$OUT/ig-$TS.db"
docker exec marketripple-backend-1 rm -f "/tmp/backup-$TS.db"
( cd "$OUT" && sha256sum "ig-$TS.db" > "ig-$TS.db.sha256" && cat "ig-$TS.db.sha256" && ls -la "ig-$TS.db" )
# keep the newest 7
ls -1t "$OUT"/ig-*.db 2>/dev/null | tail -n +8 | while read -r f; do rm -f "$f" "$f.sha256"; done
echo "BACKUP OK: $OUT/ig-$TS.db"
