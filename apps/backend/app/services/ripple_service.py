"""
Ripple Engine service — orchestrates AI-powered market dependency graph generation.

Flow:
  1. Memory cache (1h TTL) → 2. DB cache → 3. AI generation → 4. Fallback template
"""
from __future__ import annotations

import time
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.models.ripple import RippleGraph

log = structlog.get_logger(__name__)

_cache: dict = {}
_CACHE_TTL = 3600  # 1 hour


def _cached(key: str) -> dict | None:
    entry = _cache.get(key)
    if entry and time.time() - entry[0] < _CACHE_TTL:
        return entry[1]
    return None


def _store(key: str, value: dict) -> None:
    _cache[key] = (time.time(), value)


# ── DB helpers ────────────────────────────────────────────────────────────────

async def _db_get(event_id: str, db: AsyncSession) -> dict | None:
    result = await db.execute(
        select(RippleGraph)
        .where(RippleGraph.event_id == event_id)
        .where(RippleGraph.scenario_type == "event")
        .order_by(RippleGraph.generated_at.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()
    if row and row.graph_data and row.graph_data.get("nodes"):
        return row.to_dict()
    return None


async def _db_save(
    event_id: str | None,
    event_title: str,
    event_summary: str,
    event_impact: float | None,
    graph_data: dict,
    insights: dict,
    scenario_type: str = "event",
    scenario_input: str | None = None,
    db: AsyncSession | None = None,
    source: str = "ai_generated",
) -> dict:
    rg = RippleGraph(
        event_id=event_id,
        scenario_type=scenario_type,
        scenario_input=scenario_input,
        event_title=event_title[:500] if event_title else "",
        event_summary=event_summary[:2000] if event_summary else "",
        event_impact=event_impact,
        graph_data=graph_data,
        insights=insights,
        source=source,
    )
    if db:
        db.add(rg)
        await db.commit()
        await db.refresh(rg)
    return rg.to_dict()


# ── Public API ────────────────────────────────────────────────────────────────

async def get_or_generate_ripple(
    event_id: str,
    event_title: str,
    event_summary: str,
    event_type: str,
    event_impact: float | None,
    companies: list,
    sectors: list,
    db: AsyncSession,
    force_regenerate: bool = False,
) -> dict:
    cache_key = f"ripple:event:{event_id}"

    if not force_regenerate:
        hit = _cached(cache_key)
        if hit:
            return hit
        try:
            db_hit = await _db_get(event_id, db)
        except Exception as exc:
            log.warning("ripple.db_get_error", error=str(exc))
            db_hit = None
        if db_hit:
            _store(cache_key, db_hit)
            return db_hit

    # Both the AI prompt's scaling hint and the fallback template selector
    # need *some* number even when the underlying event's real score is
    # unknown — this local-only fallback never leaves the function: the
    # `result`/DB row below still store the real (possibly None) value.
    _generation_hint = event_impact if event_impact is not None else 7.0

    # Try AI generation
    try:
        from app.services.ai_service import generate_ripple_graph as ai_gen
        ai_result = await ai_gen(
            title=event_title,
            summary=event_summary,
            event_type=event_type,
            impact_score=_generation_hint,
            companies=companies,
            sectors=sectors,
        )
    except Exception as exc:
        log.warning("ripple.ai_error", error=str(exc))
        ai_result = {}

    if ai_result and ai_result.get("nodes"):
        graph_data = {"nodes": ai_result["nodes"], "edges": ai_result.get("edges", [])}
        insights = ai_result.get("insights", {})
        source = "ai_generated"
        log.info("ripple.ai_generated", event_id=event_id, nodes=len(graph_data["nodes"]))
    else:
        log.info("ripple.fallback", event_id=event_id)
        fb = _build_fallback_graph(event_title, event_summary, event_type, _generation_hint, companies, sectors)
        graph_data = {"nodes": fb["nodes"], "edges": fb["edges"]}
        insights = fb.get("insights", {})
        source = "fallback_template"

    result = {
        "event_id":    event_id,
        "event_title": event_title,
        "event_impact": event_impact,
        "graph_data":  graph_data,
        "insights":    insights,
        "source":      source,
    }
    try:
        saved = await _db_save(
            event_id=event_id,
            event_title=event_title,
            event_summary=event_summary,
            event_impact=event_impact,
            graph_data=graph_data,
            insights=insights,
            db=db,
            source=source,
        )
        result = saved
    except Exception as exc:
        log.warning("ripple.db_save_error", error=str(exc))
    _store(cache_key, result)
    return result


async def generate_scenario_ripple(scenario_text: str, db: AsyncSession) -> dict:
    cache_key = f"ripple:scenario:{abs(hash(scenario_text[:100]))}"
    hit = _cached(cache_key)
    if hit:
        return hit

    try:
        from app.services.ai_service import generate_ripple_graph as ai_gen
        ai_result = await ai_gen(
            title=f"Scenario: {scenario_text[:80]}",
            summary=f"Hypothetical market scenario analysis: {scenario_text}",
            event_type="scenario",
            impact_score=7.5,
            companies=[],
            sectors=[],
        )
    except Exception:
        ai_result = {}

    if ai_result and ai_result.get("nodes"):
        graph_data = {"nodes": ai_result["nodes"], "edges": ai_result.get("edges", [])}
        insights = ai_result.get("insights", {})
        source = "ai_generated"
    else:
        fb = _build_fallback_graph(f"Scenario: {scenario_text}", scenario_text, "scenario", 7.5, [], [])
        graph_data = {"nodes": fb["nodes"], "edges": fb["edges"]}
        insights = fb.get("insights", {})
        source = "fallback_template"

    result = {
        "event_id":    None,
        "event_title": f"Scenario: {scenario_text[:100]}",
        "event_impact": 7.5,
        "graph_data":  graph_data,
        "insights":    insights,
        "source":      source,
    }
    try:
        saved = await _db_save(
            event_id=None,
            event_title=f"Scenario: {scenario_text[:100]}",
            event_summary=scenario_text,
            event_impact=7.5,
            graph_data=graph_data,
            insights=insights,
            scenario_type="scenario",
            scenario_input=scenario_text,
            db=db,
            source=source,
        )
        result = saved
    except Exception as exc:
        log.warning("ripple.db_save_error", error=str(exc))
    _store(cache_key, result)
    return result


# ── Fallback template system ──────────────────────────────────────────────────

def _detect_template(title: str, summary: str) -> str:
    text = (title + " " + summary).lower()
    if any(w in text for w in ["war", "conflict", "attack", "tension", "missile", "nuclear", "iran", "pakistan", "russia", "israel", "geopolit"]):
        return "geopolitical"
    if any(w in text for w in ["crude", "opec", "petroleum", "brent", "oil price"]):
        return "energy"
    if any(w in text for w in ["rbi", "repo rate", "rate cut", "rate hike", "interest rate", "monetary policy"]):
        return "monetary"
    if any(w in text for w in ["budget", "fiscal", "capex", "tax revenue", "deficit", "finance minister"]):
        return "fiscal"
    return "generic"


def _build_fallback_graph(
    title: str, summary: str, event_type: str, impact: float,
    companies: list, sectors: list,
) -> dict:
    t = _detect_template(title, summary)
    if t == "geopolitical":
        return _geopolitical_template(title, impact)
    if t == "energy":
        return _energy_template(title, impact)
    if t == "monetary":
        return _monetary_template(title, impact)
    if t == "fiscal":
        return _fiscal_template(title, impact)
    return _generic_template(title, impact, companies, sectors)


def _n(nid, label, ntype, impact, strength, depth, icon, direction, subtitle=""):
    return {"id": nid, "label": label, "type": ntype, "impact": impact,
            "impact_strength": strength, "depth": depth, "icon": icon,
            "change_direction": direction, "subtitle": subtitle}


def _e(src, tgt, rel, strength, conf, explanation, horizon):
    return {"source": src, "target": tgt, "relationship": rel,
            "impact_strength": strength, "confidence": conf,
            "explanation": explanation, "time_horizon": horizon}


# ── Template: Geopolitical / War ──────────────────────────────────────────────

def _geopolitical_template(title: str, impact: float) -> dict:
    nodes = [
        _n("event_center", title[:45], "event", "mixed", round(impact/10, 1), 0, "⚡", "neutral", f"Impact {impact:.0f}/10"),
        _n("crude_oil",      "Crude Oil Prices",       "commodity", "positive",  0.88, 1, "🛢️", "up",      "+6.2%"),
        _n("gold_prices",    "Gold Prices",            "commodity", "positive",  0.75, 1, "🥇", "up",      "+1.4%"),
        _n("rupee_usd",      "Rupee vs USD",           "currency",  "negative",  0.72, 1, "💱", "down",    "-0.8%"),
        _n("defense_sector", "Defence Companies",      "sector",    "positive",  0.85, 1, "🛡️", "up",      "+4.1%"),
        _n("fii_outflow",    "FII Outflows",           "indicator", "negative",  0.68, 1, "💸", "down",    "-₹3,200Cr"),
        _n("petrol_prices",  "Petrol & Diesel",        "commodity", "negative",  0.80, 2, "⛽", "up",      "+₹5/L"),
        _n("atf",            "Aviation Fuel (ATF)",    "commodity", "negative",  0.82, 2, "✈️", "up",      "+8.1%"),
        _n("logistics",      "Logistics Costs",        "indicator", "negative",  0.72, 2, "🚛", "up",      "+3.2%"),
        _n("inflation",      "Inflation Risk",         "indicator", "negative",  0.76, 2, "📈", "up",      "+0.4%"),
        _n("ongc",           "ONGC",                   "company",   "positive",  0.92, 2, "🏭", "up",      "+4.8%"),
        _n("oil_india",      "Oil India Ltd",          "company",   "positive",  0.88, 2, "🏭", "up",      "+4.1%"),
        _n("indigo",         "IndiGo",                 "company",   "negative",  0.88, 3, "🏢", "down",    "-5.2%"),
        _n("spicejet",       "SpiceJet",               "company",   "negative",  0.85, 3, "🏢", "down",    "-4.8%"),
        _n("consumer_spend", "Consumer Spending",      "indicator", "negative",  0.65, 3, "🛒", "down",    "Pressure"),
        _n("rbi_policy",     "RBI Policy Response",    "policy",    "neutral",   0.60, 3, "🏛️", "neutral", "Watch"),
        _n("paint_sector",   "Paint Industry",         "sector",    "negative",  0.70, 3, "🎨", "down",    "-2.1%"),
        _n("chemical_sector","Chemical Industry",      "sector",    "negative",  0.68, 3, "⚗️", "down",    "-1.8%"),
        _n("export_compete", "Export Competitiveness", "indicator", "positive",  0.55, 3, "🌏", "up",      "Marginal"),
        _n("defense_capex",  "Defence Capex Cycle",    "indicator", "positive",  0.65, 4, "🔬", "up",      "Multi-year"),
        _n("tourism",        "Tourism Sector",         "sector",    "negative",  0.60, 4, "🏝️", "down",    "-8%"),
        _n("govt_fiscal",    "Government Fiscal",      "indicator", "negative",  0.55, 4, "📊", "down",    "Elevated"),
    ]
    edges = [
        _e("event_center", "crude_oil",       "causes",    0.90, 0.92, "Geopolitical tensions disrupt Middle East oil supply routes",              "immediate"),
        _e("event_center", "gold_prices",     "causes",    0.75, 0.85, "Safe haven demand surges during geopolitical uncertainty",                 "immediate"),
        _e("event_center", "rupee_usd",       "causes",    0.70, 0.80, "Risk-off sentiment weakens emerging market currencies",                    "immediate"),
        _e("event_center", "defense_sector",  "benefits",  0.85, 0.88, "Defence budget expectations rise on geopolitical tensions",               "immediate"),
        _e("event_center", "fii_outflow",     "causes",    0.65, 0.75, "Global risk aversion triggers FII selling in emerging markets",            "immediate"),
        _e("crude_oil",    "atf",             "causes",    0.85, 0.90, "Jet fuel is a direct crude derivative — prices move in lockstep",          "immediate"),
        _e("crude_oil",    "petrol_prices",   "causes",    0.82, 0.88, "Retail fuel prices follow crude with a short lag",                        "short_term"),
        _e("crude_oil",    "logistics",       "causes",    0.75, 0.85, "Diesel is the primary fuel for Indian road freight",                      "short_term"),
        _e("crude_oil",    "ongc",            "benefits",  0.92, 0.94, "ONGC's upstream oil revenues rise directly with crude prices",             "immediate"),
        _e("crude_oil",    "oil_india",       "benefits",  0.88, 0.92, "Oil India benefits as a pure upstream crude producer",                    "immediate"),
        _e("crude_oil",    "paint_sector",    "hurts",     0.72, 0.80, "Raw material costs (TiO2, solvents) are crude derivatives",               "short_term"),
        _e("crude_oil",    "chemical_sector", "hurts",     0.70, 0.78, "Petrochemical feedstock costs escalate with crude prices",                "short_term"),
        _e("atf",          "indigo",          "hurts",     0.90, 0.94, "Fuel costs are 35-40% of airline operating expenses",                     "immediate"),
        _e("atf",          "spicejet",        "hurts",     0.85, 0.91, "SpiceJet's thin balance sheet makes fuel cost exposure critical",          "immediate"),
        _e("petrol_prices","inflation",       "causes",    0.78, 0.82, "Fuel price hike feeds directly into CPI via transport and food costs",     "short_term"),
        _e("logistics",    "inflation",       "causes",    0.72, 0.80, "Higher freight costs are passed through to consumer prices",               "short_term"),
        _e("inflation",    "rbi_policy",      "influences",0.65, 0.70, "RBI may pause rate cuts if inflation rises materially above target",       "medium_term"),
        _e("inflation",    "consumer_spend",  "hurts",     0.68, 0.75, "Real purchasing power declines as inflation outpaces wage growth",         "short_term"),
        _e("consumer_spend","tourism",        "hurts",     0.60, 0.70, "Discretionary travel spend gets cut first during inflation stress",        "medium_term"),
        _e("fii_outflow",  "rupee_usd",       "causes",    0.70, 0.75, "FII dollar selling to repatriate funds weakens INR further",              "immediate"),
        _e("defense_sector","defense_capex",  "benefits",  0.75, 0.80, "Geopolitical events accelerate multi-year defence modernisation",          "long_term"),
        _e("rupee_usd",    "export_compete",  "benefits",  0.55, 0.60, "Weaker INR marginally improves price competitiveness of exports",          "medium_term"),
        _e("rupee_usd",    "govt_fiscal",     "hurts",     0.60, 0.65, "Rupee weakness increases INR cost of crude oil imports for the government","medium_term"),
    ]
    insights = {
        "summary": "The geopolitical event is triggering a classic oil-shock ripple across Indian markets. Energy and defence sectors face contrasting fortunes — upstream oil producers and defence companies benefit while aviation, logistics, and consumer-facing sectors face significant margin pressure. The RBI faces a dilemma between supporting growth and containing imported inflation.",
        "key_drivers": [
            "Crude oil supply disruption raising global energy prices",
            "Safe-haven demand boosting gold while weakening INR",
            "FII risk-off sentiment creating selling pressure in equity markets",
        ],
        "ripple_strength": {"direct": "High", "indirect": "Medium", "long_term": "Medium"},
        "market_volatility": "High", "inflation_risk": "Elevated", "growth_impact": "Negative",
        "beneficiaries": [
            {"name": "ONGC",         "ticker": "ONGC",     "confidence": 0.92, "impact": "Very Positive", "reason": "Upstream oil revenues surge with crude prices"},
            {"name": "Oil India",    "ticker": "OIL",      "confidence": 0.89, "impact": "Very Positive", "reason": "Pure upstream exposure benefits from higher crude"},
            {"name": "Mazagon Dock", "ticker": "MAZDOCK",  "confidence": 0.86, "impact": "Positive",      "reason": "Defence shipbuilding demand rises"},
            {"name": "HAL",          "ticker": "HAL",      "confidence": 0.84, "impact": "Positive",      "reason": "Aerospace and defence demand accelerates"},
            {"name": "BEL",          "ticker": "BEL",      "confidence": 0.82, "impact": "Positive",      "reason": "Electronics defence procurement rises"},
        ],
        "losers": [
            {"name": "IndiGo",        "ticker": "INDIGO",    "confidence": 0.93, "impact": "Very Negative", "reason": "Aviation fuel accounts for 35-40% of operating costs"},
            {"name": "SpiceJet",      "ticker": "SPICEJET",  "confidence": 0.91, "impact": "Very Negative", "reason": "Thin margins make airlines most vulnerable to fuel shocks"},
            {"name": "Asian Paints",  "ticker": "ASIANPAINT","confidence": 0.87, "impact": "Negative",      "reason": "Crude-linked raw material costs compress margins"},
            {"name": "Bajaj Auto",    "ticker": "BAJAJ-AUTO","confidence": 0.83, "impact": "Negative",      "reason": "Petrochemical input costs rise, auto demand softens"},
            {"name": "Deepak Nitrite","ticker": "DEEPAKNI",  "confidence": 0.80, "impact": "Negative",      "reason": "Petrochemical feedstock cost escalation"},
        ],
        "impacted_commodities": [
            {"name": "Crude Oil (Brent)", "current_price": "$78.50", "change_pct": 6.21, "positive": True},
            {"name": "Gold",              "current_price": "$2,380", "change_pct": 1.37, "positive": True},
            {"name": "Natural Gas",       "current_price": "$2.75",  "change_pct": 3.11, "positive": True},
        ],
        "impacted_sectors": [
            {"name": "Energy",    "strength": "Very High", "positive": True},
            {"name": "Aviation",  "strength": "Very High", "positive": False},
            {"name": "Defence",   "strength": "High",      "positive": True},
            {"name": "Logistics", "strength": "High",      "positive": False},
            {"name": "Chemicals", "strength": "High",      "positive": False},
        ],
        "ripple_timeline": [
            {"period": "0-7 Days",    "description": "Crude and gold surge, aviation stocks fall sharply, INR weakens vs USD"},
            {"period": "1-4 Weeks",   "description": "Retail fuel price hike announced, airline ticket prices rise, FII outflows accelerate"},
            {"period": "1-3 Months",  "description": "CPI inflation ticks up, RBI pauses rate cuts, consumer confidence dips"},
            {"period": "3-6 Months",  "description": "Defence spending revision upward, sector rotation from consumer to energy"},
        ],
    }
    return {"nodes": nodes, "edges": edges, "insights": insights}


# ── Template: Energy / Oil shock ──────────────────────────────────────────────

def _energy_template(title: str, impact: float) -> dict:
    nodes = [
        _n("event_center",  title[:45],                "event",    "mixed",    round(impact/10,1), 0, "🛢️", "neutral", f"Impact {impact:.0f}/10"),
        _n("brent_crude",   "Brent Crude",             "commodity","positive", 0.92, 1, "🛢️", "up",   "+8.3%"),
        _n("natural_gas",   "Natural Gas",             "commodity","positive", 0.70, 1, "🔥", "up",   "+4.1%"),
        _n("opec_policy",   "OPEC+ Production Cut",   "policy",   "positive", 0.85, 1, "📉", "down", "-1M bbl/d"),
        _n("usd_index",     "US Dollar (DXY)",        "currency", "positive", 0.65, 1, "💵", "up",   "+0.6%"),
        _n("inr_usd",       "INR vs USD",             "currency", "negative", 0.72, 1, "💱", "down", "-0.9%"),
        _n("atf",           "Aviation Turbine Fuel",  "commodity","negative", 0.88, 2, "⛽", "up",   "+9.2%"),
        _n("ongc",          "ONGC",                   "company",  "positive", 0.92, 2, "🏭", "up",   "+5.6%"),
        _n("oil_india",     "Oil India Ltd",          "company",  "positive", 0.88, 2, "🏭", "up",   "+4.8%"),
        _n("hpcl",          "HPCL / BPCL",            "company",  "negative", 0.78, 2, "🏭", "down", "-2.3%"),
        _n("petrol_retail", "Petrol Retail Prices",   "indicator","negative", 0.82, 2, "🚗", "up",   "+₹6/L"),
        _n("transport_cost","Transport Costs",        "indicator","negative", 0.76, 2, "🚛", "up",   "+4.2%"),
        _n("aviation",      "Aviation Sector",        "sector",   "negative", 0.85, 3, "✈️", "down", "-4.8%"),
        _n("logistics_sec", "Logistics & Freight",   "sector",   "negative", 0.73, 3, "📦", "down", "-2.7%"),
        _n("inflation_cpi", "CPI Inflation",          "indicator","negative", 0.74, 3, "📊", "up",   "+0.5%"),
        _n("agri_costs",    "Agricultural Input Costs","indicator","negative",0.65, 3, "🌾", "up",   "+2.1%"),
        _n("consumer_stap", "Consumer Staples Margins","sector",  "negative", 0.62, 3, "🛒", "down", "Pressure"),
        _n("rbi_hold",      "RBI Rate Decision",      "policy",   "neutral",  0.58, 4, "🏛️", "neutral","On hold"),
        _n("solar_energy",  "Renewable Energy Push",  "sector",   "positive", 0.55, 4, "☀️", "up",   "Long-term"),
        _n("ev_adoption",   "EV Adoption Tailwind",   "indicator","positive", 0.50, 4, "⚡", "up",   "Accelerating"),
    ]
    edges = [
        _e("event_center",  "brent_crude",   "causes",   0.92, 0.95, "Supply disruption or OPEC+ policy drives crude prices higher",              "immediate"),
        _e("event_center",  "opec_policy",   "causes",   0.85, 0.90, "Production decision directly impacts global crude supply-demand balance",    "immediate"),
        _e("event_center",  "usd_index",     "influences",0.60,0.65, "Oil priced in USD — supply shocks often strengthen the dollar",              "immediate"),
        _e("brent_crude",   "ongc",          "benefits", 0.92, 0.94, "ONGC realisations per barrel rise directly with crude prices",              "immediate"),
        _e("brent_crude",   "oil_india",     "benefits", 0.88, 0.92, "Oil India benefits as upstream crude oil producer",                         "immediate"),
        _e("brent_crude",   "atf",           "causes",   0.88, 0.92, "Aviation fuel is a direct refinery product of crude oil",                  "immediate"),
        _e("brent_crude",   "petrol_retail", "causes",   0.80, 0.85, "OMCs pass through crude cost to retail fuel prices",                       "short_term"),
        _e("brent_crude",   "hpcl",          "hurts",    0.75, 0.80, "Refiners face under-recovery risk if they cannot fully pass through costs", "short_term"),
        _e("atf",           "aviation",      "hurts",    0.88, 0.92, "Fuel is 35-40% of airline costs — price surge destroys margins",           "immediate"),
        _e("petrol_retail", "transport_cost","causes",   0.78, 0.85, "Higher diesel prices directly escalate last-mile logistics costs",          "short_term"),
        _e("transport_cost","logistics_sec", "hurts",    0.73, 0.80, "Freight companies absorb or pass through higher fuel costs",               "short_term"),
        _e("transport_cost","agri_costs",    "causes",   0.65, 0.70, "Agricultural supply chain costs rise with fuel prices",                    "short_term"),
        _e("petrol_retail", "inflation_cpi", "causes",   0.74, 0.80, "Fuel is a direct CPI component and multiplier through transport",          "short_term"),
        _e("agri_costs",    "inflation_cpi", "causes",   0.65, 0.70, "Food price inflation rises when agricultural input costs increase",         "medium_term"),
        _e("inflation_cpi", "rbi_hold",      "influences",0.60,0.65, "Higher inflation reduces RBI's scope for rate cuts",                       "medium_term"),
        _e("inflation_cpi", "consumer_stap", "hurts",    0.60, 0.68, "Input cost inflation pressures FMCG and consumer staples margins",         "medium_term"),
        _e("usd_index",     "inr_usd",       "hurts",    0.70, 0.75, "Stronger USD weakens INR, increasing cost of crude imports further",       "immediate"),
        _e("inr_usd",       "inflation_cpi", "causes",   0.65, 0.70, "Rupee depreciation makes imports costlier, adding to inflation",           "short_term"),
        _e("brent_crude",   "solar_energy",  "benefits", 0.55, 0.60, "High fossil fuel prices make renewable energy comparatively attractive",   "long_term"),
        _e("solar_energy",  "ev_adoption",   "benefits", 0.50, 0.55, "Energy transition accelerates as petrol becomes expensive vs electricity", "long_term"),
    ]
    insights = {
        "summary": "The energy shock is creating a bifurcated market — upstream oil producers like ONGC and Oil India gain while downstream consumers (aviation, logistics, OMCs) face severe margin pressure. The CPI spillover risk is the key macro concern, limiting RBI's room for easing.",
        "key_drivers": [
            "Crude oil supply reduction driving global prices higher",
            "INR weakening amplifying cost of oil imports for India",
            "Downstream margin compression across transport-intensive sectors",
        ],
        "ripple_strength": {"direct": "Very High", "indirect": "High", "long_term": "Medium"},
        "market_volatility": "High", "inflation_risk": "Very High", "growth_impact": "Negative",
        "beneficiaries": [
            {"name": "ONGC",       "ticker": "ONGC",       "confidence": 0.94, "impact": "Very Positive", "reason": "Upstream crude realisation rises with Brent"},
            {"name": "Oil India",  "ticker": "OIL",        "confidence": 0.90, "impact": "Very Positive", "reason": "Pure upstream exposure benefits from higher crude"},
            {"name": "Vedanta",    "ticker": "VEDL",       "confidence": 0.82, "impact": "Positive",      "reason": "Oil & gas production revenues surge"},
            {"name": "MRPL",       "ticker": "MRPL",       "confidence": 0.75, "impact": "Positive",      "reason": "Refining margins benefit from inventory gains"},
            {"name": "Adani Green","ticker": "ADANIGREEN", "confidence": 0.65, "impact": "Positive",      "reason": "Renewable energy cheaper vs rising fossil costs"},
        ],
        "losers": [
            {"name": "IndiGo",      "ticker": "INDIGO",    "confidence": 0.93, "impact": "Very Negative", "reason": "Fuel cost shock directly hits airline margins"},
            {"name": "SpiceJet",    "ticker": "SPICEJET",  "confidence": 0.91, "impact": "Very Negative", "reason": "Highly leveraged to fuel costs with weakest balance sheet"},
            {"name": "Asian Paints","ticker": "ASIANPAINT","confidence": 0.86, "impact": "Negative",      "reason": "Input cost inflation in crude-linked raw materials"},
            {"name": "Grasim",      "ticker": "GRASIM",    "confidence": 0.82, "impact": "Negative",      "reason": "Chemical and cement raw material costs escalate"},
            {"name": "Zomato",      "ticker": "ZOMATO",    "confidence": 0.78, "impact": "Negative",      "reason": "Delivery fleet fuel costs rise, discretionary spending falls"},
        ],
        "impacted_commodities": [
            {"name": "Brent Crude",  "current_price": "$85.20", "change_pct": 8.30, "positive": True},
            {"name": "Natural Gas",  "current_price": "$3.15",  "change_pct": 4.10, "positive": True},
            {"name": "Gold",         "current_price": "$2,410", "change_pct": 0.80, "positive": True},
        ],
        "impacted_sectors": [
            {"name": "Energy (Upstream)", "strength": "Very High", "positive": True},
            {"name": "Aviation",          "strength": "Very High", "positive": False},
            {"name": "Refining & OMCs",   "strength": "High",      "positive": False},
            {"name": "Logistics",         "strength": "High",      "positive": False},
            {"name": "Chemicals",         "strength": "Medium",    "positive": False},
        ],
        "ripple_timeline": [
            {"period": "0-7 Days",   "description": "Crude and gas prices spike, ONGC/OIL surge, aviation and logistics stocks fall"},
            {"period": "1-4 Weeks",  "description": "OMCs hike retail fuel prices, inflation expectations rise, FII flows turn cautious"},
            {"period": "1-3 Months", "description": "CPI inflation rises, RBI holds rates, earnings miss in fuel-intensive sectors"},
            {"period": "3-6 Months", "description": "Sector rotation to upstream energy; renewable energy narrative strengthens"},
        ],
    }
    return {"nodes": nodes, "edges": edges, "insights": insights}


# ── Template: Monetary / RBI ──────────────────────────────────────────────────

def _monetary_template(title: str, impact: float) -> dict:
    pos = impact >= 5
    dir_ = "up" if pos else "down"
    sign = "+" if pos else "-"
    nodes = [
        _n("event_center",  title[:45],               "event",    "mixed",                 round(impact/10,1), 0, "🏛️", "neutral", f"Impact {impact:.0f}/10"),
        _n("repo_rate",     f"Repo Rate {'Cut' if pos else 'Hike'}", "policy", "positive" if pos else "negative", 0.95, 1, "📉" if pos else "📈", dir_, f"{sign}25 bps"),
        _n("bond_yields",   "10Y Bond Yields",        "indicator","negative" if pos else "positive", 0.88, 1, "📊", "down" if pos else "up",  f"{'−' if pos else '+'}15 bps"),
        _n("banking_nim",   "Banking Sector NIM",     "sector",   "negative" if pos else "positive", 0.82, 1, "🏦", dir_,   f"{sign}1.8%"),
        _n("rupee",         "INR vs USD",             "currency", "positive" if pos else "negative", 0.68, 1, "💱", dir_,   f"{sign}0.4%"),
        _n("real_estate",   "Real Estate Sector",     "sector",   "positive" if pos else "negative", 0.78, 2, "🏘️", dir_,   "Demand ↑" if pos else "Demand ↓"),
        _n("auto_sector",   "Auto Sector",            "sector",   "positive" if pos else "negative", 0.75, 2, "🚗", dir_,   "Loans cheaper" if pos else "Loans costlier"),
        _n("nbfc",          "NBFCs & HFCs",           "sector",   "positive" if pos else "negative", 0.80, 2, "💼", dir_,   "Spreads ↑" if pos else "Spreads ↓"),
        _n("hdfc_bank",     "HDFC Bank",              "company",  "negative" if pos else "positive", 0.78, 2, "🏢", "down" if pos else "up",  f"{'−' if pos else '+'}1.8%"),
        _n("sbi",           "SBI",                    "company",  "negative" if pos else "positive", 0.80, 2, "🏢", "down" if pos else "up",  f"{'−' if pos else '+'}2.1%"),
        _n("bajaj_finance", "Bajaj Finance",          "company",  "positive" if pos else "negative", 0.75, 2, "🏢", dir_,   "AUM ↑" if pos else "NIM ↓"),
        _n("inflation_out", "Inflation Outlook",      "indicator","positive" if pos else "negative", 0.72, 3, "📈", "down" if pos else "up",  "Contained" if pos else "Rising"),
        _n("credit_growth", "Credit Growth",          "indicator","positive" if pos else "negative", 0.70, 3, "💰", dir_,   f"{'12%' if pos else '8%'} YoY"),
        _n("consumer_dem",  "Consumer Demand",        "indicator","positive" if pos else "negative", 0.68, 3, "🛒", dir_,   "Pickup" if pos else "Softening"),
        _n("equity_val",    "Equity Valuations",      "indicator","positive" if pos else "negative", 0.65, 3, "📊", dir_,   "Re-rating" if pos else "De-rating"),
        _n("gdp_growth",    "GDP Growth Impact",      "indicator","positive" if pos else "negative", 0.60, 4, "📊", dir_,   f"{sign}0.3% FY"),
        _n("fii_flows",     "FII Flows",              "indicator","positive" if pos else "negative", 0.62, 4, "💸", dir_,   "Inflows" if pos else "Outflows"),
    ]
    edges = [
        _e("event_center", "repo_rate",     "causes",    0.95, 0.98, "RBI monetary policy committee announces rate decision",                    "immediate"),
        _e("repo_rate",    "bond_yields",   "causes",    0.88, 0.92, "Policy rate change directly anchors short-term bond yields",               "immediate"),
        _e("repo_rate",    "banking_nim",   "influences",0.82, 0.88, "Bank lending and deposit rates reset with policy rate",                    "short_term"),
        _e("repo_rate",    "rupee",         "influences",0.65, 0.70, "Rate differential vs US Fed impacts capital flows and INR",                "immediate"),
        _e("repo_rate",    "real_estate",   "influences",0.78, 0.82, "Home loan EMIs change directly with repo rate",                           "short_term"),
        _e("repo_rate",    "auto_sector",   "influences",0.72, 0.78, "Vehicle loan rates adjust with monetary policy",                          "short_term"),
        _e("banking_nim",  "hdfc_bank",     "influences",0.78, 0.84, "HDFC Bank's NIM and loan growth respond to rate environment",             "short_term"),
        _e("banking_nim",  "sbi",           "influences",0.80, 0.85, "SBI, as largest lender, is most sensitive to rate changes",               "short_term"),
        _e("banking_nim",  "nbfc",          "influences",0.78, 0.82, "NBFC funding costs change with bank lending rates",                       "short_term"),
        _e("nbfc",         "bajaj_finance", "influences",0.75, 0.80, "Bajaj Finance's borrowing costs and spread are directly impacted",        "short_term"),
        _e("real_estate",  "consumer_dem",  "influences",0.65, 0.70, "Cheaper home loans stimulate purchases and wealth effect",                "medium_term"),
        _e("auto_sector",  "consumer_dem",  "influences",0.68, 0.75, "Vehicle affordability improves with lower EMIs",                          "medium_term"),
        _e("credit_growth","consumer_dem",  "supports",  0.70, 0.75, "Higher credit availability supports consumer spending",                   "medium_term"),
        _e("consumer_dem", "gdp_growth",    "influences",0.60, 0.65, "Private consumption is 55% of India's GDP",                              "long_term"),
        _e("bond_yields",  "equity_val",    "influences",0.65, 0.70, "Lower bond yields make equities comparatively more attractive",           "short_term"),
        _e("equity_val",   "fii_flows",     "influences",0.62, 0.68, "Equity re-rating improves India's attractiveness vs global peers",        "medium_term"),
        _e("inflation_out","repo_rate",     "influences",0.55, 0.60, "Inflation trajectory determines future rate path",                        "long_term"),
        _e("banking_nim",  "credit_growth", "influences",0.70, 0.75, "Bank lending capacity changes with rate environment",                     "medium_term"),
    ]
    insights = {
        "summary": f"The RBI {'rate cut' if pos else 'rate hike'} triggers a multi-layered transmission through the Indian economy. Banking sector dynamics shift immediately, while real economy effects on consumption, housing, and auto sales materialize over 2-4 quarters.",
        "key_drivers": [
            f"Policy rate change of 25 bps ({'cut' if pos else 'hike'})",
            "Bond yield transmission to corporate borrowing costs",
            "Consumer credit and home loan demand response",
        ],
        "ripple_strength": {"direct": "Very High", "indirect": "High", "long_term": "High"},
        "market_volatility": "Medium", "inflation_risk": "Low" if pos else "Elevated", "growth_impact": "Positive" if pos else "Negative",
        "beneficiaries": [
            {"name": "Bajaj Finance", "ticker": "BAJFINANCE", "confidence": 0.85, "impact": "Positive", "reason": "Lower borrowing costs expand NIM and AUM growth"},
            {"name": "HDFC AMC",      "ticker": "HDFCAMC",    "confidence": 0.80, "impact": "Positive", "reason": "Lower rates drive equity SIP inflows"},
        ] if pos else [
            {"name": "HDFC Bank",     "ticker": "HDFCBANK",   "confidence": 0.82, "impact": "Positive", "reason": "Higher rates boost NIM in short term"},
            {"name": "Kotak Bank",    "ticker": "KOTAKBANK",  "confidence": 0.79, "impact": "Positive", "reason": "Well-positioned CASA ratio benefits from rate hike"},
        ],
        "losers": [
            {"name": "DLF",           "ticker": "DLF",         "confidence": 0.82, "impact": "Negative", "reason": "Real estate affordability worsens as home loan EMIs rise"},
            {"name": "Prestige Estates","ticker": "PRESTIGE",  "confidence": 0.78, "impact": "Negative", "reason": "Higher mortgage rates reduce buyer affordability"},
        ] if not pos else [
            {"name": "HDFC Bank",     "ticker": "HDFCBANK",    "confidence": 0.80, "impact": "Slightly Negative", "reason": "NIM compression as lending rates fall faster"},
            {"name": "Axis Bank",     "ticker": "AXISBANK",    "confidence": 0.76, "impact": "Slightly Negative", "reason": "Short-term NIM headwind from rate cut"},
        ],
        "impacted_commodities": [
            {"name": "Gold",     "current_price": "$2,350", "change_pct": -0.80 if pos else 1.20, "positive": not pos},
            {"name": "USD/INR",  "current_price": "₹83.80", "change_pct": -0.40 if pos else 0.60, "positive": pos},
        ],
        "impacted_sectors": [
            {"name": "Banking",              "strength": "Very High", "positive": not pos},
            {"name": "Real Estate",          "strength": "High",      "positive": pos},
            {"name": "Auto",                 "strength": "High",      "positive": pos},
            {"name": "NBFCs",                "strength": "High",      "positive": pos},
            {"name": "Consumer Discretionary","strength": "Medium",   "positive": pos},
        ],
        "ripple_timeline": [
            {"period": "0-7 Days",    "description": f"Bond yields move immediately; Nifty Bank reacts to NIM outlook change"},
            {"period": "1-4 Weeks",   "description": "Banks announce MCLR/loan rate changes; credit demand adjusts"},
            {"period": "1-3 Months",  "description": "Real estate sales and auto bookings show measurable response"},
            {"period": "3-6 Months",  "description": "GDP growth forecast revisions; FII positioning adjusts to India vs EM peers"},
        ],
    }
    return {"nodes": nodes, "edges": edges, "insights": insights}


# ── Template: Fiscal / Budget ─────────────────────────────────────────────────

def _fiscal_template(title: str, impact: float) -> dict:
    nodes = [
        _n("event_center",  title[:45],               "event",    "mixed",    round(impact/10,1), 0, "📜", "neutral", f"Impact {impact:.0f}/10"),
        _n("capex_boost",   "Govt Capex ↑",           "policy",   "positive", 0.88, 1, "🏗️", "up",   "+₹50,000Cr"),
        _n("tax_revenue",   "Tax Revenue Target",     "indicator","positive", 0.72, 1, "💰", "up",   "+8% YoY"),
        _n("fiscal_def",    "Fiscal Deficit Target",  "indicator","mixed",    0.75, 1, "📊", "neutral","4.9% GDP"),
        _n("psu_capex",     "PSU Investment Push",    "indicator","positive", 0.82, 1, "🏭", "up",   "+15%"),
        _n("infra_sector",  "Infrastructure",         "sector",   "positive", 0.88, 2, "🏛️", "up",   "+4.2%"),
        _n("defence_psu",   "Defence PSUs",           "sector",   "positive", 0.82, 2, "🛡️", "up",   "+3.8%"),
        _n("railways",      "Railways Sector",        "sector",   "positive", 0.85, 2, "🚂", "up",   "+5.1%"),
        _n("cement",        "Cement Sector",          "sector",   "positive", 0.78, 2, "🏗️", "up",   "+2.9%"),
        _n("steel",         "Steel Sector",           "sector",   "positive", 0.75, 2, "⚙️", "up",   "+2.4%"),
        _n("bond_yields",   "G-Sec Bond Yields",      "indicator","negative", 0.70, 2, "📋", "up",   "+8 bps"),
        _n("bel",           "BEL",                    "company",  "positive", 0.88, 3, "🏢", "up",   "+4.6%"),
        _n("rvnl",          "RVNL",                   "company",  "positive", 0.85, 3, "🏢", "up",   "+5.2%"),
        _n("lt",            "L&T",                    "company",  "positive", 0.82, 3, "🏢", "up",   "+3.1%"),
        _n("employment",    "Employment Generation",  "indicator","positive", 0.65, 3, "👷", "up",   "+2M jobs"),
        _n("rural_demand",  "Rural Economy",          "indicator","positive", 0.62, 4, "🌾", "up",   "MNREGA boost"),
        _n("gdp_impact",    "GDP Growth",             "indicator","positive", 0.60, 4, "📊", "up",   "+0.4% FY"),
    ]
    edges = [
        _e("event_center","capex_boost",   "causes",  0.88, 0.92, "Budget allocates higher capital expenditure for infrastructure and defence", "immediate"),
        _e("event_center","fiscal_def",    "causes",  0.75, 0.80, "Budget sets fiscal deficit target, impacting bond market expectations",      "immediate"),
        _e("event_center","psu_capex",     "causes",  0.82, 0.88, "Government directs PSUs to accelerate capital investment",                  "immediate"),
        _e("event_center","tax_revenue",   "causes",  0.72, 0.78, "Revised tax slabs and collection targets affect revenue outlook",            "short_term"),
        _e("capex_boost", "infra_sector",  "benefits",0.88, 0.92, "Roads, ports, airports, and urban infra get direct funding boost",          "immediate"),
        _e("capex_boost", "railways",      "benefits",0.85, 0.90, "Railway capex allocation benefits construction and rolling stock companies", "immediate"),
        _e("psu_capex",   "defence_psu",   "benefits",0.82, 0.88, "Defence PSUs get large order books from budget allocation",                 "short_term"),
        _e("infra_sector","cement",        "benefits",0.78, 0.84, "Infrastructure construction drives cement demand and volume growth",         "short_term"),
        _e("infra_sector","steel",         "benefits",0.75, 0.82, "Steel is the primary input for infrastructure projects",                    "short_term"),
        _e("railways",    "rvnl",          "benefits",0.85, 0.90, "RVNL directly executes railway electrification and infra projects",         "short_term"),
        _e("infra_sector","lt",            "benefits",0.82, 0.88, "L&T is the dominant EPC contractor for large infra projects",               "short_term"),
        _e("defence_psu", "bel",           "benefits",0.88, 0.92, "BEL is the largest defence electronics PSU beneficiary",                   "short_term"),
        _e("fiscal_def",  "bond_yields",   "causes",  0.70, 0.75, "Higher government borrowing puts upward pressure on G-Sec yields",         "immediate"),
        _e("capex_boost", "employment",    "benefits",0.65, 0.70, "Large-scale construction projects create significant employment",           "medium_term"),
        _e("employment",  "rural_demand",  "benefits",0.62, 0.68, "Higher employment incomes boost rural consumption and demand",              "medium_term"),
        _e("rural_demand","gdp_impact",    "influences",0.60,0.65,"Rural consumption is a critical driver of India's consumption-led growth", "long_term"),
    ]
    insights = {
        "summary": "The budget announcement creates a clear beneficiary map concentrated in PSU infrastructure and defence companies. While bond yields face modest upward pressure from higher government borrowing, the growth multiplier from capex spending is expected to dominate the medium-term narrative.",
        "key_drivers": [
            "Government capex allocation boosting infrastructure order books",
            "PSU defence spending creating multi-year revenue visibility",
            "Rural economy support measures sustaining consumption",
        ],
        "ripple_strength": {"direct": "High", "indirect": "High", "long_term": "Very High"},
        "market_volatility": "Low", "inflation_risk": "Low", "growth_impact": "Positive",
        "beneficiaries": [
            {"name": "BEL",              "ticker": "BEL",        "confidence": 0.90, "impact": "Very Positive", "reason": "Defence electronics order book expands significantly"},
            {"name": "RVNL",             "ticker": "RVNL",       "confidence": 0.88, "impact": "Very Positive", "reason": "Railway electrification projects are key budget priority"},
            {"name": "L&T",              "ticker": "LT",         "confidence": 0.85, "impact": "Positive",      "reason": "Dominant EPC contractor benefits from infrastructure push"},
            {"name": "Ultratech Cement", "ticker": "ULTRACEMCO", "confidence": 0.80, "impact": "Positive",      "reason": "Cement demand rises with construction activity"},
            {"name": "NTPC",             "ticker": "NTPC",       "confidence": 0.78, "impact": "Positive",      "reason": "Power sector capex allocation supports expansion"},
        ],
        "losers": [
            {"name": "Private Banks", "ticker": "HDFCBANK", "confidence": 0.70, "impact": "Slightly Negative", "reason": "Higher G-Sec yields compete with bank deposit rates"},
        ],
        "impacted_commodities": [
            {"name": "Steel",  "current_price": "₹52,400/MT", "change_pct": 2.80, "positive": True},
            {"name": "Cement", "current_price": "₹380/50kg",  "change_pct": 1.90, "positive": True},
        ],
        "impacted_sectors": [
            {"name": "Infrastructure", "strength": "Very High", "positive": True},
            {"name": "Defence PSUs",   "strength": "Very High", "positive": True},
            {"name": "Cement & Steel", "strength": "High",      "positive": True},
            {"name": "Railways",       "strength": "High",      "positive": True},
            {"name": "Private Banking","strength": "Low",       "positive": False},
        ],
        "ripple_timeline": [
            {"period": "0-7 Days",   "description": "Infra and defence stocks surge on budget day; bond yields tick up"},
            {"period": "1-4 Weeks",  "description": "Companies share order pipeline updates; cement volume guidance revised up"},
            {"period": "1-3 Months", "description": "Tender flows accelerate; Q1 construction season begins with higher activity"},
            {"period": "3-6 Months", "description": "Employment and rural income multiplier effects show up in IIP data"},
        ],
    }
    return {"nodes": nodes, "edges": edges, "insights": insights}


# ── Template: Generic market shock ────────────────────────────────────────────

def _generic_template(title: str, impact: float, companies: list, sectors: list) -> dict:
    pos = impact >= 5
    dir_ = "up" if pos else "down"
    sign = "+" if pos else "-"
    sentiment = "positive" if pos else "negative"
    nodes = [
        _n("event_center",  title[:45],               "event",    "mixed",    round(impact/10,1), 0, "⚡", "neutral", f"Impact {impact:.0f}/10"),
        _n("market_sent",   "Market Sentiment",       "indicator",sentiment,  0.80, 1, "📊", dir_,  f"{sign}0.8%"),
        _n("nifty50",       "Nifty 50",               "indicator",sentiment,  0.78, 1, "📈" if pos else "📉", dir_, f"{sign}0.6%"),
        _n("fii_activity",  "FII Activity",           "indicator",sentiment,  0.72, 1, "💸", dir_,  f"{sign}₹1,200Cr"),
        _n("vix",           "India VIX",              "indicator","negative" if pos else "positive", 0.70, 1, "⚡", "down" if pos else "up", "-1.2pt" if pos else "+2.4pt"),
        _n("banking",       "Banking Sector",         "sector",   sentiment,  0.68, 2, "🏦", dir_,  f"{sign}0.9%"),
        _n("it_sector",     "IT Sector",              "sector",   sentiment,  0.65, 2, "💻", dir_,  f"{sign}0.5%"),
        _n("auto_sector",   "Auto Sector",            "sector",   sentiment,  0.62, 2, "🚗", dir_,  f"{sign}0.7%"),
        _n("bond_market",   "Bond Market",            "indicator","positive" if pos else "negative", 0.60, 2, "📋", "down" if pos else "up", "Yields ↓" if pos else "Yields ↑"),
        _n("rupee",         "INR vs USD",             "currency", sentiment,  0.55, 2, "💱", dir_,  f"{sign}0.3%"),
        _n("consumer_conf", "Consumer Confidence",   "indicator",sentiment,  0.58, 3, "🛒", dir_,  "Improving" if pos else "Declining"),
        _n("capex_cycle",   "Capex Cycle",            "indicator",sentiment,  0.55, 3, "🏗️", dir_,  "Accelerating" if pos else "Slowing"),
        _n("earnings_revs", "FY26 Earnings",          "indicator",sentiment,  0.60, 3, "📊", dir_,  f"{sign}3% revisions"),
        _n("psu_stocks",    "PSU Stocks",             "sector",   sentiment,  0.62, 4, "🏛️", dir_,  "Outperform" if pos else "Underperform"),
        _n("midcap",        "Mid & Small Caps",       "sector",   sentiment,  0.55, 4, "📊", dir_,  f"{sign}1.2%"),
    ]
    edges = [
        _e("event_center","market_sent",  "causes",    0.85, 0.88, "Event creates immediate market sentiment shift across asset classes",       "immediate"),
        _e("event_center","fii_activity", "influences",0.72, 0.78, "Foreign institutional investors react to Indian market catalysts",          "immediate"),
        _e("market_sent", "nifty50",      "influences",0.80, 0.85, "Broader market sentiment directly drives index movement",                  "immediate"),
        _e("market_sent", "vix",          "influences",0.70, 0.75, "Improved sentiment reduces volatility expectations (VIX)",                 "immediate"),
        _e("nifty50",     "banking",      "influences",0.68, 0.72, "Banking is largest weight in Nifty50 and leads market moves",              "immediate"),
        _e("nifty50",     "it_sector",    "influences",0.65, 0.70, "IT sector responds to global risk sentiment and INR moves",                "short_term"),
        _e("fii_activity","rupee",        "influences",0.55, 0.62, "FII capital flows impact INR vs USD through forex demand/supply",          "immediate"),
        _e("fii_activity","bond_market",  "influences",0.62, 0.68, "FII participation in G-Sec market affects bond yields",                   "short_term"),
        _e("banking",     "consumer_conf","influences",0.58, 0.65, "Banking sector health affects credit availability and confidence",          "medium_term"),
        _e("consumer_conf","auto_sector", "influences",0.62, 0.68, "Consumer confidence directly drives vehicle purchase decisions",            "medium_term"),
        _e("market_sent", "capex_cycle",  "influences",0.55, 0.60, "Corporate confidence and capex intentions follow market sentiment",        "medium_term"),
        _e("earnings_revs","market_sent", "influences",0.60, 0.65, "Earnings revisions compound or offset the initial sentiment move",         "short_term"),
        _e("capex_cycle", "psu_stocks",   "influences",0.62, 0.68, "PSU stocks benefit from government capex and infra spending",             "long_term"),
        _e("market_sent", "midcap",       "influences",0.55, 0.60, "Mid and small caps amplify market direction by 1.5-2x",                   "short_term"),
        _e("consumer_conf","earnings_revs","influences",0.58,0.65, "Consumer demand outlook drives revenue growth forecast revisions",          "medium_term"),
    ]
    insights = {
        "summary": f"This event is creating a {sentiment} ripple across Indian equity markets. The primary transmission channels are institutional flows, market sentiment, and sector rotation patterns. The impact is expected to be most pronounced in the near term with gradual normalization over 2-4 weeks.",
        "key_drivers": [
            f"Event-driven {'buying' if pos else 'selling'} pressure across large caps",
            f"FII {'inflows' if pos else 'outflows'} amplifying domestic institutional behavior",
            f"Sector rotation {'towards' if pos else 'away from'} high-beta segments",
        ],
        "ripple_strength": {"direct": "Medium", "indirect": "Low", "long_term": "Low"},
        "market_volatility": "Medium" if impact < 7 else "High",
        "inflation_risk": "Low",
        "growth_impact": "Positive" if pos else "Negative",
        "beneficiaries": [
            {"name": "Nifty 50 ETF",  "ticker": "NIFTYBEES", "confidence": 0.75, "impact": "Positive" if pos else "Negative", "reason": "Broad market move benefits index funds"},
        ],
        "losers": [
            {"name": "India VIX", "ticker": "VIX", "confidence": 0.70, "impact": "High" if not pos else "Low", "reason": "Volatility rises as uncertainty increases"},
        ],
        "impacted_commodities": [
            {"name": "Gold", "current_price": "$2,340", "change_pct": 0.80 if not pos else -0.40, "positive": not pos},
        ],
        "impacted_sectors": [
            {"name": "Banking", "strength": "Medium", "positive": pos},
            {"name": "IT",      "strength": "Low",    "positive": pos},
            {"name": "Auto",    "strength": "Low",    "positive": pos},
        ],
        "ripple_timeline": [
            {"period": "0-7 Days",   "description": f"Initial market reaction, FII {'buying' if pos else 'selling'}, sector rotation"},
            {"period": "1-4 Weeks",  "description": "Earnings revision cycle begins, corporate commentary adjusts"},
            {"period": "1-3 Months", "description": "Economic data validates or contradicts the initial market move"},
            {"period": "3-6 Months", "description": "Structural sector allocation shifts based on event's lasting impact"},
        ],
    }
    return {"nodes": nodes, "edges": edges, "insights": insights}
