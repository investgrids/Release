import pickle
with open("b5_resolver_results.pkl", "rb") as f:
    results = pickle.load(f)

single = [r for r in results if len(r["matches"]) == 1]
multi = [r for r in results if len(r["matches"]) >= 2]
unlinked = [r for r in results if len(r["matches"]) == 0]

print(f"SINGLE: {len(single)}  MULTI: {len(multi)}  UNLINKED: {len(unlinked)}\n")

print("=== ALL SINGLE MATCHES ===")
for r in single:
    m = r["matches"][0]
    print(f"[{r['id'][:8]}] entity={m['entity_id']} method={m['method']} matched={m['matched_text']!r} in_title={m['in_title']}")
    print(f"   TITLE: {r['title']}")
    print(f"   SUMMARY: {r['summary'][:200]}")
    print()
