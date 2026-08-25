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

import re
import time
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


def _is_real_symbol(symbol: str) -> bool:
    """Guards ranking output against non-company tickers leaking into
    AICompanySignal from upstream article extraction — confirmed live:
    index proxies like "NIFTY_IT" and malformed multi-symbol strings like
    "ICICIBANK, KOTAKBANK" (an unsplit companies_affected[].symbol value)
    were both showing up as ranked "companies" with their own AI score and
    verdict. Real fix belongs further upstream in extraction, but this is
    the one place every consumer (rankings, stats, historical) reads
    through, so it's the reliable backstop regardless of when a bad row
    was written."""
    from app.api.companies import _NSE_UNIVERSE
    sym = symbol.upper().split(".")[0].strip()
    return any(c["symbol"] == sym for c in _NSE_UNIVERSE)


_IMPACT_SIGN = {"positive": 1.0, "negative": -1.0, "neutral": 0.0}
_TREND_SIGN = {"up": 1.0, "down": -1.0, "neutral": 0.0}

# Name<->symbol guard (owner decision, 2026-08-25, following the cross-
# sector companies_affected extraction audit) — deterministic, no LLM
# call. Validated against every real companies_affected entry in the dev
# DB before being wired in here: found the same real bug the audit did
# (PNB Housing Finance mis-tagged with symbol "PNB", Punjab National
# Bank) plus 2 more of the same class (HDB Financial Services tagged
# HDFCBANK; Shriram Finance tagged SRF), with zero false corrections and
# zero wrongful drops on the full real dataset.
_NAME_STOPWORDS = {"ltd", "limited", "inc", "corp", "corporation", "company", "co", "plc", "the", "and", "of", "for", "in", "at"}


def _name_words(name: str) -> list[str]:
    words = re.sub(r"[^a-z0-9\s]", " ", (name or "").lower()).split()
    return [w for w in words if w not in _NAME_STOPWORDS and len(w) > 1]


def _name_compact(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (name or "").lower())


