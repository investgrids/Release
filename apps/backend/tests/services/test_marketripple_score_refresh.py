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
    assert result == {"started": True, "pid": 4242}
    assert calls[0][-2:] == ["scripts/run_marketripple_score_refresh.py", "--no-banks"]
    assert (tmp_reports / "running.lock").read_text() == "4242"


@pytest.mark.asyncio
async def test_sector_refresh_shares_dated_benchmarks_and_one_fixed_cutoff(tmp_reports, monkeypatch):
    """Every company in a sector is scored against the same completed
    sessions: benchmarks are fetched once, as dated closes, with one retrieval
    time and the run's single cutoff date."""
    from datetime import date

    import app.services.marketripple_score.financial_strength_industrial as industrial
    import app.services.marketripple_score.market_behaviour as market_behaviour
    import app.services.marketripple_score.sector_universe as sector_universe
    import app.services.marketripple_score.valuation as valuation

    async def _prefetch(_symbols):
        return {}

    fetched = []

    def _fetch_observations(ticker):
        fetched.append(ticker)
        return [("2026-09-29", 123.45)]

    captured = {}

    async def _persist(symbol, cache, _tally):
        captured.update(cache)

    monkeypatch.setattr(industrial, "prefetch_industrial_inputs", _prefetch)
    monkeypatch.setattr(valuation, "prefetch_valuation_snapshots", _prefetch)
    monkeypatch.setattr(market_behaviour, "_fetch_daily_close_observations_sync", _fetch_observations)
    monkeypatch.setattr(sector_universe, "sector_peer_universe", lambda _sector: ["TEST"])
    monkeypatch.setattr(refresh, "_persist", _persist)

    async def _no_sleep(_):
        return None
    monkeypatch.setattr(refresh.asyncio, "sleep", _no_sleep)

    await refresh._refresh_sector(
        "Technology", {"attempted": 0, "published": 0, "errors": []}, market_cutoff_date=date(2026, 9, 29),
    )

    assert "^NSEI" in fetched
    assert captured["benchmarks"]["^NSEI"] == [("2026-09-29", 123.45)]
    assert captured["market_cutoff_date"] == "2026-09-29"
    assert captured["benchmarks_fetched_at"]
