import pickle
with open("b5_resolver_results_v4.pkl", "rb") as f:
    results = pickle.load(f)
single = [r for r in results if len(r["matches"]) == 1]
with open("b5_v4_single_dump.txt", "w", encoding="utf-8") as out:
    out.write(f"SINGLE: {len(single)}\n")
    for r in single:
        m = r["matches"][0]
        out.write(f"[{r['id'][:8]}] entity={m['entity_id']} method={m['method']} matched={m['matched_text']!r} in_title={m['in_title']}\n")
        out.write(f"   TITLE: {r['title'][:160]!r}\n")
        out.write(f"   SUMMARY: {r['summary'][:260]!r}\n")
print("done")
