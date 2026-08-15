"""
Historical analogue integration — brief §13.

Reuses historical_memory_service.find_similar_events() completely
unmodified. Per the Phase 1 architecture doc §10's already-established
decision (confirmed again by this brief: "prefer... highest-ranked
evidence clusters", "do not call it for every low-value news item"),
this builds ONE combined query from the weekend's most significant
clusters rather than calling the matcher once per cluster — the same
"combined weekend state" pattern opening_prediction_service.py's own
_gather_historical() already uses for an analogous purpose.

"Significant" here means: the cluster contains a Critical/High-priority
Event member (evidence.py's normalize_event carries this as
impact_strength when the aggregator supplies it — see aggregator.py),
OR the cluster has at least 3 members (a real multi-source
confirmation, not one low-signal mention). Everything else is excluded
from the query construction, though it can still appear elsewhere in
the snapshot (sector/company signals, changes) — historical matching is
just not run for it.

IMPORTANT — what "similarity" actually is here: find_similar_events()
is a STRUCTURED MULTI-FACTOR POINT SCORE over 6 dimensions (category
30pts, sector-overlap Jaccard 25pts, sentiment 15pts, market regime
15pts, rate trend 8pts, crude trend 7pts = 100 max —
historical_memory_service.py's own module docstring and
compute_similarity()). It is NOT an embedding/vector similarity lookup
— there is no embedding model or vector store anywhere in this path.
Calling it "embedding-based" (as an earlier draft of the Phase 1B
completion report did) was a documentation error, not a description of
the real implementation; this docstring exists partly to stop that
mischaracterization from recurring.

That point-score shape matters for why a real weekend can legitimately
score 0 analogues even with hundreds of evidence items: `_build_query`
below only ever populates 2 of the 6 dimensions (sectors, sentiment —
worth at most 25+15=40 of the 100 points before this refinement; now
also `category` when real Event.category data exists, since that field
does exist on the Event model but was not being read here). The other
3 dimensions (market_regime, interest_rate_trend, crude_trend) have no
corresponding data anywhere in Phase 1B's evidence layer at all — no
VIX/rate/regime feed is wired into any of the 6 source normalizers —
so 15+8+7=30 points are structurally unavailable, not merely unused.
Populating them with a guess would be exactly the kind of fabrication
brief §20 and this module's own sibling files (risk_synthesis.py,
sector_synthesis.py) explicitly refuse to do elsewhere, so they stay
absent rather than invented.
"""
from __future__ import annotations

from collections import Counter

from app.services.historical_memory_service import (
    find_similar_events,
    get_verified_historical_events,
)
from app.services.weekend_intelligence.dedup import EvidenceCluster

_SIGNIFICANT_TIERS = {"Critical", "High"}
_MIN_CLUSTER_SIZE_WITHOUT_TIER = 3
_MAX_ANALOGUES = 5
_MIN_SIMILARITY = 20.0


def _is_significant(cluster: EvidenceCluster) -> bool:
    if any(m.impact_strength in _SIGNIFICANT_TIERS for m in cluster.members):
        return True
    return len(cluster.members) >= _MIN_CLUSTER_SIZE_WITHOUT_TIER


def _canonicalize_sectors(sectors: list[str], known_sectors: set[str]) -> list[str]:
    """compute_similarity()'s sector-overlap Jaccard is an exact-string
    set comparison — "oil and gas" (a real value seen from Phase 1B's
    own evidence sources) and "Oil & Gas" (the real seeded historical
    wording) never overlap even though they mean the same sector, purely
    because of casing. This corrects casing only, matching each sector
    case-insensitively against the REAL vocabulary already present in
    HistoricalMarketEvent (a small, fixed seed set) and substituting
    that row's own casing when found — never a guessed synonym. A
    punctuation difference like "and" vs "&" is NOT corrected (that
    would require an invented synonym table); such pairs are left
    unmatched, honestly, same as before this fix."""
    by_lower = {s.lower(): s for s in known_sectors}
    seen: list[str] = []
    for s in sectors:
        canonical = by_lower.get(s.lower(), s)
        if canonical not in seen:
            seen.append(canonical)
    return seen


def _build_query(significant: list[EvidenceCluster], known_sectors: set[str]) -> dict:
    sectors: list[str] = []
    for c in significant:
        for s in c.sectors:
            if s not in sectors:
                sectors.append(s)
    sectors = _canonicalize_sectors(sectors, known_sectors)

    directions = [c.net_direction for c in significant]
    pos = sum(1 for d in directions if d in ("positive", "bullish"))
    neg = sum(1 for d in directions if d in ("negative", "bearish"))
    if pos and not neg:
        sentiment = "bullish"
    elif neg and not pos:
        sentiment = "bearish"
    else:
        sentiment = "neutral"

    query = {"sectors": sectors[:6], "sentiment": sentiment}

    # category: only set from real Event.category values actually present
    # on significant clusters' members (majority vote among those that
    # have one) — most weekends will have none (this field is rarely
    # populated upstream today) and the key is simply omitted, never
    # defaulted to a guess.
    categories = [m.category for c in significant for m in c.members if m.category]
    if categories:
        query["category"] = Counter(categories).most_common(1)[0][0]

    return query


async def find_historical_analogues(clusters: list[EvidenceCluster]) -> list[dict]:
    """
    Returns find_similar_events()'s own result rows (id, similarity,
    key_lesson, etc.) — Phase 1B does not reshape them. Empty list when
    no cluster clears the significance bar (an ordinary, quiet weekend),
    or when find_similar_events itself finds nothing above
    min_similarity — both are legitimate, non-error outcomes. This
    function never lowers min_similarity or otherwise forces a match
    just to avoid returning empty (see module docstring on why 0 is
    often the honest answer).
    """
    significant = [c for c in clusters if _is_significant(c)]
    if not significant:
        return []

    seed_rows = await get_verified_historical_events(order_by_date_desc=False, limit=None)
    known_sectors = {s for row in seed_rows for s in (row.sectors or [])}

    query = _build_query(significant, known_sectors)
    if not query["sectors"] and query["sentiment"] == "neutral" and "category" not in query:
        return []  # nothing meaningful to match against

    return await find_similar_events(query, limit=_MAX_ANALOGUES, min_similarity=_MIN_SIMILARITY)
