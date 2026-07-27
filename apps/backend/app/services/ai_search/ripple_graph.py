"""
Ripple Graph (Phase 2A) — merges the REAL, already-seeded, weighted causal
graph (intelligence_graph_service: commodities/sectors/themes/policies/
countries/indices/currencies, curated relationships with real lag days —
see that module's seed_intelligence_graph) with this response's own
resolved companies, same-industry competitors, historical precedents,
risks, and opportunities into ONE renderable multi-hop graph.

V3 never called ai_search_service._build_ripple_chain before this — only
V2 did. The "Intelligence Graph" panel was showing a shallow 3-level
query -> sector -> company diagram (the older _build_graph), missing the
deep causal chain entirely. This module is additive: reuses
_build_ripple_chain verbatim (V2's own mechanism, unchanged) and extends
it downward to the specific companies/competitors/historical events/risks/
opportunities THIS answer is actually about.

Never invents an edge or node. Every macro-chain node/edge is a real
traversal result from the seeded graph; every company/competitor/
historical/risk/opportunity node is real data this response already has.
Gracefully degrades to the old shallow shape when the query's entities
don't resolve to any graph node (not every query has one) — same
resilience contract as _build_ripple_chain itself.
"""
from __future__ import annotations

_ROW_HEIGHT = 130
_COL_WIDTH = 170
_MAX_PER_ROW = 6


def _sector_for(symbol: str) -> str | None:
    from app.api.companies import _NSE_UNIVERSE
    return next((co["sector"] for co in _NSE_UNIVERSE if co["symbol"] == symbol), None)


def _industry_for(symbol: str) -> str | None:
    from app.api.companies import _NSE_UNIVERSE
    return next((co["industry"] for co in _NSE_UNIVERSE if co["symbol"] == symbol), None)


def _competitors_for(symbol: str, exclude: set[str], limit: int = 2) -> list[dict]:
    """Same reasoning as followups._same_sector_peers — sector alone isn't
    enough (this data's "Defence" bucket mixes real defence manufacturers
    with unrelated railway PSUs), so a candidate's industry must also
    share a real word with the primary company's industry."""
    from app.api.companies import _NSE_UNIVERSE
    import re
    sector = _sector_for(symbol)
    primary_industry = _industry_for(symbol) or ""
    if not sector:
        return []
    primary_words = {w.lower() for w in primary_industry.split() if len(w) > 3}
    out = []
    for co in _NSE_UNIVERSE:
        if co["sector"] != sector or co["symbol"] in exclude:
            continue
        if primary_words:
            candidate_words = {w.lower() for w in re.sub(r"[.,()&]", " ", co.get("industry") or "").split() if len(w) > 3}
            if not (primary_words & candidate_words):
                continue
        out.append(co)
        if len(out) >= limit:
            break
    return out


