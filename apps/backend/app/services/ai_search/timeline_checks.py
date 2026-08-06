"""
Pipeline-agnostic timeline-consistency checks — shared by V2
(ai_search_service.py) and V3 (ai_search/validation.py) so the two
pipelines' post-hoc checking can't silently diverge from each other again.

Every function here operates on a normalized `entries: list[tuple[str, str]]`
shape — (label, text) pairs — rather than either pipeline's own field
layout. Callers adapt their own structure (V3's `timeline_intelligence`
dict, V2's `timeline` list of {date, title, description}) into that shape
before calling, and decide their own repair/omit convention on the result —
this module only detects, it never mutates a caller's response dict.

P4 (2026-08-06): built to close three real, verified gaps — an
immediate-term entry contradicting the overall verdict's tone with no
detected repair (RBI banking-stocks report), a horizon label disagreeing
with a timeframe stated inside its own text (defense-budget report), and
near-duplicate boilerplate recycled across horizons (same report).
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher

_NEGATIVE_WORDS = {
    "decline", "crash", "fall", "drop", "weak", "bearish", "sell-off", "selloff",
    "underperform", "underperformed", "underperforming", "lagged", "retreated",
}
_POSITIVE_WORDS = {
    "rally", "surge", "strong growth", "bullish", "outperform", "breakout",
    "outperformed", "outperforming", "rebounded",
}

TIMELINE_DIFFERENTIATION_INSTRUCTION = (
    'Each timeline entry must say something genuinely different from the others — '
    "do not restate the same point in different words across horizons. Keep each "
    "entry's own stated timeframe consistent with its own label (e.g. don't write "
    '"3-6 months" inside a "1 week"/near-term entry).'
)


def tone(text: str) -> str | None:
    """Same conservative approach as the pre-existing entry-vs-entry check
    this module extends: only a clean, unmixed sentiment-word match counts
    — mixed or neutral text returns None rather than guessing."""
    t = (text or "").lower()
    neg = any(w in t for w in _NEGATIVE_WORDS)
    pos = any(w in t for w in _POSITIVE_WORDS)
    if neg and not pos:
        return "negative"
    if pos and not neg:
        return "positive"
    return None


def check_verdict_tense_contradiction(
    entries: list[tuple[str, str]], verdict_direction: str,
) -> list[str]:
    """Flags any entry whose tone flatly contradicts the overall verdict
    direction — the RBI case: an 'immediate' entry reading negative under a
    bullish/Strong Positive overall verdict, with nothing anywhere checking
    the two against each other. Conservative: only a clean, unhedged tone
    mismatch is flagged; neutral/mixed language is left alone."""
    direction = (verdict_direction or "neutral").lower()
    if direction not in ("bullish", "bearish"):
        return []
    verdict_tone = "positive" if direction == "bullish" else "negative"
    return [label for label, text in entries if tone(text) not in (None, verdict_tone)]


_NUM_RANGE_RE = re.compile(r"(\d+)\s*(?:-|–|to)\s*(\d+)\s*(day|week|month|year)s?", re.IGNORECASE)
_NUM_SINGLE_RE = re.compile(r"(\d+)\s*(day|week|month|year)s?", re.IGNORECASE)
_UNIT_DAYS = {"day": 1, "week": 7, "month": 30, "year": 365}


def _extract_window(text: str) -> tuple[float, float] | None:
    """Best-effort (lo_days, hi_days) window from free text — a range like
    '3-6 months' parses exactly; a single value like '12 months' becomes a
    loose ±50% band, since a single number in prose isn't a stated range,
    just an approximate point. Returns None when nothing extractable is
    found (vague phrasing like "over the coming quarter" is left alone
    rather than guessed at — matches this module's conservative-omit
    philosophy elsewhere)."""
    if not text:
        return None
    m = _NUM_RANGE_RE.search(text)
    if m:
        lo, hi, unit = int(m.group(1)), int(m.group(2)), m.group(3).lower()
        mult = _UNIT_DAYS.get(unit, 30)
        return (lo * mult, hi * mult)
    m = _NUM_SINGLE_RE.search(text)
    if m:
        val, unit = int(m.group(1)), m.group(2).lower()
        mult = _UNIT_DAYS.get(unit, 30)
        days = val * mult
        return (days * 0.5, days * 1.5)
    return None


def check_numeric_range_contradiction(
    entries: list[tuple[str, str]],
    horizon_days: dict[str, tuple[float, float]] | None = None,
) -> list[str]:
    """Flags entries whose own embedded numeric range clearly falls outside
    their own nominal horizon window — e.g. a 'one_to_three_months' entry
    (or a V2 '3-6 months' label) whose text says 'over the next 6-12
    months'. `horizon_days` gives V3's fixed horizon keys a precise nominal
    window; when a label isn't in that mapping (V2's freeform date labels
    like "3-6 months" have no fixed key), the window is instead derived
    from the label's own text. Only a range with zero overlap against the
    window is flagged — partial overlap and non-numeric phrasing are left
    alone, same false-positive-avoidance stance as the existing tone check."""
    flagged = []
    for label, text in entries:
        window = (horizon_days or {}).get(label) or _extract_window(label)
        if not window:
            continue
        stated = _extract_window(text)
        if not stated:
            continue
        win_lo, win_hi = window
        lo, hi = stated
        if hi < win_lo or lo > win_hi:
            flagged.append(label)
    return flagged


def check_near_duplicate_entries(
    entries: list[tuple[str, str]], threshold: float = 0.82,
) -> list[tuple[str, str]]:
    """Pairwise difflib similarity across entries — flags near-verbatim
    restatements (the defense-budget report's 'Immediate' and '1 Week'
    entries were near word-for-word identical). Returns the flagged
    (label_a, label_b) pairs; the caller decides what to do with them
    (omit one, omit both, log only) per its own repair convention."""
    texts = [(label, (text or "").strip()) for label, text in entries if (text or "").strip()]
    pairs: list[tuple[str, str]] = []
    for i in range(len(texts)):
        for j in range(i + 1, len(texts)):
            label_a, text_a = texts[i]
            label_b, text_b = texts[j]
            ratio = SequenceMatcher(None, text_a.lower(), text_b.lower()).ratio()
            if ratio >= threshold:
                pairs.append((label_a, label_b))
    return pairs
