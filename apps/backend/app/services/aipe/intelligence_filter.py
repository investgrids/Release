"""
Intelligence Filter — the gatekeeper of the AIPE.

Philosophy: Never ask "Is this news?" Always ask:
"Will this materially change an investor's understanding of the market?"

Hard NO: routine corporate events that have no investor action implication.
Hard YES: macro policy decisions, large institutional flows, systemic shocks.
Soft YES: significant earnings surprises, sector-wide structural changes.

Most NSE announcements should only update Company Pages and Knowledge Graph —
NOT create intelligence articles. We target 3-8 intelligence stories per
trading day, not 100 news items.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any

# ── Hard NO — routine corporate events ───────────────────────────────────────
_HARD_NO_PATTERNS = [
    r"\bagm\b",
    r"annual general meeting",
    r"board meeting\b(?! result)",      # board meeting, but not "board meeting results"
    r"\bdividend ex.?date\b",
    r"\brecord date\b",
    r"\bshare transfer\b",
    r"\bbook closure\b",
    r"appointment of\b",
    r"resignation of\b",
    r"\bchange of address\b",
    r"\breg(istrar|istry)\b",
    r"\bnotice to shareholders\b",
    r"\blosting of shares\b",
    r"\bpledge\b.*\bshares\b",
    r"\bscheme of arrangement\b",
    r"\bno\b.*\bmaterial impact\b",
    r"\bsurveillance measure\b",
    r"corporate action.*date",
    r"trading window",
    r"\bdemat\b",
    r"\bsebi complaint\b",
]

# ── Hard YES — macro/structural events that always get intelligence ───────────
_HARD_YES_PATTERNS = [
    r"\brbi\b.*\b(rate|repo|policy|monetary)\b",
    r"\brepo rate\b",
    r"\brate (cut|hike|unchanged|pause)\b",
    r"\bsebi\b.*\b(regulation|circular|ban|order)\b",
    r"\bunion budget\b",
    r"\binterim budget\b",
    r"\bfederal reserve\b|\bus fed\b|\bfomc\b",
    r"\bfii.*(buy|sell|net).*[₹\d].*cr",   # FII flows with amounts
    r"\bdii.*(buy|sell|net).*[₹\d].*cr",
    r"\boil\b.*(rise|fall|jump|crash|surge|drop).*[3-9]\d*%",  # big oil moves
    r"\bcircuit breaker\b|\bmarket halt\b",
    r"\bf&o ban\b|\bfo ban\b",
    r"\bdefault\b.*\b(credit|bond|payment)\b",
    r"\binsolvency\b",
    r"\bmerger|acquisition\b.*\b[₹\d].*cr",  # large M&A
    r"\bipо listing\b.*(?:premium|above|below).*%",
    r"\bgst\b.*\b(rate|revision|change)\b",
    r"\bcpi\b|\bwpi\b|\binflation\b.*data",
    r"\bgdp\b.*\b(data|growth|estimate)\b",
    r"\bindex\b.*(ban|inclusion|exclusion)",  # Nifty/MSCI index changes
    r"\bmsci\b|\bftse\b.*india",
]

# ── Minimum thresholds ────────────────────────────────────────────────────────
_MIN_URGENCY       = 6   # EventTriage.urgency  (0-10 scale)
_MIN_IMPACT_SCORE  = 6.0 # Event.impact_score   (0-10 scale)
_MIN_CONFIDENCE    = 60  # percent
_FII_THRESHOLD_CR  = 1000  # FII/DII net flow ≥ ₹1000 Cr


def _text(event: dict[str, Any]) -> str:
    return " ".join([
        (event.get("headline") or event.get("title") or ""),
        (event.get("one_liner") or event.get("summary") or ""),
    ]).lower()


def _is_hard_no(text: str) -> bool:
    return any(re.search(p, text) for p in _HARD_NO_PATTERNS)


def _is_hard_yes(text: str) -> bool:
    return any(re.search(p, text) for p in _HARD_YES_PATTERNS)


def should_generate_intelligence(
    event: dict[str, Any],
    source: str = "triage",
) -> tuple[bool, str]:
    """
    Returns (should_generate: bool, reason: str).

    event can be either an EventTriage dict or an Event dict.
    source: "triage" | "event"
    """
    text = _text(event)

    # Step 1: Hard NO — stop immediately
    if _is_hard_no(text):
        return False, "Routine corporate event — no investor action implication"

    # Step 2: Hard YES — generate immediately
    if _is_hard_yes(text):
        return True, "Macro/structural intelligence trigger confirmed"

    # Step 3: Threshold checks
    if source == "triage":
        urgency = int(event.get("urgency") or 0)
        importance = int(event.get("importance") or 0)
        market_impact = (event.get("market_impact") or "").lower()
        is_structural = bool(event.get("is_structural"))

        if urgency < _MIN_URGENCY:
            return False, f"Urgency too low ({urgency} < {_MIN_URGENCY})"
        if market_impact == "low":
            return False, "Market impact classified as low"
        # High urgency + structural = publish
        if urgency >= 8 or is_structural:
            return True, f"High urgency ({urgency}) / structural event"
        # Medium urgency needs additional validation
        if urgency >= _MIN_URGENCY and importance >= 6:
            return True, f"Urgency {urgency} + importance {importance} cleared threshold"
        return False, f"Insufficient intelligence signal (urgency={urgency}, importance={importance})"

    else:  # raw Event
        impact = float(event.get("impact_score") or 0)
        confidence = float(event.get("confidence") or 0) * 100
        sectors = event.get("sectors") or []

        if impact < _MIN_IMPACT_SCORE:
            return False, f"Impact score {impact} < {_MIN_IMPACT_SCORE}"
        if confidence < _MIN_CONFIDENCE:
            return False, f"Confidence {confidence}% < {_MIN_CONFIDENCE}%"
        if impact >= 8.0 and confidence >= 75:
            return True, f"High impact ({impact}) + confidence ({confidence:.0f}%)"
        if len(sectors) >= 3 and impact >= 6.5:
            return True, f"Multi-sector ({len(sectors)}) event with impact {impact}"
        return False, f"Insufficient intelligence value (impact={impact}, conf={confidence:.0f}%)"


def filter_triage_batch(
    triage_events: list[dict[str, Any]],
    max_per_cycle: int = 3,
) -> list[tuple[dict, str]]:
    """
    Filter a batch of triage events. Returns list of (event, reason) tuples
    that passed the intelligence filter, sorted by urgency descending.
    Enforces max_per_cycle limit.
    """
    passed: list[tuple[dict, str, int]] = []
    for ev in triage_events:
        ok, reason = should_generate_intelligence(ev, source="triage")
        if ok:
            passed.append((ev, reason, int(ev.get("urgency") or 0)))

    passed.sort(key=lambda x: x[2], reverse=True)
    return [(ev, reason) for ev, reason, _ in passed[:max_per_cycle]]
