"""
6G Cutover Gate, Step 2 — V2 vs V3 parity harness.

Different job from runner.py's --compare: that command diffs two already-
completed FULL benchmark runs (200-2400 questions) at the aggregate KPI
level. This harness runs a small, hand-curated corpus of representative
real user intents through BOTH pipelines *paired*, per query, and renders a
semantic verdict per query: does V3 preserve the capability contract V2
currently offers, not "does the prose match."

Deliberately separates two different kinds of "failure":
  - INFRA:    the provider fallback chain (shared by both pipelines --
              app.services.ai_service._call_with_fallback) got exhausted or
              errored for at least one side. Not a V2/V3 code signal --
              retry later, don't count it as a cutover blocker.
  - SEMANTIC: both pipelines produced a real synthesis, and we can actually
              compare capability: entities, specialist routing, real-
              screener/Decision-Engine grounding where required, 3-way
              entity retention, sources, confidence/calibration presence.

Reuses runner.py's call_ai_search (same rate-limit-safe HTTP plumbing,
same base-URL/timeout conventions) and load_company_lookup — this is not a
reimplementation of the benchmark suite's HTTP layer, just a different
comparison shape on top of it.

Usage:
    python parity_harness.py --base-url http://127.0.0.1:8001
    python parity_harness.py --base-url http://127.0.0.1:8001 --only single_company,sector
"""
from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from runner import call_ai_search, load_company_lookup, load_sector_lookup

OUT_DIR = Path(__file__).parent
RESULTS_DIR = OUT_DIR / "results"

# Boilerplate the generic fallback template always starts with -- same
# signature runner.py uses to isolate "fabricated placeholder answer" from
# "a real synthesis that happens to be low-confidence." See runner.py's own
# comment on main_answer_degraded for why this string, not synthesis_incomplete,
# is the reliable signal for "the actual answer text is fake."
_DEGRADED_PREFIX = "Market intelligence analysis for:"


# ─────────────────────────────────────────────────────────────────────────
# Corpus -- one query per real user-intent family from the 6G Cutover Gate
# ─────────────────────────────────────────────────────────────────────────
@dataclass
class CorpusItem:
    id: str
    family: str
    query: str
    expected_entities: set[str] = field(default_factory=set)
    checks: list[str] = field(default_factory=list)
    note: str = ""


CORPUS: list[CorpusItem] = [
    CorpusItem(
        id="single_company", family="Single company",
        query="Tell me about HDFC Bank as an investment.",
        expected_entities={"HDFCBANK"}, checks=["entities", "confidence", "sources"],
    ),
    CorpusItem(
        id="company_outlook", family="Company outlook",
        query="What is the investment outlook for TCS over the next 6 months?",
        expected_entities={"TCS"}, checks=["entities", "confidence", "sources"],
    ),
    CorpusItem(
        id="earnings_results", family="Earnings/results",
        query="How did Reliance Industries perform in its latest quarterly results?",
        expected_entities={"RELIANCE"}, checks=["entities", "confidence"],
    ),
    CorpusItem(
        id="sector", family="Sector question",
        query="What is the outlook for the IT sector right now?",
        expected_entities=set(), checks=["sectors_present", "confidence"],
    ),
    CorpusItem(
        id="market_wide", family="Market-wide question",
        query="How is the overall stock market doing today?",
        expected_entities=set(), checks=["not_degraded"],
        note="Schema differs legitimately (market_pulse type in V2) -- WARN-level only.",
    ),
    CorpusItem(
        id="top_n_stocks", family="Top-N picks (real-screener)",
        query="What are the top 5 banking stocks to invest in right now?",
        expected_entities=set(), checks=["screener_grounded", "confidence"],
    ),
    CorpusItem(
        id="two_company_comparison", family="2-company comparison (Decision Engine)",
        query="TCS vs Infosys -- which is the better investment right now?",
        expected_entities={"TCS", "INFY"}, checks=["entities", "decision_engine", "confidence"],
    ),
    CorpusItem(
        id="three_company_comparison", family="3-company comparison (entity retention)",
        query="Compare TCS, Infosys, and Wipro as investments.",
        expected_entities={"TCS", "INFY", "WIPRO"}, checks=["entities", "entity_retention_3way", "confidence"],
    ),
    CorpusItem(
        id="entry_timing", family="Entry timing",
        query="Is this a good time to buy HDFC Bank shares?",
        expected_entities={"HDFCBANK"}, checks=["entities", "confidence"],
    ),
    CorpusItem(
        id="news_event_reaction", family="News/event reaction",
        query="How will the recent RBI rate decision impact banking stocks?",
        expected_entities=set(), checks=["sectors_present_or_entities", "confidence"],
    ),
    CorpusItem(
        id="ambiguous_entity", family="Ambiguous entity",
        query="What is Tata's outlook?",
        expected_entities=set(), checks=["no_false_confidence"],
        note="V2 has no clarification UX -- informational only, not scored as a V3 regression.",
    ),
    CorpusItem(
        id="development_memory", family="Development Memory available",
        query="What is the latest update on Colgate-Palmolive India?",
        expected_entities={"COLPAL"}, checks=["entities", "confidence"],
        note="COLPAL has a real, currently-open, evidence-backed Development row in the dev DB.",
    ),
    CorpusItem(
        id="degraded_no_evidence", family="Degraded / no-evidence case",
        query="What is the investment outlook for Zylotronix Micro Industries Ltd?",
        expected_entities=set(), checks=["graceful_degradation"],
        note="Fictional company -- correct behavior is an honest 'no data', not a fabricated verdict.",
    ),
]

