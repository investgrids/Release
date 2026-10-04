"""The filing-score read endpoint: 404 for everything while the flag is off; with the flag on it serves only the active run, with labels and N/A reasons."""
from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.filing_score import get_filing_score
from app.core.config import settings
from app.db.base import Base
from app.services.filing_score import store
from app.services.filing_score.pipeline import METHOD_VERSION


@pytest.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)() as s:
        yield s
    await engine.dispose()


async def _seed(db):
    run = await store.start_run(db, METHOD_VERSION)
    await store.write_snapshots(db, run, [
        {"symbol": "SCORED", "segment": "industrial", "state": "scored", "score": 61.2, "rating": "Positive", "financial_strength": 70.0, "valuation": 50.0, "market_behaviour": 60.0,
         "coverage_pct": 100.0, "metrics_used": 6, "metadata_flags": ["[P/E from filed EPS]"], "rule_tags": ["V2-Rule-4E-FiledEpsPE"], "metrics": {"roe": 12.0},
         "valuation_detail": {"pe": 20.0, "pb": 2.0}, "provenance": {"url": "https://nsearchives.nseindia.com/x.xml", "sha256": "abc", "period_end": "2026-03-31", "scope": "Consolidated"}},
        {"symbol": "WITHHELD", "segment": "industrial", "state": "withheld", "withheld_reason": "VALUATION_DATA_DISCREPANCY", "na_label": "N/A - Valuation Data Discrepancy"},
    ])
    await store.complete_run(db, run, {"scored": 1})
    await store.activate_run(db, run.id)
    await db.commit()


async def test_endpoint_is_404_for_every_symbol_while_the_flag_is_off(db_session, monkeypatch):
    await _seed(db_session)
    monkeypatch.setattr(settings, "filing_score_public", False)
    with pytest.raises(HTTPException) as e:
        await get_filing_score("SCORED", db_session)
    assert e.value.status_code == 404


async def test_flag_on_serves_scored_with_labels_and_withheld_with_a_reason(db_session, monkeypatch):
    await _seed(db_session)
    monkeypatch.setattr(settings, "filing_score_public", True)
    ok = await get_filing_score("scored", db_session)
    assert ok["score"] == 61.2 and ok["rating"] == "Positive" and ok["labels"] == ["[P/E from filed EPS]"] and ok["unavailable"] is None
    assert ok["source"]["filing_sha256"] == "abc" and ok["pillars"]["valuation"] == 50.0
    na = await get_filing_score("WITHHELD", db_session)
    assert na["score"] is None and na["rating"] is None and na["unavailable"] == {"reason": "VALUATION_DATA_DISCREPANCY", "label": "N/A - Valuation Data Discrepancy"}
    with pytest.raises(HTTPException):
        await get_filing_score("UNKNOWN", db_session)


async def test_nothing_is_served_before_a_run_is_activated(db_session, monkeypatch):
    monkeypatch.setattr(settings, "filing_score_public", True)
    run = await store.start_run(db_session, METHOD_VERSION)
    await store.write_snapshots(db_session, run, [{"symbol": "A", "segment": "industrial", "state": "scored", "score": 50.0, "rating": "Neutral"}])
    await store.complete_run(db_session, run, {})
    with pytest.raises(HTTPException):
        await get_filing_score("A", db_session)


async def test_admin_refresh_endpoint_never_activates_and_refuses_a_second_start(monkeypatch, tmp_path):
    from app.api import admin
    from app.services.filing_score import runner
    started = {}

    class FakeProc:
        pid = 4242

    def fake_popen(cmd, **kw):
        started["cmd"] = cmd
        return FakeProc()

    import subprocess
    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    monkeypatch.setattr(runner, "lock_path", lambda: tmp_path / "running.lock")
    out = await admin.filing_score_refresh(symbols="syrma, tcs")
    assert out["started"] is True and out["activates"] is False and "--activate" not in started["cmd"] and "SYRMA,TCS" in started["cmd"]
    (tmp_path / "running.lock").write_text("1")
    import os
    monkeypatch.setattr(runner, "_pid_alive", lambda pid: True)
    again = await admin.filing_score_refresh()
    assert again["started"] is False and "already running" in again["reason"]


