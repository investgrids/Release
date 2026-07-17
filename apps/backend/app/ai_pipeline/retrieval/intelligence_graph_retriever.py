"""
Intelligence Graph Retriever — resolves the query's entity to a graph node
and surfaces its immediate N-hop neighborhood (`get_subgraph`). This is
broader, non-directional relationship context — "what connects to this
entity" — distinct from `ripple_retriever`'s directional propagation
("what happens downstream if this entity moves").
"""
from __future__ import annotations

from app.ai_pipeline.contracts import Evidence
from app.ai_pipeline.registry import RETRIEVER_REGISTRY
from app.ai_pipeline.retrieval.base import RetrievalContext, RetrieverSpec
from app.ai_pipeline.retrieval.entity_resolver import resolve_entities
from app.services.intelligence_graph_service import get_subgraph

_EDGE_POLARITY = {
    "benefits": "positive", "supports": "positive", "stimulates": "positive", "boosts": "positive",
    "hurts": "negative", "damages": "negative", "pressures": "negative", "risk_factor": "negative",
}


async def _fetch(ctx: RetrievalContext) -> list[Evidence]:
    # get_subgraph needs a real node_id — universe-only matches (a known
    # company with no graph node yet) have no neighborhood to walk.
    entities = [e for e in await resolve_entities(ctx.query, limit=5) if e.get("in_graph")]
    if not entities:
        return []

    center = entities[0]
    try:
        sub = await get_subgraph(center["id"], hops=2)
    except Exception:
        return []

    nodes_by_id = {n["id"]: n for n in sub.get("nodes", [])}
    edges = sub.get("edges", [])
    if not edges:
        return []

    evidence: list[Evidence] = []
    for edge in edges[:12]:
        other_id = edge["target"] if edge["source"] == center["id"] else edge["source"]
        other = nodes_by_id.get(other_id)
        if not other or other_id == center["id"]:
            continue
        weight = abs(float(edge.get("weight", 0.5) or 0.5))
        evidence.append(Evidence(
            id=f"intelligence_graph:{edge.get('id')}",
            source="intelligence_graph",
            entity=other.get("ticker") or other.get("label"),
            claim=f"{center['label']} {edge.get('edge_type', 'relates to')} {other.get('label')}",
            polarity=_EDGE_POLARITY.get(edge.get("edge_type"), "neutral"),
            magnitude=min(weight, 1.0),
            confidence=min(max(float(edge.get("confidence", 0.6) or 0.6), 0.0), 1.0),
            timestamp=None,
            raw=edge,
        ))

    return evidence


RETRIEVER_REGISTRY.register("intelligence_graph")(
    RetrieverSpec(key="intelligence_graph", fetch=_fetch, timeout_s=12.0)
)
