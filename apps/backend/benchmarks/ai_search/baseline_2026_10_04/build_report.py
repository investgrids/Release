"""
Applies the fixed pass/fail rules in questions.json (check_definitions) to stage1_results.json + stage2_results.json and writes results_matrix.csv and results_matrix.json.
Rules are deterministic so a later run can be scored identically. A check that could not be run is UNVERIFIED, never PASS.

Run from apps/backend:  python benchmarks/ai_search/baseline_2026_10_04/build_report.py
"""
from __future__ import annotations

import csv
import json
import os
import re
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).parent
DIR = Path(os.environ.get("BASELINE_OUT_DIR") or HERE)   # where stage1/stage2 results are read and the matrix written
Q = {q["id"]: q for q in json.loads((HERE / "questions.json").read_text(encoding="utf-8"))["questions"]}
S1 = {x["id"]: x for x in json.loads((DIR / "stage1_results.json").read_text(encoding="utf-8"))}
S2 = {x["id"]: x for x in json.loads((DIR / "stage2_results.json").read_text(encoding="utf-8"))["results"]}

PASS, FAIL, UNV = "PASS", "FAIL", "UNVERIFIED"


def ev(i):
    return S1[i].get("evidence") or {}


def tagged(i, symbols):
    return [e for e in ev(i).get("events", []) if set(e["tagged_symbols"]) & set(symbols)]


def fresh_days(i, items):
    ages = [e["age_days"] for e in items if e.get("age_days") is not None]
    return min(ages) if ages else None


# Scoring-only company names used to decide whether a filed announcement is about a company (announcement rows carry a subject, not a symbol).
ANN_TERMS = {"TCS": ["tata consultancy", "tcs"], "INFY": ["infosys"], "HDFCBANK": ["hdfc bank"], "ICICIBANK": ["icici bank"], "BEL": ["bharat electronics"],
             "HAL": ["hindustan aeronautics"], "KOTAKBANK": ["kotak"], "3MINDIA": ["3m india"]}


def anns_for(i, syms):
    return [a for a in ev(i).get("announcements", []) if any(t in a["subject"].lower() for s in syms for t in ANN_TERMS.get(s, [s.lower()]))]


def ann_age(a):
    from datetime import datetime
    try:
        return (datetime(2026, 10, 4) - datetime.fromisoformat(a["date"][:10])).days
    except Exception:
        return None


def mentions_any(i, pattern):
    e = ev(i)
    texts = [x["title"] for x in e.get("events", [])] + [x["headline"] for x in e.get("news", [])] + [x["title"] for x in e.get("policies", [])]
    return sum(1 for t in texts if re.search(pattern, t, re.I))


def check_route(i):
    s, exp = S1[i], Q[i]["expected_route"]
    if s.get("short_circuit"):
        return FAIL, f"short-circuited as {s['short_circuit']} before routing"
    ok = s.get("ui_mode") == exp["ui_mode"]
    note = f"ui_mode={s.get('ui_mode')} specialist={s.get('specialist')}"
    if ok and s.get("specialist") != exp["specialist"]:
        note += f" (specialist differs from expected {exp['specialist']}; ui_mode correct)"
    return (PASS if ok else FAIL), note


def check_entities(i):
    s, exp = S1[i], Q[i]["expected_entities"]
    if s.get("short_circuit"):
        return FAIL, f"no entities resolved ({s['short_circuit']})"
    got = s["entities"]
    gc, gs = set(got.get("companies") or []), {x.lower() for x in (got.get("sectors") or [])}
    problems = []
    if "companies" in exp:
        if gc != set(exp["companies"]):
            problems.append(f"companies {sorted(gc)} != expected {exp['companies']}")
    elif gc:
        problems.append(f"unexpected companies {sorted(gc)}")
    if "sectors" in exp:
        miss = [x for x in exp["sectors"] if x.lower() not in gs]
        if miss:
            problems.append(f"missing sectors {miss}")
        if not exp["sectors"] and gs:
            problems.append(f"unexpected sectors {sorted(gs)}")
    elif not exp.get("companies") and gs:
        problems.append(f"unexpected sectors {sorted(gs)}")
    if exp.get("policies"):
        gp = {x.lower() for x in (got.get("policies") or [])}
        miss = [x for x in exp["policies"] if x.lower() not in gp]
        if miss:
            problems.append(f"missing policies {miss}")
    return (FAIL if problems else PASS), "; ".join(problems) or "as expected"


