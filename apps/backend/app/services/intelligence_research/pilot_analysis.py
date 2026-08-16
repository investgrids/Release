"""
Phase 2E.2 pilot analysis — read-only over IntelligencePilotObservation/
Evaluation. Every output here is EXPLORATORY / SMALL SAMPLE by
construction (73 observations total) and must be reported as such, not
as a production-grade finding — owner's explicit instruction.
"""
from __future__ import annotations

from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.intelligence_pilot import IntelligencePilotObservation, IntelligencePilotEvaluation
from app.services.quant.shadow_backtest import _load_closes


def _avg(vals: list[float]) -> float | None:
    vals = [v for v in vals if v is not None]
    return round(sum(vals) / len(vals), 3) if vals else None


async def _load_joined(db: AsyncSession) -> list[dict]:
    rows = (await db.execute(
        select(
            IntelligencePilotObservation.symbol, IntelligencePilotObservation.as_of_date,
            IntelligencePilotObservation.as_of_bar_date, IntelligencePilotObservation.conflict_bucket,
            IntelligencePilotObservation.highest_impact_0_100, IntelligencePilotObservation.aggregate_confidence_0_100,
            IntelligencePilotObservation.event_positive_count, IntelligencePilotObservation.event_negative_count,
            IntelligencePilotObservation.signal_count, IntelligencePilotObservation.triage_count,
            IntelligencePilotObservation.announcement_count,
            IntelligencePilotEvaluation.horizon_days, IntelligencePilotEvaluation.stock_return_pct,
            IntelligencePilotEvaluation.relative_return_pct, IntelligencePilotEvaluation.actual_direction_absolute,
            IntelligencePilotEvaluation.actual_direction_relative,
        )
        .select_from(IntelligencePilotObservation)
        .join(IntelligencePilotEvaluation, IntelligencePilotEvaluation.observation_id == IntelligencePilotObservation.id)
    )).all()
    return [dict(r._mapping) for r in rows]


def _impact_bucket(v: float) -> str:
    if v >= 80:
        return "80-100"
    if v >= 60:
        return "60-79"
    if v >= 40:
        return "40-59"
    return "<40"


def _confidence_bucket(v: float) -> str:
    if v >= 90:
        return "90+"
    if v >= 80:
        return "80-89"
    if v >= 70:
        return "70-79"
    return "<70"


async def signal_bucket_report(db: AsyncSession) -> list[dict]:
    """Signal-strength (conflict) bucket -> avg absolute/relative return, per horizon."""
    rows = await _load_joined(db)
    grouped: dict[tuple[str, int], list[dict]] = defaultdict(list)
    for r in rows:
        grouped[(r["conflict_bucket"], r["horizon_days"])].append(r)

    report = []
    for (bucket, horizon), items in sorted(grouped.items()):
        report.append({
            "signal_bucket": bucket, "horizon_days": horizon, "n": len(items),
            "avg_absolute_return_pct": _avg([r["stock_return_pct"] for r in items]),
            "avg_relative_return_pct": _avg([r["relative_return_pct"] for r in items]),
        })
    return report


async def impact_calibration_report(db: AsyncSession) -> list[dict]:
    rows = await _load_joined(db)
    grouped: dict[tuple[str, int], list[dict]] = defaultdict(list)
    for r in rows:
        grouped[(_impact_bucket(r["highest_impact_0_100"]), r["horizon_days"])].append(r)

    report = []
    for (bucket, horizon), items in sorted(grouped.items()):
        report.append({
            "impact_bucket": bucket, "horizon_days": horizon, "n": len(items),
            "avg_absolute_return_pct": _avg([r["stock_return_pct"] for r in items]),
            "avg_relative_return_pct": _avg([r["relative_return_pct"] for r in items]),
        })
    return report


def _evidence_call(pos: int, neg: int) -> str | None:
    """The bucket's implied directional call — None for balanced/no-signal
    rows, which have no clear call to grade."""
    if pos > neg:
        return "up"
    if neg > pos:
        return "down"
    return None


