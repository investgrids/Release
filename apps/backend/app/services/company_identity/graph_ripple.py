"""
Company Ripple tab (redesign Batch 4) — resolves a real company symbol to
its real Intelligence Graph node, then serves the real, already-existing
subgraph traversal (intelligence_graph_service.get_subgraph), scoped to
that company. Never falls back to AI generation or sector templates —
/api/ripple/company/{ticker} (ripple_service.py) was traced and found to
do exactly that (source: "ai_generated" or "fallback_template"), which is
disqualified for this surface: a Company Ripple tab reads as evidence-
backed market structure, so anything shown here must be a real IGEdge row,
never an invented one.

Distinguishes four real states, so "no verified relationships yet" (real
company, no graph coverage) is never presented the same as "not a real
company" or "the graph service is down":
  no_entity  — the symbol doesn't resolve to a real Company Master entity
  no_node    — entity is real, but the Graph has no company node for it
  no_edges   — a real node exists, but has zero real relationships
  has_edges  — real, evidence-backed relationships exist
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.intelligence_graph import IGNode, IGEdge
from app.db.models.company_entity import CompanyEntity
from app.services.company_identity.qualification import resolve_entity_by_any_symbol
from app.services.company_identity.resolver import resolve_identifier, ResolutionStatus


@dataclass
class CompanyRippleResult:
    status: str  # "no_entity" | "no_node" | "no_edges" | "has_edges"
    canonical_symbol: str | None = None
    company_name: str | None = None
    node_id: str | None = None
    nodes: list[dict[str, Any]] = field(default_factory=list)
    edges: list[dict[str, Any]] = field(default_factory=list)


async def resolve_company_graph_node(db: AsyncSession, entity: CompanyEntity) -> IGNode | None:
    """Real reverse lookup: which IGNode (if any) represents this already-
    resolved Company Master entity? Checks every company node's real
    `ticker` field against the same resolver coverage.py's forward
    direction already uses (node.ticker -> resolve_identifier ->
    entity_id) -- never a name/slug guess. When more than one node
    resolves to the same entity (a real pre-C3-merge duplicate the Graph
    migration hasn't reached for this company), picks the richest by real
    edge count, the same tie-break graph_migration_executor.py's
    _choose_canonical() already uses -- not an arbitrary first match."""
    nodes = (await db.execute(select(IGNode).where(IGNode.node_type == "company"))).scalars().all()
    matches: list[IGNode] = []
    for node in nodes:
        raw = node.ticker or node.id.split(":", 1)[-1]
        result = await resolve_identifier(db, raw)
        if result.status == ResolutionStatus.RESOLVED and result.entity_id == entity.entity_id:
            matches.append(node)

    if not matches:
        return None
    if len(matches) == 1:
        return matches[0]

    node_ids = [m.id for m in matches]
    out_counts = dict((await db.execute(
        select(IGEdge.source_id, func.count()).where(IGEdge.source_id.in_(node_ids)).group_by(IGEdge.source_id)
    )).all())
    in_counts = dict((await db.execute(
        select(IGEdge.target_id, func.count()).where(IGEdge.target_id.in_(node_ids)).group_by(IGEdge.target_id)
    )).all())
    return max(matches, key=lambda n: out_counts.get(n.id, 0) + in_counts.get(n.id, 0))


async def get_company_ripple(db: AsyncSession, raw_symbol: str, hops: int = 2) -> CompanyRippleResult:
    entity = await resolve_entity_by_any_symbol(db, raw_symbol)
    if entity is None:
        return CompanyRippleResult(status="no_entity")

    node = await resolve_company_graph_node(db, entity)
    if node is None:
        return CompanyRippleResult(status="no_node", canonical_symbol=entity.symbol, company_name=entity.company_name)

    from app.services.intelligence_graph_service import get_subgraph
    sub = await get_subgraph(node.id, hops=hops)
    edges = sub.get("edges", [])
    if not edges:
        return CompanyRippleResult(
            status="no_edges", canonical_symbol=entity.symbol, company_name=entity.company_name, node_id=node.id,
        )

    return CompanyRippleResult(
        status="has_edges", canonical_symbol=entity.symbol, company_name=entity.company_name, node_id=node.id,
        nodes=sub.get("nodes", []), edges=edges,
    )
