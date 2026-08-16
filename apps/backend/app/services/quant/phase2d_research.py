"""
Phase 2D research evaluation — reads QuantResearchPrediction/
QuantResearchEvaluation only, never writes back, never touches
PredictionRecord/PredictionEvaluation or prediction_evaluator.py.

Answers the owner's four framed product questions directly:
  1. Does any simple quant signal survive five years?          -> year_stability
  2. Is relative-to-Nifty prediction better than absolute?      -> accuracy (both columns, per model/horizon)
  3. Does model agreement meaningfully increase accuracy?       -> agreement
  4. Is the signal stable enough to be worth taking toward production? -> synthesis of the above three

Coverage is reported everywhere accuracy is reported (owner's explicit
instruction: a model that predicts less often isn't comparable on
accuracy alone without knowing how often it actually produced a call).
"""
from __future__ import annotations

from collections import Counter, defaultdict

import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.quant_research import QuantResearchPrediction, QuantResearchEvaluation
from app.services.quant.phase2d_backtest import RUN_TAG, _year_bucket, _DIRECTION_TO_RELATIVE_LABEL


async def _load_rows(db: AsyncSession) -> list[dict]:
    rows = (await db.execute(
        select(
            QuantResearchPrediction.symbol, QuantResearchPrediction.model_name, QuantResearchPrediction.as_of_date,
            QuantResearchPrediction.direction, QuantResearchPrediction.expected_return,
            QuantResearchPrediction.sector, QuantResearchPrediction.own_trend_regime,
            QuantResearchEvaluation.horizon_days, QuantResearchEvaluation.stock_return_pct,
            QuantResearchEvaluation.relative_return_pct,
            QuantResearchEvaluation.actual_direction_absolute, QuantResearchEvaluation.actual_direction_relative,
            QuantResearchEvaluation.correct_absolute, QuantResearchEvaluation.correct_relative,
        )
        .select_from(QuantResearchPrediction)
        .join(QuantResearchEvaluation, QuantResearchEvaluation.prediction_id == QuantResearchPrediction.id)
        .where(QuantResearchPrediction.run_tag == RUN_TAG)
    )).all()
    return [dict(r._mapping) for r in rows]


async def _load_predictions_count_by_model(db: AsyncSession) -> dict[str, int]:
    rows = (await db.execute(
        select(QuantResearchPrediction.model_name, QuantResearchPrediction.id)
        .where(QuantResearchPrediction.run_tag == RUN_TAG)
    )).all()
    counts: dict[str, int] = defaultdict(int)
    for r in rows:
        counts[r.model_name] += 1
    return dict(counts)


def _rank_ic(rows: list[dict], return_field: str) -> float | None:
    pairs = [(r["expected_return"], r[return_field]) for r in rows
             if r["expected_return"] is not None and r[return_field] is not None]
    if len(pairs) < 10:
        return None
    s = pd.DataFrame(pairs, columns=["pred", "actual"])
    ic = s["pred"].rank().corr(s["actual"].rank())
    return None if pd.isna(ic) else round(float(ic), 3)


def _balanced_accuracy(rows: list[dict], direction_field: str, actual_field: str, labels: tuple[str, ...]) -> float | None:
    recalls = []
    for label in labels:
        actual = [r for r in rows if r[actual_field] == label]
        if not actual:
            continue
        hits = sum(1 for r in actual if r[direction_field] == label)
        recalls.append(100 * hits / len(actual))
    return round(sum(recalls) / len(recalls), 1) if recalls else None


async def compute_accuracy_report(db: AsyncSession) -> list[dict]:
    """One row per (model, horizon) — coverage + absolute + relative
    accuracy + rank IC for both outcome types."""
    rows = await _load_rows(db)
    produced = await _load_predictions_count_by_model(db)

    grouped: dict[tuple[str, int], list[dict]] = defaultdict(list)
    for r in rows:
        grouped[(r["model_name"], r["horizon_days"])].append(r)

    report = []
    for (model, horizon), items in sorted(grouped.items()):
        n_produced = produced.get(model, 0)
        n_eval = len(items)
        abs_conclusive = [r for r in items if r["actual_direction_absolute"] is not None]
        rel_conclusive = [r for r in items if r["actual_direction_relative"] is not None]
        abs_hits = sum(1 for r in abs_conclusive if r["direction"] == r["actual_direction_absolute"])
        rel_hits = sum(1 for r in rel_conclusive
                        if _DIRECTION_TO_RELATIVE_LABEL.get(r["direction"]) == r["actual_direction_relative"])

        report.append({
            "model": model, "horizon_days": horizon,
            "predictions_produced": n_produced, "evaluations_available": n_eval,
            "coverage_pct": round(100 * n_eval / n_produced, 1) if n_produced else None,
            "absolute_accuracy_pct": round(100 * abs_hits / len(abs_conclusive), 1) if abs_conclusive else None,
            "absolute_balanced_accuracy_pct": _balanced_accuracy(abs_conclusive, "direction", "actual_direction_absolute", ("up", "down", "sideways")),
            "absolute_rank_ic": _rank_ic(abs_conclusive, "stock_return_pct"),
            "relative_accuracy_pct": round(100 * rel_hits / len(rel_conclusive), 1) if rel_conclusive else None,
            "relative_balanced_accuracy_pct": _balanced_accuracy(
                [{**r, "direction": _DIRECTION_TO_RELATIVE_LABEL.get(r["direction"])} for r in rel_conclusive],
                "direction", "actual_direction_relative", ("outperform", "underperform", "inline"),
            ),
            "relative_rank_ic": _rank_ic(rel_conclusive, "relative_return_pct"),
        })
    return report


