"""
Driver Ranking Engine — collapses fused evidence into a small, ranked list
of named drivers (e.g. "Government Defence Spending: 96"), the only signals
the answer template's executive summary is allowed to foreground.

Evidence is grouped by entity (or, for entity-less broad-market evidence, by
its source) since a "driver" is a named factor, not an individual fact.
Each evidence item's own score is `magnitude * confidence * source_weight`
(0-100 scale); a driver's score is the strongest member score plus a small
corroboration bonus when multiple pieces of evidence agree on direction —
multiple independent sources confirming the same driver is itself a real
signal, not just noise to average away.
"""
from __future__ import annotations

from app.ai_pipeline.contracts import DriverScore, Evidence

# Event evidence is AI-analyzed and entity-specific — weighted highest.
# News is timely but less structured. Broad market-mood evidence is the
# least specific to any one driver.
_SOURCE_WEIGHT = {
    "event": 1.0,
    "news": 0.75,
    "intelligence_publishing": 0.6,
}
_MAX_DRIVERS = 8
_CORROBORATION_BONUS_PER_EXTRA = 3.0
_CORROBORATION_BONUS_CAP = 10.0


def _label_for(entity: str | None, evidence: list[Evidence]) -> str:
    if entity:
        return entity
    # Entity-less evidence (e.g. overall market mood) — use its source as
    # a stand-in label so it can still surface as a driver.
    return evidence[0].source.replace("_", " ").title()


def _direction_for(evidence: list[Evidence]) -> str:
    polarities = [e.polarity for e in evidence]
    has_pos = "positive" in polarities
    has_neg = "negative" in polarities
    if has_pos and has_neg:
        return "mixed"
    if has_pos:
        return "tailwind"
    if has_neg:
        return "headwind"
    return "mixed"   # neutral/uncertain-only groups carry no clear direction


def rank(evidence: list[Evidence]) -> list[DriverScore]:
    groups: dict[str, list[Evidence]] = {}
    for e in evidence:
        key = e.entity or f"__source__:{e.source}"
        groups.setdefault(key, []).append(e)

    drivers: list[DriverScore] = []
    for key, items in groups.items():
        scored = [
            (e, e.magnitude * e.confidence * _SOURCE_WEIGHT.get(e.source, 0.5) * 100.0)
            for e in items
        ]
        best_evidence, best_score = max(scored, key=lambda t: t[1])

        direction = _direction_for(items)
        agreeing = sum(1 for e in items if e.polarity == best_evidence.polarity)
        bonus = min((agreeing - 1) * _CORROBORATION_BONUS_PER_EXTRA, _CORROBORATION_BONUS_CAP)
        final_score = round(min(best_score + bonus, 100.0), 1)

        label = _label_for(best_evidence.entity, items)
        drivers.append(DriverScore(
            label=label,
            score=final_score,
            contributing_evidence_ids=[e.id for e in items],
            direction=direction,
        ))

    drivers.sort(key=lambda d: d.score, reverse=True)
    return drivers[:_MAX_DRIVERS]
