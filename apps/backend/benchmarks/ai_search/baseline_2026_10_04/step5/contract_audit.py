"""
Step 5 audit: the full PUBLIC response for each of the 13 final-response classes. ZERO provider calls: classes 1 and 2 are saved authorized live responses (re-finalized with the current code); the rest run through
the real pipeline and finalizer with deterministic fixtures and the provider function set to raise.
  PYTHONIOENCODING=utf-8 PYTHONPATH=. python benchmarks/ai_search/baseline_2026_10_04/step5/contract_audit.py [label]    # before | after
Writes contract_audit_<label>.json: per class the complete public response, plus key_inventory_<label>.json: every top-level key, its type, nested keys, and which classes carry it.
"""
from __future__ import annotations

import asyncio
import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, ".")
HERE = Path(__file__).parent
LABEL = sys.argv[1] if len(sys.argv) > 1 else "run"
ART = HERE.parent / "step3_4c"

from app.services import ai_service as S  # noqa: E402
from app.services import request_deadline as RD  # noqa: E402
from app.services.ai_search import degraded_shape as DS  # noqa: E402
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
STATE = {"gen": None, "bundle": None, "slow": False, "expire": False}


def _stub(kind):
    async def run(query, evidence, intent_data, entities):
        if STATE["expire"]:
            RD.mark_expired()
        return STATE["gen"] or ({"_degraded_reason": "capacity"}, True)
    return run

for _n in ("company_specialist", "comparison_specialist", "sector_specialist"):
    setattr(getattr(P, _n), "run", _stub(_n))


async def _collect(query, intent_data, entities, db):
    if STATE["slow"]:
        await asyncio.sleep(60)
    return STATE["bundle"]

P.evidence_mod.collect = _collect


def go(query, *, bundle_=None, gen=None, slow=False, deadline=False, expire=False):
    STATE.update(bundle=bundle_, gen=gen, slow=slow, expire=expire)

    async def run():
        if deadline or expire:
            with RD.scope(total=3.0, reserve=0.5, min_attempt=1.0, attempt_cap=1.0):
                raw, was_cached = await P.run_ai_search_v3(query, None)
        else:
            raw, was_cached = await P.run_ai_search_v3(query, None)
        return finalize_v3_response(query, raw, x_admin_key=None, was_cached=was_cached)
    return asyncio.run(run())


def saved(file, qid):
    r = copy.deepcopy(json.loads((ART / file).read_text(encoding="utf-8"))["results"][qid]["response"])
    return finalize_v3_response(qid, r, x_admin_key=None, was_cached=True)      # the CURRENT finalizer applies the public contract to the saved response


def limited():
    r = DS.build_degraded_shape(query="q", response_id="r", schema_version="v3", specialist_kind="company", degraded_reason="grounding_collapsed", summary="s",
                                related_events=[{"id": "e1", "title": "A real related event"}, {"id": "e2", "title": "Another"}], sources_count=2, intent="general", ui_mode="direct_company_research")
    return finalize_v3_response("q", r, x_admin_key=None, was_cached=True)


def failed_bundle():
    b = bundle()
    b.retrieval_failures = {"news": "LiveNewsUnavailable"}
    return b

CASES = [
    ("01 full authorized evidence-backed", lambda: saved("openai_3_4g2.json", "EI3")),
    ("02 authorized partial / narrowed", lambda: saved("openai_3_4g1.json", "CC2")),
    ("03 limited evidence / withheld", limited),
    ("04 genuine evidence insufficiency", lambda: go("How is 3M India doing as a business?", bundle_=bundle())),
    ("05 retrieval failure", lambda: go("How is 3M India doing as a business?", bundle_=failed_bundle())),
    ("06 retrieval timeout", lambda: go("What is happening with TCS lately?", bundle_=tcs_bundle(), slow=True, deadline=True)),
    ("07 provider capacity", lambda: go("What is happening with TCS lately?", bundle_=tcs_bundle())),
    ("08 generation failure", lambda: go("What is happening with TCS lately?", bundle_=tcs_bundle(), gen=({"_degraded_reason": "parse_failure"}, True))),
    ("09 time-budget exhaustion", lambda: go("What is happening with TCS lately?", bundle_=tcs_bundle(), expire=True)),
    ("10 Gate B / claims not authorized", lambda: go("What is happening with TCS lately?", bundle_=tcs_bundle(), gen=(good_generation(claim_sources=[]), False))),
    ("11 general education (GE1)", lambda: go("What is a P/E ratio and how should I read it?")),
    ("12 product knowledge (GE3)", lambda: go("How does the MarketRipple Score work?")),
    ("13 unsupported subject", lambda: go("How is Zorbex Quantum Holdings Limited doing as a business?")),
]


def shape(v):
    return type(v).__name__ if not isinstance(v, dict) else "dict"


def main():
    full, inv = {}, {}
    for label, fn in CASES:
        try:
            r = fn()
        except Exception as exc:
            r = {"__error__": type(exc).__name__ + ": " + str(exc)[:200]}
        full[label] = r
        for k, v in r.items():
            e = inv.setdefault(k, {"type": shape(v), "nested": set(), "classes": []})
            e["classes"].append(label[:2])
            if isinstance(v, dict):
                e["nested"].update(v.keys())
    (HERE / f"contract_audit_{LABEL}.json").write_text(json.dumps(full, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    out = {k: {"type": v["type"], "nested": sorted(v["nested"]), "in_classes": v["classes"]} for k, v in sorted(inv.items())}
    (HERE / f"key_inventory_{LABEL}.json").write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"{len(CASES)} classes, {len(out)} distinct top-level keys")
    for label, r in full.items():
        av = r.get("answer_availability") or {}
        print(f"{label:42s} state={av.get('state')!s:24s} reason={av.get('reason')!s:22s} basis={av.get('basis')!s:18s} degraded={r.get('degraded_reason')!s:28s} keys={len(r)}")

main()
