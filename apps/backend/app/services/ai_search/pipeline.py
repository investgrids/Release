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

from app.services import request_deadline
from app.services.ai_search.macro_drivers import macro_driver
from app.services.ai_search import cache as cache_mod
from app.services.ai_search import answer_authorization as auth_mod
from app.services.ai_search import claim_sources as claim_sources_mod
from app.services.ai_search import conclusion_scope as scope_mod
from app.services.ai_search import education as education_mod
from app.services.ai_search import evidence_sufficiency as suff_mod
from app.services.ai_search import structured_authorization as struct_mod
from app.services.ai_search.company_matching import filter_events_to_companies
from app.services.ai_search.degraded_shape import build_degraded_shape
from app.services.ai_search.evidence_filter import plan_for
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
from app.services.ai_search.ui_mode import classify_ui_mode
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
        "query": query, "schema_version": SCHEMA_VERSION, "response_id": str(uuid.uuid4()),      # Step 5: every final response carries a response_id (feedback correlation)
        "synthesis_incomplete": True, "degraded_reason": degraded_reason,
        "answer": {
            "summary": summary, "bottom_line": summary,
            "what_happened": "", "why_it_happened": "", "immediate_impact": "",
            "medium_term": "", "long_term": "", "what_priced_in": "",
            "risks": [], "opportunities": [],
            "confidence": None, "confidence_level": "unscored",
            "sentiment": None, "sources_count": 0,
        },
        "key_drivers": [], "insights": [], "companies": [], "sectors": [],
        "related_events": [], "news": [], "policies": [], "timeline": [],
        "historical_comparison": [], "ripple_chain": [], "scenarios": {},
        "market_impact_horizons": [], "what_to_monitor": [],
        "ai_reasoning_methods": [], "follow_up_questions": [],
        "investment_verdict": {
            "rating": "Not Applicable", "direction": None, "confidence": None,
            "horizon": "", "top_picks": [], "risks": [], "catalysts": [],
            "opportunity_score": None, "risk_level": "", "suitable_for": "",
        },
        "market_chart": {"labels": [], "series": []},
        "graph": {"nodes": [], "edges": []},
        "citations": [], "decision_intelligence": None,
        "confidence_data": {"level": "unscored", "score": None, "reasons": [], "breakdown": {}, "caveats": []},
        # Step 5: the same unscored confidence fields as every other class
        "confidence_breakdown": {"final_confidence": None, "level": "unscored"},
        "confidence": {"status": "unscored", "score": None, "components": {"evidence_quality": None, "market_confirmation": None, "historical_similarity": None, "data_freshness": None}},
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
    if not entities.get("companies"):
        if _SECTOR_TRIGGER.search(query):
            return sector_specialist, "sector"
        # Step 4A: a resolved sector plus a policy or macro driver is a sector transmission question even without the literal word "sector" ("How would a weaker rupee affect Indian IT exporters?").
        if entities.get("sectors") and (entities.get("policies") or macro_driver(query)):
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
    # Step 3.4A: emitted only when the pre-model gate stops the run (no specialist is called), so progress is never faked.
    "insufficient_evidence": "Evidence is not sufficient to support an analysis",
    # Step 4B: emitted only when a curated educational/product question is answered by its fixed contract (no retrieval, no model), so progress is never faked.
    "education": "Answering from MarketRipple's own explanation",
    # Step 4C: emitted instead of "insufficient_evidence" when a source FAILED during retrieval, so the failure is never reported as an absence of evidence.
    "retrieval_incomplete": "The evidence search did not complete",
    # Step 5: a definitional question with no reviewed explanation is answered with that fact, before any retrieval or model call.
    "education_not_covered": "Checking for a reviewed explanation",
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

    # Market Pulse stays V2's exact mechanism for real-data collection — a
    # different query family, out of scope for the specialist pipeline
    # (see plan) — but joins a cache discipline of its OWN (2026-09-22,
    # cache-freshness audit): previously this branch never checked or
    # wrote any query cache at all, so an identical "top gainers today"
    # asked twice re-fetched every live market feed AND re-called the LLM
    # synthesis both times. get_market_pulse_response/set_market_pulse_
    # response (cache.py) are a DEDICATED namespace, never exact_key()'s
    # — see that module's own docstring for why sharing a namespace with
    # research-answer caching would be wrong here, not just redundant:
    # the key itself encodes the current market session + IST trading
    # date, so a cached entry structurally cannot survive a pre-market ->
    # open, open -> closed, weekday -> weekend, or one-trading-date ->
    # another transition, and the TTL within a stable bucket is far
    # shorter (45s live / 300s closed) than a research answer's 30
    # minutes.
    if await _detect_market_pulse_async(query):
        cached_mp = cache_mod.get_market_pulse_response(query)
        if cached_mp is not None:
            yield "finalizing", STAGE_LABELS["finalizing"], cached_mp
            return
        mp_result = await _run_market_pulse_search(query)
        mp_result["schema_version"] = SCHEMA_VERSION
        mp_result["intent"] = "market_pulse"
        mp_result["ui_mode"] = "market_pulse"
        cache_mod.set_market_pulse_response(query, mp_result)
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
        and not session_context_mod.referential_has_antecedent(query)
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

    # Step 4B: a plain educational or product-knowledge question on a curated topic (P/E ratio, FII flows, the MarketRipple Score) is answered by its fixed contract: no retrieval, no model, nothing
    # invented. Questions naming a company, sector or policy, or asking for current or numeric data, never match and continue through the evidence-gated pipeline unchanged.
    _edu_topic = education_mod.topic_for(query, entities)
    if _edu_topic:
        log.info("ai_search_v3.education_contract", topic=_edu_topic, query=query[:60])
        yield "education", STAGE_LABELS["education"], None
        _ui = classify_ui_mode(specialist_kind="company", intent_data=intent_data, entities=entities, query=query)
        result = education_mod.build_response(query, _edu_topic, schema_version=SCHEMA_VERSION, ui_mode=_ui, intent=intent_data.get("intent", "general"))
        result["context_used"] = context_used
        yield "finalizing", STAGE_LABELS["finalizing"], result
        return

    # Step 5: every other definitional question (the evidence-free explanation plan) has no reviewed source to answer from. It used to reach a model with no evidence and no authorization; it now gets an honest
    # "not covered yet" response. Current-data wording never gets here (plan_for refuses it the explanation plan).
    if plan_for(query, intent_data, entities).kind == "explanation":
        log.info("ai_search_v3.education_not_covered", query=query[:60])
        yield "education_not_covered", STAGE_LABELS["education_not_covered"], None
        _ui = classify_ui_mode(specialist_kind="company", intent_data=intent_data, entities=entities, query=query)
        result = education_mod.build_not_covered_response(query, schema_version=SCHEMA_VERSION, ui_mode=_ui, intent=intent_data.get("intent", "general"))
        result["context_used"] = context_used
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
    _usable = request_deadline.usable()
    if _usable is None:
        evidence = await evidence_mod.collect(query, intent_data, entities, db)
    else:
        # Step 3.4H.2b: retrieval may spend what remains minus the smallest provider attempt, so a specialist call can still start. A cut-off is an infrastructure condition, recorded as a
        # retrieval failure and answered "unavailable": never "no evidence exists" and never an empty bundle sent through Gate A.
        try:
            _budget = _usable - (request_deadline.min_attempt() or 0)
            if _budget <= 0:
                raise asyncio.TimeoutError
            evidence = await asyncio.wait_for(evidence_mod.collect(query, intent_data, entities, db), timeout=_budget)
        except asyncio.TimeoutError:
            request_deadline.mark_expired()
            log.warning("ai_search_v3.retrieval_deadline", query=query[:80], budget_s=round(max(_usable - (request_deadline.min_attempt() or 0), 0), 2))
            _empty = evidence_mod.EvidenceBundle()
            _empty.retrieval_failures = {"deadline": "TimeoutError"}
            yield "done", STAGE_LABELS["finalizing"], _deadline_response(query, _empty, entities, intent_data, "retrieval_deadline_exceeded", stage_ms, _t0, context_used)
            return
    _t_stage = _checkpoint("evidence_collection_ms", _t_stage)

    specialist, specialist_kind = _route_specialist(query, intent_data, entities)
    evidence.prompt_kind = specialist_kind      # Step 3.4G.2: the evidence index and Gate B's corpus are cut to what this specialist's prompt actually shows
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

    # Gate A (Step 3.4A): no evidence capable of supporting the requested analysis means no analytical model call.
    from app.api.companies import _NSE_UNIVERSE as _UNIV
    suff = suff_mod.assess(query, intent_data, entities, evidence, _UNIV)
    if suff["status"] == suff_mod.INSUFFICIENT:
        log.warning("ai_search_v3.insufficient_evidence", query=query[:80], kind=suff["kind"], missing=suff["missing"], reason=suff["reason"],
                    retrieval_failures=dict(getattr(evidence, "retrieval_failures", {}) or {}))
        _stage = "retrieval_incomplete" if getattr(evidence, "retrieval_failures", None) else "insufficient_evidence"
        yield _stage, STAGE_LABELS[_stage], None
        response = _build_insufficient_response(query, evidence, entities, intent_data, specialist_kind, suff)
        response["timing"] = {**stage_ms, "total_ms": round((time.monotonic() - _t0) * 1000, 1)}
        response["context_used"] = context_used
        response["watch_subject"] = None
        yield "done", STAGE_LABELS["finalizing"], response      # deliberately not cached and no Investment Watch snapshot: the evidence may change
        return

    # Step 3.4H.2b checkpoint: do not start a generation that cannot finish inside the request budget.
    _u = request_deadline.usable()
    if _u is not None and _u < (request_deadline.min_attempt() or 0):
        request_deadline.mark_expired()
        log.warning("ai_search_v3.deadline_before_specialist", query=query[:80], usable_s=round(_u, 2))
        yield "done", STAGE_LABELS["finalizing"], _deadline_response(query, evidence, entities, intent_data, "deadline_exceeded", stage_ms, _t0, context_used)
        return

    yield "reasoning", STAGE_LABELS["reasoning"], None
    parsed, was_degraded = await specialist.run(query, evidence, intent_data, entities)
    _t_stage = _checkpoint("reasoning_ms", _t_stage)
    if was_degraded and request_deadline.expired():
        parsed = {**parsed, "_degraded_reason": "deadline_exceeded"}      # the provider chain stopped because the request budget ran out, not because every provider failed
    _rem = request_deadline.remaining()
    if _rem is not None and _rem < _AUTHORIZATION_MIN_S:
        # Not enough time left to authorize and assemble safely: fail closed. Generated content is never published without Gate B.
        log.warning("ai_search_v3.deadline_before_authorization", query=query[:80], remaining_s=round(_rem, 2))
        yield "done", STAGE_LABELS["finalizing"], _deadline_response(query, evidence, entities, intent_data, "deadline_exceeded", stage_ms, _t0, context_used)
        return

    yield "finalizing", STAGE_LABELS["finalizing"], None
    validated, validation_report = validation_mod.validate_and_repair(parsed)
    if not validation_report.clean:
        log.info(
            "ai_search_v3.validation_repairs",
            query=query[:50], repairs=validation_report.repairs, omissions=validation_report.omissions,
        )
    _t_stage = _checkpoint("validation_ms", _t_stage)

    # Gate B (Step 3.4A): a generated research answer is shown only if its factual claims are traceable to admissible evidence. Otherwise it is withheld (never repaired by another
    # model, never edited sentence by sentence) and the rejected generation is kept for diagnostics.
    auth = {"applicable": False, "authorized": True, "reasons": []}
    if not was_degraded:
        auth = auth_mod.authorize(validated, evidence, entities, _UNIV, query)
        # Step 3.4D-2: the conclusion must not be broader than the evidence supports (valuation-only evidence never authorizes an overall company-strength conclusion).
        cscope = scope_mod.assess(query, intent_data, entities, evidence, _UNIV)
        overreach = scope_mod.overreach(validated, cscope)
        if overreach:
            auth = {**auth, "authorized": False, "reasons": [*auth["reasons"], "conclusion_scope_exceeded"], "conclusion_overreach_count": len(overreach)}
        if not auth["authorized"]:
            yield "finalizing", STAGE_LABELS["finalizing"], None
            response = _build_rejected_response(query, validated, evidence, entities, intent_data, specialist_kind, auth)
            response["timing"] = {**stage_ms, "total_ms": round((time.monotonic() - _t0) * 1000, 1)}
            response["context_used"] = context_used
            response["watch_subject"] = None
            yield "done", STAGE_LABELS["finalizing"], response
            return

    # Step 3.4D-2: LLM-generated structured analytical claims (rating, direction, sentiment, confidence, probabilities, scores, winner/preference blocks) are never public by themselves. They are replaced
    # by an explicit unavailable state before assembly; deterministic producers (confidence breakdown, engine verdict, pairwise decision engine) still run in code.
    _rem = request_deadline.remaining()
    if _rem is not None and _rem < 0:
        log.warning("ai_search_v3.deadline_before_assembly", query=query[:80], remaining_s=round(_rem, 2))
        yield "done", STAGE_LABELS["finalizing"], _deadline_response(query, evidence, entities, intent_data, "deadline_exceeded", stage_ms, _t0, context_used)
        return

    cscope = scope_mod.assess(query, intent_data, entities, evidence, _UNIV)
    public_ai, withheld_structured = (validated, []) if was_degraded else struct_mod.sanitize(validated)
    response = await _assemble_response(
        query, public_ai, evidence, specialist_kind, was_degraded, validation_report,
        db, entities, dropped_companies=dropped_companies,
        intent_data=intent_data, is_multi_compare=is_multi_compare, conclusion_scope=cscope,
    )
    _checkpoint("assembly_ms", _t_stage)
    if not was_degraded:
        response["conclusion_scope"] = scope_mod.public_summary(cscope)
        response["structured_authorization"] = struct_mod.public_summary(withheld_structured)
        for s in response.get("sectors") or []:      # a status derived from a withheld LLM outlook would itself be an unauthorized conclusion
            s.pop("status", None)
            s.pop("time_horizon", None)
        note = scope_mod.partial_note(cscope, {m.get("symbol"): m.get("name") for m in (entities.get("company_matches") or []) if m.get("symbol")})
        if note:
            response.setdefault("confidence_data", {}).setdefault("caveats", []).append(note)
    response["evidence_sufficiency"] = _public_sufficiency(suff)
    response["answer_authorization"] = auth_mod.public_summary(auth)
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


