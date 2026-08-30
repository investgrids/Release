import pickle
with open("b5_resolver_results.pkl", "rb") as f:
    results = pickle.load(f)

unlinked = [r for r in results if len(r["matches"]) == 0]
print(f"UNLINKED total: {len(unlinked)}\n")
for r in unlinked[100:140]:
    print(f"[{r['id'][:8]}] TITLE: {r['title']}")
    print(f"   SUMMARY: {r['summary'][:180]}")
    print()
