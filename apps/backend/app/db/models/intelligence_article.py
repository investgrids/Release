"""
IntelligenceArticle — persisted output of the Autonomous Intelligence
Publishing Engine (AIPE).

Philosophy: articles are LIVING DOCUMENTS generated from Market Intelligence,
not from news. They evolve throughout the day via the Continuous Update Engine.

Lifecycle: generated → validated → published → updated* → merged | archived
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, Column, DateTime, Float, Integer, JSON, String, Text,
)

from app.db.base import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class IntelligenceArticle(Base):
    __tablename__ = "intelligence_articles"

    # ── Identity ──────────────────────────────────────────────────────────────
    id           = Column(String, primary_key=True, index=True)
    slug         = Column(String(512), nullable=True, index=True, unique=True)
    article_type = Column(String(32), nullable=False, default="event_analysis")
    # breaking | morning_intelligence | company_intelligence | sector_intelligence
    # theme_intelligence | policy_intelligence | ripple_intelligence
    # opportunity_intelligence | market_wrap | educational_intelligence
    # question_intelligence | historical_intelligence

    # ── Story grouping (multiple versions = same story) ───────────────────────
    story_id       = Column(String(64), nullable=True, index=True)
    # Date-based for daily stories: "2026-07-12"
    # Event-based for breaking: "rbi-rate-2026-07-12"
    story_version  = Column(Integer, nullable=False, default=1)
    parent_story_id = Column(String, nullable=True, index=True)
    # If this is an update, parent_story_id = original article id

    # ── Multi-angle fan-out ────────────────────────────────────────────────────
    # One triggering event can spawn several angle-specific articles (the
    # "primary" overview plus per-company / sector-rollup / evergreen spinoffs).
    # angle + angle_entity keep those siblings distinct in the duplicate
    # detector (which otherwise collapses same-event/same-type/similar-headline
    # rows); parent_event_group_id lets the frontend cluster all angles that
    # came from the same underlying event.
    angle               = Column(String(32), nullable=False, default="primary", index=True)
    # "primary" | "per_company" | "sector_rollup" | "evergreen"
    angle_entity        = Column(String(64), nullable=True)
    # company symbol (per_company) or sector name (sector_rollup); null otherwise
    parent_event_group_id = Column(String(64), nullable=True, index=True)
    is_evergreen        = Column(Boolean, nullable=False, default=False)

    # ── Lifecycle ─────────────────────────────────────────────────────────────
    lifecycle_status = Column(String(16), nullable=False, default="generated", index=True)
    # generated → validated → published → updated → merged | archived | failed
    status           = Column(String(16), nullable=False, default="draft", index=True)
    # draft | published | failed  (simplified for API consumers)
    update_count     = Column(Integer, nullable=False, default=0)
    merged_into      = Column(String, nullable=True)  # article ID if merged
    update_history   = Column(JSON, nullable=False, default=list)
    # [{"at": ISO, "version": n, "reason": "new data", "summary": "..."}]

    # ── Core content ──────────────────────────────────────────────────────────
    headline          = Column(String(512), nullable=False)
    executive_summary = Column(Text, nullable=True)
    key_takeaway      = Column(Text, nullable=True)
    why_it_matters    = Column(Text, nullable=True)
    what_happened     = Column(Text, nullable=True)

    # ── Structured sections ───────────────────────────────────────────────────
    companies_affected   = Column(JSON, nullable=False, default=list)
    sectors_affected     = Column(JSON, nullable=False, default=list)
    opportunities        = Column(JSON, nullable=False, default=list)
    risks                = Column(JSON, nullable=False, default=list)
    historical_events    = Column(JSON, nullable=False, default=list)
    ripple_effect        = Column(JSON, nullable=False, default=list)
    what_to_watch_next   = Column(JSON, nullable=False, default=list)
    faqs                 = Column(JSON, nullable=False, default=list)
    sources              = Column(JSON, nullable=False, default=list)

    # ── SEO Intelligence (Phase 3) — deterministic, derived from the
    # article's own real companies/sectors, never LLM-generated ───────────────
    headline_angle       = Column(String(24), nullable=True)
    primary_keyword      = Column(String(160), nullable=True)
    secondary_keywords   = Column(JSON, nullable=False, default=list)
    entity_keywords      = Column(JSON, nullable=False, default=list)
    question_keywords    = Column(JSON, nullable=False, default=list)
    internal_link_candidates = Column(JSON, nullable=False, default=list)

    # ── Relationships (auto-linked by Relationship Engine) ────────────────────
    related_article_ids  = Column(JSON, nullable=False, default=list)
    internal_links       = Column(JSON, nullable=False, default=list)
    related_companies    = Column(JSON, nullable=False, default=list)
    # [{"symbol": "HDFC", "name": "HDFC Bank", "link": "/companies/HDFC"}]
    related_events       = Column(JSON, nullable=False, default=list)
    # [{"event_id": "...", "title": "..."}]
    related_themes       = Column(JSON, nullable=False, default=list)
    # [{"theme": "Banking", "link": "/newsroom/themes"}]
    knowledge_graph_refs = Column(JSON, nullable=False, default=list)
    # Node IDs from intelligence_graph
    historical_refs      = Column(JSON, nullable=False, default=list)
    # IDs from historical_market_events — real evidence used
    prediction_refs      = Column(JSON, nullable=False, default=list)
    # IDs from prediction_records

    # ── SEO ───────────────────────────────────────────────────────────────────
    seo_title        = Column(String(512), nullable=True)
    meta_description = Column(Text, nullable=True)
    canonical_url    = Column(Text, nullable=True)
    json_ld          = Column(JSON, nullable=True)

    def touch_json_ld_modified(self, when: datetime) -> None:
        """
        Every content-updating code path (continuous_updater, comparison
        refresh, signal enrichment) bumps last_updated but json_ld was built
        once at publish time and never touched again — so dateModified stayed
        frozen at the original publish timestamp even after real content
        changes, which is exactly the freshness signal Google's Article/
        NewsArticle structured data is meant to convey. Reassigns the whole
        dict (not an in-place mutation) so SQLAlchemy's JSON column change
        tracking actually picks it up.
        """
        if not self.json_ld:
            return
        self.json_ld = {**self.json_ld, "dateModified": when.isoformat()}

    # ── Market context snapshot at generation time ────────────────────────────
    market_context   = Column(JSON, nullable=True)
    # {"nifty": ..., "mood": ..., "story": ..., "themes": [...], "session": "live"}
    mie_story_hash   = Column(String(64), nullable=True)
    # SHA1 of MIE story text — used for change detection by the updater

    # ── Trigger / source (from MIE, not raw events) ───────────────────────────
    trigger_event_id  = Column(String, nullable=True, index=True)
    trigger_triage_id = Column(String, nullable=True)
    trigger_type      = Column(String(32), nullable=True)
    # "mie_story_change" | "high_urgency_triage" | "theme_shift" | "scheduled"
    trigger_data      = Column(JSON, nullable=True)

    # ── Quality scores ────────────────────────────────────────────────────────
    event_score      = Column(Float, nullable=False, default=0.0)
    confidence_score = Column(Float, nullable=False, default=0.0)
    quality_score    = Column(Float, nullable=False, default=0.0)
    seo_score        = Column(Integer, nullable=False, default=0)

    # ── Validation ────────────────────────────────────────────────────────────
    validation_passed   = Column(Boolean, nullable=False, default=False)
    validation_results  = Column(JSON, nullable=True)
    validation_failures = Column(Integer, nullable=False, default=0)

    # ── Analytics ─────────────────────────────────────────────────────────────
    views            = Column(Integer, nullable=False, default=0)
    share_count      = Column(Integer, nullable=False, default=0)
    avg_time_on_page = Column(Float, nullable=True)
    organic_traffic  = Column(Integer, nullable=False, default=0)
    ctr              = Column(Float, nullable=True)
    search_rank      = Column(Integer, nullable=True)
    # Prediction tracking
    prediction_accuracy  = Column(Float, nullable=True)  # 0-1 after market outcome
    outcome_validated_at = Column(DateTime(timezone=True), nullable=True)

    # ── Timestamps ────────────────────────────────────────────────────────────
    published_at = Column(DateTime(timezone=True), nullable=True, index=True)
    last_updated = Column(DateTime(timezone=True), nullable=True)
    archived_at  = Column(DateTime(timezone=True), nullable=True)
    created_at   = Column(DateTime(timezone=True), default=_now, index=True)
