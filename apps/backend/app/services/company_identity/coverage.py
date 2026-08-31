"""
Dynamic coverage query — replaces C1's hardcoded "462 intelligence-rich
missing companies" with a live query against the real Company Master +
Graph. Owner's explicit instruction: don't carry forward a fixed number,
both sides keep growing (the Graph alone grew from 1,005 to 1,041 company
nodes within a single session during C1/C2).

"Missing" means every real Company Master entity not in the static
`_NSE_UNIVERSE` list the public site actually reads today (companies.py)
— the site's exposure gate hasn't moved yet; only the identity layer
underneath it has. The candidate universe is Company Master itself, not
just the subset the Graph happens to already have a node for — a company
whose only real evidence is an AICompanySignal (no Graph node at all)
must still be visible here, or C4's qualification gate would silently
never see it. Real graph-edge count is computed for every candidate
(0 when the Graph has no node for it) and used to rank by richness, same
methodology as C1.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.intelligence_graph import IGNode, IGEdge
from app.db.models.company_entity import CompanyEntity
from app.services.company_identity.resolver import resolve_identifier, ResolutionStatus


def _static_universe_symbols() -> set[str]:
    from app.api.companies import _NSE_UNIVERSE
    return {c["symbol"].upper() for c in _NSE_UNIVERSE}


@dataclass
class MissingCompanyCandidate:
    entity_id: str
    symbol: str
    company_name: str
    graph_edge_count: int


async def _entity_graph_edge_counts(db: AsyncSession) -> dict[str, int]:
    """Real graph-edge count per resolved entity_id -- a company with no
    Graph node at all simply never appears in this dict; callers must
    default missing entities to 0, not skip them."""
    nodes = (await db.execute(select(IGNode).where(IGNode.node_type == "company"))).scalars().all()

    edge_counts_out = dict((await db.execute(
        select(IGEdge.source_id, func.count()).group_by(IGEdge.source_id)
    )).all())
    edge_counts_in = dict((await db.execute(
        select(IGEdge.target_id, func.count()).group_by(IGEdge.target_id)
    )).all())

    entity_edges: dict[str, int] = {}
    for node in nodes:
        raw = node.ticker or node.id.split(":", 1)[-1]
        result = await resolve_identifier(db, raw)
        if result.status != ResolutionStatus.RESOLVED:
            continue
        edges = edge_counts_out.get(node.id, 0) + edge_counts_in.get(node.id, 0)
        entity_edges[result.entity_id] = entity_edges.get(result.entity_id, 0) + edges
    return entity_edges


async def find_missing_intelligence_rich_companies(db: AsyncSession) -> list[MissingCompanyCandidate]:
    static_symbols = _static_universe_symbols()
    entity_edges = await _entity_graph_edge_counts(db)

    entities = (await db.execute(select(CompanyEntity))).scalars().all()

    candidates: list[MissingCompanyCandidate] = []
    for entity in entities:
        if entity.symbol.upper() in static_symbols:
            continue
        candidates.append(MissingCompanyCandidate(
            entity_id=entity.entity_id, symbol=entity.symbol,
            company_name=entity.company_name, graph_edge_count=entity_edges.get(entity.entity_id, 0),
        ))

    candidates.sort(key=lambda c: -c.graph_edge_count)
    return candidates


async def coverage_summary(db: AsyncSession) -> dict[str, Any]:
    static_symbols = _static_universe_symbols()
    total_entities = (await db.execute(select(func.count()).select_from(CompanyEntity))).scalar_one()
    missing = await find_missing_intelligence_rich_companies(db)
    with_evidence = sum(1 for c in missing if c.graph_edge_count > 0)
    return {
        "static_universe_count": len(static_symbols),
        "total_company_master_entities": total_entities,
        "missing_from_static_count": len(missing),
        "missing_with_real_graph_edge_count": with_evidence,
        "top_20_by_richness": [
            {"symbol": c.symbol, "name": c.company_name, "graph_edges": c.graph_edge_count}
            for c in missing[:20]
        ],
    }