FOLLOWUP_FIRST = "Tell me about TCS as an investment."
FOLLOWUP_SECOND = "What about its biggest listed competitor?"
FOLLOWUP_FIRST_ENTITY = "TCS"


# ─────────────────────────────────────────────────────────────────────────
# Signal extraction -- normalizes a V2 or V3 response into one comparable shape
# ─────────────────────────────────────────────────────────────────────────
def extract_signals(status: int, result: dict | None, error: str | None, latency: float) -> dict:
    sig = {
        "http_status": status, "error": error, "latency_s": round(latency, 1),
        "infra_fail": False, "market_pulse": False,
        "entities": set(), "specialist": None,
        "confidence": None, "sources_count": 0,
        "decision_engine_present": False, "entity_analyses_count": 0,
        "screener_grounded": False, "needs_clarification": False,
        "degraded": False, "answer_text": "",
    }
    if status != 200 or result is None:
        sig["infra_fail"] = True
        return sig

    if result.get("type") == "market_pulse":
        sig["market_pulse"] = True
        sig["answer_text"] = str(result.get("ai_conclusion") or result.get("market_summary") or "")
        sig["degraded"] = not bool(sig["answer_text"])
        sig["infra_fail"] = sig["degraded"]
        return sig

    if result.get("needs_clarification"):
        sig["needs_clarification"] = True

    summary = (result.get("answer") or {}).get("summary") or ""
    sig["answer_text"] = summary
    # synthesis_incomplete is a COMBINED flag (see runner.py's own comment on
    # main_answer_degraded): it legitimately fires for a real, by-design
    # response shape too -- e.g. _ambiguous_entity_response in
    # ai_search_service.py sets it True on purpose for a bare-conglomerate
    # clarification, which is a genuine answer, not a failure. Only the
    # generic fallback-boilerplate prefix or a truly empty summary indicates
    # the main synthesis itself broke -- that's the actual infra signal.
    sig["degraded"] = bool(result.get("synthesis_incomplete"))
    sig["infra_fail"] = summary.startswith(_DEGRADED_PREFIX) or not summary

    sig["entities"] = {c.get("symbol", "").upper() for c in (result.get("companies") or []) if c.get("symbol")}
    sig["specialist"] = result.get("specialist")  # V3-only field; None for V2

    conf_data = result.get("confidence_data") or {}
    sig["confidence"] = conf_data.get("score", (result.get("answer") or {}).get("confidence"))

    sig["sources_count"] = (
        (result.get("answer") or {}).get("sources_count")
        or (len(result.get("news") or []) + len(result.get("related_events") or []) + len(result.get("policies") or []))
    )

    verdict = result.get("investment_verdict") or {}
    sig["screener_grounded"] = verdict.get("verdict_basis") == "real_screener"

    di = result.get("decision_intelligence") or {}
    sig["decision_engine_present"] = bool(di.get("engine_recommendation"))
    sig["entity_analyses_count"] = len(di.get("entity_analyses") or [])

    sig["sectors"] = {s.get("name") for s in (result.get("sectors") or []) if s.get("name")}
    return sig


