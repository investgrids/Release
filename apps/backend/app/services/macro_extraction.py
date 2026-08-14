"""
Macro-release extraction — parses real numeric figures (GST collections,
CPI/WPI/IIP prints, GDP growth, trade balance, fiscal deficit) out of PIB/
RBI press-release headline+summary text.

Deliberately conservative: every regex here is metric-specific and requires
an unambiguous number-with-unit next to a clear metric keyword. When a
headline doesn't match cleanly, extract_macro_release() returns None —
it never guesses a plausible-looking number. This is a real, if narrow,
extraction layer, not an LLM inferring a figure from prose (this codebase's
existing intelligence_filter.py FII/DII amount-threshold check follows the
same "extract with a tight regex or don't claim a value" pattern).

No expected/consensus value is ever populated — neither PIB nor RBI RSS
carries analyst consensus figures, and Phase 21's no-fabrication rule on
this specific field is absolute.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

# Structural sector sensitivity per metric — static domain knowledge (the
# same kind of thing already hand-encoded in ripple_service.py's fallback
# templates), not a per-release AI inference. Company-level exposure is
# deliberately NOT included here; that needs real per-company evidence this
# module has no way to establish from a headline alone.
SECTOR_SENSITIVITY: dict[str, list[str]] = {
    "CPI": ["Banking", "NBFC", "Auto", "Real Estate"],
    "WPI": ["Manufacturing", "Chemicals", "Metals"],
    "IIP": ["Manufacturing", "Capital Goods", "Infrastructure"],
    "GDP": ["Banking", "Auto", "FMCG", "Infrastructure"],
    "GST": ["Consumer Discretionary", "Logistics", "Retail"],
    "TRADE_BALANCE": ["IT Services", "Pharma", "Oil Marketing"],
    "FISCAL_DEFICIT": ["Banking", "Infrastructure", "PSU"],
    "EMPLOYMENT": ["Consumer Discretionary", "Real Estate"],
}

_IMPORTANCE: dict[str, str] = {
    "CPI": "High", "GDP": "Critical", "GST": "Medium", "WPI": "Medium",
    "IIP": "Medium", "TRADE_BALANCE": "Medium", "FISCAL_DEFICIT": "High",
    "EMPLOYMENT": "Medium",
}

_NUM = r"([\d]+(?:,\d{2,3})*(?:\.\d+)?)"

# (metric, unit, compiled_pattern) — pattern's group(1) is the release value.
_PATTERNS: list[tuple[str, str, re.Pattern]] = [
    ("GST", "₹ crore", re.compile(
        rf"\bgst\b.{{0,40}}?(?:collection|revenue|mop-up)?.{{0,20}}?(?:₹|rs\.?)\s*{_NUM}\s*(?:crore|cr\b)",
        re.IGNORECASE,
    )),
    ("CPI", "%", re.compile(
        rf"\bcpi\b.{{0,30}}?(?:inflation)?.{{0,20}}?(?:at|eases to|rises to|stands at|of|is)\s*{_NUM}\s*%",
        re.IGNORECASE,
    )),
    ("WPI", "%", re.compile(
        rf"\bwpi\b.{{0,30}}?(?:inflation)?.{{0,20}}?(?:at|eases to|rises to|stands at|of|is)\s*{_NUM}\s*%",
        re.IGNORECASE,
    )),
    ("IIP", "%", re.compile(
        rf"\biip\b.{{0,30}}?(?:grows|rises|contracts|declines|at)\s*(?:by\s*)?{_NUM}\s*%",
        re.IGNORECASE,
    )),
    ("GDP", "%", re.compile(
        rf"\bgdp\b.{{0,30}}?(?:growth)?.{{0,20}}?(?:at|of|estimated at|grows|expands)\s*(?:by\s*)?{_NUM}\s*%",
        re.IGNORECASE,
    )),
    ("TRADE_BALANCE", "$ billion", re.compile(
        rf"trade\s*(?:deficit|surplus)\b.{{0,30}}?(?:\$|usd)\s*{_NUM}\s*billion",
        re.IGNORECASE,
    )),
    ("FISCAL_DEFICIT", "%", re.compile(
        rf"fiscal\s*deficit\b.{{0,30}}?{_NUM}\s*%",
        re.IGNORECASE,
    )),
]

# "up from 4.8% in June" / "against $21.3 billion last month" style
# previous-value phrasing — same conservative approach, only matched right
# after a successful release_value match on the same text.
_PREVIOUS_PATTERNS = [
    re.compile(rf"(?:from|against)\s*{_NUM}\s*%", re.IGNORECASE),
    re.compile(rf"(?:from|against)\s*(?:\$|usd)\s*{_NUM}\s*billion", re.IGNORECASE),
    re.compile(rf"(?:from|against)\s*(?:₹|rs\.?)\s*{_NUM}\s*(?:crore|cr\b)", re.IGNORECASE),
]

_PERIOD_PATTERN = re.compile(
    r"\b((?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{4}|Q[1-4]\s*FY\s*\d{2,4})",
    re.IGNORECASE,
)


def _to_float(raw: str) -> float:
    return float(raw.replace(",", ""))


def extract_macro_release(
    headline: str, summary: str = "", *, source: str = "", url: str = "",
    published_at: str = "",
) -> dict[str, Any] | None:
    """Returns a dict ready to build a MacroRelease row, or None if no
    metric could be confidently extracted from the text. Never returns a
    partially-guessed value — a match either has a real number attached
    or the whole metric is skipped."""
    text = f"{headline} {summary}"

    for metric, unit, pattern in _PATTERNS:
        m = pattern.search(text)
        if not m:
            continue
        try:
            release_value = _to_float(m.group(1))
        except ValueError:
            continue

        previous_value = None
        for prev_pattern in _PREVIOUS_PATTERNS:
            pm = prev_pattern.search(text)
            if pm:
                try:
                    previous_value = _to_float(pm.group(1))
                except ValueError:
                    previous_value = None
                break

        period_match = _PERIOD_PATTERN.search(text)
        period = period_match.group(1) if period_match else None

        release_date = None
        if published_at:
            try:
                release_date = datetime.strptime(published_at, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except ValueError:
                release_date = None

        return {
            "metric": metric,
            "release_value": release_value,
            "previous_value": previous_value,
            "expected_value": None,  # never fabricated — see module docstring
            "unit": unit,
            "period": period,
            "geography": "India",
            "importance": _IMPORTANCE.get(metric),
            "affected_sectors": SECTOR_SENSITIVITY.get(metric, []),
            "affected_companies": [],
            "source": source,
            "source_url": url,
            "headline": headline,
            "raw_summary": summary,
            "release_date": release_date,
        }

    return None
