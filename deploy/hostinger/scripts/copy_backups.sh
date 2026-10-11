#!/usr/bin/env bash
# Copy the backups from the current bucket (/opt/marketripple/bucket.env or the live .env) to the new one, verified. Dry run unless --execute.
#   copy_backups.sh <new-bucket-env-file> [--execute] [--limit N]
# The destination env file uses the same names as the app (BACKUP_BUCKET_ENDPOINT, _REGION, _NAME, _ACCESS_KEY_ID, _SECRET_ACCESS_KEY, optional _ADDRESSING_STYLE).
set -euo pipefail
DSTF="${1:?usage: copy_backups.sh <new-bucket-env-file> [--execute] [--limit N]}"; shift || true
ROOT=/opt/marketripple
SRCF=$ROOT/bucket.env; [ -f "$SRCF" ] || SRCF=$ROOT/.env
[ -f "$DSTF" ] || { echo "no such file: $DSTF"; exit 2; }
TMP=$(mktemp); chmod 600 "$TMP"; trap 'rm -f "$TMP"' EXIT
g() { grep -E "^$2=" "$1" | head -1 | cut -d= -f2-; }
{
  echo "SRC_ENDPOINT=$(g "$SRCF" BACKUP_BUCKET_ENDPOINT)";   echo "SRC_REGION=$(g "$SRCF" BACKUP_BUCKET_REGION)";   echo "SRC_BUCKET=$(g "$SRCF" BACKUP_BUCKET_NAME)"
  echo "SRC_KEY_ID=$(g "$SRCF" BACKUP_BUCKET_ACCESS_KEY_ID)"; echo "SRC_SECRET=$(g "$SRCF" BACKUP_BUCKET_SECRET_ACCESS_KEY)"
  echo "DST_ENDPOINT=$(g "$DSTF" BACKUP_BUCKET_ENDPOINT)";   echo "DST_REGION=$(g "$DSTF" BACKUP_BUCKET_REGION)";   echo "DST_BUCKET=$(g "$DSTF" BACKUP_BUCKET_NAME)"
  echo "DST_KEY_ID=$(g "$DSTF" BACKUP_BUCKET_ACCESS_KEY_ID)"; echo "DST_SECRET=$(g "$DSTF" BACKUP_BUCKET_SECRET_ACCESS_KEY)"
  a=$(g "$DSTF" BACKUP_BUCKET_ADDRESSING_STYLE); [ -n "$a" ] && echo "DST_ADDRESSING=$a"
} > "$TMP"
NET=${COPY_DOCKER_NETWORK:-bridge}
mkdir -p $ROOT/copywork
docker run --rm -i --network "$NET" --env-file "$TMP" -v $ROOT/copywork:/work python:3.11-slim sh -c "pip install -q --disable-pip-version-check boto3 >/dev/null 2>&1 && python - $*" < "$(dirname "$0")/copy_backups.py"
