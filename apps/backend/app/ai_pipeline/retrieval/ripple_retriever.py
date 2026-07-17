"""
Ripple Retriever — resolves the query's primary entity to an intelligence-
graph node, infers a rise/fall direction from the query's own wording
("if crude oil falls" -> "fall"), and runs the real BFS ripple propagation
(`intelligence_graph_service.ripple_from_node`) to find downstream impacted
entities with polarity and accumulated weight.
"""
from __future__ import annotations

import re

from app.ai_pipeline.contracts import Evidence
from app.ai_pipeline.registry import RETRIEVER_REGISTRY
from app.ai_pipeline.retrieval.base import RetrievalContext, RetrieverSpec
from app.ai_pipeline.retrieval.entity_resolver import resolve_entities
from app.services.intelligence_graph_service import ripple_from_node

_FALL_RE = re.compile(r"\b(falls?|falling|drops?|declin\w*|cuts?|lower|down|crash\w*|slump\w*)\b", re.IGNORECASE)
_RISE_RE = re.compile(r"\b(rises?|rising|increas\w*|hikes?|higher|up|surges?|rally\w*)\b", re.IGNORECASE)


def _infer_change(query: str) -> str:
    if _FALL_RE.search(query):
        return "fall"
    if _RISE_RE.search(query):
        return "rise"
    return "rise"   # neutral default — direction affects polarity sign, not which nodes are reachable


async def _fetch(ctx: RetrievalContext) -> list[Evidence]:
    # Only graph-backed entities have a real node_id BFS can traverse from —
    # a universe-only match (a known company with no graph node yet) has
    # nothing to propagate through.
    entities = [e for e in await resolve_entities(ctx.query, limit=5) if e.get("in_graph")]
    if not entities:
        return []

    source_node = entities[0]
    change = _infer_change(ctx.query)

    try:
        result = await ripple_from_node(source_node["id"], change=change, max_depth=5)
    except Exception:
        return []

    if not result.get("source"):
        return []

    evidence: list[Evidence] = []
    for impact in result.get("impacts", [])[:12]:
        node = impact.get("node", {})
        direction = impact.get("impact_direction", "uncertain")
        polarity = {"positive": "positive", "negative": "negative"}.get(direction, "uncertain")
        weight = abs(float(impact.get("accumulated_weight", 0) or 0))
        evidence.append(Evidence(
            id=f"ripple:{source_node['id']}:{node.get('id')}",
            source="ripple",
            entity=node.get("ticker") or node.get("label"),
            claim=(
                f"{node.get('label')} is {direction}ly affected if {source_node['label']} {change}s "
                f"({impact.get('description', '')})".strip()
            ),
            polarity=polarity,
            magnitude=min(weight, 1.0),
            confidence=min(max(weight, 0.3), 0.85),
            timestamp=None,
            raw=impact,
        ))

    return evidence


RETRIEVER_REGISTRY.register("ripple")(RetrieverSpec(key="ripple", fetch=_fetch, timeout_s=12.0))