from app.services.ai_search.enrichment import profile_for as _profile_for


def attach_snapshots(companies: list, valuation: dict | None, profile=None) -> None:
    """Expose, per company, a structured `snapshot` for the entity card and comparison table: the figures the model was already given (P/E, P/B, 52-week range) plus display-only profile
    figures (market cap in INR crore, sector as reported). The valuation figures are exactly what evidence.valuation holds (so the Gate B corpus is unchanged); the profile figures come from
    the same Ticker.info call and never enter the evidence. Nothing is fetched here."""
    for c in companies:
        sym = str(c.get("symbol", "")).upper()
        v = (valuation or {}).get(sym) or {}
        snap = {k: v[src] for k, src in (("pe", "pe"), ("pb", "pb"), ("week52_low", "52w_low"), ("week52_high", "52w_high")) if v.get(src) is not None}
        if profile is not None:
            snap.update({k: val for k, val in (profile(sym) or {}).items() if k in ("market_cap_cr", "sector") and val is not None})
        if snap:
            c["snapshot"] = snap


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
    was_cached = not stages_seen & {"reasoning", "insufficient_evidence", "education", "retrieval_incomplete", "education_not_covered"}
    return result, was_cached


# Step 3.4H.2b: the smallest time left after generation in which Gate B and assembly can still run.
_AUTHORIZATION_MIN_S = 0.25


