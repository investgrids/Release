"""The production refresh runs in its own process, one at a time, with its
status on disk (see refresh.py for the 2026-09-28 web-worker incident)."""
from __future__ import annotations

import json
import os

import pytest

from app.services.marketripple_score import refresh


@pytest.fixture
def tmp_reports(tmp_path, monkeypatch):
    monkeypatch.setattr(refresh, "_report_dir", lambda: tmp_path)
    monkeypatch.setattr(refresh, "_proc", None)
    return tmp_path


def test_status_idle_with_no_files(tmp_reports):
    assert refresh.refresh_status() == {"running": False, "pid": None, "progress": None, "last_run": None, "last_exit": None}


def test_status_reads_last_run_from_disk(tmp_reports):
    (tmp_reports / "last_run.json").write_text(json.dumps({"published": 390, "attempted": 425}))
    status = refresh.refresh_status()
    assert status["running"] is False
    assert status["last_run"]["published"] == 390


def test_refuses_to_start_while_a_run_is_alive(tmp_reports, monkeypatch):
    (tmp_reports / "running.lock").write_text(str(os.getpid()))
    monkeypatch.setattr(refresh, "_pid_alive", lambda pid: True)
    started = []
    monkeypatch.setattr(refresh.subprocess, "Popen", lambda *a, **k: started.append(a))
    result = refresh.start_refresh_process()
    assert result["started"] is False
    assert started == []


def test_stale_lock_does_not_block_a_new_run(tmp_reports, monkeypatch):
    (tmp_reports / "running.lock").write_text("999999")
    monkeypatch.setattr(refresh, "_pid_alive", lambda pid: False)

    class _FakeProc:
        pid = 4242

        def poll(self):
            return None

    calls = []
    monkeypatch.setattr(refresh.subprocess, "Popen", lambda cmd, **k: calls.append(cmd) or _FakeProc())
    result = refresh.start_refresh_process(include_banks=False)
    assert result == {"started": True, "pid": 4242, "sectors": None}
    assert calls[0][-2:] == ["scripts/run_marketripple_score_refresh.py", "--no-banks"]
    assert (tmp_reports / "running.lock").read_text() == "4242"


@pytest.mark.asyncio
async def test_sector_refresh_shares_dated_benchmarks_and_fixed_cutoff(tmp_reports, monkeypatch):
    from datetime import date

    import app.services.marketripple_score.financial_strength_industrial as industrial
    import app.services.marketripple_score.market_behaviour as market_behaviour
    import app.services.marketripple_score.valuation as valuation

    async def _prefetch(_symbols):
        return {}

    fetched = []

    def _fetch_observations(ticker):
        fetched.append(ticker)
        return [("2026-09-29", 123.45)]

    captured = {}

    async def _build_and_commit(_sector, groups, _tally):
        captured.update(groups[0][3])
        return {"candidates": len(groups[0][1])}

    monkeypatch.setattr(industrial, "prefetch_industrial_inputs", _prefetch)
    monkeypatch.setattr(valuation, "prefetch_valuation_snapshots", _prefetch)
    monkeypatch.setattr(market_behaviour, "_fetch_daily_close_observations_sync", _fetch_observations)
    monkeypatch.setattr(refresh, "_build_and_commit", _build_and_commit)

    stats = await refresh._refresh_sector(
        "Technology", ["TEST"], {"attempted": 0, "published": 0, "errors": []},
        market_cutoff_date=date(2026, 9, 29),
    )

    assert stats["candidates"] == 1
    assert stats["prefetch_s"] >= 0.0
    assert stats["elapsed_s"] >= stats["prefetch_s"]
    assert fetched and "^NSEI" in fetched
    assert captured["benchmarks"]["^NSEI"] == [("2026-09-29", 123.45)]
    assert captured["market_cutoff_date"] == "2026-09-29"
    assert captured["benchmarks_fetched_at"]


@pytest.mark.asyncio
async def test_sector_with_any_failed_company_commits_nothing(tmp_reports, monkeypatch):
    """All-or-nothing (2026-10-03 pilot): one failed company must leave the whole
    sector untouched, so Rankings never mixes old and new peer sets."""
    from datetime import datetime, timezone

    from sqlalchemy import select

    import app.services.marketripple_score.snapshot as snapshot_mod
    from app.db.models.marketripple_score_snapshot import MarketRippleScoreSnapshot
    from app.db.session import AsyncSessionLocal

    async def _build(db, symbol, peer_group=None, industrial_cache=None, peer_group_name=None):
        if symbol == "ZBOOM":
            raise TypeError("'<' not supported between instances of 'str' and 'float'")
        return MarketRippleScoreSnapshot(
            symbol=symbol, score=50.0, rating="Neutral", coverage_pct=100.0, methodology_version="MARKETRIPPLE_SCORE_V1",
            peer_universe=[], calculated_at=datetime.now(timezone.utc), publishable=False, publication_block_reasons=["X"])

    async def _none(_symbols):
        return {}

    monkeypatch.setattr(snapshot_mod, "build_snapshot", _build)
    monkeypatch.setattr(refresh, "_previous_published", _none)

    async def _no_sleep(_):
        return None
    monkeypatch.setattr(refresh.asyncio, "sleep", _no_sleep)

    tally = {"attempted": 0, "published": 0, "errors": [], "numeric": 0, "partial": 0, "unusable": 0,
             "ratings": {}, "block_reasons": {}, "missing_pillars": {}}
    stats = await refresh._build_and_commit("Metals", [(None, ["ZOK1", "ZBOOM", "ZOK2"], None, None)], tally)
    assert stats["committed"] is False and stats["errors"] == 1
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(select(MarketRippleScoreSnapshot).where(MarketRippleScoreSnapshot.symbol.in_(["ZOK1", "ZOK2", "ZBOOM"])))).scalars().all()
    assert rows == []  # the two that built fine were NOT committed either