# ─────────────────────────────────────────────────────────────────────────
# Verdict engine
# ─────────────────────────────────────────────────────────────────────────
# (level, passed, detail) -- BLOCKER fails the cutover gate outright; WARN
# is a real difference worth a human look but not a hard stop.
def _check_entities(item: CorpusItem, v2: dict, v3: dict) -> tuple[str, bool, str]:
    if not item.expected_entities:
        return "BLOCKER", True, "no expected entities for this family"
    v2_ok = item.expected_entities.issubset(v2["entities"])
    v3_ok = item.expected_entities.issubset(v3["entities"])
    if v3_ok:
        return "BLOCKER", True, f"V3 resolved {sorted(v3['entities'] & item.expected_entities)}"
    if not v2_ok:
        return "WARN", True, "V2 itself didn't resolve the expected entity either -- not a V3-specific regression"
    return "BLOCKER", False, f"V2 resolved {sorted(v2['entities'])}, V3 resolved {sorted(v3['entities'])} -- expected {sorted(item.expected_entities)}"


def _check_confidence(item: CorpusItem, v2: dict, v3: dict) -> tuple[str, bool, str]:
    v2_has = v2["confidence"] is not None
    v3_has = v3["confidence"] is not None
    if v3_has:
        return "BLOCKER", True, f"V3 confidence={v3['confidence']}"
    if not v2_has:
        return "WARN", True, "V2 also had no confidence score for this query"
    return "BLOCKER", False, "V2 had a confidence score, V3 did not"


def _check_sources(item: CorpusItem, v2: dict, v3: dict) -> tuple[str, bool, str]:
    v2_has = (v2["sources_count"] or 0) > 0
    v3_has = (v3["sources_count"] or 0) > 0
    if v3_has or not v2_has:
        return "WARN", True, f"V3 sources={v3['sources_count']}"
    return "WARN", False, f"V2 had {v2['sources_count']} sources, V3 had 0"


def _check_sectors_present(item: CorpusItem, v2: dict, v3: dict) -> tuple[str, bool, str]:
    ok = bool(v3.get("sectors")) or bool(v3["entities"])
    return "WARN", ok, f"V3 sectors={sorted(v3.get('sectors') or [])}"


def _check_sectors_present_or_entities(item: CorpusItem, v2: dict, v3: dict) -> tuple[str, bool, str]:
    ok = bool(v3.get("sectors")) or bool(v3["entities"])
    return "WARN", ok, f"V3 grounded via sectors={sorted(v3.get('sectors') or [])} or entities={sorted(v3['entities'])}"


def _check_not_degraded(item: CorpusItem, v2: dict, v3: dict) -> tuple[str, bool, str]:
    return "WARN", not v3["degraded"], "V3 degraded" if v3["degraded"] else "V3 produced a real answer"


def _check_screener_grounded(item: CorpusItem, v2: dict, v3: dict) -> tuple[str, bool, str]:
    if v3["screener_grounded"]:
        return "BLOCKER", True, "V3 verdict_basis=real_screener"
    if not v2["screener_grounded"]:
        return "WARN", True, "V2 also had no real-screener match for this query -- corpus/data limitation, not a V3 bug"
    return "BLOCKER", False, "V2 had verdict_basis=real_screener, V3 did not"


def _check_decision_engine(item: CorpusItem, v2: dict, v3: dict) -> tuple[str, bool, str]:
    if v3["decision_engine_present"]:
        return "BLOCKER", True, "V3 has decision_intelligence.engine_recommendation"
    if not v2["decision_engine_present"]:
        return "WARN", True, "V2 also had no engine_recommendation for this pair"
    return "BLOCKER", False, "V2 had engine_recommendation, V3 did not"


