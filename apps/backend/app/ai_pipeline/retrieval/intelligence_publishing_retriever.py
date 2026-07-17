"""
Intelligence Publishing Retriever — wraps the Market Intelligence Engine
(MIE), the codebase's existing "single source of truth" aggregator for
market mood, themes, and top triaged events. Contributes broad market-
context evidence (mood/direction/risk_level, top theme, top structural
events) that isn't tied to any specific entity in the query.
"""
from __future__ import annotations

from app.ai_pipeline.contracts import Evidence
from app.ai_pipeline.registry import RETRIEVER_REGISTRY
from app.ai_pipeline.retrieval.base import RetrievalContext, RetrieverSpec
from app.services.intelligence.engine import get_intelligence_state

_MOOD_POLARITY = {
    "bullish": "positive", "cautious bull": "positive",
    "bearish": "negative", "cautious bear": "negative", "panic": "negative",
    "uncertain": "uncertain", "sideways": "neutral",
}


async def _fetch(ctx: RetrievalContext) -> list[Evidence]:
    try:
        state = await get_intelligence_state()
    except Exception:
        return []
    if not state:
        return []

    evidence: list[Evidence] = []
    signals = state.get("signals", {}) or {}
    mood = str(signals.get("mood", "")).lower()

    if signals.get("mood"):
        evidence.append(Evidence(
            id="intelligence_publishing:market_mood",
            source="intelligence_publishing",
            entity=None,
            claim=f"Overall market mood is {signals.get('mood')} ({signals.get('direction', 'sideways')})",
            polarity=_MOOD_POLARITY.get(mood, "neutral"),
            magnitude=min(max(float(signals.get("confidence", 50)) / 100.0, 0.0), 1.0),
            confidence=min(max(float(signals.get("confidence", 50)) / 100.0, 0.0), 1.0),
            timestamp=None,
            raw=signals,
        ))

    # Full ranked theme list (not just the single top theme) — needed by
    # theme_discovery, where the user wants a spread of active themes, not
    # only whichever one is currently strongest.
    for theme in (state.get("themes") or [])[:8]:
        score = float(theme.get("score", 0) or 0)
        if score <= 0:
            continue
        evidence.append(Evidence(
            id=f"intelligence_publishing:theme:{theme.get('theme')}",
            source="intelligence_publishing",
            entity=theme.get("theme"),
            claim=(
                f"Active market theme: {theme.get('theme')} (score {score:.0f}, "
                f"momentum {theme.get('momentum', 'steady')})"
            ),
            polarity="positive" if theme.get("momentum") != "declining" else "negative",
            magnitude=min(max(score / 100.0, 0.0), 1.0),
            confidence=0.55,
            timestamp=None,
            raw=theme,
        ))

    for ev in (state.get("top_events") or [])[:5]:
        if float(ev.get("urgency", 0)) < 5:
            continue
        evidence.append(Evidence(
            id=f"intelligence_publishing:event:{ev.get('id')}",
            source="intelligence_publishing",
            entity=(ev.get("tickers") or [None])[0] if ev.get("tickers") else None,
            claim=ev.get("one_liner") or ev.get("headline", ""),
            polarity={"positive": "positive", "negative": "negative"}.get(ev.get("sentiment"), "neutral"),
            magnitude=min(max(float(ev.get("urgency", 5)) / 10.0, 0.0), 1.0),
            confidence=min(max(float(ev.get("confidence", 50)) / 100.0, 0.0), 1.0) or 0.5,
            timestamp=None,
            raw=ev,
        ))

    return evidence


RETRIEVER_REGISTRY.register("intelligence_publishing")(
    RetrieverSpec(key="intelligence_publishing", fetch=_fetch, timeout_s=20.0)
)