async def confidence_calibration_report(db: AsyncSession) -> list[dict]:
    """Only rows where confidence was actually available — no fabrication.
    Accuracy is graded only for rows with a clear directional call
    (balanced-conflict rows have none, and are excluded from the
    accuracy denominator, not counted as wrong)."""
    rows = [r for r in await _load_joined(db) if r["aggregate_confidence_0_100"] is not None]
    grouped: dict[tuple[str, int], list[dict]] = defaultdict(list)
    for r in rows:
        grouped[(_confidence_bucket(r["aggregate_confidence_0_100"]), r["horizon_days"])].append(r)

    report = []
    for (bucket, horizon), items in sorted(grouped.items()):
        callable_items = [r for r in items if _evidence_call(r["event_positive_count"], r["event_negative_count"]) is not None]
        hits = sum(1 for r in callable_items if _evidence_call(r["event_positive_count"], r["event_negative_count"]) == r["actual_direction_absolute"])
        report.append({
            "confidence_bucket": bucket, "horizon_days": horizon, "n": len(items),
            "n_with_clear_call": len(callable_items),
            "direction_accuracy_pct": round(100 * hits / len(callable_items), 1) if callable_items else None,
            "avg_relative_return_pct": _avg([r["relative_return_pct"] for r in items]),
        })
    return report


async def multi_event_report(db: AsyncSession) -> list[dict]:
    rows = await _load_joined(db)
    grouped: dict[tuple[str, int], list[dict]] = defaultdict(list)
    for r in rows:
        total_events = r["event_positive_count"] + r["event_negative_count"]
        key = "3+" if total_events >= 3 else str(total_events) if total_events > 0 else "0"
        grouped[(key, r["horizon_days"])].append(r)

    report = []
    for (bucket, horizon), items in sorted(grouped.items()):
        report.append({
            "event_count_bucket": bucket, "horizon_days": horizon, "n": len(items),
            "avg_relative_return_pct": _avg([r["relative_return_pct"] for r in items]),
        })
    return report


async def event_price_confirmation_report(db: AsyncSession, horizon_days: int = 20) -> list[dict]:
    """Event x Price quadrant — the analysis the owner wants most.
    Price momentum = trailing 20-bar return sign as of the observation's
    as_of_bar_date, same no-lookahead computation Phase 2C/2D use
    (closes[:idx+1] only)."""
    rows = [r for r in await _load_joined(db) if r["horizon_days"] == horizon_days]

    momentum_cache: dict[str, list] = {}
    quadrants: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        evidence_dir = (
            "positive" if r["conflict_bucket"] in ("all_positive", "mostly_positive") else
            "negative" if r["conflict_bucket"] in ("all_negative", "mostly_negative") else
            None
        )
        if evidence_dir is None:
            continue   # balanced_conflict / no_signal excluded from this specific quadrant view

        symbol = r["symbol"]
        if symbol not in momentum_cache:
            momentum_cache[symbol] = None   # placeholder, filled lazily below via caller-provided db
        quadrants.setdefault(evidence_dir, []).append(r)

    # Resolve price momentum lazily per symbol (needs db access — done here rather than in _load_joined to keep that function purely a join)
    out = []
    for evidence_dir, items in quadrants.items():
        for price_dir in ("positive", "negative"):
            bucket_items = []
            for r in items:
                mom = await _price_momentum(db, r["symbol"], r["as_of_bar_date"])
                if mom == price_dir:
                    bucket_items.append(r)
            out.append({
                "event_direction": evidence_dir, "price_direction": price_dir, "horizon_days": horizon_days,
                "n": len(bucket_items),
                "avg_relative_return_pct": _avg([r["relative_return_pct"] for r in bucket_items]),
            })
    return out


_series_cache: dict[str, list] = {}


async def _price_momentum(db: AsyncSession, symbol: str, as_of_bar_date) -> str:
    if symbol not in _series_cache:
        _series_cache[symbol] = await _load_closes(db, symbol)
    series = _series_cache[symbol]
    dates = [d for d, _ in series]
    from bisect import bisect_left
    idx = bisect_left(dates, as_of_bar_date)
    if idx >= len(dates) or dates[idx] != as_of_bar_date or idx < 20:
        return "unknown"
    closes = [c for _, c in series[: idx + 1]]
    trailing_20 = closes[-21:]
    return "positive" if trailing_20[-1] > trailing_20[0] else "negative"
