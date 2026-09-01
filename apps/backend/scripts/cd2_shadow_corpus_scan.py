"""
P0-CD2 Generation Containment — retrospective shadow-corpus scan (read-only).

Not a new generation batch (no LLM calls, no cost, no publish risk) — pulls
a real, stratified sample of EXISTING published articles across every real
article type from the local dev backend and runs the new CD2 validators
(scan_recommendation_language, normalize_symbol) against their already-
stored fields, exactly as they'd have run at generation time. This answers
"how much of the existing corpus would the new gate have caught" without
generating anything new or touching production.
"""
import sys
sys.path.insert(0, ".")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import json
import requests

from app.services.aipe.recommendation_language import scan_recommendation_language
from app.services.symbol_normalization import normalize_symbol

API = "http://localhost:8001"
PER_TYPE_SAMPLE = 15

session = requests.Session()

print("=== Fetching article list ===")
articles = []
for offset in (0, 100, 200, 300, 400, 500):
    resp = session.get(f"{API}/api/publishing/articles", params={"limit": 100, "offset": offset}, timeout=30)
    resp.raise_for_status()
    batch = resp.json()["articles"]
    articles.extend(batch)
    if len(batch) < 100:
        break
print(f"Total articles: {len(articles)}")

by_type: dict[str, list] = {}
for a in articles:
    by_type.setdefault(a["article_type"], []).append(a)

sample = []
for t, rows in by_type.items():
    sample.extend(rows[:PER_TYPE_SAMPLE])
print(f"Stratified sample size: {len(sample)} across {len(by_type)} types\n")

rec_violations_by_type: dict[str, int] = {}
rec_examples = []
symbol_changes_by_type: dict[str, int] = {}
symbol_examples = []
fetched = 0

for row in sample:
    slug = row["slug"]
    try:
        detail = session.get(f"{API}/api/insights/{slug}", timeout=20).json()
    except Exception as e:
        print(f"  SKIP {slug}: fetch failed ({e})")
        continue
    fetched += 1
    t = row["article_type"]

    violations = scan_recommendation_language(detail)
    if violations:
        rec_violations_by_type[t] = rec_violations_by_type.get(t, 0) + 1
        if len(rec_examples) < 12:
            rec_examples.append((t, slug, violations))

    for c in (detail.get("companies_affected") or []):
        old_sym = c.get("symbol")
        new_sym = normalize_symbol(old_sym, c.get("name"))
        if new_sym != old_sym:
            symbol_changes_by_type[t] = symbol_changes_by_type.get(t, 0) + 1
            if len(symbol_examples) < 12:
                symbol_examples.append((t, slug, c.get("name"), old_sym, new_sym))

print(f"Fetched detail for {fetched}/{len(sample)} sampled articles\n")

print("=== Recommendation-language violations (would have been publish-blocking under CD2) ===")
print(f"Articles with >=1 violation: {sum(rec_violations_by_type.values())} / {fetched}")
print(json.dumps(rec_violations_by_type, indent=2))
print("\nExamples:")
for t, slug, v in rec_examples:
    print(f"  [{t}] {slug}")
    for x in v:
        print(f"      {x}")

print("\n=== Entity resolution changes (symbol would now differ / null out) ===")
print(f"Articles with >=1 symbol change: {sum(symbol_changes_by_type.values())} / {fetched}")
print(json.dumps(symbol_changes_by_type, indent=2))
print("\nExamples (name -> old_symbol -> new_symbol):")
for t, slug, name, old, new in symbol_examples:
    print(f"  [{t}] {slug}: {name!r}: {old!r} -> {new!r}")
