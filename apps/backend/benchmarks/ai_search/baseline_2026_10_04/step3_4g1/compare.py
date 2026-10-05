"""Step 3.4G.1: before/after comparison of the frozen-18 selection snapshots. Reads selection_before.json and selection_after.json; writes comparison.md. No provider calls."""
import json
import re
from pathlib import Path

HERE = Path(__file__).parent
B = {r["id"]: r for r in json.loads((HERE / "selection_before.json").read_text(encoding="utf-8"))["results"]}
A = {r["id"]: r for r in json.loads((HERE / "selection_after.json").read_text(encoding="utf-8"))["results"]}
out = []


_BP = re.compile(r"^.*?\bhas\s+informed\s+the\s+exchange\s+(?:about|regarding)\b", re.I | re.S)
_STOP = {"the", "and", "for", "with", "from", "that", "this", "has", "are", "was", "after", "its", "his", "her"}


def _words(t):
    t = re.sub(r"\blimited\b", " ", _BP.sub(" ", t or ""), flags=re.I)
    return {w for w in re.findall(r"[a-z0-9&]+", t.lower()) if len(w) >= 3 and w not in _STOP}


def dups(rec):
    ts = [x["title"] for k in ("events", "news", "announcements") for x in rec[k]]
    ws = [_words(t) for t in ts]
    return sum(1 for i in range(len(ws)) for j in range(i + 1, len(ws)) if len(ws[i] & ws[j]) / max(1, len(ws[i] | ws[j])) >= 0.5)


def titles(r, kind):
    return [x["title"] for x in r[kind]]


def short(t, n=88):
    return (t or "")[:n]


# 1. global invariants ------------------------------------------------------------------------------------------------------------------
out.append("## Global invariants (18 questions)\n")
out.append("| ID | UI mode same | entities same | Gate A same | would-call same | events b>a | news b>a | ann b>a | dups b>a | median age b>a (d) | admin items b>a | topical-tag items b>a |")
out.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
route_ok = ents_ok = gate_ok = call_ok = True
for qid in B:
    b, a = B[qid], A[qid]
    r1, r2, r3, r4 = b["ui_mode"] == a["ui_mode"] and b["specialist"] == a["specialist"], b["entities"] == a["entities"], b["gate_a"] == a["gate_a"], b["would_call_model"] == a["would_call_model"]
    route_ok &= r1; ents_ok &= r2; gate_ok &= r3; call_ok &= r4
    tb = b["tag_counts"]; ta = a["tag_counts"]
    top_b = tb["operating_result"] + tb["outlook_demand"] + tb["rate_policy"]
    top_a = ta["operating_result"] + ta["outlook_demand"] + ta["rate_policy"]
    out.append(f"| {qid} | {'yes' if r1 else '**NO**'} | {'yes' if r2 else '**NO**'} | {'yes' if r3 else '**NO**'} | {'yes' if r4 else '**NO**'} | {b['counts']['events']}>{a['counts']['events']} | {b['counts']['news']}>{a['counts']['news']} | "
               f"{b['counts']['announcements']}>{a['counts']['announcements']} | {dups(b)}>{dups(a)} | {b['freshness_median_days']}>{a['freshness_median_days']} | {tb['administrative']}>{ta['administrative']} | {top_b}>{top_a} |")
out.append(f"\nRoute unchanged for all 18: **{route_ok}**. Entities unchanged: **{ents_ok}**. Gate A decision unchanged: **{gate_ok}**. Model-call population unchanged: **{call_ok}**.\n")

