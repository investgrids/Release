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
