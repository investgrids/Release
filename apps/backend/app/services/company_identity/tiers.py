"""
C5 — coverage/indexability tiers. Answers: which Company Master entities
deserve a public/indexable page, and why? Deterministic tiers from real,
already-available fields — no invented quality score.

  A — Intelligence Rich: real MarketRipple intelligence about the
      company, from >=1 of three real, already-established sources,
      each individually gated against being a single weak/noise signal:
        - Graph relationships: >=2 real ig_edges (a lone edge can be a
          single auto-added, low-confidence artifact -- the same class
          of noise C3 spent a whole pass cleaning up; two or more
          distinct real relationships is a much stronger substance bar)
        - AICompanySignal: >=1 (already inherently substantive -- it
          only exists because a real published article's
          companies_affected[] or a real Opportunity's per-company data
          named this company; there's no "weak" AICompanySignal the way
          there's a weak auto-added graph edge)
        - Real V2 Opportunity linkage: >=1 (OpportunityV2.companies is
          only populated by the real, deterministic, evidence-gated
          formation pipeline -- see opportunity_v2/orchestration.py --
          never a placeholder)
  B — Data Rich: not A, but real, live, retrievable market data exists
      (batch yfinance price fetch -- the same real mechanism
      companies.py already uses for the directory's live prices) --
      proves an active, real market identity with real data to show,
      even without MarketRipple-specific intelligence yet.
  C — Identity Only: a valid, real Company Master entity, but neither
      real MarketRipple intelligence nor confirmed live market data.
      Resolvable (Company Master knows it exists), never indexed.

Historical/renamed identities (old_symbol/provider_symbol aliases) are
NOT a 4th entity tier -- an alias doesn't own a page, it's a real,
sourced pointer to whichever entity the CURRENT symbol resolves to (see
resolver.py). Their handling rule is a real 301 redirect to the
canonical URL, tracked separately (see alias_redirect_summary() below),
not mixed into the A/B/C entity classification.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.company_entity import CompanyEntity, CompanyAlias
from app.db.models.company_signal import AICompanySignal
from app.db.models.intelligence_graph import IGNode, IGEdge
from app.db.models.opportunity_v2 import OpportunityV2
from app.services.company_identity.coverage import _entity_graph_edge_counts

_MIN_MEANINGFUL_GRAPH_EDGES = 2


class CoverageTier(str, Enum):
    A_INTELLIGENCE_RICH = "A"
    B_DATA_RICH = "B"
    C_IDENTITY_ONLY = "C"


@dataclass
class TierResult:
    entity_id: str
    symbol: str
    company_name: str
    tier: CoverageTier
    graph_edge_count: int
    ai_signal_count: int
    v2_opportunity_count: int
    has_live_market_data: bool | None  # None = not checked (Tier A short-circuits the live check)
    public_page: bool
    indexable: bool
    sitemap: bool
    reasons: list[str] = field(default_factory=list)


async def _entity_ai_signal_counts(db: AsyncSession, symbols: list[str]) -> dict[str, int]:
    if not symbols:
        return {}
    rows = (await db.execute(
        select(AICompanySignal.symbol, func.count()).where(AICompanySignal.symbol.in_(symbols)).group_by(AICompanySignal.symbol)
    )).all()
    return dict(rows)


async def _entity_v2_opportunity_counts(db: AsyncSession) -> dict[str, int]:
    """Real V2 Opportunity company linkage — OpportunityV2.companies is a
    JSON list, only ever populated by the real, deterministic formation
    pipeline. Counted regardless of public_status (shadow vs public):
    a company being graph-confirmed into a real, evidence-formed
    opportunity is real MarketRipple intelligence about that company
    even before the opportunity itself is publicly promoted."""
    rows = (await db.execute(select(OpportunityV2.companies))).scalars().all()
    counts: dict[str, int] = {}
    for companies in rows:
        for symbol in (companies or []):
            sym = str(symbol).upper()
            counts[sym] = counts.get(sym, 0) + 1
    return counts


def _batch_has_live_price(symbols: list[str]) -> dict[str, bool]:
    """Real, cheap proxy for Tier B — the same batch yfinance mechanism
    companies.py's directory already uses for live prices, chunked so a
    single call never carries an unbounded symbol list."""
    from app.api.companies import _fetch_prices_sync

    result: dict[str, bool] = {s: False for s in symbols}
    chunk_size = 150
    for i in range(0, len(symbols), chunk_size):
        chunk = symbols[i:i + chunk_size]
        prices = _fetch_prices_sync(chunk)
        for s in chunk:
            result[s] = s in prices
    return result


async def classify_all_entities(db: AsyncSession, *, check_live_data: bool = True, sample_limit: int | None = None) -> list[TierResult]:
    """Classifies every real Company Master entity. `sample_limit` bounds
    the expensive live-price check (Tier B/C split) to a real, honest
    sample rather than every non-A entity — used for a fast reconciliation
    pass; the mechanism itself works at full scale, this only bounds cost
    for this session's report. Every entity outside the sample is
    reported as Tier C without a live check having been made for it
    (never silently assumed Tier B)."""
    entities = (await db.execute(select(CompanyEntity))).scalars().all()
    graph_edges = await _entity_graph_edge_counts(db)
    ai_signals = await _entity_ai_signal_counts(db, [e.symbol for e in entities])
    v2_counts = await _entity_v2_opportunity_counts(db)

    results: list[TierResult] = []
    non_a_symbols: list[str] = []
    for entity in entities:
        ge = graph_edges.get(entity.entity_id, 0)
        ai = ai_signals.get(entity.symbol, 0)
        v2 = v2_counts.get(entity.symbol.upper(), 0)

        reasons = []
        is_a = False
        if ge >= _MIN_MEANINGFUL_GRAPH_EDGES:
            is_a = True
            reasons.append(f"{ge} real graph relationships (>= {_MIN_MEANINGFUL_GRAPH_EDGES})")
        if ai >= 1:
            is_a = True
            reasons.append(f"{ai} real AICompanySignal(s) (published article/Opportunity)")
        if v2 >= 1:
            is_a = True
            reasons.append(f"connected to {v2} real V2 Opportunity(ies)")

        if is_a:
            results.append(TierResult(
                entity_id=entity.entity_id, symbol=entity.symbol, company_name=entity.company_name,
                tier=CoverageTier.A_INTELLIGENCE_RICH, graph_edge_count=ge, ai_signal_count=ai,
                v2_opportunity_count=v2, has_live_market_data=None,
                public_page=True, indexable=True, sitemap=True, reasons=reasons,
            ))
        else:
            non_a_symbols.append(entity.symbol)
            results.append(TierResult(
                entity_id=entity.entity_id, symbol=entity.symbol, company_name=entity.company_name,
                tier=CoverageTier.C_IDENTITY_ONLY, graph_edge_count=ge, ai_signal_count=ai,
                v2_opportunity_count=v2, has_live_market_data=None,
                public_page=False, indexable=False, sitemap=False,
                reasons=["no real graph/AI-signal/V2-opportunity evidence found"],
            ))

    if check_live_data and non_a_symbols:
        checked = non_a_symbols[:sample_limit] if sample_limit else non_a_symbols
        live_data = _batch_has_live_price(checked)
        by_symbol = {r.symbol: r for r in results}
        for sym, has_data in live_data.items():
            r = by_symbol[sym]
            r.has_live_market_data = has_data
            if has_data:
                r.tier = CoverageTier.B_DATA_RICH
                r.public_page = True
                r.indexable = True  # per owner's table: B indexes "if content gate passes" -- the live-data check itself IS that gate here
                r.sitemap = True
                r.reasons = ["real, live-retrievable market data (yfinance), no MarketRipple-specific intelligence yet"]

    return results


def summarize(results: list[TierResult]) -> dict[str, Any]:
    from collections import Counter
    tier_counts = Counter(r.tier.value for r in results)
    checked = sum(1 for r in results if r.has_live_market_data is not None or r.tier == CoverageTier.A_INTELLIGENCE_RICH)
    return {
        "total_entities": len(results),
        "tier_A": tier_counts.get("A", 0),
        "tier_B": tier_counts.get("B", 0),
        "tier_C": tier_counts.get("C", 0),
        "live_data_checked_count": sum(1 for r in results if r.has_live_market_data is not None),
        "live_data_unchecked_count": sum(1 for r in results if r.tier == CoverageTier.C_IDENTITY_ONLY and r.has_live_market_data is None),
        "public_page_count": sum(1 for r in results if r.public_page),
        "indexable_count": sum(1 for r in results if r.indexable),
        "sitemap_count": sum(1 for r in results if r.sitemap),
        "internal_only_count": sum(1 for r in results if not r.public_page),
    }


async def classify_one(db: AsyncSession, symbol: str) -> TierResult | None:
    """Real, single-symbol classification for a per-page SEO decision
    (Company redesign Batch 0) — unlike classify_all_entities(), a live
    price check for ONE symbol is cheap enough to include directly (the
    cost problem C5 flagged was ~1,800 symbols in one request, not one).
    Returns None only when the symbol doesn't resolve to a real
    CompanyEntity at all (never guessed, never fabricated)."""
    from app.services.company_identity.qualification import resolve_entity_by_any_symbol

    entity = await resolve_entity_by_any_symbol(db, symbol)
    if entity is None:
        return None

    own_symbols = {entity.symbol.upper()}
    alias_rows = (await db.execute(
        select(CompanyAlias.alias_value).where(CompanyAlias.entity_id == entity.entity_id)
    )).scalars().all()
    own_symbols |= {v.upper() for v in alias_rows}

    from app.services.company_identity.classifier import normalize_identifier
    nodes = (await db.execute(select(IGNode).where(IGNode.node_type == "company"))).scalars().all()
    node_ids = [
        n.id for n in nodes
        if normalize_identifier(n.ticker or n.id.split(":", 1)[-1]) in own_symbols
    ]

    ge = 0
    if node_ids:
        out_c = (await db.execute(select(func.count()).select_from(IGEdge).where(IGEdge.source_id.in_(node_ids)))).scalar_one()
        in_c = (await db.execute(select(func.count()).select_from(IGEdge).where(IGEdge.target_id.in_(node_ids)))).scalar_one()
        ge = out_c + in_c

    ai = (await db.execute(select(func.count()).select_from(AICompanySignal).where(AICompanySignal.symbol == entity.symbol))).scalar_one()

    v2_rows = (await db.execute(select(OpportunityV2.companies))).scalars().all()
    v2 = sum(1 for companies in v2_rows if entity.symbol.upper() in {str(c).upper() for c in (companies or [])})

    reasons = []
    if ge >= _MIN_MEANINGFUL_GRAPH_EDGES:
        reasons.append(f"{ge} real graph relationships")
    if ai >= 1:
        reasons.append(f"{ai} real AICompanySignal(s)")
    if v2 >= 1:
        reasons.append(f"connected to {v2} real V2 Opportunity(ies)")

    if reasons:
        return TierResult(
            entity_id=entity.entity_id, symbol=entity.symbol, company_name=entity.company_name,
            tier=CoverageTier.A_INTELLIGENCE_RICH, graph_edge_count=ge, ai_signal_count=ai,
            v2_opportunity_count=v2, has_live_market_data=None,
            public_page=True, indexable=True, sitemap=True, reasons=reasons,
        )

    has_live = bool(_batch_has_live_price([entity.symbol]).get(entity.symbol))
    if has_live:
        return TierResult(
            entity_id=entity.entity_id, symbol=entity.symbol, company_name=entity.company_name,
            tier=CoverageTier.B_DATA_RICH, graph_edge_count=ge, ai_signal_count=ai,
            v2_opportunity_count=v2, has_live_market_data=True,
            public_page=True, indexable=True, sitemap=True,
            reasons=["real, live-retrievable market data, no MarketRipple-specific intelligence yet"],
        )

    return TierResult(
        entity_id=entity.entity_id, symbol=entity.symbol, company_name=entity.company_name,
        tier=CoverageTier.C_IDENTITY_ONLY, graph_edge_count=ge, ai_signal_count=ai,
        v2_opportunity_count=v2, has_live_market_data=False,
        public_page=False, indexable=False, sitemap=False,
        reasons=["no real graph/AI-signal/V2-opportunity evidence, no live market data found"],
    )


async def alias_redirect_summary(db: AsyncSession) -> dict[str, Any]:
    """Real counts for the historical-alias / redirect side of the
    reconciliation — separate from the A/B/C entity tiers (see module
    docstring for why). `unresolved_conflicts` is real, not carried over
    from C3's Graph-node classification (a different concept): an alias
    VALUE that currently (valid_to IS NULL, or no dated validity at all)
    points at more than one distinct entity_id — the exact condition
    resolver.py's CONFLICT status guards against at lookup time."""
    total_aliases = (await db.execute(select(func.count()).select_from(CompanyAlias))).scalar_one()
    by_type_rows = (await db.execute(
        select(CompanyAlias.alias_type, func.count()).group_by(CompanyAlias.alias_type)
    )).all()
    by_type = dict(by_type_rows)
    redirect_types = ("old_symbol", "provider_symbol")
    canonical_redirects = sum(by_type.get(t, 0) for t in redirect_types)

    current_rows = (await db.execute(
        select(CompanyAlias.alias_value, CompanyAlias.entity_id).where(CompanyAlias.valid_to.is_(None))
    )).all()
    value_to_entities: dict[str, set[str]] = {}
    for value, entity_id in current_rows:
        value_to_entities.setdefault(value, set()).add(entity_id)
    conflicts = {v: sorted(e) for v, e in value_to_entities.items() if len(e) > 1}

    return {
        "total_aliases": total_aliases,
        "by_type": by_type,
        "canonical_redirects": canonical_redirects,
        "unresolved_conflicts": len(conflicts),
        "conflict_sample": dict(list(conflicts.items())[:10]),
    }
