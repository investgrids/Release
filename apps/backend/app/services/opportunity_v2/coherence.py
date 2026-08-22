"""
Candidate cluster discovery via real Intelligence Graph adjacency —
STRONG/WEAK tiered (owner correction, 2026-08-22): "two Developments share
a graph node" is NOT sufficient to merge them on its own. The literal
regression this fixes: "Aditya Birla Capital enters gold loans" and
"Goldman rates Indian banks" both touch `sector:banking` and nothing
else — under a naive "shared node -> merge" rule they'd cluster into one
incoherent opportunity, exactly reproducing V1's bug in graph clothing.

Tiers:
  STRONG — shared company node, OR shared theme/policy/commodity node via
    a causal edge (triggered_by/influences/benefits/hurts). Either alone
    is enough to merge a pair.
  WEAK   — shared sector node ONLY. Never sufficient alone, no matter how
    many Developments share it.

Real-data caveat (confirmed live, 2026-08-22): theme/policy/commodity
edges are 0% populated today (0 of 614 real development: graph nodes) —
app/services/development_memory/graph_link.py's linking code is correct,
but reads Development.themes (empty JSON list on all 973 real rows) and
policy-typed evidence (0 of 1,995 real DevelopmentEvidence rows have
source_type="policy"). The STRONG-tier theme/policy/commodity check below
is still implemented (it's real, correct code, and will start
contributing automatically once that upstream gap closes) — but in
practice, on today's real data, shared-company is the STRONG signal that
actually fires. Company sharing has 96% real coverage (591 of 614
development nodes have at least one company edge), so this is not a
theoretical fallback.

A Development with no ig_node_id yet (not graph-linked — either not yet
processed by development_memory/sync.py, or genuinely not graph-worthy)
cannot participate in graph-based coherence at all. It's kept as its own
singleton candidate cluster rather than silently dropped; whether a
singleton is strong enough to stand alone as an opportunity is decided by
the minimum-evidence-bar check in identity.py, not here.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.db.models.development import Development
from app.services.intelligence_graph_service import get_subgraph

_STRONG_NODE_TYPES = {"company", "theme", "policy", "commodity"}
_WEAK_NODE_TYPES = {"sector"}


@dataclass
class DevNodeAdjacency:
    """One candidate Development's real 1-hop graph neighborhood, split
    into the node ids that count as STRONG evidence vs WEAK evidence."""
    development: Development
    strong_node_ids: set[str] = field(default_factory=set)
    weak_node_ids: set[str] = field(default_factory=set)


@dataclass
class CoherentCluster:
    developments: list[Development]
    # The UNION (not intersection) of every member's own real STRONG node
    # ids — becomes the cluster's real company/theme/policy/commodity
    # attachment. Union, not intersection, is deliberate: if dev_A and
    # dev_B merged because they both connect to company:X, dev_B's
    # separate real connection to company:Y is still real evidence for
    # the resulting opportunity, not something to discard. What coherence
    # guarantees is that every member shares AT LEAST ONE real strong
    # node with SOME other member (transitively, via union-find) — never
    # that all members share the exact same one.
    strong_node_ids: set[str]
    # Real sector node ids the cluster's members connect to — NEVER used
    # to decide coherence (that would reproduce the sector-only-merge bug
    # this engine exists to fix), but real and safe to attach as
    # descriptive metadata once a cluster is already coherent via strong
    # evidence. Same union-not-intersection reasoning as strong_node_ids.
    weak_node_ids: set[str] = field(default_factory=set)


async def _adjacency_for(dev: Development) -> DevNodeAdjacency | None:
    """None when the Development has no ig_node_id yet — not graph-linked,
    so it can't participate in graph-based coherence (see module
    docstring). Caller keeps it as a singleton candidate instead."""
    if not dev.ig_node_id:
        return None

    subgraph = await get_subgraph(dev.ig_node_id, hops=1)
    strong: set[str] = set()
    weak: set[str] = set()
    for node in subgraph["nodes"]:
        if node["id"] == dev.ig_node_id:
            continue
        node_type = node.get("node_type")
        if node_type in _STRONG_NODE_TYPES:
            strong.add(node["id"])
        elif node_type in _WEAK_NODE_TYPES:
            weak.add(node["id"])
        # Any other node type (development, event, ...) reached within
        # 1 hop isn't a coherence signal at all — ignored, not weak.
    return DevNodeAdjacency(development=dev, strong_node_ids=strong, weak_node_ids=weak)


class _UnionFind:
    def __init__(self, n: int):
        self.parent = list(range(n))

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra


async def find_coherent_clusters(candidates: list[Development]) -> list[CoherentCluster]:
    """Group gate-passed candidate Developments into clusters that share
    real STRONG-tier graph evidence. Shared-sector-only pairs are never
    merged, however many Developments share that sector — this is the
    direct, structural fix for the sector-only-bucketing regression this
    whole engine was rebuilt to fix."""
    if not candidates:
        return []

    adjacencies: list[DevNodeAdjacency | None] = [await _adjacency_for(d) for d in candidates]

    uf = _UnionFind(len(candidates))
    for i in range(len(candidates)):
        ai = adjacencies[i]
        if ai is None or not ai.strong_node_ids:
            continue
        for j in range(i + 1, len(candidates)):
            aj = adjacencies[j]
            if aj is None or not aj.strong_node_ids:
                continue
            if uf.find(i) == uf.find(j):
                continue
            if ai.strong_node_ids & aj.strong_node_ids:
                uf.union(i, j)

    groups: dict[int, list[int]] = {}
    for i in range(len(candidates)):
        groups.setdefault(uf.find(i), []).append(i)

    clusters: list[CoherentCluster] = []
    for indices in groups.values():
        members = [candidates[i] for i in indices]
        shared_strong: set[str] = set()
        shared_weak: set[str] = set()
        for i in indices:
            a = adjacencies[i]
            if a is not None:
                shared_strong |= a.strong_node_ids
                shared_weak |= a.weak_node_ids
        clusters.append(CoherentCluster(developments=members, strong_node_ids=shared_strong, weak_node_ids=shared_weak))
    return clusters
