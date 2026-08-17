"""
Phase 5E.4 — Opportunity Radar scoring correctness.

Before this fix, `_score_opportunity` counted every raw NewsArticle-
derived dict in a sector group (`len(events) * 3`, capped +20 of ~39
possible bonus points — the single largest lever in the formula). Five
outlets covering the identical real story inflated the score exactly
as if 5 independent catalysts existed. Phase 5E's audit traced this to
the live scheduled job (`app/tasks/daily_tasks.py::job_daily_opportunities`,
`app/workers/opportunity_worker.py`) with no dedup step in between.

Fixed by clustering event_texts into unique developments (via the
shared evidence_clustering primitive built in 5E.3 — the same
title-overlap + time-proximity logic Weekend Intelligence already
proved works) and scoring on cluster count, not raw row count.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.db.session import AsyncSessionLocal
from app.pipeline.opportunity_generator import _cluster_event_dicts, _score_opportunity


def _ev(id_: str, title: str, summary: str = "", hours_ago: float = 0) -> dict:
    published = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
    return {"id": id_, "title": title, "summary": summary, "published_at": published.isoformat(), "category": "General"}


# ── The formula itself: shape/scale preserved, just a different input ──────

def test_score_formula_shape_matches_pre_fix_for_same_count():
    """Same numeric input (now unique_development_count instead of
    len(events)) must produce the identical score the old formula gave
    -- this proves the FIX is "which number feeds the formula", not a
    rewrite of the formula's scale/weighting."""
    # Old formula: 60 + min(20, 7*3) + min(10, 3*1.5) + min(10, 2*2) = 60+20+4.5+4 = 88.5
    score = _score_opportunity(7, ["A", "B", "C"], ["Sector1", "Sector2"])
    assert score == 88.5


def test_score_caps_at_99():
    score = _score_opportunity(50, ["A"] * 20, ["S"] * 20)
    assert score == 99.0


def test_score_floor_at_60_with_no_developments():
    score = _score_opportunity(0, [], [])
    assert score == 60.0


# ── The real fix: duplicate coverage no longer inflates the count ──────────

@pytest.mark.asyncio
async def test_duplicate_coverage_of_one_story_clusters_to_one_development():
    """The exact exploit found live: N outlets, 1 real story."""
    events = [
        _ev("a1", "HDFC Bank board approves Q1 results, profit up 12%", hours_ago=0),
        _ev("a2", "HDFC Bank Q1 results: profit rises 12%, board approves", hours_ago=1),
        _ev("a3", "HDFC Bank board approves quarterly results showing 12% profit growth", hours_ago=2),
    ]
    async with AsyncSessionLocal() as db:
        clusters = await _cluster_event_dicts(db, events)
    assert len(clusters) == 1

    old_score = _score_opportunity(len(events), [], [])       # pre-fix: 60 + min(20, 9) = 69
    new_score = _score_opportunity(len(clusters), [], [])     # post-fix: 60 + min(20, 3) = 63
    assert old_score == 69.0
    assert new_score == 63.0
    assert new_score < old_score  # the inflated score is gone


@pytest.mark.asyncio
async def test_genuinely_distinct_developments_still_count_separately():
    """The fix must not collapse real, unrelated stories -- a sector
    group with 3 genuinely different catalysts should still score for
    3 developments, not silently get squashed to 1."""
    events = [
        _ev("b1", "NTPC commissions new 800 MW solar power plant in Rajasthan", hours_ago=0),
        _ev("b2", "Larsen and Toubro wins major highway construction contract worth 5000 crore", hours_ago=1),
        _ev("b3", "Bharat Electronics secures defence order for radar systems", hours_ago=2),
    ]
    async with AsyncSessionLocal() as db:
        clusters = await _cluster_event_dicts(db, events)
    assert len(clusters) == 3

    score = _score_opportunity(len(clusters), [], [])
    assert score == 69.0  # 60 + min(20, 3*3=9)


@pytest.mark.asyncio
async def test_mixed_group_two_developments_one_with_double_coverage():
    events = [
        _ev("c1", "Tata Motors EV sales cross record monthly high in October", hours_ago=0),
        _ev("c2", "Tata Motors reports record EV sales for October, monthly high", hours_ago=1),
        _ev("c3", "Adani Enterprises announces new green hydrogen plant investment", hours_ago=0.5),
    ]
    async with AsyncSessionLocal() as db:
        clusters = await _cluster_event_dicts(db, events)
    assert len(clusters) == 2  # c1+c2 merge, c3 stays separate

    old_score = _score_opportunity(len(events), [], [])    # 60 + min(20, 9) = 69
    new_score = _score_opportunity(len(clusters), [], [])  # 60 + min(20, 6) = 66
    assert old_score == 69.0
    assert new_score == 66.0
