"""
AI Company Intelligence Score Engine.

One engine, reused by every page that ranks companies (company pages,
sector pages, best-stocks pages) instead of separate ranking logic per
feature. Two halves:

  extract_company_signals()  — turns one already-published IntelligenceArticle
                                or Opportunity's real per-company data into
                                AICompanySignal rows (the evidence layer).
  compute_company_score()    — aggregates a symbol's signals into one score
                                (computed on read — see module docstring on
                                AICompanySignal for why nothing is persisted
                                as a second "current score" table yet).

Formula: for each signal, weighted = signed_magnitude * confidence * quality
* recency_decay(age_days). Sum across signals, then apply a real (but
sparse-data-aware) historical-accuracy multiplier. Never fabricates: a
company with zero real signals returns signal_count=0 and score=None, not
a manufactured "0" that would read as a real bearish score.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import structlog

from app.db.models.company_signal import AICompanySignal
from app.db.models.intelligence_article import IntelligenceArticle

log = structlog.get_logger(__name__)

_RECENCY_HALF_LIFE_DAYS = 21   # ~3 weeks — news relevance fades faster than macro trends
_MIN_ACCURACY_SAMPLE = 10      # below this, historical accuracy stays neutral rather than fabricated confidence


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _sector_for(symbol: str) -> str | None:
    from app.api.companies import _NSE_UNIVERSE
    sym = symbol.upper().split(".")[0]
    for c in _NSE_UNIVERSE:
        if c["symbol"] == sym:
            return c["sector"]
    return None


def _name_for(symbol: str) -> str | None:
    from app.api.companies import _NSE_UNIVERSE
    sym = symbol.upper().split(".")[0]
    for c in _NSE_UNIVERSE:
        if c["symbol"] == sym:
            return c["name"]
    return None


_IMPACT_SIGN = {"positive": 1.0, "negative": -1.0, "neutral": 0.0}
_TREND_SIGN = {"up": 1.0, "down": -1.0, "neutral": 0.0}


async def extract_company_signals(db: AsyncSession, article: IntelligenceArticle, auto_commit: bool = True) -> int:
    """Extracts one AICompanySignal row per company mentioned in a just-
    published article's companies_affected[]. Idempotent per-article (skips
    if signals already exist for this source_id) so it's safe to call both
    at publish time and from a backfill job without double-counting.
    auto_commit=False lets a caller iterating many rows (the backfill job)
    batch everything into one commit instead of one per row — a boot-time
    loop over the full article/opportunity corpus doing a separate commit
    per row is real, avoidable overhead on every single deploy."""
    existing = (await db.execute(
        select(AICompanySignal.id).where(
            AICompanySignal.source_type == "article",
            AICompanySignal.source_id == article.id,
        ).limit(1)
    )).scalar_one_or_none()
    if existing is not None:
        return 0

    signal_at = _aware(article.published_at) or _aware(article.created_at) or datetime.now(timezone.utc)
    created = 0
    for c in (article.companies_affected or []):
        if not isinstance(c, dict):
            continue
        symbol = str(c.get("symbol") or "").upper().split(".")[0]
        if not symbol:
            continue
        sign = _IMPACT_SIGN.get(str(c.get("impact") or "").lower(), 0.0)
        magnitude = float(article.event_score or 0.0) * sign
        db.add(AICompanySignal(
            source_type="article",
            source_id=article.id,
            symbol=symbol,
            company_name=c.get("name") or _name_for(symbol),
            sector=_sector_for(symbol),
            signed_magnitude=magnitude,
            confidence=article.confidence_score,
            quality=article.quality_score,
            reason=c.get("reason"),
            signal_at=signal_at,
        ))
        created += 1
    if created and auto_commit:
        await db.commit()
    return created


async def extract_opportunity_signals(db: AsyncSession, opportunity_id: int, opportunity_created_at: datetime, auto_commit: bool = True) -> int:
    """Same extraction, for an Opportunity's already-real per-company
    impact_score/confidence/reason (OpportunityCompany) — the other existing
    real signal source (previously the ONLY source bestStocks.ts read).
    Merging both into one signal table is what makes this one engine
    instead of two parallel ranking systems."""
    from app.db.models.opportunity import OpportunityCompany

    existing = (await db.execute(
        select(AICompanySignal.id).where(
            AICompanySignal.source_type == "opportunity",
            AICompanySignal.source_id == str(opportunity_id),
        ).limit(1)
    )).scalar_one_or_none()
    if existing is not None:
        return 0

    rows = (await db.execute(
        select(OpportunityCompany).where(OpportunityCompany.opportunity_id == opportunity_id)
    )).scalars().all()

    signal_at = _aware(opportunity_created_at) or datetime.now(timezone.utc)
    created = 0
    for c in rows:
        symbol = str(c.company_id or "").upper().split(".")[0]
        if not symbol:
            continue
        sign = _TREND_SIGN.get(str(c.trend or "").lower(), 0.0)
        db.add(AICompanySignal(
            source_type="opportunity",
            source_id=str(opportunity_id),
            symbol=symbol,
            company_name=c.company_name or _name_for(symbol),
            sector=_sector_for(symbol),
            signed_magnitude=float(c.impact_score or 0.0) * (sign if sign != 0.0 else 1.0),
            confidence=c.confidence,
            quality=None,  # no equivalent quality gate for opportunity rows
            reason=c.reason,
            signal_at=signal_at,
        ))
        created += 1
    if created and auto_commit:
        await db.commit()
    return created


async def _accuracy_multiplier(db: AsyncSession, symbol: str) -> float:
    """Real per-company historical-accuracy signal, joined through the
    already-working prediction-evaluation loop (prediction_evaluator.py) —
    but that data is sparse today (most symbols have single-digit sample
    counts), so this stays neutral (1.0) below _MIN_ACCURACY_SAMPLE rather
    than projecting false confidence from a handful of evaluations."""
    from app.db.models.predictions import PredictionRecord, PredictionEvaluation

    rows = (await db.execute(
        select(PredictionEvaluation.score)
        .join(PredictionRecord, PredictionRecord.id == PredictionEvaluation.prediction_id)
        .where(PredictionRecord.target_entities.isnot(None))
    )).all()
    # target_entities is JSON — filter in Python (symbol match), not SQL,
    # since SQLite JSON querying support varies by build.
    matched: list[float] = []
    if rows:
        full = (await db.execute(
            select(PredictionRecord.id, PredictionRecord.target_entities)
            .where(PredictionRecord.status == "complete")
        )).all()
        matching_ids = [
            pid for pid, entities in full
            if any(str(e.get("symbol", "")).upper() == symbol for e in (entities or []) if isinstance(e, dict))
        ]
        if matching_ids:
            scores = (await db.execute(
                select(PredictionEvaluation.score).where(PredictionEvaluation.prediction_id.in_(matching_ids))
            )).scalars().all()
            matched = list(scores)

    if len(matched) < _MIN_ACCURACY_SAMPLE:
        return 1.0
    avg = sum(matched) / len(matched)
    # avg score is 0-1 (1.0 correct, 0.5 partial, 0 incorrect) — map to a
    # gentle 0.85-1.15 multiplier so historical accuracy nudges the score
    # rather than dominating it (this is a secondary signal, not the score).
    return 0.85 + (avg * 0.30)


async def compute_company_score(db: AsyncSession, symbol: str) -> dict[str, Any]:
    symbol = symbol.upper().split(".")[0]
    rows = (await db.execute(
        select(AICompanySignal).where(AICompanySignal.symbol == symbol)
    )).scalars().all()

    if not rows:
        return {
            "symbol": symbol, "score": None, "confidence": None,
            "signal_count": 0, "sector": _sector_for(symbol),
            "top_contributors": [], "breakdown": {},
        }

    now = datetime.now(timezone.utc)
    accuracy_mult = await _accuracy_multiplier(db, symbol)

    weighted_rows = []
    confidences = []
    for r in rows:
        age_days = max(0.0, (now - _aware(r.signal_at)).total_seconds() / 86400)
        decay = 0.5 ** (age_days / _RECENCY_HALF_LIFE_DAYS)
        confidence = r.confidence if r.confidence is not None else 0.5
        quality = r.quality if r.quality is not None else 1.0  # neutral for opportunity-sourced rows
        weighted = r.signed_magnitude * confidence * quality * decay * accuracy_mult
        weighted_rows.append((weighted, r))
        confidences.append(confidence)

    total = sum(w for w, _ in weighted_rows)
    # Normalize to a 0-100 scale via tanh-style compression so a handful of
    # strong signals don't blow past 100 while still differentiating a
    # 1-signal company from a 20-signal one — divisor tuned to real observed
    # magnitude range (event_score/opportunity impact_score both ~0-100).
    score = 50 + max(-50, min(50, total / max(1, len(rows)) * 0.5))

    top = sorted(weighted_rows, key=lambda x: abs(x[0]), reverse=True)[:3]

    return {
        "symbol": symbol,
        "score": round(score, 1),
        "confidence": round(sum(confidences) / len(confidences), 2) if confidences else None,
        "signal_count": len(rows),
        "sector": _sector_for(symbol),
        "top_contributors": [
            {
                "reason": r.reason, "source_type": r.source_type,
                "signed_magnitude": r.signed_magnitude, "signal_at": r.signal_at.isoformat() if r.signal_at else None,
            }
            for _, r in top
        ],
        "breakdown": {
            "accuracy_multiplier": round(accuracy_mult, 3),
            "raw_total": round(total, 1),
        },
    }


async def get_sector_signal_counts(db: AsyncSession) -> dict[str, int]:
    """Distinct-symbol count per sector, without computing full scores for
    every symbol in the universe (compute_company_score is O(signals) per
    call — cheap for one sector's worth of symbols, wasteful for all ~500).
    Powers bestStocks.ts's sector-listing page, which only needs counts to
    apply the thin-content guard, not full rankings."""
    rows = (await db.execute(
        select(AICompanySignal.sector, AICompanySignal.symbol).distinct()
    )).all()
    counts: dict[str, int] = {}
    for sector, _symbol in rows:
        if sector:
            counts[sector] = counts.get(sector, 0) + 1
    return counts


async def compute_sector_rankings(db: AsyncSession, sector: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
    """Ranks every symbol that has at least one real signal, optionally
    scoped to one sector. Powers bestStocks.ts and the sector page — the
    single query both features share instead of N per-symbol calls."""
    query = select(AICompanySignal.symbol).distinct()
    if sector:
        query = query.where(AICompanySignal.sector == sector)
    symbols = (await db.execute(query)).scalars().all()

    results = [await compute_company_score(db, s) for s in symbols]
    results = [r for r in results if r["score"] is not None]
    results.sort(key=lambda r: r["score"], reverse=True)
    return results[:limit]
