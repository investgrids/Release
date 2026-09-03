import pickle, random
with open("b5_resolver_results_v4.pkl", "rb") as f:
    results = pickle.load(f)
unlinked = [r for r in results if len(r["matches"]) == 0]
random.seed(42)
sample = random.sample(unlinked, min(40, len(unlinked)))
with open("b5_v4_unlinked_sample.txt", "w", encoding="utf-8") as out:
    out.write(f"UNLINKED total: {len(unlinked)}, sample: {len(sample)}\n")
    for r in sample:
        out.write(f"[{r['id'][:8]}] TITLE: {r['title'][:160]!r}\n")
        out.write(f"   SUMMARY: {r['summary'][:220]!r}\n")
print("done")