async def _seed_two_segments(db):
    run = await store.start_run(db, METHOD_VERSION)
    await store.write_snapshots(db, run, [
        {"symbol": "KBANK", "segment": "bank", "state": "scored", "score": 47.7, "rating": "Neutral", "financial_strength": 53.9, "valuation": 12.8, "market_behaviour": 77.6, "coverage_pct": 80.0, "metrics_used": 5},
        {"symbol": "INDCO", "segment": "industrial", "state": "scored", "score": 61.2, "rating": "Positive"},
    ])
    await store.complete_run(db, run, {"scored": 2})
    await store.activate_run(db, run.id)
    await db.commit()


async def test_banks_only_release_serves_banks_and_404s_every_other_segment(db_session, monkeypatch):
    await _seed_two_segments(db_session)
    monkeypatch.setattr(settings, "filing_score_public", False)
    monkeypatch.setattr(settings, "filing_score_public_segments", "bank")
    assert (await get_filing_score("kbank", db_session))["score"] == 47.7
    with pytest.raises(HTTPException) as e:
        await get_filing_score("INDCO", db_session)
    assert e.value.status_code == 404


async def test_no_segments_and_flag_off_stays_fully_dark(db_session, monkeypatch):
    await _seed_two_segments(db_session)
    monkeypatch.setattr(settings, "filing_score_public", False)
    monkeypatch.setattr(settings, "filing_score_public_segments", "")
    with pytest.raises(HTTPException):
        await get_filing_score("KBANK", db_session)


async def test_admin_activate_requires_a_complete_run_with_enough_scores_and_rollback_restores(db_session):
    from app.api import admin
    first = await store.start_run(db_session, METHOD_VERSION)
    await store.complete_run(db_session, first, {"scored": 1500})
    second = await store.start_run(db_session, METHOD_VERSION)
    await store.complete_run(db_session, second, {"scored": 10})
    running = await store.start_run(db_session, METHOD_VERSION)
    await db_session.commit()
    with pytest.raises(HTTPException) as e:
        await admin.filing_score_activate(run_id=running.id, db=db_session)
    assert e.value.status_code == 400
    with pytest.raises(HTTPException) as e:
        await admin.filing_score_activate(run_id=second.id, db=db_session)
    assert e.value.status_code == 400 and "min_scored" in e.value.detail
    assert (await admin.filing_score_activate(run_id=first.id, db=db_session))["activated"] is True
    assert (await store.active_run(db_session, METHOD_VERSION)).id == first.id
    assert (await admin.filing_score_activate(run_id=second.id, min_scored=5, db=db_session))["activated"] is True
    out = await admin.filing_score_rollback(db=db_session)
    assert out["restored_run_id"] == first.id and (await store.active_run(db_session, METHOD_VERSION)).id == first.id


async def test_list_overlay_gives_released_banks_their_filing_score_only(db_session, monkeypatch):
    from app.api.companies import _overlay_filing_bank_scores
    await _seed_two_segments(db_session)
    mr = {"INDCO": {"marketripple_score": {"eligible": True, "publishable": True, "score": 70.0, "rating": "Positive"}}}
    monkeypatch.setattr(settings, "filing_score_public", False)
    monkeypatch.setattr(settings, "filing_score_public_segments", "")
    await _overlay_filing_bank_scores(db_session, ["KBANK", "INDCO"], mr)
    assert "KBANK" not in mr                                     # not released: nothing changes
    monkeypatch.setattr(settings, "filing_score_public_segments", "bank")
    await _overlay_filing_bank_scores(db_session, ["KBANK", "INDCO"], mr)
    assert mr["KBANK"]["marketripple_score"] == {"eligible": True, "publishable": True, "score": 47.7, "rating": "Neutral"}
    assert mr["INDCO"]["marketripple_score"]["score"] == 70.0    # a non-bank is never touched
