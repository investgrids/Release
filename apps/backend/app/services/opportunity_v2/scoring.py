"""
Bounded/capped scoring — every component has a fixed maximum, never a raw
sum (owner correction, 2026-08-22: 10 mediocre Developments must not
outscore 2 extremely strong ones just because there are more of them).
Company/sector confirmation only count as a bonus when their own real
direction AGREES with the thesis direction; disagreement becomes a real
contradiction penalty, never silently averaged away into a smaller
bonus.

Explicitly a first, real-inputs-only version (no fabricated components —
V1's revenue_potential/expected_cagr/etc formulaic financial projections
are not reproduced here at all). Component weights/caps are reasonable
starting points, not calibrated against real outcomes yet — the plan's
own instruction is to tune from real shadow-run score distributions once
they exist, not upfront.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.development import Development
from app.services.aipe.company_score_engine import compute_company_score, sector_strength

_TIER_WEIGHT = {"critical": 1.0, "high": 0.8, "medium": 0.5, "low": 0.2}

_MAX_EVIDENCE_QUALITY = 35.0
_MAX_DEVELOPMENT_COUNT = 15.0
_MAX_COMPANY_CONFIRMATION = 25.0
_MAX_SECTOR_CONFIRMATION = 10.0
_MAX_FRESHNESS = 15.0
_MAX_CONTRADICTION_PENALTY = 30.0  # subtracted, not added to the 100 above

# compute_company_score()'s real trend vocabulary ("up"/"down"/"neutral",
# see company_score_engine.py::_trend_for) differs from thesis direction's
# ("positive"/"negative"/"neutral"/"mixed") — this maps between them
# rather than assuming they're the same words.
_TREND_TO_DIRECTION = {"up": "positive", "down": "negative", "neutral": "neutral"}
_DEVELOPMENT_COUNT_SATURATION = 5  # component reaches its max at this many linked Developments


@dataclass
class ScoreBreakdown:
    evidence_quality: float = 0.0
    development_count: float = 0.0
    company_confirmation: float = 0.0
    sector_confirmation: float = 0.0
    freshness: float = 0.0
    contradiction_penalty: float = 0.0
    contradictions: list[str] = field(default_factory=list)
    # Per-company real signal captured at the exact point it's computed
    # below, rather than discarded once folded into company_confirmation's
    # aggregate total — read_service.py's companies_connected needs this
    # to show WHICH company confirms/contradicts, not just the total
    # (V2 Promotion Blocker Remediation, Batch C). "No real signal for
    # this company" is itself recorded honestly (score/real_direction
    # both None), never silently omitted or imputed.
    company_signals: list[dict] = field(default_factory=list)

    @property
    def total(self) -> float:
        raw = (
            self.evidence_quality + self.development_count
            + self.company_confirmation + self.sector_confirmation + self.freshness
            - self.contradiction_penalty
        )
        return round(max(0.0, min(100.0, raw)), 1)


def _evidence_quality(developments: list[Development]) -> float:
    if not developments:
        return 0.0
    per_dev = []
    for d in developments:
        confidence = d.current_confidence if d.current_confidence is not None else (d.formation_confidence or 0.0)
        tier = (d.current_impact_tier or d.formation_impact_tier or "").strip().lower()
        weight = _TIER_WEIGHT.get(tier, 0.2)
        per_dev.append(confidence * weight)
    avg = sum(per_dev) / len(per_dev)
    return round(min(_MAX_EVIDENCE_QUALITY, avg * _MAX_EVIDENCE_QUALITY), 1)


def _development_count_bonus(developments: list[Development]) -> float:
    n = len(developments)
    return round(_MAX_DEVELOPMENT_COUNT * min(1.0, n / _DEVELOPMENT_COUNT_SATURATION), 1)


def _aware(dt):
    """Some real Development.last_observed_at rows come back offset-naive
    despite the column being DateTime(timezone=True) (SQLite doesn't
    strictly enforce it) — confirmed live against the real local DB, same
    class of gotcha event_lifecycle.py's own _age_hours() already guards
    against. Assume UTC, matching that precedent, rather than raising."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _freshness(developments: list[Development], now) -> float:
    if not developments:
        return 0.0
    most_recent = max((_aware(d.last_observed_at) for d in developments if d.last_observed_at), default=None)
    if most_recent is None:
        return 0.0
    age_days = max(0.0, (now - most_recent).total_seconds() / 86400.0)
    # Same half-life-style decay convention already used for company
    # scoring (company_score_engine.py's recency_decay), not a new curve.
    decay = 0.5 ** (age_days / 3.0)
    return round(_MAX_FRESHNESS * decay, 1)


