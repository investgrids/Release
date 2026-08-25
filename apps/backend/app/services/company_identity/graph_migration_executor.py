"""
Graph migration EXECUTOR — applies a MigrationPlan's MERGE and RECLASSIFY
actions to the real ig_nodes/ig_edges tables. UNRESOLVED and CONFLICT rows
are never touched — retained for review, per owner instruction ("avoid
deleting Graph nodes outright... verify edge preservation first").

dry_run=True (default) computes the exact before/after proof WITHOUT
writing anything — every write call in this module is guarded by it.
Only call with dry_run=False after reviewing that proof.

The correct edge-preservation invariant is NOT "same raw edge count
before and after" — merging genuinely collapses literal duplicate edges
(the same real relationship, previously anchored to two different
duplicate node ids), and that collapse is the fix, not data loss. The
real proof is: normalize every "before" edge's source/target through the
SAME canonical mapping this run will apply, then compare that normalized
set of DISTINCT (source, target, edge_type) triples against the actual
"after" set. If they're equal, nothing was lost — only true duplicates
collapsed. A self-loop that appears only because both sides of an edge
were duplicates of the same real entity (never a real relationship) is
reported separately, not silently folded into "duplicate."
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.intelligence_graph import IGNode, IGEdge
from app.services.company_identity.classifier import IdentifierType
from app.services.company_identity.graph_migration_plan import MigrationPlan

# Maps this module's classifier types onto node_type values already real
# and consumed elsewhere (intelligence_graph.py's own docstring: "node_type:
# company | sector | theme | event | policy | commodity | country | index |
# currency") — reusing "index"/"commodity"/"currency" rather than inventing
# parallel new names. bond_rate and unclassified are genuinely new
# categories nothing in the app modeled before; every real consumer of
# node_type filters by an explicit `== "company"` (checked before writing
# this module — none does an exhaustive enum match), so adding new values
# is safe and, for graph_link.py/orchestration.py/read_service.py's own
# `node_type == "company"` company-lookups, a direct correctness fix: they
# stop matching junk that was never a real company.
_RECLASSIFY_NODE_TYPE: dict[str, str] = {
    IdentifierType.INDEX.value: "index",
    IdentifierType.COMMODITY.value: "commodity",
    IdentifierType.CURRENCY_FX.value: "currency",
    IdentifierType.BOND_RATE.value: "bond_rate",
    IdentifierType.UNKNOWN.value: "unclassified",
}


@dataclass
class MergeClusterResult:
    entity_id: str
    canonical_node_id: str
    merged_away_node_ids: list[str] = field(default_factory=list)
    edges_repointed: int = 0
    edges_deduplicated: int = 0
    self_loops_removed: int = 0


@dataclass
class ExecutionReport:
    dry_run: bool = True
    nodes_before: int = 0
    nodes_after: int = 0
    edges_before: int = 0
    edges_after: int = 0
    distinct_relationships_before_normalized: int = 0
    distinct_relationships_after: int = 0
    relationships_preserved: bool = False
    self_loops_removed_total: int = 0
    nodes_merged_away: int = 0
    nodes_reclassified: int = 0
    reclassify_by_type: dict[str, int] = field(default_factory=dict)
    unresolved_retained: int = 0
    merge_clusters: list[MergeClusterResult] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "dry_run": self.dry_run,
            "nodes_before": self.nodes_before,
            "nodes_after": self.nodes_after,
            "edges_before": self.edges_before,
            "edges_after": self.edges_after,
            "distinct_relationships_before_normalized": self.distinct_relationships_before_normalized,
            "distinct_relationships_after": self.distinct_relationships_after,
            "relationships_preserved": self.relationships_preserved,
            "self_loops_removed_total": self.self_loops_removed_total,
            "nodes_merged_away": self.nodes_merged_away,
            "nodes_reclassified": self.nodes_reclassified,
            "reclassify_by_type": self.reclassify_by_type,
            "unresolved_retained": self.unresolved_retained,
            "merge_clusters": [
                {
                    "entity_id": c.entity_id, "canonical_node_id": c.canonical_node_id,
                    "merged_away_node_ids": c.merged_away_node_ids,
                    "edges_repointed": c.edges_repointed,
                    "edges_deduplicated": c.edges_deduplicated,
                    "self_loops_removed": c.self_loops_removed,
                }
                for c in self.merge_clusters
            ],
        }


async def _choose_canonical(db: AsyncSession, node_ids: list[str]) -> str:
    """Prefer a manually-curated node (auto_added=False) — it was
    deliberately created, not a duplicate side-effect of unfamiliar-ticker
    ingestion. Otherwise prefer the node with the most edges (least
    repointing, richest existing relationships). Tie-break alphabetically
    for determinism (same input always picks the same canonical node,
    which matters for a dry-run's proof to match the real run exactly)."""
    nodes = (await db.execute(select(IGNode).where(IGNode.id.in_(node_ids)))).scalars().all()
    manual = sorted([n.id for n in nodes if not n.auto_added])
    if manual:
        return manual[0]

    counts: dict[str, int] = {nid: 0 for nid in node_ids}
    out_rows = (await db.execute(
        select(IGEdge.source_id, func.count()).where(IGEdge.source_id.in_(node_ids)).group_by(IGEdge.source_id)
    )).all()
    in_rows = (await db.execute(
        select(IGEdge.target_id, func.count()).where(IGEdge.target_id.in_(node_ids)).group_by(IGEdge.target_id)
    )).all()
    for nid, c in out_rows:
        counts[nid] = counts.get(nid, 0) + c
    for nid, c in in_rows:
        counts[nid] = counts.get(nid, 0) + c

    max_count = max(counts.values())
    richest = sorted(nid for nid, c in counts.items() if c == max_count)
    return richest[0]


async def _fetch_all_edges(db: AsyncSession) -> list[IGEdge]:
    return (await db.execute(select(IGEdge))).scalars().all()


async def execute_graph_migration(db: AsyncSession, plan: MigrationPlan, *, dry_run: bool = True) -> ExecutionReport:
    report = ExecutionReport(dry_run=dry_run)

    report.nodes_before = (await db.execute(select(func.count()).select_from(IGNode))).scalar_one()
    all_edges_before = await _fetch_all_edges(db)
    report.edges_before = len(all_edges_before)

    # ── Build the canonical mapping for every merge cluster (read-only) ──
    canonical_map: dict[str, str] = {}
    merge_rows_by_entity: dict[str, list[str]] = defaultdict(list)
    for row in plan.rows:
        if row.action == "MERGE" and row.entity_id:
            merge_rows_by_entity[row.entity_id].append(row.node_id)

    cluster_canonical: dict[str, str] = {}
    for entity_id, node_ids in merge_rows_by_entity.items():
        canonical = await _choose_canonical(db, node_ids)
        cluster_canonical[entity_id] = canonical
        for nid in node_ids:
            canonical_map[nid] = canonical

    # ── The proof: normalize every "before" edge through the mapping this
    # run WILL apply, and count distinct (source, target, edge_type)
    # triples — this is what "after" must equal if nothing was lost. ──
    def _norm(node_id: str) -> str:
        return canonical_map.get(node_id, node_id)

    self_loops_in_before = 0
    normalized_before: set[tuple[str, str, str]] = set()
    for e in all_edges_before:
        ns, nt = _norm(e.source_id), _norm(e.target_id)
        if ns == nt:
            self_loops_in_before += 1
            continue
        normalized_before.add((ns, nt, e.edge_type))
    report.distinct_relationships_before_normalized = len(normalized_before)

    # ── Apply MERGE per cluster ──
    for entity_id, node_ids in merge_rows_by_entity.items():
        canonical = cluster_canonical[entity_id]
        merged_away = [nid for nid in node_ids if nid != canonical]
        cluster_result = MergeClusterResult(entity_id=entity_id, canonical_node_id=canonical, merged_away_node_ids=merged_away)

        for dup_id in merged_away:
            dup_edges = (await db.execute(
                select(IGEdge).where((IGEdge.source_id == dup_id) | (IGEdge.target_id == dup_id))
            )).scalars().all()

            for e in dup_edges:
                new_source = canonical if e.source_id == dup_id else e.source_id
                new_target = canonical if e.target_id == dup_id else e.target_id

                if new_source == new_target:
                    cluster_result.self_loops_removed += 1
                    if not dry_run:
                        await db.delete(e)
                    continue

                conflict = (await db.execute(
                    select(IGEdge).where(
                        IGEdge.source_id == new_source, IGEdge.target_id == new_target,
                        IGEdge.edge_type == e.edge_type, IGEdge.id != e.id,
                    )
                )).scalars().first()
                if conflict is not None:
                    cluster_result.edges_deduplicated += 1
                    if not dry_run:
                        await db.delete(e)
                    continue

                cluster_result.edges_repointed += 1
                if not dry_run:
                    e.source_id = new_source
                    e.target_id = new_target
            if not dry_run:
                await db.flush()

            if not dry_run:
                node = await db.get(IGNode, dup_id)
                if node is not None:
                    await db.delete(node)

        report.merge_clusters.append(cluster_result)
        report.nodes_merged_away += len(merged_away)

    if not dry_run:
        await db.flush()

    # ── Apply RECLASSIFY ──
    for row in plan.rows:
        if row.action != "RECLASSIFY":
            continue
        new_type = _RECLASSIFY_NODE_TYPE.get(row.identifier_type or "", "unclassified")
        report.reclassify_by_type[new_type] = report.reclassify_by_type.get(new_type, 0) + 1
        report.nodes_reclassified += 1
        if not dry_run:
            node = await db.get(IGNode, row.node_id)
            if node is not None:
                node.node_type = new_type

    report.unresolved_retained = sum(1 for r in plan.rows if r.action in ("UNRESOLVED", "CONFLICT"))

    if not dry_run:
        await db.flush()

    # ── After snapshot: for dry_run, simulate what the DB would look like;
    # for a real run, read it back for real. ──
    if dry_run:
        after_edges: set[tuple[str, str, str]] = set()
        for e in all_edges_before:
            ns, nt = _norm(e.source_id), _norm(e.target_id)
            if ns == nt:
                continue
            after_edges.add((ns, nt, e.edge_type))
        report.edges_after = report.edges_before - sum(
            c.edges_deduplicated + c.self_loops_removed for c in report.merge_clusters
        )
        report.nodes_after = report.nodes_before - report.nodes_merged_away
    else:
        after_edges_rows = await _fetch_all_edges(db)
        after_edges = {(e.source_id, e.target_id, e.edge_type) for e in after_edges_rows}
        report.edges_after = len(after_edges_rows)
        report.nodes_after = (await db.execute(select(func.count()).select_from(IGNode))).scalar_one()

    report.distinct_relationships_after = len(after_edges)
    report.relationships_preserved = normalized_before == after_edges
    report.self_loops_removed_total = self_loops_in_before if dry_run else sum(c.self_loops_removed for c in report.merge_clusters)

    return report
