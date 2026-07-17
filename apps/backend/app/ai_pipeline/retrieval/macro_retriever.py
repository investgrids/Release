"""
Macro Retriever — India VIX level and volatility regime, sourced from the
same `get_extended_indices()` call `market_retriever` already uses (Redis-
cached 5 min, so this doesn't duplicate the network round-trip in
practice). This is what lets the Decision Intelligence Engine populate
`vix_level`/`volatility_regime` in `ConfidenceFactors` — both hardcoded to
0.0/"normal" in Phase 1 since no macro signal existed yet.
"""
from __future__ import annotations

from app.ai_pipeline.contracts import Evidence
from app.ai_pipeline.registry import RETRIEVER_REGISTRY
from app.ai_pipeline.retrieval.base import RetrievalContext, RetrieverSpec
from app.services.market_data import get_extended_indices


def _vix_regime(vix: float) -> str:
    if vix <= 0:
        return "normal"
    if vix < 12:
        return "low"
    if vix < 18:
        return "normal"
    if vix < 25:
        return "high"
    return "very_high"


_REGIME_INTERPRETATION = {
    "low": "Low volatility — stable, low-uncertainty market conditions",
    "normal": "Normal volatility — typical market conditions",
    "high": "Elevated volatility — increased uncertainty and risk",
    "very_high": "Very high volatility — defensive positioning warranted",
}
_REGIME_POLARITY = {"low": "positive", "normal": "neutral", "high": "negative", "very_high": "negative"}


async def _fetch(ctx: RetrievalContext) -> list[Evidence]:
    try:
        indices = await get_extended_indices()
    except Exception:
        return []

    vix_row = next((i for i in indices if "VIX" in str(i.get("name", "")).upper()), None)
    if not vix_row:
        return []

    try:
        vix_value = float(str(vix_row.get("value", "0")).replace(",", ""))
    except (ValueError, TypeError):
        vix_value = 0.0
    if vix_value <= 0:
        return []

    regime = _vix_regime(vix_value)
    return [Evidence(
        id="macro:india_vix",
        source="macro",
        entity=None,
        claim=f"India VIX is at {vix_value:.1f} ({regime.replace('_', ' ')}). {_REGIME_INTERPRETATION[regime]}.",
        polarity=_REGIME_POLARITY[regime],
        magnitude=min(vix_value / 30.0, 1.0),
        confidence=0.75,
        timestamp=None,
        raw={"vix": vix_value, "regime": regime},
    )]


RETRIEVER_REGISTRY.register("macro")(RetrieverSpec(key="macro", fetch=_fetch, timeout_s=12.0))
