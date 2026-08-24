"""
The real V2 pipeline, wired end to end:

  list open Developments (broad — NOT development_memory/read.py's
  list_active_developments(), which pre-filters by is_graph_worthy(); see
  gate.py's own docstring on why that must stay a separate question)
    -> gate.is_opportunity_evidence_worthy() per Development
    -> coherence.find_coherent_clusters() (real IG adjacency, STRONG/WEAK
       tiered — sector-only never merges)
    -> identity.compute_thesis_identity() (never the AI title)
    -> identity.find_matching_open_opportunity() -> UPDATE vs CREATE
    -> link Developments (idempotent — a rerun over the same data must
       never create a duplicate link)
    -> scoring.score_cluster() (bounded, real inputs only)
    -> persist the deterministic fields FIRST
    -> generation.generate_narrative() LAST — a failure here never
       un-persists the deterministic candidate; it only leaves
       narrative_status="failed_capacity" (owner instruction, 2026-08-22:
       generation success must be independent from candidate persistence,
       so this app's real, currently degraded free-tier AI capacity never
       hides whether the deterministic engine formed the right thesis).

Runs entirely against real production Developments/graph/company-score
data — this module writes only to opportunities_v2/
opportunity_v2_developments (source="opportunity_v2_shadow",
public_status="shadow"). V1's tables, worker, and public read path are
never touched by anything in this module.
"""
from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.development import Development
from app.db.models.intelligence_graph import IGNode
from app.db.models.opportunity_v2 import OpportunityV2, OpportunityV2Development
from app.services.opportunity_v2.coherence import CoherentCluster, find_coherent_clusters
from app.services.opportunity_v2.gate import is_opportunity_evidence_worthy
from app.services.opportunity_v2.generation import generate_narrative
from app.services.opportunity_v2.identity import compute_thesis_identity, find_matching_open_opportunity
from app.services.opportunity_v2.scoring import score_cluster
from app.services.opportunity_v2.slugs import compute_opportunity_slug

log = structlog.get_logger(__name__)

_DEFAULT_LIMIT = 200


@dataclass
class CandidateOutcome:
    action: str  # "created" | "updated" | "rejected_no_identity"
    opportunity_id: str | None = None
    thesis_anchor: str | None = None
    thesis_direction: str | None = None
    development_ids: list[str] = field(default_factory=list)
    development_titles: list[str] = field(default_factory=list)
    new_development_ids: list[str] = field(default_factory=list)
    sectors: list[str] = field(default_factory=list)
    companies: list[str] = field(default_factory=list)
    score: float | None = None
    narrative_status: str | None = None
    title: str | None = None
    narrative_reused: bool = False  # True = skipped generation, unchanged narrative_input_hash (zero LLM call)


@dataclass
class PassSummary:
    developments_considered: int = 0
    developments_gate_passed: int = 0
    clusters_formed: int = 0
    opportunities_created: int = 0
    opportunities_updated: int = 0
    rejected_no_identity: int = 0
    narrative_generated: int = 0
    narrative_failed: int = 0
    narrative_reused: int = 0  # LLM calls avoided this pass via narrative_input_hash
    outcomes: list[CandidateOutcome] = field(default_factory=list)


async def _fetch_open_developments(db: AsyncSession, since: datetime | None, limit: int) -> list[Development]:
    """Deliberately broader than development_memory/read.py's
    list_active_developments() — no is_graph_worthy() pre-filter (see
    gate.py's module docstring for why those must stay independent
    questions). This module's own is_opportunity_evidence_worthy() is the
    only gate applied here."""
    stmt = select(Development).where(Development.status == "open")
    if since is not None:
        stmt = stmt.where(Development.last_observed_at >= since)
    stmt = stmt.order_by(Development.last_observed_at.desc()).limit(limit)
    return (await db.execute(stmt)).scalars().all()


async def _resolve_companies_and_sectors(
    db: AsyncSession, strong_node_ids: set[str], weak_node_ids: set[str],
) -> tuple[list[str], list[str]]:
    """Real IGNode.ticker/label for the cluster's real graph connections —
    never each member Development's own self-reported tags (that blind
    union was V1's confirmed bug)."""
    all_ids = list(strong_node_ids | weak_node_ids)
    if not all_ids:
        return [], []
    nodes = (await db.execute(select(IGNode).where(IGNode.id.in_(all_ids)))).scalars().all()
    companies = sorted({n.ticker for n in nodes if n.node_type == "company" and n.ticker})
    sectors = sorted({n.label for n in nodes if n.node_type == "sector" and n.label})
    return companies, sectors


