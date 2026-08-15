"""
Company signal synthesis — brief §10.

Same reuse-first approach as sector_synthesis.py: aggregates existing
EvidenceClusters by company symbol (from Event.companies,
CompanyAnnouncement.symbol, AICompanySignal.symbol, Opportunity's
resolved companies via the opportunity_refs cluster already carries) —
no new scoring formula invented, no BUY/SELL output (brief §10 is
explicit on both points).

`state` is a semantic category, not a UI string — High Conviction Watch
only when evidence is both substantial (>=3 clusters) AND uncontradicted
(no negative-direction cluster also touching this company); anything
with real contradictory evidence becomes "mixed" rather than being
allowed to look uncontested (brief §12, reused identically to
sector_synthesis's mixed-direction handling).

Phase 1B refinement (pre-commit): every symbol is validated against
_is_real_symbol() (app/services/aipe/company_score_engine.py) — the
same canonical NSE-universe check already used to backstop every other
consumer of AICompanySignal (rankings, stats, historical) — before it
can enter this ranking at all. Real, live pollution this backstops:
"NSE_SEBI", "NSE:NIFTY50", "SENSEX", and other regulator/index/exchange
pseudo-tags that upstream article extraction sometimes writes into
AICompanySignal.symbol are not tradable companies and must not appear
as one here. This filters ONLY the company-ranking entry point — an
excluded symbol's underlying evidence stays exactly where it already
was (sector signals, risks, new-since-close, evidence_refs all key off
the cluster, not the company list), so e.g. a SEBI regulatory
announcement remains fully visible everywhere except as a fake
"company" called NSE_SEBI.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.services.aipe.company_score_engine import _is_real_symbol
from app.services.weekend_intelligence.dedup import EvidenceCluster

HIGH_CONVICTION_WATCH = "high_conviction_watch"
POSITIVE_WATCH = "positive_watch"
MONITOR = "monitor"
MIXED = "mixed"
RISK_WATCH = "risk_watch"


@dataclass
class CompanySignal:
    symbol: str
    state: str  # one of the module-level constants above
    signal_strength: str  # low | medium | high
    confidence: float
    evidence_count: int
    key_reasons: list[str] = field(default_factory=list)
    opportunity_refs: list[dict] = field(default_factory=list)
    event_refs: list[dict] = field(default_factory=list)
    announcement_refs: list[dict] = field(default_factory=list)
    company_signal_refs: list[dict] = field(default_factory=list)
    news_refs: list[dict] = field(default_factory=list)
    risk_flags: list[str] = field(default_factory=list)


def _strength_bucket(evidence_count: int) -> str:
    if evidence_count >= 4:
        return "high"
    if evidence_count >= 2:
        return "medium"
    return "low"


def _refs_by_source_type(cluster: EvidenceCluster, source_type: str) -> list[dict]:
    return [
        {"source_type": m.source_type, "source_id": m.source_id}
        for m in cluster.members if m.source_type == source_type
    ]


def synthesize_companies(clusters: list[EvidenceCluster]) -> list[CompanySignal]:
    by_symbol: dict[str, list[EvidenceCluster]] = {}
    for cluster in clusters:
        for symbol in cluster.companies:
            if not _is_real_symbol(symbol):
                continue
            by_symbol.setdefault(symbol, []).append(cluster)

    signals: list[CompanySignal] = []
    for symbol, symbol_clusters in by_symbol.items():
        positive = sum(1 for c in symbol_clusters if c.net_direction in ("positive", "bullish"))
        negative = sum(1 for c in symbol_clusters if c.net_direction in ("negative", "bearish"))
        evidence_count = len(symbol_clusters)
        has_contradiction = positive > 0 and negative > 0

        risk_flags: list[str] = []
        if has_contradiction:
            risk_flags.append("conflicting_evidence")
        if evidence_count == 1:
            risk_flags.append("single_cluster_thesis")

        unique_source_types = {st for c in symbol_clusters for st in c.source_types}
        if len(unique_source_types) <= 1 and evidence_count >= 2:
            risk_flags.append("single_source_type")

        if has_contradiction:
            state = MIXED
        elif negative and not positive:
            state = RISK_WATCH
        elif positive and evidence_count >= 3 and len(unique_source_types) >= 2:
            state = HIGH_CONVICTION_WATCH
        elif positive:
            state = POSITIVE_WATCH
        else:
            state = MONITOR

        base_confidence = min(0.9, 0.2 + 0.15 * evidence_count)
        if has_contradiction:
            base_confidence *= 0.6
        if len(unique_source_types) <= 1:
            base_confidence *= 0.8  # brief §7 — don't reward duplicate-source-type ingestion

        key_reasons = [c.representative.title for c in sorted(
            symbol_clusters, key=lambda c: len(c.members), reverse=True
        )[:3]]

        signals.append(CompanySignal(
            symbol=symbol,
            state=state,
            signal_strength=_strength_bucket(evidence_count),
            confidence=round(base_confidence, 3),
            evidence_count=evidence_count,
            key_reasons=key_reasons,
            opportunity_refs=[r for c in symbol_clusters for r in _refs_by_source_type(c, "opportunity")],
            event_refs=[r for c in symbol_clusters for r in _refs_by_source_type(c, "event")],
            announcement_refs=[r for c in symbol_clusters for r in _refs_by_source_type(c, "announcement")],
            company_signal_refs=[r for c in symbol_clusters for r in _refs_by_source_type(c, "company_signal")],
            news_refs=[r for c in symbol_clusters for r in _refs_by_source_type(c, "news")],
            risk_flags=risk_flags,
        ))

    signals.sort(key=lambda s: (s.evidence_count, s.confidence), reverse=True)
    return signals