def check_evidence(i):
    s = S1[i]
    if s.get("short_circuit"):
        return FAIL, "no evidence retrieved (short-circuit)"
    e = ev(i)
    n_ev, n_news = len(e["events"]), len(e["news"])
    syms = Q[i]["expected_entities"].get("companies", [])
    maxage = Q[i].get("max_evidence_age_days")
    notes = [f"events={n_ev} news={n_news} policies={len(e['policies'])} announcements={len(e['announcements'])} valuation={e['valuation_symbols']} sector_rows={len(e['sector_rows'])}"]
    t = Q[i]["type"]
    if t == "company_comparison":
        both = [sym for sym in syms if tagged(i, [sym]) or anns_for(i, [sym])]
        val_ok = all(sym in e["valuation_symbols"] for sym in syms)
        if len(both) < len(syms):
            notes.append(f"events/announcements cover only {both} of {syms}")
        if not val_ok:
            notes.append("valuation missing for at least one side")
        old = fresh_days(i, e["events"])
        if old is not None and old > 30:
            notes.append(f"newest event {old} days old")
        return (PASS if len(both) == len(syms) and val_ok else FAIL), "; ".join(notes)
    if t == "company_research" or (t == "event_impact" and syms):
        mine = tagged(i, syms)
        resolved = set(S1[i]["entities"]["companies"] or [])
        if resolved != set(syms):
            notes.append(f"evidence is for resolved companies {sorted(resolved)}, not {syms}")
            return FAIL, "; ".join(notes)
        anns = anns_for(i, syms)
        if not mine and not anns:
            return FAIL, "; ".join(notes + [f"no event/announcement tied to {syms}"])
        ages = [a for a in [fresh_days(i, mine)] + [ann_age(x) for x in anns] if a is not None]
        age = min(ages) if ages else None
        if maxage and age is not None and age > maxage:
            return FAIL, "; ".join(notes + [f"newest company evidence {age} days old (> {maxage})"])
        if age is not None and age > 30:
            notes.append(f"STALE: newest company evidence is {age} days old")
        return PASS, "; ".join(notes)
    if i in ("EI3", "SR1"):
        hit = sum(1 for x in e["events"] if re.search(r"bank|credit|loan|nbfc|lend", x["title"], re.I))
        row = any(re.search(r"bank", x["name"], re.I) for x in e["sector_rows"])
        notes.append(f"bank-related events {hit}/{n_ev}; banking sector row={'yes' if row else 'no'}")
        return (PASS if (row and hit) else FAIL), "; ".join(notes)
    if i == "SR2":
        row = any(re.fullmatch(r"IT|Technology", x["name"]) for x in e["sector_rows"])
        hit = sum(1 for x in e["events"] if re.search(r"\bIT\b|software|tech|infosys|tcs|wipro|hcl", x["title"], re.I))
        notes.append(f"IT-related events {hit}/{n_ev}; IT sector row={'yes' if row else 'no'}")
        return (PASS if (row and hit) else FAIL), "; ".join(notes)
    if i == "SR3":
        if not e["sector_rows"]:
            return FAIL, "; ".join(notes + ["no live sector rows retrieved"])
        return PASS, "; ".join(notes + ["live sector rows retrieved (naming the weakest sectors from them is an answer-level check)"])
    if i == "MP1":
        rbi = mentions_any(i, r"rbi|repo|monetary")
        macro = bool(e["macro_indices"] or e["sector_rows"])
        notes.append(f"RBI/repo items {rbi}; macro indices or sector rows={'yes' if macro else 'no'}")
        return (PASS if (rbi and macro) else FAIL), "; ".join(notes)
    if i == "MP3":
        fx = mentions_any(i, r"rupee|usd/?inr|dollar")
        it = mentions_any(i, r"\bIT\b|software|infosys|tcs|wipro|hcl|tech mahindra|nasdaq")
        macro = bool(e["macro_indices"]) or fx > 0
        notes.append(f"rupee/FX items {fx}; IT-linked items {it}; macro indices={bool(e['macro_indices'])}")
        return (PASS if (macro and it) else FAIL), "; ".join(notes)
    if i == "MP2":
        hit = sum(1 for x in e["events"] if re.search(r"crude|oil|brent|opec|energy", x["title"], re.I))
        hist_blank = any(not h["title"] for h in e["historical"])
        notes.append(f"crude-related events {hit}/{n_ev}; macro indices={e['macro_indices']}" + ("; historical precedent has an empty title" if hist_blank else ""))
        return (PASS if (hit and e["macro_indices"]) else FAIL), "; ".join(notes)
    if t == "general_explanation":
        noise = []
        if n_ev and not tagged(i, syms):
            noise.append(f"{n_ev} unrelated events and {len(e['policies'])} policy items injected into an educational question")
        return PASS, "; ".join(notes + noise + ["no evidence required"])
    return UNV, "no rule"