def _narrative_input_hash(
    developments: list[Development], companies: list[str], sectors: list[str],
    thesis_anchor: str, thesis_direction: str,
) -> str:
    """Deterministic fingerprint of everything that actually feeds the
    narrative prompt (owner instruction, 2026-08-22: same hash must mean
    zero LLM call). Built only from real fields already computed upstream
    — sorted so member/company/sector ORDER never changes the hash, only
    genuine content differences do."""
    parts = [
        thesis_anchor, thesis_direction,
        "|".join(sorted(companies)),
        "|".join(sorted(sectors)),
        "|".join(sorted(d.canonical_title for d in developments)),
    ]
    raw = "\x01".join(parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


async def _link_developments(db: AsyncSession, opportunity_id: str, developments: list[Development], now: datetime) -> list[str]:
    """Idempotent — a rerun over the same cluster must never create a
    duplicate link (relied on by the "repeated runs update, not
    duplicate" check). Returns the ids of developments that were NEWLY
    linked this call, so the caller can decide whether new evidence
    justifies regenerating the narrative."""
    existing_ids = set((await db.execute(
        select(OpportunityV2Development.development_id).where(OpportunityV2Development.opportunity_id == opportunity_id)
    )).scalars().all())

    new_ids: list[str] = []
    for dev in developments:
        if dev.id in existing_ids:
            continue
        db.add(OpportunityV2Development(opportunity_id=opportunity_id, development_id=dev.id, added_at=now))
        new_ids.append(dev.id)
    if new_ids:
        await db.commit()
    return new_ids


async def _fetch_linked_developments(db: AsyncSession, opportunity_id: str) -> list[Development]:
    """The opportunity's FULL cumulative evidence — every Development ever
    linked to it, not just the ones in this pass's cluster. Needed because
    a Development that merged in an earlier pass can later close and drop
    out of _fetch_open_developments' candidate pool entirely; without this,
    both the narrative and its hash would silently lose that Development's
    evidence on the very next pass (confirmed live, 2026-08-22: 5 of 31
    real opportunities in one frozen-input test regenerated their
    narrative purely because an already-linked Development had closed and
    vanished from the current cluster, even though nothing about the
    opportunity's real evidence had changed from the opportunity's own
    point of view)."""
    dev_ids = (await db.execute(
        select(OpportunityV2Development.development_id).where(OpportunityV2Development.opportunity_id == opportunity_id)
    )).scalars().all()
    if not dev_ids:
        return []
    return (await db.execute(select(Development).where(Development.id.in_(dev_ids)))).scalars().all()


async def _process_cluster(db: AsyncSession, cluster: CoherentCluster, now: datetime) -> CandidateOutcome:
    identity = compute_thesis_identity(cluster)
    if identity is None:
        return CandidateOutcome(
            action="rejected_no_identity",
            development_ids=[d.id for d in cluster.developments],
            development_titles=[d.canonical_title for d in cluster.developments],
        )

    companies, sectors = await _resolve_companies_and_sectors(db, cluster.strong_node_ids, cluster.weak_node_ids)
    breakdown = await score_cluster(db, cluster.developments, identity.direction, companies, sectors, now)

    existing = await find_matching_open_opportunity(db, identity)
    action = "updated" if existing is not None else "created"

    if existing is not None:
        opp = existing
    else:
        opp = OpportunityV2(
            id=str(uuid.uuid4()), thesis_anchor=identity.anchor, thesis_direction=identity.direction,
            status="open", source="opportunity_v2_shadow",
            candidate_status="formed", narrative_status="pending", public_status="shadow",
            formation_score=breakdown.total, formation_at=now,
        )
        db.add(opp)

    opp.current_score = breakdown.total
    # Persisted exactly alongside current_score (owner correction,
    # 2026-08-23: a GET request must never reconstruct different
    # reasoning than the score it's displaying was actually computed
    # from — see read_service.py, which serves these fields as-is,
    # never a live recomputation).
    opp.score_breakdown = {
        "evidence_quality": breakdown.evidence_quality,
        "development_count": breakdown.development_count,
        "company_confirmation": breakdown.company_confirmation,
        "sector_confirmation": breakdown.sector_confirmation,
        "freshness": breakdown.freshness,
        "contradiction_penalty": breakdown.contradiction_penalty,
        "company_signals": breakdown.company_signals,
    }
    opp.contradictions = breakdown.contradictions
    opp.sectors = sectors
    opp.companies = companies
    opp.updated_at = now
    await db.commit()

    new_dev_ids = await _link_developments(db, opp.id, cluster.developments, now)

    # Hash and narrative are built from the opportunity's FULL cumulative
    # linked-Development set (see _fetch_linked_developments docstring),
    # never just this pass's transient cluster — a Development that
    # merged in an earlier pass and later closed must not silently vanish
    # from the narrative just because it dropped out of this pass's
    # candidate pool.
    all_linked_devs = await _fetch_linked_developments(db, opp.id)

    # Regenerate narrative only when the evidence/thesis payload actually
    # changed since the last SUCCESSFUL generation (owner instruction,
    # 2026-08-22: same narrative_input_hash must mean zero LLM call — a
    # worker running repeatedly in production must not re-spend a paid
    # call on an opportunity whose evidence hasn't materially moved). A
    # prior failed_capacity attempt always retries regardless of hash,
    # since capacity may have recovered and no narrative exists yet.
    new_hash = _narrative_input_hash(all_linked_devs, companies, sectors, identity.anchor, identity.direction)
    should_generate = (
        action == "created"
        or opp.narrative_status != "generated"
        or opp.narrative_input_hash != new_hash
    )
    narrative_reused = not should_generate
    if should_generate:
        evidence_text = " ".join(d.canonical_title for d in all_linked_devs)
        narrative = await generate_narrative(evidence_text, sectors, companies)
        if narrative is not None:
            opp.current_title = narrative.title
            opp.current_summary = narrative.summary
            opp.narrative_status = "generated"
            opp.narrative_input_hash = new_hash
            if opp.formation_title is None:
                opp.formation_title = narrative.title
        else:
            opp.narrative_status = "failed_capacity"
            # Deliberately NOT storing new_hash here — see docstring above.
        await db.commit()

    # Assigned once, on whichever pass first creates this row, from the
    # best real title info available at that point (never regenerated
    # afterward — see OpportunityV2.slug's own column comment).
    if opp.slug is None:
        slug_base = opp.current_title or opp.formation_title or identity.anchor
        opp.slug = compute_opportunity_slug(opp.id, slug_base)
        await db.commit()

    return CandidateOutcome(
        action=action, opportunity_id=opp.id, thesis_anchor=identity.anchor, thesis_direction=identity.direction,
        development_ids=[d.id for d in cluster.developments], development_titles=[d.canonical_title for d in cluster.developments],
        new_development_ids=new_dev_ids, sectors=sectors, companies=companies,
        score=breakdown.total, narrative_status=opp.narrative_status, title=opp.current_title,
        narrative_reused=narrative_reused,
    )


async def run_shadow_pass(db: AsyncSession, since: datetime | None = None, limit: int = _DEFAULT_LIMIT) -> PassSummary:
    """One real end-to-end pass. Writes only to opportunities_v2/
    opportunity_v2_developments — never touches V1's tables, and nothing
    written here is served by any public read path."""
    now = datetime.now(timezone.utc)
    all_devs = await _fetch_open_developments(db, since, limit)
    candidates = [d for d in all_devs if is_opportunity_evidence_worthy(d)]
    clusters = await find_coherent_clusters(candidates)

    summary = PassSummary(
        developments_considered=len(all_devs),
        developments_gate_passed=len(candidates),
        clusters_formed=len(clusters),
    )

    for cluster in clusters:
        try:
            outcome = await _process_cluster(db, cluster, now)
        except Exception as exc:
            log.warning("opportunity_v2.orchestration.cluster_failed", error=str(exc)[:200],
                        development_ids=[d.id for d in cluster.developments])
            continue

        summary.outcomes.append(outcome)
        if outcome.action == "created":
            summary.opportunities_created += 1
        elif outcome.action == "updated":
            summary.opportunities_updated += 1
        else:
            summary.rejected_no_identity += 1

        if outcome.narrative_reused:
            summary.narrative_reused += 1
        elif outcome.narrative_status == "generated":
            summary.narrative_generated += 1
        elif outcome.narrative_status == "failed_capacity":
            summary.narrative_failed += 1

    return summary
