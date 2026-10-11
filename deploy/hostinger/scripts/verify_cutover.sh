#!/usr/bin/env bash
# External checks for the new API host. Run from ANY machine (your PC is fine). Exits non-zero if anything fails.
#   ./verify_cutover.sh [https://api.marketripple.in]
# Makes only cheap GET requests and one CORS preflight. It never calls the AI search endpoint (no provider quota is used).
BASE="${1:-https://api.marketripple.in}"
SITE="https://www.marketripple.in"
fail=0
ok()  { echo "  PASS  $1"; }
bad() { echo "  FAIL  $1"; fail=1; }
code() { curl -s -m 25 -o /dev/null -w '%{http_code}' "$@"; }

echo "== reachability and TLS"
h=$(curl -s -m 25 "$BASE/health"); [ "$(code "$BASE/health")" = 200 ] && echo "$h" | grep -q '"status": *"ok"' && ok "/health 200 with status ok: $h" || bad "/health (needs 200 AND a JSON body with status ok; a placeholder page does not count)"
[ "$(curl -s -m 25 -o /dev/null -w '%{ssl_verify_result}' "$BASE/health")" = 0 ] && ok "certificate valid" || bad "certificate"
exp=$(echo | openssl s_client -connect "${BASE#https://}:443" -servername "${BASE#https://}" 2>/dev/null | openssl x509 -noout -enddate 2>/dev/null | cut -d= -f2)
echo "  info  certificate expires: $exp"

echo "== the contract the new frontend needs"
sg=$(curl -s -m 40 "$BASE/api/ai/search/suggestions"); [ "$(code "$BASE/api/ai/search/suggestions")" = 200 ] && echo "$sg" | grep -q '"items"' && ok "/api/ai/search/suggestions 200 with an items list" || bad "suggestions endpoint (needs 200 AND JSON with items)"

echo "== crawler guard (cost change)"
curl -s -m 20 "$BASE/robots.txt" | grep -q 'Disallow: /' && ok "robots.txt disallows everything" || bad "robots.txt"
curl -sI -m 20 "$BASE/api/events/" | tr -d '\r' | grep -qi '^x-robots-tag: noindex' && ok "noindex header on /api" || bad "noindex header"

echo "== CORS from the real site origin"
h=$(curl -s -m 20 -i -X OPTIONS "$BASE/api/ai/search/suggestions" -H "Origin: $SITE" -H "Access-Control-Request-Method: GET" | tr -d '\r')
echo "$h" | grep -qi "^access-control-allow-origin: $SITE" && ok "CORS allows $SITE" || bad "CORS does not allow $SITE"

echo "== HTTP -> HTTPS"
[ "$(code "http://${BASE#https://}/health")" = 308 ] || [ "$(code "http://${BASE#https://}/health")" = 301 ] && ok "http redirects to https" || bad "http redirect"

echo
[ $fail = 0 ] && echo "ALL CHECKS PASSED" || { echo "SOME CHECKS FAILED"; exit 1; }
