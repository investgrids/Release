"""
Shared impact_score scale normalization — used by both the events list/detail
API (app/api/events.py) and the event detail service (app/services/event_service.py)
so the two views can never disagree on the same event's score again.

The 5 hand-written demo events in app/db/seed.py (fixed IDs, never grows)
store impact_score on a legacy 0-10 scale; every real AIPE/pipeline event is
already 0-100. This used to be guessed from magnitude (score <= 10 => assume
legacy) — but a real pipeline event can genuinely score low (e.g. a routine
corporate announcement, confirmed via nse-d3f8b9d2fc scoring a real 7.5/100),
and that heuristic silently 10x'd correct low scores into fake high ones.
Keying off the actual known seed IDs instead removes the ambiguity entirely.
"""
from __future__ import annotations

SEED_EVENT_IDS = frozenset({
    "evt-rbi-june-2026", "evt-defence-budget-2026", "evt-solar-capacity-2026",
    "evt-it-deal-slowdown-2026", "evt-semiconductor-plc-2026",
})


def normalize_impact_score(event_id: str, score: float | None) -> float | None:
    """Normalize to 0-100 scale. None (not yet scored) stays None — never
    coerced to 0, which would misread as "confirmed zero impact"."""
    if score is None:
        return None
    if event_id in SEED_EVENT_IDS:
        return round(score * 10.0, 1)
    return round(score, 1)


def normalize_confidence(event_id: str, confidence: float | None) -> float | None:
    """Same legacy-scale split as impact_score, confirmed via real DB rows:
    seed events store confidence as a 0-1 fraction (0.93), every real
    pipeline event already stores 0-100 (65.0). None stays None."""
    if confidence is None:
        return None
    if event_id in SEED_EVENT_IDS:
        return round(confidence * 100.0, 1)
    return round(confidence, 1)
