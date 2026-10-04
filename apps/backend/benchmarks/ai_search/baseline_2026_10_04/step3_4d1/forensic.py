"""
Step 3.4D-1: CC1 live rejection forensic. Reads ONLY the saved Step 3.4C artifact (openai_qualification.json). No provider call, no pipeline run, no app change.
Re-applies the committed Gate B validators (unchanged) to the saved rejected generation and the saved evidence index, then reconciles every factual sentence and every claim_sources entry.

Run from apps/backend:  PYTHONPATH=. python benchmarks/ai_search/baseline_2026_10_04/step3_4d1/forensic.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, ".")
HERE = Path(__file__).parent
ART = HERE.parent / "step3_4c" / "openai_qualification.json"

from app.api.companies import _NSE_UNIVERSE  # noqa: E402
from app.services.ai_search import claim_sources as CS  # noqa: E402
from app.services.ai_search import figures as FG  # noqa: E402

d = json.loads(ART.read_text(encoding="utf-8"))
r = d["results"]["CC1"]
gen = r["rejected_generation"][0]["generation"]
ev = r["evidence"]
index = ev["index"]
ents = {"companies": r["entities"]["companies"], "sectors": r["entities"]["sectors"], "policies": r["entities"]["policies"]}
call = [c for c in r["calls"] if "refused" not in c][0]

out: dict = {"query": r["query"], "gate_b_saved": r["gate_b"], "usage": call["usage"], "reasoning_tokens": call["reasoning_tokens"], "finish_reason": call["finish_reason"],
             "output_chars": call["output_chars"], "latency_ms": call["latency_ms"]}

# ── 1. re-run the committed validators on the saved generation (no change to them) ─────────────────────────────────────────────
cv = CS.validate_claim_sources(gen.get("claim_sources"), index, gen, ents, _NSE_UNIVERSE, ev.get("premise"))
facts = CS.factual_sentences(gen)
pieces = CS.answer_pieces(gen)
out["validator"] = {"status": cv["status"], "summary": cv["summary"], "claims": cv["claims"], "uncovered": cv.get("uncovered")}
out["factual_sentences"] = facts
out["answer_pieces"] = [{"piece": p, "sentences": CS._sentences(p)} for p in pieces]

# ── 2. reconcile each claim <-> each factual sentence with the committed matcher and with raw token overlap (diagnostic only) ──
claims = [c for c in (gen.get("claim_sources") or []) if isinstance(c, dict)]
hay = CS._norm(" ".join(pieces))


def toks(s):
    return set(CS._TOKEN_RE.findall(CS._norm(s)))


def jac(a, b):
    ta, tb = toks(a), toks(b)
    return round(len(ta & tb) / max(1, len(ta | tb)), 2)


rows = []
for s in facts:
    best = max(((jac(s, c["claim"]), i) for i, c in enumerate(claims)), default=(0, None))
    exact = [i for i, c in enumerate(claims) if CS._norm(c["claim"]) in CS._norm(s) or CS._norm(s) in CS._norm(c["claim"])]
    rows.append({"sentence": s, "committed_similar_match": [i for i, c in enumerate(claims) if CS.similar(s, c["claim"])], "exact_substring_match": exact, "best_jaccard": best[0], "best_claim_index": best[1]})
out["sentence_reconciliation"] = rows
crow = []
for i, c in enumerate(claims):
    in_answer = CS._norm(c["claim"]) in hay
    fuzzy = any(CS.similar(s, c["claim"]) for p in pieces for s in CS._sentences(p))
    srcs = []
    for sid in c.get("sources", []):
        e = next((x for x in index if x["id"] == sid), None)
        srcs.append({"id": sid, "found": bool(e), "kind": (e or {}).get("kind"), "text": ((e or {}).get("title") or (e or {}).get("text") or str(e))[:200] if e else None})
    crow.append({"index": i, "claim": c["claim"], "sources": srcs, "verbatim_in_answer": in_answer, "committed_similar_in_answer": fuzzy})
out["claim_reconciliation"] = crow

# ── 3. figures gate on this generation (it passed: 0 unsupported) ────────────────────────────────────────────────────────────────
from app.services.ai_search import answer_authorization as AA  # noqa: E402,F401
corpus = " ".join(str(x) for x in [json.dumps(index, default=str), json.dumps(ev.get("valuation"), default=str), " ".join(ev.get("context_lines") or []) if isinstance(ev.get("context_lines"), list) else str(ev.get("context_lines"))])
out["figures_unsupported_vs_saved_index_and_valuation"] = FG.unsupported_figures(gen, corpus, r["query"])

# ── 4. payload structure: chars per top-level key ───────────────────────────────────────────────────────────────────────────────
out["payload_chars"] = {k: len(json.dumps(v, ensure_ascii=False)) for k, v in gen.items()}
out["payload_chars_total_parsed"] = sum(out["payload_chars"].values())
out["raw_output_chars"] = call["output_chars"]

# ── 5. saved evidence: every item the model could cite ────────────────────────────────────────────────────────────────────────────
out["evidence_index"] = index
out["evidence_valuation"] = ev.get("valuation")
out["evidence_context_lines"] = ev.get("context_lines")
(HERE / "forensic.json").write_text(json.dumps(out, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

print("validator:", cv["status"], "|", cv["summary"])
print("factual sentences:", len(facts), "| claims:", len(claims))
for row in rows:
    print(f'S: {row["sentence"][:110]!r} similar={row["committed_similar_match"]} exact={row["exact_substring_match"]} bestJ={row["best_jaccard"]}@{row["best_claim_index"]}')
for c in crow:
    print(f'C{c["index"]}: verbatim={c["verbatim_in_answer"]} similar={c["committed_similar_in_answer"]} src={[s["id"] for s in c["sources"]]} :: {c["claim"][:90]!r}')
print("uncovered:", cv.get("uncovered"))
print("figures unsupported:", out["figures_unsupported_vs_saved_index_and_valuation"])
print("payload chars:", out["payload_chars_total_parsed"], "raw:", out["raw_output_chars"])
