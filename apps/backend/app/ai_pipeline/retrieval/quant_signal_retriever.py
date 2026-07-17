"""
Quantitative Signal Retriever — real backtested accuracy data from the
Prediction Learning Engine (`prediction_service`), not query-specific.
Answers "how reliable has this system's confidence scoring actually been
historically", which is the honest version of "historical probability" —
Phase 1 could only ever report 0 here since this retriever didn't exist.
"""
from __future__ import annotations

from app.ai_pipeline.contracts import Evidence
from app.ai_pipeline.registry import RETRIEVER_REGISTRY
from app.ai_pipeline.retrieval.base import RetrievalContext, RetrieverSpec
from app.services.prediction_service import get_calibration_data, get_stats


async def _fetch(ctx: RetrievalContext) -> list[Evidence]:
    try:
        calibration = await get_calibration_data()
    except Exception:
        calibration = {}
    try:
        stats = await get_stats()
    except Exception:
        stats = {}

    evidence: list[Evidence] = []
    for level, data in calibration.items():
        total = int(data.get("total", 0) or 0)
        if total < 5:
            continue   # too few samples at this confidence level to be a meaningful signal
        accuracy = float(data.get("accuracy_rate", 0) or 0)
        evidence.append(Evidence(
            id=f"quant_signal:calibration:{level}",
            source="quant_signal",
            entity=None,
            claim=(
                f"Past '{level}' confidence predictions ({total} tracked) were correct "
                f"{accuracy * 100:.0f}% of the time"
            ),
            polarity="positive" if accuracy >= 0.55 else ("negative" if accuracy < 0.4 else "neutral"),
            magnitude=min(max(accuracy, 0.0), 1.0),
            confidence=min(0.5 + total / 100.0, 0.9),   # more samples -> more trustworthy signal
            timestamp=None,
            raw=data,
        ))

    total_predictions = int(stats.get("total_predictions", 0) or 0)
    overall_accuracy_pct = stats.get("overall_accuracy")   # already 0-100, or None if inconclusive so far
    if total_predictions >= 10 and overall_accuracy_pct is not None:
        overall_accuracy = float(overall_accuracy_pct) / 100.0
        evidence.append(Evidence(
            id="quant_signal:overall_stats",
            source="quant_signal",
            entity=None,
            claim=f"System-wide prediction accuracy across {total_predictions} tracked predictions: {overall_accuracy_pct:.0f}%",
            polarity="positive" if overall_accuracy >= 0.55 else "neutral",
            magnitude=min(max(overall_accuracy, 0.0), 1.0),
            confidence=0.7,
            timestamp=None,
            raw=stats,
        ))

    return evidence


RETRIEVER_REGISTRY.register("quant_signal")(RetrieverSpec(key="quant_signal", fetch=_fetch, timeout_s=8.0))