def _deadline_response(query: str, evidence, entities: dict, intent_data: dict | None, reason: str, stage_ms: dict, t0: float, context_used) -> dict:
    """Fail-closed response when the request budget ran out (3.4H.2b). Same degraded shape as a capacity failure; never a verdict or a statement about the evidence's existence."""
    kind = _route_specialist(query, intent_data or {}, entities)[1]
    response = _build_degraded_response(query, {}, evidence, kind, reason, entities, str(uuid.uuid4()), intent_data)
    response["timing"] = {**stage_ms, "total_ms": round((time.monotonic() - t0) * 1000, 1)}
    response["context_used"] = context_used
    response["watch_subject"] = None
    failures = dict(getattr(evidence, "retrieval_failures", {}) or {})
    if failures:
        response["_retrieval_failures"] = failures
    return response


def _filter_events_to_entities(events: list[dict], symbols: list[str]) -> list[dict]:
    """Thin wrapper over the shared, deterministic company<->event
    matching rule (company_matching.py) — extracted there (2026-09-21
    review) so AEV2's citation validator can reuse the exact same rule
    instead of maintaining its own copy that could silently drift."""
    return filter_events_to_companies(events, symbols)


def _premise_check(evidence) -> dict:
    """not_applicable | supported | not_established (no eligible evidence confirms the event the question asserts)."""
    p = getattr(evidence, "premise", None) or {}
    if not p.get("required"):
        return {"status": "not_applicable", "terms": []}
    return {"status": "supported" if p.get("supported") else "not_established", "terms": p.get("terms") or [], "supporting": p.get("supporting") or []}