async def build(
    query: str,
    companies_enriched: list[dict],
    sectors_raw: list[dict],
    similar_historical: list[dict],
    risks: list[str],
    opportunities: list[str],
) -> dict:
    from app.services.ai_search_service import _build_ripple_chain

    nodes: list[dict] = []
    edges: list[dict] = []
    seen_ids: set[str] = set()

    def add_node(nid: str, label: str, ntype: str, row: int, col: int, **extra) -> str:
        if nid in seen_ids:
            return nid
        seen_ids.add(nid)
        nodes.append({"id": nid, "label": label, "type": ntype, "x": col * _COL_WIDTH, "y": row * _ROW_HEIGHT, **extra})
        return nid

    def add_edge(source: str, target: str, label: str) -> None:
        eid = f"{source}->{target}"
        if any(e["id"] == eid for e in edges):
            return
        edges.append({"id": eid, "source": source, "target": target, "label": label})

    q_label = query[:28] + ("…" if len(query) > 28 else "")
    add_node("q", q_label, "query", 0, 0)

    # ── Real macro causal chain, from the seeded intelligence graph ────────
    try:
        chain = await _build_ripple_chain(query)
    except Exception:
        chain = []

    row = 1
    chain_id_map: dict[str, str] = {}  # real graph node id -> our local node id
    sector_row_by_label: dict[str, int] = {}
    if chain:
        for level in chain:
            level_nodes = level["nodes"][:_MAX_PER_ROW]
            for col, n in enumerate(level_nodes):
                local_id = f"mig-{n['id']}"
                add_node(local_id, n["label"], n["type"], row, col, direction=n.get("direction"))
                chain_id_map[n["id"]] = local_id
                if n["type"] == "sector":
                    sector_row_by_label[n["label"].lower()] = row
                parent_real_id = n.get("parent_id")
                parent_local = chain_id_map.get(parent_real_id, "q")
                add_edge(parent_local, local_id, "impacts")
            row += 1

    # ── Companies (the "Leaders" the spec asks for) — attached to a
    # matching sector node from the real chain when one resolved, else
    # directly under the query (same fallback the old shallow graph used). ──
    company_row = row
    company_ids: dict[str, str] = {}
    for i, c in enumerate(companies_enriched[:5]):
        sym = c.get("symbol")
        if not sym:
            continue
        cid = add_node(f"co-{sym}", sym, "company", company_row, i, impact_score=c.get("impact_score"))
        company_ids[sym] = cid
        sector = _sector_for(sym)
        parent = "q"
        if sector and sector.lower() in sector_row_by_label:
            # Find the actual local id of that sector node at its row.
            for n in nodes:
                if n["type"] == "sector" and n["label"].lower() == sector.lower():
                    parent = n["id"]
                    break
        add_edge(parent, cid, "involves")
    if company_ids:
        row = company_row + 1

    # ── Competitors — real same-industry peers, one hop past each leader. ──
    competitor_row = row
    col = 0
    existing_symbols = {c.get("symbol") for c in companies_enriched if c.get("symbol")}
    for sym, cid in list(company_ids.items())[:3]:
        for peer in _competitors_for(sym, existing_symbols, limit=1):
            pid = add_node(f"comp-{peer['symbol']}", peer["symbol"], "competitor", competitor_row, col)
            add_edge(cid, pid, "competes_with")
            col += 1
    if col > 0:
        row = competitor_row + 1

    # ── Historical precedents — real matches from Historical Memory. ──────
    hist_row = row
    for i, h in enumerate(similar_historical[:3]):
        title = h.get("event_title") or h.get("title") or "Historical event"
        hid = add_node(f"hist-{i}", title, "historical", hist_row, i)
        add_edge("q", hid, "echoes")
    if similar_historical[:3]:
        row = hist_row + 1

    # ── Risks / opportunities — real fields this response already has. ───
    # Attributed to whichever company's own name/symbol the text actually
    # names (found live: "BEL's EVM contract delays" was linking from HAL
    # just because HAL happened to be first in the list) — falls back to
    # the first company only when the text doesn't name one specifically.
    default_target = next(iter(company_ids.values()), "q")

    def _attribute(text: str) -> str:
        for c in companies_enriched[:5]:
            sym, name = c.get("symbol"), c.get("name") or ""
            first_word = name.split()[0] if name else ""
            if sym and sym in company_ids and (sym.lower() in text.lower() or (len(first_word) > 3 and first_word.lower() in text.lower())):
                return company_ids[sym]
        return default_target

    ro_row = row
    for i, r in enumerate(risks[:2]):
        rid = add_node(f"risk-{i}", r[:40] + ("…" if len(r) > 40 else ""), "risk", ro_row, i)
        add_edge(_attribute(r), rid, "threatens")
    for i, o in enumerate(opportunities[:2]):
        oid = add_node(f"opp-{i}", o[:40] + ("…" if len(o) > 40 else ""), "opportunity", ro_row, i + 2)
        add_edge(_attribute(o), oid, "enables")

    # V2's own shape (RippleLevel[]) — V3 never populated this field at
    # all before this (only nodes/edges), silently leaving the existing
    # frontend "hasRipple"/"View Ripple Graph" affordance permanently off
    # for every V3 response. Exposing it costs nothing extra: `chain` is
    # the exact same real traversal already computed above.
    return {"nodes": nodes, "edges": edges, "ripple_chain": chain}
