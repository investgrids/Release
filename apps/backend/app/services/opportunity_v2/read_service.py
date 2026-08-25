"""
V2 Promotion Blocker Remediation, Batch B/C — the real V2 read contract.

Deliberately NOT a port of V1's OpportunityDetailResponse
(app/schemas/opportunity_detail.py). V1's confidence/risk_level/trend/
time_horizon/revenue_potential/expected_cagr/eps_growth/market_size/
timeline/sector_distribution(donut)/graph_nodes+graph_edges(fake star
topology)/per-company impact_score+reason are all either fabricated
formulas or concepts V2 was deliberately built without (see the
promotion-readiness audit's §10-§16, and the owner's own "don't
recreate confidence yet" instruction, 2026-08-23). Every field below
traces to something OpportunityV2/scoring.py/coherence.py/identity.py
already, genuinely, computed and persisted.

Nothing here recomputes score/company-confirmation live — it serves
exactly what orchestration.py::_process_cluster persisted at write
time (score_breakdown/contradictions/companies/sectors), so a GET
response can never show reasoning that's drifted from the score it's
displaying (owner correction, 2026-08-23).

Batch E will add v1_adapter/OpportunityReadService here too, once the
4 dependent backend consumers (related.py/sectors.py/
weekend_intelligence.py/ai_search/pipeline.py) are wired — not yet.
"""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.development import Development, DevelopmentEvidence
from app.db.models.intelligence_graph import IGNode
from app.db.models.opportunity_v2 import OpportunityV2, OpportunityV2Development
from app.services.intelligence_graph_service import get_subgraph


# ── Response schema ─────────────────────────────────────────────────────────

class CompanyConnectedSchema(BaseModel):
    symbol: str
    company_name: str = ""
    real_score: Optional[float] = None
    real_direction: Optional[str] = None       # positive | negative | neutral | None (no real signal)
    confirms_thesis: bool = False
    contradicts_thesis: bool = False


class SupportingEvidenceSchema(BaseModel):
    development_id: str
    canonical_title: str
    evidence_count: int
    current_confidence: Optional[float] = None
    current_impact_tier: Optional[str] = None
    first_observed_at: Optional[str] = None
    source_types: list[str] = []               # real DevelopmentEvidence.source_type values, deduped


class RippleNodeSchema(BaseModel):
    id: str
    node_type: str
    label: str
    ticker: Optional[str] = None


class RippleEdgeSchema(BaseModel):
    id: str
    source: str
    target: str
    edge_type: str
    weight: Optional[float] = None


class RippleSchema(BaseModel):
    anchor: Optional[str] = None                # thesis_anchor, only if it's actually part of the union
    nodes: list[RippleNodeSchema] = []
    edges: list[RippleEdgeSchema] = []


class WhatChangedSchema(BaseModel):
    formation_title: Optional[str] = None
    formation_score: Optional[float] = None
    current_title: Optional[str] = None
    current_score: Optional[float] = None


class OpportunityV2DetailResponse(BaseModel):
    id: str
    slug: str
    title: str                                    # real fallback chain, see get_opportunity_v2_detail
    thesis_anchor: str
    direction: str
    current_strength: Optional[float] = None     # current_score — real, bounded, NEVER relabeled "confidence"
    evidence_count: int = 0

    candidate_status: str
    narrative_status: str
    public_status: str

    why_this_exists: Optional[str] = None         # current_summary, or None if narrative_status=failed_capacity
    what_changed: Optional[WhatChangedSchema] = None

    companies_connected: list[CompanyConnectedSchema] = []
    sectors_themes: list[str] = []
    ripple: RippleSchema = RippleSchema()
    supporting_evidence: list[SupportingEvidenceSchema] = []
    contradictions_risks: list[str] = []

    created_at: str
    updated_at: str


# ── Assembly ─────────────────────────────────────────────────────────────────

