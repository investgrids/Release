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
from app.services.ai_search.horizon import compute_horizon
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


def _degraded_shell(query: str, degraded_reason: str, summary: str) -> dict:
    """P5 Stage 2: V3-native schema-complete shell for a short-circuit
    degradation response — same field set V2's equivalent functions build
    (ai_search_service.py's _referential_no_context_response/
    _ambiguous_entity_response/_unrecognized_company_response), adapted to
    V3's shape (adds schema_version; V3 is a strict superset of V2's shape
    per _assemble_response's docstring, so the fields themselves match).
    Callers fill in query-specific fields (follow_up_questions, etc.) on
    top of this base.
    """
    return {
        "query": query, "schema_version": SCHEMA_VERSION,
        "synthesis_incomplete": True, "degraded_reason": degraded_reason,
        "answer": {
            "summary": summary, "bottom_line": summary,
            "what_happened": "", "why_it_happened": "", "immediate_impact": "",
            "medium_term": "", "long_term": "", "what_priced_in": "",
            "risks": [], "opportunities": [],
            "confidence": None, "confidence_level": "unscored",
            "sentiment": "neutral", "sources_count": 0,
        },
        "key_drivers": [], "insights": [], "companies": [], "sectors": [],
        "related_events": [], "news": [], "policies": [], "timeline": [],
        "historical_comparison": [], "ripple_chain": [], "scenarios": {},
        "market_impact_horizons": [], "what_to_monitor": [],
        "ai_reasoning_methods": [], "follow_up_questions": [],
        "investment_verdict": {
            "rating": "Not Applicable", "direction": "neutral", "confidence": None,
            "horizon": "", "top_picks": [], "risks": [], "catalysts": [],
            "opportunity_score": None, "risk_level": "", "suitable_for": "",
        },
        "market_chart": {"labels": [], "series": []},
        "graph": {"nodes": [], "edges": []},
        "citations": [], "decision_intelligence": None,
        "confidence_data": {"level": "unscored", "score": None, "reasons": [], "breakdown": {}, "caveats": []},
    }


def _referential_no_context_response(query: str) -> dict:
    """P5 Stage 2, item 2: V3-native version of V2's
    _referential_no_context_response — a referential query ("What about its
    main competitor?") with no companies/sectors of its own and no prior
    session context to merge in. Previously fell through silently to
    whatever the specialist produced from near-empty evidence; now an
    honest admission, matching V2's behavior."""
    summary = (
        "This looks like a follow-up question, but there's no prior company or sector "
        "in this session to resolve it against. Try naming the company or sector directly, "
        "or ask this right after discussing one."
    )
    result = _degraded_shell(query, "referential_no_context", summary)
    result["follow_up_questions"] = ["Name the company or sector you're asking about"]
    return result


def _ambiguous_entity_response(query: str, ambiguous: dict) -> dict:
    """P5 Stage 2, item 4: completes V3's previously-partial inline
    ambiguous-entity shape (just {query, schema_version, needs_clarification,
    ambiguous_term, candidates} — missing degraded_reason and every other
    schema field) to parity with V2's _ambiguous_entity_response — real
    named candidates in the summary, not generic boilerplate, and a full
    schema-complete response like every other path returns.
    Confident classification (this term genuinely is ambiguous), not a
    failure — synthesis_incomplete stays True (this genuinely isn't a
    complete analysis) but the distinction from a true failure is carried
    by degraded_reason itself, not a different flag."""
    names = ", ".join(f'{c["name"]} ({c["symbol"]})' for c in ambiguous["candidates"])
    summary = (
        f'"{ambiguous["term"]}" names a group with multiple listed companies, not one '
        f"specific stock — did you mean one of: {names}? Ask about a specific company by "
        "name for a real analysis."
    )
    result = _degraded_shell(query, "ambiguous_entity", summary)
    result["needs_clarification"] = True
    result["ambiguous_term"] = ambiguous["term"]
    result["candidates"] = ambiguous["candidates"]
    result["follow_up_questions"] = [f'What about {c["name"]}?' for c in ambiguous["candidates"][:3]]
    return result


