"""
Graph migration PLAN generator — read-only. Produces a report of what
*would* happen to every existing `ig_nodes` company node if the Graph were
migrated onto the Company Master, without touching the Graph at all.

Owner's explicit instruction (C2 scope): "Don't immediately merge/delete
the 30 duplicate nodes or reclassify the 48 false companies... Instead
produce a migration plan." This module is that plan. Graph cleanup itself
is deliberately a separate, later stage.

    old graph node -> resolver -> canonical entity_id -> action

Actions:
  OK          resolves to exactly one real entity, no duplicate siblings —
              nothing to do.
  MERGE       resolves to a real entity that >=1 OTHER graph node also
              resolves to — these nodes are the same real company and
              should eventually collapse into one.
  RECLASSIFY  the node's own ticker/id classifies as NOT a company
              (index/commodity/fx/bond/unknown) — node_type='company' is
              wrong on this row.
  UNRESOLVED  classifies as company-shaped but doesn't match anything in
              the Company Master yet (either the Master doesn't have this
              company at all, or it's a real symbol mismatch the Master's
              aliases don't cover yet) — needs either a Master addition or
              a sourced alias, not a guess.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.intelligence_graph import IGNode
from app.services.company_identity.classifier import normalize_identifier
from app.services.company_identity.resolver import resolve_identifier, ResolutionStatus


@dataclass
class MigrationPlanRow:
    node_id: str
    label: str
    ticker: str | None
    action: str
    entity_id: str | None = None
    identifier_type: str | None = None
    merge_with: tuple[str, ...] = ()


@dataclass
class MigrationPlan:
    rows: list[MigrationPlanRow] = field(default_factory=list)

    def summary(self) -> dict[str, Any]:
        counts: dict[str, int] = defaultdict(int)
        for r in self.rows:
            counts[r.action] += 1
        merge_clusters = defaultdict(list)
        for r in self.rows:
            if r.action == "MERGE" and r.entity_id:
                merge_clusters[r.entity_id].append(r.node_id)
        return {
            "total_nodes": len(self.rows),
            "by_action": dict(counts),
            "merge_clusters": {eid: nodes for eid, nodes in merge_clusters.items()},
            "merge_cluster_count": len(merge_clusters),
        }


async def build_graph_migration_plan(db: AsyncSession) -> MigrationPlan:
    nodes = (await db.execute(
        select(IGNode).where(IGNode.node_type == "company")
    )).scalars().all()

    resolved: list[tuple[IGNode, Any]] = []
    for node in nodes:
        raw = node.ticker or node.id.split(":", 1)[-1]
        result = await resolve_identifier(db, raw)
        resolved.append((node, result))

    entity_to_nodes: dict[str, list[str]] = defaultdict(list)
    for node, result in resolved:
        if result.status == ResolutionStatus.RESOLVED and result.entity_id:
            entity_to_nodes[result.entity_id].append(node.id)

    plan = MigrationPlan()
    for node, result in resolved:
        raw = node.ticker or node.id.split(":", 1)[-1]
        if result.status == ResolutionStatus.NOT_A_COMPANY:
            plan.rows.append(MigrationPlanRow(
                node_id=node.id, label=node.label, ticker=node.ticker,
                action="RECLASSIFY", identifier_type=result.identifier_type.value,
            ))
        elif result.status == ResolutionStatus.RESOLVED:
            siblings = tuple(n for n in entity_to_nodes[result.entity_id] if n != node.id)
            action = "MERGE" if siblings else "OK"
            plan.rows.append(MigrationPlanRow(
                node_id=node.id, label=node.label, ticker=node.ticker,
                action=action, entity_id=result.entity_id,
                identifier_type=result.identifier_type.value, merge_with=siblings,
            ))
        else:  # UNRESOLVED or CONFLICT — both need human/sourced attention, not a silent pick
            plan.rows.append(MigrationPlanRow(
                node_id=node.id, label=node.label, ticker=node.ticker,
                action="UNRESOLVED" if result.status == ResolutionStatus.UNRESOLVED else "CONFLICT",
                identifier_type=result.identifier_type.value,
                merge_with=result.candidate_entity_ids if result.status == ResolutionStatus.CONFLICT else (),
            ))

    return plan
