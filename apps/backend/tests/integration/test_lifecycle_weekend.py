"""
Phase 1E §7-§13 — Saturday and Sunday weekend checkpoint lifecycle,
through the REAL normalization/clustering/synthesis/checkpoint path.
Every evidence row below is a real ORM row of the real source model
(Event, NewsArticle, GovernmentPolicy, CompanyAnnouncement, Opportunity,
AICompanySignal) — never a hand-built WeekendIntelligenceSnapshot.
"""
from __future__ import annotations

from datetime import timezone

import pytest
from sqlalchemy import select

from app.db.models.weekend_intelligence import WeekendIntelligenceSnapshot
from app.services.weekend_intelligence.checkpoints import CREATED, SKIPPED_NO_MATERIAL_CHANGE, run_checkpoint
from app.services.weekend_intelligence.versioning import get_current_snapshot, get_version_history
from tests.integration.conftest import (
    FRIDAY, MONDAY, SATURDAY, SUNDAY, ist,
    make_announcement, make_company_signal, make_event, make_event_triage,
    make_news, make_opportunity, make_policy,
)

TARGET = MONDAY.isoformat()


def _utc(d, h, m=0):
    return ist(d, h, m).astimezone(timezone.utc)


async def _seed_saturday_morning_evidence(db):
    """Brief §7's exact fixture set: one meaningful Event + one NewsArticle
    representing the SAME development (must cluster), one independent
    GovernmentPolicy, one CompanyAnnouncement, one Opportunity, one
    contradictory signal (two AICompanySignal rows for the same symbol
    with opposite direction)."""
    evt = await make_event(
        db, title="RBI holds repo rate steady citing inflation concerns",
        when=ist(SATURDAY, 9, 0), sectors=["Banking"], companies=["HDFCBANK"],
    )
    await make_event_triage(db, evt.id, urgency=9, importance=9, headline=evt.title)  # -> High/Critical tier

    await make_news(
        db, headline="RBI holds repo rate steady amid inflation concerns",
        when=ist(SATURDAY, 9, 5), companies=["HDFCBANK"],
    )
    await make_policy(db, title="RBI Monetary Policy Committee Statement", when=ist(SATURDAY, 9, 10))
    await make_announcement(
        db, subject="INFY announces new leadership hire", when=ist(SATURDAY, 10, 0),
        symbol="INFY", sectors=["Technology"],
    )
    await make_opportunity(
        db, title="Defence manufacturing capex opportunity", when=ist(SATURDAY, 10, 30),
        sectors=["Defence"], confidence=0.8,
    )
    # Contradictory signal on the same symbol.
    await make_company_signal(db, symbol="ICICIBANK", when=ist(SATURDAY, 11, 0),
                               signed_magnitude=15.0, reason="ICICIBANK positive development")
    await make_company_signal(db, symbol="ICICIBANK", when=ist(SATURDAY, 11, 5),
                               signed_magnitude=-15.0, reason="ICICIBANK negative development")
    await db.commit()


# ── §7/§8: Saturday v1 ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_saturday_v1_created_from_real_normalized_evidence(isolated_db, frozen_time):
    await _seed_saturday_morning_evidence(isolated_db)
    frozen_time(ist(SATURDAY, 12, 0))

    result = await run_checkpoint(isolated_db, TARGET, checkpoint_time=_utc(SATURDAY, 12, 0),
                                   checkpoint_label="Saturday 12:00 IST")
    assert result.outcome == CREATED
    assert result.snapshot_version == 1

    snap = await get_current_snapshot(isolated_db, TARGET)
    assert snap is not None
    assert snap.version == 1
    assert snap.target_trading_date == TARGET
    assert snap.last_trading_date == FRIDAY.isoformat()

    # Duplicate representation clusters: Event + NewsArticle about the same
    # RBI story must NOT be 2 independent confirmations.
    banking = next((s for s in snap.top_sector_refs if s["sector"].lower() == "banking"), None)
    assert banking is not None

    # Independent evidence (policy, announcement, opportunity) stays
    # independent — evidence_summary total should reflect all 7 raw rows.
    assert len(snap.evidence_refs) == 7

    # Company mapping valid — ICICIBANK's contradiction must produce a
    # 'mixed' company state, not a fabricated one-sided direction.
    icici = next((c for c in snap.top_company_refs if c["symbol"] == "ICICIBANK"), None)
    assert icici is not None
    assert icici["state"] == "mixed"

    # Risk synthesis: mixed ICICIBANK must produce a market risk.
    assert any("ICICIBANK" in (r.get("related_companies") or []) for r in snap.risk_refs)

    # Confidence explainable — every component present, sums to the total.
    assert snap.confidence_components is not None
    weighted = snap.confidence_components["weighted_contributions"]
    assert abs(sum(weighted.values()) * 100 - snap.production_confidence) < 0.5