def _unrecognized_company_response_v3(query: str) -> dict:
    """P5 Stage 2, item 6b: V3-native version of V2's
    _unrecognized_company_response, closing V3's second-to-last remaining
    import from ai_search_service.py. Confident classification (this query
    genuinely doesn't name a real, listed company), not a failure —
    synthesis_incomplete stays True per the shared shell (this still isn't
    a complete analysis) with degraded_reason distinguishing it from a
    real synthesis failure."""
    summary = (
        "This looks like it's asking about a specific company, but it doesn't match any "
        "company currently listed on the NSE/BSE in MarketRipple's database. Double-check "
        "the spelling, or ask about a sector or market theme instead."
    )
    return _degraded_shell(query, "unsupported_entity", summary)


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
    # P5 Stage 2 (2026-08-07): _run_market_pulse_search relocated too — this
    # is now a same-package import, closing one of V3's last two remaining
    # V2 imports (see market_pulse.py's docstring).
    from app.services.ai_search.decision_intent import _detect_decision_intent
    from app.services.ai_search.market_pulse import _detect_market_pulse_async, _run_market_pulse_search

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
    # session_context is threaded through even at this pre-resolution point
    # (see cache.py's _session_signature) — the two sessions with different
    # held context must never collide on identical literal query text.
    exact_hit = cache_mod.get_response(query, session_context=session_context)
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
        log.info("ai_search_v3.ambiguous_entity", term=ambiguous["term"])
        result = _ambiguous_entity_response(query, ambiguous)
        cache_mod.set_response(query, result, session_context=session_context)
        yield "finalizing", STAGE_LABELS["finalizing"], result
        return

    # Phase 1.7 — merges session-held companies/sectors into this query's
    # own entities when it looks like a follow-up continuing the existing
    # discussion ("What about BEML?", "Which is safer?") rather than a
    # fresh, self-contained question — see session_context.resolve_context's
    # docstring for the exact conditions. Deterministic, before any LLM
    # call, per the spec's own performance rule.
    entities, context_used = session_context_mod.resolve_context(query, entities, session_context)

    # P5 Stage 2, item 2: a referential query ("What about its main
    # competitor?") that still has nothing to anchor on even after
    # attempting the session-context merge above — matches V2's ordering
    # exactly (checked after merge, so a successful merge never trips this).
    if (
        session_context_mod._REFERENTIAL_RE.search(query)
        and not entities.get("companies") and not entities.get("sectors")
    ):
        log.info("ai_search_v3.referential_no_context", query=query[:80])
        result = _referential_no_context_response(query)
        cache_mod.set_response(query, result, session_context=session_context)
        yield "finalizing", STAGE_LABELS["finalizing"], result
        return

    if entities_mod.looks_like_unrecognized_company(query, entities):
        result = _unrecognized_company_response_v3(query)
        suggestions = entities_mod.suggest_companies(query)
        if suggestions:
            result["answer"]["summary"] += " Did you mean: " + ", ".join(
                f"{s['name']} ({s['symbol']})" for s in suggestions
            ) + "?"
            result["company_suggestions"] = suggestions
        cache_mod.set_response(query, result, session_context=session_context)
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

    # P5 Stage 2, item 3 / Phase 6G Slice 1: resolve_comparison always
    # collapses to exactly 2 entities (holding/target) with zero signal
    # when more were actually resolved. Matches V2's exact detection
    # formula. Phase 6G Slice 1 gave the comparison specialist a real
    # parallel-analysis path (entity_analyses[]) for 3+ entities — see
    # specialists/comparison.py's _build_multi_compare_prompt — but that
    # path itself caps at 3 entities (a deliberate V3 limit, not V2
    # parity: even after fixing the prompt's schema shape, a 3-entity
    # request with V3's full nested schema was still truncating before
    # completing on some fallback models — see that function's own
    # docstring). So "dropped" here means genuinely beyond the 3-entity
    # cap, not "beyond 2" the way it did before this port — a 3-company
    # query now has ZERO drops; a 4+-company query still honestly
    # discloses whichever ones didn't make the cap, in company_matches
    # order (the same order _build_multi_compare_prompt itself uses).
    is_multi_compare = len(entities.get("companies") or []) >= 3
    dropped_companies: list[str] = []
    if is_multi_compare and is_cmp:
        matches = entities.get("company_matches") or []
        kept = {m["name"] for m in matches[:3]}
        dropped_companies = [m["name"] for m in matches if m["name"] not in kept]

    # Layer 2 — semantic cache: same resolved companies/intent shape as a
    # previously-answered, differently-phrased query.
    semantic_hit = cache_mod.get_response(query, intent_data, entities, session_context=session_context)
    if semantic_hit is not None:
        log.info("ai_search_v3.cache_hit", layer="semantic", query=query[:50])
        yield "finalizing", STAGE_LABELS["finalizing"], semantic_hit
        return

    log.info("ai_search_v3.start", query=query[:50])

    yield "evidence", STAGE_LABELS["evidence"], None
    evidence = await evidence_mod.collect(query, intent_data, entities, db)
    _t_stage = _checkpoint("evidence_collection_ms", _t_stage)

    specialist, specialist_kind = _route_specialist(query, intent_data, entities)
    # Free-tier data track, Stage 1 (2026-08-06): same instrumentation as V2's
    # ai_search.done — entities + a thin_evidence flag. Uses evidence.source_count
    # (events+news+policies, this pipeline's own already-computed total) rather
    # than reimplementing V2's events+news-only formula — same "source_count < 3"
    # threshold _confidence caveats/validation already treat as thin elsewhere,
    # adapted to this pipeline's evidence bundle shape rather than copied verbatim.
    log.info(
        "ai_search_v3.routed", specialist=specialist_kind, query=query[:50],
        entities=entities, thin_evidence=(evidence.source_count < 3),
    )

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
        db, entities, dropped_companies=dropped_companies,
        intent_data=intent_data, is_multi_compare=is_multi_compare,
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
        cache_mod.set_response(query, response, intent_data, entities, session_context=session_context)

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
    db: AsyncSession, entities: dict,
    dropped_companies: list[str] | None = None,
    intent_data: dict | None = None,
    is_multi_compare: bool = False,
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
    confidence_breakdown = await postprocess.compute_confidence_breakdown(evidence, ai, evidence.mie_state)
    response_id = str(uuid.uuid4())

    # P5 Stage 3, item 3 — real opportunity_score, reusing V2's own sourcing
    # mechanism verbatim: a live DB lookup against Opportunity Radar's
    # pre-computed table, matched by this query's own companies/sectors.
    # None (not a fabricated 50) when no Radar match exists — true for most
    # queries, since Radar only tracks a curated subset of names. A visual
    # gauge elsewhere may still choose a neutral midpoint for display; this
    # field itself never fabricates one.
    opportunity_score: float | None = None
    try:
        _opp_terms = (entities.get("companies") or []) + (entities.get("sectors") or [])
        if _opp_terms:
            from app.services.opportunity_service import OpportunityService
            _opp_hits = await OpportunityService(db).list_by_sector_or_theme(_opp_terms[:4], limit=1)
            if _opp_hits:
                opportunity_score = _opp_hits[0]["opportunity_score"]
    except Exception as exc:
        log.warning("ai_search_v3.opportunity_score_fail", exc=str(exc)[:120])

    # P5 Stage 3, item 1 — Investment Verdict Engine, the same engine V2
    # already uses for this exact field (investment_verdict_engine.py, not
    # opportunity_intelligence.py — its output shape is a structural mismatch
    # for engine_verdict, see Stage 3's investigation report). Produces the
    # identical {rating, tier, direction, ...} shape the frontend already
    # renders as "Data engine rating" — no frontend change needed. V2's own
    # rating-override reconciliation (verdict_basis, tier-disagreement logic)
    # is intentionally NOT ported here — out of this item's stated scope.
    engine_verdict: dict | None = None
    try:
        from app.services.investment_verdict_engine import compute_investment_verdict as _compute_engine_verdict
        engine_verdict = _compute_engine_verdict(
            direction=(evidence.mie_state or {}).get("signals", {}).get("direction", "sideways"),
            confidence_score=confidence_breakdown["final_confidence"],
            opportunity_score=opportunity_score,
            vix_level=evidence.vix_level,
        )
    except Exception as exc:
        log.warning("ai_search_v3.engine_verdict_fail", exc=str(exc)[:120])

    # P5 Stage 3, item 4 — real horizon only when the LLM didn't state one;
    # a real LLM-stated horizon is always kept as-is.
    _llm_horizon = (ai.get("investment_verdict") or {}).get("horizon")
    horizon = _llm_horizon or compute_horizon(
        evidence.vix_level, evidence.similar_historical, ai.get("medium_term"), ai.get("long_term"),
    )

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
        # P5 Stage 2, item 5: degraded_reason is the single source of truth;
        # synthesis_incomplete is derived from it, never set independently.
        # Priority: was_degraded (failed to generate at all) > grounding_collapsed
        # (generated, but its own supporting companies collapsed during
        # validation) > multi_entity_partial (generated fine, just covers
        # fewer entities than named) — each a strictly less severe
        # degradation than the one before it. P5 Stage 4: was_degraded's
        # reason was hardcoded to "parse_failure" regardless of cause — now
        # reads the real cause (base.py's parse_specialist_json sets
        # "capacity" when the LLM never returned any text at all, vs
        # "parse_failure" when it did but couldn't be parsed), mirroring
        # V2's existing distinction.
        "degraded_reason": (
            ai.get("_degraded_reason", "parse_failure") if was_degraded
            else "grounding_collapsed" if validation_report.grounding_collapsed
            else ("multi_entity_partial" if dropped_companies else None)
        ),
        "synthesis_incomplete": was_degraded or bool(dropped_companies) or validation_report.grounding_collapsed,
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
        "investment_verdict": {
            **ai.get("investment_verdict", {}),
            "confidence": confidence_breakdown["final_confidence"],
            "horizon": horizon,
            "opportunity_score": opportunity_score,
            "engine_verdict": engine_verdict,
        },
        "market_chart": chart,
        "graph": graph,
        "citations": list({a.get("source", "") for a in evidence.news if a.get("source")}),
        "decision_intelligence": ai.get("decision_intelligence"),
        "confidence_data": {
            "level": confidence_breakdown["level"],
            "score": confidence_breakdown["final_confidence"],
            "reasons": confidence_breakdown["reasons"],
            # Phase 6G Slice 3 — was hardcoded {} regardless of the real
            # breakdown already computed just above (postprocess.py's own
            # 5-part normalized view over confidence_service's raw
            # per-factor points). Found auditing page_intelligence_service's
            # V3 migration: this caller forwards confidence_data untouched,
            # so an empty breakdown was a real, silent content loss versus
            # V2's populated one — not specific to that one caller, fixed
            # here so every V3 consumer benefits.
            "breakdown": {
                "evidence_quality": confidence_breakdown["evidence_quality"],
                "market_confirmation": confidence_breakdown["market_confirmation"],
                "historical_similarity": confidence_breakdown["historical_similarity"],
                "data_freshness": confidence_breakdown["data_freshness"],
                "reasoning_confidence": confidence_breakdown["reasoning_confidence"],
            },
            # P5 Stage 2, item 3: honest signal when a 3+-entity comparison
            # got collapsed to the 2 actually compared — never silent.
            # P5 Stage 4: same treatment when the companies array itself
            # collapsed during validation — the verdict's rating was already
            # downgraded by _check_grounding_collapse; this is the
            # user-facing explanation for why.
            "caveats": (
                ([f"This comparison covers 2 of {len(dropped_companies) + 2} companies named in "
                  f"the query — {', '.join(dropped_companies)} not included."]
                 if dropped_companies else [])
                + ([f"This verdict's supporting company data could not be validated — treat this "
                    f"{(ai.get('investment_verdict') or {}).get('direction', 'directional')} call with reduced confidence."]
                   if validation_report.grounding_collapsed else [])
            ),
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
        # Phase 6G Slice 1 — present on _degraded_shell but previously
        # missing from this, the successful path; no consumer anywhere in
        # the backend reads any of these 3, so this is schema-shape
        # consistency, not a behavior change.
        "market_impact_horizons": {},
        "what_to_monitor": [],
        "ai_reasoning_methods": [],
    }

    intent_data = intent_data or {}

    # Phase 6G Slice 1 — list_picks real-screener override, ported verbatim
    # from V2 (ai_search_service.py). Real, non-LLM: pulls sector/theme-
    # matched opportunities from the Opportunity Engine, cross-referenced
    # against the real NSE universe, and overrides the AI's own invented
    # top_picks when the screener found anything real — the AI's list is
    # only kept as a fallback when nothing real matched. Runs after the
    # response dict above is fully built so it can override in place,
    # exactly mirroring V2's own after-generation override, not a
    # different route or a second LLM call.
    if intent_data.get("intent") == "list_picks":
        try:
            from app.services.ai_recommendation_engine import compute_recommendations
            from app.services.ai_search.retrieval import _words

            _pick_stopwords = {
                "give", "me", "the", "top", "best", "and", "for", "which", "what",
                "are", "should", "recommend", "picks", "pick", "stock", "stocks",
                "companies", "shares", "invest", "buy", "list", "some", "with",
            }
            _pick_terms = (entities.get("sectors") or []) + [
                w for w in _words(query) if w not in _pick_stopwords and len(w) >= 4
            ]
            _engine_picks = await compute_recommendations(db, _pick_terms, intent_data.get("pick_count") or 3)
            response["investment_verdict"]["verdict_basis"] = "real_screener" if _engine_picks else "ai_only_no_real_match"
            response["investment_verdict"]["engine_recommendations"] = _engine_picks
            if _engine_picks:
                response["investment_verdict"]["top_picks"] = [c["symbol"] for c in _engine_picks]
        except Exception as exc:
            log.warning("ai_search_v3.list_picks_screener_fail", exc=str(exc)[:120])

    # Phase 6G Slice 1 — pairwise Decision Engine, ported verbatim from V2.
    # Real, non-LLM: two independent Investment Verdict Engine reads (same
    # market-wide direction/confidence/VIX, each entity's own real
    # Opportunity Engine score) plus a real P/E comparison when both
    # sides' valuation was fetched. Reuses evidence.valuation/vix_level,
    # already collected earlier in this same request — no new data fetch.
    # Excluded for is_multi_compare, matching V2's exact boundary: this is
    # a genuine two-entity pairwise computation, not attempted for 3+.
    if (
        specialist_kind == "comparison" and not is_multi_compare
        and isinstance(response.get("decision_intelligence"), dict)
    ):
        try:
            from app.services.decision_engine import compute_decision
            from app.services.opportunity_service import OpportunityService

            _matches = entities.get("company_matches") or []
            _name_to_symbol = {m.get("name"): m.get("symbol") for m in _matches if m.get("name") and m.get("symbol")}
            _sym_a = _name_to_symbol.get(intent_data.get("holding") or "")
            _sym_b = _name_to_symbol.get(intent_data.get("target") or "")
            if _sym_a and _sym_b:
                async def _opp_for(sym: str) -> float | None:
                    hits = await OpportunityService(db).list_by_sector_or_theme([sym], limit=1)
                    return hits[0]["opportunity_score"] if hits else None
                _opp_a, _opp_b = await asyncio.gather(_opp_for(_sym_a), _opp_for(_sym_b))
                response["decision_intelligence"]["engine_recommendation"] = compute_decision(
                    entity_a_symbol=_sym_a, entity_b_symbol=_sym_b,
                    direction=(evidence.mie_state or {}).get("signals", {}).get("direction", "sideways"),
                    confidence_score=confidence_breakdown["final_confidence"], vix_level=evidence.vix_level,
                    opportunity_score_a=_opp_a, opportunity_score_b=_opp_b,
                    valuation_a=evidence.valuation.get(_sym_a), valuation_b=evidence.valuation.get(_sym_b),
                )
        except Exception as exc:
            log.warning("ai_search_v3.decision_engine_fail", exc=str(exc)[:120])

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

    # Asynchronously persist predictions for the learning engine (non-blocking).
    # Shared with V2 — see prediction_recording.py's module docstring for why
    # this was missing from V3 (the primary user-facing pipeline) until now.
    from app.services.ai_search.prediction_recording import store_search_predictions
    asyncio.create_task(
        store_search_predictions(
            result=response,
            confidence_score=confidence_breakdown["final_confidence"],
            confidence_level=confidence_breakdown["level"],
            confidence_breakdown=confidence_breakdown,
        ),
        name="prediction-store-v3",
    )

    return response