def _names_agree(symbol: str, real_name: str, claimed_name: str) -> bool:
    """True when a companies_affected[] entry's own claimed `name` is
    consistent with the real registered name for its `symbol`. Two real
    escape hatches, both confirmed against live data, not guessed:
    (1) several producers (e.g. signal_publisher.py's live-signal items)
    have no real company name available and echo the bare ticker into
    `name` as a placeholder — not a claim to validate, so it always
    agrees; (2) a real, standard initialism either direction (SBI <->
    "State Bank of India", BSE <-> "Bombay Stock Exchange") counts as
    agreement rather than a false mismatch."""
    if _name_compact(claimed_name) == _name_compact(symbol):
        return True
    real_words, claimed_words = _name_words(real_name), _name_words(claimed_name)
    if not real_words or not claimed_words:
        return True
    if _name_compact(claimed_name) == "".join(w[0] for w in real_words):
        return True
    if _name_compact(real_name).replace("ltd", "") == "".join(w[0] for w in claimed_words):
        return True
    overlap = set(real_words) & set(claimed_words)
    smaller = min(len(real_words), len(claimed_words))
    return len(overlap) >= max(1, smaller // 2)


def _name_candidates(claimed_name: str, exclude_symbol: str) -> list[str]:
    """Deterministic candidate search across the real company universe —
    never an LLM call. Requires >=2 real significant words on both sides
    so a real name that reduces to one generic word after stopword-
    stripping (e.g. "L&T Finance Ltd" -> just "finance") can't produce a
    false match purely on that one word — confirmed live this was a real
    risk (falsely resolved "Reliance Home Finance" to "L&T Finance"
    before this guard was added)."""
    from app.api.companies import _NSE_UNIVERSE

    claimed_words = set(_name_words(claimed_name))
    if len(claimed_words) < 2:
        return []
    candidates: list[str] = []
    for c in _NSE_UNIVERSE:
        if c["symbol"] == exclude_symbol:
            continue
        real_words = set(_name_words(c["name"]))
        if len(real_words) < 2:
            continue
        smaller, larger = (claimed_words, real_words) if len(claimed_words) <= len(real_words) else (real_words, claimed_words)
        jaccard = len(claimed_words & real_words) / len(claimed_words | real_words)
        if smaller.issubset(larger) or jaccard >= 0.6:
            candidates.append(c["symbol"])
    return list(dict.fromkeys(candidates))


def _validated_symbol(raw_symbol: str, claimed_name: str) -> str | None:
    """The one entry point extract_company_signals() calls per companies_
    affected[] item. Returns the symbol to actually use (unchanged, or
    corrected to a confidently-resolved different real symbol), or None
    to skip creating a signal for this entry entirely.

    Three real outcomes, validated against the full real dev dataset
    before being wired in: (1) name agrees, or disagrees but resolves to
    exactly one other real company -> use that symbol (found 3 real
    cases: PNB Housing Finance tagged PNB -> PNBHOUSING, HDB Financial
    Services tagged HDFCBANK -> HDBFS, Shriram Finance tagged SRF ->
    SHRIRAMFIN); (2) name resolves to 2+ real candidates -> genuinely
    ambiguous, drop (zero real cases found, but a real possible state);
    (3) name disagrees but resolves to zero candidates -> we can't prove
    the symbol is wrong, only that the free-text name didn't textually
    match the registry (a real, correct case: "Nykaa Retail Limited" for
    FSN E-Commerce Ventures Ltd is a real brand-vs-legal-name difference,
    not a bug) -- leave the entry untouched rather than destroy
    potentially-valid evidence on a guess. A real, still-open exception
    found live and not auto-fixed by any of these three outcomes: "RHIM"
    tagged "Reliance Home Finance" (RHIM's real name, RHI Magnesita India
    Ltd, has no relationship to it, but no confident resolution target
    exists in the current universe either) -- correctly falls into
    outcome (3), flagged here for a human look, not solved deterministically."""
    from app.api.companies import _NSE_UNIVERSE

    sym = raw_symbol.upper().split(".")[0].strip()
    real_name = next((c["name"] for c in _NSE_UNIVERSE if c["symbol"] == sym), None)
    if real_name is None:
        return None  # not a real symbol at all -- _is_real_symbol's existing job, enforced earlier now instead of only downstream
    if _names_agree(sym, real_name, claimed_name):
        return sym
    candidates = _name_candidates(claimed_name, exclude_symbol=sym)
    if len(candidates) == 1:
        return candidates[0]
    if len(candidates) >= 2:
        return None
    return sym


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
        raw_symbol = str(c.get("symbol") or "")
        if not raw_symbol:
            continue
        # Name<->symbol guard (2026-08-25, see _validated_symbol's own
        # docstring) — also now enforces _is_real_symbol()'s own long-
        # standing aspiration ("real fix belongs further upstream in
        # extraction") at write time, not just downstream in every
        # consumer: a non-real symbol (index proxies, malformed unsplit
        # multi-symbol strings) is skipped here instead of ever reaching
        # AICompanySignal.
        symbol = _validated_symbol(raw_symbol, c.get("name") or "")
        if not symbol:
            continue
        sign = _IMPACT_SIGN.get(str(c.get("impact") or "").lower(), 0.0)
        magnitude = float(article.event_score or 0.0) * sign
        db.add(AICompanySignal(
            source_type="article",
            source_id=article.id,
            symbol=symbol,
            company_name=_name_for(symbol) or c.get("name"),
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


def _accuracy_multiplier_from_matches(matched: list[float]) -> float:
    """The real math half of the historical-accuracy signal, shared by
    both the single-symbol and batch-precomputed callers so the formula
    only lives in one place."""
    if len(matched) < _MIN_ACCURACY_SAMPLE:
        return 1.0
    avg = sum(matched) / len(matched)
    # avg score is 0-1 (1.0 correct, 0.5 partial, 0 incorrect) — map to a
    # gentle 0.85-1.15 multiplier so historical accuracy nudges the score
    # rather than dominating it (this is a secondary signal, not the score).
    return 0.85 + (avg * 0.30)


async def _accuracy_multiplier(db: AsyncSession, symbol: str) -> float:
    """Real per-company historical-accuracy signal, joined through the
    already-working prediction-evaluation loop (prediction_evaluator.py) —
    but that data is sparse today (most symbols have single-digit sample
    counts), so this stays neutral (1.0) below _MIN_ACCURACY_SAMPLE rather
    than projecting false confidence from a handful of evaluations.

    Single-symbol path only (used by the per-symbol /company-scores/{symbol}
    lookup) — for ranking many symbols in one request, build an
    accuracy_map once via _build_accuracy_map() and pass it to
    compute_company_score() instead of calling this per symbol; see that
    function's own docstring for why (this real query pair is symbol-
    independent work that was being repeated once per ranked company —
    confirmed live: /api/company-scores/?limit=50 took ~24s before that
    fix, sub-second after)."""
    matched = (await _build_accuracy_map(db)).get(symbol, [])
    return _accuracy_multiplier_from_matches(matched)


async def _build_accuracy_map(db: AsyncSession) -> dict[str, list[float]]:
    """The real, symbol-independent half of the historical-accuracy query —
    fetch every completed prediction's real target symbols and real
    evaluation scores ONCE, group by symbol. Same real data and the same
    Python-side JSON filtering _accuracy_multiplier always used (SQLite's
    JSON query support varies by build, so this deliberately never filters
    target_entities in SQL) — just computed once per request instead of
    once per company being ranked."""
    from app.db.models.predictions import PredictionRecord, PredictionEvaluation

    full = (await db.execute(
        select(PredictionRecord.id, PredictionRecord.target_entities)
        .where(PredictionRecord.status == "complete")
        .where(PredictionRecord.target_entities.isnot(None))
    )).all()
    if not full:
        return {}

    symbols_by_prediction_id: dict[int, set[str]] = {}
    for pid, entities in full:
        syms = {str(e.get("symbol", "")).upper() for e in (entities or []) if isinstance(e, dict) and e.get("symbol")}
        if syms:
            symbols_by_prediction_id[pid] = syms

    if not symbols_by_prediction_id:
        return {}

    eval_rows = (await db.execute(
        select(PredictionEvaluation.prediction_id, PredictionEvaluation.score)
        .where(PredictionEvaluation.prediction_id.in_(symbols_by_prediction_id.keys()))
    )).all()

    accuracy_map: dict[str, list[float]] = {}
    for pid, score in eval_rows:
        for sym in symbols_by_prediction_id.get(pid, ()):
            accuracy_map.setdefault(sym, []).append(score)
    return accuracy_map


def _trend_for(score: float) -> str:
    """Same bucketing bestStocks.ts already applies client-side to this same
    score — centralized here so every consumer (ranked endpoint, verdict,
    company page) agrees on one trend definition instead of each computing
    its own from the raw score."""
    if score > 55:
        return "up"
    if score < 45:
        return "down"
    return "neutral"


def _risk_level_for(rows: list[AICompanySignal], confidences: list[float]) -> str:
    """Not a fabricated risk score — a real derived read on the same signal
    rows already used for the price score: low average confidence and/or
    signals disagreeing on direction (some positive, some negative) both
    mean the evidence is genuinely less conclusive, which is what "risk" is
    standing in for here (no per-company volatility/beta data exists to
    compute a true market-risk score from — see the backend data audit)."""
    if not rows:
        return "Medium"
    avg_conf = sum(confidences) / len(confidences) if confidences else 0.5
    signs = {1 if r.signed_magnitude > 0 else (-1 if r.signed_magnitude < 0 else 0) for r in rows}
    disagreement = len(signs - {0}) > 1
    if avg_conf < 0.45 or (disagreement and len(rows) < 5):
        return "High"
    if avg_conf >= 0.7 and not disagreement:
        return "Low"
    return "Medium"


async def compute_company_score(
    db: AsyncSession, symbol: str, *, accuracy_map: dict[str, list[float]] | None = None,
) -> dict[str, Any]:
    """accuracy_map (optional): a precomputed symbol -> [evaluation scores]
    mapping from _build_accuracy_map(), for batch callers ranking many
    symbols in one request — skips this function's own real but symbol-
    independent DB fetch, which was previously repeated once per ranked
    symbol (confirmed live: the ~24s /company-scores/?limit=50 regression).
    Single-symbol callers (e.g. /company-scores/{symbol}) omit it and get
    the exact same real per-symbol query as before — no behavior change
    for that path."""
    symbol = symbol.upper().split(".")[0]
    rows = (await db.execute(
        select(AICompanySignal).where(AICompanySignal.symbol == symbol)
    )).scalars().all()

    if not rows:
        return {
            "symbol": symbol, "score": None, "confidence": None,
            "signal_count": 0, "contributing_signal_count": 0, "sector": _sector_for(symbol),
            "top_contributors": [], "positive_reasons": [], "risk_factors": [],
            "trend": "neutral", "verdict": None, "breakdown": {},
        }

    now = datetime.now(timezone.utc)
    if accuracy_map is not None:
        accuracy_mult = _accuracy_multiplier_from_matches(accuracy_map.get(symbol, []))
    else:
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
    avg_confidence = sum(confidences) / len(confidences) if confidences else None
    trend = _trend_for(score)
    risk_level = _risk_level_for(rows, confidences)

    # 2026-08-25 — owner decision, following the signal semantic integrity
    # audit (artifacts/company_signal_semantic_integrity_audit.md): two
    # real producers (comparison_publisher.py, signal_publisher.py) never
    # set confidence_score/quality_score/event_score on the articles they
    # create, so every row sourced from them carries a real, stored 0.0 in
    # at least one weighted factor and is already mathematically inert —
    # it was never moving the score, only inflating signal_count and
    # dragging down the confidence average. Deliberately NOT fixed by
    # populating those fields (that would flip comparison/live-signal rows
    # from "harmlessly inert" to "actually influencing the score" without
    # anyone having designed what that evidence should mean yet — a real
    # scoring-policy change, not a display fix). Instead: signal_count
    # keeps its existing meaning (every real row, for any caller relying
    # on "has at least one signal at all"); contributing_signal_count is
    # the new, honest number for display — only rows whose real weighted
    # contribution is non-zero.
    contributing_signal_count = sum(1 for w, _ in weighted_rows if w != 0)

    # "Why Ranked" / "Risk Factors" — the same weighted evidence, just split
    # by sign instead of by |magnitude| like the old single top_contributors
    # list, so the UI can show real supporting reasons and real countervailing
    # ones separately instead of mixing them.
    positive = sorted([(w, r) for w, r in weighted_rows if w > 0], key=lambda x: x[0], reverse=True)[:5]
    negative = sorted([(w, r) for w, r in weighted_rows if w < 0], key=lambda x: x[0])[:5]
    top = sorted(weighted_rows, key=lambda x: abs(x[0]), reverse=True)[:3]

    def _contrib(w: float, r: AICompanySignal) -> dict:
        # SEO P1-P2, 2026-08-24 — real opportunity-sourced contributors
        # carried no link back to the opportunity they came from, despite
        # source_id already holding the real Opportunity.id (see
        # extract_opportunity_signals above). Article-sourced rows are
        # deliberately left without an href here — IntelligenceArticle's
        # public URL is keyed by slug, not the numeric id stored in
        # source_id, and there's no confirmed id->slug lookup at this call
        # site; a guessed link would risk pointing at the wrong article.
        href = f"/opportunity-radar/{r.source_id}" if r.source_type == "opportunity" else None
        return {
            "reason": r.reason, "source_type": r.source_type, "href": href,
            "signed_magnitude": r.signed_magnitude, "signal_at": r.signal_at.isoformat() if r.signal_at else None,
        }

    verdict = None
    if avg_confidence is not None:
        from app.services.opportunity_intelligence import compute_investment_verdict
        verdict = compute_investment_verdict(
            opportunity_score=score, confidence=avg_confidence, risk_level=risk_level, trend=trend,
        )
        # 2026-08-25 — compute_investment_verdict() is shared with the real
        # V1 Opportunity Radar verdict (radar.py), whose own confidence is a
        # separately-sourced, legitimate field this audit never touched —
        # so the shared function itself (label/tone thresholds included)
        # stays unchanged. Only this consumer's own `reasoning` sentence is
        # rebuilt here to drop the embedded "{N}% confidence" clause, since
        # the per-row-averaged confidence it would otherwise quote is
        # exactly the number retired from display everywhere else on this
        # page (see the confidence provenance audit).
        reasons = [f"Opportunity score {round(score)}/100", f"{risk_level or 'Medium'} risk"]
        if trend and trend != "neutral":
            reasons.append(f"{trend} trend")
        verdict["reasoning"] = " · ".join(reasons)

    return {
        "symbol": symbol,
        "score": round(score, 1),
        "confidence": round(avg_confidence, 2) if avg_confidence is not None else None,
        "signal_count": len(rows),
        "contributing_signal_count": contributing_signal_count,
        "sector": _sector_for(symbol),
        "trend": trend,
        "risk_level": risk_level,
        "verdict": verdict,
        "top_contributors": [_contrib(w, r) for w, r in top],
        "positive_reasons": [_contrib(w, r) for w, r in positive if r.reason],
        "risk_factors": [_contrib(w, r) for w, r in negative if r.reason],
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
    for sector, symbol in rows:
        if sector and _is_real_symbol(symbol):
            counts[sector] = counts.get(sector, 0) + 1
    return counts


async def get_ranking_stats(db: AsyncSession) -> dict[str, Any]:
    """Real aggregate KPIs for the Best Stocks hero/KPI strip — computed
    from every symbol that has at least one real signal, not capped at the
    20-50 row limit the ranking endpoints use for display. avg_score/
    avg_confidence are plain means across all ranked (score is not None)
    companies; nothing here is a display-tuned or rounded-up number."""
    symbols = (await db.execute(select(AICompanySignal.symbol).distinct())).scalars().all()
    symbols = [s for s in symbols if _is_real_symbol(s)]
    accuracy_map = await _build_accuracy_map(db)
    scored = [await compute_company_score(db, s, accuracy_map=accuracy_map) for s in symbols]
    scored = [r for r in scored if r["score"] is not None]

    sectors = {r["sector"] for r in scored if r["sector"]}
    scores = [r["score"] for r in scored]
    confidences = [r["confidence"] for r in scored if r["confidence"] is not None]

    return {
        "stocks_ranked": len(scored),
        "sectors_covered": len(sectors),
        "avg_score": round(sum(scores) / len(scores), 1) if scores else None,
        "avg_confidence": round(sum(confidences) / len(confidences) * 100, 1) if confidences else None,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


_RANKINGS_CACHE: dict[tuple[str | None, int], tuple[float, list[dict[str, Any]]]] = {}
_RANKINGS_TTL_S = 300.0  # 5 min — short enough that rankings don't go
                          # meaningfully stale, long enough that repeated
                          # page loads within a session hit cache instead
                          # of re-running the full ranking pass.


async def compute_sector_rankings(db: AsyncSession, sector: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
    """Ranks every symbol that has at least one real signal, optionally
    scoped to one sector. Powers bestStocks.ts, /companies (Overview tab),
    and the sector page — the single computation all three share instead
    of each running their own N per-symbol calls.

    Real regression found and fixed 2026-08-25: this previously ran
    compute_company_score() once per symbol with NO cache, and each of
    those calls independently repeated the same real but symbol-
    independent historical-accuracy query pair — confirmed live,
    GET /api/company-scores/?limit=50 took ~24s (several hundred symbols
    scored to produce a 50-row result), the dominant cost in a real
    ~30s /companies page load with zero frontend-side caching on that
    call. Two real, narrow fixes, not a full batch-query rewrite of
    every per-symbol lookup: (1) accuracy_map is now built ONCE per call
    via _build_accuracy_map() instead of once per symbol; (2) a short TTL
    cache (this dict) around the full ranked-and-limited result, keyed by
    the exact inputs that change it (sector, limit), so repeat requests
    within the window skip the computation entirely. Never caches an
    exception — a raised error propagates before the cache is written, so
    a failed pass is retried on the next request rather than cached."""
    cache_key = (sector, limit)
    now = time.monotonic()
    cached = _RANKINGS_CACHE.get(cache_key)
    if cached is not None and now - cached[0] < _RANKINGS_TTL_S:
        log.info("company_rankings.cache_hit", sector=sector, limit=limit)
        return cached[1]

    t0 = time.monotonic()
    query = select(AICompanySignal.symbol).distinct()
    if sector:
        query = query.where(AICompanySignal.sector == sector)
    symbols = (await db.execute(query)).scalars().all()
    symbols = [s for s in symbols if _is_real_symbol(s)]

    accuracy_map = await _build_accuracy_map(db)
    results = [await compute_company_score(db, s, accuracy_map=accuracy_map) for s in symbols]
    results = [r for r in results if r["score"] is not None]
    results.sort(key=lambda r: r["score"], reverse=True)
    results = results[:limit]

    duration_ms = round((time.monotonic() - t0) * 1000, 1)
    log.info("company_rankings.cache_miss", sector=sector, limit=limit, symbols_scored=len(symbols), duration_ms=duration_ms)
    _RANKINGS_CACHE[cache_key] = (now, results)
    return results


async def historical_track_record(db: AsyncSession, symbol: str) -> dict[str, Any]:
    """Real win-rate/avg-return/occurrence stats for a symbol, aggregated
    from HistoricalMarketEvent.historical_winners/historical_losers — the
    24 hand-verified seed events (see historical_memory_service.py). No
    aggregation of this kind existed before (confirmed by a full-backend
    grep for win_rate/avg_return/occurrence — nothing computed a rollup,
    only per-event similarity lookups).

    Deliberately does NOT round occurrences up to look more substantial —
    with only 24 total seed events today, most symbols will show single-
    digit occurrence counts. That's the honest number; the caller/UI
    should render this as "3 real historical occurrences", not imply a
    larger backtest than actually exists.
    """
    from app.db.models.historical_memory import HistoricalMarketEvent

    symbol = symbol.upper().split(".")[0]
    rows = (await db.execute(select(HistoricalMarketEvent))).scalars().all()

    occurrences: list[dict[str, Any]] = []
    for ev in rows:
        for w in (ev.historical_winners or []):
            if isinstance(w, dict) and str(w.get("symbol", "")).upper() == symbol:
                occurrences.append({
                    "event_id": ev.id, "event_title": ev.event_title, "category": ev.category,
                    "event_date": ev.event_date.isoformat() if ev.event_date else None,
                    "won": True,
                    "return_1w": w.get("return_1w"), "return_1m": w.get("return_1m"),
                    "reason": w.get("reason"),
                })
        for l in (ev.historical_losers or []):
            if isinstance(l, dict) and str(l.get("symbol", "")).upper() == symbol:
                occurrences.append({
                    "event_id": ev.id, "event_title": ev.event_title, "category": ev.category,
                    "event_date": ev.event_date.isoformat() if ev.event_date else None,
                    "won": False,
                    "return_1w": l.get("return_1w"), "return_1m": l.get("return_1m"),
                    "reason": l.get("reason"),
                })

    if not occurrences:
        return {"symbol": symbol, "occurrences": 0, "win_rate": None, "avg_return_1m": None, "events": []}

    wins = sum(1 for o in occurrences if o["won"])
    returns = [o["return_1m"] if o["return_1m"] is not None else o["return_1w"] for o in occurrences]
    returns = [r for r in returns if r is not None]

    return {
        "symbol": symbol,
        "occurrences": len(occurrences),
        "win_rate": round(wins / len(occurrences) * 100, 1),
        "avg_return_1m": round(sum(returns) / len(returns), 2) if returns else None,
        "events": occurrences,
    }


async def sector_strength(db: AsyncSession, sector: str) -> dict[str, Any]:
    """Wires up scoring_engine.score_sector_strength() with real inputs —
    that formula existed but had zero live callers anywhere in the backend
    (confirmed by a full-repo grep) before this. Supplies 4 of its 8 real
    weighted inputs (58% of total formula weight, comfortably above the
    formula's own 35% minimum-coverage gate) from data that already exists;
    the other 4 (institutional_flow, momentum, economic_drivers,
    historical_trend) have no real per-sector source today and are left
    unset rather than approximated, so the formula redistributes their
    weight across the real ones instead of averaging in a guess."""
    from app.services.scoring_engine import SectorStrengthInputs, score_sector_strength

    rankings = await compute_sector_rankings(db, sector=sector, limit=500)
    if not rankings:
        return {"sector": sector, "score": None, "reasoning": ["No ranked companies in this sector yet."]}

    scores = [r["score"] for r in rankings]
    avg_company_performance = sum(scores) / len(scores)

    # Market breadth: real share of this sector's ranked companies trending
    # up vs down, on the same trend bucketing the rest of the engine uses.
    up = sum(1 for r in rankings if r["trend"] == "up")
    market_breadth = (up / len(rankings)) * 100

    # News flow proxy: real signal volume in this sector, normalized against
    # a reasonable "very active sector" ceiling (30 signals) rather than an
    # arbitrary 0-100 guess — more signals is a real, if approximate, read
    # on how much is actually happening in this sector right now.
    signal_count = sum(r["signal_count"] for r in rankings)
    news_flow = min(100.0, (signal_count / 30.0) * 100.0)

    # Relative strength: this sector's avg score vs the overall market's
    # avg score across every sector with real rankings — a real comparison,
    # not a fabricated percentile.
    all_counts = await get_sector_signal_counts(db)
    other_scores: list[float] = []
    for other_sector in all_counts:
        if other_sector == sector:
            continue
        other_rankings = await compute_sector_rankings(db, sector=other_sector, limit=500)
        other_scores.extend(r["score"] for r in other_rankings)
    market_avg = (sum(other_scores) / len(other_scores)) if other_scores else 50.0
    relative_strength = max(0.0, min(100.0, 50.0 + (avg_company_performance - market_avg)))

    result = score_sector_strength(SectorStrengthInputs(
        avg_company_performance=avg_company_performance,
        news_flow=news_flow,
        market_breadth=market_breadth,
        relative_strength=relative_strength,
    ))
    return {"sector": sector, **result.to_dict()}