def _public_sufficiency(suff: dict) -> dict:
    return {k: suff.get(k) for k in ("status", "kind", "required", "satisfied", "missing", "reason", "missing_entities", "context")}


RETRIEVAL_FAILED_TITLE = "The evidence search did not complete"
RETRIEVAL_FAILED_BODY = ("MarketRipple couldn't finish searching its evidence for this question just now, so it can't tell whether supporting evidence exists. "
                         "No conclusion was drawn. Please try again in a moment.")


def _build_insufficient_response(query: str, evidence, entities: dict, intent_data: dict | None, specialist_kind: str, suff: dict) -> dict:
    """Deterministic public response when the evidence cannot support the analysis. No model was called. No verdict, confidence, timeline, scenario, figure or forecast: the shared degraded
    shape carries none. States exactly what cannot be established; verified related evidence (if any) is listed separately as context."""
    from app.api.companies import _NSE_UNIVERSE
    title, body = suff_mod.public_message(suff, entities, _NSE_UNIVERSE, getattr(evidence, "premise", None))
    reason, sufficiency = "insufficient_evidence", _public_sufficiency(suff)
    if getattr(evidence, "retrieval_failures", None):
        # Step 4C: Gate A's verdict is unchanged, but when a source failed during retrieval the public answer must not say evidence does not exist: it says the search did not complete.
        title, body, reason, sufficiency = RETRIEVAL_FAILED_TITLE, RETRIEVAL_FAILED_BODY, "retrieval_failed", None
    symbols = entities.get("companies") or []
    related = _filter_events_to_entities(evidence.events, symbols)[:6]
    return build_degraded_shape(
        query=query, response_id=str(uuid.uuid4()), schema_version=SCHEMA_VERSION, specialist_kind=specialist_kind, degraded_reason=reason, summary=body,
        related_events=related, sources_count=len(related), source_attribution=[f"event:{e.get('id')}" for e in related if e.get("id")],
        intent=(intent_data or {}).get("intent", "general"),
        ui_mode=classify_ui_mode(specialist_kind=specialist_kind, intent_data=intent_data, entities=entities, query=query),
        evidence_sufficiency=sufficiency, premise_check=_premise_check(evidence), public_title=title,
    )


