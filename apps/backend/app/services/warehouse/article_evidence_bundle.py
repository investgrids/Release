"""
ArticleEvidenceBundle — AI Article V2 Phase A (owner decision, 2026-08-29,
following the 7-consumer Warehouse audit). The audit found that none of
AIPE's 11 real article-generation stages are Warehouse-grounded today,
despite the Warehouse capturing the same raw material AIPE's own triage
already consumes. This module is the retrieval boundary Phase A adds: it
resolves a company through the REAL canonical resolver (never the
hardcoded `_NSE_UNIVERSE` list AIPE currently uses — see
company_identity/resolver.py::resolve_identifier, the same one
EvidenceEntityLink itself is built on) and assembles real, traceable
evidence for it.

Explicitly Phase A scope only:
  - Warehouse-linked evidence: real (via read_service.get_evidence_for_entity)
  - Historical context: KEPT AS-IS (real, verified HistoricalMarketEvent —
    the audit found this genuinely real, just not Warehouse-sourced yet;
    expanding it to Warehouse memory is a later pass, not Phase A)
  - Real market price move: reused verbatim from fact_grounding.py
  - Financial facts: Phase B, deliberately not built here
  - MarketRipple Score: deliberately NOT wired in. Two real reasons: (1)
    the owner's own instruction — AIPE must never receive an internal,
    not-yet-publishable score, not even hidden in a prompt, while S5-E is
    running; the article pipeline should eventually consume the same
    public-projection boundary S5-C established
    (marketripple_score/public_projection.py), never a raw snapshot; (2)
    as a plain fact, `marketripple_score` does not exist at all on this
    branch (integration/warehouse-company-master) — it was built on the
    separate company-identity/c1-reconciliation branch, and the two
    haven't been merged. `score` stays None until both are true: the
    branches merge, AND the score has actually passed its own
    publication gate for the company in question.

This module builds the bundle only — it does not write it into any
prompt, generate an article, or touch AIPE's existing pipeline. That's
the next Phase A step (compose_what_happened_from_evidence), still
shadow-only, never wired into production article generation.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.warehouse.read_service import LinkedEvidence, get_evidence_for_entity


@dataclass(frozen=True)
class ArticleEvidenceBundle:
    resolved: bool
    entity_id: str | None
    symbol: str | None
    company_name: str | None
    evidence: list[LinkedEvidence] = field(default_factory=list)
    price_move_pct: float | None = None
    historical_events: list[dict] = field(default_factory=list)
    marketripple_score: None = None  # deliberately always None in Phase A — see module docstring
    built_at: datetime | None = None


async def build_article_evidence_bundle(
    db: AsyncSession, raw_symbol: str, *, include_historical: bool = True, include_price_move: bool = True,
) -> ArticleEvidenceBundle:
    """The one real entry point for Phase A. Resolves `raw_symbol` through
    the canonical Company Identity resolver — never the hardcoded
    `_NSE_UNIVERSE` the current AIPE pipeline uses for the same job — then
    assembles whatever real evidence actually exists. An unresolved symbol
    or a company with zero linked evidence still returns a real, honest
    bundle (resolved=False, or evidence=[]) — never fabricated content."""
    from datetime import datetime as _dt, timezone as _tz
    from app.services.company_identity.qualification import resolve_entity_by_any_symbol

    entity = await resolve_entity_by_any_symbol(db, raw_symbol)
    if entity is None:
        return ArticleEvidenceBundle(
            resolved=False, entity_id=None, symbol=raw_symbol.upper(), company_name=None,
            built_at=_dt.now(_tz.utc),
        )

    evidence = await get_evidence_for_entity(db, entity.entity_id)

    price_move_pct = None
    if include_price_move:
        from app.services.aipe.fact_grounding import fetch_price_moves
        moves = await fetch_price_moves([entity.symbol])
        if moves:
            price_move_pct = moves.get(entity.symbol)

    historical_events: list[dict] = []
    if include_historical and entity.sector:
        from app.services.aipe.market_story_engine import fetch_historical_context
        historical_events = await fetch_historical_context(db, sectors=[entity.sector], keywords=[entity.company_name], limit=3)

    return ArticleEvidenceBundle(
        resolved=True, entity_id=entity.entity_id, symbol=entity.symbol, company_name=entity.company_name,
        evidence=evidence, price_move_pct=price_move_pct, historical_events=historical_events,
        marketripple_score=None, built_at=_dt.now(_tz.utc),
    )


def compose_what_happened_from_evidence(bundle: ArticleEvidenceBundle) -> str | None:
    """Code-composed, never LLM-generated — mirrors the pattern the audit
    already found and praised in comparison_publisher.py's
    compose_what_happened/compose_why_it_matters (code-composed from
    already-real structured fields, not a second free-form LLM call).

    Deliberately narrow: this states only what the real linked evidence
    itself says (title, source, real published date) — it does not
    interpret, does not speculate on causes/effects, and does not invent
    numbers not present in the evidence. That reasoning step ("Why It
    Matters") is explicitly a later, separate stage per the owner's own
    design ("the LLM can turn those verified facts into readable prose ...
    Why It Matters can perform reasoning, but it must reason from those
    facts") — not built in this module.

    Returns None when there's no real evidence to compose from — never a
    fabricated placeholder sentence."""
    if not bundle.resolved or not bundle.evidence:
        return None

    latest = bundle.evidence[0]  # most recent real linked item (query is already DESC by published_at)
    if not latest.title:
        return None

    date_str = latest.published_at.strftime("%d %B %Y") if latest.published_at else "an unspecified date"
    source_label = {"nse": "an NSE regulatory filing", "rss": "a published news report",
                    "rbi": "an RBI release", "pib": "a PIB release", "sebi": "a SEBI release",
                    "fed": "a US Federal Reserve release"}.get(latest.source_type, f"a {latest.source_type} source")

    parts = [f"On {date_str}, {bundle.company_name} was the subject of {source_label}: \"{latest.title}\""]
    if bundle.price_move_pct is not None:
        direction = "gained" if bundle.price_move_pct >= 0 else "declined"
        parts.append(f"{bundle.symbol} shares {direction} {abs(bundle.price_move_pct):.1f}% on the day this was reported.")
    return " ".join(parts)
