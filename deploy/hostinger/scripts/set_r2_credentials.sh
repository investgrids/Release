#!/usr/bin/env bash
# Type the new bucket's credentials ON THE SERVER, with hidden input, so they never pass through chat, a terminal log or the repo.
# Run from your PC:   ssh -t -i ~/.ssh/marketripple_hostinger root@157.173.218.197 'bash /opt/marketripple/src/deploy/hostinger/scripts/set_r2_credentials.sh'
# Writes /opt/marketripple/bucket.r2.env (mode 600). It changes nothing else; switch_backup_target.sh does the switch.
set -euo pipefail
OUT=/opt/marketripple/bucket.r2.env
[ -t 0 ] || { echo "run this with ssh -t so the prompts work"; exit 2; }
echo "Cloudflare R2: dashboard -> R2 -> your bucket -> Settings gives the S3 API address; Manage API tokens gives the Access Key ID and Secret."
read -r  -p "S3 API address (paste either https://<account-id>.r2.cloudflarestorage.com or the same with /<bucket-name> on the end): " ENDPOINT
# accept the address with the bucket name appended, as the Cloudflare dashboard shows it
PATHPART="${ENDPOINT#https://*.r2.cloudflarestorage.com}"; PATHPART="${PATHPART#/}"; PATHPART="${PATHPART%%/*}"
ENDPOINT="${ENDPOINT%/$PATHPART}"; ENDPOINT="${ENDPOINT%/}"
if [ -n "$PATHPART" ]; then BUCKET="$PATHPART"; echo "bucket name taken from the address: $BUCKET"; else read -r -p "Bucket name: " BUCKET; fi
read -r  -p "Access Key ID: " KEYID
read -rs -p "Secret Access Key (hidden): " SECRET; echo
case "$ENDPOINT" in https://*.r2.cloudflarestorage.com) ;; *) echo "that does not look like an R2 endpoint (https://<account-id>.r2.cloudflarestorage.com): aborting"; exit 2;; esac
[ -n "$BUCKET" ] && [ -n "$KEYID" ] && [ -n "$SECRET" ] || { echo "a value was empty: aborting"; exit 2; }
umask 177
cat > "$OUT" <<EOF
BACKUP_BUCKET_ENDPOINT=${ENDPOINT%/}
BACKUP_BUCKET_REGION=auto
BACKUP_BUCKET_NAME=$BUCKET
BACKUP_BUCKET_ACCESS_KEY_ID=$KEYID
BACKUP_BUCKET_SECRET_ACCESS_KEY=$SECRET
EOF
chmod 600 "$OUT"
echo "saved $OUT (mode $(stat -c %a "$OUT")); names: $(cut -d= -f1 "$OUT" | tr '\n' ' ')"
