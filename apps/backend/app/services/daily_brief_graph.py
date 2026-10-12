"""Exposure facts for the Daily Brief, read from the app's own knowledge graph (ig_nodes / ig_edges) instead of hand-written tables.

The graph already holds macro-variable -> sector edges (for example commodity:crude-oil -hurts-> sector:airlines) with a weight, a
confidence, a typical lag and a written rationale. This module only (1) loads those edges, (2) says which graph node speaks for each market
variable the brief tracks, and (3) turns an edge into 'pressured' or 'helped' for the move that happened (edges are written for an increase
of the variable, so a fall inverts them).

Nothing here decides a sector's exposure. If the graph has no edge, the brief shows no exposure for that variable.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field

import structlog

log = structlog.get_logger(__name__)

# Which graph node speaks for each tracked market variable, and whether its edges must be inverted for this direction of move.
# 'yields' are covered by the RBI rate-hike / rate-cut policy nodes: the graph has no bond-yield node, so this is the closest recorded
# sensitivity (financing conditions tightening or easing), and the exposure row says so.
VARIABLE_NODES: dict[str, tuple[str, bool]] = {
    "rupee_weaker": ("currency:usd-inr", False),
    "rupee_stronger": ("currency:usd-inr", True),
    "crude_rising": ("commodity:crude-oil", False),
    "crude_falling": ("commodity:crude-oil", True),
    "yields_rising": ("policy:rbi-rate-hike", False),
    "yields_falling": ("policy:rbi-rate-cut", False),
}
MACRO_NODES = sorted({node for node, _ in VARIABLE_NODES.values()})
TOP_PER_SIDE = 6
_TTL_SECONDS = 3600


@dataclass(frozen=True)
class Edge:
    sector_id: str
    sector: str
    edge_type: str            # 'hurts' | 'benefits' (as written, for an increase of the variable)
    weight: float | None
    confidence: float | None
    lag_days: int | None
    why: str | None


@dataclass
class GraphContext:
    edges: dict[str, list[Edge]] = field(default_factory=dict)       # macro node id -> sector edges
    node_labels: dict[str, str] = field(default_factory=dict)        # macro node id -> label
    sector_vocabulary: list[str] = field(default_factory=list)       # sector labels the graph uses (for reading headlines)
    loaded_at: float = 0.0

    def exposure(self, variable: str) -> dict | None:
        """{'pressured': [...], 'helped': [...], 'node_id', 'node_label', 'inverted', 'basis'} for a tracked variable, or None."""
        spec = VARIABLE_NODES.get(variable)
        if not spec:
            return None
        node_id, invert = spec
        edges = self.edges.get(node_id) or []
        if not edges:
            return None
        pressured, helped = [], []
        for e in sorted(edges, key=lambda x: -(x.weight or 0)):
            hurts = (e.edge_type == "hurts") != invert
            item = {"sector": e.sector, "sector_id": e.sector_id, "weight": e.weight, "confidence": e.confidence, "lag_days": e.lag_days, "why": e.why,
                    "edge": e.edge_type}
            (pressured if hurts else helped).append(item)
        label = self.node_labels.get(node_id) or node_id
        return {"pressured": pressured[:TOP_PER_SIDE], "helped": helped[:TOP_PER_SIDE], "node_id": node_id, "node_label": label, "inverted": invert,
                "basis": f"Knowledge graph: {label} edges to sectors" + (" (inverted for this direction of move)" if invert else "")}

    def affected_labels(self, node_id: str, limit: int = 5) -> list[str]:
        """Sector labels most strongly tied to a macro node, either direction, strongest first."""
        edges = sorted(self.edges.get(node_id) or [], key=lambda x: -(x.weight or 0))
        return [e.sector for e in edges][:limit]


def _clean_label(label: str | None) -> str | None:
    if not label:
        return None
    n = re.sub(r"[^a-z0-9& ]+", " ", label.lower()).strip()
    if len(n) < 2 or n.startswith("all") or n in ("others", "other", "general", "market", "markets"):
        return None
    return label.strip()


_cache: dict[str, object] = {"ctx": None, "at": 0.0}


async def load_graph_context(force: bool = False) -> GraphContext | None:
    """The macro exposure edges and the sector vocabulary, cached for an hour (the graph changes slowly). None when the graph is unreadable."""
    now = time.time()
    if not force and _cache["ctx"] is not None and now - float(_cache["at"]) < _TTL_SECONDS:
        return _cache["ctx"]  # type: ignore[return-value]
    try:
        from sqlalchemy import select
        from app.db.models.intelligence_graph import IGEdge, IGNode
        from app.db.session import AsyncSessionLocal
        async with AsyncSessionLocal() as db:
            rows = (await db.execute(
                select(IGEdge.source_id, IGEdge.target_id, IGEdge.edge_type, IGEdge.weight, IGEdge.confidence, IGEdge.lag_days, IGEdge.description)
                .where(IGEdge.source_id.in_(MACRO_NODES), IGEdge.edge_type.in_(("hurts", "benefits")), IGEdge.target_id.like("sector:%"))
            )).all()
            ids = {r.target_id for r in rows} | set(MACRO_NODES)
            labels = dict((await db.execute(select(IGNode.id, IGNode.label).where(IGNode.id.in_(ids)))).all())
            vocab_rows = (await db.execute(
                select(IGNode.label).join(IGEdge, IGEdge.target_id == IGNode.id)
                .where(IGNode.node_type == "sector", ~IGEdge.source_id.like("development:%")).distinct()
            )).all()
        ctx = GraphContext(loaded_at=now)
        for r in rows:
            sector = labels.get(r.target_id) or r.target_id.split(":", 1)[-1].replace("-", " ").title()
            ctx.edges.setdefault(r.source_id, []).append(Edge(r.target_id, sector, r.edge_type, r.weight, r.confidence, r.lag_days, r.description))
        ctx.node_labels = {n: labels[n] for n in MACRO_NODES if n in labels}
        ctx.sector_vocabulary = sorted({c for (lbl,) in vocab_rows if (c := _clean_label(lbl))})
        _cache["ctx"], _cache["at"] = ctx, now
        return ctx
    except Exception as exc:  # noqa: BLE001
        log.warning("daily_brief_graph.load_failed", error=str(exc)[:200])
        return None
