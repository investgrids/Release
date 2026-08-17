"""
Development -> Historical Analogue Retrieval — Phase 6D V1.

Pure, on-demand, read-only. No new table, no sync-job wiring, no
significance gate. Reuses historical_memory_service.find_similar_events()
completely unmodified, following
weekend_intelligence/historical_integration.py's established query-
construction pattern (the direct precedent for "a synthesis system
builds a find_similar_events() query") — applied here to a single
Development instead of an aggregate of EvidenceClusters. Reuses that
module's own _canonicalize_sectors()/_real_interest_rate_trend() helpers
rather than re-implementing them.

Why no persistence: interest_rate_trend is explicitly a query-TIME
dimension in the existing precedent (fetched live from macro_rates, not
stored). Precomputing and storing analogue results at Development-
formation time would go stale the moment the rate trend, the seeded
historical set, or the matcher's own weights change — a Development
queried today should be compared against today's macro context, not
whatever it was when the Development first formed. AI Search actually
consuming this is Phase 6F's explicit job, not this module's.

Why no significance gate (unlike is_graph_worthy()/is_prediction_worthy()):
those gate real downside — graph bloat, a wrong directional price claim.
Historical retrieval is a cheap, deterministic, read-only lookup against
a small curated table with neither downside, and a Development that
isn't globally "significant" can still be exactly what a user is asking
AI Search about. Every Development is eligible.

Mixed direction: retrieval still runs (a genuinely mixed/conflicting
Development is often the MORE interesting historical question — "have
we seen similarly conflicting situations before" — not a reason to
refuse retrieval). Maps to "neutral" for the existing matcher (which
only understands bullish/bearish/neutral), the same treatment
historical_integration.py already gives an evenly-split cluster
aggregate. The original "mixed" state is preserved separately as
source_direction on the returned context, not erased by the neutral
mapping — Phase 6E (Evidence Reconciliation) may need to distinguish
true-neutral from high-conflict-mixed later, and this is where that
distinction would otherwise get lost.

market_regime and crude_trend are never populated — no live source for
either exists anywhere in this app today (same gap
historical_integration.py already documents), so they're honestly
omitted from the query rather than guessed.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.db.models.development import Development
from app.services.historical_memory_service import find_similar_events, get_verified_historical_events
from app.services.weekend_intelligence.historical_integration import (
    _canonicalize_sectors,
    _real_interest_rate_trend,
)

MAX_ANALOGUES = 5      # matches historical_integration.py's own _MAX_ANALOGUES
MIN_SIMILARITY = 20.0  # matches historical_integration.py's own _MIN_SIMILARITY

_DIRECTION_TO_SENTIMENT = {
    "positive": "bullish", "negative": "bearish", "neutral": "neutral", "mixed": "neutral",
}


@dataclass
class DevelopmentHistoricalContext:
    development_id: str
    source_direction: str | None  # the Development's own current_direction, unmapped — see module docstring
    query_used: dict              # exactly what was queried; only real, non-fabricated dimensions ever appear here
    analogues: list[dict] = field(default_factory=list)  # find_similar_events()'s own rows, unreshaped


async def build_historical_query(dev: Development, known_sectors: set[str]) -> dict:
    query: dict = {"sentiment": _DIRECTION_TO_SENTIMENT.get(dev.current_direction, "neutral")}

    sectors = _canonicalize_sectors(list(dev.sectors or []), known_sectors)
    if sectors:
        query["sectors"] = sectors[:6]

    if dev.category:
        query["category"] = dev.category

    interest_rate_trend = await _real_interest_rate_trend()
    if interest_rate_trend:
        query["interest_rate_trend"] = interest_rate_trend

    return query


async def find_similar_developments_context(dev: Development) -> DevelopmentHistoricalContext:
    seed_rows = await get_verified_historical_events(order_by_date_desc=False, limit=None)
    known_sectors = {s for row in seed_rows for s in (row.sectors or [])}

    query = await build_historical_query(dev, known_sectors)
    analogues = await find_similar_events(query, limit=MAX_ANALOGUES, min_similarity=MIN_SIMILARITY)

    return DevelopmentHistoricalContext(
        development_id=dev.id,
        source_direction=dev.current_direction,
        query_used=query,
        analogues=analogues,
    )