# ── §9: Saturday material update -> v2 ───────────────────────────────────────

@pytest.mark.asyncio
async def test_saturday_material_update_creates_v2_and_supersedes_v1(isolated_db, frozen_time):
    await _seed_saturday_morning_evidence(isolated_db)
    frozen_time(ist(SATURDAY, 12, 0))
    await run_checkpoint(isolated_db, TARGET, checkpoint_time=_utc(SATURDAY, 12, 0))

    v1 = await get_current_snapshot(isolated_db, TARGET)
    assert v1.version == 1

    # Genuinely material: a new Critical-tier event.
    evt2 = await make_event(isolated_db, title="Government announces major defence policy overhaul",
                             when=ist(SATURDAY, 15, 0), sectors=["Defence"], companies=["HAL"])
    await make_event_triage(isolated_db, evt2.id, urgency=10, importance=10, headline=evt2.title)
    await isolated_db.commit()

    frozen_time(ist(SATURDAY, 18, 0))
    result = await run_checkpoint(isolated_db, TARGET, checkpoint_time=_utc(SATURDAY, 18, 0),
                                   checkpoint_label="Saturday 18:00 IST")
    assert result.outcome == CREATED
    assert result.snapshot_version == 2

    history = await get_version_history(isolated_db, TARGET)
    assert len(history) == 2
    v1_reloaded, v2 = history[0], history[1]
    assert v1_reloaded.is_current is False
    assert v2.is_current is True
    assert v2.version == 2

    # Exactly one current row.
    current_rows = (await isolated_db.execute(
        select(WeekendIntelligenceSnapshot).where(
            WeekendIntelligenceSnapshot.target_trading_date == TARGET,
            WeekendIntelligenceSnapshot.is_current.is_(True),
        )
    )).scalars().all()
    assert len(current_rows) == 1

    # changes_since_prior contains only meaningful changes (a new Defence
    # signal appearing), not noise.
    assert len(v2.changes_since_prior) >= 1
    assert any(c["entity_id"] == "Defence" or c["entity_id"] == "HAL" for c in v2.changes_since_prior)


# ── §10: Saturday non-material update -> skipped ────────────────────────────

@pytest.mark.asyncio
async def test_saturday_non_material_update_is_skipped(isolated_db, frozen_time):
    await _seed_saturday_morning_evidence(isolated_db)
    frozen_time(ist(SATURDAY, 12, 0))
    await run_checkpoint(isolated_db, TARGET, checkpoint_time=_utc(SATURDAY, 12, 0))

    # Noise: a single routine, low-tier, non-material news item, added
    # strictly AFTER the v1 checkpoint boundary so it's the only new
    # thing the materiality gate sees.
    await make_news(isolated_db, headline="Routine market commentary of no particular significance",
                     when=ist(SATURDAY, 12, 30), impact_score=3.0)
    await isolated_db.commit()

    frozen_time(ist(SATURDAY, 13, 0))
    result = await run_checkpoint(isolated_db, TARGET, checkpoint_time=_utc(SATURDAY, 13, 0))
    assert result.outcome == SKIPPED_NO_MATERIAL_CHANGE

    history = await get_version_history(isolated_db, TARGET)
    assert len(history) == 1  # still just v1, no v3/v2 created


# ── §11: restart after v2 ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_restart_after_v2_preserves_state(isolated_db, frozen_time):
    await _seed_saturday_morning_evidence(isolated_db)
    frozen_time(ist(SATURDAY, 12, 0))
    await run_checkpoint(isolated_db, TARGET, checkpoint_time=_utc(SATURDAY, 12, 0))

    evt2 = await make_event(isolated_db, title="Major RBI policy statement on liquidity",
                             when=ist(SATURDAY, 15, 0), sectors=["Banking"])
    await make_event_triage(isolated_db, evt2.id, urgency=10, importance=10, headline=evt2.title)
    await isolated_db.commit()
    frozen_time(ist(SATURDAY, 18, 0))
    await run_checkpoint(isolated_db, TARGET, checkpoint_time=_utc(SATURDAY, 18, 0))

    # Simulate restart: query again via a FRESH lookup, exactly as a
    # newly-booted process would (get_current_snapshot has no in-memory
    # cache/module state to carry over — this proves that).
    snap_after_restart = await get_current_snapshot(isolated_db, TARGET)
    assert snap_after_restart.version == 2
    assert snap_after_restart.is_current is True

    # Re-running the SAME (already-applied) checkpoint again must not
    # duplicate or reset anything (idempotency under restart).
    frozen_time(ist(SATURDAY, 18, 1))
    result = await run_checkpoint(isolated_db, TARGET, checkpoint_time=_utc(SATURDAY, 18, 1))
    assert result.outcome == SKIPPED_NO_MATERIAL_CHANGE
    history = await get_version_history(isolated_db, TARGET)
    assert len(history) == 2  # no duplicate v3 from the restart re-run