async def _fetch_linked_developments(db: AsyncSession, opportunity_id: str) -> list[Development]:
    dev_ids = (await db.execute(
        select(OpportunityV2Development.development_id).where(OpportunityV2Development.opportunity_id == opportunity_id)
    )).scalars().all()
    if not dev_ids:
        return []
    return (await db.execute(select(Development).where(Development.id.in_(dev_ids)))).scalars().all()


async def _build_companies_connected(db: AsyncSession, opp: OpportunityV2) -> list[CompanyConnectedSchema]:
    """From the persisted score_breakdown.company_signals — never a live
    compute_company_score() call (see module docstring)."""
    signals_by_symbol = {}
    if opp.score_breakdown:
        for sig in opp.score_breakdown.get("company_signals", []):
            signals_by_symbol[sig["symbol"]] = sig

    names_by_symbol: dict[str, str] = {}
    if opp.companies:
        nodes = (await db.execute(
            select(IGNode).where(IGNode.node_type == "company", IGNode.ticker.in_(opp.companies))
        )).scalars().all()
        names_by_symbol = {n.ticker: n.label for n in nodes}

    out: list[CompanyConnectedSchema] = []
    for symbol in opp.companies:
        sig = signals_by_symbol.get(symbol, {})
        out.append(CompanyConnectedSchema(
            symbol=symbol,
            company_name=names_by_symbol.get(symbol, ""),
            real_score=sig.get("score"),
            real_direction=sig.get("real_direction"),
            confirms_thesis=sig.get("confirms_thesis", False),
            contradicts_thesis=sig.get("contradicts_thesis", False),
        ))
    return out


async def _build_supporting_evidence(db: AsyncSession, developments: list[Development]) -> list[SupportingEvidenceSchema]:
    if not developments:
        return []
    dev_ids = [d.id for d in developments]
    evidence_rows = (await db.execute(
        select(DevelopmentEvidence).where(DevelopmentEvidence.development_id.in_(dev_ids))
    )).scalars().all()
    source_types_by_dev: dict[str, list[str]] = {}
    for ev in evidence_rows:
        source_types_by_dev.setdefault(ev.development_id, [])
        if ev.source_type not in source_types_by_dev[ev.development_id]:
            source_types_by_dev[ev.development_id].append(ev.source_type)

    return [
        SupportingEvidenceSchema(
            development_id=d.id,
            canonical_title=d.canonical_title,
            evidence_count=d.evidence_count,
            current_confidence=d.current_confidence,
            current_impact_tier=d.current_impact_tier or d.formation_impact_tier,
            first_observed_at=d.first_observed_at.isoformat() if d.first_observed_at else None,
            source_types=source_types_by_dev.get(d.id, []),
        )
        for d in sorted(developments, key=lambda x: x.first_observed_at)
    ]


async def _build_ripple(thesis_anchor: str, developments: list[Development]) -> RippleSchema:
    """Union of each linked Development's own 1-hop real graph
    neighborhood — never a single anchor-node BFS (owner correction,
    2026-08-23). Every node/edge here is by construction reachable from
    at least one real linked Development. Empty for a `raw_company:`/
    `raw_dev:` opportunity with no graph-linked Developments — that's
    correct, never a manufactured star."""
    dev_node_ids = sorted({d.ig_node_id for d in developments if d.ig_node_id})
    if not dev_node_ids:
        return RippleSchema(anchor=None, nodes=[], edges=[])

    nodes_by_id: dict[str, dict[str, Any]] = {}
    edges_by_id: dict[str, dict[str, Any]] = {}
    for node_id in dev_node_ids:
        sub = await get_subgraph(node_id, hops=1)
        for n in sub["nodes"]:
            nodes_by_id[n["id"]] = n
        for e in sub["edges"]:
            edges_by_id[e["id"]] = e

    anchor = thesis_anchor if thesis_anchor in nodes_by_id else None
    return RippleSchema(
        anchor=anchor,
        nodes=[RippleNodeSchema(id=n["id"], node_type=n["node_type"], label=n["label"], ticker=n.get("ticker")) for n in nodes_by_id.values()],
        edges=[RippleEdgeSchema(id=e["id"], source=e["source"], target=e["target"], edge_type=e["edge_type"], weight=e.get("weight")) for e in edges_by_id.values()],
    )