def _check_entity_retention_3way(item: CorpusItem, v2: dict, v3: dict) -> tuple[str, bool, str]:
    if v3["entity_analyses_count"] >= 3:
        return "BLOCKER", True, f"V3 entity_analyses has {v3['entity_analyses_count']} entries"
    if v2["entity_analyses_count"] < 3:
        return "WARN", True, f"V2 also didn't retain all 3 entities (had {v2['entity_analyses_count']})"
    return "BLOCKER", False, f"V2 retained {v2['entity_analyses_count']} entities, V3 retained {v3['entity_analyses_count']}"


def _check_no_false_confidence(item: CorpusItem, v2: dict, v3: dict) -> tuple[str, bool, str]:
    high_conf_no_entities = (v3["confidence"] or 0) >= 85 and not v3["entities"] and not v3["needs_clarification"]
    return "BLOCKER", not high_conf_no_entities, (
        "V3 gave high confidence with no resolved entity and no clarification request -- looks like a guess presented as certainty"
        if high_conf_no_entities else "V3 either asked for clarification or kept confidence appropriately measured"
    )


def _check_graceful_degradation(item: CorpusItem, v2: dict, v3: dict) -> tuple[str, bool, str]:
    fabricated = bool(v3["entities"])  # a fictional company should never resolve to a real symbol
    if fabricated:
        return "BLOCKER", False, f"V3 fabricated a match for a fictional company: {sorted(v3['entities'])}"
    return "BLOCKER", True, "V3 correctly returned no fabricated company match"


_CHECKS = {
    "entities": _check_entities, "confidence": _check_confidence, "sources": _check_sources,
    "sectors_present": _check_sectors_present, "sectors_present_or_entities": _check_sectors_present_or_entities,
    "not_degraded": _check_not_degraded, "screener_grounded": _check_screener_grounded,
    "decision_engine": _check_decision_engine, "entity_retention_3way": _check_entity_retention_3way,
    "no_false_confidence": _check_no_false_confidence, "graceful_degradation": _check_graceful_degradation,
}


def evaluate(item: CorpusItem, v2: dict, v3: dict) -> dict:
    if v2["infra_fail"] and v3["infra_fail"]:
        return {"category": "INFRA", "verdict": "INFRA_BOTH_FAILED", "checks": [],
                "reason": "Both pipelines failed/degraded -- looks like shared provider exhaustion, not a V2/V3 difference."}
    if v2["infra_fail"] and not v3["infra_fail"]:
        return {"category": "INFRA", "verdict": "INFRA_V2_ONLY_FAILED", "checks": [],
                "reason": "V2 failed/degraded, V3 produced a real answer -- informational, arguably favors V3."}
    if v3["infra_fail"] and not v2["infra_fail"]:
        return {"category": "INFRA", "verdict": "INFRA_V3_ONLY_FAILED", "checks": [],
                "reason": "V3 failed/degraded while V2 succeeded. Could be a real V3 bug or provider bad luck on this "
                          "specific call -- NOT auto-counted as a semantic blocker. Retry before treating as a finding."}

    checks_run = []
    verdict = "PASS"
    for check_name in item.checks:
        level, passed, detail = _CHECKS[check_name](item, v2, v3)
        checks_run.append({"check": check_name, "level": level, "passed": passed, "detail": detail})
        if not passed:
            if level == "BLOCKER":
                verdict = "BLOCKER"
            elif level == "WARN" and verdict == "PASS":
                verdict = "WARN"
    return {"category": "SEMANTIC", "verdict": verdict, "checks": checks_run, "reason": ""}


# ─────────────────────────────────────────────────────────────────────────
# Run
# ─────────────────────────────────────────────────────────────────────────
def _pace(delay: float, latency: float) -> None:
    remaining = delay - latency
    if remaining > 0:
        time.sleep(remaining)


