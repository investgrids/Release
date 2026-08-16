"""
Phase 2C — quant_research.py metric functions, offline (no DB, no network).

These pin down the metrics the owner explicitly asked for as an
alternative to the existing evaluator's verdict-weighted accuracy
(balanced accuracy, per-direction precision, rank IC, coverage,
magnitude-proxy calibration, sector/regime segmentation) — every
metric here is checked against a hand-computable synthetic example so
a future refactor can't silently change what these numbers mean.
"""
from __future__ import annotations

from app.services.quant.quant_research import (
    _precision, _recall, _balanced_accuracy, _rank_ic,
    _avg_return_by_bucket, _magnitude_calibration, _segment_report,
)


def _row(direction, actual_direction, expected_return=None, actual_move_pct=None, sector=None, regime=None):
    return {
        "direction": direction, "actual_direction": actual_direction,
        "expected_return": expected_return, "actual_move_pct": actual_move_pct,
        "sector": sector, "own_trend_regime": regime,
    }


def test_precision_counts_only_predictions_of_that_label():
    rows = [
        _row("up", "up"), _row("up", "down"), _row("up", "up"),
        _row("down", "down"),
    ]
    assert _precision(rows, "up") == 66.7   # 2/3 "up" calls were right
    assert _precision(rows, "down") == 100.0


def test_precision_is_none_when_label_never_predicted():
    rows = [_row("down", "down")]
    assert _precision(rows, "up") is None


def test_recall_counts_only_actual_occurrences_of_that_label():
    rows = [
        _row("up", "up"), _row("down", "up"), _row("down", "down"),
    ]
    assert _recall(rows, "up") == 50.0   # 2 actual "up"s, 1 correctly called


def test_balanced_accuracy_averages_per_class_recall():
    # up: 1/1 correct=100, down: 1/2 correct=50, sideways: 0/1=0 -> mean=50
    rows = [
        _row("up", "up"),
        _row("down", "down"), _row("up", "down"),
        _row("up", "sideways"),
    ]
    assert _balanced_accuracy(rows) == 50.0


def test_rank_ic_is_none_below_minimum_sample_size():
    rows = [_row("up", "up", expected_return=1.0, actual_move_pct=1.0) for _ in range(5)]
    assert _rank_ic(rows) is None


def test_rank_ic_positive_for_monotonic_agreement():
    rows = [_row("up", "up", expected_return=float(i), actual_move_pct=float(i) * 2) for i in range(12)]
    ic = _rank_ic(rows)
    assert ic is not None and ic > 0.9


def test_rank_ic_ignores_rows_without_a_numeric_expected_return():
    rows = [_row("up", "up", expected_return=None, actual_move_pct=1.0) for _ in range(12)]
    assert _rank_ic(rows) is None


def test_avg_return_by_bucket_groups_by_predicted_direction_not_actual():
    rows = [
        _row("up", "up", actual_move_pct=2.0),
        _row("up", "down", actual_move_pct=-1.0),   # still counts under "up" bucket — it's grouped by the CALL
        _row("down", "down", actual_move_pct=-3.0),
    ]
    out = _avg_return_by_bucket(rows)
    assert out["up"] == 0.5    # mean(2.0, -1.0)
    assert out["down"] == -3.0
    assert out["sideways"] is None


def test_magnitude_calibration_splits_on_median_absolute_return():
    # Small |expected_return| calls all wrong, large all right — the
    # split should show 0% vs 100%, not blended together.
    rows = (
        [_row("up", "down", expected_return=0.1) for _ in range(5)]
        + [_row("up", "up", expected_return=5.0) for _ in range(5)]
    )
    out = _magnitude_calibration(rows)
    assert out["small_magnitude_accuracy_pct"] == 0.0
    assert out["large_magnitude_accuracy_pct"] == 100.0


def test_magnitude_calibration_is_none_below_minimum_sample_size():
    rows = [_row("up", "up", expected_return=1.0) for _ in range(5)]
    out = _magnitude_calibration(rows)
    assert out["small_magnitude_accuracy_pct"] is None


def test_segment_report_groups_by_the_given_key_and_skips_missing_values():
    rows = [
        _row("up", "up", sector="IT"), _row("up", "down", sector="IT"),
        _row("down", "down", sector="Financials"),
        _row("up", "up", sector=None),   # no sector -> excluded from the segmentation
    ]
    out = _segment_report(rows, "sector")
    assert out["IT"]["n"] == 2
    assert out["IT"]["direction_accuracy_pct"] == 50.0
    assert out["Financials"]["n"] == 1
    assert out["Financials"]["direction_accuracy_pct"] == 100.0
    assert None not in out
