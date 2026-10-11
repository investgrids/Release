#!/usr/bin/env bash
# Is NSE reachable from THIS server's IP? Same two-step pattern the app uses (session warm-up, then the data API), a few polite requests.
# Run ON the VPS before cutover, and again after (new IPs can be flagged later). It does not try to evade anything: ordinary headers, low volume.
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
J=$(mktemp); trap 'rm -f "$J" /tmp/nse_o.json' EXIT
echo "exit IP: $(curl -s -m 15 https://ipinfo.io/json | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d.get("ip"), d.get("city"), d.get("country"), d.get("org"))')"
echo "homepage warm-up: HTTP $(curl -s -m 25 -o /dev/null -w '%{http_code}' -c "$J" -A "$UA" https://www.nseindia.com/)   (a 403 here is common; the API below is what matters)"
call() { curl -s -m 25 -o /tmp/nse_o.json -w '%{http_code}' -b "$J" -A "$UA" -H 'Referer: https://www.nseindia.com/' -H 'Accept: application/json' "$1"; }
pass=0; total=0
for i in 1 2 3; do
  c=$(call "https://www.nseindia.com/api/corporate-announcements?index=equities"); total=$((total+1)); [ "$c" = 200 ] && pass=$((pass+1))
  n=$(python3 -c 'import json;print(len(json.load(open("/tmp/nse_o.json"))))' 2>/dev/null || echo -); echo "announcements try $i: HTTP $c items $n"; sleep 15
done
for u in corporate-board-meetings corporates-corporateActions; do
  c=$(call "https://www.nseindia.com/api/$u?index=equities"); total=$((total+1)); [ "$c" = 200 ] && pass=$((pass+1)); echo "$u: HTTP $c"; sleep 5
done
echo "RESULT: $pass/$total NSE data calls returned 200"
[ "$pass" = "$total" ]