def synth(i):
    return S2.get(i, {})


def check_addresses(i):
    r = synth(i)
    if r.get("degraded_reason") in ("ambiguous_entity", "unsupported_entity"):
        return FAIL, f"user got a '{r['degraded_reason']}' message instead of an answer"
    return UNV, "no synthesized answer produced (all model providers exhausted locally)"


def check_degraded_honesty(i):
    r = synth(i)
    if not r.get("synthesis_incomplete"):
        return UNV, "response was not degraded"
    bad = r.get("fabricated_when_degraded")
    return (FAIL if bad else PASS), f"degraded_reason={r.get('degraded_reason')}; verdict/confidence/companies/picks present={bad}"


def check_degraded_surface(i):
    """Extra check (not in the original definitions): the degraded response must not promise evidence it does not show."""
    r = synth(i)
    if r.get("degraded_reason") != "capacity":
        return UNV, "n/a"
    retrieved = len(ev(i).get("events", [])) + len(ev(i).get("news", [])) + len(ev(i).get("policies", []))
    shown = (r["attribution"]["related_events_shown"] or 0) + (r["attribution"]["news_shown"] or 0)
    claimed = (r.get("answer_availability") or {}).get("evidence_count")
    promise = "available below" in (r.get("summary") or "")
    bad = promise and shown == 0
    return (FAIL if bad else PASS), f"retrieved {retrieved}, shown {shown}, availability.evidence_count={claimed}, copy says 'available below'={promise}"


ROWS = []
for i, q in Q.items():
    row = {"id": i, "type": q["type"], "query": q["query"]}
    for name, fn in (("route", check_route), ("entities", check_entities), ("evidence", check_evidence), ("addresses_question", check_addresses), ("degraded_honesty", check_degraded_honesty),
                     ("degraded_copy_vs_evidence", check_degraded_surface)):
        status, note = fn(i)
        row[name], row[name + "_note"] = status, note
    for name in ("numbers_supported", "citations", "score_consistency"):
        row[name], row[name + "_note"] = UNV, "no synthesized answer to inspect (live model calls failed: provider capacity)"
    s2 = synth(i)
    row.update({"route_selected": f"{S1[i].get('specialist') or '-'} / {S1[i].get('ui_mode') or S1[i].get('short_circuit')}",
                "degraded_state": s2.get("degraded_reason") or "none", "availability": (s2.get("answer_availability") or {}).get("state"),
                "latency_s_live": s2.get("latency_s"), "retrieval_s": S1[i].get("elapsed_s"), "model_calls": s2.get("model_call_count"), "evidence_items": (
                    len(ev(i).get("events", [])) + len(ev(i).get("news", [])) + len(ev(i).get("policies", [])) + len(ev(i).get("announcements", []))) if ev(i) else 0})
    ROWS.append(row)

CHECKS = ["route", "entities", "evidence", "addresses_question", "numbers_supported", "citations", "score_consistency", "degraded_honesty", "degraded_copy_vs_evidence"]
with open(DIR / "results_matrix.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["id", "type", "query", *CHECKS, "route_selected", "degraded_state", "availability", "latency_s_live", "retrieval_s", "model_calls", "evidence_items"])
    for r in ROWS:
        w.writerow([r["id"], r["type"], r["query"], *[r[c] for c in CHECKS], r["route_selected"], r["degraded_state"], r["availability"], r["latency_s_live"], r["retrieval_s"], r["model_calls"], r["evidence_items"]])
(DIR / "results_matrix.json").write_text(json.dumps(ROWS, indent=2, ensure_ascii=False), encoding="utf-8")

by = defaultdict(lambda: defaultdict(Counter))
for r in ROWS:
    for c in CHECKS:
        by[r["type"]][c][r[c]] += 1
print(f'{"type":20}', *[f"{c[:11]:>12}" for c in CHECKS])
for t, d in by.items():
    print(f"{t:20}", *[f'{d[c][PASS]}P/{d[c][FAIL]}F/{d[c][UNV]}U'.rjust(12) for c in CHECKS])
tot = {c: Counter(r[c] for r in ROWS) for c in CHECKS}
print(f'{"TOTAL (18)":20}', *[f'{tot[c][PASS]}P/{tot[c][FAIL]}F/{tot[c][UNV]}U'.rjust(12) for c in CHECKS])
for r in ROWS:
    print(r["id"], "|", r["route"], r["entities"], r["evidence"], "|", r["route_note"][:60], "|", r["entities_note"][:70])
