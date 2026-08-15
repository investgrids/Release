"""
Overall market bias — brief §18. A conservative directional LEAN across
this weekend's evidence, not an opening-point prediction — deliberately
operates on the already-aggregated sector/company signals (evidence_count
+ direction), not raw price data, and never touches a Nifty-points
number. Monday Pre-Market (a later, separately-scoped phase — brief
§38) is responsible for combining this lean with fresh morning market
data into an actual opening call.

Bucketing is by the net-lean RATIO (net / total directional evidence),
not raw counts — otherwise a weekend with 20 clusters split 11-to-9 would
look identical in strength to one split 2-to-0. "mixed" is reserved for
a near-even split with real volume on both sides (a genuine tension, not
just noise) — distinct from "neutral", which means little or no
directional evidence existed at all.
"""
from __future__ import annotations

from app.services.weekend_intelligence.company_synthesis import CompanySignal
from app.services.weekend_intelligence.sector_synthesis import SectorSignal

STRONG_POSITIVE = "strong_positive"
POSITIVE = "positive"
NEUTRAL = "neutral"
NEGATIVE = "negative"
STRONG_NEGATIVE = "strong_negative"
MIXED = "mixed"

# Minimum total directional evidence-weight before a near-even split is
# called "mixed" rather than "neutral" — a lone +1/-1 tie is noise, not a
# meaningful tension worth flagging as its own bias state.
_MIXED_MIN_TOTAL_WEIGHT = 4


def compute_overall_bias(
    sector_signals: list[SectorSignal], company_signals: list[CompanySignal],
) -> str:
    positive_weight = 0
    negative_weight = 0

    for s in sector_signals:
        if s.direction == "positive":
            positive_weight += s.evidence_count
        elif s.direction == "negative":
            negative_weight += s.evidence_count
        elif s.direction == "mixed":
            positive_weight += s.positive_evidence
            negative_weight += s.negative_evidence

    for c in company_signals:
        # CompanySignal doesn't split positive/negative sub-counts the
        # way SectorSignal does (brief §10's shape has no equivalent
        # field) — its evidence_count is attributed by state instead.
        if c.state in ("high_conviction_watch", "positive_watch"):
            positive_weight += c.evidence_count
        elif c.state == "risk_watch":
            negative_weight += c.evidence_count
        elif c.state == "mixed":
            positive_weight += c.evidence_count / 2
            negative_weight += c.evidence_count / 2

    total = positive_weight + negative_weight
    if total == 0:
        return NEUTRAL

    ratio = (positive_weight - negative_weight) / total

    if abs(ratio) < 0.2 and total >= _MIXED_MIN_TOTAL_WEIGHT:
        return MIXED
    if ratio >= 0.6:
        return STRONG_POSITIVE
    if ratio >= 0.2:
        return POSITIVE
    if ratio <= -0.6:
        return STRONG_NEGATIVE
    if ratio <= -0.2:
        return NEGATIVE
    return NEUTRAL
