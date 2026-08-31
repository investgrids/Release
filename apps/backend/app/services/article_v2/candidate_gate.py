"""
Article V2 Phase C1 — Candidate Gate (owner design, 2026-08-31).

Answers exactly one question, deterministically: does this event deserve
coverage, and what type of coverage could it justify? Does NOT decide
article format — FULL_ARTICLE / FACTUAL_UPDATE / SKIP is Phase C4's job,
downstream of C2 (Evidence Set Builder) and C3 (Event-aware Context) —
and writes nothing; this is a pure decision function, shadow-only.

Three outcomes:
  CANDIDATE        — real evidence, real materiality, no existing
                      coverage found. Proceed to C2.
  UPDATE_CANDIDATE — a real signal exists but genuinely belongs as an
                      update to existing coverage rather than a new
                      article (either real coverage of the exact same
                      triggering event already exists, or a
                      near-identical headline was already covered
                      recently).
  SKIP             — insufficient evidence, insufficient materiality
                      (administrative/routine filing), or the entity
                      never resolved to a real canonical CompanyEntity.

Evidence-first by explicit instruction — no LLM call anywhere in this
module, and no invented 0-100 materiality score. Every signal reused is
a real, already-built, already-tested deterministic fact:
  - canonical entity resolution: ArticleEvidenceBundle.resolved (Phase A)
  - linked evidence existence/count: ArticleEvidenceBundle.evidence
  - materiality: evidence_ranking.rank_evidence()'s own real 0.0-1.0
    substantiveness+relevance score (Phase A.1) — reused as-is via
    ArticleEvidenceBundle.ranked_evidence, not reimplemented and not
    replaced with a new number.
  - duplicate/already-covered: the EXACT same 2-tier priority and
    thresholds duplicate_detector.py already uses in production
    (trigger_event_id exact match first — event identity is a stronger
    signal than headline text — then Jaccard headline similarity >= 0.50
    within the same 24h lookback), reused verbatim, not re-derived,
    against real published IntelligenceArticle rows.

Every decision carries a machine-readable reason_code and a human-
readable reason_detail explaining exactly which real fact drove it —
the objective per the owner's own framing is that the reasoning is
auditable and defensible, not that the candidate rate looks good.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.intelligence_article import IntelligenceArticle
from app.services.aipe.duplicate_detector import _jaccard, _tokenize
from app.services.warehouse.article_evidence_bundle import build_article_evidence_bundle

# Same window/threshold/lifecycle-filter duplicate_detector.py already
# uses for exactly this class of check (see its own find_duplicate()) —
# reused for consistency with the real, already-approved production
# mechanism, not re-derived from scratch.
_LOOKBACK_HOURS = 24
_HEADLINE_SIMILARITY_THRESHOLD = 0.50
_LIVE_LIFECYCLE_STATUSES_EXCLUDED = ("archived", "merged", "failed")

# evidence_ranking.py's own _SCORE_LOW is 0.2 (a single recognized
# low-substantiveness filing, no query-context relevance). The floor sits
# just above that so a bare low-substantiveness filing with zero
# relevance signal (score == 0.2 exactly) is caught as LOW_MATERIALITY,
# not waved through by a floor set exactly at the same value.
_MATERIALITY_FLOOR = 0.25

CANDIDATE = "CANDIDATE"
UPDATE_CANDIDATE = "UPDATE_CANDIDATE"
SKIP = "SKIP"


@dataclass(frozen=True)
class CandidateDecision:
    outcome: str
    reason_code: str
    reason_detail: str
    entity_id: str | None
    symbol: str | None
    evidence_count: int
    top_evidence_score: float | None
    top_evidence_reasons: list[str] | None = None
    matched_article_id: str | None = None  # set only when reason_code == "ALREADY_COVERED"


async def _find_already_covered(
    db: AsyncSession, *, event_id: str | None, symbol: str, headline: str,
) -> IntelligenceArticle | None:
    """Real coverage check against real published articles — event
    identity checked first (stronger signal), headline similarity only
    as a fallback, exactly duplicate_detector.py's own priority order."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=_LOOKBACK_HOURS)

    if event_id:
        result = await db.execute(
            select(IntelligenceArticle)
            .where(IntelligenceArticle.trigger_event_id == event_id)
            .where(IntelligenceArticle.created_at >= cutoff)
            .where(IntelligenceArticle.lifecycle_status.notin_(_LIVE_LIFECYCLE_STATUSES_EXCLUDED))
            .order_by(IntelligenceArticle.created_at.desc())
            .limit(1)
        )
        existing = result.scalar_one_or_none()
        if existing is not None:
            return existing

    result = await db.execute(
        select(IntelligenceArticle)
        .where(IntelligenceArticle.created_at >= cutoff)
        .where(IntelligenceArticle.lifecycle_status.notin_(_LIVE_LIFECYCLE_STATUSES_EXCLUDED))
        .order_by(IntelligenceArticle.created_at.desc())
        .limit(50)
    )
    recent = result.scalars().all()
    query_tokens = _tokenize(headline)
    for article in recent:
        if not article.headline:
            continue
        companies_affected = article.companies_affected or []
        mentions_symbol = article.angle_entity == symbol or any(
            isinstance(c, dict) and c.get("symbol") == symbol for c in companies_affected
        )
        if not mentions_symbol:
            continue
        similarity = _jaccard(query_tokens, _tokenize(article.headline))
        if similarity >= _HEADLINE_SIMILARITY_THRESHOLD:
            return article
    return None