# 2. displaced and newly selected, per question ------------------------------------------------------------------------------------------
out.append("## Selected-evidence deltas per question (items in only one snapshot)\n")
displaced_useful = []
for qid in B:
    b, a = B[qid], A[qid]
    lines = []
    for kind in ("events", "news", "announcements"):
        tb, ta = {x["title"]: x for x in b[kind]}, {x["title"]: x for x in a[kind]}
        gone = [t for t in tb if t not in ta]
        new = [t for t in ta if t not in tb]
        for t in gone:
            x = tb[t]
            lines.append(f"  - OUT {kind[:-1]}: {short(t)!r} tags={x['tags']} age={x['age_days']}d in_prompt={x['in_prompt']}")
            if set(x["tags"]) & {"operating_result", "outlook_demand", "rate_policy"}:
                displaced_useful.append((qid, kind, t, x["tags"]))
        for t in new:
            x = ta[t]
            lines.append(f"  - IN  {kind[:-1]}: {short(t)!r} tags={x['tags']} age={x['age_days']}d in_prompt={x['in_prompt']}")
    if lines:
        out.append(f"**{qid}** ({B[qid]['query'][:60]})")
        out += lines
out.append("")

# 3. order changes (evidence IDs) -----------------------------------------------------------------------------------------------------
out.append("## Order of what the model is shown (prompt-visible events/news/announcements, first 6 each)\n")
for qid in ("CR1", "SR2", "MP1", "CC2"):
    out.append(f"**{qid}**")
    for label, R in (("before", B[qid]), ("after ", A[qid])):
        for kind in ("events", "news", "announcements"):
            vis = [short(x["title"], 70) for x in R[kind] if x["in_prompt"]][:6]
            out.append(f"- {label} {kind:<13} visible={sum(1 for x in R[kind] if x['in_prompt'])}/{len(R[kind])}: {vis}")
    out.append("")

# 4. target specimens ---------------------------------------------------------------------------------------------------------------
out.append("## Target specimens\n")
def has(r, kind, needle):
    return [x for x in r[kind] if needle.lower() in x["title"].lower()]
checks = [("SR2", "events", "crashes 11%"), ("SR2", "news", "reality check"), ("SR2", "news", "earnings dilemma"), ("SR2", "events", "Q2 Results Dates"), ("SR2", "news", "Accenture Q4 revenue, outlook"),
          ("MP1", "events", "MPC may hike"), ("MP1", "events", "MPC Meeting October"), ("MP1", "events", "bond yields"), ("MP1", "events", "Rate Hike Bets"), ("MP1", "news", "RBI MPC"),
          ("CR1", "announcements", "Investor Presentation"), ("CR1", "announcements", "General Updates")]
out.append("| Q | item | before selected / visible | after selected / visible |")
out.append("|---|---|---|---|")
for qid, kind, needle in checks:
    hb, ha = has(B[qid], kind, needle), has(A[qid], kind, needle)
    f = lambda h: "no" if not h else f"yes ({len(h)}) / " + ("visible" if any(x["in_prompt"] for x in h) else "not visible")
    out.append(f"| {qid} | {kind[:-1]}: *{needle}* | {f(hb)} | {f(ha)} |")
out.append("")

# 5. rank components -------------------------------------------------------------------------------------------------------------------
out.append("## Rank components of the top selected items (after)\n")
for qid in ("SR2", "MP1", "CR1"):
    rt = A[qid].get("rank_trace") or {}
    out.append(f"**{qid}**")
    for kind in ("events", "news", "announcements"):
        sel = [t for t in rt.get(kind, []) if t["selected"]][:6]
        for t in sel:
            out.append(f"- {kind[:-1]:<12} score {t['score']:.2f} (coverage {t['coverage']:.2f}, recency {t['recency']:.2f}, substance {t['substance']:.2f}, impact {t['impact']:.2f}) {'DUP-DEFERRED' if t.get('duplicate_deferred') else ''} {short(t['title'], 80)!r}")
    out.append("")

out.append("## Previously useful (topical-tagged) items displaced from the selection\n")
if displaced_useful:
    for q, k, t, tg in displaced_useful:
        out.append(f"- {q} {k[:-1]}: {short(t, 90)!r} tags={tg}")
else:
    out.append("- none")
(HERE / "comparison.md").write_text("\n".join(out) + "\n", encoding="utf-8")
print("\n".join(out))