def _build_rejected_response(query: str, generation: dict, evidence, entities: dict, intent_data: dict | None, specialist_kind: str, auth: dict) -> dict:
    """Public response when a generated answer is NOT authorized. Carries the outcome and reason codes only; the withheld generation travels in an internal field the finalizer strips and in
    answer_authorization.REJECTED_GENERATIONS."""
    title, body = auth_mod.rejection_message(auth)
    symbols = entities.get("companies") or []
    related = _filter_events_to_entities(evidence.events, symbols)[:6]
    response_id = str(uuid.uuid4())
    shape = build_degraded_shape(
        query=query, response_id=response_id, schema_version=SCHEMA_VERSION, specialist_kind=specialist_kind, degraded_reason="claims_not_authorized", summary=body,
        related_events=related, sources_count=len(related), source_attribution=[f"event:{e.get('id')}" for e in related if e.get("id")],
        intent=(intent_data or {}).get("intent", "general"),
        ui_mode=classify_ui_mode(specialist_kind=specialist_kind, intent_data=intent_data, entities=entities, query=query),
        premise_check=_premise_check(evidence), answer_authorization=auth_mod.public_summary(auth), public_title=title,
    )
    auth_mod.remember(response_id, query, auth, generation, evidence.index())
    shape["_rejected_generation"] = {"generation": generation, "reasons": list(auth["reasons"]), "unsupported_figures": auth.get("unsupported_figures")}
    return shape