async def evaluate_candidate(
    db: AsyncSession, *, symbol: str, event_headline: str, event_id: str | None = None,
) -> CandidateDecision:
    """The one real entry point. `symbol` is resolved through the same
    canonical Company Identity resolver Phase A already uses (never a
    keyword guess). `event_headline` is used both as the ranking query
    context (so evidence relevant to THIS event outranks unrelated
    linked evidence) and as the duplicate-check text. `event_id` is the
    real triggering event's own id (e.g. EventTriage.event_id) when one
    exists — omit it and only the headline-similarity duplicate check
    runs."""
    bundle = await build_article_evidence_bundle(
        db, symbol, query_context=event_headline,
        include_historical=False, include_price_move=False, include_financial_context=False,
        # C1 only needs entity resolution + linked evidence + ranking to
        # decide; price-move (a real live yfinance call) and financial
        # context are real costs this gate has no use for — C2/C3 build
        # the full bundle again once something is a real CANDIDATE.
    )

    if not bundle.resolved:
        return CandidateDecision(
            outcome=SKIP, reason_code="ENTITY_UNRESOLVED",
            reason_detail=f"{symbol!r} did not resolve to a real canonical CompanyEntity",
            entity_id=None, symbol=symbol, evidence_count=0, top_evidence_score=None,
        )

    if not bundle.evidence:
        return CandidateDecision(
            outcome=SKIP, reason_code="INSUFFICIENT_EVIDENCE",
            reason_detail="zero real linked RawEvidence for this entity",
            entity_id=bundle.entity_id, symbol=bundle.symbol, evidence_count=0, top_evidence_score=None,
        )

    already_covered = await _find_already_covered(
        db, event_id=event_id, symbol=bundle.symbol, headline=event_headline,
    )
    top = bundle.ranked_evidence[0] if bundle.ranked_evidence else None
    top_score = top.score if top else None
    top_reasons = top.reasons if top else None

    if already_covered is not None:
        return CandidateDecision(
            outcome=UPDATE_CANDIDATE, reason_code="ALREADY_COVERED",
            reason_detail=(
                f"real coverage already exists (article {already_covered.id}, "
                f"headline={already_covered.headline!r:.80}) -- route as an update to "
                f"existing coverage, not a new article"
            ),
            entity_id=bundle.entity_id, symbol=bundle.symbol, evidence_count=len(bundle.evidence),
            top_evidence_score=top_score, top_evidence_reasons=top_reasons,
            matched_article_id=already_covered.id,
        )

    if top_score is None or top_score < _MATERIALITY_FLOOR:
        return CandidateDecision(
            outcome=SKIP, reason_code="LOW_MATERIALITY",
            reason_detail=(
                f"top-ranked evidence score {top_score} is below the materiality floor "
                f"({_MATERIALITY_FLOOR}) -- {top_reasons}"
            ),
            entity_id=bundle.entity_id, symbol=bundle.symbol, evidence_count=len(bundle.evidence),
            top_evidence_score=top_score, top_evidence_reasons=top_reasons,
        )

    return CandidateDecision(
        outcome=CANDIDATE, reason_code="EVIDENCE_SUFFICIENT",
        reason_detail=(
            f"top-ranked evidence score {top_score} clears the materiality floor "
            f"({_MATERIALITY_FLOOR}), no existing coverage found -- {top_reasons}"
        ),
        entity_id=bundle.entity_id, symbol=bundle.symbol, evidence_count=len(bundle.evidence),
        top_evidence_score=top_score, top_evidence_reasons=top_reasons,
    )
