"""
Risk synthesis — brief §12, refined post-review into two separate
buckets (Phase 1B refinement, pre-commit): MARKET RISKS vs CONFIDENCE
WARNINGS. These answer different questions and were originally returned
as one undifferentiated list, which made "what should I actually worry
about in the market" indistinguishable from "how much should I trust
this particular synthesis run" — e.g. "RBI policy stance conflicts with
IT-sector earnings guidance" (a real market risk) and "Friday's close
snapshot is missing" (a statement about THIS run's own data quality, not
about the market) were interchangeable entries in the same list.

Market risks — synthesize_market_risks(): deliberately NOT a
bullish-only system: every sector/company signal carrying real
contradictory evidence (dedup.py's cluster-level "mixed" net_direction,
or company_synthesis's per-symbol contradiction check) surfaces here,
not just as a slightly-lower confidence number buried in a
positive-looking entry.

Confidence warnings — synthesize_confidence_warnings(): everything that
is about the SYNTHESIS PROCESS rather than the market itself — a missing
close baseline, evidence concentrated in one source type (both a
per-company thesis depending on a single source type, and now also a
whole-snapshot check), a weak/absent historical analogue, and thin
overall evidence volume.

Two risk types the brief lists — "negative policy impact" and "commodity
shock" — are deliberately NOT auto-detected as their own dedicated risk
type here: GovernmentPolicy carries no sentiment/direction field in this
codebase's schema (evidence.py's normalize_policy leaves it None), and
there is no commodity-evidence source wired into Phase 1A's evidence
normalizers at all. A policy or commodity-linked risk still surfaces
correctly through the ordinary "negative sector/company signal" path
whenever that evidence got clustered (dedup.py) with something that does
carry a real direction — inventing a separate keyword-based detector for
these two specific cases would be exactly the kind of heuristic
fabrication the brief elsewhere warns against.

Both synthesize_* functions return entries ranked by severity (high
first) then by evidence involvement, and cap the result — an
undifferentiated, unranked list of 42 risks (the real count observed in
Phase 1B's first local-DB run) is not "what actually matters," it is
"everything we detected," which is exactly the distinction this
refinement exists to fix.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from app.services.weekend_intelligence.company_synthesis import CompanySignal, MIXED, RISK_WATCH
from app.services.weekend_intelligence.materiality import DEFAULT_EVIDENCE_COUNT_THRESHOLD
from app.services.weekend_intelligence.sector_synthesis import SectorSignal

CONFLICTING_EVIDENCE = "conflicting_evidence"
SOURCE_CONCENTRATION = "source_concentration"
STALE_OR_MISSING_BASELINE = "stale_or_missing_baseline"
WEAK_HISTORICAL_ANALOGUE = "weak_historical_analogue"
INSUFFICIENT_EVIDENCE = "insufficient_evidence"
# Phase 1E hardening: a source table failed to read for THIS checkpoint
# (evidence_window.collect_evidence_since's per-source isolation) —
# distinct from SOURCE_CONCENTRATION (which is about the MIX of evidence
# that WAS successfully read being skewed, not about a read failure).
SOURCE_UNAVAILABLE = "source_unavailable"

# Human-readable label per EvidenceItem.source_type — used only to word
# the SOURCE_UNAVAILABLE warning; matches evidence_window.py's SOURCE_*
# constants exactly (not re-declared there to avoid a circular import,
# risk_synthesis.py already sits "above" evidence_window.py in the
# dependency graph).
_SOURCE_LABELS = {
    "event": "Event",
    "policy": "Government policy",
    "announcement": "Company announcement",
    "news": "News",
    "company_signal": "Company signal",
    "opportunity": "Opportunity",
}

_SEVERITY_RANK = {"high": 3, "medium": 2, "low": 1}

# A single undifferentiated bucket of 42 risks (Phase 1B's first real
# local-DB run) is noise, not signal — cap each bucket to what's actually
# worth a reader's attention, ranked by severity then evidence weight.
_MARKET_RISK_LIMIT = 10
_CONFIDENCE_WARNING_LIMIT = 8

# Below this share of total evidence concentrated in one source_type,
# a whole-snapshot "evidence concentrated in X" warning isn't worth
# raising — some skew is normal and expected (news/RSS is always the
# highest-volume source in this codebase). Only flag real dominance.
_SOURCE_CONCENTRATION_SHARE = 0.7
_SOURCE_CONCENTRATION_MIN_EVIDENCE = 10


@dataclass
class Risk:
    description: str
    risk_type: str
    severity: str  # low | medium | high
    evidence_refs: list[dict] = field(default_factory=list)
    related_sectors: list[str] = field(default_factory=list)
    related_companies: list[str] = field(default_factory=list)


def _rank_and_cap(risks: list[Risk], limit: int) -> list[Risk]:
    ranked = sorted(
        risks,
        key=lambda r: (_SEVERITY_RANK.get(r.severity, 0), len(r.evidence_refs)),
        reverse=True,
    )
    return ranked[:limit]


def synthesize_market_risks(
    sector_signals: list[SectorSignal], company_signals: list[CompanySignal],
) -> list[Risk]:
    """Real, market-relevant contradiction — a reader should be able to
    treat every entry here as "something about the market/a company",
    never "something about our own data quality" (see
    synthesize_confidence_warnings for that)."""
    risks: list[Risk] = []

    for s in sector_signals:
        if s.direction == "mixed":
            risks.append(Risk(
                description=f"{s.sector}: conflicting positive and negative evidence this weekend",
                risk_type=CONFLICTING_EVIDENCE,
                severity="high" if s.evidence_count >= 4 else "medium",
                evidence_refs=s.evidence_refs,
                related_sectors=[s.sector],
            ))

    for c in company_signals:
        if c.state == MIXED:
            risks.append(Risk(
                description=f"{c.symbol}: conflicting evidence — positive and negative signals both present",
                risk_type=CONFLICTING_EVIDENCE,
                severity="high" if c.evidence_count >= 4 else "medium",
                related_companies=[c.symbol],
            ))
        elif c.state == RISK_WATCH:
            risks.append(Risk(
                description=f"{c.symbol}: negative-only evidence this weekend",
                risk_type=CONFLICTING_EVIDENCE,
                severity="medium",
                related_companies=[c.symbol],
            ))

    return _rank_and_cap(risks, _MARKET_RISK_LIMIT)


def synthesize_confidence_warnings(
    company_signals: list[CompanySignal],
    *,
    baseline_available: bool,
    historical_analogue_count: int,
    total_evidence_count: int,
    source_type_counts: dict[str, int] | None = None,
    source_failures: list[str] | None = None,
) -> list[Risk]:
    """Everything here is about how much to trust THIS synthesis run,
    not about the market itself — a reader should be able to treat this
    whole list as "caveats on the numbers above", separate from the
    market risks list (see synthesize_market_risks)."""
    warnings: list[Risk] = []

    if not baseline_available:
        warnings.append(Risk(
            description="Last trading session's close snapshot is missing — synthesis is based on weekend evidence only, without a verified price/breadth baseline",
            risk_type=STALE_OR_MISSING_BASELINE,
            severity="high",
        ))

    # Phase 1E hardening: one plain-English warning per source that
    # failed to read this checkpoint (never silent — this is the whole
    # point of the refinement). Severity "medium", not "high": the
    # PRIOR snapshot (if any) remains the current one and the app stays
    # up — this is a temporary, this-run-only gap, not the kind of
    # structural gap STALE_OR_MISSING_BASELINE represents.
    for source in source_failures or []:
        label = _SOURCE_LABELS.get(source, source)
        warnings.append(Risk(
            description=f"{label} data was unavailable during this update.",
            risk_type=SOURCE_UNAVAILABLE,
            severity="medium",
        ))

    source_type_counts = source_type_counts or {}
    total_sourced = sum(source_type_counts.values())
    if total_sourced >= _SOURCE_CONCENTRATION_MIN_EVIDENCE:
        dominant_type, dominant_count = Counter(source_type_counts).most_common(1)[0]
        if dominant_count / total_sourced >= _SOURCE_CONCENTRATION_SHARE:
            warnings.append(Risk(
                description=(
                    f"Evidence concentrated in {dominant_type} "
                    f"({dominant_count}/{total_sourced} items, "
                    f"{round(100 * dominant_count / total_sourced)}%) — other source types are comparatively sparse this weekend"
                ),
                risk_type=SOURCE_CONCENTRATION,
                severity="medium",
            ))

    for c in company_signals:
        if "single_source_type" in c.risk_flags and c.evidence_count >= 3:
            # Only worth flagging once the thesis is substantial enough
            # (>=3 clusters) that its single-source-type dependence is
            # actually load-bearing — a lone single-cluster mention
            # already reads as low-confidence on its own (see
            # company_synthesis's confidence discount), no need to also
            # double-flag it as a concentration warning.
            warnings.append(Risk(
                description=f"{c.symbol}: thesis rests on a single evidence source type despite {c.evidence_count} clusters",
                risk_type=SOURCE_CONCENTRATION,
                severity="low",
                related_companies=[c.symbol],
            ))

    if total_evidence_count > 0 and historical_analogue_count == 0:
        warnings.append(Risk(
            description="No comparable historical analogue found for this weekend's dominant evidence",
            risk_type=WEAK_HISTORICAL_ANALOGUE,
            severity="low",
        ))

    if 0 < total_evidence_count < DEFAULT_EVIDENCE_COUNT_THRESHOLD:
        warnings.append(Risk(
            description=f"Evidence volume is thin ({total_evidence_count} item(s)) — synthesis has lower statistical support than a typical checkpoint",
            risk_type=INSUFFICIENT_EVIDENCE,
            severity="medium",
        ))

    return _rank_and_cap(warnings, _CONFIDENCE_WARNING_LIMIT)
