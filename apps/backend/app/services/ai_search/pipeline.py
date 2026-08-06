"""
V3 pipeline orchestrator: intent -> entity -> evidence -> specialist ->
validation -> postprocess -> response.

V2's `run_ai_search` (ai_search_service.py) is untouched and keeps serving
`/api/ai/search` throughout Phase 1 development — this module is purely
additive, reached only via the new `/api/ai/search/v3` route, until the
benchmark gate passes and a deliberate cutover decision is made (see plan).
"""
from __future__ import annotations

import asyncio
import time
import uuid

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.ai_search import cache as cache_mod
from app.services.ai_search import entities as entities_mod
from app.services.ai_search import evidence as evidence_mod
from app.services.ai_search import followups as followups_mod
from app.services.ai_search import intent as intent_mod
from app.services.ai_search import investment_watch as investment_watch_mod
from app.services.ai_search import ripple_graph as ripple_graph_mod
from app.services.ai_search import session_context as session_context_mod
from app.services.ai_search import postprocess
from app.services.ai_search import validation as validation_mod
from app.services.ai_search.schema import SCHEMA_VERSION
from app.services.ai_search.specialists import comparison as comparison_specialist
from app.services.ai_search.specialists import company as company_specialist
from app.services.ai_search.specialists import sector as sector_specialist

log = structlog.get_logger(__name__)


def _route_specialist(query: str, intent_data: dict, entities: dict):
    """Exactly 3 routes for Phase 1 — see plan §"Routing". Comparison
    detection is deterministic (intent.py), not another LLM call — combines
    V2's own extraction with a broader pattern-and-entity fallback (see
    intent.py's module docstring for why: verified live that V2's regex
    alone missed real comparisons like "Between X and Y, which is the safer
    bet?"). intent_data is updated in place with the resolved holding/target
    so comparison.py's existing prompt-building code needs no changes."""
    from app.services.ai_search.regexes import _SECTOR_TRIGGER

    is_cmp, holding, target = intent_mod.resolve_comparison(query, intent_data, entities)
    if is_cmp and intent_data.get("intent") not in (
        "list_picks", "portfolio_review", "news_reaction", "earnings_preview", "entry_timing",
    ):
        if holding and target:
            intent_data["holding"], intent_data["target"] = holding, target
        intent_data["is_comparison"] = True
        return comparison_specialist, "comparison"
    if _SECTOR_TRIGGER.search(query) and not entities.get("companies"):
        return sector_specialist, "sector"
    return company_specialist, "company"


# The 7 stages named in the approved spec, mapped onto what the pipeline
# actually does — "Searching MarketRipple database" and "Collecting
# evidence" are genuinely one atomic step in evidence.collect() (DB search
# and the trigger-gated real-data fetches run together, not sequentially),
# so they're reported as one combined stage rather than fabricating a false
# boundary that doesn't exist in the real code. Never fake progress.
STAGE_LABELS = {
    "intent": "Understanding your question",
    "entities": "Detecting companies, sectors, and policies",
    "evidence": "Searching MarketRipple database and collecting evidence",
    "reasoning": "Running specialist analysis",
    "finalizing": "Building investment decision and finalizing response",
}


