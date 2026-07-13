"""Market Intelligence Graph API — /api/graph/*"""
from __future__ import annotations

import structlog
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

log = structlog.get_logger(__name__)
router = APIRouter()


@router.get("/full")
async def get_full_graph():
    """All nodes + edges for graph visualisation. Cached 5 min."""
    from app.services.intelligence_graph_service import get_full_graph
    return await get_full_graph()


@router.get("/subgraph/{node_id:path}")
async def get_subgraph(node_id: str, hops: int = Query(2, ge=1, le=4)):
    """N-hop undirected neighbourhood around a node."""
    from app.services.intelligence_graph_service import get_subgraph
    return await get_subgraph(node_id, hops)


@router.get("/ripple/{node_id:path}")
async def get_ripple(
    node_id: str,
    change: str = Query("rise", description="rise | fall | shock"),
    max_depth: int = Query(5, ge=1, le=8),
):
    """
    BFS ripple analysis from a source node.

    change=rise  → entity increases / strengthens  (e.g. crude oil rises)
    change=fall  → entity decreases / weakens       (e.g. crude oil falls)
    change=shock → large-magnitude shock (same direction as rise but wider cascade)
    """
    if change not in ("rise", "fall", "shock"):
        raise HTTPException(400, "change must be 'rise', 'fall', or 'shock'")
    from app.services.intelligence_graph_service import ripple_from_node
    return await ripple_from_node(node_id, change, max_depth)


@router.get("/stats")
async def get_stats():
    """Node and edge counts by type."""
    from app.services.intelligence_graph_service import get_full_graph
    from collections import Counter
    g = await get_full_graph()
    return {
        "total_nodes":   len(g["nodes"]),
        "total_edges":   len(g["edges"]),
        "nodes_by_type": dict(Counter(n["node_type"] for n in g["nodes"])),
        "edges_by_type": dict(Counter(e["edge_type"] for e in g["edges"])),
    }


# ── Write endpoints ───────────────────────────────────────────────────────────

class NodeIn(BaseModel):
    node_type: str
    label: str
    ticker: str | None = None
    description: str | None = None
    extra: dict = {}
    auto_added: bool = False


class EdgeIn(BaseModel):
    source_id: str
    target_id: str
    edge_type: str
    weight: float = 0.7
    confidence: float = 0.8
    lag_days: int = 0
    description: str | None = None
    source_event: str | None = None
    auto_added: bool = False


@router.post("/node")
async def upsert_node_endpoint(body: NodeIn):
    from app.services.intelligence_graph_service import upsert_node, NODE_TYPES
    if body.node_type not in NODE_TYPES:
        raise HTTPException(400, f"node_type must be one of: {sorted(NODE_TYPES)}")
    node_id = await upsert_node(
        body.node_type, body.label, body.ticker,
        body.description, body.extra, body.auto_added,
    )
    return {"id": node_id}


@router.post("/edge")
async def upsert_edge_endpoint(body: EdgeIn):
    from app.services.intelligence_graph_service import upsert_edge, EDGE_TYPES
    if body.edge_type not in EDGE_TYPES:
        raise HTTPException(400, f"edge_type must be one of: {sorted(EDGE_TYPES)}")
    edge_id = await upsert_edge(
        body.source_id, body.target_id, body.edge_type,
        body.weight, body.confidence, body.lag_days,
        body.description, body.source_event, body.auto_added,
    )
    return {"id": edge_id}
