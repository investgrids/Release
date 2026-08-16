"""
Quant Research evaluation view — Phase 2C.

A SEPARATE analysis layer, not a replacement for prediction_evaluator.py
(owner's explicit instruction: "The existing evaluator can remain
untouched... Kronos promotion should never be based mainly on the
63.3%-style weighted metric"). Reads the same PredictionRecord/
PredictionEvaluation rows prediction_evaluator.py already wrote —
this module only computes additional metrics over them, it never
writes a verdict/score of its own back to those tables.

Every metric here answers a specific critique from the Phase 2B
review:
  - direction_accuracy / balanced_accuracy / up_precision /
    down_precision — the strict, unweighted view (the review's #2:
    the existing evaluator's verdict scoring gives "sideways" a wider
    tolerance band, which flattered random_walk's 63.3% number).
  - rank_ic — Spearman correlation between each model's own
    `expected_return` and the realized `actual_move_pct`. Only
    computed over predictions that actually produced a numeric
    expected_return (random_walk always reports 0.0 by construction —
    included; but rows with expected_return=None are excluded, not
    imputed).
  - avg_realized_return_by_bucket — mean actual_move_pct grouped by
    the model's OWN predicted direction bucket, a check for "does the
    model's up/down call actually correspond to a different realized
    outcome on average."
  - coverage — fraction of generated predictions that reached a
    conclusive evaluation (actual_direction is not None) — a low
    coverage number is itself informative (evaluator couldn't resolve
    real price data for that horizon/symbol), not something to hide
    inside the accuracy denominator.
  - magnitude_calibration — NOT a probability-calibration curve (every
    shadow prediction here carries a uniform nominal confidence_score
    of 50 by design — Phase 2B/2C deliberately never fabricated a
    differentiated confidence signal for the baselines). Instead: are
    LARGER |expected_return| calls more accurate than smaller ones?
    Real, computed, honestly labeled as a proxy, not conflated with
    probability calibration.
  - Segmented by sector (universe.SECTOR) and by the symbol's own
    trailing-20-day trend regime (stored in confidence_factors at
    generation time — see phase2c_backtest.py; NOT the app's
    fragmented "market_regime" concept, Phase 2A §17).
"""
from __future__ import annotations

from collections import defaultdict

import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.predictions import PredictionRecord, PredictionEvaluation
from app.services.quant.phase2c_backtest import P2C_SUFFIX


async def _load_p2c_rows(db: AsyncSession) -> list[dict]:
    rows = (await db.execute(
        select(
            PredictionRecord.model_version, PredictionRecord.direction, PredictionRecord.expected_return,
            PredictionRecord.confidence_factors, PredictionEvaluation.horizon_days,
            PredictionEvaluation.actual_direction, PredictionEvaluation.actual_move_pct,
        )
        .join(PredictionEvaluation, PredictionEvaluation.prediction_id == PredictionRecord.id)
        .where(PredictionRecord.model_version.like(f"%{P2C_SUFFIX}"))
    )).all()
    out = []
    for r in rows:
        factors = r.confidence_factors or {}
        out.append({
            "model_version": r.model_version, "direction": r.direction, "expected_return": r.expected_return,
            "sector": factors.get("sector"), "own_trend_regime": factors.get("own_trend_regime"),
            "horizon_days": r.horizon_days, "actual_direction": r.actual_direction, "actual_move_pct": r.actual_move_pct,
        })
    return out


def _precision(rows: list[dict], predicted_label: str) -> float | None:
    called = [r for r in rows if r["direction"] == predicted_label and r["actual_direction"] is not None]
    if not called:
        return None
    hits = sum(1 for r in called if r["actual_direction"] == predicted_label)
    return round(100 * hits / len(called), 1)


def _recall(rows: list[dict], label: str) -> float | None:
    actual = [r for r in rows if r["actual_direction"] == label]
    if not actual:
        return None
    hits = sum(1 for r in actual if r["direction"] == label)
    return round(100 * hits / len(actual), 1)


def _balanced_accuracy(rows: list[dict]) -> float | None:
    recalls = [_recall(rows, label) for label in ("up", "down", "sideways")]
    real = [r for r in recalls if r is not None]
    return round(sum(real) / len(real), 1) if real else None