def degraded_evidence_sentence(shown_events: int) -> str:
    """One sentence about the evidence shown with a degraded answer, derived from the count actually displayed."""
    if shown_events <= 0:
        return "No supporting evidence is shown for this question."
    return f"{shown_events} related event{'s' if shown_events != 1 else ''} found for this question {'are' if shown_events != 1 else 'is'} listed below."


def _build_degraded_response(
    query: str, ai: dict, evidence, specialist_kind: str, degraded_reason: str,
    entities: dict, response_id: str, intent_data: dict | None = None,
) -> dict:
    """Fail-closed shape for a genuinely failed synthesis (was_degraded=True
    from specialist.run()).

    Found live (2026-09-21): previously, base.py's hardcoded degraded_response()
    stub — a fixed "Neutral / 6-12 months / Macro uncertainty / Policy clarity"
    shell with no relation to the actual query — flowed through this same
    function's FULL analytical machinery untouched: a real, evidence-derived
    confidence score and a real engine_verdict got computed and attached right
    next to that fabricated verdict, producing a page that admits "synthesis
    failed" in the summary while presenting a fully-dressed investment
    analysis two sections below it (confidence %, horizon, risk level,
    scenarios, Research Outlook/Investment Watch disagreeing with each
    other) — none of it meaningfully about the query. Real evidence WAS
    already collected before the specialist call failed, so it's kept —
    filtered to only what's deterministically tied to the query's own
    resolved company (Event.companies), never news/policy (no company field
    exists on those rows) and never a keyword match. No verdict, confidence
    score, horizon, risk level, suitability, scenario, or engine computation
    is safe to show here — this is a distinct response shape, not a normal
    response with a warning banner on top."""
    symbols = entities.get("companies") or []
    related_events = _filter_events_to_entities(evidence.events, symbols)[:6]
    sources_count = len(related_events)
    summary = (
        ai.get("bottom_line") or ai.get("summary") or
        "Full AI analysis wasn't available for this query, with no generated conclusion, confidence score, or outlook."
    )
    # Step 2: the copy may only describe evidence that is actually displayed below. It used to promise "event and news data is available below" while the
    # degraded shape shows no news at all and only entity-tagged events (8 of 14 capacity-degraded baseline answers showed nothing).
    summary = summary + " " + degraded_evidence_sentence(len(related_events))
    # ui_mode/intent are structural routing metadata, not a verdict —
    # safe to carry through even here (they only tell the frontend which
    # shell variant's evidence layout to use, e.g. a comparison-shaped
    # degraded response still benefits from the 2-entity evidence table
    # rather than the single-entity one). Passed through the shared
    # builder itself (not bolted on after) so this stays on the same key
    # skeleton as safety_gate's degraded response.
    return build_degraded_shape(
        query=query, response_id=response_id, schema_version=SCHEMA_VERSION,
        specialist_kind=specialist_kind, degraded_reason=degraded_reason, summary=summary,
        related_events=related_events, sources_count=sources_count,
        source_attribution=[f"event:{e.get('id')}" for e in related_events if e.get("id")],
        intent=(intent_data or {}).get("intent", "general"),
        ui_mode=classify_ui_mode(
            specialist_kind=specialist_kind, intent_data=intent_data, entities=entities, query=query,
        ),
    )


# Step 3.4D-2.1: ui_modes whose question is itself market-wide, the only scopes where the market-wide engine verdict is a compatible thing to show.
MARKET_WIDE_UI_MODES = frozenset({"policy_macro_impact", "market_pulse"})