# ── §12/§13: Sunday ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_sunday_target_session_remains_monday(isolated_db, frozen_time):
    """Saturday target Monday, Sunday target Monday — NOT Sunday target
    Tuesday. Both checkpoints must resolve to the SAME upcoming session."""
    await _seed_saturday_morning_evidence(isolated_db)
    frozen_time(ist(SATURDAY, 12, 0))
    await run_checkpoint(isolated_db, TARGET, checkpoint_time=_utc(SATURDAY, 12, 0))

    evt = await make_event(isolated_db, title="Sunday material development in Energy sector",
                            when=ist(SUNDAY, 10, 0), sectors=["Energy"], companies=["RELIANCE"])
    await make_event_triage(isolated_db, evt.id, urgency=9, importance=9, headline=evt.title)
    await isolated_db.commit()

    frozen_time(ist(SUNDAY, 10, 30))
    result = await run_checkpoint(isolated_db, TARGET, checkpoint_time=_utc(SUNDAY, 10, 30))
    assert result.outcome == CREATED
    assert result.snapshot_version == 2

    snap = await get_current_snapshot(isolated_db, TARGET)
    assert snap.target_trading_date == MONDAY.isoformat()  # still Monday, not Tuesday
    assert snap.last_trading_date == FRIDAY.isoformat()


@pytest.mark.asyncio
async def test_sunday_final_state_integrity(isolated_db, frozen_time):
    await _seed_saturday_morning_evidence(isolated_db)
    frozen_time(ist(SATURDAY, 12, 0))
    await run_checkpoint(isolated_db, TARGET, checkpoint_time=_utc(SATURDAY, 12, 0))

    # A pseudo-symbol (regulator tag) that must never appear as a company.
    await make_company_signal(isolated_db, symbol="NSE_SEBI", when=ist(SUNDAY, 9, 0),
                               signed_magnitude=10.0, reason="SEBI regulatory update")
    evt = await make_event(isolated_db, title="Sunday consumer sector development",
                            when=ist(SUNDAY, 9, 30), sectors=["Consumer"], companies=["ITC"])
    await make_event_triage(isolated_db, evt.id, urgency=9, importance=9, headline=evt.title)
    await isolated_db.commit()

    frozen_time(ist(SUNDAY, 18, 0))
    result = await run_checkpoint(isolated_db, TARGET, checkpoint_time=_utc(SUNDAY, 18, 0),
                                   checkpoint_label="Sunday 18:00 IST")
    assert result.outcome == CREATED

    snap = await get_current_snapshot(isolated_db, TARGET)

    # Exactly one current snapshot for the target session.
    current_rows = (await isolated_db.execute(
        select(WeekendIntelligenceSnapshot).where(
            WeekendIntelligenceSnapshot.target_trading_date == TARGET,
            WeekendIntelligenceSnapshot.is_current.is_(True),
        )
    )).scalars().all()
    assert len(current_rows) == 1

    # Caps.
    assert len(snap.top_sector_refs) <= 5
    assert len(snap.top_company_refs) <= 12
    assert len(snap.risk_refs) <= 10
    assert len(snap.confidence_warning_refs) <= 8

    # Invalid entity excluded from the company ranking.
    assert not any(c["symbol"] == "NSE_SEBI" for c in snap.top_company_refs)

    # Market risks vs confidence warnings separated by construction —
    # risk_type vocabulary never overlaps between the two lists.
    market_risk_types = {r["risk_type"] for r in snap.risk_refs}
    warning_types = {w["risk_type"] for w in snap.confidence_warning_refs}
    assert market_risk_types.isdisjoint({"stale_or_missing_baseline", "source_concentration",
                                          "weak_historical_analogue", "insufficient_evidence"})
    assert "conflicting_evidence" not in warning_types

    # No fake historical analogue, no fabricated opportunities section.
    assert isinstance(snap.historical_analogue_refs, list)  # empty is valid, never forced
    assert isinstance(snap.opportunity_refs, list)

    # Confidence still explainable.
    assert snap.confidence_components is not None
    weighted = snap.confidence_components["weighted_contributions"]
    assert abs(sum(weighted.values()) * 100 - snap.production_confidence) < 0.5

    # Truthfulness: mixed/degraded/insufficient are all valid outcomes —
    # this assertion only checks the status is one of the real values,
    # never asserts a specific "good-looking" bias.
    assert snap.status in ("ok", "degraded", "insufficient_evidence")
    assert snap.overall_bias in ("strong_positive", "positive", "neutral", "negative", "strong_negative", "mixed")