async def get_opportunity_v2_detail(db: AsyncSession, slug: str) -> Optional[OpportunityV2DetailResponse]:
    # Sitemap Truth Audit, 2026-08-24 — this lookup had no public_status
    # filter at all, meaning any shadow-status (unpublished) opportunity
    # would be fully fetchable by anyone who guessed or was given its real
    # slug, bypassing the shadow gate entirely. public_status="public" is
    # the only value that means "promoted, meant to be publicly reachable"
    # per this model's own column comment — shadow rows return the same
    # 404 an unknown slug would (radar.py's caller already maps a None
    # return to HTTPException 404, so this is the only change needed).
    opp = (await db.execute(
        select(OpportunityV2).where(OpportunityV2.slug == slug, OpportunityV2.public_status == "public")
    )).scalar_one_or_none()
    if opp is None:
        return None

    developments = await _fetch_linked_developments(db, opp.id)

    what_changed = None
    if opp.formation_title != opp.current_title or opp.formation_score != opp.current_score:
        what_changed = WhatChangedSchema(
            formation_title=opp.formation_title, formation_score=opp.formation_score,
            current_title=opp.current_title, current_score=opp.current_score,
        )

    why_this_exists = opp.current_summary if opp.narrative_status == "generated" else None

    # V2-A contract alignment, 2026-08-24 — the response had no top-level
    # display title at all (only formation_title/current_title inside
    # what_changed, which is only present once the title has actually
    # changed). The frontend page needs a real title to render regardless
    # of narrative_status. Reuses the exact real fallback chain the model
    # itself already documents (opportunity_v2.py's own column comment) and
    # orchestration.py already uses for slug_base — never a fabricated
    # string, and identical to what this opportunity would already fall
    # back to elsewhere in the codebase.
    title = opp.current_title or opp.formation_title or opp.thesis_anchor

    return OpportunityV2DetailResponse(
        id=opp.id,
        slug=opp.slug,
        title=title,
        thesis_anchor=opp.thesis_anchor,
        direction=opp.thesis_direction,
        current_strength=opp.current_score,
        evidence_count=len(developments),
        candidate_status=opp.candidate_status,
        narrative_status=opp.narrative_status,
        public_status=opp.public_status,
        why_this_exists=why_this_exists,
        what_changed=what_changed,
        companies_connected=await _build_companies_connected(db, opp),
        sectors_themes=opp.sectors,
        ripple=await _build_ripple(opp.thesis_anchor, developments),
        supporting_evidence=await _build_supporting_evidence(db, developments),
        contradictions_risks=opp.contradictions or [],
        created_at=opp.created_at.isoformat(),
        updated_at=opp.updated_at.isoformat(),
    )


# ── List — V2-B, 2026-08-24 ───────────────────────────────────────────────────
# The list capability the sitemap (and, later, any "recent opportunities"
# widget migrated off V1) needs. No V2 list endpoint existed before this —
# every prior consumer of OpportunityV2 was the single-slug detail lookup
# above. Filters on public_status="public" for the exact same reason the
# detail lookup does: a shadow row must never become independently
# reachable, not through a direct slug guess and not through a list either.

class OpportunityV2ListItem(BaseModel):
    id: str
    slug: str
    title: str
    current_strength: Optional[float] = None
    sectors_themes: list[str] = []
    updated_at: str


class PaginatedOpportunitiesV2(BaseModel):
    items: list[OpportunityV2ListItem]
    total: int
    page: int
    page_size: int
    pages: int


