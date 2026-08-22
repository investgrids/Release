"""
Thesis identity — the real merge key for OpportunityV2, NEVER the
AI-generated title (owner correction, 2026-08-22: a single Development
can legitimately support several distinct theses — an RBI rate cut
supports a Banking-margin opportunity AND a Real-Estate-demand
opportunity, genuinely different theses, not duplicates of each other —
so "this Development is already linked to an Opportunity" cannot be the
merge signal on its own; only a matching thesis_anchor + thesis_direction
means "this is the same investable idea").

Two real anchor paths, chosen by what's actually populated in real data
(confirmed live, 2026-08-22): a graph-anchored path using the cluster's
own real coherence.py output (preferred — ties identity directly to the
real shared node that made the cluster coherent in the first place,
robust even when members' individual primary_company fields disagree),
and a raw-field fallback for clusters with no real graph anchor at all
(singleton, not-yet-graph-linked candidates).
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.development import Development
from app.db.models.opportunity_v2 import OpportunityV2
from app.services.development_memory.identity import _net_direction
from app.services.opportunity_v2.coherence import CoherentCluster


@dataclass
class ThesisIdentity:
    anchor: str
    direction: str


def compute_thesis_identity(cluster: CoherentCluster) -> ThesisIdentity | None:
    """None only when the cluster has neither a real graph anchor nor any
    usable raw Development field to anchor on at all — an honest "cannot
    form a thesis identity" rather than a fabricated placeholder."""
    directions = [
        d.current_direction or d.formation_direction
        for d in cluster.developments
        if (d.current_direction or d.formation_direction)
    ]
    direction = _net_direction(directions) or "neutral"

    anchor = _pick_graph_anchor(cluster.strong_node_ids) or _pick_raw_anchor(cluster.developments)
    if anchor is None:
        return None
    return ThesisIdentity(anchor=anchor, direction=direction)


def _pick_graph_anchor(strong_node_ids: set[str]) -> str | None:
    """Prefer a real company node (the most specific, best-populated real
    anchor — 96% of graph-linked Developments have one) over a theme/
    policy/commodity node. Deterministic (sorted) so the same cluster
    always picks the same anchor across repeated runs, never an
    arbitrary set-iteration-order choice."""
    companies = sorted(n for n in strong_node_ids if n.startswith("company:"))
    if companies:
        return companies[0]
    drivers = sorted(n for n in strong_node_ids if n.startswith(("theme:", "policy:", "commodity:")))
    if drivers:
        return drivers[0]
    return None


def _pick_raw_anchor(developments: list[Development]) -> str | None:
    """Fallback for a cluster with no real graph anchor (not yet
    graph-linked). This path is only ever reached for a genuine singleton
    cluster — coherence.py's union-find only merges two Developments when
    their real strong_node_ids intersect, so any cluster with more than
    one member already has a non-empty strong_node_ids and would have
    been anchored by _pick_graph_anchor above.

    No sector fallback (removed 2026-08-22, confirmed live): sector alone
    is WEAK-tier and must never be sufficient to merge two Developments —
    that's the whole point of the coherence tiering. A sector-keyed raw
    anchor broke that guarantee at the identity layer instead: two
    company-less "Banking" singletons ("Aditya Birla Capital enters gold
    loan market" and "Goldman rates Indian banks" — the literal reported
    regression) both fell back to `raw_sector:banking` and
    find_matching_open_opportunity silently merged them, reproducing the
    exact bug this engine exists to fix. Anchoring on the Development's
    own id instead is still stable across repeated runs over the same
    Development (so reruns update, not duplicate) but can never collide
    with an unrelated one."""
    for d in developments:
        if d.primary_company:
            return f"raw_company:{d.primary_company.strip().upper()}"
    if developments:
        return f"raw_dev:{developments[0].id}"
    return None


async def find_matching_open_opportunity(db: AsyncSession, identity: ThesisIdentity) -> OpportunityV2 | None:
    """The real merge-vs-create check — an open OpportunityV2 with the
    exact same (thesis_anchor, thesis_direction). Direction is part of
    the match key deliberately: a positive Banking thesis and a negative
    Banking thesis anchored on the same node are not the same investable
    idea and must never merge."""
    return (await db.execute(
        select(OpportunityV2).where(
            OpportunityV2.thesis_anchor == identity.anchor,
            OpportunityV2.thesis_direction == identity.direction,
            OpportunityV2.status == "open",
        )
    )).scalar_one_or_none()
