"""
Quantitative Intelligence Layer — Phase 2B.

Historical OHLCV -> Feature/Data Quality -> Quant Models (baselines today,
Kronos later, always shadow-mode) -> QuantSignal store -> Outcome
Evaluation (reuses app.services.prediction_service /
prediction_evaluator, no parallel framework) -> Qlib research (later,
external) -> production, only after a model earns it (Phase 2A §16).

No production_weight > 0 exists anywhere in this package yet. Everything
here writes PredictionRecord rows with experimental=True (see
db/models/predictions.py's own docstring on that column) and is excluded
from prediction_service.recompute_calibration()/get_stats() by that flag.
"""
