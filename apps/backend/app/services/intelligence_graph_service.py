"""
Market Intelligence Graph (MIG) Service.

Global directed graph of market entities and causal relationships.
Powers: Ripple Analysis, AI context injection, cross-entity discovery.

Node types:  company | sector | theme | event | policy | commodity | country | index | currency
Edge types:  benefits | hurts | supplies | depends_on | competes_with | influences | triggered_by

Cached in Redis under `mig:full:v1` with 5-minute TTL.
Any write (upsert_node / upsert_edge) invalidates the cache immediately.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any

import structlog

log = structlog.get_logger(__name__)

_CACHE_KEY = "mig:full:v1"
_CACHE_TTL = 300

NODE_TYPES = {"company", "sector", "theme", "event", "policy", "commodity", "country", "index", "currency"}
EDGE_TYPES = {"benefits", "hurts", "supplies", "depends_on", "competes_with", "influences", "triggered_by"}

# How an edge type propagates the direction signal through the graph
# "same"    → rise/fall follows through (oil rises → airline costs rise → airlines hurt)
# "inverse" → direction flips  (oil rises → airline profits fall)
# "neutral" → direction uncertain / contextual
EDGE_POLARITY: dict[str, str] = {
    "benefits":      "same",
    "hurts":         "inverse",
    "supplies":      "same",
    "depends_on":    "same",
    "competes_with": "inverse",
    "influences":    "neutral",
    "triggered_by":  "neutral",
}


# ── ID helpers ────────────────────────────────────────────────────────────────

def make_node_id(node_type: str, label: str) -> str:
    slug = re.sub(r"[^\w]+", "-", label.lower()).strip("-")
    return f"{node_type}:{slug}"


def make_edge_id(source_id: str, edge_type: str, target_id: str) -> str:
    raw = f"{source_id}|{edge_type}|{target_id}"
    return hashlib.md5(raw.encode()).hexdigest()[:32]


# ── Cache helpers ─────────────────────────────────────────────────────────────

async def _invalidate_cache() -> None:
    try:
        from app.core.redis import get_redis
        r = await get_redis()
        if r:
            await r.delete(_CACHE_KEY)
    except Exception:
        pass


# ── Graph read ────────────────────────────────────────────────────────────────

async def get_full_graph() -> dict:
    """Return all nodes + edges. Redis-first, 5 min TTL."""
    try:
        from app.core.redis import get_redis
        r = await get_redis()
        if r:
            cached = await r.get(_CACHE_KEY)
            if cached:
                return json.loads(cached)
    except Exception:
        pass

    graph = await _load_from_db()

    try:
        from app.core.redis import get_redis
        r = await get_redis()
        if r:
            await r.setex(_CACHE_KEY, _CACHE_TTL, json.dumps(graph))
    except Exception:
        pass

    return graph


async def _load_from_db() -> dict:
    from app.db.session import AsyncSessionLocal
    from app.db.models.intelligence_graph import IGNode, IGEdge
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        node_rows = (await db.execute(select(IGNode))).scalars().all()
        edge_rows = (await db.execute(select(IGEdge))).scalars().all()

    return {
        "nodes": [
            {
                "id": n.id, "node_type": n.node_type, "label": n.label,
                "ticker": n.ticker, "description": n.description,
                "extra": n.extra or {}, "auto_added": n.auto_added,
            }
            for n in node_rows
        ],
        "edges": [
            {
                "id": e.id, "source": e.source_id, "target": e.target_id,
                "edge_type": e.edge_type, "weight": e.weight,
                "confidence": e.confidence, "lag_days": e.lag_days,
                "description": e.description, "source_event": e.source_event,
                "auto_added": e.auto_added,
            }
            for e in edge_rows
        ],
    }


async def get_subgraph(node_id: str, hops: int = 2) -> dict:
    """Return N-hop neighbourhood of a node (undirected BFS)."""
    graph = await get_full_graph()

    # Build undirected adjacency (edges travel both ways for discovery)
    adj: dict[str, list[dict]] = {}
    for e in graph["edges"]:
        adj.setdefault(e["source"], []).append(e)
        adj.setdefault(e["target"], []).append({**e, "source": e["target"], "target": e["source"]})

    visited_nodes: set[str] = {node_id}
    visited_edges: set[str] = set()
    frontier: set[str] = {node_id}

    for _ in range(hops):
        next_frontier: set[str] = set()
        for nid in frontier:
            for e in adj.get(nid, []):
                visited_nodes.add(e["source"])
                visited_nodes.add(e["target"])
                visited_edges.add(e["id"])
                if e["target"] not in visited_nodes:
                    next_frontier.add(e["target"])
        frontier = next_frontier

    nodes_map = {n["id"]: n for n in graph["nodes"]}
    return {
        "nodes": [nodes_map[nid] for nid in visited_nodes if nid in nodes_map],
        "edges": [e for e in graph["edges"] if e["id"] in visited_edges],
    }


# ── Ripple analysis ───────────────────────────────────────────────────────────

async def ripple_from_node(
    node_id: str,
    change: str = "rise",   # rise | fall | shock
    max_depth: int = 5,
    min_weight: float = 0.08,
) -> dict:
    """
    BFS ripple traversal from a source node following directed edges.

    The `change` parameter sets the source direction:
      rise  → source entity increases/strengthens (e.g. crude oil rises)
      fall  → source entity decreases/weakens     (e.g. crude oil falls)
      shock → large-magnitude move (same direction as rise, larger weight)

    Returns impacts sorted by accumulated_weight descending.
    """
    graph = await get_full_graph()

    adj: dict[str, list[dict]] = {}
    for e in graph["edges"]:
        adj.setdefault(e["source"], []).append(e)

    nodes_map = {n["id"]: n for n in graph["nodes"]}
    if node_id not in nodes_map:
        return {"source": None, "change": change, "total_impacted": 0, "impacts": []}

    shock_mult = 1.3 if change == "shock" else 1.0
    source_dir = "positive" if change in ("rise", "shock") else "negative"

    # Queue: (node_id, direction, accumulated_weight, depth, path)
    queue: list[tuple[str, str, float, int, list[dict]]] = [
        (node_id, source_dir, 1.0 * shock_mult, 0, [])
    ]
    best_weight: dict[str, float] = {node_id: 1.0}
    results: list[dict] = []

    while queue:
        curr_id, curr_dir, curr_w, depth, path = queue.pop(0)
        if depth >= max_depth:
            continue

        for edge in adj.get(curr_id, []):
            tgt_id   = edge["target"]
            polarity = EDGE_POLARITY.get(edge["edge_type"], "neutral")

            if polarity == "same":
                tgt_dir = curr_dir
            elif polarity == "inverse":
                tgt_dir = "negative" if curr_dir == "positive" else "positive"
            else:
                tgt_dir = "uncertain"

            new_w = curr_w * edge["weight"] * edge.get("confidence", 0.8)
            if new_w < min_weight:
                continue
            if best_weight.get(tgt_id, 0) >= new_w:
                continue
            best_weight[tgt_id] = new_w

            tgt_node = nodes_map.get(tgt_id)
            if not tgt_node or tgt_id == node_id:
                continue

            new_path = path + [{"from": curr_id, "edge_type": edge["edge_type"], "to": tgt_id}]
            results.append({
                "node":              tgt_node,
                "depth":             depth + 1,
                "impact_direction":  tgt_dir,
                "accumulated_weight": round(new_w, 3),
                "path":              new_path,
                "edge_type":         edge["edge_type"],
                "lag_days":          edge.get("lag_days") or 0,
                "description":       edge.get("description") or "",
            })
            queue.append((tgt_id, tgt_dir, new_w, depth + 1, new_path))

    results.sort(key=lambda x: x["accumulated_weight"], reverse=True)

    return {
        "source":          nodes_map[node_id],
        "change":          change,
        "total_impacted":  len(results),
        "impacts":         results,
    }


# ── Graph write ───────────────────────────────────────────────────────────────

async def upsert_node(
    node_type: str,
    label: str,
    ticker: str | None = None,
    description: str | None = None,
    extra: dict | None = None,
    auto_added: bool = False,
    node_id: str | None = None,
) -> str:
    from app.db.session import AsyncSessionLocal
    from app.db.models.intelligence_graph import IGNode
    from sqlalchemy import select

    nid = node_id or make_node_id(node_type, label)
    now = datetime.now(timezone.utc)

    async with AsyncSessionLocal() as db:
        ex = (await db.execute(select(IGNode).where(IGNode.id == nid))).scalar_one_or_none()
        if ex:
            ex.label       = label
            ex.ticker      = ticker or ex.ticker
            ex.description = description or ex.description
            ex.extra       = {**(ex.extra or {}), **(extra or {})}
            ex.updated_at  = now
        else:
            db.add(IGNode(
                id=nid, node_type=node_type, label=label,
                ticker=ticker, description=description,
                extra=extra or {}, auto_added=auto_added,
                created_at=now, updated_at=now,
            ))
        await db.commit()

    await _invalidate_cache()
    return nid


async def upsert_edge(
    source_id: str,
    target_id: str,
    edge_type: str,
    weight: float = 0.7,
    confidence: float = 0.8,
    lag_days: int = 0,
    description: str | None = None,
    source_event: str | None = None,
    auto_added: bool = False,
) -> str:
    from app.db.session import AsyncSessionLocal
    from app.db.models.intelligence_graph import IGEdge, IGNode
    from sqlalchemy import select

    eid = make_edge_id(source_id, edge_type, target_id)

    async with AsyncSessionLocal() as db:
        ex = (await db.execute(select(IGEdge).where(IGEdge.id == eid))).scalar_one_or_none()
        if ex:
            ex.weight      = max(ex.weight, weight)
            ex.confidence  = max(ex.confidence, confidence)
            ex.description = description or ex.description
        else:
            # Verify nodes exist
            src = (await db.execute(select(IGNode).where(IGNode.id == source_id))).scalar_one_or_none()
            tgt = (await db.execute(select(IGNode).where(IGNode.id == target_id))).scalar_one_or_none()
            if not src or not tgt:
                log.warning("mig.edge_skip_missing_nodes", src=source_id, tgt=target_id)
                return eid
            db.add(IGEdge(
                id=eid, source_id=source_id, target_id=target_id,
                edge_type=edge_type, weight=weight, confidence=confidence,
                lag_days=lag_days, description=description,
                source_event=source_event, auto_added=auto_added,
                created_at=datetime.now(timezone.utc),
            ))
        await db.commit()

    await _invalidate_cache()
    return eid


# ── Auto-update from new events ───────────────────────────────────────────────

async def update_from_event(event: dict) -> None:
    """Extract entities from a triage event and upsert into the graph.

    Called automatically when high-urgency (>=6) events are processed.
    Only auto-adds nodes/edges that don't conflict with the seed graph.
    """
    urgency   = float(event.get("urgency") or event.get("impact_score") or 0)
    if urgency < 6:
        return

    event_id  = str(event.get("id", ""))[:40]
    headline  = (event.get("headline") or "")[:100]
    sectors   = event.get("affected_sectors") or event.get("sectors") or []
    companies = event.get("companies") or []
    sentiment = event.get("sentiment") or "neutral"

    et = "influences"
    if sentiment == "bullish":
        et = "benefits"
    elif sentiment == "bearish":
        et = "hurts"

    # Upsert event node for high-urgency events
    evt_node_id: str | None = None
    if headline and urgency >= 7:
        evt_node_id = await upsert_node(
            "event", headline,
            auto_added=True, node_id=f"event:{event_id}" if event_id else None,
        )

    # Upsert sectors + link
    for s in (sectors[:5] if isinstance(sectors, list) else []):
        s_label = s if isinstance(s, str) else str(s)
        if not s_label:
            continue
        sid = await upsert_node("sector", s_label, auto_added=True)
        if evt_node_id:
            await upsert_edge(evt_node_id, sid, et, min(urgency / 10, 0.9),
                              source_event=event_id, auto_added=True)

    # Upsert companies + link
    for co in (companies[:3] if isinstance(companies, list) else []):
        co_label  = (co.get("name") or co.get("symbol", "")) if isinstance(co, dict) else str(co)
        co_ticker = co.get("symbol") if isinstance(co, dict) else None
        if not co_label:
            continue
        cid = await upsert_node("company", co_label, ticker=co_ticker, auto_added=True)
        if evt_node_id:
            await upsert_edge(evt_node_id, cid, et, min(urgency / 10, 0.9),
                              source_event=event_id, auto_added=True)


# ── Seed ─────────────────────────────────────────────────────────────────────

async def seed_intelligence_graph() -> None:
    """Populate the MIG with verified Indian market relationships.

    Skipped if the graph already has nodes (idempotent).
    """
    from app.db.session import AsyncSessionLocal
    from app.db.models.intelligence_graph import IGNode
    from sqlalchemy import select, func

    async with AsyncSessionLocal() as db:
        count = (await db.execute(select(func.count()).select_from(IGNode))).scalar_one()
    if count > 0:
        log.info("mig.seed_skipped", existing_nodes=count)
        return

    log.info("mig.seeding")

    # ── Commodities ───────────────────────────────────────────────────────────
    for label, desc in [
        ("Crude Oil",    "Global benchmark; key input for fuel, petrochemicals, plastics. India imports 85% of needs."),
        ("Gold",         "Safe-haven metal; India is world's 2nd largest consumer. Imports drive CAD."),
        ("Silver",       "Industrial and investment metal; correlated with gold and industrial output."),
        ("Natural Gas",  "Power generation and industrial fuel; LNG import price volatile."),
        ("Coal",         "Fuels 70%+ of India's electricity generation; domestic + imported."),
        ("Steel",        "Core infrastructure and manufacturing input; prices track China demand."),
    ]:
        await upsert_node("commodity", label, description=desc)

    # ── Sectors ───────────────────────────────────────────────────────────────
    for label, desc in [
        ("Airlines",          "Fuel-intensive; jet fuel = 35-45% of operating costs. USD-denominated leases add FX risk."),
        ("IT",                "Exports USD revenue; weak INR inflates INR earnings. USA is 60%+ of revenue."),
        ("Banking",           "Rate-sensitive; NII expands short-term on rate hikes; credit risk rises in slowdowns."),
        ("NBFC",              "Market-rate borrowers; squeezed immediately when RBI hikes repo."),
        ("Real Estate",       "Rate and liquidity sensitive; demand tracks EMI affordability."),
        ("Auto",              "Rate-sensitive demand; steel/chip inputs; EV disruption underway."),
        ("FMCG",              "Defensive; input cost inflation compresses margins. Rural demand proxy."),
        ("Pharma",            "USD earner (generics exports). API imports from China create input risk."),
        ("Infrastructure",    "Policy and budget driven; largest consumer of steel, cement, power."),
        ("Cement",            "Infrastructure proxy; coal and power are primary cost drivers."),
        ("Paint",             "Crude derivatives (TiO2, solvents) = 40%+ of raw material cost."),
        ("Telecom",           "Capital intensive; ARPUs drive profitability; 5G capex cycle."),
        ("Defence",           "Government policy-driven; PLI and Make-in-India primary beneficiary."),
        ("Tourism",           "Discretionary; suppressed by expensive flights and economic slowdowns."),
        ("Hotels",            "Linked to tourism arrivals; consumer discretionary at heart."),
        ("Metal",             "China demand proxy; tracks global industrial cycle. Iron ore key input."),
        ("Power",             "Coal and gas cost sensitive; AI data centers + EV charging as long-term tailwinds."),
        ("Consumer Spending", "Macro demand indicator; hurt by inflation, high EMIs, and job uncertainty."),
        ("Jewellery",         "Gold-price linked; premium discretionary; heavy festive/wedding seasonality."),
        ("Chemical",          "Crude derivative inputs; China+1 opportunity for specialty chemicals."),
        ("Textiles",          "PLI beneficiary; USD earner; competes with Bangladesh and Vietnam."),
        ("Oil & Gas",         "Upstream exploration benefits from high crude; downstream OMCs face margin pressure."),
    ]:
        await upsert_node("sector", label, description=desc)

    # ── Themes ────────────────────────────────────────────────────────────────
    for label, desc in [
        ("AI Boom",           "Global AI adoption driving tech capex; benefits cloud, power, data centres, Indian IT."),
        ("PLI Scheme",        "Production Linked Incentive — boosts domestic manufacturing across 14 sectors."),
        ("Make in India",     "Domestic manufacturing drive; defence and electronics manufacturing focus."),
        ("EV Transition",     "Electric vehicle adoption; disrupts traditional auto, benefits power and battery supply chain."),
        ("Inflation",         "Rising consumer prices; compresses margins, triggers rate hikes, hurts real demand."),
        ("Recession Fear",    "Global slowdown anxiety; risk-off sentiment, FII outflows, commodity demand drops."),
        ("China Plus One",    "Supply chain diversification away from China; India wins in chemicals, textiles, electronics."),
        ("Rate Cut Cycle",    "RBI easing cycle; benefits rate-sensitive borrowers, re-rates equities higher."),
        ("Rate Hike Cycle",   "RBI tightening cycle; hurts borrowers, NBFCs, real estate; defensive bias."),
        ("Global Risk Off",   "FII selling emerging markets; Nifty and INR weaken together."),
        ("FII Buying",        "Foreign institutional inflows; Nifty positive, INR strengthens, momentum builds."),
        ("Capex Super Cycle", "Multi-year infrastructure and manufacturing investment boom; government + private."),
    ]:
        await upsert_node("theme", label, description=desc)

    # ── Countries ─────────────────────────────────────────────────────────────
    for label, desc in [
        ("USA",         "Largest export market for IT and pharma; Fed policy drives global rates and FII flows."),
        ("China",       "Largest commodity consumer globally; slowdown ripples to metals, crude, and global growth."),
        ("Europe",      "IT and pharma export destination; gas-price-sensitive post-Ukraine war."),
        ("Middle East", "India's primary crude oil supplier (60%+); geopolitical risk drives oil volatility."),
    ]:
        await upsert_node("country", label, description=desc)

    # ── Indices ───────────────────────────────────────────────────────────────
    for label, ticker, desc in [
        ("Nifty 50",   "^NSEI",    "India's benchmark 50-stock large-cap index."),
        ("Bank Nifty", "^NSEBANK", "India's banking sector index; rate and credit cycle sensitive."),
        ("Nifty IT",   "^CNXIT",   "India's IT sector index; USD/INR and US growth sensitive."),
    ]:
        await upsert_node("index", label, ticker=ticker, description=desc)

    # ── Currencies ────────────────────────────────────────────────────────────
    for label, ticker, desc in [
        ("USD/INR", "USDINR=X", "Dollar-rupee rate. Weak INR benefits IT/pharma exports, hurts importers."),
        ("EUR/INR", "EURINR=X", "Euro-rupee rate. Europe-India trade and investment proxy."),
    ]:
        await upsert_node("currency", label, ticker=ticker, description=desc)

    # ── Policies ─────────────────────────────────────────────────────────────
    for label, desc in [
        ("RBI Rate Hike",           "RBI increases repo rate; hurts borrowers and growth-sensitive sectors."),
        ("RBI Rate Cut",            "RBI decreases repo rate; benefits borrowers and rate-sensitive sectors."),
        ("Union Budget Infra Boost","Annual budget allocates record capex for roads, railways, ports, airports."),
        ("PLI Manufacturing",       "PLI scheme disbursements for electronics, auto, textiles, defence."),
        ("Windfall Tax on Crude",   "Government levies windfall tax on domestic crude producers when prices spike."),
        ("GST",                     "Goods and Services Tax; unified indirect tax affecting FMCG and retail margins."),
    ]:
        await upsert_node("policy", label, description=desc)

    # ── Helper ────────────────────────────────────────────────────────────────

    async def E(src: str, st: str, et: str, tgt: str, tt: str,
                w: float = 0.70, c: float = 0.85, lag: int = 0, d: str = "") -> None:
        await upsert_edge(
            make_node_id(st, src), make_node_id(tt, tgt),
            et, w, c, lag, d or None,
        )

    # ── CRUDE OIL — the canonical cascade ────────────────────────────────────
    # Oil → Airlines → Tourism → Hotels → Consumer Spending
    await E("Crude Oil", "commodity", "hurts",     "Airlines",          "sector",   0.90, 0.95, 0,   "Jet fuel = 35-45% of airline operating costs; direct pass-through")
    await E("Crude Oil", "commodity", "hurts",     "Paint",             "sector",   0.80, 0.90, 14,  "TiO₂ and solvents are crude derivatives; 40%+ of RM cost")
    await E("Crude Oil", "commodity", "hurts",     "Chemical",          "sector",   0.75, 0.88, 7,   "Petrochemical feedstocks = crude derivatives")
    await E("Crude Oil", "commodity", "hurts",     "Cement",            "sector",   0.55, 0.82, 7,   "Pet coke (crude derivative) is key cement kiln fuel")
    await E("Crude Oil", "commodity", "hurts",     "FMCG",              "sector",   0.50, 0.78, 14,  "Packaging (polyethylene) and logistics costs track crude")
    await E("Crude Oil", "commodity", "hurts",     "Auto",              "sector",   0.45, 0.78, 30,  "Higher pump prices suppress vehicle demand; plastics cost up")
    await E("Crude Oil", "commodity", "benefits",  "Oil & Gas",         "sector",   0.85, 0.92, 0,   "Upstream producers (ONGC, Oil India) directly benefit from higher crude")
    await E("Crude Oil", "commodity", "influences","USD/INR",           "currency", 0.80, 0.90, 3,   "India imports 85% of crude in USD — high prices weaken INR")
    await E("Crude Oil", "commodity", "influences","Inflation",         "theme",    0.85, 0.92, 14,  "Oil is the single biggest input to Indian CPI basket")
    await E("Crude Oil", "commodity", "influences","Middle East",       "country",  0.70, 0.80, 0,   "Oil revenues drive Middle East geopolitical stability and demand")

    # Airlines cascade downstream
    await E("Airlines",  "sector",    "hurts",     "Tourism",           "sector",   0.65, 0.82, 7,   "Expensive or unavailable flights suppress inbound/outbound travel")
    await E("Tourism",   "sector",    "hurts",     "Hotels",            "sector",   0.80, 0.88, 14,  "Lower tourist arrivals directly reduce hotel occupancy rates")
    await E("Tourism",   "sector",    "influences","Consumer Spending",  "sector",   0.55, 0.75, 30,  "Tourism spend is a component of consumer discretionary demand")
    await E("Hotels",    "sector",    "influences","Consumer Spending",  "sector",   0.45, 0.72, 14,  "Hospitality is consumer discretionary; both track economic mood")

    # ── USD/INR ───────────────────────────────────────────────────────────────
    await E("USD/INR",   "currency",  "benefits",  "IT",                "sector",   0.85, 0.95, 0,   "IT earns USD; INR depreciation inflates INR revenues mechanically")
    await E("USD/INR",   "currency",  "benefits",  "Pharma",            "sector",   0.75, 0.90, 7,   "Generic pharma exports USD; weak INR boosts reported INR earnings")
    await E("USD/INR",   "currency",  "benefits",  "Textiles",          "sector",   0.65, 0.85, 7,   "Textile exports become price-competitive globally on weak INR")
    await E("USD/INR",   "currency",  "hurts",     "Airlines",          "sector",   0.70, 0.88, 0,   "Aircraft leases and USD-denominated fuel costs rise in INR terms")
    await E("USD/INR",   "currency",  "hurts",     "Auto",              "sector",   0.55, 0.80, 14,  "Auto imports semiconductors and components priced in USD")
    await E("USD/INR",   "currency",  "hurts",     "Chemical",          "sector",   0.50, 0.75, 7,   "Specialty chemical imports and API raw materials priced in USD")
    await E("USD/INR",   "currency",  "influences","Inflation",         "theme",    0.65, 0.82, 30,  "Weak INR makes all imports more expensive → imported inflation")
    await E("USD/INR",   "currency",  "hurts",     "NBFC",              "sector",   0.40, 0.70, 0,   "ECB (external commercial borrowing) repayment burden rises in INR")
    await E("USD/INR",   "currency",  "influences","Nifty 50",          "index",    0.60, 0.80, 0,   "Persistent INR weakness triggers FII selling → Nifty headwind")

    # ── GOLD ─────────────────────────────────────────────────────────────────
    await E("Gold",      "commodity", "benefits",  "Jewellery",         "sector",   0.85, 0.92, 0,   "Gold is the primary input for India's ₹5L-cr jewellery sector")
    await E("Gold",      "commodity", "influences","Banking",           "sector",   0.40, 0.70, 0,   "Gold loans are a key NBFC/SFB product; gold price affects LTV")
    await E("Gold",      "commodity", "hurts",     "USD/INR",           "currency", 0.55, 0.78, 7,   "Record gold imports widen India's current account deficit → weak INR")
    await E("Gold",      "commodity", "influences","Global Risk Off",   "theme",    0.70, 0.85, 0,   "Gold is the canonical risk-off safe haven; they move together")
    await E("Gold",      "commodity", "influences","Recession Fear",    "theme",    0.65, 0.82, 0,   "Gold rises on recession fear as investors seek store of value")

    # ── NATURAL GAS ──────────────────────────────────────────────────────────
    await E("Natural Gas","commodity","hurts",     "Power",             "sector",   0.75, 0.88, 0,   "Gas is key fuel for peaking power plants; price spikes hit power cos")
    await E("Natural Gas","commodity","hurts",     "Chemical",          "sector",   0.70, 0.85, 0,   "Gas is feedstock for ammonia/fertilisers and specialty chemicals")
    await E("Natural Gas","commodity","influences","Inflation",         "theme",    0.60, 0.78, 14,  "Gas prices pass through to electricity bills and industrial costs")

    # ── COAL ─────────────────────────────────────────────────────────────────
    await E("Coal",      "commodity", "hurts",     "Power",             "sector",   0.80, 0.90, 7,   "Coal fuels 70%+ of India's electricity; coal price = power cost")
    await E("Coal",      "commodity", "hurts",     "Cement",            "sector",   0.70, 0.85, 7,   "Coal and pet coke are primary fuels in cement kilns")
    await E("Coal",      "commodity", "influences","Inflation",         "theme",    0.55, 0.78, 14,  "Coal costs pass through to electricity bills → industrial inflation")

    # ── STEEL ─────────────────────────────────────────────────────────────────
    await E("Steel",     "commodity", "benefits",  "Infrastructure",    "sector",   0.85, 0.92, 0,   "Steel is the primary structural material for roads, bridges, railways")
    await E("Steel",     "commodity", "benefits",  "Defence",           "sector",   0.60, 0.80, 30,  "Defence shipbuilding, armoured vehicles, artillery require steel")
    await E("Steel",     "commodity", "hurts",     "Auto",              "sector",   0.60, 0.82, 14,  "Steel is a major input cost; higher steel prices compress auto margins")
    await E("China",     "country",   "influences","Steel",             "commodity",0.75, 0.88, 0,   "China produces and consumes 50%+ of global steel; slowdown = price crash")
    await E("China",     "country",   "influences","Metal",             "sector",   0.80, 0.90, 0,   "Metal prices globally track China's industrial demand cycle closely")

    # ── RBI RATE HIKE ─────────────────────────────────────────────────────────
    await E("RBI Rate Hike","policy", "hurts",     "NBFC",              "sector",   0.90, 0.95, 0,   "NBFCs borrow at market rates; hikes immediately compress NIMs")
    await E("RBI Rate Hike","policy", "hurts",     "Real Estate",       "sector",   0.85, 0.92, 30,  "Higher home loan rates reduce affordability; demand falls with a lag")
    await E("RBI Rate Hike","policy", "hurts",     "Auto",              "sector",   0.70, 0.88, 30,  "Higher auto loan EMIs depress vehicle purchase decisions")
    await E("RBI Rate Hike","policy", "hurts",     "Infrastructure",    "sector",   0.65, 0.82, 30,  "Higher project financing costs slow private infra investment")
    await E("RBI Rate Hike","policy", "influences","Banking",           "sector",   0.70, 0.85, 0,   "Short-term NII expands; longer-term NPA risk rises if economy slows")
    await E("RBI Rate Hike","policy", "hurts",     "Consumer Spending", "sector",   0.60, 0.80, 30,  "Higher EMI burden on home, auto, and personal loans cuts discretionary")
    await E("RBI Rate Hike","policy", "influences","Inflation",         "theme",    0.75, 0.88, 60,  "Rate hikes aim to reduce demand-pull inflation; lag of 2-3 quarters")
    await E("RBI Rate Hike","policy", "influences","Rate Hike Cycle",   "theme",    0.90, 0.95, 0,   "Multiple hikes signal and reinforce the rate hike cycle theme")

    # ── RBI RATE CUT ──────────────────────────────────────────────────────────
    await E("RBI Rate Cut","policy",  "benefits",  "Real Estate",       "sector",   0.85, 0.92, 30,  "Lower home loan rates restore affordability and unlock demand")
    await E("RBI Rate Cut","policy",  "benefits",  "Auto",              "sector",   0.75, 0.88, 30,  "Lower auto loan EMIs stimulate vehicle purchase decisions")
    await E("RBI Rate Cut","policy",  "benefits",  "NBFC",              "sector",   0.80, 0.90, 0,   "NBFCs borrow cheaper; cost of funds falls immediately")
    await E("RBI Rate Cut","policy",  "benefits",  "Infrastructure",    "sector",   0.70, 0.85, 30,  "Lower project financing costs accelerate private capex decisions")
    await E("RBI Rate Cut","policy",  "benefits",  "Consumer Spending", "sector",   0.60, 0.80, 60,  "Lower EMIs increase household disposable income → spending")
    await E("RBI Rate Cut","policy",  "benefits",  "Nifty 50",          "index",    0.75, 0.85, 7,   "Rate cuts lift sentiment; P/E multiples re-rate on lower cost of capital")
    await E("RBI Rate Cut","policy",  "influences","Rate Cut Cycle",    "theme",    0.90, 0.95, 0,   "Multiple cuts confirm and reinforce the easing cycle theme")

    # ── USA ───────────────────────────────────────────────────────────────────
    await E("USA",       "country",   "influences","IT",                "sector",   0.85, 0.92, 30,  "USA is 60%+ of Indian IT export revenues; US slowdown = fewer deals")
    await E("USA",       "country",   "influences","Pharma",            "sector",   0.70, 0.85, 30,  "USA is the largest market for Indian generic pharma by value")
    await E("USA",       "country",   "influences","Textiles",          "sector",   0.55, 0.78, 30,  "US is a top-3 destination for Indian apparel and textile exports")
    await E("USA",       "country",   "influences","Recession Fear",    "theme",    0.80, 0.90, 0,   "US recession signals trigger global risk-off and EM outflows")
    await E("USA",       "country",   "influences","Global Risk Off",   "theme",    0.85, 0.92, 0,   "Fed rate hikes drive DXY strength and global risk-off mode")
    await E("USA",       "country",   "influences","USD/INR",           "currency", 0.75, 0.88, 0,   "US Fed policy drives DXY; strong dollar = weak rupee")

    # ── CHINA ─────────────────────────────────────────────────────────────────
    await E("China",     "country",   "influences","China Plus One",    "theme",    0.90, 0.92, 0,   "China supply chain concerns are the root cause of the theme")
    await E("China",     "country",   "benefits",  "Chemical",          "sector",   0.65, 0.80, 90,  "India's chemical sector wins contracts as China+1 diversification accelerates")
    await E("China",     "country",   "benefits",  "Textiles",          "sector",   0.60, 0.78, 90,  "Global brands shift sourcing from China to India for textile exports")
    await E("China",     "country",   "influences","Crude Oil",         "commodity",0.65, 0.80, 0,   "China is world's largest crude importer; slowdown suppresses global oil prices")

    # ── MIDDLE EAST ───────────────────────────────────────────────────────────
    await E("Middle East","country",  "supplies",  "Crude Oil",         "commodity",0.85, 0.90, 0,   "Middle East (Saudi, UAE, Iraq) supplies 60%+ of India's crude imports")
    await E("Middle East","country",  "influences","Crude Oil",         "commodity",0.80, 0.88, 0,   "OPEC+ production decisions directly set global crude price direction")

    # ── THEMES ────────────────────────────────────────────────────────────────
    await E("AI Boom",   "theme",     "benefits",  "IT",                "sector",   0.90, 0.92, 0,   "AI adoption drives demand for Indian tech services, cloud, and AI engineers")
    await E("AI Boom",   "theme",     "benefits",  "Power",             "sector",   0.70, 0.82, 90,  "AI data centres need 10-100x more power per compute unit than legacy IT")
    await E("AI Boom",   "theme",     "influences","Nifty IT",          "index",    0.85, 0.90, 0,   "AI narrative re-rates IT sector P/E multiples and drives index outperformance")

    await E("PLI Scheme","theme",     "benefits",  "Defence",           "sector",   0.80, 0.88, 180, "PLI drives domestic defence manufacturing investment and local sourcing")
    await E("PLI Scheme","theme",     "benefits",  "Chemical",          "sector",   0.70, 0.82, 180, "PLI for specialty chemicals reduces import dependence on China")
    await E("PLI Scheme","theme",     "benefits",  "Textiles",          "sector",   0.65, 0.80, 180, "PLI drives large-format textile park investments")
    await E("PLI Scheme","theme",     "benefits",  "Auto",              "sector",   0.60, 0.78, 180, "PLI for auto components and EV manufacturing secures supply chain")
    await E("PLI Manufacturing","policy","benefits","Defence",           "sector",   0.82, 0.90, 0,   "PLI disbursements for defence components, systems, and shipbuilding")
    await E("PLI Manufacturing","policy","benefits","Auto",              "sector",   0.72, 0.85, 0,   "PLI incentives for auto components and advanced chemistry cells")

    await E("EV Transition","theme",  "benefits",  "Power",             "sector",   0.80, 0.85, 365, "EV charging infrastructure adds significant new power demand")
    await E("EV Transition","theme",  "hurts",     "Auto",              "sector",   0.55, 0.72, 365, "EV transition disrupts ICE component suppliers; margins compress")
    await E("EV Transition","theme",  "hurts",     "Crude Oil",         "commodity",0.50, 0.65, 730, "Long-term EV adoption structurally reduces gasoline demand")
    await E("EV Transition","theme",  "benefits",  "Chemical",          "sector",   0.60, 0.78, 365, "Battery chemistry, electrolytes, and cell materials drive chemical demand")

    await E("Inflation",  "theme",    "hurts",     "FMCG",              "sector",   0.75, 0.88, 0,   "Input cost inflation (packaging, logistics, RM) compresses FMCG EBITDA margins")
    await E("Inflation",  "theme",    "hurts",     "Consumer Spending", "sector",   0.80, 0.90, 30,  "Real purchasing power erodes; consumers trade down or defer purchases")
    await E("Inflation",  "theme",    "influences","RBI Rate Hike",     "policy",   0.85, 0.92, 30,  "High inflation forces RBI hand on rate hikes (MPC mandate is 4% CPI)")
    await E("Inflation",  "theme",    "hurts",     "Nifty 50",          "index",    0.60, 0.80, 30,  "Inflation compresses corporate margins and triggers multiple de-rating")

    await E("Recession Fear","theme", "hurts",     "IT",                "sector",   0.75, 0.88, 90,  "US recession reduces tech spending; Indian IT deal wins slow, BFSI clients cut")
    await E("Recession Fear","theme", "hurts",     "Metal",             "sector",   0.70, 0.85, 0,   "Recession fear crashes industrial commodity and metal prices globally")
    await E("Recession Fear","theme", "influences","Global Risk Off",   "theme",    0.90, 0.95, 0,   "Recession fear is the primary driver of broad global risk-off sentiment")
    await E("Recession Fear","theme", "influences","Crude Oil",         "commodity",0.65, 0.80, 0,   "Recession reduces oil demand expectations; futures curve falls")

    await E("Global Risk Off","theme","hurts",     "Nifty 50",          "index",    0.80, 0.88, 0,   "FII selling in risk-off episodes directly depresses Nifty")
    await E("Global Risk Off","theme","hurts",     "Bank Nifty",        "index",    0.75, 0.85, 0,   "Banking has highest FII ownership; most affected by FII selling")
    await E("Global Risk Off","theme","hurts",     "USD/INR",           "currency", 0.75, 0.88, 0,   "Risk-off = capital outflows from EM = rupee weakens sharply")

    await E("FII Buying","theme",     "benefits",  "Nifty 50",          "index",    0.85, 0.90, 0,   "FII inflows directly lift Nifty through large-cap buying")
    await E("FII Buying","theme",     "benefits",  "Banking",           "sector",   0.80, 0.88, 0,   "Banking stocks have highest FII ownership; FII buying = banking rally")
    await E("FII Buying","theme",     "benefits",  "USD/INR",           "currency", 0.70, 0.82, 0,   "FII inflows are in USD; conversion to INR strengthens the rupee")

    await E("China Plus One","theme", "benefits",  "Chemical",          "sector",   0.75, 0.85, 90,  "India becomes preferred alternate source for specialty chemicals")
    await E("China Plus One","theme", "benefits",  "Textiles",          "sector",   0.70, 0.82, 90,  "Global apparel brands shift sourcing from China to India")
    await E("China Plus One","theme", "benefits",  "Defence",           "sector",   0.60, 0.78, 180, "Defence component supply chains diversify away from China")

    await E("Capex Super Cycle","theme","benefits","Infrastructure",    "sector",   0.90, 0.92, 0,   "Infrastructure IS the capex cycle; roads, railways, ports, airports")
    await E("Capex Super Cycle","theme","benefits","Cement",            "sector",   0.85, 0.90, 0,   "Cement demand surges with infra-led capex — 1:1 relationship")
    await E("Capex Super Cycle","theme","benefits","Steel",             "commodity",0.80, 0.88, 0,   "Steel demand driven by infra and manufacturing investment boom")
    await E("Capex Super Cycle","theme","benefits","Power",             "sector",   0.70, 0.85, 0,   "Capex cycle includes large power transmission and generation investments")

    # ── UNION BUDGET INFRA BOOST ──────────────────────────────────────────────
    await E("Union Budget Infra Boost","policy","benefits","Infrastructure","sector",0.92, 0.95, 0,  "Direct government capex budget allocation for infra projects")
    await E("Union Budget Infra Boost","policy","benefits","Cement",    "sector",   0.85, 0.92, 0,   "Budget infra → road/bridge contracts → cement demand surge")
    await E("Union Budget Infra Boost","policy","benefits","Steel",     "commodity",0.80, 0.90, 0,   "Government infra projects are the largest steel offtake client")
    await E("Union Budget Infra Boost","policy","influences","Capex Super Cycle","theme",0.80,0.88,0,"Budget infra boost is the trigger/reinforcement of the capex theme")

    # Infrastructure downstream
    await E("Infrastructure","sector","benefits",  "Cement",            "sector",   0.80, 0.88, 30,  "Infra projects consume 40%+ of India's cement output")
    await E("Infrastructure","sector","benefits",  "Steel",             "commodity",0.75, 0.85, 30,  "Infra is the single largest steel consuming sector in India")
    await E("Infrastructure","sector","benefits",  "Power",             "sector",   0.65, 0.80, 30,  "Infra capex includes power transmission grid investments")

    # Indices composed of sectors
    await E("IT",        "sector",    "influences","Nifty IT",          "index",    0.90, 0.95, 0,   "IT sector IS the Nifty IT index; moves track perfectly")
    await E("Banking",   "sector",    "influences","Bank Nifty",        "index",    0.92, 0.96, 0,   "Banking sector IS the Bank Nifty index")
    await E("Banking",   "sector",    "influences","Nifty 50",          "index",    0.75, 0.88, 0,   "Banking has ~30% weight in Nifty 50; largest constituent block")
    await E("IT",        "sector",    "influences","Nifty 50",          "index",    0.65, 0.82, 0,   "IT has ~15% weight in Nifty 50; second largest block")

    # Windfall tax
    await E("Windfall Tax on Crude","policy","hurts","Oil & Gas",       "sector",   0.80, 0.88, 0,   "Windfall tax directly reduces realisation for ONGC, Oil India")

    # Rate hike cycle → Bank Nifty
    await E("Rate Hike Cycle","theme","influences","Bank Nifty",        "index",    0.75, 0.85, 0,   "Rate hike cycle is the primary driver of Bank Nifty's relative performance")
    await E("Rate Cut Cycle", "theme","benefits",  "Nifty 50",          "index",    0.75, 0.85, 0,   "Rate cut cycle lifts all boats; re-rates growth equities higher")

    log.info("mig.seeded")
