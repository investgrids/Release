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

# RETIRED tags (owner decision 2026-08-29 / 2026-09-27) — kept as literal
# historical constants only (real, already-persisted snapshot rows carry
# these exact strings forever; never rewritten). Neither is selected as
# "current" by get_latest_snapshot() anymore — see
# MARKETRIPPLE_SCORE_METHODOLOGY_VERSION below, which superseded both on
# 2026-09-27 as part of the owner's "one score calculation" unification.
BANKING_METHODOLOGY_VERSION = "BANKING_V1"
NONBANK_INDUSTRIAL_METHODOLOGY_VERSION = "NONBANK_INDUSTRIAL_V2"

# MARKETRIPPLE_SCORE_V1 (owner instruction, 2026-09-27) — the ONE current
# methodology identifier for every supported company, replacing the two
# separate tags above. Banking and every NONBANK_INDUSTRIAL_SECTORS sector
# now compute their headline number via the exact same shared function
# (engine.py's compute_headline) and the exact same disclosed weights
# (8/15, 4/15, 3/15) — sector-specific code still produces the raw
# Financial Strength/Valuation/Market Behaviour PillarScores themselves
# (genuinely different raw metrics for Banking vs. Industrial), but the
# headline composition, rating bands and missing-pillar rule are now
# identical across every sector, so one identifier covers all of them.
# get_latest_snapshot() selects ONLY this tag going forward — real history
# under BANKING_V1/NONBANK_INDUSTRIAL_V2 stays queryable directly but can
# never be mistaken for a current-methodology row again.
MARKETRIPPLE_SCORE_METHODOLOGY_VERSION = "MARKETRIPPLE_SCORE_V1"


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
    # Comparability rule (2026-09-26 audit finding, generalized into the
    # ONE shared headline function by the 2026-09-27 "one score
    # calculation" unification): a renormalized partial-pillar score is not
    # comparable to a full one — the real, measured evidence for this
    # (scripts/marketripple_score_shadow_pillar_comparability.py, now
    # archival) showed dropping a single pillar materially moves both the
    # score and rank position. engine.py's compute_headline() enforces this
    # directly: `score` stays None unless all 3 required pillars
    # (Financial Strength, Valuation, Market Behaviour) produced a real
    # number — never a renormalized subset, for any sector — even though
    # `pillars` still carries every real per-pillar result that WAS
    # produced. pillar_coverage_status is "complete" | "partial" |
    # "insufficient"; pillar_coverage_message is the real, human-readable
    # reason (e.g. "Partial coverage — 2 of 3 required pillars") a caller
    # should show in place of a combined number.
    pillar_coverage_status: str = "insufficient"
    pillar_coverage_message: str = "No pillar produced a real score for this symbol."
