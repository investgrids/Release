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
    # Standard SEBI LODR board-meeting-intimation boilerplate — the subject
    # line NSE announcements use for "we're holding a board meeting whose
    # agenda includes approving quarterly results," not the results
    # themselves. Confirmed live (2026-08-10 audit): this exact fragment,
    # with no "board meeting" prefix surviving in the truncated headline,
    # was still reaching the priority engine's weak-keyword floor via
    # "results" alone.
    r"to consider and approve.*(financial results|unaudited results)",
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
    # FII/DII flows are NOT in this list — see _fii_dii_exceeds_threshold
    # below. They used to be two presence-only patterns here (matched as
    # soon as "fii"/"dii" + buy/sell/net + any digit + "cr" all appeared,
    # regardless of amount), which meant _FII_THRESHOLD_CR was a declared,
    # documented ₹1000 Cr business rule that literally nothing checked —
    # confirmed via re-audit grep: zero comparison sites anywhere in the
    # codebase. Moved to its own function so the threshold is real.
    r"\boil\b.*(rise|fall|jump|crash|surge|drop).*[3-9]\d*%",  # big oil moves
    r"\bcircuit breaker\b|\bmarket halt\b",
    r"\bf&o ban\b|\bfo ban\b",
    r"\bdefault\b.*\b(credit|bond|payment)\b",
    r"\binsolvency\b",
    # Re-audit (2026-08-13) fixes two bugs in this pattern:
    #  1. Missing grouping — `\bmerger|acquisition\b...` parses as
    #     `(\bmerger)|(acquisition\b...)`, so "merger" alone matched
    #     unconditionally (no amount required, and no TRAILING \b either —
    #     "mergers"/"mergerXYZ" would also match), while "acquisition"
    #     alone required the full `...cr` amount suffix. Wrapped both
    #     alternatives in one group with a boundary on each end.
    r"\b(merger|acquisition)\b.*\b[₹\d].*cr",  # large M&A
    # 2. "ipо listing" used a Cyrillic о (U+043E), not ASCII "o" — a
    #    copy-paste artifact that made this pattern silently never match
    #    the real string "ipo listing" it was written to catch. Confirmed
    #    via direct byte inspection during the re-audit.
    r"\bipo listing\b.*(?:premium|above|below).*%",
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


# Captures the rupee-crore amount next to an "fii"/"dii" mention (e.g. "FII
# sold ₹3,200 Cr" / "DII net buying at 1500 crore") so it can be compared
# against _FII_THRESHOLD_CR — not just checked for presence. .{0,60}? keeps
# the match from spanning past the flow figure that actually belongs to
# this fii/dii mention if the headline goes on to name a second, unrelated
# amount later in the sentence.
_FII_DII_AMOUNT_PATTERN = re.compile(
    r"\b(?:fii|dii)\b.{0,60}?[₹]?\s*([\d,]+(?:\.\d+)?)\s*(?:cr\b|crore\b)"
)


def _fii_dii_exceeds_threshold(text: str) -> bool:
    """True only when a real FII/DII flow amount is present AND meets the
    configured ₹1000 Cr threshold — not merely mentioned. text is already
    lowercased by _text() before reaching here."""
    m = _FII_DII_AMOUNT_PATTERN.search(text)
    if not m:
        return False
    try:
        amount = float(m.group(1).replace(",", ""))
    except ValueError:
        return False
    return amount >= _FII_THRESHOLD_CR


def _is_hard_yes(text: str) -> bool:
    return any(re.search(p, text) for p in _HARD_YES_PATTERNS) or _fii_dii_exceeds_threshold(text)


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

        # Audit fix (2026-08-12): the urgency<_MIN_URGENCY gate below used
        # to be unconditional, so a keyword-floor-elevated Critical/High
        # event (app.services.intelligence.engine.compute_priority's
        # _CRITICAL_KEYWORDS/_HIGH_KEYWORDS_STRONG, e.g. "war", "rbi",
        # "budget") with a low AI-assigned raw urgency was rejected here
        # before ever reaching filter_triage_batch's own Critical/High
        # rescue downstream — that rescue can't save an event that never
        # made it into the "passed" list in the first place. Confirmed
        # live: a real triaged event (urgency=1, headline containing
        # "war") computed to Critical via the keyword floor but would have
        # been silently rejected right here. _HARD_YES_PATTERNS above is a
        # second, independently-maintained "always important" keyword
        # list that had already drifted from engine.py's (no "war" match
        # among its patterns) — reusing compute_priority (the codebase's
        # own documented single source of truth for these tiers) instead
        # of patching yet another parallel keyword list closes that gap
        # for good, not just for this one example.
        from app.services.intelligence.engine import compute_priority
        from app.services.coverage_engine import is_must_cover
        headline = event.get("headline") or event.get("title") or ""
        _, priority_tier = compute_priority(urgency, importance, None, headline)
        if is_must_cover(priority_tier):
            return True, f"{priority_tier}-tier event (Intelligence Priority Queue)"

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
    Enforces max_per_cycle limit — EXCEPT for Critical/High-priority events
    (per app.services.intelligence.engine.compute_priority, the same tiers
    already used homepage-wide), which are never truncated by the per-
    cycle cap. This is the fix for the audit's core finding: an important
    event competing against 4+ other approved events in the same 5-min
    cycle used to be silently dropped just for not being in the top 3 by
    urgency — it may still land in a later cycle since the 3-hour lookback
    re-considers it, but there's no guarantee of that, so Critical/High
    events get a hard guarantee here instead of a probabilistic one.
    """
    from app.services.coverage_engine import classify, is_must_cover

    passed: list[tuple[dict, str, int]] = []
    for ev in triage_events:
        ok, reason = should_generate_intelligence(ev, source="triage")
        if ok:
            passed.append((ev, reason, int(ev.get("urgency") or 0)))

    passed.sort(key=lambda x: x[2], reverse=True)
    top = passed[:max_per_cycle]
    overflow_ids = {id(ev) for ev, _, _ in top}
    critical_overflow = [
        (ev, reason, urgency) for ev, reason, urgency in passed[max_per_cycle:]
        if id(ev) not in overflow_ids
        and is_must_cover(classify(urgency, int(ev.get("importance") or 0), ev.get("headline") or ev.get("title"))[1])
    ]
    return [(ev, reason) for ev, reason, _ in top + critical_overflow]
