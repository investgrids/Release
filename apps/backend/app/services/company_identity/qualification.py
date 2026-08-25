"""
C4 — intelligence-rich qualification. Answers one question per company:
does MarketRipple actually have real evidence about it, from a real
source, right now? Not a score, not a weighted heuristic — a company
either has >=1 real signal from an existing intelligence system or it
doesn't. Two real, already-existing sources, checked directly (no new
data invented for this):

  graph_edges   — real relationships in the now-cleaned Intelligence
                  Graph (post-C3: no duplicate-inflated or misclassified
                  counts), resolved through Company Master so an old or
                  provider-variant ticker on a graph node still counts.
  ai_signals    — real AICompanySignal rows: a company mentioned in a
                  published IntelligenceArticle's companies_affected[], or
                  linked via a real Opportunity's per-company data (see
                  company_score_engine.py's own extraction functions).

Owner's own framing: "qualify using actual intelligence/evidence, not a
fixed count" and "thresholds should come from the real available fields —
we shouldn't invent arbitrary scores now." This module does exactly that:
qualified = (graph_edges >= 1) OR (ai_signals >= 1). No weighting, no
invented cutoff beyond ">=1 real signal exists."
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.company_entity import CompanyEntity
from app.db.models.company_signal import AICompanySignal
from app.services.company_identity.coverage import find_missing_intelligence_rich_companies


@dataclass
class QualificationResult:
    entity_id: str
    symbol: str
    company_name: str
    graph_edge_count: int
    ai_signal_count: int

    @property
    def qualified(self) -> bool:
        return self.graph_edge_count > 0 or self.ai_signal_count > 0


async def qualify_missing_companies(db: AsyncSession) -> list[QualificationResult]:
    """Real evidence check layered on top of coverage.py's live missing-
    company list. Every candidate coverage.py returns already has
    graph_edge_count computed; this adds the second real source
    (AICompanySignal) and returns the full, transparent picture rather
    than silently pre-filtering."""
    candidates = await find_missing_intelligence_rich_companies(db)
    if not candidates:
        return []

    symbols = [c.symbol for c in candidates]
    signal_rows = (await db.execute(
        select(AICompanySignal.symbol, func.count()).where(AICompanySignal.symbol.in_(symbols)).group_by(AICompanySignal.symbol)
    )).all()
    signal_counts = dict(signal_rows)

    return [
        QualificationResult(
            entity_id=c.entity_id, symbol=c.symbol, company_name=c.company_name,
            graph_edge_count=c.graph_edge_count, ai_signal_count=signal_counts.get(c.symbol, 0),
        )
        for c in candidates
    ]


async def qualified_missing_companies(db: AsyncSession) -> list[QualificationResult]:
    """The actual C4 exposure list — only real evidence-backed companies."""
    all_results = await qualify_missing_companies(db)
    return [r for r in all_results if r.qualified]


async def resolve_entity_by_any_symbol(db: AsyncSession, raw_symbol: str) -> CompanyEntity | None:
    """The Company-read-path resolution step: given any symbol a request
    arrives with (current, historical, or a known vendor variant), find
    the real CompanyEntity it belongs to via the C2 resolver — never a
    fuzzy match. Returns None (not a guess) if nothing resolves."""
    from app.services.company_identity.resolver import resolve_identifier, ResolutionStatus

    result = await resolve_identifier(db, raw_symbol)
    if result.status != ResolutionStatus.RESOLVED or not result.entity_id:
        return None
    return await db.get(CompanyEntity, result.entity_id)
