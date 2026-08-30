import pickle
with open("b5_resolver_results_v4.pkl", "rb") as f:
    results = pickle.load(f)
multi = [r for r in results if len(r["matches"]) >= 2]
with open("b5_v4_multi_dump.txt", "w", encoding="utf-8") as out:
    out.write(f"MULTI: {len(multi)}\n")
    for r in multi:
        ids = [(m["entity_id"], m["method"], m["matched_text"]) for m in r["matches"]]
        out.write(f"[{r['id'][:8]}] {ids}\n")
        out.write(f"   TITLE: {r['title'][:160]!r}\n")
        out.write(f"   SUMMARY: {r['summary'][:260]!r}\n")
print("done")