async def _run_v3_steps(query: str, db: AsyncSession, session_context: dict | None = None):
    """Async generator — the single source of truth for the v3 pipeline.
    Yields (stage_key, label, response_or_None) at each real checkpoint;
    response is only non-None on the final yield. Both the non-streaming
    `run_ai_search_v3` and the SSE route consume this same generator so
    there's exactly one pipeline implementation, not two to keep in sync."""
    # P5 Stage 1 (2026-08-06): _detect_decision_intent/_detect_market_pulse_async
    # relocated to ai_search/ — imported from their new home below.
    # _run_market_pulse_search deliberately still imported from
    # ai_search_service.py — flagged there as a Stage 2 decision (Market
    # Pulse "stays V2's exact mechanism" per this file's own earlier design).
    from app.services.ai_search.decision_intent import _detect_decision_intent
    from app.services.ai_search.market_pulse import _detect_market_pulse_async
    from app.services.ai_search_service import _run_market_pulse_search

    _t0 = time.monotonic()
    stage_ms: dict[str, float] = {}

    def _checkpoint(stage: str, since: float) -> float:
        now = time.monotonic()
        stage_ms[stage] = round((now - since) * 1000, 1)
        return now

    yield "intent", STAGE_LABELS["intent"], None

    # Market Pulse stays V2's exact mechanism — a different query family,
    # out of scope for the specialist pipeline (see plan).
    if await _detect_market_pulse_async(query):
        mp_result = await _run_market_pulse_search(query)
        mp_result["schema_version"] = SCHEMA_VERSION
        yield "finalizing", STAGE_LABELS["finalizing"], mp_result
        return

    # Layer 1 — exact query cache, checked before any resolution work.
    exact_hit = cache_mod.get_response(query)
    if exact_hit is not None:
        log.info("ai_search_v3.cache_hit", layer="exact", query=query[:50])
        yield "finalizing", STAGE_LABELS["finalizing"], exact_hit
        return

    _t_stage = time.monotonic()
    intent_data = _detect_decision_intent(query)
    _t_stage = _checkpoint("intent_detection_ms", _t_stage)

    yield "entities", STAGE_LABELS["entities"], None
    entities = entities_mod.extract_entities(query)
    _t_stage = _checkpoint("entity_detection_ms", _t_stage)

    # Phase 1.7 — ambiguous conglomerate name ("Compare with Tata") short-
    # circuits with real candidates rather than letting the model guess
    # which Tata entity was meant. Checked BEFORE session-context merge:
    # if the query's own text is ambiguous, session context doesn't get a
    # chance to silently pick one for the user either.
    ambiguous = session_context_mod.check_ambiguous_group(query, entities)
    if ambiguous:
        result = {
            "query": query, "schema_version": SCHEMA_VERSION,
            "needs_clarification": True,
            "ambiguous_term": ambiguous["term"], "candidates": ambiguous["candidates"],
        }
        yield "finalizing", STAGE_LABELS["finalizing"], result
        return

    # Phase 1.7 — merges session-held companies/sectors into this query's
    # own entities when it looks like a follow-up continuing the existing
    # discussion ("What about BEML?", "Which is safer?") rather than a
    # fresh, self-contained question — see session_context.resolve_context's
    # docstring for the exact conditions. Deterministic, before any LLM
    # call, per the spec's own performance rule.
    entities, context_used = session_context_mod.resolve_context(query, entities, session_context)

    if entities_mod.looks_like_unrecognized_company(query, entities):
        from app.services.ai_search_service import _unrecognized_company_response
        result = _unrecognized_company_response(query)
        result["schema_version"] = SCHEMA_VERSION
        suggestions = entities_mod.suggest_companies(query)
        if suggestions:
            result["answer"]["summary"] += " Did you mean: " + ", ".join(
                f"{s['name']} ({s['symbol']})" for s in suggestions
            ) + "?"
            result["company_suggestions"] = suggestions
        cache_mod.set_response(query, result)
        yield "finalizing", STAGE_LABELS["finalizing"], result
        return

    # Resolved this early (cheap, deterministic — no I/O) purely so the
    # canonical entity/intent shape is known before Layer 2's lookup; the
    # routing call below re-derives the same values from the same inputs
    # (resolve_comparison short-circuits when they're already set), so this
    # isn't duplicated work, just moved earlier.
    is_cmp, holding, target = intent_mod.resolve_comparison(query, intent_data, entities)
    if is_cmp and holding and target:
        intent_data["is_comparison"] = True
        intent_data["holding"], intent_data["target"] = holding, target

    # Layer 2 — semantic cache: same resolved companies/intent shape as a
    # previously-answered, differently-phrased query.
    semantic_hit = cache_mod.get_response(query, intent_data, entities)
    if semantic_hit is not None:
        log.info("ai_search_v3.cache_hit", layer="semantic", query=query[:50])
        yield "finalizing", STAGE_LABELS["finalizing"], semantic_hit
        return

    log.info("ai_search_v3.start", query=query[:50])

    yield "evidence", STAGE_LABELS["evidence"], None
    evidence = await evidence_mod.collect(query, intent_data, entities, db)
    _t_stage = _checkpoint("evidence_collection_ms", _t_stage)

    specialist, specialist_kind = _route_specialist(query, intent_data, entities)
    log.info("ai_search_v3.routed", specialist=specialist_kind, query=query[:50])

    yield "reasoning", STAGE_LABELS["reasoning"], None
    parsed, was_degraded = await specialist.run(query, evidence, intent_data, entities)
    _t_stage = _checkpoint("reasoning_ms", _t_stage)

    yield "finalizing", STAGE_LABELS["finalizing"], None
    validated, validation_report = validation_mod.validate_and_repair(parsed)
    if not validation_report.clean:
        log.info(
            "ai_search_v3.validation_repairs",
            query=query[:50], repairs=validation_report.repairs, omissions=validation_report.omissions,
        )
    _t_stage = _checkpoint("validation_ms", _t_stage)

    response = await _assemble_response(
        query, validated, evidence, specialist_kind, was_degraded, validation_report,
    )
    _checkpoint("assembly_ms", _t_stage)
    response["timing"] = {**stage_ms, "total_ms": round((time.monotonic() - _t0) * 1000, 1)}
    # Phase 1.7 — honestly reports what (if anything) session context
    # contributed to this answer, rather than the frontend guessing.
    response["context_used"] = context_used

    # Phase 2B — resolved once here (from the query's own entities, not
    # response["companies"] — see subject_for's docstring for why) so the
    # frontend can call GET /investment-watch with the exact same key the
    # snapshot below was written under, instead of re-deriving it and
    # risking a mismatch. None when this response isn't single-subject
    # (comparisons, multi-sector, etc.) — the frontend just hides the panel.
    subject = investment_watch_mod.subject_for(entities, response["companies"])
    response["watch_subject"] = subject

    if not was_degraded:
        cache_mod.set_response(query, response, intent_data, entities)

        # Phase 2B — Investment Watch's persistence half. Best-effort: a
        # snapshot-write failure must never affect the actual search
        # response (see investment_watch.py's module docstring).
        try:
            if subject:
                await investment_watch_mod.record_snapshot(
                    db, subject, query, response["response_id"],
                    verdict_scale=response.get("decision_engine_v2", {}).get("verdict_scale"),
                    rating=response.get("investment_verdict", {}).get("rating"),
                    confidence=int(response.get("answer", {}).get("confidence", 50) or 50),
                    why=response.get("decision_engine_v2", {}).get("why"),
                )
        except Exception as exc:
            log.warning("ai_search_v3.watch_snapshot_fail", exc=str(exc)[:160])

    yield "done", STAGE_LABELS["finalizing"], response