async def list_public_opportunities_v2(db: AsyncSession, page: int = 1, page_size: int = 100) -> PaginatedOpportunitiesV2:
    base = select(OpportunityV2).where(OpportunityV2.public_status == "public")
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()

    rows = (await db.execute(
        base.order_by(OpportunityV2.updated_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
    )).scalars().all()

    items = [
        OpportunityV2ListItem(
            id=o.id, slug=o.slug,
            title=o.current_title or o.formation_title or o.thesis_anchor,
            current_strength=o.current_score, sectors_themes=o.sectors or [],
            updated_at=o.updated_at.isoformat(),
        )
        for o in rows
    ]
    pages = max(1, (total + page_size - 1) // page_size)
    return PaginatedOpportunitiesV2(items=items, total=total, page=page, page_size=page_size, pages=pages)


# ── Sector/theme search — Batch E consumer migration, 2026-08-24 ────────────
# V2-native equivalent of OpportunityRepository.list_by_sector_or_theme
# (same real matching strategy: sectors is list-membership, title is a
# length-gated substring match — ported verbatim, not reinvented, so
# search behavior doesn't silently change shape between modes). Real
# fields only in the returned dicts — current_strength/direction, never
# opportunity_score/confidence/risk_level (V2 doesn't have them). Callers
# (ai_search/pipeline.py, ai_search_service.py, ai_search/evidence.py,
# ai_recommendation_engine.py) must read the right keys for the active
# mode — see OpportunityService.list_by_sector_or_theme's dispatch.
async def list_public_opportunities_v2_by_sector_or_theme(db: AsyncSession, terms: list[str], limit: int = 10) -> list[dict]:
    if not terms:
        return []
    terms_lower = [t.lower() for t in terms]
    title_terms = [t for t in terms_lower if len(t) >= 4]

    candidates = (await db.execute(
        select(OpportunityV2)
        .where(OpportunityV2.public_status == "public")
        .order_by(OpportunityV2.current_score.desc())
        .limit(200)
    )).scalars().all()

    def _matches(opp: OpportunityV2) -> bool:
        opp_sectors = [str(s).lower() for s in (opp.sectors or [])]
        if any(t in opp_sectors for t in terms_lower):
            return True
        title = (opp.current_title or opp.formation_title or "").lower()
        return any(t in title for t in title_terms)

    return [
        {
            "id": o.id, "slug": o.slug,
            "title": o.current_title or o.formation_title or o.thesis_anchor,
            "summary": o.current_summary if o.narrative_status == "generated" else None,
            "current_strength": o.current_score, "direction": o.thesis_direction,
            "sectors": o.sectors or [],
        }
        for o in candidates if _matches(o)
    ][:limit]


# ── Company → Opportunity — Batch E consumer migration, 2026-08-24 ──────────
# V2-native equivalent of company_intelligence.py::get_related_opportunities
# (which joins V1's OpportunityCompany junction table). V2 has no such
# junction table — real graph-confirmed companies live on
# OpportunityV2.companies (JSON list, set by orchestration.py at write
# time). SQLite has no portable JSON-containment operator (same reason
# list_by_sector_or_theme's own V1 repository method filters in Python
# rather than DB-side), so this filters a bounded, score-ordered public
# candidate pool in Python too.
async def list_public_opportunities_v2_for_company(db: AsyncSession, symbol: str, limit: int = 3) -> list[dict]:
    symbol_upper = symbol.upper()
    candidates = (await db.execute(
        select(OpportunityV2)
        .where(OpportunityV2.public_status == "public")
        .order_by(OpportunityV2.current_score.desc())
        .limit(200)
    )).scalars().all()

    matches = [o for o in candidates if symbol_upper in [c.upper() for c in (o.companies or [])]]
    return [
        {
            "id": o.id,
            "title": o.current_title or o.formation_title or o.thesis_anchor,
            "href": f"/opportunity-radar/{o.slug}",
            "score": o.current_score,
        }
        for o in matches[:limit]
    ]