def _rank_ic(rows: list[dict]) -> float | None:
    """Spearman rank correlation, computed as Pearson correlation over
    rank-transformed values — mathematically identical to scipy's
    spearmanr, no scipy dependency needed (pandas' own method="spearman"
    requires scipy internally; this avoids adding it for one metric)."""
    pairs = [(r["expected_return"], r["actual_move_pct"]) for r in rows
             if r["expected_return"] is not None and r["actual_move_pct"] is not None]
    if len(pairs) < 10:   # too few points for a meaningful rank correlation
        return None
    s = pd.DataFrame(pairs, columns=["pred", "actual"])
    ic = s["pred"].rank().corr(s["actual"].rank())
    return None if pd.isna(ic) else round(float(ic), 3)


def _avg_return_by_bucket(rows: list[dict]) -> dict[str, float | None]:
    out = {}
    for label in ("up", "down", "sideways"):
        vals = [r["actual_move_pct"] for r in rows if r["direction"] == label and r["actual_move_pct"] is not None]
        out[label] = round(sum(vals) / len(vals), 3) if vals else None
    return out


def _magnitude_calibration(rows: list[dict]) -> dict[str, float | None]:
    """Real, computed proxy — NOT probability calibration (see module
    docstring). Splits by |expected_return| into small/large halves by
    RANK POSITION (not a value threshold) — a value-threshold split
    breaks when many rows share the same magnitude (e.g. random_walk's
    uniform 0.0), since a "<=" comparison against a tied median value
    would then dump every row into "small". Sorting rows and cutting at
    the midpoint index is robust to ties regardless of how the
    magnitudes are distributed."""
    have_return = [r for r in rows if r["expected_return"] is not None and r["actual_direction"] is not None]
    if len(have_return) < 10:
        return {"small_magnitude_accuracy_pct": None, "large_magnitude_accuracy_pct": None}
    ordered = sorted(have_return, key=lambda r: abs(r["expected_return"]))
    mid = len(ordered) // 2
    small, large = ordered[:mid], ordered[mid:]

    def acc(bucket):
        if not bucket:
            return None
        hits = sum(1 for r in bucket if r["direction"] == r["actual_direction"])
        return round(100 * hits / len(bucket), 1)

    return {"small_magnitude_accuracy_pct": acc(small), "large_magnitude_accuracy_pct": acc(large)}


def _segment_report(rows: list[dict], key: str) -> dict[str, dict]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        val = r.get(key)
        if val:
            groups[val].append(r)
    return {
        val: {
            "n": len(items),
            "direction_accuracy_pct": (
                round(100 * sum(1 for r in items if r["direction"] == r["actual_direction"]) /
                      max(1, sum(1 for r in items if r["actual_direction"] is not None)), 1)
                if any(r["actual_direction"] is not None for r in items) else None
            ),
        }
        for val, items in sorted(groups.items())
    }


async def compute_quant_research_report(db: AsyncSession) -> list[dict]:
    """One row per (model_version, horizon_days) — the primary Phase 2C
    output table."""
    all_rows = await _load_p2c_rows(db)

    grouped: dict[tuple[str, int], list[dict]] = defaultdict(list)
    for r in all_rows:
        grouped[(r["model_version"], r["horizon_days"])].append(r)

    report = []
    for (model_version, horizon_days), rows in sorted(grouped.items()):
        conclusive = [r for r in rows if r["actual_direction"] is not None]
        n = len(rows)
        n_conclusive = len(conclusive)
        direction_hits = sum(1 for r in conclusive if r["direction"] == r["actual_direction"])

        report.append({
            "model_version": model_version,
            "horizon_days": horizon_days,
            "n": n,
            "coverage_pct": round(100 * n_conclusive / n, 1) if n else None,
            "direction_accuracy_pct": round(100 * direction_hits / n_conclusive, 1) if n_conclusive else None,
            "balanced_accuracy_pct": _balanced_accuracy(conclusive),
            "up_precision_pct": _precision(conclusive, "up"),
            "down_precision_pct": _precision(conclusive, "down"),
            "rank_ic": _rank_ic(conclusive),
            "avg_realized_return_by_call": _avg_return_by_bucket(conclusive),
            "magnitude_calibration": _magnitude_calibration(conclusive),
            "by_sector": _segment_report(conclusive, "sector"),
            "by_own_trend_regime": _segment_report(conclusive, "own_trend_regime"),
        })
    return report