def run(base_url: str, delay: float, timeout: float, only: set[str] | None, skip_followup: bool) -> dict:
    items = [c for c in CORPUS if not only or c.id in only]
    rows: list[dict] = []

    print(f"Running {len(items)} paired queries (+{0 if skip_followup else 1} follow-up pair) against {base_url}\n")

    for i, item in enumerate(items, 1):
        print(f"[{i}/{len(items)}] {item.family}: {item.query}")
        v2_status, v2_result, v2_error, v2_lat = call_ai_search(base_url, item.query, timeout, pipeline="v2")
        _pace(delay, v2_lat)
        v3_status, v3_result, v3_error, v3_lat = call_ai_search(base_url, item.query, timeout, pipeline="v3")
        _pace(delay, v3_lat)

        v2_sig = extract_signals(v2_status, v2_result, v2_error, v2_lat)
        v3_sig = extract_signals(v3_status, v3_result, v3_error, v3_lat)
        outcome = evaluate(item, v2_sig, v3_sig)

        row = {
            "id": item.id, "family": item.family, "query": item.query, "note": item.note,
            "v2": {**v2_sig, "entities": sorted(v2_sig["entities"]), "sectors": sorted(v2_sig.get("sectors") or [])},
            "v3": {**v3_sig, "entities": sorted(v3_sig["entities"]), "sectors": sorted(v3_sig.get("sectors") or [])},
            **outcome,
        }
        rows.append(row)
        print(f"    -> {outcome['category']}/{outcome['verdict']}"
              + (f"  ({outcome['reason']})" if outcome["reason"] else ""))
        for c in outcome["checks"]:
            if not c["passed"]:
                print(f"       [{c['level']}] {c['check']}: {c['detail']}")

    if not skip_followup and (not only or "session_followup" in only):
        print(f"\n[followup] Session follow-up (2-turn): \"{FOLLOWUP_FIRST}\" -> \"{FOLLOWUP_SECOND}\"")
        rows.append(_run_followup(base_url, delay, timeout))
        row = rows[-1]
        print(f"    -> {row['category']}/{row['verdict']}" + (f"  ({row['reason']})" if row["reason"] else ""))
        for c in row["checks"]:
            if not c["passed"]:
                print(f"       [{c['level']}] {c['check']}: {c['detail']}")

    summary = _summarize(rows)
    _print_summary(summary)

    RESULTS_DIR.mkdir(exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = RESULTS_DIR / f"parity_{ts}.json"
    out_path.write_text(json.dumps({"summary": summary, "rows": rows}, indent=2, ensure_ascii=False, default=list),
                         encoding="utf-8")
    print(f"\nWrote {out_path}")
    return {"summary": summary, "rows": rows}


def _run_followup(base_url: str, delay: float, timeout: float) -> dict:
    """2-turn referential follow-up. Not in CORPUS because it needs a
    stateful pair of calls per pipeline (first call establishes context,
    second call sends it back as session_context), unlike every other
    single-shot family."""
    session_ctx = {"companies": [FOLLOWUP_FIRST_ENTITY], "sectors": [], "time_horizon": None,
                    "risk_tolerance": None, "investment_goal": None, "current_position": None}

    def _one_pipeline(pipeline: str) -> dict:
        s1, r1, e1, l1 = call_ai_search(base_url, FOLLOWUP_FIRST, timeout, pipeline=pipeline)
        _pace(delay, l1)
        # call_ai_search doesn't thread session_context -- build the request directly, same
        # SearchRequest shape both routes share.
        import json as _json
        import urllib.request
        path = "/api/ai/search/v3" if pipeline == "v3" else "/api/ai/search"
        url = f"{base_url.rstrip('/')}{path}"
        body = _json.dumps({"query": FOLLOWUP_SECOND, "session_context": session_ctx}).encode("utf-8")
        req = urllib.request.Request(url, data=body, method="POST", headers={"Content-Type": "application/json"})
        t0 = time.monotonic()
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                payload = _json.loads(resp.read().decode("utf-8"))
                s2, r2, e2 = resp.status, payload.get("result"), None
        except Exception as exc:  # noqa: BLE001
            s2, r2, e2 = 0, None, str(exc)
        l2 = time.monotonic() - t0
        return extract_signals(s2, r2, e2, l2)

    v2_sig = _one_pipeline("v2")
    _pace(delay, v2_sig["latency_s"])
    v3_sig = _one_pipeline("v3")

    item = CorpusItem(id="session_followup", family="Session follow-up (referential)",
                       query=f"{FOLLOWUP_FIRST!r} then {FOLLOWUP_SECOND!r}",
                       expected_entities=set(), checks=["entities"])
    sector_lookup = load_sector_lookup()
    first_sector = sector_lookup.get(FOLLOWUP_FIRST_ENTITY)

    def _referential_entities(sig: dict) -> set[str]:
        return sig["entities"] - {FOLLOWUP_FIRST_ENTITY}

    # Two distinct signals, not one -- "did it resolve anything new" can look
    # fine while actually losing the intended referent (e.g. resolving to an
    # unrelated company because session_context was ignored and the follow-up
    # text alone got parsed generically). referential_resolution checks the
    # weaker "resolved *something* beyond turn 1's company" signal;
    # referential_relevance checks the stronger "resolved something in the
    # SAME sector as turn 1's company" signal -- real proof the context (not
    # just generic entity extraction) drove the answer, since "its biggest
    # listed competitor" is meaningless without knowing what "its" refers to.
    v2_new = _referential_entities(v2_sig)
    v3_new = _referential_entities(v3_sig)
    v2_resolved = bool(v2_new)
    v3_resolved = bool(v3_new)
    v2_relevant = bool(first_sector) and any(sector_lookup.get(s) == first_sector for s in v2_new)
    v3_relevant = bool(first_sector) and any(sector_lookup.get(s) == first_sector for s in v3_new)

    if v2_sig["infra_fail"] and v3_sig["infra_fail"]:
        outcome = {"category": "INFRA", "verdict": "INFRA_BOTH_FAILED", "checks": [], "reason": "Both pipelines failed on the follow-up turn."}
    elif v3_sig["infra_fail"] and not v2_sig["infra_fail"]:
        outcome = {"category": "INFRA", "verdict": "INFRA_V3_ONLY_FAILED", "checks": [], "reason": "V3 failed on the follow-up turn while V2 succeeded -- retry before treating as a finding."}
    elif v2_sig["infra_fail"] and not v3_sig["infra_fail"]:
        outcome = {"category": "INFRA", "verdict": "INFRA_V2_ONLY_FAILED", "checks": [], "reason": "V2 failed on the follow-up turn, V3 succeeded."}
    else:
        checks_run = []
        resolution_check = {"check": "referential_resolution", "level": "BLOCKER", "passed": v3_resolved,
                             "detail": f"V3 follow-up resolved to {sorted(v3_new)}" if v3_resolved
                                       else f"V3 follow-up never resolved a company beyond {FOLLOWUP_FIRST_ENTITY} -- session_context may not be threading into V3's entity resolution"}
        if not v3_resolved and not v2_resolved:
            resolution_check["level"], resolution_check["passed"] = "WARN", True
            resolution_check["detail"] = "V2 also didn't resolve a referential company on the follow-up -- not a V3-specific regression"
        checks_run.append(resolution_check)

        # Relevance only means something once resolution itself succeeded --
        # can't judge "is it the right competitor" if nothing new resolved at all.
        if v3_resolved:
            relevance_check = {"check": "referential_relevance", "level": "WARN", "passed": v3_relevant,
                                "detail": f"V3's resolved compan{'y is' if len(v3_new) == 1 else 'ies are'} in the "
                                          f"{first_sector} sector like {FOLLOWUP_FIRST_ENTITY}, confirming the "
                                          f"reference carried real context" if v3_relevant else
                                          f"V3 resolved {sorted(v3_new)}, none in {first_sector} (turn 1's sector) -- "
                                          f"looks like a plausible-sounding but disconnected answer, not real context carry-over"}
            if not v3_relevant and not v2_relevant:
                relevance_check["level"], relevance_check["passed"] = "WARN", True
                relevance_check["detail"] += " (V2 also didn't resolve a same-sector peer -- not a V3-specific regression)"
            checks_run.append(relevance_check)

        verdict = "PASS"
        for c in checks_run:
            if not c["passed"]:
                verdict = "BLOCKER" if c["level"] == "BLOCKER" else ("WARN" if verdict == "PASS" else verdict)
        outcome = {"category": "SEMANTIC", "verdict": verdict, "checks": checks_run, "reason": ""}

    return {
        "id": item.id, "family": item.family, "query": item.query, "note": "2-turn stateful check, not in CORPUS.",
        "v2": {**v2_sig, "entities": sorted(v2_sig["entities"]), "sectors": sorted(v2_sig.get("sectors") or [])},
        "v3": {**v3_sig, "entities": sorted(v3_sig["entities"]), "sectors": sorted(v3_sig.get("sectors") or [])},
        **outcome,
    }


def _summarize(rows: list[dict]) -> dict:
    semantic = [r for r in rows if r["category"] == "SEMANTIC"]
    infra = [r for r in rows if r["category"] == "INFRA"]
    passed = [r for r in semantic if r["verdict"] == "PASS"]
    warned = [r for r in semantic if r["verdict"] == "WARN"]
    blocked = [r for r in semantic if r["verdict"] == "BLOCKER"]
    return {
        "total_queries": len(rows),
        "semantic_evaluated": len(semantic),
        "infra_excluded": len(infra),
        "infra_breakdown": {
            "both_failed": sum(1 for r in infra if r["verdict"] == "INFRA_BOTH_FAILED"),
            "v2_only_failed": sum(1 for r in infra if r["verdict"] == "INFRA_V2_ONLY_FAILED"),
            "v3_only_failed_needs_retry": sum(1 for r in infra if r["verdict"] == "INFRA_V3_ONLY_FAILED"),
        },
        "pass": len(passed), "warn": len(warned), "blocker": len(blocked),
        "pass_ids": [r["id"] for r in passed], "warn_ids": [r["id"] for r in warned], "blocker_ids": [r["id"] for r in blocked],
    }


def _print_summary(s: dict) -> None:
    print("\n" + "=" * 72)
    print("  6G Cutover Gate -- V2 vs V3 Parity Harness")
    print("=" * 72)
    n = s["semantic_evaluated"]
    print(f"  Of {s['total_queries']} representative real user intents, {n} were semantically "
          f"comparable (both pipelines produced a real synthesis).")
    print(f"  V3 was equivalent/better on {s['pass']}, weaker (WARN) on {s['warn']}, "
          f"and had {s['blocker']} actual cutover BLOCKER(s).")
    if s["infra_excluded"]:
        b = s["infra_breakdown"]
        print(f"\n  {s['infra_excluded']} quer{'y' if s['infra_excluded'] == 1 else 'ies'} excluded from the "
              f"semantic verdict as infrastructure noise:")
        print(f"    both pipelines failed (shared provider exhaustion): {b['both_failed']}")
        print(f"    V2 only failed (informational, favors V3):          {b['v2_only_failed']}")
        print(f"    V3 only failed -- NEEDS A RETRY, not yet a finding: {b['v3_only_failed_needs_retry']}")
    if s["blocker_ids"]:
        print(f"\n  BLOCKER ids: {', '.join(s['blocker_ids'])}")
    if s["warn_ids"]:
        print(f"  WARN ids:    {', '.join(s['warn_ids'])}")
    print("=" * 72 + "\n")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base-url", default="http://127.0.0.1:8000")
    ap.add_argument("--delay", type=float, default=6.5)
    ap.add_argument("--timeout", type=float, default=150.0)
    ap.add_argument("--only", default=None, help="Comma-separated corpus ids to run instead of the full corpus")
    ap.add_argument("--skip-followup", action="store_true", help="Skip the 2-turn session follow-up pair")
    args = ap.parse_args()
    only = set(args.only.split(",")) if args.only else None
    run(args.base_url, args.delay, args.timeout, only, args.skip_followup)


if __name__ == "__main__":
    main()
