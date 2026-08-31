"""
Common scoring contracts — the owner's own S2-A spec, verbatim shape.

PillarStatus reflects how much of a pillar's PROPOSED metric set was
actually real and usable for this symbol, never how "good" the result
looks — a bank with 0 real signals and a bank with a strongly negative
real score are both COMPLETE if every proposed input was available; a
bank missing 8 of 12 proposed Financial Strength metrics is PARTIAL
regardless of what the 4 available ones say.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from enum import Enum


class PillarStatus(str, Enum):
    COMPLETE = "COMPLETE"          # every proposed metric for this pillar was real and used
    PARTIAL = "PARTIAL"            # some proposed metrics real, some missing
    INSUFFICIENT = "INSUFFICIENT"  # too few real metrics to compute a defensible pillar score at all


METHODOLOGY_VERSION = "s2-2026-08-25"

# S4.5 (owner decision, 2026-08-29) — Banking gets its own versioned
# methodology tag once its peer universe and quality rules are frozen,
# separate from the generic placeholder above (which other, not-yet-built
# sectors still use). Bumping this is how a future real methodology change
# (a different peer universe, a new metric) becomes traceable on every
# already-computed score, instead of silently reinterpreting old results.
BANKING_METHODOLOGY_VERSION = "BANKING_V1"


@dataclass
class PillarScore:
    name: str
    score: float | None            # 0-100, or None when INSUFFICIENT
    coverage_pct: float            # real metrics used / metrics proposed for this pillar, 0-100
    status: PillarStatus
    metrics_used: list[str] = field(default_factory=list)
    metrics_missing: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    as_of: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    methodology_version: str = METHODOLOGY_VERSION
    detail: dict = field(default_factory=dict)  # real, traceable intermediate values — never hidden


@dataclass
class MarketRippleScore:
    symbol: str
    score: float | None             # 0-100, or None when not enough pillars are usable at all
    label: str | None               # "Strong" / "Positive" / "Neutral" / "Cautious" / None
    publishable: bool               # explicit gate — see module docstring; False for the whole S2 phase
    publish_reason: str             # why publishable is what it is, always populated
    pillars: dict[str, PillarScore]
    weights: dict[str, float]       # candidate weights actually used for this computation
    overall_coverage_pct: float
    methodology_version: str = METHODOLOGY_VERSION
    calculated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    # S4.5 (owner decision, 2026-08-29) — real, structural fields (not
    # buried in a detail dict) so the same bank can never silently get one
    # score from a 5-bank endpoint and another from the Company page: the
    # peer population a score was actually computed against travels with
    # the score itself. peer_universe is the real symbol list actually
    # used for this computation (== ALL_ELIGIBLE_NSE_BANKS for the Banking
    # V1 default; a caller-supplied peer_group when explicitly overridden).
    peer_universe: list[str] = field(default_factory=list)
    peer_universe_count: int = 0
    peer_universe_as_of: date | None = None
