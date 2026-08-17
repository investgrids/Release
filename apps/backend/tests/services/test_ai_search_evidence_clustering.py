"""
Phase 5E.5 — AI Search evidence independence.

Before this fix, EvidenceBundle.source_count (feeding both the star
rating in postprocess.compute_evidence_score and
ConfidenceFactors.source_count in postprocess.compute_confidence_breakdown)
counted raw Event/NewsArticle/policy rows with zero cross-source dedup.
Phase 5E's audit confirmed live that the same NSE filing can surface as
an Event row AND a NewsArticle row AND a CompanyAnnouncement row — 3
rows, 1 real development — inflating confidence as if 3 independent
sources agreed.

Fixed via the shared evidence-clustering primitive (5E.3, the same one
that fixed Opportunity Radar's scoring in 5E.4): EvidenceBundle now
carries development_count (clusters) alongside the unchanged
source_count/corroborating_source_count (raw rows), and confidence
scoring reads development_count instead.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.db.session import AsyncSessionLocal
from app.services.ai_search.evidence import EvidenceBundle, _apply_clustering
from app.services.ai_search.postprocess import compute_confidence_breakdown, compute_evidence_score
from app.services.confidence_service import ConfidenceFactors, calculate_confidence


def _bundle(events=None, news=None, announcements=None) -> EvidenceBundle:
    b = EvidenceBundle()
    b.events = events or []
    b.news = news or []
    b.announcements = announcements or []
    return b


def _now_str() -> str:
    return datetime.now(timezone.utc).strftime("%b %d, %Y")


# ── Core clustering behavior on the bundle ──────────────────────────────────

@pytest.mark.asyncio
async def test_event_and_news_for_same_filing_is_one_development():
    bundle = _bundle(
        events=[{"id": "e1", "title": "HDFC Bank board approves Q1 results, profit up 12%", "date": _now_str(),
                 "category": "corporate", "impact_score": 7.0}],
        news=[{"id": "n1", "headline": "HDFC Bank Q1 results: profit rises 12%, board approves",
               "published_at": datetime.now(timezone.utc).isoformat(), "source": "ET"}],
    )
    async with AsyncSessionLocal() as db:
        await _apply_clustering(db, bundle)

    assert bundle.development_count == 1
    assert bundle.corroborating_source_count == 2
    # deduped views collapse to one representative...
    assert len(bundle.deduped_events()) + len(bundle.deduped_news()) == 1
    # ...but nothing is deleted from the raw lists citations read.
    assert len(bundle.events) == 1
    assert len(bundle.news) == 1


@pytest.mark.asyncio
async def test_same_development_three_outlets_one_development_three_sources_preserved():
    now = datetime.now(timezone.utc)
    bundle = _bundle(news=[
        {"id": "n1", "headline": "RBI cuts repo rate by 25bps to 5.25%", "published_at": now.isoformat(), "source": "ET"},
        {"id": "n2", "headline": "RBI cuts repo rate 25bps, brings rate to 5.25%", "published_at": (now - timedelta(minutes=5)).isoformat(), "source": "Moneycontrol"},
        {"id": "n3", "headline": "RBI cuts repo rate by 25bps, rate now at 5.25%", "published_at": (now - timedelta(minutes=10)).isoformat(), "source": "NDTV Profit"},
    ])
    async with AsyncSessionLocal() as db:
        await _apply_clustering(db, bundle)

    assert bundle.development_count == 1
    assert bundle.corroborating_source_count == 3
    # All 3 raw news rows remain -- citations/source_attribution read these directly.
    assert len(bundle.news) == 3


@pytest.mark.asyncio
async def test_two_genuinely_different_developments_stay_two():
    now = datetime.now(timezone.utc)
    bundle = _bundle(events=[
        {"id": "e1", "title": "NTPC commissions new 800 MW solar plant in Rajasthan", "date": _now_str(), "category": "corporate", "impact_score": 7.0},
        {"id": "e2", "title": "Larsen and Toubro wins highway construction contract worth 5000 crore", "date": _now_str(), "category": "corporate", "impact_score": 7.0},
    ])
    async with AsyncSessionLocal() as db:
        await _apply_clustering(db, bundle)

    assert bundle.development_count == 2
    assert len(bundle.deduped_events()) == 2


@pytest.mark.asyncio
async def test_announcements_do_not_disappear_when_clustered_with_an_event():
    """The representative for a cluster prefers the Event (DETERMINISTIC),
    so the redundant member for PROMPT TEXT is the announcement -- but the
    raw announcements list (citations/get_recent_announcements-derived
    data) must be completely untouched."""
    now_iso = datetime.now(timezone.utc).isoformat()
    bundle = _bundle(
        events=[{"id": "nse-abc", "title": "Kitex Garments Limited has informed the Exchange about Copy of Newspaper Publication",
                  "date": _now_str(), "category": "corporate", "impact_score": 6.5}],
        announcements=[{"id": "ann_nse-abc", "subject": "Kitex Garments Limited has informed the Exchange about Copy of Newspaper Publication",
                          "announcement_date": now_iso, "category": "General"}],
    )
    async with AsyncSessionLocal() as db:
        await _apply_clustering(db, bundle)

    assert bundle.development_count == 1
    assert len(bundle.announcements) == 1          # raw list untouched
    assert len(bundle.deduped_announcements()) == 0  # redundant for PROMPT text (Event is representative)
    assert len(bundle.deduped_events()) == 1         # Event carries the merged story in the prompt


# ── Confidence/evidence-score correctness ───────────────────────────────────

def test_confidence_decreases_when_previously_inflated_by_duplicates():
    """Same raw evidence, scored two ways: as if source_count were still
    raw rows (pre-fix) vs. development_count (post-fix) when 3 of 4 rows
    are actually the same story."""
    pre_fix = calculate_confidence(ConfidenceFactors(source_count=4))  # old behavior: 4 raw rows
    post_fix = calculate_confidence(ConfidenceFactors(source_count=1, corroborating_source_count=4))  # 1 real development
    assert post_fix.total_score < pre_fix.total_score
    assert "independent development" in " ".join(post_fix.reasons)


def test_confidence_unchanged_when_evidence_was_already_independent():
    """No duplication -> development_count == raw count -> identical score
    to what the old formula would have given (this fix is a no-op when
    there's nothing to deduplicate)."""
    no_dup_old = calculate_confidence(ConfidenceFactors(source_count=3))
    no_dup_new = calculate_confidence(ConfidenceFactors(source_count=3, corroborating_source_count=3))
    assert no_dup_old.total_score == no_dup_new.total_score


def test_evidence_score_uses_development_count_not_raw_source_count():
    bundle = _bundle()
    bundle.development_count = 1
    bundle._evidence_clusters = []
    result = compute_evidence_score(bundle)
    assert result["development_count"] == 1
    assert "source_count" in result  # still present, unchanged raw diversity number


# ── Citations / attribution survive clustering ──────────────────────────────

@pytest.mark.asyncio
async def test_citations_source_attribution_unaffected_by_clustering():
    bundle = _bundle(
        events=[{"id": "e1", "title": "Same story", "date": _now_str(), "category": "corporate", "impact_score": 7.0}],
        news=[{"id": "n1", "headline": "Same story covered", "published_at": datetime.now(timezone.utc).isoformat(), "source": "ET"}],
    )
    async with AsyncSessionLocal() as db:
        await _apply_clustering(db, bundle)

    ids = bundle.to_source_ids()
    assert "event:e1" in ids
    assert "news:n1" in ids  # both present even though they clustered into 1 development


# ── Failure isolation ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_clustering_failure_falls_back_to_source_count_not_a_crash():
    bundle = _bundle(events=[{"id": "e1", "title": "X", "date": _now_str(), "category": "c", "impact_score": 5}])
    with patch("app.services.ai_search.evidence.cluster_evidence", AsyncMock(side_effect=RuntimeError("boom"))):
        async with AsyncSessionLocal() as db:
            await _apply_clustering(db, bundle)  # must not raise
    assert bundle.development_count == bundle.source_count


# ── Live, real-DB proof (matches this codebase's `_live` test convention) ───

@pytest.mark.asyncio
async def test_live_evidence_collection_produces_a_sane_development_count():
    from app.services.ai_search.evidence import collect
    async with AsyncSessionLocal() as db:
        bundle = await collect("Kitex Garments latest updates", {"intent": "general"}, {"companies": ["KITEX"]}, db)
    assert bundle.development_count <= bundle.corroborating_source_count
    assert bundle.development_count >= 0