async def score_cluster(
    db: AsyncSession, developments: list[Development], thesis_direction: str,
    companies: list[str], sectors: list[str], now,
) -> ScoreBreakdown:
    """companies/sectors: the real, graph-confirmed union already computed
    upstream (never re-derived here from each Development's own
    self-reported tags — that was V1's bug)."""
    breakdown = ScoreBreakdown(
        evidence_quality=_evidence_quality(developments),
        development_count=_development_count_bonus(developments),
        freshness=_freshness(developments, now),
    )

    company_confirm_total = 0.0
    contradiction_total = 0.0
    for symbol in companies:
        result = await compute_company_score(db, symbol)
        if result.get("score") is None:
            breakdown.company_signals.append({
                "symbol": symbol, "score": None, "real_direction": None,
                "confirms_thesis": False, "contradicts_thesis": False,
            })
            continue  # no real signal for this company — contributes nothing, never imputed
        real_direction = _TREND_TO_DIRECTION.get(result.get("trend"), "neutral")
        agrees = real_direction == thesis_direction or thesis_direction == "neutral" or real_direction == "neutral"
        contradicts = real_direction != "neutral" and thesis_direction not in ("neutral", "mixed") and real_direction != thesis_direction
        confirms = agrees and real_direction != "neutral" and not contradicts
        if contradicts:
            contradiction_total += 1
            breakdown.contradictions.append(f"{symbol}: real trend ({real_direction}) disagrees with thesis ({thesis_direction})")
        elif confirms:
            company_confirm_total += 1
        breakdown.company_signals.append({
            "symbol": symbol, "score": result.get("score"), "real_direction": real_direction,
            "confirms_thesis": confirms, "contradicts_thesis": contradicts,
        })
    if companies:
        breakdown.company_confirmation = round(
            _MAX_COMPANY_CONFIRMATION * min(1.0, company_confirm_total / max(1, len(companies))), 1
        )

    sector_confirm_total = 0.0
    for sector in sectors:
        result = await sector_strength(db, sector)
        if result.get("score") is None:
            continue
        # sector_strength's own score is a plain 0-100 strength number, not
        # a directional trend — treat >55/<45 the same way
        # company_score_engine._trend_for buckets an individual company's
        # score, for consistency rather than inventing a second threshold
        # scheme.
        score = result["score"]
        real_direction = "positive" if score > 55 else "negative" if score < 45 else "neutral"
        if real_direction != "neutral" and thesis_direction not in ("neutral", "mixed") and real_direction != thesis_direction:
            contradiction_total += 1
            breakdown.contradictions.append(f"{sector}: real sector strength ({real_direction}) disagrees with thesis ({thesis_direction})")
        elif real_direction == thesis_direction and real_direction != "neutral":
            sector_confirm_total += 1
    if sectors:
        breakdown.sector_confirmation = round(
            _MAX_SECTOR_CONFIRMATION * min(1.0, sector_confirm_total / max(1, len(sectors))), 1
        )

    breakdown.contradiction_penalty = round(
        min(_MAX_CONTRADICTION_PENALTY, contradiction_total * 10.0), 1
    )
    return breakdown