async def compute_year_stability_report(db: AsyncSession) -> list[dict]:
    """One row per (model, horizon, year_bucket) — answers "did the edge
    survive every year, or was one year (or the five-year average)
    carrying it."""
    rows = await _load_rows(db)
    for r in rows:
        r["year_bucket"] = _year_bucket(r["as_of_date"])

    grouped: dict[tuple[str, int, str], list[dict]] = defaultdict(list)
    for r in rows:
        grouped[(r["model_name"], r["horizon_days"], r["year_bucket"])].append(r)

    report = []
    for (model, horizon, year), items in sorted(grouped.items()):
        abs_conclusive = [r for r in items if r["actual_direction_absolute"] is not None]
        rel_conclusive = [r for r in items if r["actual_direction_relative"] is not None]
        abs_hits = sum(1 for r in abs_conclusive if r["direction"] == r["actual_direction_absolute"])
        rel_hits = sum(1 for r in rel_conclusive
                        if _DIRECTION_TO_RELATIVE_LABEL.get(r["direction"]) == r["actual_direction_relative"])
        report.append({
            "model": model, "horizon_days": horizon, "year": year, "n": len(items),
            "absolute_accuracy_pct": round(100 * abs_hits / len(abs_conclusive), 1) if abs_conclusive else None,
            "relative_accuracy_pct": round(100 * rel_hits / len(rel_conclusive), 1) if rel_conclusive else None,
        })
    return report


async def compute_agreement_report(db: AsyncSession, horizon_days: int) -> list[dict]:
    """Groups the 4 models' calls per (symbol, as_of_date), buckets by
    size of the largest same-direction group (4/4, 3/4, 2/4-or-less —
    the last bucket folds true 2-2 splits and 2-1-1 weak leans together,
    matching how the owner framed it), and reports accuracy of the
    MODAL direction's call in each bucket — both absolute and relative.
    Answers: does consensus size predict accuracy better than any single
    model does."""
    rows = await _load_rows(db)
    at_horizon = [r for r in rows if r["horizon_days"] == horizon_days]

    by_symbol_date: dict[tuple[str, object], list[dict]] = defaultdict(list)
    for r in at_horizon:
        by_symbol_date[(r["symbol"], r["as_of_date"])].append(r)

    buckets: dict[str, list[dict]] = defaultdict(list)
    for (_symbol, _date), items in by_symbol_date.items():
        if len(items) != 4:   # a model's own eligibility can occasionally differ (e.g. no_outcome row) — only grade complete quads
            continue
        counts = Counter(r["direction"] for r in items)
        modal_direction, modal_count = counts.most_common(1)[0]
        bucket = "4/4" if modal_count == 4 else "3/4" if modal_count == 3 else "2/4_or_split"

        actual_absolute = items[0]["actual_direction_absolute"]
        actual_relative = items[0]["actual_direction_relative"]
        buckets[bucket].append({
            "modal_direction": modal_direction,
            "correct_absolute": (modal_direction == actual_absolute) if actual_absolute is not None else None,
            "correct_relative": (
                _DIRECTION_TO_RELATIVE_LABEL.get(modal_direction) == actual_relative
                if actual_relative is not None else None
            ),
        })

    report = []
    for bucket_name in ("4/4", "3/4", "2/4_or_split"):
        items = buckets.get(bucket_name, [])
        abs_conclusive = [r for r in items if r["correct_absolute"] is not None]
        rel_conclusive = [r for r in items if r["correct_relative"] is not None]
        report.append({
            "agreement_bucket": bucket_name,
            "horizon_days": horizon_days,
            "n": len(items),
            "absolute_accuracy_pct": round(100 * sum(1 for r in abs_conclusive if r["correct_absolute"]) / len(abs_conclusive), 1) if abs_conclusive else None,
            "relative_accuracy_pct": round(100 * sum(1 for r in rel_conclusive if r["correct_relative"]) / len(rel_conclusive), 1) if rel_conclusive else None,
        })
    return report
