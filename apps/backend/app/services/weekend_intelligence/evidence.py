"""
Evidence normalization — typed, source-agnostic view over existing durable
tables. See design doc §4: deliberately NOT a new persisted table — every
normalizer here is a pure mapping function over an already-durable row
(Event, GovernmentPolicy, CompanyAnnouncement, NewsArticle, AICompanySignal,
Opportunity), called fresh whenever the aggregator (Phase 1B) needs a
window of evidence. Follows the same "@dataclass, never invents evidence,
degrades gracefully" pattern already established by
app/services/ai_search/evidence.py's EvidenceBundle — reused, not
reinvented.

`score_kind` matters more than it might look: per
WEEKEND_INTELLIGENCE_PHASE1_ARCHITECTURE.md §8, roughly half of this
codebase's "confidence" numbers are LLM self-ratings or heuristics
dressed up as scores, not deterministic feature-based computations. A
materiality/synthesis layer that treats all of them as equally trustworthy
would be wrong. Every normalizer below states its classification and why.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.db.models.company_announcements import CompanyAnnouncement
from app.db.models.company_signal import AICompanySignal
from app.db.models.event import Event, GovernmentPolicy
from app.db.models.opportunity import Opportunity
from app.db.models_legacy import NewsArticle

# score_kind values — see module docstring.
DETERMINISTIC = "deterministic"
HEURISTIC = "heuristic"
LLM_SELF_RATED = "llm_self_rated"
DERIVED = "derived"
UNKNOWN = "unknown"


@dataclass
class EvidenceItem:
    source_type: str          # "event" | "policy" | "announcement" | "news" | "company_signal" | "opportunity"
    source_id: str
    observed_at: datetime     # see each normalizer for exactly which source column this is and why
    title: str
    summary: str | None = None
    companies: list[str] = field(default_factory=list)
    sectors: list[str] = field(default_factory=list)
    themes: list[str] = field(default_factory=list)
    direction: str | None = None        # "positive" | "negative" | "neutral" | None
    impact_strength: str | None = None  # e.g. an event's Critical/High/Medium/Low priority tier
    confidence: float | None = None
    quality: float | None = None
    score_kind: str = UNKNOWN
    reason: str | None = None
    # Real Event.category value when the source row carries one (only
    # Event has this field among the 6 source tables — GovernmentPolicy/
    # CompanyAnnouncement/NewsArticle/AICompanySignal/Opportunity have no
    # comparable column). Used by historical_integration.py to populate
    # find_similar_events()'s "category" query dimension with real data
    # instead of leaving it unset — never guessed from title/keywords.
    category: str | None = None


def _utc(dt: datetime | None) -> datetime | None:
    """Normalize a possibly-naive datetime to UTC-aware, matching this
    codebase's own convention (naive datetimes elsewhere are always
    treated as UTC — see engine.py::session_label_for, Phase 0)."""
    if dt is None:
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def normalize_event(row: Event, *, priority_tier: str | None = None) -> EvidenceItem:
    """
    Timestamp precedence (design doc §18's rule: real source timestamp,
    then published, then ingested — never silently ingestion-as-occurrence):
    event_date (the real "when it happened" field) when present, else
    published_at (ingestion-time in practice — see Phase 0/Phase 1 audits,
    `_create_events` stamps this at ingest, not the source's real date),
    which is always populated so this is a safe final fallback.

    impact_score/confidence come from scoring_engine.score_event_impact —
    a real, deterministic, feature-based scorer (its own explicit rule:
    "no score is ever invented") — hence DETERMINISTIC, not a guess.

    `priority_tier` (Critical/High/Medium/Low) is optional here on purpose
    — computing it requires a join to EventTriage for urgency/importance,
    which the caller (the evidence-window assembler) does once per batch
    rather than this per-row normalizer doing N+1 queries. Reuses
    engine.py's own `compute_priority` (the public alias the module
    itself says other code should call instead of re-implementing the
    cutoffs) — never a new Critical/High threshold invented here.
    """
    observed_at = _utc(row.event_date) or _utc(row.published_at)
    return EvidenceItem(
        source_type="event",
        source_id=row.id,
        observed_at=observed_at,
        title=row.title,
        summary=row.summary or row.description,
        companies=list(row.companies or []),
        sectors=list(row.sectors or []),
        impact_strength=priority_tier,
        confidence=row.confidence,
        score_kind=DETERMINISTIC,
        reason="scoring_engine.score_event_impact (feature-based, no score is ever invented)",
        category=row.category,
    )


def normalize_policy(row: GovernmentPolicy) -> EvidenceItem:
    """
    Timestamp: announcement_date is confirmed always NULL in this codebase
    (ingest_tasks.py always passes None — Phase 0/1 audit finding), so
    created_at (real ingestion time) is the only usable timestamp here,
    not a silent occurrence-time assumption — it's the honest fallback
    because the "real" field is a known, documented gap upstream, not
    something this normalizer is hiding.

    No score exists for GovernmentPolicy anywhere in this codebase —
    confidence/impact_strength stay None rather than fabricated.
    """
    return EvidenceItem(
        source_type="policy",
        source_id=str(row.id),
        observed_at=_utc(row.created_at),
        title=row.title,
        summary=row.summary,
        score_kind=UNKNOWN,
        reason="GovernmentPolicy carries no score in this codebase — none invented here",
    )


def normalize_announcement(row: CompanyAnnouncement) -> EvidenceItem:
    """
    Timestamp: announcement_date is real (exchange-sourced) per the Phase
    1 audit's finding for this specific model — used directly, with
    ingested_at only as the fallback for the rare row where it's NULL.

    impact_score is documented on the model itself as "0-10, AI-assigned"
    — an LLM self-rating, not a computed feature score, hence
    LLM_SELF_RATED (confidence here is that same 0-10 value rescaled to
    0-1, not an independently-derived confidence).
    """
    confidence = (row.impact_score / 10.0) if row.impact_score is not None else None
    direction = row.sentiment if row.sentiment in ("bullish", "bearish", "neutral") else None
    return EvidenceItem(
        source_type="announcement",
        source_id=row.id,
        observed_at=_utc(row.announcement_date) or _utc(row.ingested_at),
        title=row.subject,
        summary=row.description or row.ai_summary,
        companies=[row.symbol] if row.symbol else [],
        sectors=list(row.sectors or []),
        themes=list(row.themes or []),
        direction=direction,
        impact_strength="high" if row.is_high_impact else None,
        confidence=confidence,
        score_kind=LLM_SELF_RATED,
        reason="CompanyAnnouncement.impact_score is documented as AI-assigned, 0-10",
    )


def normalize_news(row: NewsArticle) -> EvidenceItem:
    """
    Timestamp: NewsArticle.published_at is a STRING column (design doc
    §18 flags this explicitly), source-format-dependent, not always
    parseable. Best-effort ISO parse; falls back to created_at (real
    ingestion-time DateTime) on any failure — documented as a fallback,
    not silently treated as the real occurrence time.

    impact_score is a fixed per-source-type constant assigned at
    ingestion (confirmed: NSE=7.5/6.5/7.0, RSS defaults to 6.5 —
    app/providers/{nse,rss,bse}_provider.py), not derived from this
    article's actual content at all — HEURISTIC at best, explicitly not
    DETERMINISTIC (that label is reserved for scoring_engine's real
    feature-based scorer).
    """
    observed_at = None
    if row.published_at:
        try:
            observed_at = datetime.fromisoformat(row.published_at.replace("Z", "+00:00"))
        except ValueError:
            observed_at = None
    observed_at = _utc(observed_at) or _utc(row.created_at)
    return EvidenceItem(
        source_type="news",
        source_id=row.id,
        observed_at=observed_at,
        title=row.headline,
        summary=row.summary,
        companies=list(row.companies or []),
        confidence=(row.impact_score / 10.0) if row.impact_score is not None else None,
        score_kind=HEURISTIC,
        reason="NewsArticle.impact_score is a fixed per-source-type constant, not content-derived",
    )


def normalize_company_signal(row: AICompanySignal) -> EvidenceItem:
    """
    Timestamp: signal_at is explicitly documented on the model as "source's
    published_at/created_at" — already the right real-source timestamp,
    denormalized so no join is needed here.

    score_kind depends on which half of AICompanySignal this row is (see
    design doc §8): article-sourced confidence is the LLM's own
    confidence_score, passed straight through (LLM_SELF_RATED);
    opportunity-sourced signed_magnitude/confidence are arithmetically
    derived from opportunity_generator's heuristic _score_opportunity
    formula (HEURISTIC), despite in-code comments elsewhere calling this
    "real" — this normalizer does not repeat that claim.
    """
    score_kind = LLM_SELF_RATED if row.source_type == "article" else HEURISTIC
    direction = "positive" if row.signed_magnitude > 0 else ("negative" if row.signed_magnitude < 0 else "neutral")
    # Phase 1B local-DB verification found real rows where the upstream
    # AI extraction (company_score_engine.py) couldn't resolve a company
    # and stored the literal string "N/A" rather than a real symbol (23
    # such rows in the local dev DB at review time). "N/A" is not a
    # resolvable company — treating it as one would create a fake "N/A"
    # entry in company_synthesis's output. This is the one place Phase 1B
    # filters it; the underlying AICompanySignal row and its real content
    # (reason, sector, direction) are still used, just not attributed to
    # a company that doesn't exist.
    symbol = row.symbol if row.symbol and row.symbol.strip().upper() != "N/A" else None
    return EvidenceItem(
        source_type="company_signal",
        source_id=f"{row.source_type}:{row.source_id}",
        observed_at=_utc(row.signal_at),
        title=row.reason or f"{symbol or 'unresolved company'} signal ({row.source_type})",
        companies=[symbol] if symbol else [],
        sectors=[row.sector] if row.sector else [],
        direction=direction,
        confidence=row.confidence,
        quality=row.quality,
        score_kind=score_kind,
        reason=(
            "AICompanySignal.confidence is the LLM's own confidence_score"
            if score_kind == LLM_SELF_RATED else
            "AICompanySignal.* (opportunity-sourced) is derived from _score_opportunity's heuristic formula"
        ),
    )


def normalize_opportunity(row: Opportunity) -> EvidenceItem:
    """
    Timestamp: created_at, deliberately — a new Opportunity row appearing
    is the relevant "new evidence" event; using updated_at instead would
    count every minor score nudge on an existing opportunity as fresh
    evidence, which overstates what actually changed (design doc §5:
    evidence-level deltas, not noisy field-level ones).

    opportunity_score/confidence are confirmed heuristic — a count-based
    formula (60 + event/company/sector counts), confidence derived
    arithmetically from that same score, not an independent signal (Phase
    1 audit §9). Companies are intentionally left empty here — resolving
    them requires a join to OpportunityCompany, which the evidence-window
    assembler does separately per design doc §4's "keep Phase 1A minimal."
    """
    return EvidenceItem(
        source_type="opportunity",
        source_id=str(row.id),
        observed_at=_utc(row.created_at),
        title=row.title,
        summary=row.summary,
        sectors=list(row.sectors or []),
        confidence=row.confidence,
        score_kind=HEURISTIC,
        reason="opportunity_score/confidence are a count-based heuristic formula, not independent evidence",
    )
