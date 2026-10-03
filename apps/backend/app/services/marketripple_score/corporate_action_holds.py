"""
Companies whose score is held back after a corporate action that breaks the
comparability of the inputs the score is built from.

Reviewed list, not an automatic detector: a measured sweep of what an
automatic rule would hide has to come first (it can't tell a demerger from a
genuine crash). A hold is removed by a deliberate decision, never by expiry.

HEG / HEGAM (added 2026-10-03): demerger effective 2026-09-07. Verified in the
data, not assumed — Yahoo's HEGAM.NS closes go 728.2 -> 272.2 (-62.6%) on that
day, unadjusted in both HEG.NS and HEGAM.NS, while the annual financial
statements are still the pre-demerger FY2026 ones. A score would divide a
post-demerger price by pre-demerger earnings (the old public 59.7 had a 96.9
"valuation" pillar for exactly that reason) and treat the demerger as a
crash. The market-history floor can't catch this: the series is long enough.
Both symbols are listed because snapshots exist under the old one (HEG,
renamed to HEGAM on 2026-09-22).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class ScoreHold:
    event_date: date
    headline: str
    message: str


_HEG = ScoreHold(
    event_date=date(2026, 9, 7),
    headline="Score on hold",
    message=(
        "HEG Advanced Materials completed a demerger on 7 September 2026. Its prices and financial "
        "statements from before and after that date aren't comparable yet, so MarketRipple is holding "
        "its score until post-demerger data is available."
    ),
)

SCORE_HOLDS: dict[str, ScoreHold] = {"HEG": _HEG, "HEGAM": _HEG}

REASON_CORPORATE_ACTION_HOLD = "CORPORATE_ACTION_HOLD"


def score_hold_for(symbol: str | None) -> ScoreHold | None:
    return SCORE_HOLDS.get((symbol or "").upper().split(".")[0])