async def _assemble_response(
    query: str, ai: dict, evidence, specialist_kind: str, was_degraded: bool, validation_report,
    db: AsyncSession, entities: dict,
    dropped_companies: list[str] | None = None,
    intent_data: dict | None = None,
    is_multi_compare: bool = False,
    conclusion_scope: dict | None = None,
) -> dict:
    """Builds the final response dict — a strict superset of V2's shape
    (see schema.py) plus Phase 1's new fields. Reuses V2's own enrichment/
    graph-build machinery directly (untouched, imported) rather than
    reimplementing it.

    Fail-closed gate: a genuinely failed synthesis (was_degraded=True) never
    reaches any of the analytical computation below — see
    _build_degraded_response's docstring for the real defect this closes
    (confidence/horizon/engine_verdict were being computed from real evidence
    and attached to a hardcoded, query-irrelevant verdict stub)."""
    if was_degraded:
        return _build_degraded_response(
            query, ai, evidence, specialist_kind,
            ai.get("_degraded_reason", "parse_failure"), entities, str(uuid.uuid4()),
            intent_data=intent_data,
        )

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
    attach_snapshots(companies_enriched, evidence.valuation, profile=_profile_for)

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
            from app.core.config import settings
            from app.services.opportunity_service import OpportunityService
            _opp_hits = await OpportunityService(db).list_by_sector_or_theme(_opp_terms[:4], limit=1)
            if _opp_hits:
                # Batch E consumer migration, 2026-08-24 — V2 mode returns
                # current_strength, not opportunity_score (V2 doesn't have
                # that concept). Same real signal, real V2 field name.
                opportunity_score = _opp_hits[0]["current_strength"] if settings.opportunity_v2_promoted else _opp_hits[0]["opportunity_score"]
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
    # Step 5: the engine rating needs a MEASURED confidence. None exists (see postprocess.compute_confidence_breakdown), and inside the engine a missing direction, confidence, opportunity score and VIX
    # each fall back to a constant ("sideways", 0, 50, 15), so a rating computed without one would be a neutral conclusion manufactured from defaults. No engine rating is published instead.
    if confidence_breakdown["final_confidence"] is not None:
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

    # Claim-level source IDs: the evidence index the prompt used, and the model's claim_sources checked against it (non-blocking, see claim_sources.py).
    from app.api.companies import _NSE_UNIVERSE as _UNIVERSE
    evidence_index = evidence.index()
    claim_validation = claim_sources_mod.validate_claim_sources(ai.get("claim_sources"), evidence_index, ai, entities, _UNIVERSE, getattr(evidence, "premise", None))

    _response_ui_mode = classify_ui_mode(specialist_kind=specialist_kind, intent_data=intent_data, entities=entities, query=query)
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
        # Additive (2026-09-21, AI Answer UI work): intent is decision_
        # intent.py's own 12-label classification, unchanged; ui_mode is
        # ui_mode.py's projection of it (+ specialist_kind + entities)
        # onto one of the 8 first-release AI Answer layouts. Neither
        # replaces the other — see ui_mode.py's own docstring for why
        # this is an interim projection, not the eventual consolidated
        # IntentResolution contract.
        "intent": (intent_data or {}).get("intent", "general"),
        "ui_mode": _response_ui_mode,
        # Additive (2026-09-22, switch_analysis): the SAME holding/target
        # company names _route_specialist already resolved into
        # intent_data for comparison.py's prompt-building — zero new
        # retrieval. Serialized here specifically so CoreAnswer.
        # from_v3_response can recover them (intent_data itself is a
        # local variable that never otherwise reaches this dict) for
        # aev2/switch_analysis.py's deterministic assembly.
        "switch_holding": (intent_data or {}).get("holding"),
        "switch_target": (intent_data or {}).get("target"),
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
            "sentiment": ai.get("sentiment"),
            "sources_count": evidence.source_count,
        },
        "key_drivers": ai.get("key_drivers", []),
        "insights": ai.get("insights", []),
        "companies": companies_enriched,
        "sectors": sectors_raw,
        "related_events": evidence.events[:6],
        "news": evidence.news[:6],
        "policies": evidence.policies[:4],
        # Additive (2026-09-21, AEV2 citation-coverage extension): the
        # already-approved per-symbol CompanyAnnouncement relationship
        # (evidence.collect() fetches these via get_recent_announcements
        # (sym, ...) — a direct symbol query, not a keyword match). Never
        # read by V2/V3's own existing rendering, so this cannot change
        # V3's existing output; AEV2 uses it for claim evidence coverage.
        "announcements": evidence.announcements[:6],
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
            # Step 3.4D-2.1: engine_verdict is a MARKET-WIDE read (market direction, confidence, VIX). Next to a company, comparison, event or sector answer it reads as MarketRipple's view of
            # those companies, so it is public only for a market-wide / macro scope. The computed value is kept internally (stripped by the finalizer) for diagnostics.
            "engine_verdict": engine_verdict if _response_ui_mode in MARKET_WIDE_UI_MODES else None,
        },
        "market_chart": chart,
        "graph": graph,
        "citations": list({a.get("source", "") for a in evidence.news if a.get("source")}),
        "decision_intelligence": ai.get("decision_intelligence"),
        "_engine_verdict_internal": engine_verdict,
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
        # The frontend-facing confidence contract (2026-09-21 AI Answer UI
        # work) — same canonical formula aev2/confidence.py uses, shared
        # via postprocess.build_confidence_contract so the frontend never
        # recomputes weighting itself. Exposed on every V3 response, not
        # gated by AEV2 mode, since the new AI Answer shell needs it for
        # local end-to-end UI work while AEV2 assembly stays off publicly.
        "confidence": postprocess.build_confidence_contract(confidence_breakdown),
        "source_attribution": evidence.to_source_ids(),
        "evidence_index": claim_sources_mod.compact_index(evidence_index),
        "claim_sources": claim_validation["claims"],
        "claim_validation": {"status": claim_validation["status"], "summary": claim_validation["summary"], "uncovered": claim_validation.get("uncovered", [])},
        "premise_check": _premise_check(evidence),
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
        and (conclusion_scope or {}).get("partial") is not True      # Step 3.4D-2: a winner/preference needs the conclusion to be authorized, valuation-only evidence does not
        and confidence_breakdown["final_confidence"] is not None     # Step 5: the pairwise engine rates both sides from a measured confidence; with none it would rate from defaults
    ):
        try:
            from app.services.decision_engine import compute_decision
            from app.services.opportunity_service import OpportunityService

            _matches = entities.get("company_matches") or []
            _name_to_symbol = {m.get("name"): m.get("symbol") for m in _matches if m.get("name") and m.get("symbol")}
            _sym_a = _name_to_symbol.get(intent_data.get("holding") or "")
            _sym_b = _name_to_symbol.get(intent_data.get("target") or "")
            if _sym_a and _sym_b:
                from app.core.config import settings

                async def _opp_for(sym: str) -> float | None:
                    hits = await OpportunityService(db).list_by_sector_or_theme([sym], limit=1)
                    if not hits:
                        return None
                    # Batch E consumer migration, 2026-08-24 — current_strength
                    # in V2 mode (real V2 field, no opportunity_score concept).
                    return hits[0]["current_strength"] if settings.opportunity_v2_promoted else hits[0]["opportunity_score"]
                # sequential, not gathered: both lookups share this one AsyncSession and a session cannot run two operations at once (Step 3.4G.3)
                _opp_a = await _opp_for(_sym_a)
                _opp_b = await _opp_for(_sym_b)
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

    # Prediction recording moved to response_finalize.py (2026-09-21) —
    # scheduling it here, unconditionally, meant a response that parses
    # cleanly (was_degraded=False, so it reaches this point) but later
    # fails the recommendation-language safety gate downstream in
    # response_finalize.py would already have had a prediction recorded
    # from its pre-gate (unsafe) content by the time the gate ever ran.
    # response_finalize.py is the one place that knows the FINAL,
    # post-gate response every route actually returns, and the one place
    # that knows whether this was a fresh computation or a cache replay
    # — both required to record "one prediction per fresh, clean answer,
    # zero on cache hits or a gate rejection." See its own docstring.
    return response
