"""
Step 4C audit: the PUBLIC response field matrix for representative cases A to H. ZERO provider calls: A and B are saved authorized live responses (step3_4c artifacts; a real assembly needs live market data);
C to H run through the real pipeline and the real finalizer with deterministic fixtures and the provider function set to raise.
  PYTHONIOENCODING=utf-8 PYTHONPATH=. python benchmarks/ai_search/baseline_2026_10_04/step4c/field_matrix.py [label]     # label: before | after
Writes field_matrix_<label>.json and .md next to this file.
"""
from __future__ import annotations

import asyncio
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, ".")
HERE = Path(__file__).parent
LABEL = sys.argv[1] if len(sys.argv) > 1 else "run"
ART = HERE.parent / "step3_4c"

from app.services import ai_service as S  # noqa: E402
from app.services import request_deadline as RD  # noqa: E402
from app.services.ai_search import market_pulse as mp_mod  # noqa: E402
from app.services.ai_search import pipeline as P  # noqa: E402
from app.services.ai_search.response_finalize import finalize_v3_response  # noqa: E402
from tests.services.test_ai_search_fail_closed import bundle, good_generation, tcs_bundle  # noqa: E402


async def _boom(*a, **k):
    raise AssertionError("provider call")


async def _no_cls(q):
    return False

S._call_with_fallback = _boom
mp_mod._call_with_fallback = _boom
mp_mod._classify_market_pulse_llm = _no_cls
P.cache_mod.get_response = lambda *a, **k: None
P.cache_mod.set_response = lambda *a, **k: None

STATE = {"gen": None, "bundle": None, "slow": False}


def _stub(kind):
    async def run(query, evidence, intent_data, entities):
        return STATE["gen"] or ({"_degraded_reason": "capacity"}, True)
    return run

for _n in ("company_specialist", "comparison_specialist", "sector_specialist"):
    setattr(getattr(P, _n), "run", _stub(_n))


async def _collect(query, intent_data, entities, db):
    if STATE["slow"]:
        await asyncio.sleep(60)
    return STATE["bundle"]

P.evidence_mod.collect = _collect


def go(query: str, *, bundle_=None, gen=None, slow=False, deadline=False):
    STATE.update(bundle=bundle_, gen=gen, slow=slow)

    async def run():
        if deadline:
            with RD.scope(total=3.0, reserve=0.5, min_attempt=1.0, attempt_cap=1.0):
                raw, was_cached = await P.run_ai_search_v3(query, None)
        else:
            raw, was_cached = await P.run_ai_search_v3(query, None)
        return finalize_v3_response(query, raw, x_admin_key=None, was_cached=was_cached)
    return asyncio.run(run())


def pick(res: dict) -> dict:
    a = res.get("answer") or {}
    v = res.get("investment_verdict") or {}
    cd = res.get("confidence_data") or {}
    es = res.get("evidence_score") or {}
    text = json.dumps(res, ensure_ascii=False)
    counts_in_text = sorted(set(re.findall(r"\b\d+\s+(?:trusted\s+|verified\s+|independent\s+)?(?:sources?|events?|articles?|items?)\b", text)))
    return {
        "answer_availability": res.get("answer_availability"),
        "degraded_reason": res.get("degraded_reason"), "synthesis_incomplete": res.get("synthesis_incomplete"),
        "specialist": res.get("specialist"), "ui_mode": res.get("ui_mode"),
        "answer.confidence": a.get("confidence"), "answer.confidence_level": a.get("confidence_level"), "answer.sentiment": a.get("sentiment"), "answer.sources_count": a.get("sources_count"),
        "verdict.rating": v.get("rating"), "verdict.direction": v.get("direction"), "verdict.confidence": v.get("confidence"), "verdict.horizon": v.get("horizon"),
        "verdict.risk_level": v.get("risk_level"), "verdict.verdict_basis": v.get("verdict_basis"), "verdict.engine_verdict_public": v.get("engine_verdict") is not None,
        "confidence_data.level": cd.get("level"), "confidence_data.score": cd.get("score"), "confidence_data.reasons": cd.get("reasons"),
        "confidence_breakdown": res.get("confidence_breakdown"), "confidence": res.get("confidence"),
        "evidence_score": {k: es.get(k) for k in ("stars", "source_count", "development_count", "corroborating_source_count")},
        "list_counts": {"related_events": len(res.get("related_events") or []), "news": len(res.get("news") or []), "policies": len(res.get("policies") or [])},
        "human_readable_counts": counts_in_text,
        "public_title": res.get("public_title"), "evidence_sufficiency.status": (res.get("evidence_sufficiency") or {}).get("status"),
        "summary_head": (a.get("summary") or "")[:140], "education": res.get("education"),
    }


def saved(file: str, qid: str) -> dict:
    """A saved authorized live response, re-finalized through the CURRENT finalizer (the public-count and availability rules live there) and with the CURRENT confidence-copy rule applied to its reasons,
    so the matrix shows the present contract for it. The answer text, claims and verdict fields are the saved ones."""
    import copy
    r = copy.deepcopy(json.loads((ART / file).read_text(encoding="utf-8"))["results"][qid]["response"])
    return finalize_v3_response(qid, r, x_admin_key=None, was_cached=True)      # (Step 5: the confidence copy rewrite this used to apply no longer exists; the finalizer enforces the public contract)


CASES = [
    ("A authorized evidence-backed (saved EI3, sector)", lambda: saved("openai_3_4g2.json", "EI3")),
    ("B authorized partial scope (saved CC2, valuation-only comparison)", lambda: saved("openai_3_4g1.json", "CC2")),
    ("C Gate A insufficient evidence (retrieval succeeded, nothing found)", lambda: go("How is 3M India doing as a business?", bundle_=bundle())),
    ("C2 Gate A insufficient, but a source FAILED during retrieval", lambda: go("How is 3M India doing as a business?", bundle_=_failed_bundle())),
    ("D retrieval cut off by the deadline", lambda: go("What is happening with TCS lately?", bundle_=tcs_bundle(), slow=True, deadline=True)),
    ("E provider capacity failure", lambda: go("What is happening with TCS lately?", bundle_=tcs_bundle())),
    ("F Gate B rejection", lambda: go("What is happening with TCS lately?", bundle_=tcs_bundle(), gen=(good_generation(claim_sources=[]), False))),
    ("G educational (GE1)", lambda: go("What is a P/E ratio and how should I read it?")),
    ("H product knowledge (GE3)", lambda: go("How does the MarketRipple Score work?")),
]


def _failed_bundle():
    b = bundle()
    b.retrieval_failures = {"news": "LiveNewsUnavailable"}
    return b


def main():
    out = {}
    for label, fn in CASES:
        try:
            out[label] = pick(fn())
        except Exception as exc:                                   # an audit row must never abort the others
            out[label] = {"error": type(exc).__name__ + ": " + str(exc)[:160]}
    (HERE / f"field_matrix_{LABEL}.json").write_text(json.dumps(out, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    for label, row in out.items():
        print("\n== " + label)
        for k, v in row.items():
            print(f"   {k:34s} {v!r}"[:230])

main()
