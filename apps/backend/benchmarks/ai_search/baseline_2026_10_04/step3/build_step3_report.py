"""
Merges answers.json + auto_checks.json (automatic checks) with manual_review.json (the reviewer's verdict per question and check, each with a reason) into the Step 3
answer-level matrix. Rules:
  * No real answer (capacity-degraded, crashed, skipped) -> every answer-level check is UNVERIFIED. Never PASS.
  * A manual verdict, when present, overrides the automatic suggestion and must carry a reason.
  * Without a manual verdict the automatic result is only a SUGGESTION and is reported as UNVERIFIED (nothing is passed on an unreviewed flag count).

Run from apps/backend:  python benchmarks/ai_search/baseline_2026_10_04/step3/build_step3_report.py
"""
from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).parent
CHECKS = ["addresses_question", "numbers_supported", "claims_source_eligible", "dates_and_recency", "citations", "score_and_rank", "insufficient_evidence_honesty"]
answers = json.loads((HERE / "answers.json").read_text(encoding="utf-8"))["results"]
auto = json.loads((HERE / "auto_checks.json").read_text(encoding="utf-8"))
manual_path = HERE / "manual_review.json"
manual = json.loads(manual_path.read_text(encoding="utf-8")) if manual_path.exists() else {}
Q = {q["id"]: q for q in json.loads((HERE.parent / "questions.json").read_text(encoding="utf-8"))["questions"]}

rows = []
for qid, q in Q.items():
    a = auto[qid]
    row = {"id": qid, "type": q["type"], "query": q["query"], "answer_exists": a["answer_exists"]}
    for c in CHECKS:
        m = (manual.get(qid) or {}).get(c)
        if not a["answer_exists"]:
            row[c], row[c + "_note"] = "UNVERIFIED", f"no real answer ({a.get('reason')})"
        elif m:
            row[c], row[c + "_note"] = m[0], m[1]
        else:
            row[c], row[c + "_note"] = "UNVERIFIED", "not manually reviewed"
    rec = answers[qid]
    row.update({"latency_s": rec.get("latency_s"), "model_calls": rec.get("model_call_count"), "evidence_items": a.get("evidence_total"),
                "auto_unsupported_numbers": len(a.get("unsupported_numbers") or []) if a["answer_exists"] else None,
                "auto_ineligible_claims": len((a.get("claims") or {}).get("ineligible_only") or []) if a["answer_exists"] else None,
                "auto_unsupported_claims": len((a.get("claims") or {}).get("unsupported") or []) if a["answer_exists"] else None})
    rows.append(row)

with open(HERE / "step3_matrix.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["id", "type", "query", "answer_exists", *CHECKS, "latency_s", "model_calls", "evidence_items", "auto_unsupported_numbers", "auto_ineligible_claims", "auto_unsupported_claims"])
    for r in rows:
        w.writerow([r["id"], r["type"], r["query"], r["answer_exists"], *[r[c] for c in CHECKS], r["latency_s"], r["model_calls"], r["evidence_items"], r["auto_unsupported_numbers"],
                    r["auto_ineligible_claims"], r["auto_unsupported_claims"]])
(HERE / "step3_matrix.json").write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")

by = defaultdict(lambda: defaultdict(Counter))
for r in rows:
    for c in CHECKS:
        by[r["type"]][c][r[c]] += 1
print(f'{"type":20}', *[c[:14].rjust(15) for c in CHECKS])
for t, d in by.items():
    print(f"{t:20}", *[f'{d[c]["PASS"]}P/{d[c]["FAIL"]}F/{d[c]["UNVERIFIED"]}U'.rjust(15) for c in CHECKS])
tot = {c: Counter(r[c] for r in rows) for c in CHECKS}
print(f'{"TOTAL":20}', *[f'{tot[c]["PASS"]}P/{tot[c]["FAIL"]}F/{tot[c]["UNVERIFIED"]}U'.rjust(15) for c in CHECKS])
print("answers produced:", sum(r["answer_exists"] for r in rows), "of", len(rows))