async def run_ai_search_v3(query: str, db: AsyncSession, session_context: dict | None = None) -> tuple[dict, bool]:
    """Non-streaming entry point — used by /api/ai/search/v3. Drains
    _run_v3_steps and returns (response, was_cached). was_cached is
    derived from which stages actually ran — a Layer 1/2 cache hit skips
    straight to "finalizing" without ever yielding "evidence"/"reasoning",
    so their absence is the real signal, not a separate flag threaded
    through by hand."""
    result = None
    stages_seen: set[str] = set()
    async for stage, _label, payload in _run_v3_steps(query, db, session_context):
        stages_seen.add(stage)
        if payload is not None:
            result = payload
    was_cached = "reasoning" not in stages_seen
    return result, was_cached


async def _assemble_response(
    query: str, ai: dict, evidence, specialist_kind: str, was_degraded: bool, validation_report,
) -> dict:
    """Builds the final response dict — a strict superset of V2's shape
    (see schema.py) plus Phase 1's new fields. Reuses V2's own enrichment/
    graph-build machinery directly (untouched, imported) rather than
    reimplementing it."""
    from app.services.ai_search.enrichment import (
        _classify_ripple_position,
        _enrich_sync,
        _fetch_chart_sync,
    )

    loop = asyncio.get_running_loop()
    raw_cos = ai.get("companies", [])
    try:
        companies_enriched = await loop.run_in_executor(None, _enrich_sync, raw_cos) if raw_cos else []
    except Exception as exc:
        log.warning("ai_search_v3.enrich_fail", exc=str(exc)[:120])
        companies_enriched = []
    companies_enriched.sort(key=lambda c: float(c.get("impact_score", 0) or 0), reverse=True)
    _classify_ripple_position(companies_enriched)
    for c in companies_enriched:
        c.setdefault("why_it_matters", c.get("reason", ""))

    sectors_raw = ai.get("sectors", [])
    for s in sectors_raw:
        from app.services.ai_search.enrichment import _sector_status, _sector_time_horizon
        status = _sector_status(bool(s.get("positive", True)), float(s.get("score", 0) or 0))
        s["status"] = status
        s["time_horizon"] = _sector_time_horizon(status)
        s.setdefault("explanation", "")

    try:
        chart_tickers = [c["symbol"] for c in companies_enriched[:5] if c.get("symbol")]
        chart = await loop.run_in_executor(None, _fetch_chart_sync, chart_tickers) if chart_tickers else {"labels": [], "series": []}
    except Exception:
        chart = {"labels": [], "series": []}

    try:
        # Phase 2A — merges the real, seeded, weighted macro causal graph
        # (intelligence_graph_service, via V2's own _build_ripple_chain)
        # with this response's companies/competitors/historical precedents/
        # risks/opportunities into one multi-hop graph. Replaces the old
        # shallow query->sector->company _build_graph entirely — see
        # ripple_graph.py's module docstring.
        graph_sig = (
            query[:60] + "|" +
            ",".join(sorted(s.get("name", "") for s in sectors_raw)) + "|" +
            ",".join(sorted(c.get("symbol", "") for c in companies_enriched))
        )

        async def _graph_factory():
            return await ripple_graph_mod.build(
                query, companies_enriched, sectors_raw,
                evidence.similar_historical, ai.get("risks", []), ai.get("opportunities", []),
            )

        graph = await cache_mod.component("graph", graph_sig, _graph_factory)
    except Exception:
        graph = {"nodes": [], "edges": []}
    # .get(), not .pop() — cache_mod.component caches this exact dict
    # object in-process; mutating it here would corrupt it for the next
    # cache hit (ripple_chain silently missing on every call after the first).
    ripple_chain = graph.get("ripple_chain", [])
    graph = {"nodes": graph.get("nodes", []), "edges": graph.get("edges", [])}

    evidence_score = postprocess.compute_evidence_score(evidence)
    confidence_breakdown = postprocess.compute_confidence_breakdown(evidence, ai, evidence.mie_state)
    response_id = str(uuid.uuid4())

    response = {
        "query": query,
        # Identifies this generated ANSWER (stable across repeat cache-hit
        # serves within the cache's TTL — the same dict object is what gets
        # returned on a hit), not the individual HTTP request. Lets
        # feedback from different users about the same cached analysis
        # correlate as one signal (see AISearchFeedback's docstring).
        "response_id": response_id,
        "schema_version": SCHEMA_VERSION,
        "specialist": specialist_kind,
        "synthesis_incomplete": was_degraded,
        "answer": {
            "summary": ai.get("summary", ""),
            "bottom_line": ai.get("bottom_line", ai.get("summary", "")),
            "what_happened": ai.get("what_happened", ""),
            "why_it_happened": ai.get("why_it_happened", ""),
            "immediate_impact": ai.get("immediate_impact", ""),
            "medium_term": ai.get("medium_term", ""),
            "long_term": ai.get("long_term", ""),
            "what_priced_in": ai.get("what_priced_in", ""),
            "risks": ai.get("risks", []),
            "opportunities": ai.get("opportunities", []),
            "confidence": confidence_breakdown["final_confidence"],
            "confidence_level": confidence_breakdown["level"],
            "sentiment": ai.get("sentiment", "neutral"),
            "sources_count": evidence.source_count,
        },
        "key_drivers": ai.get("key_drivers", []),
        "insights": ai.get("insights", []),
        "companies": companies_enriched,
        "sectors": sectors_raw,
        "related_events": evidence.events[:6],
        "news": evidence.news[:6],
        "policies": evidence.policies[:4],
        "timeline": ai.get("timeline", []),
        "historical_comparison": evidence.similar_historical,
        "ripple_chain": ripple_chain,
        "scenarios": ai.get("scenarios", {}),
        "monitoring": ai.get("monitoring", {}),
        "follow_up_questions": ai.get("follow_up_questions", []),
        # P4: same canonical-confidence fix V2 already shipped and proved
        # (ai_search_service.py) — investment_verdict.confidence used to
        # keep whatever number the LLM self-rated, independent of and
        # frequently miles from answer.confidence's real evidence-grounded
        # score (a 53-point gap observed live). Force it to the one real
        # blended number rather than presenting two disagreeing "confidence"
        # fields as if they were interchangeable.
        "investment_verdict": {**ai.get("investment_verdict", {}), "confidence": confidence_breakdown["final_confidence"]},
        "market_chart": chart,
        "graph": graph,
        "citations": list({a.get("source", "") for a in evidence.news if a.get("source")}),
        "decision_intelligence": ai.get("decision_intelligence"),
        "confidence_data": {
            "level": confidence_breakdown["level"],
            "score": confidence_breakdown["final_confidence"],
            "reasons": confidence_breakdown["reasons"],
            "breakdown": {},
        },
        # ── Phase 1 new fields ──
        "decision_engine_v2": ai.get("decision_engine_v2", {}),
        "timeline_intelligence": ai.get("timeline_intelligence", {}),
        "opportunity_risk_matrix": ai.get("opportunity_risk_matrix", {}),
        "ai_conclusion": ai.get("ai_conclusion", {}),
        "evidence_score": evidence_score,
        "confidence_breakdown": confidence_breakdown,
        "source_attribution": evidence.to_source_ids(),
        "validation": {
            "repairs": validation_report.repairs,
            "omissions": validation_report.omissions,
            "contradiction_flagged": validation_report.contradiction_flagged,
        },
    }

    if not was_degraded:
        # Real evidence + resolved companies behind this answer, cached
        # under its own response_id — see cache.set_snapshot's docstring
        # (Refine Analysis's whole point is reusing this instead of
        # re-fetching). Never snapshotted for a degraded response — there's
        # no real evidence context worth refining against.
        cache_mod.set_snapshot(response_id, {
            "query": query,
            "specialist_kind": specialist_kind,
            "is_comparison": specialist_kind == "comparison",
            "evidence_context": evidence.to_context_text(),
            "companies": [
                {"symbol": c.get("symbol"), "name": c.get("name")} for c in companies_enriched
            ],
        })
        # Phase 1.6 — grouped, contextual follow-ups built from the response's
        # own structured data (see followups.py's module docstring for why
        # this is deliberately NOT another LLM call). Skipped on a degraded
        # response — there's no real decision/evidence signal to ground them in.
        response["follow_up_groups"] = followups_mod.generate(response, specialist_kind, query, evidence.to_context_text())
    else:
        response["follow_up_groups"] = []

    return response
